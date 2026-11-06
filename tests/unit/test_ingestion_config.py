
import pytest

from ragforge.ingestion.config import IngestionConfig


def test_default_configuration():
    config = IngestionConfig()

    assert ".py" in config.include_extensions
    assert ".md" in config.include_extensions
    assert "node_modules" in config.exclude_dirs
    assert config.max_file_size_bytes == 1_048_576
    assert config.follow_symlinks is False


def test_custom_file_size():
    config = IngestionConfig(max_file_size_bytes=2_000_000)

    assert config.max_file_size_bytes == 2_000_000


def test_invalid_file_size():
    with pytest.raises(ValueError):
        IngestionConfig(max_file_size_bytes=0)


def test_invalid_extension():
    with pytest.raises(ValueError):
        IngestionConfig(include_extensions=frozenset({"py", ".md"}))


def test_empty_encoding_fallbacks():
    with pytest.raises(ValueError):
        IngestionConfig(encoding_fallbacks=())
