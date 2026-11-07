
import hashlib
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
    source_hash: str | None = None

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
            return FileReadResult(
                None,
                size_bytes,
                "file_too_large",
                source_hash=_stream_hash(path),
            )

        raw_content = path.read_bytes()
        size_bytes = len(raw_content)

    except PermissionError:
        return FileReadResult(None, 0, "permission_denied")
    except OSError:
        return FileReadResult(None, 0, "read_error")

    if size_bytes > config.max_file_size_bytes:
        return FileReadResult(
            None,
            size_bytes,
            "file_too_large",
            source_hash=_stream_hash(path),
        )

    source_hash = hashlib.sha256(raw_content).hexdigest()

    if not raw_content:
        return FileReadResult(None, 0, "empty_file", source_hash=source_hash)

    # Detect binary content using NUL bytes in the first 8 KB.
    if b"\x00" in raw_content[:8192]:
        return FileReadResult(None, size_bytes, "binary_file", source_hash=source_hash)

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
        return FileReadResult(None, size_bytes, "decoding_error", source_hash=source_hash)

    # Normalize Windows and old Mac line endings to Unix line endings.
    source_prefix = "\ufeff" if raw_content.startswith(b"\xef\xbb\xbf") else ""
    original_content = (
        f"{source_prefix}{content}"
        if source_prefix and not content.startswith(source_prefix)
        else content
    )
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    if not content.strip():
        return FileReadResult(None, size_bytes, "empty_file", source_hash=source_hash)

    preserved_source = original_content if original_content != content else None
    return FileReadResult(
        content,
        size_bytes,
        source_prefix=source_prefix,
        original_content=preserved_source,
        source_hash=source_hash,
    )


def _stream_hash(path: Path) -> str | None:
    """Hash a too-large file in bounded memory for stable manifest identity."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            while block := source.read(1024 * 1024):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()
