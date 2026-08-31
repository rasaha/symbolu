"""The surface ratchet — "the allowlist cannot grow silently", enforced from history.

What R-11 actually claims, and what it does not
------------------------------------------------
**Every public attribute declared on** :class:`CapacityAuthorizationCandidate` **or inherited
through its MRO is either a dataclass field covered by** ``digest_payload()`` **or an
explicitly named non-field surface member. The allowlist cannot grow without a disclosed,
reviewed change.**

That is deliberately narrower than "every attribute an instance could ever expose". The class
is a frozen dataclass without ``__slots__``, so ``object.__setattr__`` can still staple an
attribute onto one instance at runtime; no static check sees that, and this module does not
pretend to. What it covers is the *declared* surface, which is where a binding would actually
be added by someone writing code rather than attacking a live object.

Why the allowlist needs history and the previous check did not work
---------------------------------------------------------------------
The first attempt at R-11 tried to decide whether an exempt attribute was instance-derived by
reading its source for the name ``self``. That is source classification, and "does this derive
from instance state" is a semantic property: every syntactic approximation has a bypass class —
a renamed receiver, a helper delegate, ``getattr``, a custom descriptor. Broadening the scan
only moves the boundary.

So the classifier is gone. Enumeration is **total over names** instead: whatever the member is
implemented as, it must be named. That closes accidental drift completely, because a
contributor adding a convenience attribute touches nothing in the allowlist and the test fires.

It does not close a contributor who edits the class and the allowlist together — nothing in a
tree can, since the tests and the code share one trust domain. What history buys is the same
thing it bought the partition ratchet: the "before" cannot be edited in the commit that changes
the "after", so *widening* becomes a disclosed event rather than a silent one. It still cannot
make the disclosure true; that residual is recorded, not repaired.

Everything below except :func:`sources_at_revision` is pure, so the negative controls drive the
gate with synthetic sources and observe it fail without touching the repository.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
from typing import Final, Optional

__all__ = [
    "PACKAGE_FILES",
    "SurfaceRatchetBaselineUnavailable",
    "allowlist_from_source",
    "baseline_revision",
    "ratchet_problems",
    "sources_at_revision",
]

_PKG = "packages/integration/cloud-scaling-authorization-contracts"
#: The allowlist lives in the test module; the disclosure it owes a reader lives in the
#: changelog. Both are read at the baseline and in the working tree.
PACKAGE_FILES: "dict[str, str]" = {
    "completeness": f"{_PKG}/tests/test_digest_completeness.py",
    "changelog": f"{_PKG}/CHANGELOG.md",
}

#: The assignment the ratchet reads out of the completeness module.
_ALLOWLIST_NAME: Final = "FROZEN_NON_FIELD_SURFACE"

_DISCLOSURE_RE: Final = re.compile(
    r"^\s*[-*]?\s*surface:\s*(?P<rest>.*)$", re.IGNORECASE
)


class SurfaceRatchetBaselineUnavailable(RuntimeError):
    """No honest "before" exists. Skipping is correct; inventing a baseline is not."""


def allowlist_from_source(source: str, *, absent_is_empty: bool = False) -> "frozenset[str]":
    """The allowlist as of one revision, parsed rather than imported.

    Two versions of one module cannot both be imported, so the baseline is read with
    :mod:`ast`. ``test_surface_ratchet.py`` measures this parser against the imported truth for
    the working tree before trusting it on history — a parser that silently returned the empty
    set would make the whole gate vacuous while leaving it green.
    """

    tree = ast.parse(source)
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        if _ALLOWLIST_NAME not in targets or node.value is None:
            continue
        return frozenset(_string_elements(node.value))
    if absent_is_empty:
        # At a revision predating the allowlist nothing was exempt, so the truthful "before"
        # is the empty set — which makes introducing the allowlist disclose its whole membership
        # rather than arriving unannounced. Only ever granted to the *baseline*: absent in the
        # working tree means the guard was deleted, and that must raise.
        return frozenset()
    raise SurfaceRatchetBaselineUnavailable(
        f"{_ALLOWLIST_NAME} was not found; the allowlist cannot be compared against nothing"
    )


def _string_elements(node: ast.AST) -> "list[str]":
    """Every string constant inside a ``frozenset({...})``-shaped expression."""

    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _discloses(changelog: str, name: str) -> bool:
    """Whether the changelog names this member on a structured ``surface:`` line.

    Structured for the reason D-5B1-3's third rule is structured: a mention-anywhere check is
    satisfied by prose that says the opposite, and this repository has already measured that
    failure once.
    """

    for line in changelog.splitlines():
        match = _DISCLOSURE_RE.match(line)
        if match and re.search(rf"\b{re.escape(name)}\b", match.group("rest")):
            return True
    return False


def ratchet_problems(*, baseline: "dict[str, str]", current: "dict[str, str]") -> "list[str]":
    """Every reason this change widened the surface allowlist without disclosing it.

    Only growth is gated. Removing a member narrows the exempt surface, which needs no
    ceremony — the completeness test itself refuses a name that no longer exists.
    """

    before = allowlist_from_source(baseline["completeness"], absent_is_empty=True)
    after = allowlist_from_source(current["completeness"])
    added = sorted(after - before)
    if not added:
        return []
    changelog = current["changelog"]
    return [
        f"{name} was added to {_ALLOWLIST_NAME} and no changelog line discloses it; a public "
        f"member exempt from the candidate digest must be announced as "
        f"'surface: {name} — <why it carries no per-candidate meaning>'"
        for name in added
        if not _discloses(changelog, name)
    ]


def _git(repo: pathlib.Path, *args: str) -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=60
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def baseline_revision(repo: pathlib.Path) -> str:
    """The revision whose allowlist is the "before". Raises when there is no honest answer.

    Mirrors the partition ratchet deliberately, including the refusal to fall back to ``HEAD``:
    comparing a branch against itself reports "no growth" for every widening on it.
    """

    injected = os.environ.get("UGENCE_RATCHET_BASE")
    if injected:
        resolved = _git(repo, "rev-parse", "--verify", f"{injected}^{{commit}}")
        if resolved is None:
            raise SurfaceRatchetBaselineUnavailable(
                f"UGENCE_RATCHET_BASE={injected!r} does not resolve to a commit"
            )
        return _require_baseline_precedes_head(repo, resolved.strip(), source=repr(injected))
    for ref in _candidate_base_refs(repo):
        if _git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}") is None:
            continue
        merge_base = _git(repo, "merge-base", "HEAD", ref)
        if merge_base:
            return _require_baseline_precedes_head(
                repo, merge_base.strip(), source=f"merge base with {ref}"
            )
    raise SurfaceRatchetBaselineUnavailable(
        "no default-branch ref is available to take a merge base against; set "
        "UGENCE_RATCHET_BASE to the revision this change started from"
    )


def _require_baseline_precedes_head(repo: pathlib.Path, revision: str, *, source: str) -> str:
    """Refuse a baseline that already contains the change under test.

    The docstring above claimed this module mirrors the partition ratchet "including the
    refusal to fall back to HEAD" — but that guard covered only the *resolution* path, not
    the answer. Both paths could still return a revision containing ``HEAD``, and then
    :func:`ratchet_problems` reads the post-change allowlist on both sides: nothing added,
    gate green, for every widening.

    Not hypothetical, and worse than the partition ratchet's version of the same hole
    because this one failed *open*: on every default-branch push the workflow computed
    ``git merge-base HEAD <default>`` — HEAD itself — injected it as
    ``UGENCE_RATCHET_BASE``, and the gate passed. Measured on run 33317988694 (the push of
    merge commit ``a24d9c6b``): the job's environment shows the baseline equal to the head
    SHA, and the job is green. A baseline that contains the change is therefore refused as
    *unavailable* rather than used: no baseline is a visible skip (or a failure under
    ``UGENCE_RATCHET_REQUIRED``), and a vacuous pass is neither.
    """

    head = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if head is None:
        raise SurfaceRatchetBaselineUnavailable("HEAD does not resolve to a commit")
    head = head.strip()
    if revision == head:
        raise SurfaceRatchetBaselineUnavailable(
            f"the baseline ({source}) resolved to HEAD itself ({head[:12]}). Comparing the "
            "change against itself reports no growth for every widening on it, so the gate "
            "would pass vacuously"
        )
    # ``--is-ancestor`` exits 0 when HEAD is an ancestor of ``revision``; ``_git`` maps a
    # non-zero exit to None, so a non-None result means the baseline already contains HEAD.
    if _git(repo, "merge-base", "--is-ancestor", head, revision) is not None:
        raise SurfaceRatchetBaselineUnavailable(
            f"the baseline ({source}) resolved to {revision[:12]}, which already contains "
            f"HEAD ({head[:12]}). A baseline that includes the change under test carries the "
            "post-change allowlist on both sides, so the gate would pass vacuously"
        )
    return revision


def _candidate_base_refs(repo: pathlib.Path) -> "list[str]":
    refs = ["refs/remotes/origin/ratchet-base"]
    symbolic = _git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if symbolic:
        refs.append(symbolic.strip())
    refs += ["origin/main", "origin/master", "main", "master"]
    return refs


def sources_at_revision(repo: pathlib.Path, revision: str) -> "dict[str, str]":
    """Both files as of ``revision``. Raises when either cannot be read."""

    sources = {}
    for key, path in PACKAGE_FILES.items():
        blob = _git(repo, "show", f"{revision}:{path}")
        if blob is None:
            raise SurfaceRatchetBaselineUnavailable(
                f"{path} could not be read at {revision}; a partial baseline would compare "
                "the allowlist against nothing"
            )
        sources[key] = blob
    return sources
