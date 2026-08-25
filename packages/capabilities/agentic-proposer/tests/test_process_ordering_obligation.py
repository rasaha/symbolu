"""R-3 process ordering: an explicit, self-arming obligation — **not** coverage.

**Read this first: R-3 is not enforced anywhere in this package today.**

R-3 requires ``ProposerProcessRecord.state_transitions`` to be a subsequence of

    RECEIVED -> VALIDATED -> OBSERVING -> RECONCILING -> EVALUATING
             -> {PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE}

with no backward transition, no repeat, at most one terminal state and only in final
position, and ``at`` non-decreasing across the list.

Nothing here proves any of that. The reason is recorded in full in
``s1_specification_mirror``'s docstring and repeated here because a reader who opens only
this file must not have to go looking: the specification types
``ProposerProcessStateTransition.state`` as ``ProposerProcessState``,
``src/ugence_agentic_proposer/vocabulary.py`` does not declare that enum, and the mirror
may not originate a vocabulary the specification assigns to the package's public surface.
The representative shape therefore stands ``TerminalOutcome`` in — a strict **subset**
carrying the four terminal states and none of the five process states — so a
representative transition cannot express ``RECEIVED`` or ``EVALUATING`` at all, and the
ordering rule has nothing to be exercised against.

**Why this module exists rather than nothing.** A rule that no test mentions is
indistinguishable from a rule nobody has thought about. Before this module, R-3 appeared
in the specification and in no test file at all: a reader counting green tests would have
found no signal that a ratified invariant was uncovered. The obligation below is
therefore written now, **skipped by name**, and it **arms itself** the moment
``ProposerProcessState`` is declared. It is deliberately not a passing test:

* while the placeholder stands, it is an explicit skip whose reason says R-3 is uncovered
  — visible in ``pytest -rs`` and impossible to mistake for coverage;
* once the enum is declared, the skip lifts and the assertions run. They will **fail**
  until the ordering validator exists, which is the point: the implementation stage must
  replace the placeholder with the ratified ``ProposerProcessState`` and prove
  forward-only ordering in the same change.

`[G]` **One thing this module does not settle, and must not.** The specification fixes
R-3's ordering chain but does not state ``ProposerProcessState``'s member list as such:
whether the four terminal outcomes are members of that enum, or arrive from
``TerminalOutcome`` in the final position, is not written down. The assertions below pin
only the five process states the chain names, and the implementation stage must settle
the terminal question **against the specification**, not against this file. Inventing a
cardinality here would be exactly the origination a mirror may not do.
"""
from __future__ import annotations

import pathlib
import re

import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec

SRC = pathlib.Path(ap.__file__).resolve().parent
MIRROR = pathlib.Path(spec.__file__).resolve()

#: The five process states R-3's chain names, in ratified order. The terminal states are
#: deliberately absent — see the `[G]` note above.
RATIFIED_PROCESS_STATES = (
    "RECEIVED", "VALIDATED", "OBSERVING", "RECONCILING", "EVALUATING",
)

#: The enum the specification assigns to ``ProposerProcessStateTransition.state``.
PROCESS_STATE_ENUM = "ProposerProcessState"


def _process_state_enum():
    """The declared ``ProposerProcessState``, or ``None`` while it does not exist.

    Read from the package's own surface, not from the mirror, because the mirror may not
    declare it and its presence there would mean the boundary had been crossed.
    """
    return getattr(ap, PROCESS_STATE_ENUM, None) or getattr(
        getattr(ap, "vocabulary", None), PROCESS_STATE_ENUM, None)


_ENUM = _process_state_enum()
_UNARMED_REASON = (
    "R-3 PROCESS ORDERING IS NOT COVERED. "
    f"{PROCESS_STATE_ENUM} is not declared in src/ugence_agentic_proposer/, so the "
    "representative shape stands TerminalOutcome in as a documented placeholder and no "
    "transition here can express a process state. This skip is the obligation: it arms "
    "itself when the enum is declared, and the implementation stage must then prove "
    "forward-only ordering. Do not read a green suite as R-3 coverage."
)


