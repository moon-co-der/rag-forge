from ragforge.chunking import StructuralChunker
from ragforge.ingestion.document_builder import build_document
from ragforge.ingestion.models import RepositoryInfo
from ragforge.parsing import parse_document


def test_ingested_document_flows_through_parser_and_chunker():
    repository = RepositoryInfo("repo", "repo", "local", "file:///repo")
    source = "import math\n\ndef area(radius):\n    return math.pi * radius ** 2\n"
    document = build_document(repository, "src/geometry.py", source, len(source.encode()))

    parsed = parse_document(document)
    chunks = StructuralChunker().chunk(document, parsed)

    symbol = next(chunk for chunk in chunks if chunk.symbol_name == "area")
    assert symbol.document_id == document.document_id
    assert symbol.repository_id == repository.repository_id
    assert symbol.file_path == document.file_path
    assert symbol.signature.startswith("def area(radius)")
    top_level_content = "".join(chunk.content for chunk in chunks if chunk.parent_chunk_id is None)
    assert top_level_content == source
