import hashlib
import zipfile

import pytest

from ragforge.ingestion import IngestionConfig, ingest_zip
from ragforge.ingestion.resolvers import zip as zip_resolver
from ragforge.ingestion.resolvers.zip import resolve_zip


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_ingests_multiple_nested_repository_files(tmp_path):
    archive_path = make_zip(tmp_path / "sample.zip", {
        "project/src/app.py": "print('hello')\n",
        "project/docs/guide.md": "# Guide\n",
        "project/config.yaml": "enabled: true\n",
        "project/data.bin": b"\x00\x01",
    })

    result = ingest_zip(archive_path)

    assert result.repository.name == "sample"
    assert result.repository.source_type == "zip"
    assert result.discovered_files == 3
    assert result.processed_files == 3
    documents = {document.file_path: document for document in result.documents}
    assert set(documents) == {"project/src/app.py", "project/docs/guide.md", "project/config.yaml"}
    assert documents["project/src/app.py"].language == "python"
    assert documents["project/docs/guide.md"].language == "markdown"
    assert documents["project/src/app.py"].line_count == 1
    assert documents["project/src/app.py"].content_hash == hashlib.sha256(
        "print('hello')\n".encode()
    ).hexdigest()
    assert all("ragforge-zip-" not in document.file_path for document in result.documents)


def test_zip_identity_is_independent_of_archive_location_and_entry_order(tmp_path):
    files = [("repo/src/app.py", b"print('hello')\n"), ("repo/README.md", b"# demo\n")]
    first_path = tmp_path / "one" / "first.zip"
    second_path = tmp_path / "different" / "second.zip"
    first_path.parent.mkdir()
    second_path.parent.mkdir()
    for path, entries in ((first_path, files), (second_path, list(reversed(files)))):
        with zipfile.ZipFile(path, "w") as archive:
            for name, content in entries:
                archive.writestr(name, content)

    first = ingest_zip(first_path)
    second = ingest_zip(second_path)

    assert first.repository.repository_id.startswith("zip:")
    assert first.repository.repository_id == second.repository.repository_id
    assert first.snapshot_id == second.snapshot_id
    assert first.snapshot_manifest.to_dict() == second.snapshot_manifest.to_dict()


def test_zip_identity_changes_when_archive_file_content_changes(tmp_path):
    first_path = make_zip(tmp_path / "one.zip", {"repo/app.py": "value = 1\n"})
    second_path = make_zip(tmp_path / "two.zip", {"repo/app.py": "value = 2\n"})

    first = ingest_zip(first_path)
    second = ingest_zip(second_path)

    assert first.repository.repository_id != second.repository.repository_id
    assert first.snapshot_id != second.snapshot_id


def test_zip_identity_is_independent_of_archive_filename_and_parent(tmp_path):
    content = {"repo/app.py": "value = 1\n"}
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first_path = make_zip(tmp_path / "a" / "first.zip", content)
    second_path = make_zip(tmp_path / "b" / "renamed.zip", content)

    first = resolve_zip(first_path, tmp_path / "extract-a")
    second = resolve_zip(second_path, tmp_path / "extract-b")

    assert first.repository.repository_id == second.repository.repository_id
    assert first.repository.source_uri != second.repository.source_uri


def test_rejects_zip_path_traversal_without_extracting_outside_root(tmp_path):
    archive_path = make_zip(tmp_path / "traversal.zip", {"repo/../../escape.py": "bad"})
    extraction_root = tmp_path / "extract"
    with pytest.raises(ValueError, match="Unsafe ZIP entry path"):
        resolve_zip(archive_path, extraction_root)
    assert not (tmp_path / "escape.py").exists()


def test_scanner_filters_apply_to_extracted_files(tmp_path):
    archive_path = make_zip(tmp_path / "filter.zip", {
        "repo/empty.py": "",
        "repo/unsupported.xyz": "skip",
        "repo/.hidden.py": "skip",
        "repo/node_modules/ignored.py": "skip",
        "repo/large.py": "x" * 32,
        "repo/good.py": "ok",
    })
    result = ingest_zip(archive_path, IngestionConfig(max_file_size_bytes=8))
    assert [doc.file_path for doc in result.documents] == ["repo/good.py"]
    assert result.discovered_files == 3
    assert result.processed_files == 1
    assert result.skipped_files == 2
    assert result.skip_reasons == {"empty_file": 1, "file_too_large": 1}


