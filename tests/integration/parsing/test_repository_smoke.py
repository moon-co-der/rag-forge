import subprocess
import sys
from pathlib import Path

from ragforge.chunking import chunk_document, write_jsonl
from ragforge.ingestion.local_ingestion import ingest_local
from ragforge.parsing.source import source_bytes


def _chunks_with_coverage(root: Path):
    documents = ingest_local(root).documents
    output = []
    for document in documents:
        chunks = chunk_document(document)
        raw = source_bytes(document)
        coverage = sorted(
            (chunk.start_byte, chunk.end_byte, chunk.content.encode("utf-8"))
            for chunk in chunks
            if chunk.metadata.get("coverage")
        )
        cursor = 0
        for start, end, content in coverage:
            assert start == cursor, f"coverage gap or overlap in {document.file_path} at {cursor}"
            assert raw[start:end] == content
            cursor = end
        assert cursor == len(raw), f"incomplete coverage in {document.file_path} at {cursor}"
        output.extend(chunks)
    return tuple(output)


def test_ragforge_python_repository_has_exact_coverage_and_deterministic_jsonl(tmp_path):
    repository = Path(__file__).parents[3]
    source_root = repository / "src" / "ragforge"

    first = _chunks_with_coverage(source_root)
    second = _chunks_with_coverage(source_root)
    first_path, second_path = tmp_path / "first.jsonl", tmp_path / "second.jsonl"
    write_jsonl(first, first_path)
    write_jsonl(second, second_path)

    assert first
    assert first_path.read_bytes() == second_path.read_bytes()


def test_former_native_crash_files_are_isolated_and_reported_by_path():
    repository = Path(__file__).parents[3]
    reproductions = (
        "src/ragforge/chunking/structural.py",
        "src/ragforge/parsing/tree_sitter/base.py",
    )
    worker = (
        "import sys; from pathlib import Path; "
        "from ragforge.ingestion.document_builder import build_document; "
        "from ragforge.ingestion.models import RepositoryInfo; "
        "from ragforge.parsing.tree_sitter.python_parser import PythonParser; "
        "path=Path(sys.argv[1]); raw=path.read_bytes(); "
        "doc=build_document(RepositoryInfo('repo','repo','local','file:///repo'), "
        "path.as_posix(), raw.decode('utf-8'), len(raw)); "
        "result=PythonParser().parse(doc); assert result.symbols; print(len(result.symbols))"
    )
    for relative_path in reproductions:
        result = subprocess.run(
            [sys.executable, "-X", "faulthandler", "-c", worker, relative_path],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Tree-sitter worker failed for {relative_path} "
            f"(exit {result.returncode}): {result.stderr[-1000:]}"
        )
