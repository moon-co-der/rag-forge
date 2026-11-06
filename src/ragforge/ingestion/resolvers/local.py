
import hashlib
from pathlib import Path

from ragforge.ingestion.models import RepositoryInfo, RepoSnapshot


def resolve_local(source: str | Path) -> RepoSnapshot:
    """Validate and resolve a local repository directory."""

    root = Path(source).expanduser()

    if not root.exists():
        raise FileNotFoundError(f"Repository directory not found: {root}")

    if root.is_symlink():
        raise ValueError("Repository root cannot be a symbolic link.")

    if not root.is_dir():
        raise ValueError(f"Source is not a directory: {root}")

    root = root.resolve()

    repository_id = hashlib.sha256(
        str(root).encode("utf-8")
    ).hexdigest()[:12]

    repository = RepositoryInfo(
        repository_id=repository_id,
        name=root.name,
        source_type="local",
        source_uri=root.as_uri(),
    )

    return RepoSnapshot(
        root_path=root,
        repository=repository,
    )
