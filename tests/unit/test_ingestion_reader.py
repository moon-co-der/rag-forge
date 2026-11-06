

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.reader import read_file


def test_reads_text_file(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("print('hello')", encoding="utf-8")

    result = read_file(path, IngestionConfig())

    assert result.success
    assert result.content == "print('hello')"
    assert result.skip_reason is None


def test_normalizes_line_endings(tmp_path):
    path = tmp_path / "app.py"
    path.write_bytes(b"line1\r\nline2\rline3")

    result = read_file(path, IngestionConfig())

    assert result.success
    assert result.content == "line1\nline2\nline3"


def test_reads_utf8_bom(tmp_path):
    path = tmp_path / "readme.md"
    path.write_bytes(b"\xef\xbb\xbfHello")

    result = read_file(path, IngestionConfig())

    assert result.success
    assert result.content == "Hello"


def test_skips_empty_file(tmp_path):
    path = tmp_path / "empty.py"
    path.write_bytes(b"")

    result = read_file(path, IngestionConfig())

    assert not result.success
    assert result.skip_reason == "empty_file"


def test_skips_binary_file(tmp_path):
    path = tmp_path / "image.py"
    path.write_bytes(b"hello\x00world")

    result = read_file(path, IngestionConfig())

    assert not result.success
    assert result.skip_reason == "binary_file"


def test_skips_oversized_file(tmp_path):
    path = tmp_path / "large.py"
    path.write_text("x" * 100)

    config = IngestionConfig(max_file_size_bytes=50)
    result = read_file(path, config)

    assert not result.success
    assert result.skip_reason == "file_too_large"


def test_uses_fallback_encoding(tmp_path):
    path = tmp_path / "text.py"
    path.write_bytes("café".encode("latin-1"))

    result = read_file(path, IngestionConfig())

    assert result.success
    assert result.content == "café"


def test_reports_decoding_error(tmp_path):
    path = tmp_path / "text.py"
    path.write_bytes(b"\xff\xfe")

    config = IngestionConfig(encoding_fallbacks=("unknown-encoding",))
    result = read_file(path, config)

    assert not result.success
    assert result.skip_reason == "decoding_error"


def test_skips_whitespace_only_file(tmp_path):
    path = tmp_path / "blank.py"
    path.write_text("   \n\t  ")

    result = read_file(path, IngestionConfig())

    assert not result.success
    assert result.skip_reason == "empty_file"
