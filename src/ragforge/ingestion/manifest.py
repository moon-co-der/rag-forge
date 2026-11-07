"""Deterministic content manifests for ingested repository snapshots."""

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Literal

from ragforge.paths import normalize_repo_path

if TYPE_CHECKING:
    from ragforge.ingestion.config import IngestionConfig


@dataclass(frozen=True, slots=True)
class SnapshotFile:
    """One discovered path and its exact-byte ingestion outcome."""

    file_path: str
    size_bytes: int
    source_hash: str | None
    processed: bool
    skip_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", normalize_repo_path(self.file_path))
        if not self.file_path:
            raise ValueError("snapshot file path is required")
        if self.size_bytes < 0:
            raise ValueError("snapshot file size cannot be negative")
        if self.source_hash is not None and (
            len(self.source_hash) != 64
            or any(character not in "0123456789abcdef" for character in self.source_hash)
        ):
            raise ValueError("source_hash must be a lowercase SHA-256 digest")
        if self.processed and self.skip_reason is not None:
            raise ValueError("processed snapshot files cannot have a skip reason")
        if not self.processed and not self.skip_reason:
            raise ValueError("skipped snapshot files require a skip reason")


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """Sorted file inventory with a content-addressed stable snapshot ID.

    The ID hashes schema version, explicit repository ID, ingestion-config hash,
    and sorted per-file path, exact-byte size/hash, processed flag, and skip reason.
    Checkout paths, timestamps, source URIs, and discovery order are excluded.
    """

    repository_id: str
    snapshot_id: str
    files: tuple[SnapshotFile, ...]
    config_hash: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.repository_id:
            raise ValueError("stable repository identity is required")
        paths = [item.file_path for item in self.files]
        if paths != sorted(paths) or len(paths) != len(set(paths)):
            raise ValueError("snapshot manifest paths must be sorted and unique")
        if len(self.config_hash) != 64:
            raise ValueError("config_hash must be a SHA-256 digest")
        expected = _manifest_id(
            self.repository_id,
            self.config_hash,
            self.files,
            self.schema_version,
        )
        if self.snapshot_id != expected:
            raise ValueError("snapshot_id must match the canonical manifest contents")

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible, deterministically ordered manifest mapping."""
        return {
            "schema_version": self.schema_version,
            "repository_id": self.repository_id,
            "config_hash": self.config_hash,
            "snapshot_id": self.snapshot_id,
            "files": [asdict(item) for item in self.files],
        }


@dataclass(frozen=True, slots=True)
class SnapshotChange:
    """One deterministic file change between two manifests."""

    file_path: str
    change_type: Literal["added", "removed", "modified"]
    previous: SnapshotFile | None
    current: SnapshotFile | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", normalize_repo_path(self.file_path))
        if self.change_type == "added" and (self.previous is not None or self.current is None):
            raise ValueError("added changes require only a current file")
        if self.change_type == "removed" and (self.previous is None or self.current is not None):
            raise ValueError("removed changes require only a previous file")
        if self.change_type == "modified" and (self.previous is None or self.current is None):
            raise ValueError("modified changes require both versions")


def build_snapshot_manifest(
    repository_id: str,
    files: tuple[SnapshotFile, ...] | list[SnapshotFile],
    config: "IngestionConfig",
) -> SnapshotManifest:
    """Sort discovered files and derive a stable ID from their exact metadata."""
    if not repository_id:
        raise ValueError("stable repository identity is required")
    ordered = tuple(sorted(files, key=lambda item: item.file_path))
    if len({item.file_path for item in ordered}) != len(ordered):
        raise ValueError("snapshot manifest cannot contain duplicate paths")
    config_hash = _config_hash(config)
    return SnapshotManifest(
        repository_id,
        _manifest_id(repository_id, config_hash, ordered, 1),
        ordered,
        config_hash,
    )


def diff_snapshots(
    previous: SnapshotManifest,
    current: SnapshotManifest,
) -> tuple[SnapshotChange, ...]:
    """Return added, removed and modified files in path-sorted order."""
    if previous.repository_id != current.repository_id:
        raise ValueError("cannot diff snapshots belonging to different repositories")
    before = {item.file_path: item for item in previous.files}
    after = {item.file_path: item for item in current.files}
    changes = []
    for file_path in sorted(before.keys() | after.keys()):
        old, new = before.get(file_path), after.get(file_path)
        if old is None:
            changes.append(SnapshotChange(file_path, "added", None, new))
        elif new is None:
            changes.append(SnapshotChange(file_path, "removed", old, None))
        elif (old.size_bytes, old.source_hash, old.processed, old.skip_reason) != (
            new.size_bytes,
            new.source_hash,
            new.processed,
            new.skip_reason,
        ):
            changes.append(SnapshotChange(file_path, "modified", old, new))
    return tuple(changes)


def _manifest_id(
    repository_id: str,
    config_hash: str,
    files: tuple[SnapshotFile, ...],
    schema_version: int,
) -> str:
    payload = {
        "schema_version": schema_version,
        "repository_id": repository_id,
        "config_hash": config_hash,
        "files": [asdict(item) for item in files],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _config_hash(config: "IngestionConfig") -> str:
    payload = {
        "include_extensions": sorted(config.include_extensions),
        "include_filenames": sorted(config.include_filenames),
        "exclude_dirs": sorted(config.exclude_dirs),
        "exclude_globs": sorted(config.exclude_globs),
        "max_file_size_bytes": config.max_file_size_bytes,
        "follow_symlinks": config.follow_symlinks,
        "include_hidden_files": config.include_hidden_files,
        "encoding_fallbacks": list(config.encoding_fallbacks),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
