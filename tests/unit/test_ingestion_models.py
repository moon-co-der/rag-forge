
from pathlib import Path

from ragforge.ingestion.models import (
    Document,
    IngestionResult,
    RepositoryInfo,
    RepoSnapshot,
)


def test_repository_info():
    repository = RepositoryInfo(
        repository_id="rag-forge-main",
        name="rag-forge",
        source_type="github",
        source_uri="https://github.com/moon-co-der/rag-forge",
    )

    assert repository.name == "rag-forge"
    assert repository.source_type == "github"


def test_repo_snapshot():
    repository = RepositoryInfo(
        repository_id="test-repo",
        name="test-repo",
        source_type="local",
        source_uri="./test-repo",
    )

    snapshot = RepoSnapshot(
        root_path=Path("./test-repo"),
        repository=repository,
    )

    assert snapshot.root_path == Path("./test-repo")


def test_document():
    document = Document(
        document_id="doc-001",
        repository_id="test-repo",
        file_path="src/app.py",
        extension=".py",
        language="python",
        content="print('hello')",
        size_bytes=14,
        content_hash="abc123",
        line_count=1,
    )

    assert document.file_name == "app.py"
    assert document.language == "python"


def test_ingestion_result():
    repository = RepositoryInfo(
        repository_id="test-repo",
        name="test-repo",
        source_type="local",
        source_uri="./test-repo",
    )

    result = IngestionResult(
        repository=repository,
        documents=(),
        discovered_files=5,
        processed_files=3,
        skipped_files=2,
    )

    assert result.discovered_files == 5
    assert result.processed_files == 3
    assert result.skipped_files == 2
