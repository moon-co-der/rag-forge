"""Resolve GitHub repository references only at a verified immutable commit."""

import re
import subprocess
import tempfile
from pathlib import Path

from ragforge.ingestion.models import RepositoryInfo, RepoSnapshot

_GITHUB_URL = re.compile(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
_FULL_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def resolve_github(
    repository_url: str,
    commit_sha: str,
    destination: str | Path | None = None,
) -> RepoSnapshot:
    """Fetch and checkout the exact commit SHA; branch and tag names are rejected."""
    match = _GITHUB_URL.fullmatch(repository_url)
    if not match:
        raise ValueError("repository_url must be an HTTPS GitHub owner/repository URL")
    if not _FULL_SHA.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full 40-character hexadecimal commit SHA")
    owner, name = match.groups()
    canonical_url = f"https://github.com/{owner}/{name}.git"
    repository_id = f"github:{owner.lower()}/{name.lower()}"
    root = Path(destination) if destination is not None else Path(
        tempfile.mkdtemp(prefix="ragforge-github-")
    )
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "--quiet")
    _git(root, "remote", "add", "origin", canonical_url)
    requested = commit_sha.lower()
    _git(root, "fetch", "--quiet", "--depth=1", "origin", requested)
    resolved = _git(root, "rev-parse", "FETCH_HEAD^{commit}").lower()
    if resolved != requested:
        raise ValueError(f"GitHub resolved commit {resolved}, expected {requested}")
    _git(root, "checkout", "--quiet", "--detach", requested)
    checked_out = _git(root, "rev-parse", "HEAD^{commit}").lower()
    if checked_out != requested:
        raise ValueError(f"GitHub checkout is {checked_out}, expected {requested}")
    repository = RepositoryInfo(
        repository_id=repository_id,
        name=f"{owner}/{name}",
        source_type="github",
        source_uri=canonical_url,
        commit_sha=requested,
    )
    return RepoSnapshot(root.resolve(), repository)


def _git(root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError(f"GitHub resolution failed during git {arguments[0]}") from exc
    return result.stdout.strip()
