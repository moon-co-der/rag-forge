"""Java Tree-sitter adapter for classes, interfaces, methods, and constructors."""

import tree_sitter_java

from ragforge.parsing.tree_sitter.base import TreeSitterAdapter


class JavaParser(TreeSitterAdapter):
    language = "java"
    grammar = staticmethod(tree_sitter_java.language)
    symbol_types = {
        "class_declaration": "class",
        "enum_declaration": "enum",
        "record_declaration": "record",
        "interface_declaration": "interface",
        "method_declaration": "method",
        "constructor_declaration": "constructor",
    }
