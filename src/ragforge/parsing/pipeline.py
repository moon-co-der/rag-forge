"""Document-to-symbol entry point with registry-based adapter selection."""

from ragforge.ingestion.models import Document
from ragforge.parsing.config import ParsingConfig
from ragforge.parsing.models import ParseError, ParseResult
from ragforge.parsing.registry import DEFAULT_REGISTRY, LanguageRegistry
from ragforge.parsing.source import source_bytes


def parse_document(
    document: Document,
    registry: LanguageRegistry = DEFAULT_REGISTRY,
    config: ParsingConfig | None = None,
) -> ParseResult | None:
    """Parse a registered language, returning ``None`` for unsupported languages.

    The chunking pipeline handles ``None`` with an explicit ``unsupported_language``
    fallback record so unregistered formats remain source-covered.
    """
    settings = config or ParsingConfig()
    byte_size = len(source_bytes(document))
    if byte_size > settings.max_source_size_bytes:
        return ParseResult(
            document.document_id,
            document.repository_id,
            document.file_path,
            document.language,
            errors=(
                ParseError(
                    f"Source exceeds configured limit of {settings.max_source_size_bytes} bytes",
                    1,
                    max(document.line_count, 1),
                    "source_size_limit",
                ),
            ),
            used_fallback=settings.oversized_file_policy == "fallback",
            fallback_reason="source_size_limit",
            skip_reason=("file_too_large" if settings.oversized_file_policy == "skip" else None),
        )
    language = "tsx" if document.file_path.lower().endswith(".tsx") else document.language
    adapter = registry.get(language)
    if adapter is None:
        return None
    return adapter.parse(document)
