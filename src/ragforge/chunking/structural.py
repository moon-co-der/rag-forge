"""Python structure-aware chunking with non-overlapping source coverage."""

from bisect import bisect_right

from ragforge.chunking.config import ChunkingConfig
from ragforge.chunking.fallback import _split_text, fallback_chunks
from ragforge.chunking.identifiers import (
    chunk_identifier,
    content_hash,
    virtual_symbol_key,
)
from ragforge.chunking.models import ChunkRecord, is_trivial_source_content
from ragforge.ingestion.models import Document
from ragforge.parsing.models import ParsedSymbol, ParseResult
from ragforge.parsing.source import source_bytes

_LEAF_TYPES = {"function", "method", "constructor"}
_CONTAINER_TYPES = {"class"}


class StructuralChunker:
    """Emit class summaries, leaf source pieces, and residue covering the source once."""

    def chunk(
        self,
        document: Document,
        parsed: ParseResult | None = None,
        config: ChunkingConfig | None = None,
    ) -> tuple[ChunkRecord, ...]:
        settings = config or ChunkingConfig()
        if parsed is None:
            return fallback_chunks(document, settings, "unsupported_language")
        if parsed.skip_reason:
            return ()
        if parsed.used_fallback:
            return fallback_chunks(document, settings, parsed.fallback_reason or "parser_limit")
        if parsed.errors and settings.fallback_on_parse_error:
            if len(parsed.errors) > settings.syntax_error_threshold:
                return fallback_chunks(document, settings, "syntax_error_threshold_exceeded")

        raw = source_bytes(document)
        line_starts = [0]
        line_starts.extend(index + 1 for index, byte in enumerate(raw) if byte == 10)
        symbols = _flatten(parsed.symbols)
        symbols_by_key = {symbol.symbol_key: symbol for symbol in symbols}
        records: list[ChunkRecord] = []
        container_ids: dict[str, str] = {}

        for symbol in symbols:
            if symbol.symbol_type not in _CONTAINER_TYPES:
                continue
            summary = _container_summary(symbol)
            parent_id = container_ids.get(symbol.parent_symbol_id or "")
            record = _make_record(
                document=document,
                symbol_key=symbol.symbol_key,
                content=summary,
                part_index=0,
                language=symbol.language,
                symbol_name=symbol.name,
                symbol_type="class_summary",
                qualified_name=symbol.qualified_name,
                signature=symbol.signature,
                start_line=symbol.start_line,
                end_line=symbol.end_line,
                start_byte=symbol.start_byte,
                end_byte=symbol.end_byte,
                parent_chunk_id=parent_id,
                context_header=_context_header(document.file_path, symbol.qualified_name),
                chunk_origin="structural",
                metadata={
                    "coverage": False,
                    "container_summary": True,
                    **_context_metadata(symbol, symbols_by_key),
                },
            )
            records.append(record)
            container_ids[symbol.symbol_key] = record.chunk_id

        leaf_intervals: list[tuple[int, int, ParsedSymbol, int]] = []
        symbol_first_chunk: dict[str, str] = {}
        for symbol in symbols:
            if symbol.symbol_type not in _LEAF_TYPES:
                continue
            start = max(0, min(symbol.start_byte, len(raw)))
            end = max(start, min(symbol.end_byte, len(raw)))
            excluded = sorted(
                (max(start, child.start_byte), min(end, child.end_byte))
                for child in symbol.children
                if child.end_byte > start and child.start_byte < end
            )
            own_ranges = _subtract_intervals(start, end, excluded)
            part_index = 0
            for range_start, range_end in own_ranges:
                if range_start >= range_end:
                    continue
                leaf_intervals.append((range_start, range_end, symbol, part_index))
                for record in _source_records(
                    document,
                    raw,
                    line_starts,
                    range_start,
                    range_end,
                    settings.max_chunk_size,
                    symbol_key=symbol.symbol_key,
                    symbol_name=symbol.name,
                    symbol_type=symbol.symbol_type,
                    qualified_name=symbol.qualified_name,
                    signature=symbol.signature,
                    context_header=_context_header(document.file_path, symbol.qualified_name),
                    chunk_origin="structural",
                    parent_chunk_id=(
                        container_ids.get(symbol.parent_symbol_id or "")
                        or symbol_first_chunk.get(symbol.parent_symbol_id or "")
                    ),
                    part_index_start=part_index,
                    metadata={
                        "coverage": True,
                        "documentation": symbol.documentation,
                        "symbol_id": symbol.symbol_id,
                        "complete_symbol": (
                            len(own_ranges) == 1
                            and own_ranges[0] == (start, end)
                            and end - start <= settings.max_chunk_size
                        ),
                        **_context_metadata(symbol, symbols_by_key),
                    },
                ):
                    if symbol.symbol_key not in symbol_first_chunk:
                        symbol_first_chunk[symbol.symbol_key] = record.chunk_id
                    records.append(record)
                    part_index += 1

        coverage = sorted((start, end) for start, end, _, _ in leaf_intervals)
        residue_ranges = _complement_intervals(len(raw), coverage)
        residue_index = 0
        for range_start, range_end in residue_ranges:
            if range_start == range_end:
                continue
            owner = _residue_owner(symbols, range_start, range_end)
            qualified = owner.qualified_name if owner else ""
            key = virtual_symbol_key(
                document.repository_id,
                document.file_path,
                "residue",
                residue_index,
            )
            records.extend(
                _source_records(
                    document,
                    raw,
                    line_starts,
                    range_start,
                    range_end,
                    settings.max_chunk_size,
                    symbol_key=key,
                    symbol_name="",
                    symbol_type="module_residue",
                    qualified_name=qualified,
                    signature="",
                    context_header=_context_header(document.file_path, qualified),
                    chunk_origin="structural",
                    parent_chunk_id=(
                        container_ids.get(owner.symbol_key)
                        if owner and owner.symbol_type in _CONTAINER_TYPES
                        else None
                    ),
                    part_index_start=0,
                    metadata={
                        "coverage": True,
                        "residue_part": residue_index,
                        "enclosing_class": owner.name
                        if owner and owner.symbol_type == "class"
                        else None,
                        "parent_symbol_key": owner.symbol_key if owner else None,
                    },
                )
            )
            residue_index += 1

        records.sort(
            key=lambda record: (
                record.start_byte,
                not bool(record.metadata.get("coverage")),
                record.chunk_id,
            )
        )
        return tuple(records)


