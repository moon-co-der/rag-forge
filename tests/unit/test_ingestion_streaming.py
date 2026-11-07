from ragforge.ingestion.config import IngestionConfig
from ragforge.ingestion.resolvers.local import resolve_local
from ragforge.ingestion.streaming import iter_ingestion


def test_streaming_yields_sorted_success_and_oversized_skip_events(tmp_path):
    (tmp_path / "b.py").write_text("b=2\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("a=1\n", encoding="utf-8")
    (tmp_path / "large.py").write_text("x" * 100, encoding="utf-8")
    snapshot = resolve_local(tmp_path, "stream-project")
    events = list(iter_ingestion(snapshot, IngestionConfig(max_file_size_bytes=10)))
    file_events, summary = events[:-1], events[-1]
    assert [event.file_path for event in file_events] == ["a.py", "b.py", "large.py"]
    assert all(event.document is not None for event in events[:2])
    assert file_events[2].document is None
    assert file_events[2].skip_reason == "file_too_large"
    assert summary.snapshot_manifest is not None
    assert summary.discovered_files == 3
    assert summary.processed_files == 2
    assert summary.skip_reasons == {"file_too_large": 1}


def test_streaming_is_repeatable_and_does_not_stop_after_read_error(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_text("a=1\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("b=2\n", encoding="utf-8")
    snapshot = resolve_local(tmp_path, "stream-project")
    import ragforge.ingestion.streaming as streaming

    original = streaming.read_file

    def interrupted(path, config):
        if path.name == "a.py":
            from ragforge.ingestion.reader import FileReadResult

            return FileReadResult(None, 4, "read_error")
        return original(path, config)

    monkeypatch.setattr(streaming, "read_file", interrupted)
    first = list(iter_ingestion(snapshot, IngestionConfig()))
    second = list(iter_ingestion(snapshot, IngestionConfig()))
    assert [(item.file_path, item.skip_reason) for item in first] == [
        (item.file_path, item.skip_reason) for item in second
    ]
    assert first[0].skip_reason == "read_error"
    assert first[1].document is not None
    assert first[-1].snapshot_manifest is not None
    assert first[-1].snapshot_manifest.to_dict() == second[-1].snapshot_manifest.to_dict()
    assert first[-1].skip_reasons == {"read_error": 1}


def test_streaming_can_be_consumed_incrementally(tmp_path):
    for index in range(100):
        (tmp_path / f"{index:03}.py").write_text(f"value={index}\n", encoding="utf-8")
    events = iter_ingestion(resolve_local(tmp_path, "large-stream"), IngestionConfig())
    first = next(events)
    assert first.file_path == "000.py"
    assert first.document is not None
    events.close()
