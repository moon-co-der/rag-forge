"""Configuration for structural chunks and controlled fallback processing."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChunkingConfig:
    max_chunk_size: int = 8_000
    fallback_chunk_size: int = 8_000
    fallback_on_parse_error: bool = True
    syntax_error_threshold: int = 0

    def __post_init__(self) -> None:
        if self.max_chunk_size <= 0 or self.fallback_chunk_size <= 0:
            raise ValueError("Chunk sizes must be greater than zero")
        if self.syntax_error_threshold < 0:
            raise ValueError("syntax_error_threshold cannot be negative")
