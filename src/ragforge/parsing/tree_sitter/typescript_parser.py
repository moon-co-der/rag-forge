"""TypeScript and TSX Tree-sitter adapters."""

import tree_sitter_typescript

from ragforge.parsing.tree_sitter.base import TreeSitterAdapter

_SYMBOL_TYPES = {
    "function_declaration": "function",
    "generator_function_declaration": "function",
    "class_declaration": "class",
    "abstract_class_declaration": "class",
    "method_definition": "method",
    "abstract_method_signature": "method",
    "enum_declaration": "enum",
    "internal_module": "namespace",
    "module": "namespace",
    "interface_declaration": "interface",
    "type_alias_declaration": "type_alias",
}


class TypeScriptParser(TreeSitterAdapter):
    language = "typescript"
    grammar = staticmethod(tree_sitter_typescript.language_typescript)
    symbol_types = _SYMBOL_TYPES

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


class TSXParser(TypeScriptParser):
    language = "tsx"
    grammar = staticmethod(tree_sitter_typescript.language_tsx)
