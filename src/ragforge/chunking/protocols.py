"""Interfaces for chunking strategies."""

from typing import Protocol

from ragforge.chunking.config import ChunkingConfig
from ragforge.chunking.models import ChunkRecord
from ragforge.ingestion.models import Document
from ragforge.parsing.models import ParseResult


class Chunker(Protocol):
    def chunk(
        self,
        document: Document,
        parsed: ParseResult | None = None,
        config: ChunkingConfig | None = None,
    ) -> tuple[ChunkRecord, ...]:
        """Produce stable chunks for a single document."""
