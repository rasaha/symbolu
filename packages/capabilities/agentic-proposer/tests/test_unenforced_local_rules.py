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
no verifier, no second contract, no supplied observation collection. R-5, R-6, R-7, R-9
and R-10 are therefore absent by construction: each compares two contracts. R-2 is absent:
it calls ``evaluate_readiness``. Most of R-1b is absent for the same reason — it resolves
the referenced ``AdvisoryCandidateSet`` — but clauses (v) and (vi) became locally
decidable when OD-4(a) nested the candidates inside the advisory, and those two halves are
here.

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


def _candidate(candidate_id):
    return _shapes()["CandidateAdvisory"](**spec.complete_candidate(candidate_id))


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


def test_the_two_validators_the_mirror_does_declare_still_hold():
    """The other side of the asymmetry, so this module is discriminating rather than a
    list of things that happen not to raise.

    C7 and R-1a **are** declared, and they reject. If they did not, every case above
    would be unremarkable and this module would prove nothing about the mirror.
    """
    pydantic = pytest.importorskip("pydantic")
    with pytest.raises(pydantic.ValidationError):
        _shapes()["CandidateAdvisory"](**{
            **spec.complete_candidate(),
            "domain_check_completion": spec.DomainCheckCompletion.COMPLETE})
    with pytest.raises(pydantic.ValidationError):
        _advisory(selected_candidate_id="cand-1")
    with pytest.raises(pydantic.ValidationError):
        _advisory(recommended_disposition=ap.CandidateDisposition.RECOMMEND_WITHHOLD)


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
