"""Lightweight command-line inspection tools for RAGForge."""

import argparse
import sys
from pathlib import Path

from ragforge.chunking.config import ChunkingConfig
from ragforge.chunking.pipeline import chunk_document
from ragforge.chunking.serialization import write_jsonl
from ragforge.chunking.statistics import chunk_statistics
from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.local_ingestion import ingest_local
from ragforge.ingestion.reader import read_file
from ragforge.ingestion.resolvers.local import resolve_local


def main(argv: list[str] | None = None) -> int:
    """Run the RAGForge command line."""
    parser = argparse.ArgumentParser(prog="ragforge")
    commands = parser.add_subparsers(dest="command", required=True)
    chunks_command = commands.add_parser("chunks", help="inspect chunks from a Python file or repo")
    chunks_command.add_argument("path", type=Path)
    chunks_command.add_argument(
        "--strategy", choices=("structural", "fixed", "recursive_line"), default="structural"
    )
    chunks_command.add_argument("--max-chunk-size", type=int, default=8_000)
    chunks_command.add_argument("--jsonl", type=Path)
    args = parser.parse_args(argv)
    if args.command == "chunks":
        return _inspect_chunks(args.path, args.strategy, args.max_chunk_size, args.jsonl)
    return 2


def _inspect_chunks(path: Path, strategy: str, maximum: int, jsonl: Path | None) -> int:
    if maximum <= 0:
        print("--max-chunk-size must be greater than zero", file=sys.stderr)
        return 2
    try:
        documents = _documents(path)
    except (OSError, ValueError) as exc:
        print(f"Unable to read {path}: {exc}", file=sys.stderr)
        return 2

    config = ChunkingConfig(max_chunk_size=maximum)
    chunks = []
    failures = 0
    for document in documents:
        try:
            chunks.extend(chunk_document(document, strategy, config))
        except Exception as exc:  # One broken file should not block other documents.
            failures += 1
            print(f"Failed {document.file_path}: {exc}", file=sys.stderr)

    for chunk in chunks:
        print(
            f"{chunk.chunk_id} | {chunk.symbol_name or '-'} | {chunk.symbol_type} | "
            f"{chunk.file_path}:{chunk.start_line}-{chunk.end_line} | "
            f"parent={chunk.parent_chunk_id or '-'} | chars={len(chunk.content)} | "
            f"origin={chunk.chunk_origin}"
        )
    stats = chunk_statistics(chunks)
    print(f"Total chunks: {stats.total_chunks}")
    print(
        f"Chunk size chars: min={stats.minimum_size}, median={stats.median_size:g}, "
        f"p95={stats.p95_size}, max={stats.maximum_size}"
    )
    print(f"Fallback rate: {stats.fallback_rate:.1%}")
    print(f"Complete symbol chunks: {stats.complete_symbol_percentage:.1f}%")
    if jsonl:
        write_jsonl(chunks, jsonl)
    return 1 if failures else 0


def _documents(path: Path):
    path = path.expanduser().resolve()
    if path.is_dir():
        return ingest_local(path).documents
    if not path.is_file():
        raise FileNotFoundError(path)
    repository_snapshot = resolve_local(path.parent)
    config = IngestionConfig()
    result = read_file(path, config)
    if not result.success:
        raise ValueError(result.skip_reason or "could not read source file")
    metadata = {
        key: value
        for key, value in {
            "source_prefix": result.source_prefix,
            "original_source_content": result.original_content,
        }.items()
        if value is not None and value != ""
    }
    return (
        build_document(
            repository_snapshot.repository,
            path.relative_to(repository_snapshot.root_path).as_posix(),
            result.content or "",
            result.size_bytes,
            metadata=metadata,
        ),
    )


if __name__ == "__main__":
    raise SystemExit(main())