# --------------------------------------------------------------------------- #
# Always runs: the placeholder boundary is real, documented, and unchanged
# --------------------------------------------------------------------------- #

def test_the_placeholder_is_still_a_placeholder_and_says_so():
    """The substitution must stay explicit. If the mirror is edited to type the field
    with something else, or the explanation is deleted, this fails rather than leaving a
    silent departure from the specification in a module whose whole claim is that it
    mirrors it."""
    source = spec.SPECIFICATION_MIRROR_SOURCE
    doc = " ".join((spec.__doc__ or "").split())
    assert "PLACEHOLDER" in source, (
        "the placeholder comment at ProposerProcessStateTransition.state is gone; either "
        "the enum was declared — in which case update this module — or the departure has "
        "become silent")
    for clause in (
        "typed ``TerminalOutcome``, and the specification types it "
        "``ProposerProcessState``",
        "no probe here exercises R-3's ordering rule",
    ):
        assert " ".join(clause.split()) in doc, (
            f"the mirror no longer documents the placeholder: {clause!r}")


def test_the_placeholder_type_is_a_strict_subset_of_what_the_rule_needs():
    """Why the placeholder cannot be used to fake coverage, demonstrated.

    ``TerminalOutcome`` carries none of the five process states, so there is no way to
    build a representative transition sequence R-3 could be evaluated against. A test
    that tried would be asserting something about four terminal values, not about
    ordering.
    """
    members = {member.name for member in ap.TerminalOutcome}
    assert members == {"PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"}
    assert not members & set(RATIFIED_PROCESS_STATES), (
        "TerminalOutcome now carries a process state; the placeholder analysis has "
        "changed and this module must be re-read")
    transition = spec.representative_shapes()["ProposerProcessStateTransition"]
    annotation = transition.model_fields["state"].annotation
    assert annotation is ap.TerminalOutcome, (
        f"the placeholder type changed to {annotation!r} without this module being "
        "updated")


def test_the_mirror_does_not_declare_the_enum_itself():
    """The boundary this stage preserves: the mirror may not originate a vocabulary the
    specification assigns to the package's public surface. If this ever fails, the
    enum was added in the wrong place."""
    # Word-anchored: ``class ProposerProcessStateTransition`` is a lawful declaration
    # here and shares a prefix with the enum's name.
    declared = re.search(rf"^class {PROCESS_STATE_ENUM}\b", spec.SPECIFICATION_MIRROR_SOURCE,
                         re.M)
    assert declared is None, (
        f"{PROCESS_STATE_ENUM} is declared in the mirror; it belongs in "
        "src/ugence_agentic_proposer/vocabulary.py, and adding it there is a separate, "
        "separately authorized change")


def test_the_obligation_arms_when_the_enum_is_declared():
    """The arming condition itself, asserted so it cannot rot.

    Whichever way the enum arrives — exported from the package or declared on
    ``vocabulary`` — ``_process_state_enum`` must see it. A detector that could not see
    the enum would leave this obligation skipped forever, which is the failure mode a
    skip-based obligation has.
    """
    assert _process_state_enum() is _ENUM
    if _ENUM is None:
        assert not hasattr(ap, PROCESS_STATE_ENUM)
        assert PROCESS_STATE_ENUM not in (SRC / "vocabulary.py").read_text(
            encoding="utf-8"), (
            f"{PROCESS_STATE_ENUM} appears in vocabulary.py but the detector did not "
            "resolve it; the obligation below would stay skipped after arming")
    assert _UNARMED_REASON.startswith("R-3 PROCESS ORDERING IS NOT COVERED")


# --------------------------------------------------------------------------- #
# Skipped by name until the enum lands, then armed and failing until R-3 holds
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(_ENUM is None, reason=_UNARMED_REASON)
def test_the_process_state_enum_carries_the_five_ratified_process_states():
    """Armed by the enum's declaration. The five states R-3's chain names must all be
    members, in that order.

    The terminal states are not asserted here: whether they are members of this enum or
    arrive from ``TerminalOutcome`` is not stated in the specification, and this file
    does not get to decide it.
    """
    names = [member.name for member in _ENUM]
    for state in RATIFIED_PROCESS_STATES:
        assert state in names, f"{PROCESS_STATE_ENUM} is missing {state}"
    positions = [names.index(state) for state in RATIFIED_PROCESS_STATES]
    assert positions == sorted(positions), (
        f"{PROCESS_STATE_ENUM} declares the process states out of R-3's order: {names}")


