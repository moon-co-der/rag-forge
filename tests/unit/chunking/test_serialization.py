import hashlib
from dataclasses import replace

import pytest

from ragforge.chunking import ChunkRecord, chunk_from_dict, chunk_to_dict, read_jsonl, write_jsonl


def test_chunk_serialization_round_trip_and_jsonl_unicode(tmp_path):
    record = ChunkRecord(
        chunk_id="c",
        symbol_key="s",
        content_hash=hashlib.sha256("print('café')".encode()).hexdigest(),
        document_id="d",
        repository_id="r",
        file_path="src/é.py",
        content="print('café')",
        context_header="src/é.py > A.f",
        language="python",
        symbol_name="f",
        symbol_type="function",
        qualified_name="A.f",
        signature="def f()",
        start_line=2,
        end_line=3,
        start_byte=1,
        end_byte=15,
        parent_chunk_id="p",
        chunk_origin="structural",
        metadata={"start_byte": 1, "unicode": "café"},
    )
    assert chunk_from_dict(chunk_to_dict(record)) == record
    parent = replace(record, chunk_id="p", symbol_name="A", symbol_type="class_summary")
    child = replace(record, parent_chunk_id="p")
    path = tmp_path / "chunks.jsonl"
    write_jsonl([parent, child], path)
    assert read_jsonl(path) == (parent, child)


def test_invalid_chunk_records_are_rejected(tmp_path):
    with pytest.raises(ValueError, match="Missing required"):
        chunk_from_dict({"chunk_id": "only"})
    with pytest.raises(ValueError, match="line range"):
        ChunkRecord(
            "c",
            "s",
            hashlib.sha256(b"x").hexdigest(),
            "d",
            "r",
            "a.py",
            "x",
            "a.py",
            "python",
            start_line=0,
        )
    path = tmp_path / "bad.jsonl"
    path.write_text("not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        read_jsonl(path)


def test_jsonl_output_is_byte_for_byte_deterministic(tmp_path):
    record = ChunkRecord(
        chunk_id="c",
        symbol_key="s",
        content_hash=hashlib.sha256("π".encode()).hexdigest(),
        document_id="d",
        repository_id="r",
        file_path="a.py",
        content="π",
        context_header="a.py",
        language="python",
        start_byte=0,
        end_byte=len("π".encode()),
        metadata={"coverage": True},
    )
    first, second = tmp_path / "one.jsonl", tmp_path / "two.jsonl"
    write_jsonl([record], first)
    write_jsonl([record], second)
    assert first.read_bytes() == second.read_bytes()


def test_symbol_key_is_a_serialized_field_and_mapping_order_is_irrelevant(tmp_path):
    record = ChunkRecord(
        chunk_id="chunk",
        symbol_key="logical-symbol",
        content_hash=hashlib.sha256(b"body").hexdigest(),
        document_id="doc",
        repository_id="repo",
        file_path="a.py",
        content="body",
        context_header="a.py > f",
        language="python",
        metadata={"z": 1, "a": {"y": 2, "b": 3}},
    )
    reversed_metadata = {"a": {"b": 3, "y": 2}, "z": 1}
    reordered = replace(record, metadata=reversed_metadata)
    first, second = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    write_jsonl([record], first)
    write_jsonl([reordered], second)
    assert chunk_to_dict(record)["symbol_key"] == "logical-symbol"
    assert first.read_bytes() == second.read_bytes()
