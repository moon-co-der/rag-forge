
from pathlib import Path

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import IngestionResult
from ragforge.ingestion.reader import read_file
from ragforge.ingestion.resolvers.local import resolve_local
from ragforge.ingestion.scanner import scan_repository


def ingest_local(
    source: str | Path,
    config: IngestionConfig | None = None,
) -> IngestionResult:
    """Ingest a local repository and return structured documents."""

    if config is None:
        config = IngestionConfig()

    snapshot = resolve_local(source)

    documents = []
    skip_reasons = {}
    discovered_files = 0

    for file_path in scan_repository(snapshot.root_path, config):
        discovered_files += 1

        result = read_file(file_path, config)

        if not result.success:
            reason = result.skip_reason or "unknown_error"
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
            continue

        relative_path = file_path.relative_to(
            snapshot.root_path
        ).as_posix()

        document = build_document(
            repository=snapshot.repository,
            file_path=relative_path,
            content=result.content,
            size_bytes=result.size_bytes,
        )

        documents.append(document)

    processed_files = len(documents)
    skipped_files = sum(skip_reasons.values())

    return IngestionResult(
        repository=snapshot.repository,
        documents=tuple(documents),
        discovered_files=discovered_files,
        processed_files=processed_files,
        skipped_files=skipped_files,
        skip_reasons=skip_reasons,
    )
