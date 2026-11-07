
import fnmatch
import os
from collections.abc import Iterator
from pathlib import Path

from ragforge.ingestion.config import IngestionConfig


def scan_repository(
    root: Path,
    config: IngestionConfig,
) -> Iterator[Path]:
    """Yield eligible file paths from a repository."""

    root = Path(root)

    if not root.exists() or not root.is_dir():
        raise ValueError(f"Repository directory does not exist: {root}")

    if root.is_symlink():
        raise ValueError("Repository root cannot be a symbolic link.")

    def scan_directory(directory: Path) -> Iterator[Path]:
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda entry: entry.name.lower())
        except OSError:
            return

        for entry in entries:
            path = Path(entry.path)

            # Never follow symbolic links.
            if entry.is_symlink():
                continue

            # Handle directories.
            if entry.is_dir(follow_symlinks=False):
                if entry.name in config.exclude_dirs:
                    continue

                if entry.name.startswith(".") and not config.include_hidden_files:
                    continue

                yield from scan_directory(path)
                continue

            if not entry.is_file(follow_symlinks=False):
                continue

            # Allow explicitly included filenames, such as .env.example.
            explicitly_included = entry.name in config.include_filenames

            if entry.name.startswith("."):
                if not config.include_hidden_files and not explicitly_included:
                    continue

            # Check excluded file patterns.
            relative_path = path.relative_to(root).as_posix()

            if any(
                fnmatch.fnmatch(entry.name, pattern)
                or fnmatch.fnmatch(relative_path, pattern)
                for pattern in config.exclude_globs
            ):
                continue

            # Check supported extensions or explicitly included filenames.
            extension = path.suffix.lower()

            if (
                extension not in config.include_extensions
                and not explicitly_included
            ):
                continue

            # Leave size and read failures to the reader so ingestion can report
            # them in its skip ledger and snapshot manifest.
            yield path

    yield from scan_directory(root)
