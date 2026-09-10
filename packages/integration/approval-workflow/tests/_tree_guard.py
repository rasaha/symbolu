"""Resolving a base branch, and detecting a committed edit to a frozen tree.

Both integration suites assert that this branch changed none of the Decision Authority
kernel. Each did it inline, with the same two defects:

* the base was "the one other remote branch", so a third branch made the committed half
  ``pytest.skip`` — an immutability guard that stops guarding without saying so;
* the candidate filter kept the bare remote pointer (``origin``) that a single-branch
  clone leaves behind. In a shallow checkout that pointer *is* the only candidate and
  resolves to ``HEAD`` itself, so the guard asserted an empty diff against itself and
  passed vacuously. That is worse than skipping: a vacuous pass reads as a real one.

``base_ref`` drops alias arrows and any name without a ``/`` (what the bare pointer looks
like), then picks the candidate whose merge-base with ``HEAD`` is closest to ``HEAD`` —
the nearest fork point, deterministic for any number of branches, ties broken by name.

An unresolvable base **fails**; it does not skip. For a guard whose whole job is to notice
a change, silence and success are not the same thing. A distance of zero is fine and does
not fail: a base that already contains ``HEAD`` means this branch added nothing, and an
empty diff is then the correct answer rather than an unresolvable base.

This mirrors ``cloud-scaling-producer-attestation/tests/_tree_guard.py``. The duplication
is deliberate — the two packages may not import each other, and the repository's existing
pattern is a private ``_*.py`` helper per package.
"""

from __future__ import annotations

import pathlib
import subprocess

__all__ = ["BaseRefUnresolvable", "base_ref", "git", "tree_was_modified"]


class BaseRefUnresolvable(RuntimeError):
    """No remote branch can serve as a base for the committed-diff half."""


def git(repo: pathlib.Path, *args: str) -> str:
    return subprocess.run(
        ("git", "-C", str(repo)) + args, capture_output=True, text=True, check=True
    ).stdout.strip()


def _git_or_none(repo: pathlib.Path, *args: str) -> str | None:
    try:
        return git(repo, *args)
    except subprocess.CalledProcessError:
        return None


def base_ref(repo: pathlib.Path) -> str:
    here = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    candidates = [
        name
        for name in (raw.strip() for raw in git(
            repo, "branch", "-r", "--format=%(refname:short)").splitlines())
        if name and "->" not in name and "/" in name and not name.endswith(f"/{here}")
    ]

    scored: list[tuple[int, str]] = []
    for name in candidates:
        merge_base = _git_or_none(repo, "merge-base", "HEAD", name)
        if merge_base is None:
            continue
        distance = _git_or_none(repo, "rev-list", "--count", f"{merge_base}..HEAD")
        if distance is not None:
            scored.append((int(distance), name))

    if not scored:
        raise BaseRefUnresolvable(
            "no remote branch shares history with HEAD, so the committed half of this "
            "guard cannot run. In CI this means the checkout was shallow: the job needs "
            "actions/checkout with fetch-depth: 0. This is a failure rather than a skip "
            "because a guard that quietly stops guarding is indistinguishable from one "
            "that passed."
        )
    return min(scored)[1]


def tree_was_modified(repo: pathlib.Path, tree: str) -> str:
    """Any edit to ``tree``, pending or committed on this branch. ``""`` if none."""

    report = []
    pending = git(repo, "status", "--porcelain", "--", tree)
    if pending:
        report.append(f"uncommitted:\n{pending}")
    committed = git(repo, "diff", "--name-only", f"{base_ref(repo)}...HEAD", "--", tree)
    if committed:
        report.append(f"committed on this branch:\n{committed}")
    return "\n".join(report)
