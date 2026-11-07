import difflib
import json
from pathlib import Path

from ragforge.chunking import chunk_document, write_jsonl
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo
from ragforge.parsing.models import ParseResult
from ragforge.parsing.pipeline import parse_document
from ragforge.parsing.registry import LanguageRegistry
from ragforge.parsing.source import source_bytes

FIXTURES = Path(__file__).parents[2] / "fixtures" / "parsing" / "python"
GOLDEN = FIXTURES / "basic.golden.json"


def assert_parser_contract(adapter, document):
    result = adapter.parse(document)
    assert isinstance(result, ParseResult)
    assert result.document_id == document.document_id
    assert result.repository_id == document.repository_id
    assert result.file_path == document.file_path
    expected_language = "tsx" if document.file_path.lower().endswith(".tsx") else document.language
    raw = source_bytes(document)
    for symbol in _flatten(result.symbols):
        assert symbol.language == expected_language
        assert symbol.start_line >= 1 and symbol.end_line >= symbol.start_line
        assert 0 <= symbol.start_byte <= symbol.end_byte <= len(raw)
        assert symbol.file_path == document.file_path.replace("\\", "/")
    return result


def _snapshot(document):
    parsed = parse_document(document)
    chunks = chunk_document(document)
    return {
        "parse": {
            "has_syntax_errors": parsed.has_syntax_errors,
            "syntax_error_count": parsed.syntax_error_count,
            "used_fallback": parsed.used_fallback,
            "fallback_reason": parsed.fallback_reason,
            "errors": [
                {
                    "message": error.message,
                    "start_line": error.start_line,
                    "end_line": error.end_line,
                    "kind": error.kind,
                }
                for error in parsed.errors
            ],
        },
        "symbols": [
            {
                "name": symbol.name,
                "symbol_type": symbol.symbol_type,
                "qualified_name": symbol.qualified_name,
                "signature": symbol.signature,
                "start_line": symbol.start_line,
                "end_line": symbol.end_line,
                "documentation": symbol.documentation,
                "symbol_key": symbol.symbol_key,
                "parent_symbol_id": symbol.parent_symbol_id,
                "start_byte": symbol.start_byte,
                "end_byte": symbol.end_byte,
                "source_slice": source_bytes(document)[
                    symbol.start_byte : symbol.end_byte
                ].decode("utf-8", "replace"),
            }
            for symbol in _flatten(parsed.symbols)
        ],
        "chunks": [
            {
                "symbol_name": chunk.symbol_name,
                "symbol_type": chunk.symbol_type,
                "qualified_name": chunk.qualified_name,
                "content": chunk.content,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "parent_chunk_id": chunk.parent_chunk_id,
                "chunk_origin": chunk.chunk_origin,
                "coverage": chunk.metadata.get("coverage"),
                "context_header": chunk.context_header,
                "signature": chunk.signature,
                "enclosing_class": chunk.metadata.get("enclosing_class"),
                "parent_symbol_key": chunk.metadata.get("parent_symbol_key"),
                "is_trivial": chunk.metadata.get("is_trivial", False),
                "fallback_reason": chunk.metadata.get("fallback_reason"),
                "start_byte": chunk.start_byte,
                "end_byte": chunk.end_byte,
            }
            for chunk in chunks
        ],
    }


def _flatten(symbols):
    output = []
    stack = list(reversed(symbols))
    while stack:
        symbol = stack.pop()
        output.append(symbol)
        stack.extend(reversed(symbol.children))
    return output


def test_conformance_harness_accepts_stub_parser():
    document = build_document(RepositoryInfo("r", "r", "local", "file:///r"), "x.py", "pass", 4)

    class StubParser:
        language = "python"

        def parse(self, value):
            return ParseResult(value.document_id, value.repository_id, value.file_path, "python")

    assert_parser_contract(StubParser(), document)


def test_python_golden_symbols_and_chunks():
    source = (FIXTURES / "basic.py").read_text(encoding="utf-8")
    document = build_document(
        RepositoryInfo("golden-repo", "golden", "local", "file:///golden"),
        "basic.py",
        source,
        len(source.encode()),
    )
    registry = LanguageRegistry()
    from ragforge.parsing.tree_sitter.python_parser import PythonParser

    registry.register(PythonParser())
    assert_parser_contract(registry.get("python"), document)
    actual = _snapshot(document)
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert actual == expected, "\n".join(
        difflib.unified_diff(
            json.dumps(expected, indent=2, ensure_ascii=False).splitlines(),
            json.dumps(actual, indent=2, ensure_ascii=False).splitlines(),
            fromfile="expected golden",
            tofile="actual output",
            lineterm="",
        )
    )


def test_python_syntax_error_golden_reports_recovery_and_fallback():
    source = (FIXTURES / "syntax_error.py").read_bytes().decode("utf-8")
    document = build_document(
        RepositoryInfo("golden-repo", "golden", "local", "file:///golden"),
        "syntax_error.py",
        source,
        len(source.encode()),
    )
    actual = _snapshot(document)
    expected = json.loads((FIXTURES / "syntax_error.golden.json").read_text(encoding="utf-8"))
    assert actual == expected
    assert actual["parse"]["has_syntax_errors"] is True
    assert actual["chunks"][0]["fallback_reason"] == "syntax_error_threshold_exceeded"


