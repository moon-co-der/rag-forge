"""Stable identifiers for commit-pinned evaluation repository snapshots."""

import hashlib
import re

_FULL_COMMIT = re.compile(r"^[0-9a-f]{40}$")


def pinned_snapshot_id(repository_url: str, commit_sha: str) -> str:
    """Return a stable ID for one immutable repository revision."""
    if not repository_url.startswith(("https://", "ssh://", "git@")):
        raise ValueError("repository_url must identify a remote Git repository")
    if not _FULL_COMMIT.fullmatch(commit_sha):
        raise ValueError("commit_sha must be a full 40-character lowercase Git SHA")
    identity = f"{repository_url.rstrip('/')}@{commit_sha}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
