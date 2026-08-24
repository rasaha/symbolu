"""The partition ratchet — "promoting a fact requires a profile bump", enforced from history.

Why a constant in this tree could never enforce it
---------------------------------------------------
``tests/test_frozen_digests.py`` pins the partition fingerprint and says that the pin ties a
membership change to a :data:`VERIFICATION_PROFILE_VERSION` bump. It does not, and the 5B-1
audit measured why: promoting ``candidate_digest_fact``, updating the two constants and
leaving the profile version at ``"v1"`` passes that file at 5 passed. Updating the pin is
exactly as cheap as the change the pin exists to gate, because both live in the same tree and
land in the same commit.

So the "before" cannot come from this tree. It comes from **repository history**: the
membership recorded at the merge base is compared against the membership in the working tree,
and a change that moved a fact between the two halves without moving the profile version is a
failure. A profile version that moved without a changelog entry naming it is a failure too —
a bumped version nobody documented tells a consumer that the profile changed and nothing about
how.

Reading the baseline without importing it
------------------------------------------
Two versions of one module cannot both be imported, so the baseline membership is **parsed**
out of the historical source with :mod:`ast` rather than executed. A parser that silently
returned nothing would make this whole gate vacuous, so
``test_partition_ratchet.py`` measures the parser against the imported truth for the working
tree before trusting it on history.

Everything below except :func:`sources_at_revision` is pure: it takes source text and returns
findings. That is what lets the negative controls drive the gate with synthetic sources and
observe it fail, without touching the repository.
"""

from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
from dataclasses import dataclass
from typing import Final, Optional

__all__ = [
    "PartitionSnapshot",
    "PACKAGE_FILES",
    "RatchetBaselineUnavailable",
    "baseline_revision",
    "ratchet_problems",
    "snapshot_from_sources",
    "sources_at_revision",
]

#: Repository-relative paths of the three files the ratchet reads. The membership lives in
#: ``verified.py``, the profile version and the two domain tags in ``identifiers.py``, and
#: the discipline the bump owes a reader in ``CHANGELOG.md``.
_PKG = "packages/integration/cloud-scaling-policy-authenticity"
PACKAGE_FILES: "dict[str, str]" = {
    "verified": f"{_PKG}/src/ugence_cloud_scaling_policy_authenticity/verified.py",
    "identifiers": f"{_PKG}/src/ugence_cloud_scaling_policy_authenticity/identifiers.py",
    "changelog": f"{_PKG}/CHANGELOG.md",
}


class RatchetBaselineUnavailable(RuntimeError):
    """No historical baseline could be resolved. A skip locally; a failure in CI.

    ``UGENCE_RATCHET_REQUIRED=1`` turns this into a failure, and the package's CI sets it:
    a gate that quietly skips where it is supposed to run is not a gate.
    """


@dataclass(frozen=True)
class PartitionSnapshot:
    """The partition as of one revision: both halves, their frames, and the profile version."""

    verified: "frozenset[str]"
    recorded: "frozenset[str]"
    verified_domain: str
    recorded_domain: str
    profile_version: str

    @property
    def membership(self) -> tuple:
        """Everything a promotion moves. Deliberately excludes the profile version."""

        return (
            tuple(sorted(self.verified)),
            tuple(sorted(self.recorded)),
            self.verified_domain,
            self.recorded_domain,
        )


def _assigned_value(source: str, name: str, filename: str):
    """The value assigned to a module-level ``name``, evaluated as a literal.

    Handles both ``NAME = ...`` and ``NAME: Final[str] = ...``, and unwraps the
    ``frozenset({...})`` call the membership sets are written as. Anything it cannot read is
    an error rather than a ``None``: a silent miss here would disarm the ratchet.
    """

    tree = ast.parse(source, filename=filename)
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign) and node.value is not None
            else []
        )
        for target in targets:
            if not (isinstance(target, ast.Name) and target.id == name):
                continue
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "frozenset"
                and len(value.args) == 1
            ):
                return frozenset(ast.literal_eval(value.args[0]))
            return ast.literal_eval(value)
    raise ValueError(
        f"{name!r} is not assigned at module level in {filename}; the partition ratchet "
        "cannot read a baseline it cannot find, and refuses rather than passing vacuously"
    )


def snapshot_from_sources(*, verified_py: str, identifiers_py: str) -> PartitionSnapshot:
    """Parse one revision's partition out of its source text. Never imports it."""

    return PartitionSnapshot(
        verified=_assigned_value(verified_py, "VERIFIED_FACT_NAMES", "verified.py"),
        recorded=_assigned_value(verified_py, "RECORDED_FACT_NAMES", "verified.py"),
        verified_domain=_assigned_value(
            identifiers_py, "POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN", "identifiers.py"
        ),
        recorded_domain=_assigned_value(
            identifiers_py, "POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN", "identifiers.py"
        ),
        profile_version=_assigned_value(
            identifiers_py, "VERIFICATION_PROFILE_VERSION", "identifiers.py"
        ),
    )


