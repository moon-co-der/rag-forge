"""Shared Tree-sitter adapter implementation and node-to-symbol conversion."""

from collections.abc import Callable
from typing import Any

from tree_sitter import Language, Parser

from ragforge.ingestion.models import Document
from ragforge.parsing.identifiers import make_symbol_key
from ragforge.parsing.models import ParsedSymbol, ParseError, ParseResult
from ragforge.parsing.source import source_bytes

GrammarFactory = Callable[[], object]
MAX_PARSE_BYTES = 20 * 1024 * 1024
MAX_TREE_NESTING = 128


class TreeSitterAdapter:
    """Extract nested declarations with a language-specific grammar and node map."""

    language = ""
    grammar: GrammarFactory
    symbol_types: dict[str, str] = {}

    def _parser(self) -> Parser:
        parser = Parser()
        parser.language = Language(self.grammar())
        return parser

    def parse(self, document: Document) -> ParseResult:
        full_source = source_bytes(document)
        prefix_bytes = b"\xef\xbb\xbf" if full_source.startswith(b"\xef\xbb\xbf") else b""
        source = full_source[len(prefix_bytes) :]
        if len(full_source) > MAX_PARSE_BYTES:
            return ParseResult(
                document.document_id,
                document.repository_id,
                document.file_path,
                self.language,
                errors=(
                    ParseError(
                        f"Source exceeds the {MAX_PARSE_BYTES}-byte Tree-sitter limit",
                        1,
                        max(document.line_count, 1),
                        "parser_limit",
                    ),
                ),
                used_fallback=True,
                fallback_reason="source_size_limit",
            )
        if _nesting_exceeds_limit(source, MAX_TREE_NESTING):
            return ParseResult(
                document.document_id,
                document.repository_id,
                document.file_path,
                self.language,
                errors=(ParseError(
                    f"Source exceeds the {MAX_TREE_NESTING}-level parser nesting limit",
                    1,
                    max(document.line_count, 1),
                    "parser_limit",
                ),),
                used_fallback=True,
                fallback_reason="parser_nesting_limit",
            )
        try:
            tree = self._parser().parse(source)
        except (ValueError, RuntimeError) as exc:
            return ParseResult(
                document.document_id,
                document.repository_id,
                document.file_path,
                self.language,
                errors=(ParseError(str(exc), 1, max(document.line_count, 1), "parser_error"),),
            )
        if tree is None:
            errors = (
                ParseError("Tree-sitter returned no syntax tree", 1, max(document.line_count, 1)),
            )
            return ParseResult(
                document.document_id,
                document.repository_id,
                document.file_path,
                self.language,
                errors=errors,
            )
        errors = _collect_errors(tree.root_node)
        try:
            symbols = self._symbols(tree.root_node, source, document, len(prefix_bytes))
        except (RecursionError, MemoryError) as exc:
            return ParseResult(
                document.document_id,
                document.repository_id,
                document.file_path,
                self.language,
                errors=(
                    ParseError(
                        f"Parser nesting exceeds the supported recursion depth: {exc}",
                        1,
                        max(document.line_count, 1),
                        "parser_limit",
                    ),
                ),
            )
        return ParseResult(
            document.document_id,
            document.repository_id,
            document.file_path,
            self.language,
            symbols=tuple(symbols),
            errors=tuple(errors),
        )

    def _symbols(
        self, root, source: bytes, document: Document, byte_prefix: int
    ) -> list[ParsedSymbol]:
        """Iteratively collect declarations, then assemble their immutable tree bottom-up."""
        raw_symbols = []
        sibling_ordinals: dict[tuple[str | None, str, str], int] = {}
        stack: list[tuple[Any, str | None, str]] = [(root, None, "")]
        while stack:
            node, parent_id, parent_name = stack.pop()
            current_id, current_name = parent_id, parent_name
            kind = self._kind(node)
            if kind:
                name_node = _name_node(node)
                if name_node is not None:
                    name = source[name_node.start_byte : name_node.end_byte].decode(
                        "utf-8", "replace"
                    )
                    qualified = f"{parent_name}.{name}" if parent_name else name
                    scope_key = (parent_id, qualified, kind)
                    ordinal = sibling_ordinals.get(scope_key, 0)
                    sibling_ordinals[scope_key] = ordinal + 1
                    symbol_key = make_symbol_key(
                        document.repository_id,
                        document.file_path,
                        qualified,
                        kind,
                        ordinal,
                    )
                    source_node = self._source_node(node)
                    raw_symbols.append(
                        (
                            node,
                            parent_id,
                            name,
                            qualified,
                            kind,
                            symbol_key,
                            source_node.start_point.row + 1,
                            source_node.end_point.row
                            + (0 if source_node.end_point.column == 0 else 1),
                            source_node.start_byte + byte_prefix,
                            source_node.end_byte + byte_prefix,
                        )
                    )
                    current_id, current_name = symbol_key, qualified
            for child in reversed(_named_children(node)):
                stack.append((child, current_id, current_name))

        children: dict[str, list[ParsedSymbol]] = {}
        for (
            node,
            parent_id,
            name,
            qualified,
            kind,
            symbol_key,
            start_line,
            end_line,
            start_byte,
            end_byte,
        ) in reversed(raw_symbols):
            symbol = ParsedSymbol(
                symbol_id=symbol_key,
                name=name,
                symbol_type=kind,
                language=self.language,
                file_path=document.file_path,
                start_line=start_line,
                end_line=end_line,
                start_byte=start_byte,
                end_byte=end_byte,
                signature=self._symbol_signature(node, source),
                documentation=_documentation(node, source, self.language),
                parent_symbol_id=parent_id,
                qualified_name=qualified,
                children=tuple(
                    sorted(children.pop(symbol_key, []), key=lambda item: item.start_byte)
                ),
                metadata=self._symbol_metadata(node, source),
            )
            if parent_id:
                children.setdefault(parent_id, []).append(symbol)
            else:
                children.setdefault("", []).append(symbol)
        return sorted(children.get("", []), key=lambda item: item.start_byte)

    def _kind(self, node) -> str | None:
        return self.symbol_types.get(node.type)

    def _source_node(self, node):
        return node

    def _symbol_signature(self, node, source: bytes) -> str:
        return _signature(node, source, self.language)

    def _symbol_metadata(self, node, source: bytes) -> dict[str, object]:
        return {}


