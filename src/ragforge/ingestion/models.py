
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

SourceType = Literal["github", "zip", "local"]


@dataclass(frozen=True, slots=True)
class RepositoryInfo:
    repository_id: str
    name: str
    source_type: SourceType
    source_uri: str
    commit_sha: str | None = None
    default_branch: str | None = None


@dataclass(frozen=True, slots=True)
class RepoSnapshot:
    root_path: Path
    repository: RepositoryInfo


@dataclass(frozen=True, slots=True)
class Document:
    document_id: str
    repository_id: str
    file_path: str
    extension: str
    language: str
    content: str
    size_bytes: int
    content_hash: str
    line_count: int
    metadata: dict = field(default_factory=dict)

    @property
    def file_name(self) -> str:
        return self.file_path.rsplit("/", 1)[-1]


@dataclass(frozen=True, slots=True)
class IngestionResult:
    repository: RepositoryInfo
    documents: tuple[Document, ...]
    discovered_files: int
    processed_files: int
    skipped_files: int
    skip_reasons: dict[str, int] = field(default_factory=dict)