def test_extraction_directory_is_cleaned_and_documents_survive(tmp_path, monkeypatch):
    archive_path = make_zip(tmp_path / "cleanup.zip", {"app.py": "print(1)"})
    observed = []
    original = zip_resolver.resolve_zip

    def recording_resolve(source, destination):
        snapshot = original(source, destination)
        observed.append((snapshot.root_path, (snapshot.root_path / "app.py").exists()))
        return snapshot

    monkeypatch.setattr("ragforge.ingestion.zip_ingestion.resolve_zip", recording_resolve)
    result = ingest_zip(archive_path)
    assert observed[0][1] is True
    assert observed[0][0].exists() is False
    assert result.documents[0].content == "print(1)"


@pytest.mark.parametrize(
    "filename",
    ["../escape.py", "/absolute.py", "C:/drive.py", "..\\escape.py", "\\\\server\\share.py"],
)
def test_rejects_unsafe_paths(tmp_path, filename):
    archive_path = make_zip(tmp_path / "unsafe.zip", {filename: "bad"})
    with pytest.raises(ValueError, match="Unsafe ZIP entry path"):
        resolve_zip(archive_path, tmp_path / "extract")
    assert not (tmp_path / "escape.py").exists()


def test_rejects_symlink_entry(tmp_path):
    archive_path = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("link")
    info.create_system = 3
    info.external_attr = (0o120777 << 16)
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(info, "target")
    with pytest.raises(ValueError, match="Symbolic links"):
        resolve_zip(archive_path, tmp_path / "extract")


@pytest.mark.parametrize("kind", ["missing", "invalid", "empty"])
def test_rejects_missing_invalid_and_empty_archives(tmp_path, kind):
    path = tmp_path / "archive.zip"
    if kind == "invalid":
        path.write_text("not a zip")
    elif kind == "empty":
        with zipfile.ZipFile(path, "w"):
            pass
    with pytest.raises((ValueError, FileNotFoundError)):
        resolve_zip(path if kind != "missing" else tmp_path / "missing.zip", tmp_path / "extract")


def test_rejects_corrupted_zip_member(tmp_path):
    archive_path = tmp_path / "corrupted.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("app.py", "print('valid')")
        info = archive.getinfo("app.py")
        data_offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    damaged = bytearray(archive_path.read_bytes())
    damaged[data_offset] ^= 0x01
    archive_path.write_bytes(damaged)
    with pytest.raises(ValueError, match="Corrupted ZIP member"):
        resolve_zip(archive_path, tmp_path / "extract")


def test_enforces_entry_size_and_compression_limits(tmp_path, monkeypatch):
    archive_path = tmp_path / "limits.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("a.py", "x" * 100)
    monkeypatch.setattr(zip_resolver, "MAX_ARCHIVE_ENTRIES", 0)
    with pytest.raises(ValueError, match="entry limit"):
        resolve_zip(archive_path, tmp_path / "extract1")

    monkeypatch.setattr(zip_resolver, "MAX_ARCHIVE_ENTRIES", 5000)
    monkeypatch.setattr(zip_resolver, "MAX_UNCOMPRESSED_BYTES", 10)
    with pytest.raises(ValueError, match="uncompressed size"):
        resolve_zip(archive_path, tmp_path / "extract2")

    monkeypatch.setattr(zip_resolver, "MAX_UNCOMPRESSED_BYTES", 500 * 1024 * 1024)
    monkeypatch.setattr(zip_resolver, "MAX_COMPRESSION_RATIO", 1)
    with pytest.raises(ValueError, match="compression ratio"):
        resolve_zip(archive_path, tmp_path / "extract3")


def test_rejects_duplicate_and_conflicting_paths(tmp_path):
    archive_path = tmp_path / "conflict.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("folder/item.py", "x")
        archive.writestr("folder", "file")
    with pytest.raises(ValueError, match="conflicts"):
        resolve_zip(archive_path, tmp_path / "extract")


def test_cleanup_happens_when_pipeline_raises(tmp_path, monkeypatch):
    archive_path = make_zip(tmp_path / "failure.zip", {"app.py": "ok"})
    extracted_roots = []

    def fail(snapshot, config):
        extracted_roots.append(snapshot.root_path)
        raise RuntimeError("pipeline failure")

    monkeypatch.setattr("ragforge.ingestion.zip_ingestion.ingest_snapshot", fail)
    with pytest.raises(RuntimeError, match="pipeline failure"):
        ingest_zip(archive_path)
    assert extracted_roots[0].exists() is False
