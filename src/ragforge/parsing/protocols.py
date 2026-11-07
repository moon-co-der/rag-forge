"""Small interfaces that keep language grammars replaceable."""

from typing import Protocol

from ragforge.ingestion.models import Document
from ragforge.parsing.models import ParseResult


class ParserAdapter(Protocol):
    language: str

    def parse(self, document: Document) -> ParseResult:
        """Parse one document into the common symbol model."""


class ParserRegistry(Protocol):
    def get(self, language: str) -> ParserAdapter | None:
        """Return an adapter registered for a normalized language name."""
