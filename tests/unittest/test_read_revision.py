import subprocess

import pytest

from app import _git_head, read_revision

pytestmark = pytest.mark.unittest

COMMIT = "8f414ae86cb195c6de5d60f0494a5824a90cf5f5"
OTHER = "c5d9e91b806fbfc1672df2f3abf0f832ef45a914"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_reads_branch_ref(tmp_path):
    write(tmp_path / ".git" / "HEAD", "ref: refs/heads/staging\n")
    write(tmp_path / ".git" / "refs" / "heads" / "staging", COMMIT + "\n")

    assert _git_head(str(tmp_path)) == COMMIT


def test_reads_packed_ref(tmp_path):
    write(tmp_path / ".git" / "HEAD", "ref: refs/heads/staging\n")
    write(tmp_path / ".git" / "packed-refs",
          "# pack-refs with: peeled fully-peeled sorted\n"
          f"{OTHER} refs/heads/master\n{COMMIT} refs/heads/staging\n")

    assert _git_head(str(tmp_path)) == COMMIT


def test_reads_detached_head(tmp_path):
    write(tmp_path / ".git" / "HEAD", COMMIT + "\n")

    assert _git_head(str(tmp_path)) == COMMIT


def test_reads_worktree(tmp_path):
    common = tmp_path / "main" / ".git"
    worktree_git = common / "worktrees" / "deploy"
    write(worktree_git / "HEAD", "ref: refs/heads/staging\n")
    write(worktree_git / "commondir", "../..\n")
    write(common / "refs" / "heads" / "staging", COMMIT + "\n")
    checkout = tmp_path / "deploy"
    write(checkout / ".git", f"gitdir: {worktree_git}\n")

    assert _git_head(str(checkout)) == COMMIT


def test_no_checkout_gives_nothing(tmp_path):
    assert _git_head(str(tmp_path)) == ""


def test_works_without_git_on_path(monkeypatch):
    """The production service runs with only the virtualenv on PATH."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if not head:
        pytest.skip("not running inside a git checkout")
    monkeypatch.setenv("PATH", "/nonexistent")

    assert read_revision() == head
