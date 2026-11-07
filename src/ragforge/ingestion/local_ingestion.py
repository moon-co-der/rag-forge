
from pathlib import Path

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.models import IngestionResult
from ragforge.ingestion.pipeline import ingest_snapshot
from ragforge.ingestion.resolvers.local import resolve_local


def ingest_local(
    source: str | Path,
    config: IngestionConfig | None = None,
    *,
    repository_id: str | None = None,
) -> IngestionResult:
    """Ingest a local checkout using an explicit stable repository identity.

    Callers that previously relied on path-derived repository IDs must now pass
    ``repository_id``. This prevents machine-specific paths from entering
    document and snapshot identities.
    """

    if config is None:
        config = IngestionConfig()

    snapshot = resolve_local(source, repository_id=repository_id)

    return ingest_snapshot(snapshot, config)
