"""Detecting an edit to a tree this package must not touch — committed or not.

Two guards in ``test_phase5a_invariants.py`` assert that this package leaves the Phase 5A
tree and the Cloud Scaling Controller alone. Both used to ask only
``git status --porcelain``, which observes the *workspace*: it catches an edit while it is
pending and goes green the moment the same edit is committed. The property they state —
"this package's tree adds files; it edits none of theirs" — is a property of a **change**,
and a working-tree check cannot express it. The T-2 re-freeze at ``d46cf6cb`` demonstrated
the gap: the guard caught that edit before commit and could not see it afterwards.

So both halves are asked here. The working-tree half needs only a repository. The
committed half needs a base to diff against, and resolving one is where the sibling
implementation in ``approval-workflow`` is fragile in a way worth not copying:

* it treats "the one other remote branch" as the base, so a third branch makes it skip;
* its filter keeps the bare remote pointer (``origin``) that a single-branch clone
  creates. In a shallow checkout that pointer *is* the only candidate and resolves to
  ``HEAD`` itself, so the guard asserts an empty diff against itself and passes
  vacuously — worse than skipping, because a vacuous pass is indistinguishable from a
  real one.

``base_ref`` therefore drops alias arrows and any name without a ``/`` (which is what the
bare pointer looks like), and among the remaining candidates picks the one whose
merge-base with ``HEAD`` is *closest* to ``HEAD`` — the nearest fork point. That is
deterministic for any number of branches, and unlike the sibling it does not degrade into
a skip when a third branch appears.

**An unresolvable base fails; it does not skip.** For an immutability guard, silence and
success are not the same thing, and a guard that quietly stops guarding is the failure
mode this module exists to remove. The one legitimate "no checkout" case — an extracted
sdist — is handled earlier and separately by ``repo_root()``, and these guards are in
``DELIBERATELY_NOT_SHIPPED`` besides, so they never run there. The CI job that does run
them (``producer-attestation-suite``) checks out with ``fetch-depth: 0``, so a base is
available; a failure here means the base genuinely could not be resolved, and the message
says how to fix it.
"""

from __future__ import annotations

import pathlib
import subprocess

__all__ = ["BaseRefUnresolvable", "base_ref", "git", "tree_was_modified"]


class BaseRefUnresolvable(RuntimeError):
    """No remote branch can serve as a base for the committed-diff half."""