def ratchet_problems(
    *,
    baseline: PartitionSnapshot,
    current: PartitionSnapshot,
    changelog: str,
) -> "list[str]":
    """The findings. Empty means the change is disciplined; anything else fails the gate.

    Three rules, and they are the whole gate:

    #. membership moved ⇒ the profile version must move in the same change;
    #. the profile version moved ⇒ the changelog must name it, on one line, beside
       ``VERIFICATION_PROFILE_VERSION``;
    #. **every fact that changed halves must be disclosed on its own changelog line**, in the
       form ``promoted: <fact> — …`` or ``demoted: <fact> — …``. A bump earned by one
       promotion does not carry a second, undisclosed one along with it, and an incidental
       mention of a fact name elsewhere in the changelog is not a disclosure.

    A version bump with no membership change is allowed and unremarked: a gate can be added,
    removed or reordered without the partition moving, and that bump is just as required.
    """

    problems: "list[str]" = []
    membership_moved = baseline.membership != current.membership
    version_moved = baseline.profile_version != current.profile_version
    promoted = sorted(current.verified & baseline.recorded)
    demoted = sorted(current.recorded & baseline.verified)

    if membership_moved and not version_moved:
        problems.append(
            "the verified/recorded partition moved while VERIFICATION_PROFILE_VERSION "
            f"stayed at {current.profile_version!r} "
            f"(promoted: {promoted or 'none'}; demoted: {demoted or 'none'}; "
            f"baseline verified/recorded frames: "
            f"{baseline.verified_domain!r}/{baseline.recorded_domain!r}). A promotion "
            "changes what a determination establishes, so it changes the profile that "
            "produced it. Bump the profile version in the same commit."
        )
    if version_moved and not _changelog_names(changelog, current.profile_version):
        problems.append(
            f"VERIFICATION_PROFILE_VERSION moved from {baseline.profile_version!r} to "
            f"{current.profile_version!r} with no changelog line naming it. Add a line "
            "carrying both VERIFICATION_PROFILE_VERSION and the new value, saying which "
            "digest moved and why."
        )
    # A bump is not a blanket permit. Without this, the FIRST disclosed promotion pays for
    # every later one in the same change: `version_moved` is already True, so the rule above
    # stays silent, and the changelog line the first promotion added already satisfies the
    # rule beside it. An independent audit of 5B-1 found that hole, and measuring it showed
    # it was worse than a misleading signal — a second, undisclosed promotion took the whole
    # 282-property suite green, because every other guard that noticed was a pinned constant
    # or a hardcoded fact name, and updating those is exactly the cheap edit this gate exists
    # to render insufficient. So each fact that changed halves must be named in the changelog
    # on its own account.
    undisclosed = [
        f"{fact} ({direction})"
        for direction, facts in (("promoted", promoted), ("demoted", demoted))
        for fact in facts
        if not _changelog_discloses(changelog, direction, fact)
    ]
    if undisclosed:
        problems.append(
            f"the partition moved facts the changelog does not disclose: {undisclosed}. "
            f"(promoted: {promoted or 'none'}; demoted: {demoted or 'none'}.) A profile "
            "version bump is not a blanket permit for every fact that moves alongside the "
            "one it was raised for. Disclose each on its own line, in the form "
            "`promoted: <fact> — <what now establishes it>` or "
            "`demoted: <fact> — <what stopped establishing it>`."
        )
    return problems


#: An explicit disclosure line: the direction, a colon, and the fact name.
_DISCLOSURE_RE: Final = re.compile(
    r"^\s*[-*]?\s*(?P<direction>promoted|demoted)\s*:\s*(?P<rest>.*)$", re.IGNORECASE
)


def _changelog_discloses(changelog: str, direction: str, fact: str) -> bool:
    """True when a changelog line explicitly discloses this fact moving in this direction.

    A **structured** line, not a mention. The first form of this rule asked only whether the
    fact name appeared anywhere in the changelog, and testing it end to end showed that was
    vacuous: ``resolved_as_of_fact`` already appears in this package's changelog in a sentence
    saying it *stays* in the recorded half, which silently satisfied the check for a promotion
    of that very fact. An incidental mention is not a disclosure, and a gate that accepts one
    is the same kind of pin it was written to replace.
    """

    for line in changelog.splitlines():
        match = _DISCLOSURE_RE.match(line)
        if match is None or match.group("direction").lower() != direction:
            continue
        if re.search(rf"\b{re.escape(fact)}\b", match.group("rest")):
            return True
    return False


