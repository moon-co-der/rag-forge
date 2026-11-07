from collections import Counter

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.manifest import SnapshotFile, build_snapshot_manifest
from ragforge.ingestion.models import IngestionResult, RepoSnapshot
from ragforge.ingestion.reader import read_file
from ragforge.ingestion.scanner import scan_repository


def ingest_snapshot(snapshot: RepoSnapshot, config: IngestionConfig) -> IngestionResult:
    """Read eligible files from a resolved snapshot and build its documents."""
    documents = []
    manifest_files = []
    skip_reasons: Counter[str] = Counter()
    discovered = 0
    for path in scan_repository(snapshot.root_path, config):
        discovered += 1
        result = read_file(path, config)
        relative_path = path.relative_to(snapshot.root_path).as_posix()
        if not result.success:
            reason = result.skip_reason or "read_error"
            skip_reasons[reason] += 1
            manifest_files.append(
                SnapshotFile(relative_path, result.size_bytes, result.source_hash, False, reason)
            )
            continue
        manifest_files.append(
            SnapshotFile(relative_path, result.size_bytes, result.source_hash, True)
        )
        documents.append(
            build_document(
                snapshot.repository,
                relative_path,
                result.content or "",
                result.size_bytes,
                metadata={
                    key: value
                    for key, value in {
                        "source_prefix": result.source_prefix,
                        "original_source_content": result.original_content,
                    }.items()
                    if value is not None and value != ""
                },
            )
        )
    return IngestionResult(
        repository=snapshot.repository,
        documents=tuple(documents),
        discovered_files=discovered,
        processed_files=len(documents),
        skipped_files=sum(skip_reasons.values()),
        skip_reasons=dict(skip_reasons),
        snapshot_manifest=build_snapshot_manifest(
            snapshot.repository.repository_id,
            manifest_files,
            config,
        ),
    )
