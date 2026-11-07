"""Recover exact source bytes carried by an M1 Document."""

from ragforge.ingestion.models import Document


def source_bytes(document: Document) -> bytes:
    """Return preserved original UTF-8 source, including BOM and original line endings."""
    original = document.metadata.get("original_source_content")
    if isinstance(original, str):
        return original.encode("utf-8")
    content = document.content.encode("utf-8")
    prefix = str(document.metadata.get("source_prefix", "")).encode("utf-8")
    if prefix and not content.startswith(prefix):
        return prefix + content
    return content
