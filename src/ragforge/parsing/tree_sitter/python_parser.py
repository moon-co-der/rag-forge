"""Python Tree-sitter adapter for classes, functions, and methods."""

import tree_sitter_python

from ragforge.parsing.tree_sitter.base import TreeSitterAdapter, _named_children


class PythonParser(TreeSitterAdapter):
    language = "python"
    grammar = staticmethod(tree_sitter_python.language)
    symbol_types = {
        "class_definition": "class",
        "function_definition": "function",
    }

    def _kind(self, node):
        if node.type == "assignment":
            value = node.child_by_field_name("right")
            if value is not None and value.type == "lambda":
                return "function"
        return super()._kind(node)

    def _source_node(self, node):
        if node.parent is not None and node.parent.type == "decorated_definition":
            return node.parent
        return node

    def _symbol_metadata(self, node, source: bytes) -> dict[str, object]:
        if node.parent is None or node.parent.type != "decorated_definition":
            return {}
        decorators = [
            source[child.start_byte : child.end_byte].decode("utf-8", "replace")
            for child in _named_children(node.parent)
            if child.type == "decorator"
        ]
        return {"decorators": decorators} if decorators else {}
