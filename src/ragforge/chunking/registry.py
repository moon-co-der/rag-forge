"""Strategy-name registry for compatible chunker implementations."""

from ragforge.chunking.baselines import FixedSizeChunker, RecursiveLineChunker
from ragforge.chunking.protocols import Chunker
from ragforge.chunking.structural import StructuralChunker


class ChunkerRegistry:
    """Register chunkers by a short stable strategy name."""

    def __init__(self) -> None:
        self._chunkers: dict[str, Chunker] = {}

    def register(self, name: str, chunker: Chunker) -> None:
        if not name:
            raise ValueError("chunker name must not be empty")
        self._chunkers[name.lower()] = chunker

    def get(self, name: str) -> Chunker | None:
        return self._chunkers.get(name.lower())


DEFAULT_CHUNKERS = ChunkerRegistry()
DEFAULT_CHUNKERS.register("structural", StructuralChunker())
DEFAULT_CHUNKERS.register("fixed", FixedSizeChunker())
DEFAULT_CHUNKERS.register("recursive_line", RecursiveLineChunker())
