
import hashlib
from pathlib import Path

from ragforge.ingestion.models import Document, RepositoryInfo

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".kt": "kotlin",
    ".swift": "swift",
    ".sh": "shell",
    ".md": "markdown",
    ".rst": "restructuredtext",
    ".txt": "text",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
}


SPECIAL_FILENAME_MAP = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "readme": "markdown",
}


def detect_language(file_path: str) -> str:
    """Identify a file's language using its extension or filename."""

    path = Path(file_path)
    filename = path.name.lower()

    if filename in SPECIAL_FILENAME_MAP:
        return SPECIAL_FILENAME_MAP[filename]

    return LANGUAGE_MAP.get(path.suffix.lower(), "unknown")


def build_document(
    repository: RepositoryInfo,
    file_path: str,
    content: str,
    size_bytes: int,
) -> Document:
    """Create a structured Document from normalized file content."""

    normalized_path = Path(file_path).as_posix()
    extension = Path(normalized_path).suffix.lower()

    document_identity = f"{repository.repository_id}:{normalized_path}"
    document_id = hashlib.sha256(
        document_identity.encode("utf-8")
    ).hexdigest()

    content_hash = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    return Document(
        document_id=document_id,
        repository_id=repository.repository_id,
        file_path=normalized_path,
        extension=extension,
        language=detect_language(normalized_path),
        content=content,
        size_bytes=size_bytes,
        content_hash=content_hash,
        line_count=len(content.splitlines()),
    )
