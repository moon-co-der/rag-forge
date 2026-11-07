"""Bounded-memory event stream for repository ingestion."""

from collections import Counter
from dataclasses import dataclass
from typing import Iterator

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.manifest import SnapshotFile, SnapshotManifest, build_snapshot_manifest
from ragforge.ingestion.models import Document, RepoSnapshot
from ragforge.ingestion.reader import read_file
from ragforge.ingestion.scanner import scan_repository


@dataclass(frozen=True, slots=True)
class IngestionEvent:
    """One file result, followed by a final event with snapshot summary."""

    file_path: str
    document: Document | None = None
    skip_reason: str | None = None
    snapshot_manifest: SnapshotManifest | None = None
    discovered_files: int = 0
    processed_files: int = 0
    skip_reasons: dict[str, int] | None = None


def iter_ingestion(snapshot: RepoSnapshot, config: IngestionConfig) -> Iterator[IngestionEvent]:
    """Yield sorted file outcomes and a final manifest/skip summary.

    Only the current document plus compact per-file manifest metadata are retained;
    repository document contents are never accumulated.
    """
    manifest_files: list[SnapshotFile] = []
    skip_reasons: Counter[str] = Counter()
    processed = 0
    for path in scan_repository(snapshot.root_path, config):
        relative_path = path.relative_to(snapshot.root_path).as_posix()
        result = read_file(path, config)
        if not result.success:
            reason = result.skip_reason or "read_error"
            skip_reasons[reason] += 1
            manifest_files.append(
                SnapshotFile(relative_path, result.size_bytes, result.source_hash, False, reason)
            )
            yield IngestionEvent(relative_path, skip_reason=reason)
            continue
        manifest_files.append(
            SnapshotFile(relative_path, result.size_bytes, result.source_hash, True)
        )
        processed += 1
        metadata = {
            key: value
            for key, value in {
                "source_prefix": result.source_prefix,
                "original_source_content": result.original_content,
            }.items()
            if value is not None and value != ""
        }
        yield IngestionEvent(
            relative_path,
            document=build_document(
                snapshot.repository,
                relative_path,
                result.content or "",
                result.size_bytes,
                metadata=metadata,
            ),
        )
    yield IngestionEvent(
        "",
        snapshot_manifest=build_snapshot_manifest(
            snapshot.repository.repository_id,
            manifest_files,
            config,
        ),
        discovered_files=len(manifest_files),
        processed_files=processed,
        skip_reasons=dict(sorted(skip_reasons.items())),
    )
