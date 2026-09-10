"""The tree guards measured, not assumed.

P-11 and P-12 assert that a tree stays untouched. A guard like that is only worth its
green: if it cannot fail, it is decoration. Until ``d46cf6cb`` it could not see a
committed edit at all, and in a single-branch clone its sibling implementation asserted an
empty diff against ``HEAD`` itself and passed vacuously.

Every property below runs against a synthetic repository built in ``tmp_path``, so the
detection path is exercised for real without touching this checkout: a base branch, a
feature branch, and commits that a correct guard must catch.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from _tree_guard import BaseRefUnresolvable, base_ref, git, tree_was_modified

GUARDED = "packages/guarded"


def _run(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(
        ("git", "-C", str(repo)) + args,
        check=True,
        capture_output=True,
        text=True,
    )


def _write(repo: pathlib.Path, rel: str, text: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _commit(repo: pathlib.Path, message: str) -> str:
    _run(repo, "add", "-A")
    _run(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "--short", "HEAD")


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    """A repo with a remote-tracking base branch and a feature branch checked out.

    The base is a *remote* branch because that is what ``base_ref`` resolves against, and
    a fixture that used a local branch would prove nothing about the real path.
    """

    origin = tmp_path / "origin"
    origin.mkdir()
    _run(origin, "init", "-q", "-b", "main")
    _write(origin, f"{GUARDED}/frozen.py", "VALUE = 1\n")
    _write(origin, "packages/other/mine.py", "OK = True\n")
    _commit(origin, "base")

    work = tmp_path / "work"
    _run(tmp_path, "clone", "-q", str(origin), str(work))
    _run(work, "checkout", "-q", "-b", "feature")
    return work


def test_an_untouched_tree_reports_nothing(repo):
    """The positive control: without it, a guard that always fails would also pass."""

    _write(repo, "packages/other/mine.py", "OK = True  # my own package\n")
    _commit(repo, "change only my own tree")

    assert tree_was_modified(repo, repo / GUARDED) == ""


def test_a_committed_edit_is_caught(repo):
    """The property tier 1 could not deliver, and the reason for this whole module."""

    _write(repo, f"{GUARDED}/frozen.py", "VALUE = 2\n")
    _commit(repo, "tamper with the guarded tree")

    report = tree_was_modified(repo, repo / GUARDED)

    assert "committed on this branch" in report
    assert "frozen.py" in report


def test_a_pending_edit_is_caught(repo):
    """Tier 1's property is kept, not traded away for the new one."""

    _write(repo, f"{GUARDED}/frozen.py", "VALUE = 3\n")

    report = tree_was_modified(repo, repo / GUARDED)

    assert "uncommitted" in report and "frozen.py" in report











# ------------------------------------------------------------------ base resolution
def test_the_bare_remote_pointer_is_never_used_as_a_base(repo):
    """The defect that made the sibling guard pass vacuously in a shallow checkout.

    A single-branch clone leaves a bare ``origin`` pointer that resolves to ``HEAD``. A
    filter that keeps it finds exactly one "candidate", asserts an empty diff against
    itself, and reports success. Excluding names without a ``/`` is what prevents that,
    and this asserts the resolved base is a real branch rather than the pointer.
    """

    _write(repo, "packages/other/mine.py", "OK = 'moved on'\n")
    _commit(repo, "so the base and HEAD genuinely differ, as on a real branch")

    resolved = base_ref(repo)

    assert "/" in resolved and not resolved.endswith("/feature"), resolved
    assert git(repo, "rev-parse", resolved) != git(repo, "rev-parse", "HEAD"), (
        "the resolved base must be a real branch behind HEAD, not a pointer at it")


def test_more_than_one_candidate_still_resolves(repo):
    """Three branches must not degrade the guard into a skip, as the sibling does."""

    _run(repo, "update-ref", "refs/remotes/origin/unrelated", git(repo, "rev-parse", "HEAD"))
    _write(repo, f"{GUARDED}/frozen.py", "VALUE = 9\n")
    _commit(repo, "tamper after a third branch exists")

    report = tree_was_modified(repo, repo / GUARDED)

    assert "frozen.py" in report, (
        "a third remote branch must not stop the guard from resolving a base")


def test_an_unresolvable_base_fails_rather_than_passing_quietly(tmp_path):
    """Silence and success are not the same thing for an immutability guard."""

    lone = tmp_path / "lone"
    lone.mkdir()
    _run(lone, "init", "-q", "-b", "main")
    _write(lone, f"{GUARDED}/frozen.py", "VALUE = 1\n")
    _commit(lone, "only commit, no remotes at all")

    with pytest.raises(BaseRefUnresolvable, match="fetch-depth: 0"):
        tree_was_modified(lone, lone / GUARDED)
