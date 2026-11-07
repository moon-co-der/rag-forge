"""JavaScript Tree-sitter adapter, including named arrow-function bindings."""

import tree_sitter_javascript

from ragforge.parsing.tree_sitter.base import TreeSitterAdapter


class JavaScriptParser(TreeSitterAdapter):
    language = "javascript"
    grammar = staticmethod(tree_sitter_javascript.language)
    symbol_types = {
        "function_declaration": "function",
        "generator_function_declaration": "function",
        "class_declaration": "class",
        "method_definition": "method",
    }

    def _kind(self, node):
        if node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if value is not None and value.type in {"arrow_function", "function_expression"}:
                return "function"
        return super()._kind(node)

    def _symbol_signature(self, node, source: bytes) -> str:
        if node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if value is not None and value.type in {"arrow_function", "function_expression"}:
                body = value.child_by_field_name("body")
                end = body.start_byte if body is not None else value.end_byte
                return source[node.start_byte : end].decode("utf-8", "replace").strip()
        return super()._symbol_signature(node, source)
