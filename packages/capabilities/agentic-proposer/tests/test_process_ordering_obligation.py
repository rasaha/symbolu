"""R-3 process ordering: a self-arming obligation, now discharged.

**Read this first: the obligation below is discharged.** ``ProposerProcessState`` is
declared in ``vocabulary.py``, ``ProposerProcessStateTransition.state`` is typed with
it, and ``ProposerProcessRecord`` enforces R-3 and R-4. The skip this module was built
around lifted the moment the enum landed; the historical account below — why the
placeholder existed, exactly which R-3 clause it blocked, and what the mirror was and
was not permitted to originate — is kept because it is the record of what was proved
and when, not because anything here is still pending.

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
representative transition cannot express ``RECEIVED`` or ``EVALUATING`` at all.

**Precisely which clause that blocks, and which it does not.** Two earlier revisions of
this docstring got this wrong in the same direction. The first said the ordering rule
"has nothing to be exercised against"; the second narrowed that to two blocked clauses.
Both overstated the placeholder's reach. R-3 has several clauses, and the placeholder
blocks exactly **one** of them:

* **Blocked** — *no backward transition*, and only that. Stating a backward transition
  needs an order over the states in hand: ``TerminalOutcome`` carries none of the five
  process states, and R-3 fixes no order among the four terminal states it does carry —
  they are alternatives at the end of the chain, not a sequence. So no list buildable from
  ``TerminalOutcome`` is a backward transition. That clause is what this module's skipped
  obligation carries, and it is genuinely inexpressible today.
* **Not blocked** — *``at`` non-decreasing across the list*, *no repeat*, *at most one
  terminal state*, *terminal only in final position*, **and** *subsequence of*
  ``RECEIVED → VALIDATED → OBSERVING → RECONCILING → EVALUATING``. The subsequence clause
  belongs on this side, not the other: the chain admits at most one terminal state and
  only at its end, so a two-element list of terminal states is not a subsequence of it,
  and such a list is buildable from ``TerminalOutcome`` alone. It is entangled with the
  terminal-count clause in exactly the way terminal-count and terminal-position are
  entangled with each other — one two-terminal list violates all three at once — and the
  entanglement is why an earlier reading mistook it for blocked. Each of these is
  expressible today and **not enforced**, and each is recorded where the rest of the
  unenforced local rules are recorded, with a constructed violating instance:
  ``tests/test_unenforced_local_rules.py``.

`[G]` **R-4 is likewise uncovered, and is not blocked at all.** It requires
``terminal_outcome`` to equal the terminal state present in ``state_transitions``, and
under the placeholder both sides are ``TerminalOutcome`` — so the comparison-basis
ambiguity recorded below does **not** arise here, and a record whose narrative and outcome
disagree is constructible and accepted today. That case is in
``tests/test_unenforced_local_rules.py`` too. Nothing in this module covers R-4; it is
cited below only as the premise for terminal membership.

Nothing here may be read as evidence about any R-3 clause, blocked or not.

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

`[G]` **What this module does not settle, and must not.** Terminal **membership** is
settled by entailment, and two other things are not.

Membership: D8's nested-shape table types ``state`` as ``ProposerProcessState``, validated
by enum membership, and R-4 says ``terminal_outcome`` equals "the terminal
``ProposerProcessState`` **when one is present** in ``state_transitions``" — which
presupposes that such a member exists. R-3 carries no weight in that argument: it says
"at most one terminal state and only in final position", which *permits* a terminal state
and does not require one. The load-bearing premises are D8's typing and R-4's
presupposition, and nothing else.

Left open, and for the specification rather than this file: **(i) cardinality** — whether
the enum carries nine members or the five process states alongside some other spelling of
the four; and **(ii) the comparison basis** — R-4 equates ``terminal_outcome``, a
``TerminalOutcome``, with a ``ProposerProcessState``, and a cross-enum ``==`` is never
true in Python, so R-4 must mean equality of name or of value and does not say which. The
assertions below pin only the five process states the chain names. Inventing a cardinality
or a comparison basis here would be exactly the origination a mirror may not do.
"""
from __future__ import annotations

import inspect
import pathlib
import re

import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec

SRC = pathlib.Path(ap.__file__).resolve().parent
MIRROR = pathlib.Path(spec.__file__).resolve()

#: The five process states R-3's chain names, in ratified order. The terminal states are
#: deliberately absent — not because their membership is in doubt (see the `[G]` note
#: above: D8's typing plus R-4's presupposition entail it) but because the enum's
#: cardinality is, and pinning a count here would originate one.
RATIFIED_PROCESS_STATES = (
    "RECEIVED", "VALIDATED", "OBSERVING", "RECONCILING", "EVALUATING",
)

