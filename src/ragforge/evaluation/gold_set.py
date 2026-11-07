"""Validation and JSONL loading for the M3 question gold set."""

import json
import re
from pathlib import Path, PurePosixPath
from typing import Any

_QUESTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SNAPSHOT_ID = re.compile(r"^[0-9a-f]{64}$")
_CATEGORIES = {"exact_symbol", "conceptual", "cross_file", "overview", "unanswerable"}
_SPLITS = {"dev", "test"}
_QUESTION_FIELDS = {
    "question_id",
    "text",
    "category",
    "answerable",
    "gold_spans",
    "snapshot_id",
    "split",
    "reference_answer",
}


def validate_gold_question(record: dict[str, Any]) -> None:
    """Raise ``ValueError`` unless a mapping conforms to the gold-set contract."""
    if not isinstance(record, dict):
        raise ValueError("question record must be an object")
    missing = _QUESTION_FIELDS - {"reference_answer"} - record.keys()
    unknown = record.keys() - _QUESTION_FIELDS
    if missing:
        raise ValueError(f"missing question fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"unknown question fields: {', '.join(sorted(unknown))}")
    if not isinstance(record["question_id"], str) or not _QUESTION_ID.fullmatch(
        record["question_id"]
    ):
        raise ValueError("question_id must be a non-empty stable identifier")
    if not isinstance(record["text"], str) or not record["text"].strip():
        raise ValueError("text must be a non-empty string")
    if not isinstance(record["category"], str) or record["category"] not in _CATEGORIES:
        raise ValueError(f"category must be one of {', '.join(sorted(_CATEGORIES))}")
    if type(record["answerable"]) is not bool:
        raise ValueError("answerable must be a boolean")
    if not isinstance(record["snapshot_id"], str) or not _SNAPSHOT_ID.fullmatch(
        record["snapshot_id"]
    ):
        raise ValueError("snapshot_id must be a 64-character lowercase SHA-256")
    if not isinstance(record["split"], str) or record["split"] not in _SPLITS:
        raise ValueError("split must be 'dev' or 'test'")
    if "reference_answer" in record and not isinstance(record["reference_answer"], str):
        raise ValueError("reference_answer must be a string when provided")
    spans = record["gold_spans"]
    if not isinstance(spans, list):
        raise ValueError("gold_spans must be an array")
    if record["answerable"]:
        if record["category"] == "unanswerable" or not spans:
            raise ValueError("answerable questions need a non-unanswerable category and spans")
    elif record["category"] != "unanswerable" or spans:
        raise ValueError("unanswerable questions must use the unanswerable category and no spans")
    for index, span in enumerate(spans):
        _validate_span(span, index)


def _validate_span(span: Any, index: int) -> None:
    label = f"gold_spans[{index}]"
    if not isinstance(span, dict) or not isinstance(span.get("file_path"), str):
        raise ValueError(f"{label} must be an object with file_path")
    file_path = span["file_path"]
    path = PurePosixPath(file_path)
    if (
        not file_path
        or "\\" in file_path
        or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"{label}.file_path must be a safe repository-relative POSIX path")
    line_fields = {"start_line", "end_line"}
    allowed = {"file_path", "start_line", "end_line", "symbol"}
    if span.keys() - allowed:
        raise ValueError(f"{label} contains unknown fields")
    has_lines = line_fields <= span.keys()
    has_symbol = isinstance(span.get("symbol"), str) and bool(span["symbol"].strip())
    if has_lines == has_symbol or bool(line_fields & span.keys()) != has_lines:
        raise ValueError(f"{label} must specify either a line range or a symbol")
    if has_lines:
        start, end = span["start_line"], span["end_line"]
        if type(start) is not int or type(end) is not int or start < 1 or end < start:
            raise ValueError(f"{label} lines must be one-based integers in ascending order")


def load_gold_set_jsonl(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Load and validate JSONL records, rejecting malformed or duplicate IDs."""
    records = []
    question_ids: set[str] = set()
    with Path(path).open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            try:
                value = json.loads(line)
                validate_gold_question(value)
            except (json.JSONDecodeError, ValueError) as exc:
                raise ValueError(f"Invalid gold-set record at line {line_number}: {exc}") from exc
            question_id = value["question_id"]
            if question_id in question_ids:
                raise ValueError(
                    f"Invalid gold-set record at line {line_number}: duplicate question_id "
                    f"{question_id!r}"
                )
            question_ids.add(question_id)
            records.append(value)
    return tuple(records)
