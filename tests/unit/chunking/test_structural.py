from ragforge.chunking import ChunkingConfig, StructuralChunker
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo
from ragforge.parsing import parse_document

REPOSITORY = RepositoryInfo("repo", "repo", "local", "file:///repo")


def make_document(content, path="src/app.py", language="python"):
    return build_document(REPOSITORY, path, content, len(content.encode()))


def test_structural_chunks_keep_hierarchy_locations_and_source_context():
    source = "import os\n\nclass A:\n    def f(self):\n        return 1\n\n# loose note\n"
    document = make_document(source)
    parsed = parse_document(document)
    chunks = StructuralChunker().chunk(document, parsed)
    class_chunk = next(chunk for chunk in chunks if chunk.symbol_name == "A")
    method_chunk = next(chunk for chunk in chunks if chunk.symbol_name == "f")
    assert method_chunk.parent_chunk_id == class_chunk.chunk_id
    assert class_chunk.start_line == 3
    assert method_chunk.start_line == 4
    assert any(
        chunk.symbol_type == "module_residue" and "import os" in chunk.content for chunk in chunks
    )
    assert any(
        chunk.symbol_type == "module_residue" and "loose note" in chunk.content for chunk in chunks
    )
    assert class_chunk.metadata["coverage"] is False
    assert method_chunk.metadata["coverage"] is True
    assert method_chunk.context_header == "src/app.py > A.f"
    assert method_chunk.qualified_name == "A.f"
    assert method_chunk.metadata["enclosing_class"] == "A"
    assert method_chunk.metadata["parent_symbol_key"]
    assert "def f(self)" in class_chunk.content
    assert "return 1" not in class_chunk.content
    assert "src/app.py > A.f" not in method_chunk.content
    assert any(
        "class A:" in chunk.content
        for chunk in chunks
        if chunk.symbol_type == "module_residue"
    )


def test_oversized_functions_split_without_losing_source_and_ids_are_stable():
    source = "def f():\n" + "    value = 1\n" * 30
    document = make_document(source)
    parsed = parse_document(document)
    chunker = StructuralChunker()
    config = ChunkingConfig(max_chunk_size=35)
    chunks = chunker.chunk(document, parsed, config)
    function_chunks = [chunk for chunk in chunks if chunk.symbol_name == "f"]
    assert len(function_chunks) > 1
    assert "".join(chunk.content for chunk in function_chunks) == source.rstrip("\n")
    assert chunks == chunker.chunk(document, parsed, config)
    changed = make_document(source.replace("value = 1", "value = 2", 1))
    changed_chunks = chunker.chunk(changed, parse_document(changed), config)
    assert (
        function_chunks[0].chunk_id
        != next(c for c in changed_chunks if c.symbol_name == "f").chunk_id
    )


def test_fallback_for_unparsed_and_unsupported_files_preserves_content():
    chunker = StructuralChunker()
    config = ChunkingConfig(fallback_chunk_size=12)
    for doc, parsed in [
        (make_document("broken text\nmore text", "broken.py"), None),
        (make_document("plain unsupported text\nnext", "notes.xyz", "unknown"), None),
    ]:
        chunks = chunker.chunk(doc, parsed, config)
        assert "".join(chunk.content for chunk in chunks) == doc.content
        assert all(chunk.chunk_origin == "fallback" for chunk in chunks)
    assert any(
        chunk.metadata["is_trivial"]
        for chunk in chunker.chunk(
            make_document("plain unsupported text\nnext", "notes.xyz", "unknown"),
            None,
            config,
        )
    )


def test_parse_error_uses_configured_fallback():
    doc = make_document("def broken(:\n pass\n")
    parsed = parse_document(doc)
    chunks = StructuralChunker().chunk(doc, parsed)
    assert len(chunks) == 1
    assert chunks[0].metadata["fallback_reason"] == "syntax_error_threshold_exceeded"


def test_syntax_error_threshold_can_keep_valid_recovered_symbols():
    from ragforge.chunking import ChunkingConfig

    doc = make_document("def good():\n    return 1\n\ndef broken(:\n    pass\n")
    parsed = parse_document(doc)
    chunks = StructuralChunker().chunk(
        doc, parsed, ChunkingConfig(syntax_error_threshold=len(parsed.errors))
    )
    assert any(chunk.symbol_name == "good" for chunk in chunks)
    assert all(chunk.chunk_origin == "structural" for chunk in chunks)


def test_oversized_file_policy_supports_controlled_fallback_and_skip():
    from ragforge.parsing import ParsingConfig, parse_document

    doc = make_document("def f():\n    return 1\n")
    fallback_parse = parse_document(
        doc, config=ParsingConfig(max_source_size_bytes=4, oversized_file_policy="fallback")
    )
    fallback = StructuralChunker().chunk(doc, fallback_parse)
    assert fallback and fallback[0].metadata["fallback_reason"] == "source_size_limit"
    skipped_parse = parse_document(
        doc, config=ParsingConfig(max_source_size_bytes=4, oversized_file_policy="skip")
    )
    assert StructuralChunker().chunk(doc, skipped_parse) == ()


