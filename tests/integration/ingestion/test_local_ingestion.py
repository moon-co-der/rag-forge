
import pytest

from ragforge.ingestion.local_ingestion import ingest_local
from ragforge.ingestion.resolvers.local import resolve_local


def test_resolves_local_repository(tmp_path):
    snapshot = resolve_local(tmp_path)

    assert snapshot.root_path == tmp_path.resolve()
    assert snapshot.repository.name == tmp_path.name
    assert snapshot.repository.source_type == "local"


def test_ingests_local_repository(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules").mkdir()

    (tmp_path / "src" / "app.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# My Project",
        encoding="utf-8",
    )
    (tmp_path / "empty.py").write_text("", encoding="utf-8")
    (tmp_path / "node_modules" / "ignored.py").write_text(
        "ignored",
        encoding="utf-8",
    )

    result = ingest_local(tmp_path)

    assert result.repository.name == tmp_path.name
    assert result.discovered_files == 3
    assert result.processed_files == 2
    assert result.skipped_files == 1

    paths = {document.file_path for document in result.documents}

    assert "src/app.py" in paths
    assert "README.md" in paths
    assert "node_modules/ignored.py" not in paths

    assert result.skip_reasons["empty_file"] == 1


def test_ingestion_returns_document_metadata(tmp_path):
    (tmp_path / "app.py").write_text(
        "print('hello')",
        encoding="utf-8",
    )

    result = ingest_local(tmp_path)

    document = result.documents[0]

    assert document.language == "python"
    assert document.extension == ".py"
    assert document.file_path == "app.py"
    assert document.content == "print('hello')"
    assert document.content_hash
    assert document.document_id


def test_rejects_nonexistent_directory(tmp_path):
    missing = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        ingest_local(missing)


def test_rejects_file_as_repository(tmp_path):
    file_path = tmp_path / "app.py"
    file_path.write_text("print('hello')")

    with pytest.raises(ValueError):
        ingest_local(file_path)