def _flatten(symbols: tuple[ParsedSymbol, ...]) -> list[ParsedSymbol]:
    result = []
    stack = list(reversed(symbols))
    while stack:
        symbol = stack.pop()
        result.append(symbol)
        stack.extend(reversed(symbol.children))
    return result


def _container_summary(symbol: ParsedSymbol) -> str:
    lines = [symbol.signature or f"class {symbol.name}"]
    if symbol.documentation:
        lines.append(symbol.documentation)
    signatures = [child.signature for child in symbol.children if child.signature]
    if signatures:
        lines.append("Members:")
        lines.extend(signatures)
    return "\n".join(lines)


def _subtract_intervals(
    start: int, end: int, excluded: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    ranges = []
    cursor = start
    for excluded_start, excluded_end in excluded:
        if excluded_start > cursor:
            ranges.append((cursor, excluded_start))
        cursor = max(cursor, excluded_end)
    if cursor < end:
        ranges.append((cursor, end))
    return ranges


def _complement_intervals(total: int, intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    gaps = []
    cursor = 0
    for start, end in intervals:
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total:
        gaps.append((cursor, total))
    return gaps


def _residue_owner(symbols: list[ParsedSymbol], start: int, end: int) -> ParsedSymbol | None:
    owners = [
        symbol
        for symbol in symbols
        if symbol.symbol_type in _CONTAINER_TYPES
        and symbol.start_byte <= start
        and end <= symbol.end_byte
    ]
    return min(owners, key=lambda symbol: symbol.end_byte - symbol.start_byte) if owners else None


def _context_header(file_path: str, qualified_name: str) -> str:
    return f"{file_path} > {qualified_name}" if qualified_name else file_path


def _context_metadata(
    symbol: ParsedSymbol, symbols_by_key: dict[str, ParsedSymbol]
) -> dict[str, str | None]:
    parent = symbols_by_key.get(symbol.parent_symbol_id or "")
    return {
        "enclosing_class": parent.name if parent and parent.symbol_type == "class" else None,
        "parent_symbol_key": parent.symbol_key if parent else None,
    }


def _source_records(
    document: Document,
    raw: bytes,
    line_starts: list[int],
    start: int,
    end: int,
    maximum: int,
    *,
    symbol_key: str,
    symbol_name: str,
    symbol_type: str,
    qualified_name: str,
    signature: str,
    context_header: str,
    chunk_origin: str,
    parent_chunk_id: str | None,
    part_index_start: int,
    metadata: dict[str, object],
) -> list[ChunkRecord]:
    text = raw[start:end].decode("utf-8", "replace")
    records = []
    local_byte = 0
    for offset, piece in enumerate(_split_text(text, maximum)):
        piece_start = start + local_byte
        local_byte += len(piece.encode("utf-8"))
        piece_end = start + local_byte
        start_line = bisect_right(line_starts, piece_start)
        newline_count = piece.count("\n")
        end_line = max(
            start_line,
            start_line + newline_count - (1 if piece.endswith("\n") else 0),
        )
        part_index = part_index_start + offset
        records.append(
            _make_record(
                document=document,
                symbol_key=symbol_key,
                content=piece,
                part_index=part_index,
                language=document.language,
                symbol_name=symbol_name,
                symbol_type=symbol_type,
                qualified_name=qualified_name,
                signature=signature,
                start_line=start_line,
                end_line=end_line,
                start_byte=piece_start,
                end_byte=piece_end,
                parent_chunk_id=parent_chunk_id,
                context_header=context_header,
                chunk_origin=chunk_origin,
                metadata=metadata,
            )
        )
    return records


def _make_record(
    *,
    document: Document,
    symbol_key: str,
    content: str,
    part_index: int,
    language: str,
    symbol_name: str,
    symbol_type: str,
    qualified_name: str,
    signature: str,
    start_line: int,
    end_line: int,
    start_byte: int,
    end_byte: int,
    parent_chunk_id: str | None,
    context_header: str,
    chunk_origin: str,
    metadata: dict[str, object],
) -> ChunkRecord:
    return ChunkRecord(
        chunk_id=chunk_identifier(symbol_key, content, part_index),
        symbol_key=symbol_key,
        content_hash=content_hash(content),
        document_id=document.document_id,
        repository_id=document.repository_id,
        file_path=document.file_path,
        content=content,
        context_header=context_header,
        language=language,
        symbol_name=symbol_name,
        symbol_type=symbol_type,
        qualified_name=qualified_name,
        signature=signature,
        start_line=start_line,
        end_line=end_line,
        start_byte=start_byte,
        end_byte=end_byte,
        parent_chunk_id=parent_chunk_id,
        chunk_origin=chunk_origin,
        metadata={
            **metadata,
            "is_trivial": is_trivial_source_content(content),
        },
    )
