"""Deterministic fallback splitting for unsupported and malformed source files."""

from bisect import bisect_right

from ragforge.chunking.config import ChunkingConfig
from ragforge.chunking.identifiers import chunk_identifier, content_hash, virtual_symbol_key
from ragforge.chunking.models import ChunkRecord, is_trivial_source_content
from ragforge.ingestion.models import Document
from ragforge.parsing.source import source_bytes


def fallback_chunks(
    document: Document,
    config: ChunkingConfig,
    reason: str,
) -> tuple[ChunkRecord, ...]:
    """Split exact source at line boundaries, splitting only oversized lines by characters."""
    raw = source_bytes(document)
    if not raw:
        return ()
    text = raw.decode("utf-8", "replace")
    parts = _split_text(text, config.fallback_chunk_size)
    line_starts = [0]
    line_starts.extend(index + 1 for index, byte in enumerate(raw) if byte == 10)
    records = []
    byte_cursor = 0
    symbol_key = virtual_symbol_key(
        document.repository_id, document.file_path, f"fallback:{reason}", 0
    )
    for index, part in enumerate(parts):
        start_byte = byte_cursor
        end_byte = start_byte + len(part.encode("utf-8"))
        start_line = bisect_right(line_starts, start_byte)
        newline_count = part.count("\n")
        end_line = max(
            start_line,
            start_line + newline_count - (1 if part.endswith("\n") else 0),
        )
        records.append(
            ChunkRecord(
                chunk_id=chunk_identifier(symbol_key, part, index),
                symbol_key=symbol_key,
                content_hash=content_hash(part),
                document_id=document.document_id,
                repository_id=document.repository_id,
                file_path=document.file_path,
                content=part,
                context_header=document.file_path,
                language=document.language,
                symbol_type="fallback",
                start_line=start_line,
                end_line=end_line,
                start_byte=start_byte,
                end_byte=end_byte,
                chunk_origin="fallback",
                metadata={
                    "coverage": True,
                    "fallback_reason": reason,
                    "part_index": index,
                    "is_trivial": is_trivial_source_content(part),
                },
            )
        )
        byte_cursor = end_byte
    return tuple(records)


def _split_text(text: str, maximum: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if current and len(current) + len(line) > maximum:
            pieces.append(current)
            current = ""
        while len(line) > maximum:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:maximum])
            line = line[maximum:]
        current += line
    if current:
        pieces.append(current)
    return pieces or [text]