def _changelog_names(changelog: str, version: str) -> bool:
    """One line must carry both the constant's name and the new value.

    Both, on one line, because either alone is too easy to satisfy by accident — ``"v2"``
    occurs in domain tags and type names all over this repository.
    """

    return any(
        "VERIFICATION_PROFILE_VERSION" in line and version in line
        for line in changelog.splitlines()
    )


# --------------------------------------------------------------------------------------- #
# The only part that touches the repository
# --------------------------------------------------------------------------------------- #


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
    """The revision whose partition is the "before". Raises when there is no honest answer.

    ``UGENCE_RATCHET_BASE`` wins, so CI can name the pull request's actual base and the
    negative controls can pin a revision. Otherwise the merge base with the default branch,
    which is the change's own starting point. There is deliberately no fallback to ``HEAD``:
    comparing a branch against itself would report "no movement" for every promotion on it,
    which is worse than admitting there is no baseline.
    """

    injected = os.environ.get("UGENCE_RATCHET_BASE")
    if injected:
        resolved = _git(repo, "rev-parse", "--verify", f"{injected}^{{commit}}")
        if resolved is None:
            raise RatchetBaselineUnavailable(
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
    raise RatchetBaselineUnavailable(
        "no default-branch ref is available to take a merge base against; set "
        "UGENCE_RATCHET_BASE to the revision this change started from"
    )


def _require_baseline_precedes_head(repo: pathlib.Path, revision: str, *, source: str) -> str:
    """Refuse a baseline that already contains the change under test.

    The docstring above says there is no fallback to ``HEAD`` because comparing a branch
    against itself reports "no movement" for every promotion on it. That guard covered only
    the *resolution* path — it did not check the answer. Both paths could still return a
    revision that already contains ``HEAD``, and then every rule in
    :func:`ratchet_problems` is evaluated against the post-change partition on both sides:
    ``membership_moved`` is ``False``, ``promoted`` and ``demoted`` are empty, and the gate
    passes **vacuously**.

    That is not hypothetical. Measured on the 5B-3 pull request: the package's CI computes the
    baseline itself as ``git merge-base HEAD origin/<default>`` and it resolved to the pull
    request's own head commit, so the ratchet ran, reported nothing, and went green on a
    change that promoted ``policy_type``. The only reason it surfaced at all is that a
    separate property skipped, and the workflow treats a skip as a failure.

    A baseline that contains the change is therefore refused as *unavailable* rather than
    used: no baseline is a skip a reader can see, and a vacuous pass is not.
    """

    head = _git(repo, "rev-parse", "--verify", "HEAD^{commit}")
    if head is None:
        raise RatchetBaselineUnavailable("HEAD does not resolve to a commit")
    head = head.strip()
    if revision == head:
        raise RatchetBaselineUnavailable(
            f"the baseline ({source}) resolved to HEAD itself ({head[:12]}). Comparing the "
            "change against itself reports no movement for every promotion on it, so the "
            "gate would pass vacuously"
        )
    # ``--is-ancestor`` exits 0 when HEAD is an ancestor of ``revision``; ``_git`` maps a
    # non-zero exit to None, so a non-None result means the baseline already contains HEAD.
    if _git(repo, "merge-base", "--is-ancestor", head, revision) is not None:
        raise RatchetBaselineUnavailable(
            f"the baseline ({source}) resolved to {revision[:12]}, which already contains "
            f"HEAD ({head[:12]}). A baseline that includes the change under test carries the "
            "post-change partition on both sides, so the gate would pass vacuously"
        )
    return revision


def _candidate_base_refs(repo: pathlib.Path) -> "list[str]":
    """Refs that might name the default branch, most authoritative first.

    ``origin/HEAD`` is the only one that is actually *told* to us — this repository's default
    branch is not called ``main``, so a hardcoded list would silently resolve to nothing and
    the gate would skip on exactly the repository it guards. The named fallbacks stay for
    ordinary clones, and CI passes ``UGENCE_RATCHET_BASE`` outright rather than relying on any
    of this.
    """

    refs = ["refs/remotes/origin/ratchet-base"]
    symbolic = _git(repo, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if symbolic:
        refs.append(symbolic.strip())
    refs += ["origin/main", "origin/master", "main", "master"]
    return refs


def sources_at_revision(repo: pathlib.Path, revision: str) -> "dict[str, str]":
    """The three files as of ``revision``. Raises when any of them cannot be read."""

    sources = {}
    for key, path in PACKAGE_FILES.items():
        blob = _git(repo, "show", f"{revision}:{path}")
        if blob is None:
            raise RatchetBaselineUnavailable(
                f"{path} could not be read at {revision}; the baseline is incomplete, and a "
                "partial baseline would compare a partition against nothing"
            )
        sources[key] = blob
    return sources
