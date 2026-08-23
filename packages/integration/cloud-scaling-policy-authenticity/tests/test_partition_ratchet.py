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

The same argument is why rule 4's controls (below, under their own banner) land before any
fact is added to the verified half: a name entering that half from *neither* baseline half is
not a promotion, so nothing above it is fact-specific about the arrival, and a guard built
after the first such fact would again have missed the one event it exists to catch.
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
    # Two findings, because an undisclosed promotion without a bump breaks both rules: the
    # version did not move, and no `promoted:` line discloses the fact.
    assert len(problems) == 2, problems
    assert "VERIFICATION_PROFILE_VERSION" in problems[0] and fact in problems[0]
    assert "does not disclose" in problems[1] and fact in problems[1]


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
        f"- VERIFICATION_PROFILE_VERSION moves to v99.\n- promoted: {fact} — the artifact "
        "digest moved with it.\n"
    )
    assert ratchet_problems(
        baseline=current, current=disciplined, changelog=changelog
    ) == []


@pytest.mark.adversarial
def test_a_bump_earned_by_one_promotion_does_not_carry_a_second_one():
    """The free ride, refused. This is the hole an independent audit of 5B-1 found.

    Rule 1 asks whether the version moved, not whether the disclosure accounts for what moved.
    So once one legitimate promotion has bumped the version and added its changelog line, a
    second promotion in the same change was invisible: the version had already moved, and the
    line the first promotion added already satisfied the rule beside it.

    Measuring it showed the consequence was not merely a misleading signal. With a second,
    undisclosed promotion applied to the real tree and every pinned constant and hardcoded
    fact name updated alongside it, the entire suite went green and this file passed 10/10 —
    because every other guard that noticed was itself a pin, and updating a pin is the cheap
    edit this gate exists to render insufficient.
    """

    current = _working_tree_snapshot()
    disclosed, undisclosed = sorted(current.recorded)[:2]
    both_promoted = PartitionSnapshot(
        verified=current.verified | {disclosed, undisclosed},
        recorded=current.recorded - {disclosed, undisclosed},
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    changelog = (
        f"- VERIFICATION_PROFILE_VERSION moves to v99.\n- promoted: {disclosed} — now "
        "checked by its own gate.\n"
    )
    problems = ratchet_problems(
        baseline=current, current=both_promoted, changelog=changelog
    )
    assert len(problems) == 1, problems
    reported = problems[0].split("disclose: ")[1].split("]")[0]
    assert undisclosed in reported and disclosed not in reported


@pytest.mark.adversarial
def test_a_demotion_riding_alongside_a_disclosed_promotion_is_refused():
    """The direction that matters more: a checked fact quietly reclassified as unchecked."""

    current = _working_tree_snapshot()
    promoted = sorted(current.recorded)[0]
    demoted = "policy_body_digest"
    assert demoted in current.verified
    mixed = PartitionSnapshot(
        verified=(current.verified | {promoted}) - {demoted},
        recorded=(current.recorded - {promoted}) | {demoted},
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    changelog = (
        f"- VERIFICATION_PROFILE_VERSION moves to v99.\n- promoted: {promoted} — now "
        "checked by its own gate.\n"
    )
    problems = ratchet_problems(baseline=current, current=mixed, changelog=changelog)
    assert len(problems) == 1 and demoted in problems[0]


@pytest.mark.happy
def test_naming_every_moved_fact_passes():
    """The disciplined multi-fact change, which the gate must not obstruct."""

    current = _working_tree_snapshot()
    first, second = sorted(current.recorded)[:2]
    both = PartitionSnapshot(
        verified=current.verified | {first, second},
        recorded=current.recorded - {first, second},
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    changelog = (
        "- VERIFICATION_PROFILE_VERSION moves to v99.\n"
        f"- promoted: {first} — now checked by its own gate.\n"
        f"- promoted: {second} — likewise.\n"
    )
    assert ratchet_problems(baseline=current, current=both, changelog=changelog) == []


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


# --------------------------------------------------------------------------------------- #
# Rule 4 — a fact entering the verified half from neither baseline half
# --------------------------------------------------------------------------------------- #
#
# Rules 1-3 are keyed on movement between the halves. A brand-new verified fact does not move
# through anything: it is in neither half at the baseline and in the verified half after, so
# `promoted` is empty and nothing in rules 1-3 is fact-specific about it. The gap is generic —
# it applies to whatever the next verified fact turns out to be, whatever establishes it — and
# these controls drive it with a synthetic name for exactly that reason.

#: A name no partition has ever carried, so the controls below cannot accidentally exercise a
#: promotion of a real fact.
_NEW_FACT = "synthetic_new_verified_fact"

#: The changelog a disciplined bump carries, without any per-fact line.
_BUMPED = "- VERIFICATION_PROFILE_VERSION moves to v99.\n"


def _with_new_verified_fact(
    current: PartitionSnapshot, fact: str = _NEW_FACT
) -> PartitionSnapshot:
    """``current`` plus one verified fact that was in neither half, under a profile bump."""

    assert fact not in current.verified and fact not in current.recorded
    return PartitionSnapshot(
        verified=current.verified | {fact},
        recorded=current.recorded,
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )


@pytest.mark.adversarial
def test_a_new_verified_fact_with_only_a_profile_bump_fails_the_gate():
    """The bump and the version line are honest, and still say nothing about the fact.

    Rules 1 and 2 are both satisfied here — the version moved and the changelog names it — so
    before rule 4 this change reported clean while the artifact silently began attesting a
    fact no reader of the changelog could name.
    """

    current = _working_tree_snapshot()
    problems = ratchet_problems(
        baseline=current, current=_with_new_verified_fact(current), changelog=_BUMPED
    )
    assert len(problems) == 1, problems
    assert "added-verified" in problems[0] and _NEW_FACT in problems[0]


@pytest.mark.adversarial
def test_a_general_profile_disclosure_does_not_satisfy_the_addition_rule():
    """Prose naming the fact is not a disclosure, for the same reason rule 3 rejects one."""

    current = _working_tree_snapshot()
    changelog = (
        _BUMPED
        + f"- The verified half now carries {_NEW_FACT}, and the artifact digest moved.\n"
    )
    problems = ratchet_problems(
        baseline=current, current=_with_new_verified_fact(current), changelog=changelog
    )
    assert len(problems) == 1 and _NEW_FACT in problems[0]


@pytest.mark.adversarial
@pytest.mark.parametrize(
    "line",
    [
        pytest.param(f"- added: {_NEW_FACT} — a gate now checks it.\n", id="ambiguous-prefix"),
        pytest.param(
            f"- added-verified {_NEW_FACT} — a gate now checks it.\n", id="no-colon"
        ),
        pytest.param(
            "- added-verified: some_other_fact — a gate now checks it.\n", id="wrong-fact"
        ),
        pytest.param(f"- promoted: {_NEW_FACT} — a gate now checks it.\n", id="wrong-direction"),
    ],
)
def test_a_malformed_or_misdirected_addition_entry_fails_the_gate(line):
    """``added`` is not ``added-verified``, and a line about another fact is about another fact.

    The bare prefix is refused rather than accepted as a shorthand: it does not say which half
    gained the fact, and the two halves carry different authority — one says a gate checked it,
    the other says nothing checked it. ``promoted`` is refused too, because it asserts the fact
    was already carried and merely became attested, which is a different history.
    """

    current = _working_tree_snapshot()
    problems = ratchet_problems(
        baseline=current, current=_with_new_verified_fact(current), changelog=_BUMPED + line
    )
    assert len(problems) == 1 and _NEW_FACT in problems[0]


@pytest.mark.happy
def test_a_new_verified_fact_with_its_own_added_verified_line_passes():
    """The disciplined addition, which the gate must not obstruct."""

    current = _working_tree_snapshot()
    changelog = _BUMPED + f"- added-verified: {_NEW_FACT} — a new gate establishes it.\n"
    assert (
        ratchet_problems(
            baseline=current, current=_with_new_verified_fact(current), changelog=changelog
        )
        == []
    )


@pytest.mark.adversarial
def test_the_promotion_rule_is_unchanged_by_the_addition_rule():
    """Rule 3 still answers for movement, and rule 4 for arrival. Neither covers the other.

    Both populations in one change: a promotion disclosed only as an addition, and an addition
    disclosed only as a promotion. Each is refused by the rule that owns it, so the two rules
    are measured to be independent rather than assumed to be.
    """

    current = _working_tree_snapshot()
    promoted = sorted(current.recorded)[0]
    mixed = PartitionSnapshot(
        verified=current.verified | {promoted, _NEW_FACT},
        recorded=current.recorded - {promoted},
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    changelog = (
        _BUMPED
        + f"- added-verified: {promoted} — mislabelled; this fact was already carried.\n"
        + f"- promoted: {_NEW_FACT} — mislabelled; this fact was in neither half.\n"
    )
    problems = ratchet_problems(baseline=current, current=mixed, changelog=changelog)
    assert len(problems) == 2, problems
    assert "does not disclose" in problems[0] and promoted in problems[0]
    assert "added-verified" in problems[1] and _NEW_FACT in problems[1]


@pytest.mark.adversarial
def test_a_rename_owes_a_disclosure_for_the_new_verified_name():
    """A rename is a removal plus an addition, and the addition is what rule 4 sees."""

    current = _working_tree_snapshot()
    renamed_from = "policy_body_digest"
    assert renamed_from in current.verified
    renamed = PartitionSnapshot(
        verified=(current.verified - {renamed_from}) | {_NEW_FACT},
        recorded=current.recorded,
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    problems = ratchet_problems(baseline=current, current=renamed, changelog=_BUMPED)
    assert len(problems) == 1 and _NEW_FACT in problems[0]

    disclosed = _BUMPED + (
        f"- added-verified: {_NEW_FACT} — renamed from {renamed_from}, same gate.\n"
    )
    assert ratchet_problems(baseline=current, current=renamed, changelog=disclosed) == []


@pytest.mark.happy
def test_a_fact_added_only_to_the_recorded_half_owes_no_per_fact_line():
    """The deliberate boundary of rule 4, ratified rather than inferred.

    A recorded fact is carried and digest-covered and nothing checked it, so adding one does
    not change what a determination establishes. Rules 1 and 2 still surface it — the
    membership tuple moved, so the profile version must move and the changelog must name it —
    and that is the disclosure this direction owes.
    """

    current = _working_tree_snapshot()
    recorded_addition = PartitionSnapshot(
        verified=current.verified,
        recorded=current.recorded | {_NEW_FACT},
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version="v99",
    )
    assert (
        ratchet_problems(baseline=current, current=recorded_addition, changelog=_BUMPED) == []
    )
    # ...and without the bump it is still a membership change, so rule 1 still fires.
    unbumped = PartitionSnapshot(
        verified=current.verified,
        recorded=current.recorded | {_NEW_FACT},
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version=current.profile_version,
    )
    problems = ratchet_problems(baseline=current, current=unbumped, changelog=_BUMPED)
    assert len(problems) == 1 and "VERIFICATION_PROFILE_VERSION" in problems[0]


@pytest.mark.adversarial
def test_a_new_verified_fact_without_a_bump_trips_both_the_membership_and_addition_rules():
    """Rule 4 does not replace rule 1: an undisclosed, unbumped addition breaks both."""

    current = _working_tree_snapshot()
    unbumped = PartitionSnapshot(
        verified=current.verified | {_NEW_FACT},
        recorded=current.recorded,
        verified_domain=current.verified_domain,
        recorded_domain=current.recorded_domain,
        profile_version=current.profile_version,
    )
    problems = ratchet_problems(baseline=current, current=unbumped, changelog=_read("changelog"))
    assert len(problems) == 2, problems
    assert "VERIFICATION_PROFILE_VERSION" in problems[0]
    assert "added-verified" in problems[1] and _NEW_FACT in problems[1]


@pytest.mark.invariant
def test_the_parser_sees_a_new_verified_fact_in_the_real_source_shape():
    """Rule 4's population comes from parsed source, so it is measured on parsed source.

    The controls above build snapshots directly. This one rewrites the shipped
    ``VERIFIED_FACT_NAMES`` assignment, parses it back, and confirms the new name arrives as an
    addition and not as a promotion — so the gate would see a real edit the same way.
    """

    current = _working_tree_snapshot()
    added_source = _rewritten(
        _read("verified"), "VERIFIED_FACT_NAMES", current.verified | {_NEW_FACT}
    )
    parsed = snapshot_from_sources(
        verified_py=added_source, identifiers_py=_read("identifiers")
    )
    assert _NEW_FACT in parsed.verified
    assert parsed.recorded == current.recorded
    assert not (parsed.verified & current.recorded) - (current.verified & current.recorded)
    problems = ratchet_problems(baseline=current, current=parsed, changelog=_BUMPED)
    assert len(problems) == 2, problems
    assert "added-verified" in problems[1] and _NEW_FACT in problems[1]
