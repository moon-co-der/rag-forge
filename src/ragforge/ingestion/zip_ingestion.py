import tempfile
from pathlib import Path

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.models import IngestionResult
from ragforge.ingestion.pipeline import ingest_snapshot
from ragforge.ingestion.resolvers.zip import resolve_zip


def ingest_zip(
    source: str | Path,
    config: IngestionConfig | None = None,
) -> IngestionResult:
    """Ingest a software repository from a ZIP archive."""
    settings = config or IngestionConfig()
    with tempfile.TemporaryDirectory(prefix="ragforge-zip-") as extraction_dir:
        snapshot = resolve_zip(source, extraction_dir)
        return ingest_snapshot(snapshot, settings)
