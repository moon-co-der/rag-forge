import hashlib

from ragforge.chunking import ChunkRecord, chunk_to_dict, write_jsonl
from ragforge.chunking.identifiers import chunk_identifier
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo
from ragforge.parsing.identifiers import make_symbol_key


def test_equivalent_windows_and_posix_paths_have_identical_document_and_symbol_ids():
    repository = RepositoryInfo("repo", "repo", "local", "file:///repo")
    windows = build_document(repository, r"src\pkg\module.py", "def f(): pass\n", 13)
    posix = build_document(repository, "src/pkg/module.py", "def f(): pass\n", 13)

    assert windows.file_path == posix.file_path == "src/pkg/module.py"
    assert windows.document_id == posix.document_id
    assert make_symbol_key("repo", r"src\pkg\module.py", "f", "function") == make_symbol_key(
        "repo", "src/pkg/module.py", "f", "function"
    )
    key = make_symbol_key("repo", r"src\pkg\module.py", "f", "function")
    assert chunk_identifier(key, "def f(): pass\n") == chunk_identifier(
        make_symbol_key("repo", "src/pkg/module.py", "f", "function"), "def f(): pass\n"
    )


def test_windows_and_posix_chunk_paths_serialize_identically(tmp_path):
    values = []
    for file_path, context in (
        (r"src\pkg\module.py", r"src\pkg\module.py > f"),
        ("src/pkg/module.py", "src/pkg/module.py > f"),
    ):
        values.append(
            ChunkRecord(
                chunk_id="chunk",
                symbol_key="symbol",
                content_hash=hashlib.sha256(b"x").hexdigest(),
                document_id="doc",
                repository_id="repo",
                file_path=file_path,
                content="x",
                context_header=context,
                language="python",
            )
        )
    assert values[0] == values[1]
    assert chunk_to_dict(values[0])["file_path"] == "src/pkg/module.py"
    first, second = tmp_path / "windows.jsonl", tmp_path / "posix.jsonl"
    write_jsonl([values[0]], first)
    write_jsonl([values[1]], second)
    assert first.read_bytes() == second.read_bytes()
