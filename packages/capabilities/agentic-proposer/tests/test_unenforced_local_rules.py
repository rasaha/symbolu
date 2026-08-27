"""The locally decidable rules, and which of them the declared contracts enforce.

**Read this first: this module has changed roles.** It was written while
``tests/s1_specification_mirror.py`` returned temporary representative shapes that
declared only two validators — C7's unconditional rejection of
``DomainCheckCompletion.COMPLETE`` and R-1a's selector/dependent coupling — so that the
asymmetry between "considered and deferred" and "missed" would be visible rather than
silent. ``representative_shapes()`` now returns the declared ``src/`` contracts (I5,
I7), which implement every locally decidable rule stated in Part D and Part E except
one. This module is now split accordingly:

* **``UNENFORCED``** carries what remains genuinely undecidable from a single instance
  — today, exactly one entry, ``S-2 (via R-1b)`` (see below for why it stays out).
* **``ENFORCED``** carries every rule that **is** locally decidable and **is** enforced,
  each paired with a construction the contract must reject. This is the discharge record
  for what used to be a long ``UNENFORCED`` list: every case that once lived there and
  now raises has moved here rather than being deleted silently, so the history of what
  was proved and when stays legible.

**"Locally decidable" is the membership rule for both registries, and it is what keeps
them bounded.** A rule belongs here when one instance of one contract is enough to
decide it — no builder, no verifier, no second contract, no supplied observation
collection.

**The rule admits entailed consequences, and says so.** Where a rule stated of one
contract lands on another because a ratified clause carries it there, and the resulting
obligation is still decidable from one instance, the consequence belongs here and is
labelled with the clause that carries it. ``S-2 (via R-1b)`` is the one entry that relies
on this: R-1b(iii) requires the advisory's nested ``candidates`` to equal the referenced
``AdvisoryCandidateSet``'s in content, and R-1b(iv) requires the selectors to be equal,
so S-2 (itself stated of ``AdvisoryCandidateSet``) lands on ``ProposerAdvisory`` as a
consequence — but only once both R-1b clauses are checked against the **referenced set**,
which no single ``ProposerAdvisory`` instance carries. It is not double-counted: S-2
stated directly of ``AdvisoryCandidateSet`` is decidable from that one instance and is
enforced there (see ``ENFORCED``); ``S-2 (via R-1b)`` names the separate, still-open
question of whether an advisory's *carried* copy of a candidate remains eligible, which
only the builder and ``verify_advisory_selection`` can answer.

Absent from both registries, and why — stated here rather than left to be inferred from
silence:

* **R-5, R-6, R-7, R-9, R-10** each compare two contracts. Out of scope by construction;
  each is discharged by ``identity.py``'s builders and by ``verification.py``.
* **R-2** calls ``evaluate_readiness``, which needs the identity, role, mandate and
  context objects a ``ProposerProcessRecord`` alone does not carry. What R-2 requires in
  S1 — that ``PROPOSAL`` is unreachable — is a distinct, locally decidable rule and **is**
  enforced (see ``ENFORCED``); the general biconditional stays a builder obligation.
* **R-1b clauses (i), (ii), (iii), (iv), (viii), (ix)** resolve the referenced
  ``AdvisoryCandidateSet``. Out of scope **as clauses to be violated on one instance**:
  deciding whether any of them holds needs that set, and they are discharged by
  ``verify_advisory_selection``. Clauses **(v)**, **(vi)** and the **local half of
  (vii)** became decidable from one instance once OD-4(a) nested the candidates inside
  the advisory, and are enforced (see ``ENFORCED``); (vii)'s other conjunct — membership
  in ``CognitiveRoleContract.permitted_review_actions`` — needs the role contract and
  stays a builder/verifier obligation.
* **``CandidateAdvisory.claim_refs``** is absent because no rule bars a duplicate there —
  see the test at the foot of this module.

**When a builder- or verifier-level rule above is later found to be locally
decidable after all**, or when ``S-2 (via R-1b)`` is discharged by a future change, the
signal is the same as it always was: move the case into ``ENFORCED`` with a construction
that raises, and update the corresponding row in ``docs/S1_ENFORCEMENT.md`` in the same
change.
"""
from __future__ import annotations

import unicodedata

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

#: The same instant with its offset stripped, for C4's timezone-awareness clause. `[V]`
#: A9 and C4 both record that ``strict=True`` does not reject a naive ``datetime``, so
#: the explicit ``@field_validator`` C4 requires is the only thing that would, and the
#: mirror declares none.
_NAIVE_INSTANT = spec.FIXED_INSTANT.replace(tzinfo=None)

#: A ``purpose`` that is not NFC: the same text as ``"reconcile\u0301"`` would be after
#: NFD decomposition, built with ``unicodedata`` rather than pasted so the file's own
#: encoding cannot silently normalise it away.
_NON_NFC_PURPOSE = unicodedata.normalize("NFD", "reconcil\u00e9 and propose")
assert not unicodedata.is_normalized("NFC", _NON_NFC_PURPOSE), (
    "the non-NFC fixture is NFC after all; D3's case would pass for the wrong reason")


