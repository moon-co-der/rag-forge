
import pytest

from ragforge.ingestion.resolvers import github

SHA = "0123456789abcdef0123456789abcdef01234567"


def test_github_resolver_fetches_and_verifies_pinned_detached_commit(tmp_path, monkeypatch):
    calls = []

    def fake_git(root, *args):
        calls.append(args)
        if args[:2] == ("rev-parse", "FETCH_HEAD^{commit}"):
            return SHA
        if args[:2] == ("rev-parse", "HEAD^{commit}"):
            return SHA
        return ""

    monkeypatch.setattr(github, "_git", fake_git)
    result = github.resolve_github(
        "https://github.com/Owner/Repo", SHA.upper(), tmp_path / "checkout"
    )
    assert result.repository.repository_id == "github:owner/repo"
    assert result.repository.commit_sha == SHA
    assert ("fetch", "--quiet", "--depth=1", "origin", SHA) in calls
    assert ("checkout", "--quiet", "--detach", SHA) in calls


@pytest.mark.parametrize(
    ("url", "revision"),
    [
        ("https://github.com/owner/repo", "main"),
        ("https://github.com/owner/repo", "a" * 39),
        ("https://gitlab.com/owner/repo", SHA),
        ("git@github.com:owner/repo.git", SHA),
    ],
)
def test_github_resolver_rejects_moving_revisions_and_unsupported_urls(url, revision):
    with pytest.raises(ValueError):
        github.resolve_github(url, revision)


def test_github_resolver_rejects_sha_mismatch(tmp_path, monkeypatch):
    monkeypatch.setattr(github, "_git", lambda root, *args: "f" * 40)
    with pytest.raises(ValueError, match="expected"):
        github.resolve_github("https://github.com/owner/repo", SHA, tmp_path / "repo")


def test_github_resolver_reports_git_fetch_failure(tmp_path, monkeypatch):
    def fail(root, *args):
        raise ValueError("GitHub resolution failed during git fetch")

    monkeypatch.setattr(github, "_git", fail)
    with pytest.raises(ValueError, match="fetch"):
        github.resolve_github("https://github.com/owner/repo", SHA, tmp_path / "repo")