def test_leaf_and_residue_intervals_cover_every_source_byte_once():
    source = (
        "\ufeff# 🧪 தமிழ் comment\r\n"
        "import os\r\n\r\n"
        "class A:\r\n"
        '    """தமிழ் docs"""\r\n'
        "    def outer(self):\r\n"
        "        def inner():\r\n            return '🙂'\r\n"
        "        return inner()\r\n"
        "value = 3\r\n"
    )
    document = make_document(source)
    chunks = StructuralChunker().chunk(document, parse_document(document))
    covered = sorted(
        (chunk.start_byte, chunk.end_byte, chunk.content.encode("utf-8"))
        for chunk in chunks
        if chunk.metadata.get("coverage")
    )
    expected = source.encode("utf-8")
    cursor = 0
    reconstructed = bytearray()
    for start, end, content in covered:
        assert start == cursor
        assert end - start == len(content)
        reconstructed.extend(content)
        cursor = end
    assert cursor == len(expected)
    assert bytes(reconstructed) == expected


def test_symbol_key_is_stable_for_body_edits_and_duplicate_names_are_distinct():
    first = make_document("def same():\n    return 1\n\ndef same():\n    return 2\n")
    changed = make_document("def same():\n    return 9\n\ndef same():\n    return 2\n")
    first_symbols = parse_document(first).symbols
    changed_symbols = parse_document(changed).symbols
    assert [symbol.symbol_key for symbol in first_symbols] == [
        symbol.symbol_key for symbol in changed_symbols
    ]
    assert first_symbols[0].symbol_key != first_symbols[1].symbol_key


def test_symbol_and_chunk_id_semantics_for_body_edits_and_unchanged_symbols():
    from ragforge.parsing.identifiers import make_symbol_key

    source = (
        "def changed():\n    return 1\n\n"
        "def stable():\n    return 'same'\n"
    )
    edited = source.replace("return 1", "return 2")
    original_chunks = StructuralChunker().chunk(
        make_document(source), parse_document(make_document(source))
    )
    edited_document = make_document(edited)
    edited_chunks = StructuralChunker().chunk(
        edited_document, parse_document(edited_document)
    )
    original = {chunk.symbol_name: chunk for chunk in original_chunks if chunk.symbol_name}
    changed = {chunk.symbol_name: chunk for chunk in edited_chunks if chunk.symbol_name}

    assert original["changed"].symbol_key == changed["changed"].symbol_key
    assert original["changed"].content_hash != changed["changed"].content_hash
    assert original["changed"].chunk_id != changed["changed"].chunk_id
    assert (
        original["stable"].symbol_key,
        original["stable"].content_hash,
        original["stable"].chunk_id,
    ) == (
        changed["stable"].symbol_key,
        changed["stable"].content_hash,
        changed["stable"].chunk_id,
    )
    expected = make_symbol_key("repo", "src/app.py", "changed", "function", 0)
    assert original["changed"].symbol_key == expected


def test_chunk_ids_do_not_depend_on_top_level_symbol_traversal_order():
    from dataclasses import replace

    document = make_document(
        "def first():\n    return 1\n\ndef second():\n    return 2\n"
    )
    parsed = parse_document(document)
    reversed_result = replace(parsed, symbols=tuple(reversed(parsed.symbols)))
    chunker = StructuralChunker()
    assert chunker.chunk(document, parsed) == chunker.chunk(document, reversed_result)


def test_same_name_methods_and_duplicate_ordinals_have_stable_logical_keys():
    source = (
        "class A:\n"
        "    def f(self):\n        return 1\n"
        "    def f(self):\n        return 2\n"
        "class B:\n"
        "    def f(self):\n        return 3\n"
    )
    result = parse_document(make_document(source))
    methods = [symbol for symbol in result.symbols for symbol in symbol.children]
    keys = {symbol.qualified_name: symbol.symbol_key for symbol in methods}
    assert set(keys) == {"A.f", "B.f"}
    assert keys["A.f"] != keys["B.f"]
    a_methods = [symbol for symbol in methods if symbol.qualified_name == "A.f"]
    assert len(a_methods) == 2
    assert a_methods[0].symbol_key != a_methods[1].symbol_key


def test_java_overloads_receive_distinct_symbol_keys():
    source = (
        "class A { int f(int x) { return x; } "
        "int f(String x) { return 1; } } "
        "class B { int f(int x) { return x; } }"
    )
    result = parse_document(make_document(source, "A.java", "java"))
    methods = [
        symbol
        for symbol in result.symbols
        for symbol in symbol.children
        if symbol.name == "f"
    ]
    a_overloads = [symbol for symbol in methods if symbol.qualified_name == "A.f"]
    b_methods = [symbol for symbol in methods if symbol.qualified_name == "B.f"]
    assert len(a_overloads) == 2
    assert len(b_methods) == 1
    assert len({symbol.symbol_key for symbol in methods}) == 3


def test_trivial_source_chunks_are_flagged_without_losing_byte_coverage():
    source = "def f():\n    return 1\n\n"
    document = make_document(source)
    chunks = StructuralChunker().chunk(document, parse_document(document))
    tiny = [chunk for chunk in chunks if len(chunk.content) <= 8]
    assert tiny
    assert all(chunk.metadata["is_trivial"] for chunk in tiny)
    assert b"".join(
        chunk.content.encode("utf-8")
        for chunk in sorted(
            (chunk for chunk in chunks if chunk.metadata["coverage"]),
            key=lambda chunk: chunk.start_byte,
        )
    ) == source.encode("utf-8")