def git(repo: pathlib.Path, *args: str) -> str:
    """Run ``git`` in ``repo`` and return stripped stdout. Raises on a non-zero exit."""

    return subprocess.run(
        ("git", "-C", str(repo)) + args,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _git_or_none(repo: pathlib.Path, *args: str) -> str | None:
    try:
        return git(repo, *args)
    except subprocess.CalledProcessError:
        return None


def _candidates(repo: pathlib.Path) -> list[str]:
    """Remote branches that could serve as a base, current branch excluded.

    Excludes alias arrows (``origin/HEAD -> origin/main``) and any name without a ``/``.
    The latter is the bare remote pointer a single-branch clone leaves behind; it is not a
    branch, and admitting it is what makes the sibling guard pass vacuously.
    """

    here = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    listed = git(repo, "branch", "-r", "--format=%(refname:short)").splitlines()
    return [
        name
        for name in (raw.strip() for raw in listed)
        if name and "->" not in name and "/" in name and not name.endswith(f"/{here}")
    ]


def base_ref(repo: pathlib.Path) -> str:
    """The remote branch this one most plausibly forked from.

    Deterministic for any branch count: among candidates whose merge-base with ``HEAD`` is
    not ``HEAD`` itself, the winner is the one needing the fewest commits to reach ``HEAD``
    — i.e. the nearest fork point. Ties break on the name, so the answer never depends on
    the order git happens to list refs in.
    """

    scored: list[tuple[int, str]] = []
    for name in _candidates(repo):
        merge_base = _git_or_none(repo, "merge-base", "HEAD", name)
        if merge_base is None:
            # No shared history at all — an unrelated branch cannot serve as a base.
            continue
        # Distance zero is kept deliberately: a branch that already contains HEAD means
        # this branch has added nothing, and an empty diff is then the correct answer
        # rather than an unresolvable base. The vacuous-pass failure mode this module
        # exists to prevent comes from the bare remote pointer, which ``_candidates``
        # already drops, not from an honestly empty diff.
        distance = _git_or_none(repo, "rev-list", "--count", f"{merge_base}..HEAD")
        if distance is not None:
            scored.append((int(distance), name))

    if not scored:
        raise BaseRefUnresolvable(
            "no remote branch shares history with HEAD without containing it, so the "
            "committed half of this guard cannot run. In CI this means the checkout was "
            "shallow: the job needs actions/checkout with fetch-depth: 0. Locally, fetch "
            "the branch this one forked from. This is a failure rather than a skip "
            "because a guard that quietly stops guarding is indistinguishable from one "
            "that passed."
        )
    return min(scored)[1]


def tree_was_modified(
    repo: pathlib.Path,
    tree: pathlib.Path,
    *,
    ratified: "dict[str, str] | None" = None,
) -> str:
    """Report any *unratified* edit to ``tree``, pending or committed. ``""`` if none.

    Both halves are reported together so a caller sees every offending path at once
    instead of fixing them one failure at a time.

    ``ratified`` maps a repo-relative path to the one commit authorized to have changed
    it. Promoting this guard to see committed edits made an allow-list unavoidable: the
    guard reports *that* an edit exists and cannot know whether it was allowed, so a
    ratified change would otherwise fail the suite forever on the branch that made it.

    The allow-list is deliberately narrow, and it is not a mute button:

    * it is keyed by **path and commit**, so a *different* commit touching an
      already-ratified path is still a violation — the entry authorizes one change, not
      the file;
    * a pending (uncommitted) edit is never covered, whatever the path;
    * an entry naming a commit that does not exist, or that never touched its path, is
      itself a failure rather than being ignored, so a stale or invented entry cannot sit
      there quietly widening the guard.
    """

    ratified = ratified or {}
    report = []

    pending = git(repo, "status", "--porcelain", "--", str(tree))
    if pending:
        report.append(f"uncommitted:\n{pending}")

    base = base_ref(repo)
    committed = [
        line
        for line in git(
            repo, "diff", "--name-only", f"{base}...HEAD", "--", str(tree)
        ).splitlines()
        if line.strip()
    ]

    unratified = []
    for path in committed:
        authorized = ratified.get(path)
        touching = set(
            git(repo, "log", "--format=%h", f"{base}..HEAD", "--", path).split()
        )
        if authorized is None:
            unratified.append(f"  {path} (touched by {sorted(touching)})")
            continue
        rogue = {c for c in touching if not authorized.startswith(c) and not c.startswith(authorized)}
        if rogue:
            unratified.append(
                f"  {path} is ratified for {authorized} only, but also changed by "
                f"{sorted(rogue)}"
            )
    if unratified:
        report.append("committed on this branch, unratified:\n" + "\n".join(unratified))

    # A ratification entry that no longer describes reality is a defect in the allow-list
    # itself. Checked here so the list cannot rot into a permanent exemption.
    for path, commit in ratified.items():
        # ``cat-file -e`` prints nothing and signals through its exit status, so the test
        # is ``is None`` (the call failed), never falsiness (success prints "" too).
        if _git_or_none(repo, "cat-file", "-e", f"{commit}^{{commit}}") is None:
            report.append(f"ratified entry names a commit that does not exist: {commit}")
        elif path not in committed and not _git_or_none(
            # ``diff-tree`` asks whether THIS commit touched the path. ``git log``
            # would answer whether any ancestor did, which the base commit that created
            # the file satisfies — so a stale entry would never be reported.
            repo, "diff-tree", "--no-commit-id", "--name-only", "-r", commit, "--", path
        ):
            report.append(
                f"ratified entry is stale: {commit} never touched {path}"
            )

    return "\n".join(report)
