from ragforge.chunking import (
    ChunkerRegistry,
    ChunkingConfig,
    FixedSizeChunker,
    chunk_document,
)
from ragforge.cli import main
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo


def test_chunker_registry_selection_and_unknown_language_fallback():
    registry = ChunkerRegistry()
    fixed = FixedSizeChunker()
    registry.register("custom", fixed)
    document = build_document(
        RepositoryInfo("r", "r", "local", "file:///r"), "note.xyz", "unknown text", 12
    )
    chunks = chunk_document(document, "custom", chunker_registry=registry)
    assert chunks[0].chunk_origin == "baseline"
    assert registry.get("missing") is None

    fallback = chunk_document(document)
    assert fallback[0].chunk_origin == "fallback"
    assert fallback[0].metadata["fallback_reason"] == "unsupported_language"


def test_cli_inspects_and_exports_a_single_file(tmp_path, capsys):
    source = tmp_path / "sample.py"
    source.write_text("def answer():\n    return 42\n", encoding="utf-8")
    export = tmp_path / "chunks.jsonl"
    result = main(["chunks", str(source), "--strategy", "fixed", "--jsonl", str(export)])
    captured = capsys.readouterr()
    assert result == 0
    assert "Total chunks: 1" in captured.out
    assert "origin=baseline" in captured.out
    assert export.read_text(encoding="utf-8").count("\n") == 1


def test_cli_reports_one_file_failure_and_continues(tmp_path, monkeypatch, capsys):
    (tmp_path / "bad.py").write_text("raise", encoding="utf-8")
    (tmp_path / "good.py").write_text("def good():\n    return 1\n", encoding="utf-8")
    from ragforge import cli

    actual = cli.chunk_document

    def fail_one(document, *args, **kwargs):
        if document.file_path == "bad.py":
            raise RuntimeError("fixture failure")
        return actual(document, *args, **kwargs)

    monkeypatch.setattr(cli, "chunk_document", fail_one)
    assert main(["chunks", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert "Failed bad.py: fixture failure" in output.err
    assert "good.py" in output.out


def test_dummy_chunker_registers_without_core_changes():
    class DummyChunker:
        def chunk(self, document, parsed=None, config=None):
            return FixedSizeChunker().chunk(document, parsed, config)

    registry = ChunkerRegistry()
    registry.register("dummy", DummyChunker())
    document = build_document(RepositoryInfo("r", "r", "local", "file:///r"), "a.py", "abc", 3)
    assert chunk_document(document, "dummy", ChunkingConfig(), chunker_registry=registry)
