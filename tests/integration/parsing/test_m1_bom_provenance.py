from ragforge.chunking import chunk_document
from ragforge.ingestion.local_ingestion import ingest_local


def test_m1_document_retains_bom_and_crlf_bytes_for_m2_coverage(tmp_path):
    source = "\ufeff# 🧪 தமிழ்\r\ndef greet():\r\n    return '🙂'\r\n"
    file_path = tmp_path / "greet.py"
    file_path.write_bytes(source.encode("utf-8"))

    document = ingest_local(tmp_path).documents[0]
    chunks = chunk_document(document)
    coverage = sorted(
        (chunk.start_byte, chunk.end_byte, chunk.content.encode("utf-8"))
        for chunk in chunks
        if chunk.metadata.get("coverage")
    )
    cursor = 0
    recovered = bytearray()
    for start, end, part in coverage:
        assert start == cursor
        assert end - start == len(part)
        recovered.extend(part)
        cursor = end
    assert cursor == len(source.encode("utf-8"))
    assert bytes(recovered) == source.encode("utf-8")
    assert document.content.startswith("#")
