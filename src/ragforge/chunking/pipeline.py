"""Single-document orchestration from M1 Document to selected chunk strategy."""

from ragforge.chunking.config import ChunkingConfig
from ragforge.chunking.models import ChunkRecord
from ragforge.chunking.registry import DEFAULT_CHUNKERS, ChunkerRegistry
from ragforge.ingestion.models import Document
from ragforge.parsing.config import ParsingConfig
from ragforge.parsing.pipeline import parse_document
from ragforge.parsing.registry import DEFAULT_REGISTRY, LanguageRegistry


def chunk_document(
    document: Document,
    strategy: str = "structural",
    config: ChunkingConfig | None = None,
    parsing_config: ParsingConfig | None = None,
    *,
    parser_registry: LanguageRegistry = DEFAULT_REGISTRY,
    chunker_registry: ChunkerRegistry = DEFAULT_CHUNKERS,
) -> tuple[ChunkRecord, ...]:
    """Parse when required, select a registered chunker, and return its records."""
    chunker = chunker_registry.get(strategy)
    if chunker is None:
        raise ValueError(f"Unknown chunking strategy: {strategy}")
    parsed = None
    if strategy.lower() == "structural":
        parsed = parse_document(document, parser_registry, parsing_config)
    return chunker.chunk(document, parsed, config)