def _state(name):
    """Resolve one state name to a member, from whichever enum carries it.

    The specification does not settle whether the four terminal outcomes are members of
    ``ProposerProcessState`` or arrive from ``TerminalOutcome``, so this resolves from
    either rather than assuming one. If a name resolves from neither, that is the open
    question surfacing as a concrete blocker, and it is reported as such instead of
    escaping as an enum ``KeyError`` that says nothing to the implementer.
    """
    for enum in (_ENUM, ap.TerminalOutcome):
        if enum is not None and name in getattr(enum, "__members__", {}):
            return enum[name]
    pytest.fail(
        f"{name!r} is a member of neither {PROCESS_STATE_ENUM} nor TerminalOutcome. "
        "R-3's chain ends in the four terminal outcomes, so one of the two must carry "
        "them; the specification does not say which, and that question must be settled "
        "there before this obligation can be discharged.")


@pytest.mark.skipif(_ENUM is None, reason=_UNARMED_REASON)
def test_r3_forward_only_ordering_is_enforced():
    """Armed by the enum's declaration, and **expected to fail until R-3 is
    implemented**. That is the obligation, not a defect in this test.

    The implementation stage must supply a ``ProposerProcessRecord`` that rejects each of
    the five ways R-3 can be violated. Until the validator exists, the representative
    shape accepts all of them and this fails, naming which one was accepted.
    """
    pydantic = pytest.importorskip("pydantic")
    record = spec.representative_shapes()["ProposerProcessRecord"]
    shape = spec.representative_shapes()["ProposerProcessStateTransition"]
    later = spec.FIXED_INSTANT.replace(year=spec.FIXED_INSTANT.year + 1)

    def transitions(pairs):
        built = []
        for name, at in pairs:
            try:
                built.append(shape(state=_state(name), at=at))
            except pydantic.ValidationError as error:
                pytest.fail(
                    f"the transition shape rejects {name!r}: {error}. The placeholder "
                    "must be replaced with the ratified ProposerProcessState in the "
                    "same change that discharges this obligation.")
        return built

    def rejected(label, pairs):
        try:
            record(**_process_record_fixture(state_transitions=transitions(pairs)))
        except pydantic.ValidationError:
            return True
        pytest.fail(f"R-3 is not enforced: {label} was accepted")

    at = spec.FIXED_INSTANT
    assert rejected("a backward transition",
                    [("VALIDATED", at), ("RECEIVED", at)])
    assert rejected("a repeated state",
                    [("RECEIVED", at), ("RECEIVED", at)])
    assert rejected("two terminal states",
                    [("EVALUATING", at), ("ABSTAIN", at), ("ESCALATE", at)])
    assert rejected("a terminal state in non-final position",
                    [("ABSTAIN", at), ("EVALUATING", at)])
    assert rejected("a non-monotonic timestamp",
                    [("RECEIVED", later), ("VALIDATED", at)])


def _process_record_fixture(**overrides):
    """Every required ``ProposerProcessRecord`` field, so an R-3 rejection can only be
    about ordering and never about a missing field."""
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "process_record_id": "record-1",
        "case_ref": "case-1",
        "declared_strategy": "reconcile and propose",
        "state_transitions": [],
        "tool_invocations": [],
        "deterministic_checks": [],
        "candidate_ids": [],
        "selected_candidate_id": None,
        "semantic_audit_refs": [],
        "terminal_outcome": ap.TerminalOutcome.ABSTAIN,
        "reason_codes": [],
        "advisory_digest": "placeholder",
        "jcs_distribution_version": "0.2.0",
        "started_at": spec.FIXED_INSTANT,
        "completed_at": spec.FIXED_INSTANT,
    }
    fixture.update(overrides)
    return fixture
