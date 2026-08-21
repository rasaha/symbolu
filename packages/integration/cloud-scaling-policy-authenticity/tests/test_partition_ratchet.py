"""The partition ratchet, and the proof that it fires.

``tests/test_frozen_digests.py`` pins the partition fingerprint. A pin is not a ratchet: the
5B-1 audit measured that promoting a fact, updating both pinned constants and leaving
``VERIFICATION_PROFILE_VERSION`` at ``"v1"`` passes that file at 5 passed. This module closes
that, by taking the "before" from repository history rather than from a constant sitting in
the same commit as the change it is supposed to gate.

Three kinds of property here, and all three are needed:

* **the gate** — the working tree's partition against the merge base's, through git;
* **the parser** — the historical membership is *parsed*, never imported, so the parser is
  measured against the imported truth before it is trusted on history. A parser that silently
  read nothing would make the gate vacuous while it still reported green;
* **the negative controls** — a promotion without a bump, and a bump with a silent changelog,
  each driven through the gate and observed to fail. A guard nobody has watched fail is a
  guard nobody has tested.

The controls are what make this file meaningful before the first real promotion: 5B-1 promotes
``candidate_digest_fact`` in a later step of the same change, and a guard built after that
promotion would have missed the one event it exists to catch.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

from _partition_ratchet import (
    PACKAGE_FILES,
    PartitionSnapshot,
    RatchetBaselineUnavailable,
    baseline_revision,
    ratchet_problems,
    snapshot_from_sources,
    sources_at_revision,
)
from _policy_fixtures import _find_repo_root
from ugence_cloud_scaling_policy_authenticity import (
    POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
    POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
    VERIFICATION_PROFILE_VERSION,
)
from ugence_cloud_scaling_policy_authenticity.verified import (
    RECORDED_FACT_NAMES,
    VERIFIED_FACT_NAMES,
)

REPO = _find_repo_root()

pytestmark = pytest.mark.skipif(
    REPO is None, reason="no source checkout; the ratchet reads the repository's history"
)


def _read(key: str) -> str:
    return (REPO / PACKAGE_FILES[key]).read_text(encoding="utf-8")


def _working_tree_snapshot() -> PartitionSnapshot:
    return snapshot_from_sources(
        verified_py=_read("verified"), identifiers_py=_read("identifiers")
    )


def _imported_snapshot() -> PartitionSnapshot:
    return PartitionSnapshot(
        verified=VERIFIED_FACT_NAMES,
        recorded=RECORDED_FACT_NAMES,
        verified_domain=POLICY_AUTHENTICITY_VERIFIED_FACTS_DOMAIN,
        recorded_domain=POLICY_AUTHENTICITY_RECORDED_FACTS_DOMAIN,
        profile_version=VERIFICATION_PROFILE_VERSION,
    )


def _rewritten(source: str, name: str, names: "frozenset[str]") -> str:
    """Rewrite one module-level ``frozenset({...})`` assignment, keeping the file parseable.

    Used only by the negative controls, and deliberately operating on the **real** source
    text: a control built from a hand-written toy module would exercise the parser on a shape
    this package does not actually use.
    """

    tree = ast.parse(source, filename=name)
    for node in tree.body:
        targets = (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign) and node.value is not None
            else []
        )
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        lines = source.splitlines(keepends=True)
        body = ", ".join(repr(value) for value in sorted(names))
        head = lines[node.lineno - 1].split("=")[0].rstrip()
        replacement = f"{head} = frozenset({{{body}}})\n"
        return "".join(
            lines[: node.lineno - 1] + [replacement] + lines[node.value.end_lineno :]
        )
    raise AssertionError(f"{name} was not found in the source to rewrite")


# --------------------------------------------------------------------------------------- #
# The parser, measured against the imported truth
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_parser_reads_the_working_tree_exactly_as_the_import_does():
    """If this fails, every historical reading below is untrustworthy."""

    assert _working_tree_snapshot() == _imported_snapshot()


@pytest.mark.adversarial
def test_the_parser_refuses_a_source_that_does_not_declare_the_partition():
    """A silent miss would disarm the gate, so a missing name raises rather than returning."""

    with pytest.raises(ValueError):
        snapshot_from_sources(verified_py="X = 1\n", identifiers_py=_read("identifiers"))


# --------------------------------------------------------------------------------------- #
# The gate itself
# --------------------------------------------------------------------------------------- #


@pytest.mark.invariant
def test_the_partition_moved_only_with_a_profile_bump_and_a_changelog_line():
    """The ratchet, against this change's own starting point.

    Skips only where no baseline can be resolved — a shallow clone, or a checkout with no
    default-branch ref. ``UGENCE_RATCHET_REQUIRED=1``, which this package's CI sets, turns
    that skip into a failure.
    """

    import os

    try:
        revision = baseline_revision(REPO)
        baseline_sources = sources_at_revision(REPO, revision)
    except RatchetBaselineUnavailable as exc:
        if os.environ.get("UGENCE_RATCHET_REQUIRED") == "1":
            pytest.fail(f"the partition ratchet could not run: {exc}")
        pytest.skip(f"no ratchet baseline available: {exc}")

    baseline = snapshot_from_sources(
        verified_py=baseline_sources["verified"],
        identifiers_py=baseline_sources["identifiers"],
    )
    problems = ratchet_problems(
        baseline=baseline, current=_imported_snapshot(), changelog=_read("changelog")
    )
    assert problems == [], "\n".join(problems)


# --------------------------------------------------------------------------------------- #
# The negative controls — the gate, observed failing
# --------------------------------------------------------------------------------------- #


def _promote_one(source: str, snapshot: PartitionSnapshot) -> "tuple[str, str]":
    """Move one fact from the recorded half to the verified half, in the real source text."""

    fact = sorted(snapshot.recorded)[0]
    promoted = _rewritten(source, "VERIFIED_FACT_NAMES", snapshot.verified | {fact})
    promoted = _rewritten(promoted, "RECORDED_FACT_NAMES", snapshot.recorded - {fact})
    return promoted, fact


@pytest.mark.adversarial
def test_a_promotion_without_a_profile_bump_fails_the_gate():
    """The exact change the audit measured passing at 5 passed, now refused."""

    current = _working_tree_snapshot()
    promoted_source, fact = _promote_one(_read("verified"), current)
    promoted = snapshot_from_sources(
        verified_py=promoted_source, identifiers_py=_read("identifiers")
    )
    # The transform really is a promotion, and the profile version really did not move.
    assert fact in promoted.verified and fact not in promoted.recorded
    assert promoted.profile_version == current.profile_version

    problems = ratchet_problems(
        baseline=current, current=promoted, changelog=_read("changelog")
    )
    assert len(problems) == 1
    assert "VERIFICATION_PROFILE_VERSION" in problems[0] and fact in problems[0]


@pytest.mark.adversarial
def test_a_profile_bump_with_a_silent_changelog_fails_the_gate():
    current = _working_tree_snapshot()
    bumped = PartitionSnapshot(
        verified=current.verified,
        recorded=current.recorded,
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    problems = ratchet_problems(
        baseline=current, current=bumped, changelog="# Changelog\n\nNothing to see.\n"
    )
    assert len(problems) == 1 and "no changelog line naming it" in problems[0]


@pytest.mark.adversarial
def test_a_changelog_that_names_only_the_value_is_not_enough():
    """``v2`` alone occurs in domain tags and type names; the constant must be named too."""

    current = _working_tree_snapshot()
    bumped = PartitionSnapshot(
        verified=current.verified,
        recorded=current.recorded,
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    problems = ratchet_problems(
        baseline=current,
        current=bumped,
        changelog="- ProducerAttestationV2 now reports v99 in its tag\n",
    )
    assert len(problems) == 1


@pytest.mark.adversarial
def test_renaming_a_half_s_domain_tag_is_a_membership_change_too():
    """The frame a fact sits in is part of what the artifact digest commits to."""

    current = _working_tree_snapshot()
    reframed = PartitionSnapshot(
        verified=current.verified,
        recorded=current.recorded,
        verified_domain=current.verified_domain + "/renamed",
        recorded_domain=current.recorded_domain,
        profile_version=current.profile_version,
    )
    problems = ratchet_problems(
        baseline=current, current=reframed, changelog=_read("changelog")
    )
    assert len(problems) == 1 and "partition moved" in problems[0]


@pytest.mark.happy
def test_a_promotion_with_a_bump_and_a_changelog_line_passes():
    """The disciplined change, which is the one the gate must not obstruct."""

    current = _working_tree_snapshot()
    promoted_source, fact = _promote_one(_read("verified"), current)
    promoted = snapshot_from_sources(
        verified_py=promoted_source, identifiers_py=_read("identifiers")
    )
    disciplined = PartitionSnapshot(
        verified=promoted.verified,
        recorded=promoted.recorded,
        verified_domain=promoted.verified_domain,
        recorded_domain=promoted.recorded_domain,
        profile_version="v99",
    )
    changelog = (
        f"- VERIFICATION_PROFILE_VERSION moves to v99: {fact} was promoted to the verified "
        "half, and the artifact digest moved with it.\n"
    )
    assert ratchet_problems(
        baseline=current, current=disciplined, changelog=changelog
    ) == []


@pytest.mark.happy
def test_a_change_that_moves_nothing_reports_nothing():
    current = _working_tree_snapshot()
    assert ratchet_problems(
        baseline=current, current=current, changelog=_read("changelog")
    ) == []


@pytest.mark.adversarial
def test_the_ratchet_refuses_to_invent_a_baseline_when_history_is_unavailable():
    """No fallback to HEAD: a branch compared against itself reports every promotion clean."""

    with pytest.raises(RatchetBaselineUnavailable):
        sources_at_revision(pathlib.Path(REPO), "0" * 40)
