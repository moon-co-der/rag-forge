"""Resource and error policy for parsing source documents."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ParsingConfig:
    max_source_size_bytes: int = 20 * 1024 * 1024
    oversized_file_policy: Literal["fallback", "skip"] = "fallback"

    def __post_init__(self) -> None:
        if self.max_source_size_bytes <= 0:
            raise ValueError("max_source_size_bytes must be greater than zero")
        if self.oversized_file_policy not in {"fallback", "skip"}:
            raise ValueError("oversized_file_policy must be fallback or skip")
