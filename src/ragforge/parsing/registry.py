"""Simple normalized language-to-parser registry."""

from ragforge.parsing.protocols import ParserAdapter
from ragforge.parsing.tree_sitter import (
    JavaParser,
    JavaScriptParser,
    PythonParser,
    TSXParser,
    TypeScriptParser,
)


class LanguageRegistry:
    """Register and resolve parser adapters without coupling the pipeline to grammars."""

    def __init__(self, adapters: tuple[ParserAdapter, ...] = ()) -> None:
        self._adapters: dict[str, ParserAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ParserAdapter, *aliases: str) -> None:
        for language in (adapter.language, *aliases):
            self._adapters[language.lower()] = adapter

    def get(self, language: str) -> ParserAdapter | None:
        return self._adapters.get(language.lower())


DEFAULT_REGISTRY = LanguageRegistry()
DEFAULT_REGISTRY.register(PythonParser())
DEFAULT_REGISTRY.register(JavaScriptParser(), "jsx")
DEFAULT_REGISTRY.register(TypeScriptParser())
DEFAULT_REGISTRY.register(TSXParser())
DEFAULT_REGISTRY.register(JavaParser())
