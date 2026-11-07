"""Fixed-size and recursive line-based baseline chunking strategies."""

from bisect import bisect_right

from ragforge.chunking.config import ChunkingConfig
from ragforge.chunking.identifiers import chunk_identifier, content_hash, virtual_symbol_key
from ragforge.chunking.models import ChunkRecord
from ragforge.ingestion.models import Document
from ragforge.parsing.models import ParseResult
from ragforge.parsing.source import source_bytes


class FixedSizeChunker:
    """Split exact source bytes at deterministic character boundaries."""

    strategy = "fixed"

    def chunk(
        self,
        document: Document,
        parsed: ParseResult | None = None,
        config: ChunkingConfig | None = None,
    ) -> tuple[ChunkRecord, ...]:
        settings = config or ChunkingConfig()
        return _baseline_chunks(document, settings, self.strategy, _fixed_split)


class RecursiveLineChunker:
    """Prefer paragraph and line boundaries before deterministic character splits."""

    strategy = "recursive_line"

    def chunk(
        self,
        document: Document,
        parsed: ParseResult | None = None,
        config: ChunkingConfig | None = None,
    ) -> tuple[ChunkRecord, ...]:
        settings = config or ChunkingConfig()
        return _baseline_chunks(document, settings, self.strategy, _recursive_split)


def _baseline_chunks(document, config, strategy, splitter):
    raw = source_bytes(document)
    text = raw.decode("utf-8", "replace")
    line_starts = [0]
    line_starts.extend(index + 1 for index, byte in enumerate(raw) if byte == 10)
    symbol_key = virtual_symbol_key(document.repository_id, document.file_path, strategy, 0)
    records = []
    byte_cursor = 0
    for index, content in enumerate(splitter(text, config.max_chunk_size)):
        start_byte = byte_cursor
        end_byte = start_byte + len(content.encode("utf-8"))
        start_line = bisect_right(line_starts, start_byte)
        newline_count = content.count("\n")
        end_line = max(
            start_line,
            start_line + newline_count - (1 if content.endswith("\n") else 0),
        )
        records.append(
            ChunkRecord(
                chunk_id=chunk_identifier(symbol_key, content, index),
                symbol_key=symbol_key,
                content_hash=content_hash(content),
                document_id=document.document_id,
                repository_id=document.repository_id,
                file_path=document.file_path,
                content=content,
                context_header=document.file_path,
                language=document.language,
                symbol_type=strategy,
                start_line=start_line,
                end_line=end_line,
                start_byte=start_byte,
                end_byte=end_byte,
                chunk_origin="baseline",
                metadata={"coverage": True, "part_index": index, "strategy": strategy},
            )
        )
        byte_cursor = end_byte
    return tuple(records)


def _recursive_split(text: str, maximum: int) -> list[str]:
    chunks = []
    remainder = text
    while len(remainder) > maximum:
        boundary = -1
        boundary_size = 0
        for separator in ("\n\n", "\n", " "):
            candidate = remainder.rfind(separator, 0, maximum - len(separator) + 1)
            if candidate > 0:
                boundary = candidate
                boundary_size = len(separator)
                break
        if boundary < 0:
            boundary = maximum
        else:
            boundary += boundary_size
        chunks.append(remainder[:boundary])
        remainder = remainder[boundary:]
    if remainder:
        chunks.append(remainder)
    return chunks


def _fixed_split(text: str, maximum: int) -> list[str]:
    return [text[index : index + maximum] for index in range(0, len(text), maximum)]