def _agent_identity_ref(**overrides):
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "agent_id": "agent-1",
        "agent_version": "1.0.0",
        "lifecycle_state": spec.AgentLifecycleState.ACTIVE,
        "bound_role_contract_id": "role-1",
        "owner_role_ref": "role-2",
    }
    fixture.update(overrides)
    return _shapes()["AgentIdentityRef"](**fixture)


def _context_envelope(**overrides):
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "context_id": "context-1",
        "mandate_id": "mandate-1",
        "allowed_record_refs": [],
        "excluded_data_classes": [],
        "context_hash": spec.PLACEHOLDER_DIGEST,
        "expires_at": spec.FIXED_INSTANT,
    }
    fixture.update(overrides)
    return _shapes()["BoundedContextEnvelope"](**fixture)


def _tool_observation(**overrides):
    fixture = {
        "schema_version": "1.0",
        "tenant_id": "tenant-1",
        "created_at": spec.FIXED_INSTANT,
        "observation_id": "obs-1",
        "case_ref": "case-1",
        "tool_name": "tool-1",
        "operation_class": spec.ToolOperationClass.READ_ONLY,
        "source_ref": "source-1",
        "observed_at": spec.FIXED_INSTANT,
        "content_hash": spec.PLACEHOLDER_DIGEST,
        "normalized_fields": {},
        "admission_status": spec.ToolObservationAdmissionStatus.NOT_EVALUATED,
    }
    fixture.update(overrides)
    return _shapes()["ToolObservation"](**fixture)


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
        "advisory_digest": spec.PLACEHOLDER_DIGEST,
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


#: The one rule that remains genuinely undecidable from a single instance (see the
#: module docstring for why ``S-2 (via R-1b)`` cannot fold into ``S-2`` itself, which
#: **is** enforced and lives in ``ENFORCED`` below).
_STATED_CASES = (
    ("S-2 (via R-1b)",
     "ProposerAdvisory selected nested candidate has is_eligible False",
     lambda: _advisory(candidates=(_candidate("a-1", is_eligible=False),),
                       **_selection("a-1"))),
)


#: Every ``datetime`` field Part D declares, contract by contract, in the order the
#: contracts are stated. Pinned rather than derived from the shapes so the headline count
#: stays a reviewed number, and checked against the shapes by
#: ``test_the_c4_cases_cover_every_datetime_field_the_shapes_declare`` below — a field
#: added to Part D and mirrored fails there rather than escaping this registry in silence.
C4_DATETIME_FIELDS = (
    ("AgentIdentityRef", "created_at"),
    ("CognitiveRoleContract", "created_at"),
    ("WorkMandate", "created_at"),
    ("WorkMandate", "expires_at"),
    ("BoundedContextEnvelope", "created_at"),
    ("BoundedContextEnvelope", "expires_at"),
    ("ToolObservation", "created_at"),
    ("ToolObservation", "observed_at"),
    ("CandidateAdvisory", "evaluated_at"),
    ("AdvisoryCandidateSet", "created_at"),
    ("ProposerAdvisory", "created_at"),
    ("ProposerAdvisory", "expires_at"),
    ("ProposerProcessStateTransition", "at"),
    ("ProposerProcessRecord", "created_at"),
    ("ProposerProcessRecord", "started_at"),
    ("ProposerProcessRecord", "completed_at"),
)

#: One complete-fixture builder per contract, so a C4 rejection could only ever be about
#: the naive value and never about a missing required field.
_CONTRACT_BUILDERS = {
    "AgentIdentityRef": _agent_identity_ref,
    "CognitiveRoleContract": _role_contract,
    "WorkMandate": _work_mandate,
    "BoundedContextEnvelope": _context_envelope,
    "ToolObservation": _tool_observation,
    "CandidateAdvisory": lambda **overrides: _candidate("cand-1", **overrides),
    "AdvisoryCandidateSet": _candidate_set,
    "ProposerAdvisory": _advisory,
    "ProposerProcessStateTransition": (
        lambda **overrides: _transition(ap.TerminalOutcome.ABSTAIN, **overrides)),
    "ProposerProcessRecord": _process_record,
}


def _naive_case(contract, field):
    """One C4 case: the complete fixture with ``field`` replaced by a naive instant."""
    return lambda: _CONTRACT_BUILDERS[contract](**{field: _NAIVE_INSTANT})


#: C4 requires **every** ``datetime`` field to be timezone-aware, enforced by an explicit
#: ``@field_validator``. One case per field rather than one case for the rule: the
#: requirement is stated of each field, and a single case would leave fifteen fields
#: unprobed. Every one of these now raises, so the registry lives in ``ENFORCED``.
_C4_ENFORCED_CASES = tuple(
    ("C4", f"{contract}.{field} rejects a naive datetime", _naive_case(contract, field))
    for contract, field in C4_DATETIME_FIELDS)

