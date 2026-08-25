"""The locally decidable rules the representative shapes do **not** enforce, recorded.

**Read this first: nothing here is coverage.** Every case below is a specification rule
that the mirror's representative shapes currently *accept in violation*, and each is
asserted to be accepted. A green run of this module means the rules are still unenforced.

**Why this module exists rather than nothing.** ``tests/s1_specification_mirror.py``
declares two model validators — C7's unconditional rejection of
``DomainCheckCompletion.COMPLETE`` and R-1a's selector/dependent coupling — and declares
no others. That asymmetry is invisible: a reader who sees two validators has no way to
tell whether the other locally decidable rules were considered and deferred, or missed.
``docs/S1_ENFORCEMENT.md`` states the omission in prose, and prose about absence rots the
moment someone implements one. This module is the mechanical half: it constructs a
violating instance for **every** rule that prose lists, so the list cannot claim a rule is
unenforced when it is, or quietly omit one that still is.

**"Locally decidable" is the membership rule, and it is what keeps this list bounded.** A
rule belongs here when one instance of one contract is enough to decide it — no builder,
no verifier, no second contract, no supplied observation collection.

Absent, and why — stated here rather than left to be inferred from the list's silence:

* **R-5, R-6, R-7, R-9, R-10** each compare two contracts. Out of scope by construction.
* **R-2** calls ``evaluate_readiness``. Out of scope by construction.
* **R-1b clauses (i)–(iv), (viii), (ix)** resolve the referenced ``AdvisoryCandidateSet``.
  Out of scope. Clauses **(v)**, **(vi)** and the **local half of (vii)** became decidable
  from one instance when OD-4(a) nested the candidates inside the advisory, and are here.
  (vii)'s other conjunct — membership in ``CognitiveRoleContract.permitted_review_actions``
  — needs the role contract and stays out.
* **R-3's chain clauses** — no backward transition, and subsequence of
  ``RECEIVED → … → EVALUATING`` — cannot be *expressed* while
  ``ProposerProcessStateTransition.state`` stands in as ``TerminalOutcome``, which carries
  no process state. They are out of scope for that reason and only that reason, and
  ``tests/test_process_ordering_obligation.py`` carries them as a named skip. R-3's
  remaining clauses **are** expressible today and are here.
* **``CandidateAdvisory.claim_refs``** is absent because no rule bars a duplicate there —
  see the test at the foot of this module.

Two entries are **derived** rather than stated twice, and are labelled as such:

* **S-2 on ``ProposerAdvisory``.** S-2 is stated under D6, of ``AdvisoryCandidateSet``.
  R-1b(iii) requires the advisory's nested ``candidates`` to equal the set's in content
  and R-1b(iv) requires the selectors to be equal, so S-2 lands on the advisory as a
  consequence. It is exercised on both, and the advisory-side case is labelled
  ``S-2 (via R-1b)`` so that no reader takes it for a second statement of the rule.
* **R-3's terminal-count and terminal-position clauses** are entangled under the
  placeholder: with only terminal states available, a two-element list that puts one in
  non-final position necessarily also carries two of them. One construction violates
  both, and is labelled once rather than counted twice.

`[I]` **S-1 and S-2 are vacuous in S1**, because B3 makes ``selected_candidate_id``
``None`` for every advisory S1 can construct (spec: "Under B3, ``selected_candidate_id``
is ``None`` for every advisory S1 can construct", and again under *What S1 does not
build*). They are exercised here anyway: the representative shapes do not enforce B3
either, so a non-null selector is constructible, and a rule that is vacuous by an
invariant nothing checks is not a rule anything is enforcing.

**When one of these is implemented**, its case fails, and the failure is the signal to
delete the case and update the row in ``docs/S1_ENFORCEMENT.md`` in the same change. That
is the intended lifecycle, not a defect.
"""
from __future__ import annotations

import pytest

import ugence_agentic_proposer as ap
import s1_specification_mirror as spec


def _shapes():
    pytest.importorskip("pydantic")
    return spec.representative_shapes()


def _candidate(candidate_id, **overrides):
    return _shapes()["CandidateAdvisory"](
        **{**spec.complete_candidate(candidate_id), **overrides})


