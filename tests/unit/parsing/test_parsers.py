from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo
from ragforge.parsing import DEFAULT_REGISTRY, parse_document

REPOSITORY = RepositoryInfo("repo", "repo", "local", "file:///repo")


def document(path, content, language):
    return build_document(REPOSITORY, path, content, len(content.encode()))


def flatten(symbols):
    return [symbol for item in symbols for symbol in (item, *flatten(item.children))]


def test_python_nested_symbols_docstring_decorator_async_and_unicode():
    source = (
        "# coding: utf-8\n@cache\nclass Café:\n"
        "    async def run(self, value: str) -> str:\n"
        '        """Return a value."""\n'
        "        def nested():\n            return value\n"
    )
    result = parse_document(document("src/app.py", source, "python"))
    symbols = flatten(result.symbols)
    assert [(item.name, item.symbol_type) for item in symbols] == [
        ("Café", "class"),
        ("run", "function"),
        ("nested", "function"),
    ]
    assert symbols[0].metadata["decorators"] == ["@cache"]
    run = symbols[1]
    assert run.documentation == '"""Return a value."""'
    assert run.signature.startswith("async def run")
    assert run.parent_symbol_id == symbols[0].symbol_id
    assert source.encode()[run.start_byte : run.end_byte].decode().startswith("async def run")
    assert result.errors == ()


def test_javascript_typescript_tsx_and_java_symbols():
    fixtures = [
        (
            "src/a.js",
            "export function f(x) { return x; } class A { m() {} } const g = () => 1;",
            "javascript",
            {"f", "A", "m", "g"},
        ),
        (
            "src/a.ts",
            "export interface I { x: string } type T = string;\n"
            "export function f(): T { return ''; }",
            "typescript",
            {"I", "T", "f"},
        ),
        ("src/a.tsx", "export const View = () => <div />;", "tsx", {"View"}),
        (
            "src/A.java",
            "/** API */ class A { A() {} void f() {} class B {} }",
            "java",
            {"A", "f", "B"},
        ),
    ]
    for path, source, language, expected in fixtures:
        result = parse_document(document(path, source, language))
        symbols = flatten(result.symbols)
        assert expected <= {item.name for item in symbols}
        assert not result.errors
        assert all(item.start_line >= 1 and item.end_line >= item.start_line for item in symbols)
        if language == "java":
            assert symbols[0].documentation == "/** API */"


def test_syntax_errors_empty_files_and_unicode_are_controlled():
    broken = parse_document(document("bad.py", "def broken(:\n pass\n", "python"))
    assert broken.errors
    empty = parse_document(document("empty.py", "", "python"))
    assert empty.symbols == ()
    assert empty.errors == ()


def test_large_source_uses_a_controlled_parser_limit(monkeypatch):
    import ragforge.parsing.tree_sitter.base as parser_base

    monkeypatch.setattr(parser_base, "MAX_PARSE_BYTES", 4)
    result = parse_document(document("large.py", "def f(): pass", "python"))
    assert result.errors[0].kind == "parser_limit"


def test_deeply_nested_python_symbols_use_iterative_traversal():
    depth = 48
    source = "".join(f"{'    ' * level}def nested_{level}():\n" for level in range(depth))
    source += f"{'    ' * depth}return 1\n"
    result = parse_document(document("deep.py", source, "python"))
    assert not result.errors
    symbols = flatten(result.symbols)
    assert len(symbols) == depth
    assert symbols[-1].name == f"nested_{depth - 1}"

    extreme = "".join(
        f"{'    ' * level}def nested_{level}():\n" for level in range(180)
    ) + f"{'    ' * 180}return 1\n"
    bounded = parse_document(document("extreme.py", extreme, "python"))
    assert bounded.errors[0].kind == "parser_limit"
    assert bounded.fallback_reason == "parser_nesting_limit"


def test_name_bound_lambdas_are_symbols_but_anonymous_lambdas_are_not():
    source = "named = lambda value: value\nitems = [lambda item: item]\n"
    result = parse_document(document("lambda.py", source, "python"))
    assert [symbol.name for symbol in result.symbols] == ["named"]


def test_registry_accepts_new_adapters_and_unknown_language():
    class ExampleParser:
        language = "example"

        def parse(self, doc):
            return None

    registry = type(DEFAULT_REGISTRY)()
    adapter = ExampleParser()
    registry.register(adapter, "example-alias")
    assert registry.get("EXAMPLE-ALIAS") is adapter
    assert registry.get("unknown") is None


def test_registry_aliases_and_unknown_language_fallback_are_explicit():
    from ragforge.chunking import chunk_document
    from ragforge.parsing.tree_sitter import JavaScriptParser, TSXParser

    assert DEFAULT_REGISTRY.get("jsx").__class__ is JavaScriptParser
    assert DEFAULT_REGISTRY.get("tsx").__class__ is TSXParser
    unsupported = document("notes.unknown", "plain text", "unknown")
    assert parse_document(unsupported) is None
    chunks = chunk_document(unsupported)
    assert chunks and all(
        chunk.metadata["fallback_reason"] == "unsupported_language"
        for chunk in chunks
    )


def test_syntax_error_policy_is_consistent_across_all_registered_languages():
    from ragforge.chunking import chunk_document

    cases = (
        ("bad.js", "function keep() {}\nfunction broken( {", "javascript", "keep"),
        ("bad.ts", "function keep(): void {}\nfunction broken( {", "typescript", "keep"),
        ("bad.tsx", "const View = () => <section>{value}</section;", "typescript", "View"),
        ("bad.java", "class Good { void keep() {} }\nclass Broken {", "java", "Good"),
    )
    for path, source, language, recoverable_name in cases:
        doc = document(path, source, language)
        result = parse_document(doc)
        assert result.has_syntax_errors, path
        assert any(symbol.name == recoverable_name for symbol in flatten(result.symbols)), path
        chunks = chunk_document(doc)
        assert chunks and all(chunk.chunk_origin == "fallback" for chunk in chunks), path
        assert all(
            chunk.metadata["fallback_reason"] == "syntax_error_threshold_exceeded"
            for chunk in chunks
        ), path
