
from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import IngestionResult, RepoSnapshot
from ragforge.ingestion.reader import read_file
from ragforge.ingestion.scanner import scan_repository


def ingest_snapshot(
    snapshot: RepoSnapshot,
    config: IngestionConfig,
) -> IngestionResult:
    """Process a resolved repository snapshot."""

    documents = []
    skip_reasons = {}
    discovered_files = 0

    for file_path in scan_repository(snapshot.root_path, config):
        discovered_files += 1

        read_result = read_file(file_path, config)

        if not read_result.success:
            reason = read_result.skip_reason or "unknown_error"
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            continue

        relative_path = file_path.relative_to(
            snapshot.root_path
        ).as_posix()

        document = build_document(
            repository=snapshot.repository,
            file_path=relative_path,
            content=read_result.content,
            size_bytes=read_result.size_bytes,
        )

        documents.append(document)

    return IngestionResult(
        repository=snapshot.repository,
        documents=tuple(documents),
        discovered_files=discovered_files,
        processed_files=len(documents),
        skipped_files=sum(skip_reasons.values()),
        skip_reasons=skip_reasons,
    )