def _transition(state, at=None):
    return _shapes()["ProposerProcessStateTransition"](
        state=state, at=spec.FIXED_INSTANT if at is None else at)


#: A second lawful ``ReviewAction``, so a contradiction can be built without inventing a
#: value. Resolved from the ratified enum rather than written out.
_OTHER_REVIEW_ACTION = next(
    action for action in spec.ReviewAction
    if action is not spec.ReviewAction.ROUTE_APPROVAL_BUNDLE)

#: An instant strictly after ``FIXED_INSTANT``, for the ``at`` monotonicity clause. No
#: wall clock is read (C4).
_LATER_INSTANT = spec.FIXED_INSTANT.replace(year=spec.FIXED_INSTANT.year + 1)


def _role_contract(**overrides):
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "role_contract_id": "role-1",
        "primary_function": "reconcile and propose",
        "permitted_tool_scopes": [],
        "permitted_candidate_dispositions": [ap.CandidateDisposition.RECOMMEND_WITHHOLD],
        "permitted_review_actions": [spec.ReviewAction.ROUTE_APPROVAL_BUNDLE],
        "escalation_role_ref": "role-2",
        "activation_status": spec.RoleActivationStatus.ACTIVE,
    }
    fixture.update(overrides)
    return _shapes()["CognitiveRoleContract"](**fixture)


def _work_mandate(**overrides):
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "mandate_id": "mandate-1",
        "case_ref": "case-1",
        "assigned_role_contract_id": "role-1",
        "purpose": "reconcile and propose",
        "allowed_source_scopes": ["scope-1"],
        "expires_at": spec.FIXED_INSTANT,
    }
    fixture.update(overrides)
    return _shapes()["WorkMandate"](**fixture)


def _candidate_set(**overrides):
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "candidate_set_id": "set-1",
        "case_ref": "case-1",
        "candidates": (_candidate("cand-1"),),
        "selected_candidate_id": None,
        "selection_reason_codes": [],
    }
    fixture.update(overrides)
    return _shapes()["AdvisoryCandidateSet"](**fixture)


def _process_record(**overrides):
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
    return _shapes()["ProposerProcessRecord"](**fixture)


def _advisory(**overrides):
    return _shapes()["ProposerAdvisory"](**spec.complete_advisory_fixture(**overrides))


def _selection(selected, **overrides):
    """A complete R-1a-satisfying selection, so a rejection can only be about the rule
    under probe and never about the local coupling."""
    fixture = {
        "selected_candidate_id": selected,
        "recommended_disposition": ap.CandidateDisposition.RECOMMEND_WITHHOLD,
        "requested_review_action": spec.ReviewAction.ROUTE_APPROVAL_BUNDLE,
        "requested_review_destination_role_ref": "role-1",
    }
    fixture.update(overrides)
    return fixture