#: The enum the specification assigns to ``ProposerProcessStateTransition.state``.
PROCESS_STATE_ENUM = "ProposerProcessState"

#: The rules this module **claims** to carry as a named skip obligation, each mapped to
#: the test functions that are supposed to carry it. This is a claim, not the registry:
#: ``OBLIGATION_RULES`` at the foot of this module is derived from it by checking that
#: each named function actually exists here, is armed by the placeholder skip, names the
#: rule in its own source, and carries assertions. A hand-written registry could claim a
#: rule this module says nothing about — the same defect, one level up, that
#: ``test_documentation_consistency.py`` exists to prevent for rule *mentions*.
#:
#: R-4 is **not** here. This module cites it as the premise for terminal membership and
#: covers none of it; its uncovered status is recorded in
#: ``tests/test_unenforced_local_rules.py``, which constructs a violating instance.
_CLAIMED_OBLIGATIONS = {
    "R-3": ("test_r3_forward_only_ordering_is_enforced",),
}


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
    "transition here can express a process state. That blocks exactly one of R-3's "
    "clauses: no backward transition, which needs an order over the states in hand and "
    "has none, since the four terminal outcomes are alternatives rather than a sequence. "
    "Its at-monotonicity, no-repeat, terminal-count, terminal-position AND subsequence "
    "clauses ARE expressible today — a two-terminal list violates the last three at once "
    "— are equally unenforced, and are recorded with constructed violating instances in "
    "test_unenforced_local_rules.py. This skip is the obligation for the one blocked "
    "clause: it arms itself when the enum is declared, and the implementation stage must "
    "then prove forward-only ordering for the whole rule. Do not read a green suite as "
    "R-3 coverage."
)


# --------------------------------------------------------------------------- #
# Always runs: the obligation is discharged — the placeholder is gone, and the
# real ``ProposerProcessState`` enum stands in its place.
# --------------------------------------------------------------------------- #

def test_the_placeholder_has_been_discharged_not_merely_edited():
    """The substitution is retired, not silently reworded. If a later change reverts
    ``ProposerProcessStateTransition.state`` to ``TerminalOutcome`` — or to any type
    other than ``ProposerProcessState`` — this fails rather than leaving a silent
    departure from the specification in a module whose whole claim is that it mirrors
    it."""
    source = spec.SPECIFICATION_MIRROR_SOURCE
    assert "state: TerminalOutcome" not in source, (
        "ProposerProcessStateTransition.state is still typed TerminalOutcome "
        "somewhere in the mirror; the discharge that replaced it with "
        "ProposerProcessState is incomplete")
    assert "PLACEHOLDER, documented" not in source, (
        "the old placeholder comment survives in the mirror; the discharge that "
        "replaced TerminalOutcome with ProposerProcessState should have removed it")
    transition = spec.representative_shapes()["ProposerProcessStateTransition"]
    annotation = transition.model_fields["state"].annotation
    assert annotation is ap.ProposerProcessState, (
        f"ProposerProcessStateTransition.state is {annotation!r}, not the ratified "
        "ProposerProcessState")


