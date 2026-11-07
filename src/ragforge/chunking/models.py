"""Typed records emitted by the chunking engine."""

import hashlib
from dataclasses import dataclass, field

from ragforge.paths import normalize_context_header, normalize_repo_path


def is_trivial_source_content(content: str) -> bool:
    """Flag whitespace-only or at-most-eight-character source chunks.

    These chunks remain in output to preserve byte coverage; consumers can exclude
    records marked ``metadata.is_trivial`` from indexing.
    """
    return not content.strip() or len(content) <= 8


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    symbol_key: str
    content_hash: str
    document_id: str
    repository_id: str
    file_path: str
    content: str
    context_header: str
    language: str
    symbol_name: str = ""
    symbol_type: str = "file"
    qualified_name: str = ""
    signature: str = ""
    start_line: int = 1
    end_line: int = 1
    start_byte: int = 0
    end_byte: int = 0
    parent_chunk_id: str | None = None
    chunk_origin: str = "structural"
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", normalize_repo_path(self.file_path))
        object.__setattr__(self, "context_header", normalize_context_header(self.context_header))
        for name in (
            "chunk_id",
            "symbol_key",
            "content_hash",
            "document_id",
            "repository_id",
            "file_path",
            "language",
        ):
            if not getattr(self, name):
                raise ValueError(f"{name} must not be empty")
        if not self.content:
            raise ValueError("content must not be empty")
        expected_hash = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        if self.content_hash != expected_hash:
            raise ValueError("content_hash must match the exact UTF-8 chunk content")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("chunk line range must be one-based and ordered")
        if self.start_byte < 0 or self.end_byte < self.start_byte:
            raise ValueError("chunk byte range must be non-negative and ordered")
        if self.chunk_origin not in {"structural", "fallback", "baseline"}:
            raise ValueError("chunk_origin must be structural, fallback, or baseline")
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a mapping")
