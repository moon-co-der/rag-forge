
from pathlib import Path

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.models import IngestionResult
from ragforge.ingestion.pipeline import ingest_snapshot
from ragforge.ingestion.resolvers.local import resolve_local


def ingest_local(
    source: str | Path,
    config: IngestionConfig | None = None,
) -> IngestionResult:
    """Ingest a repository from a local directory."""

    if config is None:
        config = IngestionConfig()

    snapshot = resolve_local(source)

    return ingest_snapshot(snapshot, config)
