
from pathlib import Path

import pytest

from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.scanner import scan_repository


@pytest.fixture
def sample_repository(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "node_modules").mkdir()

    (tmp_path / "src" / "app.py").write_text("print('hello')")
    (tmp_path / "README.md").write_text("# Project")
    (tmp_path / "notes.xyz").write_text("Ignore this")
    (tmp_path / "node_modules" / "package.py").write_text("Ignore this")

    return tmp_path


def test_discovers_supported_files(sample_repository):
    config = IngestionConfig()

    files = list(scan_repository(sample_repository, config))

    relative_paths = {
        path.relative_to(sample_repository).as_posix()
        for path in files
    }

    assert "src/app.py" in relative_paths
    assert "README.md" in relative_paths
    assert "notes.xyz" not in relative_paths


def test_skips_excluded_directories(sample_repository):
    config = IngestionConfig()

    files = list(scan_repository(sample_repository, config))

    assert not any("node_modules" in path.parts for path in files)


def test_skips_hidden_files(tmp_path):
    (tmp_path / ".secret.py").write_text("secret")
    (tmp_path / ".env.example").write_text("APP_ENV=dev")

    config = IngestionConfig()

    files = list(scan_repository(tmp_path, config))
    filenames = {path.name for path in files}

    assert ".secret.py" not in filenames
    assert ".env.example" in filenames


def test_skips_oversized_files(tmp_path):
    (tmp_path / "small.py").write_text("hello")
    (tmp_path / "large.py").write_text("x" * 100)

    config = IngestionConfig(max_file_size_bytes=50)

    files = list(scan_repository(tmp_path, config))
    filenames = {path.name for path in files}

    assert "small.py" in filenames
    assert "large.py" not in filenames


def test_invalid_repository_path():
    config = IngestionConfig()

    with pytest.raises(ValueError):
        list(scan_repository(Path("does-not-exist"), config))


def test_excluded_glob(tmp_path):
    (tmp_path / "app.py").write_text("print('hello')")
    (tmp_path / "bundle.min.js").write_text("minified code")

    config = IngestionConfig()

    files = list(scan_repository(tmp_path, config))
    filenames = {path.name for path in files}

    assert "app.py" in filenames
    assert "bundle.min.js" not in filenames
