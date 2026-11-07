import hashlib
import json

import pytest

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.local_ingestion import ingest_local
from ragforge.ingestion.manifest import (
    SnapshotFile,
    SnapshotManifest,
    build_snapshot_manifest,
    diff_snapshots,
)


def test_snapshot_manifest_is_order_independent_and_content_addressed():
    first = SnapshotFile("src/b.py", 1, hashlib.sha256(b"b").hexdigest(), True)
    second = SnapshotFile("src/a.py", 1, hashlib.sha256(b"a").hexdigest(), True)
    config = IngestionConfig()
    one = build_snapshot_manifest("repository-stable-id", [first, second], config)
    two = build_snapshot_manifest("repository-stable-id", [second, first], config)
    assert one.snapshot_id == two.snapshot_id
    assert one.files == (second, first)
    assert one.repository_id == "repository-stable-id"
    assert json.dumps(one.to_dict(), sort_keys=True) == json.dumps(two.to_dict(), sort_keys=True)


def test_ingesting_identical_trees_at_different_roots_has_same_snapshot_id(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root in (left, right):
        (root / "app.py").write_bytes(b"# comment\r\nvalue = 'caf\xc3\xa9'\r\n")
        (root / "empty.py").write_bytes(b"")
    one = ingest_local(left, repository_id="same-project")
    two = ingest_local(right, repository_id="same-project")
    assert one.snapshot_id == two.snapshot_id
    assert one.snapshot_manifest is not None
    assert one.snapshot_manifest.files[0].source_hash == hashlib.sha256(
        b"# comment\r\nvalue = 'caf\xc3\xa9'\r\n"
    ).hexdigest()
    assert one.snapshot_manifest.files[1].skip_reason == "empty_file"
    assert one.snapshot_manifest.files[1].source_hash == hashlib.sha256(b"").hexdigest()


def test_stable_repository_identity_is_part_of_snapshot_hash_but_root_is_not(tmp_path):
    one_root, two_root = tmp_path / "one", tmp_path / "two"
    one_root.mkdir()
    two_root.mkdir()
    for root in (one_root, two_root):
        (root / "module.py").write_bytes(b"x = 1\n")
    one = ingest_local(one_root, repository_id="same-project")
    two = ingest_local(two_root, repository_id="same-project")
    assert one.snapshot_id == two.snapshot_id
    different_repository = ingest_local(two_root, repository_id="other-project")
    assert different_repository.snapshot_id != one.snapshot_id


def test_edit_changes_only_that_file_hash_and_snapshot_identity(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("value = 1\n", encoding="utf-8")
    (root / "b.py").write_text("value = 2\n", encoding="utf-8")
    original = ingest_local(root, repository_id="sample-project")
    (root / "a.py").write_text("value = 3\n", encoding="utf-8")
    changed = ingest_local(root, repository_id="sample-project")
    before = {item.file_path: item.source_hash for item in original.snapshot_manifest.files}
    after = {item.file_path: item.source_hash for item in changed.snapshot_manifest.files}
    assert before["a.py"] != after["a.py"]
    assert before["b.py"] == after["b.py"]
    assert original.snapshot_id != changed.snapshot_id


def test_oversized_file_manifest_uses_bounded_exact_byte_hash(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    raw = b"x" * 8193
    (root / "big.py").write_bytes(raw)
    config = IngestionConfig(max_file_size_bytes=10)
    result = ingest_local(root, config=config, repository_id="large-project")
    repeated = ingest_local(root, config=config, repository_id="large-project")
    entry = result.snapshot_manifest.files[0]
    assert entry.skip_reason == "file_too_large"
    assert entry.source_hash == hashlib.sha256(raw).hexdigest()
    assert entry.processed is False
    assert result.documents == ()
    assert result.snapshot_id == repeated.snapshot_id
    assert result.snapshot_manifest.to_dict() == repeated.snapshot_manifest.to_dict()


def test_snapshot_manifest_rejects_duplicate_or_unsorted_paths():
    a = SnapshotFile("a.py", 1, "0" * 64, True)
    with pytest.raises(ValueError, match="duplicate"):
        build_snapshot_manifest("repo", [a, a], IngestionConfig())
    with pytest.raises(ValueError, match="sorted and unique"):
        SnapshotManifest(
            "repo",
            "0" * 64,
            (SnapshotFile("b.py", 1, "0" * 64, True), a),
            "0" * 64,
        )


def test_snapshot_diff_is_sorted_and_reports_added_removed_modified():
    old = build_snapshot_manifest(
        "repo",
        [
            SnapshotFile("same.py", 1, "a" * 64, True),
            SnapshotFile("gone.py", 1, "b" * 64, True),
            SnapshotFile("edit.py", 1, "c" * 64, True),
        ],
        IngestionConfig(),
    )
    new = build_snapshot_manifest(
        "repo",
        [
            SnapshotFile("same.py", 1, "a" * 64, True),
            SnapshotFile("edit.py", 1, "d" * 64, True),
            SnapshotFile("new.py", 1, "e" * 64, True),
        ],
        IngestionConfig(),
    )
    assert [(change.file_path, change.change_type) for change in diff_snapshots(old, new)] == [
        ("edit.py", "modified"),
        ("gone.py", "removed"),
        ("new.py", "added"),
    ]
    assert diff_snapshots(old, old) == ()


def test_snapshot_diff_detects_size_status_and_skip_reason_changes():
    old = build_snapshot_manifest(
        "repo",
        [SnapshotFile("a.py", 4, "a" * 64, False, "file_too_large")],
        IngestionConfig(),
    )
    new = build_snapshot_manifest(
        "repo",
        [SnapshotFile("a.py", 5, "b" * 64, False, "binary_file")],
        IngestionConfig(),
    )
    changes = diff_snapshots(old, new)
    assert [(item.file_path, item.change_type) for item in changes] == [("a.py", "modified")]


def test_snapshot_diff_rejects_different_repository_identities():
    files = [SnapshotFile("a.py", 1, "a" * 64, True)]
    first = build_snapshot_manifest("repo-a", files, IngestionConfig())
    second = build_snapshot_manifest("repo-b", files, IngestionConfig())
    with pytest.raises(ValueError, match="different repositories"):
        diff_snapshots(first, second)


def test_snapshot_id_includes_ingestion_configuration_and_empty_manifest_is_stable(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    default_config = IngestionConfig()
    same_config = IngestionConfig(
        include_extensions=frozenset(reversed(sorted(default_config.include_extensions)))
    )
    one = ingest_local(root, config=default_config, repository_id="empty-project")
    two = ingest_local(root, config=same_config, repository_id="empty-project")
    changed = ingest_local(
        root,
        config=IngestionConfig(max_file_size_bytes=default_config.max_file_size_bytes - 1),
        repository_id="empty-project",
    )
    assert one.snapshot_manifest.files == ()
    assert one.snapshot_id == two.snapshot_id
    assert one.snapshot_id != changed.snapshot_id


def test_file_creation_order_and_repeated_runs_do_not_change_snapshot_id(tmp_path):
    first_root, second_root = tmp_path / "checkout-a", tmp_path / "checkout-b"
    first_root.mkdir()
    second_root.mkdir()
    for name, content in (("b.py", b"b=2\n"), ("a.py", b"a=1\n")):
        (first_root / name).write_bytes(content)
    for name, content in (("a.py", b"a=1\n"), ("b.py", b"b=2\n")):
        (second_root / name).write_bytes(content)
    first = ingest_local(first_root, repository_id="ordered-project")
    repeated = ingest_local(first_root, repository_id="ordered-project")
    other_creation_order = ingest_local(second_root, repository_id="ordered-project")
    assert first.snapshot_id == repeated.snapshot_id == other_creation_order.snapshot_id
    assert first.snapshot_manifest.to_dict() == other_creation_order.snapshot_manifest.to_dict()
