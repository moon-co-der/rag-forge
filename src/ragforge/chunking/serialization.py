"""JSON-compatible and JSONL serialization for portable chunk records."""

import json
from pathlib import Path
from typing import Any

from ragforge.chunking.models import ChunkRecord
from ragforge.paths import normalize_context_header, normalize_repo_path

SCHEMA_VERSION = 1


def chunk_to_dict(chunk: ChunkRecord) -> dict[str, Any]:
    """Convert a chunk to a JSON-compatible mapping."""
    return {
        "schema_version": SCHEMA_VERSION,
        "chunk_id": chunk.chunk_id,
        "symbol_key": chunk.symbol_key,
        "content_hash": chunk.content_hash,
        "document_id": chunk.document_id,
        "repository_id": chunk.repository_id,
        "file_path": normalize_repo_path(chunk.file_path),
        "content": chunk.content,
        "context_header": normalize_context_header(chunk.context_header),
        "language": chunk.language,
        "symbol_name": chunk.symbol_name,
        "symbol_type": chunk.symbol_type,
        "qualified_name": chunk.qualified_name,
        "signature": chunk.signature,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "start_byte": chunk.start_byte,
        "end_byte": chunk.end_byte,
        "parent_chunk_id": chunk.parent_chunk_id,
        "chunk_origin": chunk.chunk_origin,
        "metadata": chunk.metadata,
    }


def chunk_from_dict(value: dict[str, Any]) -> ChunkRecord:
    """Validate a mapping and construct a chunk record."""
    required = {
        "schema_version",
        "chunk_id",
        "symbol_key",
        "content_hash",
        "document_id",
        "repository_id",
        "file_path",
        "content",
        "context_header",
        "language",
        "start_line",
        "end_line",
        "start_byte",
        "end_byte",
        "chunk_origin",
    }
    missing = required - value.keys()
    if missing:
        raise ValueError(f"Missing required chunk fields: {', '.join(sorted(missing))}")
    version = value.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError(f"Unsupported chunk schema version: {version}")
    allowed = set(ChunkRecord.__dataclass_fields__) | {"schema_version"}
    unknown = value.keys() - allowed
    if unknown:
        raise ValueError(f"Unknown chunk fields: {', '.join(sorted(unknown))}")
    try:
        return ChunkRecord(**{key: item for key, item in value.items() if key != "schema_version"})
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid chunk record: {exc}") from exc


def write_jsonl(chunks: tuple[ChunkRecord, ...] | list[ChunkRecord], path: str | Path) -> None:
    """Write one chunk record per UTF-8 JSONL line."""
    with Path(path).open("w", encoding="utf-8", newline="\n") as output:
        for chunk in chunks:
            output.write(json.dumps(chunk_to_dict(chunk), ensure_ascii=False, sort_keys=True))
            output.write("\n")


def read_jsonl(path: str | Path) -> tuple[ChunkRecord, ...]:
    """Read and validate chunk records from JSONL."""
    chunks = []
    with Path(path).open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("record must be a JSON object")
                chunks.append(chunk_from_dict(value))
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid JSONL record at line {line_number}: {exc}") from exc
    known_ids = {chunk.chunk_id for chunk in chunks}
    for chunk in chunks:
        if chunk.parent_chunk_id and chunk.parent_chunk_id not in known_ids:
            raise ValueError(f"Chunk {chunk.chunk_id} references a missing parent chunk")
    return tuple(chunks)
