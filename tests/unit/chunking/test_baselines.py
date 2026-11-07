from ragforge.chunking import (
    ChunkingConfig,
    FixedSizeChunker,
    RecursiveLineChunker,
    chunk_statistics,
)
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo


def test_baselines_share_records_and_cover_source_exactly():
    source = "# 🧪 தமிழ்\r\n\r\nline two\r\nline three\r\n"
    document = build_document(
        RepositoryInfo("repo", "repo", "local", "file:///repo"),
        "src/demo.py",
        source,
        len(source.encode()),
    )
    for chunker in (FixedSizeChunker(), RecursiveLineChunker()):
        chunks = chunker.chunk(document, config=ChunkingConfig(max_chunk_size=12))
        assert b"".join(chunk.content.encode("utf-8") for chunk in chunks) == source.encode("utf-8")
        assert all(chunk.chunk_origin == "baseline" for chunk in chunks)
        assert all(chunk.context_header == "src/demo.py" for chunk in chunks)
        assert all(chunk.symbol_key and chunk.content_hash and chunk.chunk_id for chunk in chunks)


def test_chunk_statistics_and_empty_input():
    document = build_document(
        RepositoryInfo("repo", "repo", "local", "file:///repo"), "a.py", "x\ny\nz", 5
    )
    chunks = FixedSizeChunker().chunk(document)
    stats = chunk_statistics(chunks)
    assert stats.total_chunks == 1
    assert stats.minimum_size == stats.maximum_size == 5
    assert chunk_statistics([]).total_chunks == 0
