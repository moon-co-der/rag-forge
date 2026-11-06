
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IngestionConfig:
    """Configuration controlling repository ingestion."""

    include_extensions: frozenset[str] = frozenset({
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".java", ".c", ".cpp", ".h",
        ".go", ".rs", ".rb", ".php", ".cs",
        ".kt", ".swift", ".sh",
        ".md", ".rst", ".txt",
        ".toml", ".yaml", ".yml", ".json",
        ".sql", ".html", ".css",
    })

    include_filenames: frozenset[str] = frozenset({
        "Dockerfile",
        "Makefile",
        "README",
        "README.md",
        ".env.example",
    })

    exclude_dirs: frozenset[str] = frozenset({
        ".git",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        "target",
        "out",
        "coverage",
        ".next",
        ".idea",
        ".vscode",
        "vendor",
    })

    exclude_globs: frozenset[str] = frozenset({
        "*.min.js",
        "*.map",
    })

    max_file_size_bytes: int = 1_048_576

    follow_symlinks: bool = False

    include_hidden_files: bool = False

    encoding_fallbacks: tuple[str, ...] = ("latin-1",)

    def __post_init__(self):
        if self.max_file_size_bytes <= 0:
            raise ValueError("Maximum file size must be greater than zero.")

        if any(not extension.startswith(".") for extension in self.include_extensions):
            raise ValueError("File extensions must start with a dot.")

        if not self.encoding_fallbacks:
            raise ValueError("At least one fallback encoding must be provided.")