#: Every rule that remains locally decidable and unenforced. Today, exactly the one
#: entry ``_STATED_CASES`` carries — see the module docstring.
UNENFORCED = _STATED_CASES


@pytest.mark.parametrize("rule,description,construct",
                         UNENFORCED, ids=lambda v: str(v)[:60])
def test_the_shape_accepts_this_violation(rule, description, construct):
    """One violating instance per recorded rule, constructed rather than described.

    A rule listed in the enforcement documentation as unenforced must actually be
    unenforced, or the documentation understates what the guards establish. If this
    starts raising, the validator was implemented: delete the case and update
    ``docs/S1_ENFORCEMENT.md`` in the same change.

    **The instance is required, not merely the absence of a raise.** A construct that
    returned ``None`` — or that was quietly reduced to a no-op while its label stayed —
    would satisfy a bare "did not raise" and would credit this registry, and every
    derivation downstream of it, with a case that builds nothing. So the value is
    checked: each entry must hand back a live model, which is the only evidence that the
    violating shape was actually accepted.
    """
    pydantic = pytest.importorskip("pydantic")
    try:
        instance = construct()
    except pydantic.ValidationError as error:
        pytest.fail(
            f"{rule} is now enforced for: {description}. That is progress, not a "
            f"failure — delete this case and update the 'What the guards do not yet "
            f"establish' row in docs/S1_ENFORCEMENT.md in the same change. ({error})")
    assert isinstance(instance, pydantic.BaseModel), (
        f"{rule}'s construct for {description!r} returned {instance!r} rather than a "
        "model instance; a case that builds nothing is not evidence that the shape "
        "accepts the violation")


def test_the_c4_cases_cover_every_datetime_field_the_shapes_declare():
    """C4 is stated of **each** ``datetime`` field, so the case list must be exhaustive.

    ``C4_DATETIME_FIELDS`` is pinned so the headline count stays reviewable, and pinning
    is only safe while something checks the pin. This reads the representative shapes and
    requires exact agreement: a ``datetime`` field mirrored from Part D with no case fails
    here, and a case naming a field the shapes no longer declare fails here too.
    """
    import datetime as datetime_module

    pytest.importorskip("pydantic")
    shapes = _shapes()
    declared = {
        (name, field)
        for name, model in shapes.items()
        for field, info in model.model_fields.items()
        if info.annotation is datetime_module.datetime
    }
    assert set(C4_DATETIME_FIELDS) == declared, (
        f"pinned-only {sorted(set(C4_DATETIME_FIELDS) - declared)}, "
        f"shape-only {sorted(declared - set(C4_DATETIME_FIELDS))}; C4 applies to every "
        "datetime field, so the pinned list and the shapes must agree exactly")
    assert {contract for contract, _ in C4_DATETIME_FIELDS} <= set(_CONTRACT_BUILDERS), (
        "a C4 case names a contract with no complete-fixture builder")


#: The rules that are locally decidable and **are** enforced, paired with a construction
#: each must reject. Kept as a registry rather than as inline assertions so that
#: ``test_documentation_consistency.py`` can read which rules a test actually works with
#: instead of inferring it from a textual mention. Every entry here once lived in
#: ``UNENFORCED`` (or was original to this module); the discharge history is in
#: ``docs/S1_ENFORCEMENT.md``.
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

    ("L-1", "parent_advisory_digest equals this advisory's own advisory_digest",
     lambda: _advisory(advisory_digest=spec.PLACEHOLDER_DIGEST,
                       parent_advisory_digest=spec.PLACEHOLDER_DIGEST)),

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
    ("D3 purpose", "WorkMandate.purpose is not NFC",
     lambda: _work_mandate(purpose=_NON_NFC_PURPOSE)),
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
    ("R-3", "state_transitions has a backward transition",
     lambda: _process_record(state_transitions=[
         _transition(ap.ProposerProcessState.VALIDATED),
         _transition(ap.ProposerProcessState.RECEIVED)])),

    ("R-4", "terminal_outcome disagrees with the terminal state in state_transitions",
     lambda: _process_record(
         state_transitions=[_transition(ap.TerminalOutcome.ESCALATE)],
         terminal_outcome=ap.TerminalOutcome.ABSTAIN)),

    ("V13", "terminal_outcome=PROPOSAL is unreachable in S1",
     lambda: _process_record(terminal_outcome=ap.TerminalOutcome.PROPOSAL)),

    ("D8 completed_at", "ProposerProcessRecord.completed_at precedes started_at",
     lambda: _process_record(started_at=_LATER_INSTANT,
                             completed_at=spec.FIXED_INSTANT)),
) + _C4_ENFORCED_CASES


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