def test_multilanguage_golden_fixtures_share_the_parser_contract(tmp_path):
    cases = (
        ("javascript", "conformance.js", {"greet", "Greeter", "constructor", "say", "normalize"}),
        (
            "typescript",
            "conformance.ts",
            {"Color", "Base", "run", "Tools", "go", "Shape", "Point"},
        ),
        ("tsx", "conformance.tsx", {"Props", "View"}),
        (
            "java",
            "conformance.java",
            {"Outer", "Outer", "run", "Inner", "Shade", "Point"},
        ),
    )
    repository = RepositoryInfo("golden-repo", "golden", "local", "file:///golden")
    registry = LanguageRegistry()
    from ragforge.parsing.tree_sitter import (
        JavaParser,
        JavaScriptParser,
        TSXParser,
        TypeScriptParser,
    )

    registry.register(JavaScriptParser(), "jsx")
    registry.register(TypeScriptParser())
    registry.register(TSXParser())
    registry.register(JavaParser())

    for language, filename, expected_names in cases:
        fixture = Path(__file__).parents[2] / "fixtures" / "parsing" / language / filename
        raw = fixture.read_bytes()
        document = build_document(
            repository, filename, raw.decode("utf-8"), len(raw)
        )
        if language == "tsx":
            from dataclasses import replace

            document = replace(document, language="typescript")
            assert registry.get("tsx").__class__.__name__ == "TSXParser"
        result = assert_parser_contract(registry.get(language), document)
        symbols = _flatten(result.symbols)
        assert expected_names <= {symbol.name for symbol in symbols}
        if language == "javascript":
            assert "item" not in {symbol.name for symbol in symbols}
            assert next(symbol for symbol in symbols if symbol.name == "normalize").signature == (
                "normalize = (value) =>"
            )
        elif language == "typescript":
            assert {symbol.symbol_type for symbol in symbols} >= {
                "enum",
                "class",
                "namespace",
                "interface",
                "type_alias",
                "method",
            }
            assert next(symbol for symbol in symbols if symbol.name == "go").qualified_name == (
                "Tools.go"
            )
        elif language == "tsx":
            assert result.language == "tsx"
            chunk_text = "\n".join(
                chunk.content for chunk in chunk_document(document)
            )
            assert "name.toUpperCase()" in chunk_text
        if language == "java":
            outer = next(symbol for symbol in symbols if symbol.name == "Outer")
            constructor = next(symbol for symbol in symbols if symbol.symbol_type == "constructor")
            overloads = [
                symbol
                for symbol in symbols
                if symbol.qualified_name == "Outer.run" and symbol.symbol_type == "method"
            ]
            assert outer.documentation == "/** Public API for conformance. */"
            assert constructor.documentation == "/** Construct an outer value. */"
            assert len(overloads) == 2 and overloads[0].symbol_key != overloads[1].symbol_key
            assert any(
                symbol.symbol_type == "enum" and symbol.name == "Shade"
                for symbol in symbols
            )
            assert any(
                symbol.symbol_type == "record" and symbol.name == "Point"
                for symbol in symbols
            )
        actual = _snapshot(document)
        golden = fixture.with_suffix(".golden.json")
        expected = json.loads(golden.read_text(encoding="utf-8"))
        assert actual == expected, f"golden mismatch for {filename}"
        first = chunk_document(document)
        second = chunk_document(document)
        first_path = tmp_path / f"{language}-one.jsonl"
        second_path = tmp_path / f"{language}-two.jsonl"
        write_jsonl(first, first_path)
        write_jsonl(second, second_path)
        assert first_path.read_bytes() == second_path.read_bytes(), filename


def test_all_language_fixtures_have_exact_byte_coverage():
    fixture_root = FIXTURES.parent
    source_extensions = {".py", ".js", ".ts", ".tsx", ".java"}
    checked = 0
    for fixture in sorted(fixture_root.rglob("*")):
        if not fixture.is_file() or fixture.suffix not in source_extensions:
            continue
        source = fixture.read_bytes()
        relative_path = fixture.relative_to(fixture_root).as_posix()
        document = build_document(
            RepositoryInfo("golden-repo", "golden", "local", "file:///golden"),
            relative_path,
            source.decode("utf-8"),
            len(source),
        )
        chunks = chunk_document(document)
        coverage = sorted(
            (chunk.start_byte, chunk.end_byte, chunk.content.encode("utf-8"))
            for chunk in chunks
            if chunk.metadata.get("coverage")
        )
        cursor = 0
        for start, end, content in coverage:
            assert start == cursor, f"coverage gap or overlap in {relative_path} at byte {cursor}"
            assert source[start:end] == content
            cursor = end
        assert cursor == len(source), f"incomplete coverage in {relative_path} at byte {cursor}"
        checked += 1
    assert checked >= 6
