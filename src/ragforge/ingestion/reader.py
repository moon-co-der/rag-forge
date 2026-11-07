
from dataclasses import dataclass
from pathlib import Path

from ragforge.ingestion.config import IngestionConfig


@dataclass(frozen=True, slots=True)
class FileReadResult:
    """Result of attempting to read a repository file."""

    content: str | None
    size_bytes: int
    skip_reason: str | None = None
    source_prefix: str = ""
    original_content: str | None = None

    @property
    def success(self) -> bool:
        return self.content is not None and self.skip_reason is None


def read_file(path: Path, config: IngestionConfig) -> FileReadResult:
    """Read and normalize a text file."""

    path = Path(path)

    try:
        if path.is_symlink():
            return FileReadResult(None, 0, "symlink")

        if not path.is_file():
            return FileReadResult(None, 0, "not_a_file")

        size_bytes = path.stat().st_size

        if size_bytes > config.max_file_size_bytes:
            return FileReadResult(None, size_bytes, "file_too_large")

        raw_content = path.read_bytes()
        size_bytes = len(raw_content)

    except PermissionError:
        return FileReadResult(None, 0, "permission_denied")
    except OSError:
        return FileReadResult(None, 0, "read_error")

    if size_bytes > config.max_file_size_bytes:
        return FileReadResult(None, size_bytes, "file_too_large")

    if not raw_content:
        return FileReadResult(None, 0, "empty_file")

    # Detect binary content using NUL bytes in the first 8 KB.
    if b"\x00" in raw_content[:8192]:
        return FileReadResult(None, size_bytes, "binary_file")

    content = None

    # Try UTF-8 with BOM support first.
    encodings = ("utf-8-sig", *config.encoding_fallbacks)

    for encoding in encodings:
        try:
            content = raw_content.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if content is None:
        return FileReadResult(None, size_bytes, "decoding_error")

    # Normalize Windows and old Mac line endings to Unix line endings.
    source_prefix = "\ufeff" if raw_content.startswith(b"\xef\xbb\xbf") else ""
    original_content = (
        f"{source_prefix}{content}"
        if source_prefix and not content.startswith(source_prefix)
        else content
    )
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    if not content.strip():
        return FileReadResult(None, size_bytes, "empty_file")

    preserved_source = original_content if original_content != content else None
    return FileReadResult(
        content,
        size_bytes,
        source_prefix=source_prefix,
        original_content=preserved_source,
    )