#: Every rule ``docs/S1_ENFORCEMENT.md`` records as locally decidable and unenforced,
#: paired with a construction that violates it. ``rule`` is the specification's own id or
#: table row, so the row and this registry can be read against each other by eye.
UNENFORCED = (
    ("L-1", "parent_advisory_digest equals this advisory's own advisory_digest",
     lambda: _advisory(advisory_digest="sha", parent_advisory_digest="sha")),

    ("D7 candidates", "ProposerAdvisory.candidates is empty",
     lambda: _advisory(candidates=())),
    ("D7 candidates", "ProposerAdvisory.candidates repeats a candidate_id",
     lambda: _advisory(candidates=(_candidate("dup"), _candidate("dup")))),
    ("D7 candidates", "ProposerAdvisory.candidates is descending by candidate_id",
     lambda: _advisory(candidates=(_candidate("b-2"), _candidate("a-1")))),

    ("D6 candidates", "AdvisoryCandidateSet.candidates is empty",
     lambda: _candidate_set(candidates=())),
    ("D6 candidates", "AdvisoryCandidateSet.candidates repeats a candidate_id",
     lambda: _candidate_set(candidates=(_candidate("dup"), _candidate("dup")))),
    ("D6 candidates", "AdvisoryCandidateSet.candidates is descending by candidate_id",
     lambda: _candidate_set(candidates=(_candidate("b-2"), _candidate("a-1")))),

    ("R-8", "ProposerAdvisory.observation_refs repeats an entry",
     lambda: _advisory(observation_refs=["obs-1", "obs-1"])),
    ("R-8", "CandidateAdvisory.observation_refs repeats an entry",
     lambda: _shapes()["CandidateAdvisory"](
         **{**spec.complete_candidate(), "observation_refs": ["obs-1", "obs-1"]})),
    ("R-8", "ProposerProcessRecord.candidate_ids repeats an entry",
     lambda: _process_record(candidate_ids=["cand-1", "cand-1"])),
    ("R-8", "CognitiveRoleContract.permitted_tool_scopes repeats an entry",
     lambda: _role_contract(permitted_tool_scopes=["scope-1", "scope-1"])),
    ("R-8", "CognitiveRoleContract.permitted_candidate_dispositions repeats an entry",
     lambda: _role_contract(permitted_candidate_dispositions=[
         ap.CandidateDisposition.RECOMMEND_WITHHOLD,
         ap.CandidateDisposition.RECOMMEND_WITHHOLD])),
    ("R-8", "CognitiveRoleContract.permitted_review_actions repeats an entry",
     lambda: _role_contract(permitted_review_actions=[
         spec.ReviewAction.ROUTE_APPROVAL_BUNDLE,
         spec.ReviewAction.ROUTE_APPROVAL_BUNDLE])),
    ("R-8", "WorkMandate.allowed_source_scopes repeats an entry",
     lambda: _work_mandate(allowed_source_scopes=["scope-1", "scope-1"])),

    ("D3 cardinality", "WorkMandate.allowed_source_scopes is empty",
     lambda: _work_mandate(allowed_source_scopes=[])),
    ("D2 cardinality", "CognitiveRoleContract.permitted_candidate_dispositions is empty",
     lambda: _role_contract(permitted_candidate_dispositions=[])),
    ("D2 cardinality", "CognitiveRoleContract.permitted_review_actions is empty",
     lambda: _role_contract(permitted_review_actions=[])),

    ("R-1b(v)", "selected_candidate_id names no member of the advisory's own candidates",
     lambda: _advisory(candidates=(_candidate("a-1"),),
                       **_selection("not-a-candidate"))),
    ("R-1b(vi)", "recommended_disposition contradicts the selected nested candidate",
     lambda: _advisory(
         candidates=(_candidate("a-1"),),
         **_selection("a-1", recommended_disposition=(
             ap.CandidateDisposition.RECOMMEND_MATCHED_FOR_APPROVAL)))),
    ("R-1b(vii)",
     "requested_review_action contradicts the selected nested candidate (local half)",
     lambda: _advisory(
         candidates=(_candidate("a-1"),),
         **_selection("a-1", requested_review_action=_OTHER_REVIEW_ACTION))),

    ("S-1", "AdvisoryCandidateSet selector names no member of candidates",
     lambda: _candidate_set(selected_candidate_id="not-a-candidate")),
    ("S-1", "AdvisoryCandidateSet selector resolves to two candidates",
     lambda: _candidate_set(candidates=(_candidate("dup"), _candidate("dup")),
                            selected_candidate_id="dup")),

    ("S-2", "AdvisoryCandidateSet resolved candidate has is_eligible False",
     lambda: _candidate_set(candidates=(_candidate("a-1", is_eligible=False),),
                            selected_candidate_id="a-1")),
    ("S-2 (via R-1b)",
     "ProposerAdvisory selected nested candidate has is_eligible False",
     lambda: _advisory(candidates=(_candidate("a-1", is_eligible=False),),
                       **_selection("a-1"))),

    ("R-3", "state_transitions has a decreasing `at`",
     lambda: _process_record(state_transitions=[
         _transition(ap.TerminalOutcome.NEED_EVIDENCE, _LATER_INSTANT),
         _transition(ap.TerminalOutcome.ABSTAIN)],
         terminal_outcome=ap.TerminalOutcome.ABSTAIN)),
    ("R-3", "state_transitions carries two terminal states, one in non-final position",
     lambda: _process_record(state_transitions=[
         _transition(ap.TerminalOutcome.ABSTAIN),
         _transition(ap.TerminalOutcome.ESCALATE)],
         terminal_outcome=ap.TerminalOutcome.ESCALATE)),
    ("R-3", "state_transitions repeats a state",
     lambda: _process_record(state_transitions=[
         _transition(ap.TerminalOutcome.ABSTAIN),
         _transition(ap.TerminalOutcome.ABSTAIN)])),

    ("R-4", "terminal_outcome disagrees with the terminal state in state_transitions",
     lambda: _process_record(
         state_transitions=[_transition(ap.TerminalOutcome.ESCALATE)],
         terminal_outcome=ap.TerminalOutcome.ABSTAIN)),
)


