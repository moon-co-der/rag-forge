import json
from pathlib import Path

import pytest

from ragforge.evaluation.gold_set import load_gold_set_jsonl, validate_gold_question
from ragforge.evaluation.snapshots import pinned_snapshot_id

ROOT = Path(__file__).parents[2]
SNAPSHOT_ID = "a" * 64


def question(**overrides):
    value = {
        "question_id": "dev-001",
        "text": "Where is the repository scanner defined?",
        "category": "exact_symbol",
        "answerable": True,
        "gold_spans": [
            {"file_path": "src/ragforge/ingestion/scanner.py", "symbol": "scan_repository"}
        ],
        "snapshot_id": SNAPSHOT_ID,
        "split": "dev",
    }
    return {**value, **overrides}


def test_pinned_repository_snapshots_are_stable_and_content_addressed():
    url = "https://github.com/example/project.git"
    sha = "0123456789abcdef0123456789abcdef01234567"
    assert pinned_snapshot_id(url, sha) == pinned_snapshot_id(url, sha)
    assert pinned_snapshot_id(url, sha) != pinned_snapshot_id(url, "f" * 40)
    with pytest.raises(ValueError, match="full 40-character"):
        pinned_snapshot_id(url, sha[:8])


def test_pinned_evaluation_repositories_are_revisioned_and_varied():
    repositories = json.loads((ROOT / "evaluation" / "repositories.json").read_text())
    assert 2 <= len(repositories) <= 3
    assert any(item["developer_familiar"] for item in repositories)
    assert len({item["commit_sha"] for item in repositories}) == len(repositories)
    assert {language for item in repositories for language in item["languages"]} >= {
        "python",
        "typescript",
        "tsx",
        "java",
    }
    for item in repositories:
        assert len(item["commit_sha"]) == 40
        assert item["snapshot_id"] == pinned_snapshot_id(item["url"], item["commit_sha"])
        assert item["source_files"] > 0


def test_gold_set_json_schema_declares_the_required_contract():
    schema = json.loads((ROOT / "schemas" / "gold_set.schema.json").read_text())
    assert schema["$schema"].endswith("2020-12/schema")
    assert set(schema["required"]) == {
        "question_id",
        "text",
        "category",
        "answerable",
        "gold_spans",
        "snapshot_id",
        "split",
    }
    assert {"start_line", "end_line", "symbol"} <= set(
        schema["properties"]["gold_spans"]["items"]["properties"]
    )


def test_gold_question_accepts_line_and_symbol_spans_and_optional_reference():
    validate_gold_question(question(reference_answer="The scanner is in scanner.py."))
    validate_gold_question(
        question(gold_spans=[{"file_path": "src/main.py", "start_line": 2, "end_line": 4}])
    )
    validate_gold_question(
        question(
            category="unanswerable",
            answerable=False,
            gold_spans=[],
            split="test",
        )
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"question_id": ""},
        {"text": " "},
        {"category": "other"},
        {"category": []},
        {"answerable": 1},
        {"snapshot_id": "not-a-snapshot"},
        {"split": "validation"},
        {"split": []},
        {"answerable": False},
        {"gold_spans": [{"file_path": "../escape.py", "symbol": "f"}]},
        {"gold_spans": [{"file_path": "a.py", "start_line": 4, "end_line": 2}]},
        {"gold_spans": [{"file_path": "a.py", "symbol": "f", "start_line": 1, "end_line": 2}]},
    ],
)
def test_gold_question_rejects_malformed_records(overrides):
    with pytest.raises(ValueError):
        validate_gold_question(question(**overrides))


def test_jsonl_loader_rejects_malformed_json_and_duplicate_question_ids(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text(json.dumps(question()) + "\n{" + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_gold_set_jsonl(path)
    path.write_text(json.dumps(question()) + "\n" + json.dumps(question()) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate question_id"):
        load_gold_set_jsonl(path)