def test_the_process_state_enum_is_a_proper_superset_of_the_terminal_outcomes():
    """The completion this obligation discharges, checked structurally: every
    ``TerminalOutcome`` member is a ``ProposerProcessState`` member of the same name
    and the same wire value, which is what makes R-4's cross-enum comparison a plain
    value comparison rather than an unstated one."""
    terminal_names = {member.name for member in ap.TerminalOutcome}
    assert terminal_names == {"PROPOSAL", "NEED_EVIDENCE", "ABSTAIN", "ESCALATE"}
    process_state_names = {member.name for member in _ENUM}
    assert terminal_names <= process_state_names
    for name in terminal_names:
        assert ap.TerminalOutcome[name].value == _ENUM[name].value


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

    The terminal states are not asserted here. D8's typing and R-4's "when one is
    present" entail that they are members, but the enum's **cardinality** is not stated in
    the specification, and this file does not get to decide it — so no count is pinned and
    no absence is asserted.
    """
    names = [member.name for member in _ENUM]
    for state in RATIFIED_PROCESS_STATES:
        assert state in names, f"{PROCESS_STATE_ENUM} is missing {state}"
    positions = [names.index(state) for state in RATIFIED_PROCESS_STATES]
    assert positions == sorted(positions), (
        f"{PROCESS_STATE_ENUM} declares the process states out of R-3's order: {names}")


def _state(name):
    """Resolve one state name to a member, from whichever enum carries it.

    D8's typing and R-4's "when one is present" entail that the four terminal outcomes are
    members of ``ProposerProcessState``, but the specification states neither the enum's
    cardinality nor the basis on which R-4 compares a ``TerminalOutcome`` with a
    ``ProposerProcessState``, so this resolves from either enum rather than assuming a
    spelling. If a name resolves from neither, that is the open question surfacing as a
    concrete blocker, and it is reported as such instead of escaping as an enum
    ``KeyError`` that says nothing to the implementer.
    """
    for enum in (_ENUM, ap.TerminalOutcome):
        if enum is not None and name in getattr(enum, "__members__", {}):
            return enum[name]
    pytest.fail(
        f"{name!r} is a member of neither {PROCESS_STATE_ENUM} nor TerminalOutcome. "
        f"R-3's chain ends in the four terminal outcomes and D8's typing plus R-4's "
        f"\"when one is present\" entail that {PROCESS_STATE_ENUM} carries them; the "
        "specification states neither the enum's cardinality nor R-4's comparison basis, "
        "and both must be settled there before this obligation can be discharged.")


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
        "advisory_digest": spec.PLACEHOLDER_DIGEST,
        "jcs_distribution_version": "0.2.0",
        "started_at": spec.FIXED_INSTANT,
        "completed_at": spec.FIXED_INSTANT,
    }
    fixture.update(overrides)
    return fixture


# --------------------------------------------------------------------------- #
# The obligation registry, derived from the tests that carry it
# --------------------------------------------------------------------------- #

def _obligation_is_carried(rule, test_names):
    """Whether this module really carries ``rule`` as an armed skip obligation.

    Four things must hold of every test named for the rule, and each is the failure mode
    a hand-written registry could not see:

    * the function **exists** in this module — a renamed or deleted test must not keep
      crediting the rule;
    * it is **armed by the placeholder skip**, so the obligation lifts by itself rather
      than staying dormant after the enum lands;
    * its own source **names the rule**, so a test about something else cannot be
      enlisted; and
    * it carries **assertions**, so a body reduced to ``pass`` stops counting.
    """
    if not test_names:
        return False
    for name in test_names:
        function = globals().get(name)
        if not callable(function):
            return False
        marks = getattr(function, "pytestmark", ())
        if not any(mark.name == "skipif" for mark in marks):
            return False
        source = inspect.getsource(function).lower()
        spellings = (rule.lower(), rule.replace("-", "").lower())
        if not any(spelling in source for spelling in spellings):
            return False
        if "assert " not in source and "pytest.fail" not in source:
            return False
    return rule in _UNARMED_REASON


#: The rules this module carries as a **named skip obligation** — written, deliberately
#: not passing, and armed to run when the placeholder is replaced. Read by
#: ``test_documentation_consistency.py`` so that "a test works with this rule" is decided
#: by a registry rather than by a rule id appearing somewhere in prose. Derived, so the
#: registry cannot outlive the tests it describes.
OBLIGATION_RULES = tuple(
    rule for rule, tests in _CLAIMED_OBLIGATIONS.items()
    if _obligation_is_carried(rule, tests))


def test_the_obligation_registry_is_derived_and_discriminating():
    """The registry must be earned by the module's contents, and must be refusable.

    Two directions, because a derivation that admits everything proves nothing about what
    it admits. R-3 is claimed and carried, so it is present; a rule claimed with a test
    that does not exist, with no test at all, or with a test that is not skip-armed is
    refused. Without the negative half, ``_obligation_is_carried`` could be a constant
    ``True`` and this file would still look green.
    """
    assert OBLIGATION_RULES == ("R-3",), (
        f"the derived obligation registry is {OBLIGATION_RULES}; either a claimed rule "
        "lost the test that carried it, or a new obligation landed without this "
        "assertion being updated")
    assert not _obligation_is_carried("R-3", ()), "a rule with no test must be refused"
    assert not _obligation_is_carried("R-3", ("test_no_such_obligation_exists",)), (
        "a rule naming a test that does not exist must be refused")
    assert not _obligation_is_carried(
        "R-3", ("test_the_placeholder_is_still_a_placeholder_and_says_so",)), (
        "a rule named against an always-running test must be refused; the obligation is "
        "the skip, and an unarmed test is not one")
    assert not _obligation_is_carried("R-9", _CLAIMED_OBLIGATIONS["R-3"]), (
        "a rule the carrying test never names, and the skip reason never states, must "
        "be refused")
