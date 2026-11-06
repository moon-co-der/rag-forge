
import hashlib

from ragforge.ingestion.document_builder import (
    build_document,
    detect_language,
)
from ragforge.ingestion.models import RepositoryInfo


def create_repository():
    return RepositoryInfo(
        repository_id="test-repo",
        name="test-repo",
        source_type="local",
        source_uri="./test-repo",
    )


def test_builds_document():
    repository = create_repository()

    document = build_document(
        repository=repository,
        file_path="src/app.py",
        content="print('hello')",
        size_bytes=14,
    )

    assert document.file_path == "src/app.py"
    assert document.language == "python"
    assert document.extension == ".py"
    assert document.size_bytes == 14
    assert document.line_count == 1


def test_document_id_is_deterministic():
    repository = create_repository()

    first = build_document(repository, "src/app.py", "hello", 5)
    second = build_document(repository, "src/app.py", "changed", 7)

    assert first.document_id == second.document_id


def test_document_id_changes_with_file_path():
    repository = create_repository()

    first = build_document(repository, "src/app.py", "hello", 5)
    second = build_document(repository, "src/db.py", "hello", 5)

    assert first.document_id != second.document_id


def test_content_hash():
    repository = create_repository()
    content = "print('hello')"

    document = build_document(repository, "app.py", content, 14)

    expected_hash = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    assert document.content_hash == expected_hash


def test_line_count():
    repository = create_repository()

    document = build_document(
        repository, "app.py", "line1\nline2\nline3", 17
    )

    assert document.line_count == 3


def test_detect_language():
    assert detect_language("app.py") == "python"
    assert detect_language("App.tsx") == "typescript"
    assert detect_language("README.md") == "markdown"
    assert detect_language("Dockerfile") == "dockerfile"
    assert detect_language("unknown.xyz") == "unknown"


def test_special_filename_extension():
    repository = create_repository()

    document = build_document(
        repository, "Dockerfile", "FROM python:3.11", 16
    )

    assert document.extension == ""
    assert document.language == "dockerfile"