@pytest.mark.parametrize("rule,description,construct",
                         UNENFORCED, ids=lambda v: str(v)[:60])
def test_the_shape_accepts_this_violation(rule, description, construct):
    """One violating instance per recorded rule, constructed rather than described.

    A rule listed in the enforcement documentation as unenforced must actually be
    unenforced, or the documentation understates what the guards establish. If this
    starts raising, the validator was implemented: delete the case and update
    ``docs/S1_ENFORCEMENT.md`` in the same change.
    """
    pydantic = pytest.importorskip("pydantic")
    try:
        construct()
    except pydantic.ValidationError as error:
        pytest.fail(
            f"{rule} is now enforced for: {description}. That is progress, not a "
            f"failure — delete this case and update the 'What the guards do not yet "
            f"establish' row in docs/S1_ENFORCEMENT.md in the same change. ({error})")


#: The rules the mirror **does** enforce, paired with a construction each must reject.
#: The other side of the asymmetry, kept as a registry rather than as inline assertions so
#: that ``test_documentation_consistency.py`` can read which rules a test actually works
#: with instead of inferring it from a textual mention.
ENFORCED = (
    ("C7", "DomainCheckCompletion.COMPLETE on a candidate",
     lambda: _shapes()["CandidateAdvisory"](**{
         **spec.complete_candidate(),
         "domain_check_completion": spec.DomainCheckCompletion.COMPLETE})),
    ("R-1a", "a selector with none of its three dependents",
     lambda: _advisory(selected_candidate_id="cand-1")),
    ("R-1a", "a dependent with no selector",
     lambda: _advisory(
         recommended_disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD)),
)


@pytest.mark.parametrize("rule,description,construct", ENFORCED, ids=lambda v: str(v)[:60])
def test_the_rules_the_mirror_does_declare_still_reject(rule, description, construct):
    """The other side of the asymmetry, so this module is discriminating rather than a
    list of things that happen not to raise.

    C7 and R-1a **are** declared, and they reject. If they did not, every case in
    ``UNENFORCED`` would be unremarkable and this module would prove nothing about the
    mirror.
    """
    pydantic = pytest.importorskip("pydantic")
    with pytest.raises(pydantic.ValidationError):
        construct()
    assert rule not in {entry[0] for entry in UNENFORCED}, (
        f"{rule} is registered as both enforced and unenforced; one of the two is wrong")


def test_claim_refs_is_not_listed_because_no_rule_bars_a_duplicate_there():
    """A near miss, recorded so it is not "fixed" later by someone reading the list.

    ``CandidateAdvisory.claim_refs`` looks like the R-8 lists and is not one of them: its
    Part D row states ``each C5a`` and nothing more, and R-8 names ``observation_refs``,
    ``candidate_ids``, ``permitted_tool_scopes``, ``permitted_candidate_dispositions``,
    ``permitted_review_actions`` and ``allowed_source_scopes`` — not ``claim_refs``. A
    duplicate there is therefore lawful, and adding it to the registry above would be a
    test originating a rule the specification does not state.
    """
    body = spec.SPECIFICATION.read_text(encoding="utf-8")
    row = [line for line in body.splitlines() if line.startswith("| `claim_refs` |")]
    assert row, "the claim_refs row is gone; re-read this analysis"
    assert "no duplicates" not in row[0], (
        "claim_refs now carries a no-duplicates rule; it belongs in UNENFORCED above")
    assert all("claim_refs" not in line
               for line in body.splitlines() if line.startswith("| R-8 |")), (
        "R-8 now names claim_refs; it belongs in UNENFORCED above")

    # And the shape does accept a duplicate today, which is lawful rather than a gap.
    _shapes()["CandidateAdvisory"](
        **{**spec.complete_candidate(), "claim_refs": ["c-1", "c-1"]})