def _name_node(node):
    identifier_types = {"identifier", "property_identifier", "type_identifier", "field_identifier"}
    for field_name in ("name", "declarator", "property"):
        child = node.child_by_field_name(field_name)
        if child is not None:
            if child.type in identifier_types:
                return child
            for descendant in _named_children(child):
                if descendant.type in identifier_types:
                    return descendant
    for child in _named_children(node):
        if child.type in identifier_types:
            return child
    return None


def _signature(node, source: bytes, language: str) -> str:
    body = node.child_by_field_name("body")
    if body is not None:
        value = source[node.start_byte : body.start_byte]
        return value.decode("utf-8", "replace").strip().rstrip(":").strip()
    text = source[node.start_byte : node.end_byte].decode("utf-8", "replace")
    if language == "python":
        return text.splitlines()[0].strip().rstrip(":")
    return text.split("{", 1)[0].strip().rstrip(";")


def _documentation(node, source: bytes, language: str) -> str:
    body = node.child_by_field_name("body")
    if body is not None and language != "java":
        candidates = _named_children(body)
        if candidates:
            first = candidates[0]
            if language == "python" and first.type == "expression_statement":
                if first.named_children and first.named_children[0].type == "string":
                    return (
                        source[first.start_byte : first.end_byte].decode("utf-8", "replace").strip()
                    )
            if first.type in {"comment", "line_comment", "block_comment"}:
                return source[first.start_byte : first.end_byte].decode("utf-8", "replace").strip()
    parent = node.parent
    if parent is not None:
        siblings = _named_children(parent)
        index = next((i for i, sibling in enumerate(siblings) if sibling.id == node.id), -1)
        if index > 0 and siblings[index - 1].type in {"comment", "line_comment", "block_comment"}:
            comment = siblings[index - 1]
            between = source[comment.end_byte : node.start_byte]
            if between.count(b"\n") <= 2:
                return (
                    source[comment.start_byte : comment.end_byte].decode("utf-8", "replace").strip()
                )
    return ""


def _collect_errors(root) -> list[ParseError]:
    errors: list[ParseError] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == "ERROR" or node.is_missing:
            message = "Missing syntax node" if node.is_missing else f"Syntax error near {node.type}"
            errors.append(
                ParseError(
                    message,
                    node.start_point.row + 1,
                    max(node.end_point.row + 1, node.start_point.row + 1),
                )
            )
        stack.extend(
            node.child(index)
            for index in range(node.child_count - 1, -1, -1)
        )
    return errors


def _named_children(node):
    """Yield named direct children without materializing a recursive native tuple."""
    children = []
    for index in range(node.child_count):
        child = node.child(index)
        if child.is_named:
            children.append(child)
    return children


def _nesting_exceeds_limit(source: bytes, maximum: int) -> bool:
    """Bound pathological indentation and delimiter depth before native parsing."""
    indent_depth = 0
    for line in source.splitlines():
        indentation = len(line) - len(line.lstrip(b" \t"))
        indent_depth = max(indent_depth, indentation)
        if indent_depth > maximum * 4:
            return True
    depth = 0
    for byte in source:
        if byte in b"([{":
            depth += 1
            if depth > maximum:
                return True
        elif byte in b")]}":
            depth = max(0, depth - 1)
    return False
