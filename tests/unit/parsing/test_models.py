import pytest

from ragforge.parsing.models import ParsedSymbol, ParseError, ParseResult


def test_parsed_symbol_supports_nested_records_and_metadata():
    child = ParsedSymbol(
        "child",
        "inner",
        "function",
        "python",
        "src/a.py",
        2,
        3,
        10,
        20,
        "def inner()",
        parent_symbol_id="parent",
    )
    parent = ParsedSymbol(
        "parent",
        "outer",
        "function",
        "python",
        "src/a.py",
        1,
        4,
        0,
        30,
        "def outer()",
        children=(child,),
        metadata={"decorators": ["@cache"]},
    )
    result = ParseResult("doc", "repo", "src/a.py", "python", (parent,))
    assert result.symbols[0].children[0].name == "inner"
    assert parent.metadata["decorators"] == ["@cache"]


def test_symbol_and_error_models_validate_source_ranges():
    with pytest.raises(ValueError, match="line range"):
        ParsedSymbol("id", "name", "function", "python", "a.py", 0, 1, 0, 2, "def name")
    with pytest.raises(ValueError, match="byte range"):
        ParsedSymbol("id", "name", "function", "python", "a.py", 1, 1, 2, 1, "def name")
    with pytest.raises(ValueError, match="ordered"):
        ParseError("bad syntax", 3, 2)
    child = ParsedSymbol("child", "inner", "function", "python", "a.py", 1, 1, 0, 1, "x")
    with pytest.raises(ValueError, match="containing symbol"):
        ParsedSymbol(
            "parent", "outer", "class", "python", "a.py", 1, 1, 0, 1, "x", children=(child,)
        )
