"""Compact size and origin statistics for chunk inspection."""

from dataclasses import dataclass
from statistics import median

from ragforge.chunking.models import ChunkRecord


@dataclass(frozen=True, slots=True)
class ChunkStatistics:
    total_chunks: int
    minimum_size: int
    median_size: float
    p95_size: int
    maximum_size: int
    fallback_rate: float
    complete_symbol_percentage: float


def chunk_statistics(chunks: tuple[ChunkRecord, ...] | list[ChunkRecord]) -> ChunkStatistics:
    """Return character-size percentiles and chunk origin/completeness rates."""
    sizes = sorted(len(chunk.content) for chunk in chunks)
    total = len(sizes)
    if not total:
        return ChunkStatistics(0, 0, 0.0, 0, 0, 0.0, 0.0)
    p95_index = max(0, (95 * total + 99) // 100 - 1)
    fallback_count = sum(chunk.chunk_origin == "fallback" for chunk in chunks)
    complete_count = sum(bool(chunk.metadata.get("complete_symbol")) for chunk in chunks)
    return ChunkStatistics(
        total_chunks=total,
        minimum_size=sizes[0],
        median_size=float(median(sizes)),
        p95_size=sizes[p95_index],
        maximum_size=sizes[-1],
        fallback_rate=fallback_count / total,
        complete_symbol_percentage=100 * complete_count / total,
    )
