"""Tree-sitter-independent models shared by parsers and chunkers."""

from dataclasses import dataclass, field

from ragforge.paths import normalize_repo_path


@dataclass(frozen=True, slots=True)
class ParseError:
    message: str
    start_line: int
    end_line: int
    kind: str = "syntax_error"

    def __post_init__(self) -> None:
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("parse error lines must be one-based and ordered")


@dataclass(frozen=True, slots=True)
class ParsedSymbol:
    """One source declaration with one-based lines and half-open byte offsets.

    ``symbol_key`` is the documented compatibility alias for ``symbol_id``. The
    chunk model stores and serializes that value under the ``symbol_key`` field.
    """

    symbol_id: str
    name: str
    symbol_type: str
    language: str
    file_path: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    signature: str
    documentation: str = ""
    parent_symbol_id: str | None = None
    qualified_name: str = ""
    children: tuple["ParsedSymbol", ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def symbol_key(self) -> str:
        """Stable logical identity; ``symbol_id`` remains as a compatibility alias."""
        return self.symbol_id

    def __post_init__(self) -> None:
        object.__setattr__(self, "file_path", normalize_repo_path(self.file_path))
        if not self.symbol_id or not self.name or not self.language or not self.file_path:
            raise ValueError("symbol identity, name, language, and file path are required")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("symbol line range must be one-based and ordered")
        if self.start_byte < 0 or self.end_byte < self.start_byte:
            raise ValueError("symbol byte range must be non-negative and ordered")
        if any(child.parent_symbol_id != self.symbol_id for child in self.children):
            raise ValueError("nested symbols must reference their containing symbol")


@dataclass(frozen=True, slots=True)
class ParseResult:
    document_id: str
    repository_id: str
    file_path: str
    language: str
    symbols: tuple[ParsedSymbol, ...] = ()
    errors: tuple[ParseError, ...] = ()
    used_fallback: bool = False
    fallback_reason: str | None = None
    skip_reason: str | None = None

    def __post_init__(self) -> None:
        if (
            not self.document_id
            or not self.repository_id
            or not self.file_path
            or not self.language
        ):
            raise ValueError(
                "parse result requires document, repository, path, and language identity"
            )

    @property
    def has_syntax_errors(self) -> bool:
        return bool(self.errors)

    @property
    def syntax_error_count(self) -> int:
        return len(self.errors)
