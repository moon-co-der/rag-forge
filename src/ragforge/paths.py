"""Path normalization helpers for repository-relative identities."""

from pathlib import PurePosixPath


def normalize_repo_path(file_path: str) -> str:
    """Return a stable POSIX-style repository-relative path."""
    return PurePosixPath(str(file_path).replace("\\", "/")).as_posix()


def normalize_context_header(context_header: str) -> str:
    """Normalize the repository path prefix in a serialized chunk context."""
    file_path, separator, context = context_header.partition(" > ")
    if not separator:
        return normalize_repo_path(file_path)
    return f"{normalize_repo_path(file_path)}{separator}{context}"
