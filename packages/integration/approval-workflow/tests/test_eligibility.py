"""Who may approve is a port, never an identity check.

The package refuses structurally — ineligible at the instant, a kind that may never
approve, the wrong role, the requester as sole approver — and it authenticates
nobody. Nothing here proves who anyone *is*; that stays with the IdP.
"""

from __future__ import annotations

import pytest

from ugence_approval_workflow import (
    ELIGIBLE_APPROVER_KINDS,
    ApproverEligibilityPort,
    ApproverKind,
    ApproverRef,
    ContractViolation,
    EligibilityDecision,
    EligibilityRefused,
    InMemoryApprovalWorkflowStore,
    ProductionModeRefused,
    ReviewDecision,
    StaticApproverEligibility,
    structural_refusals,
)

from _fixtures import (
    AI_APPROVER,
    APPROVER,
    REQUESTER,
    ROLE,
    SECOND_APPROVER,
    T0,
    T1,
    memory_store,
    subject,
    window,
)


def _pending(store):
    record = store.request_approval(subject(), requested_by=REQUESTER, required_role=ROLE,
                                    validity=window(), as_of=T0)
    store.present_for_decision(record.approval_id, as_of=T0)
    return record


def test_only_a_human_or_committee_may_ever_approve():
    assert ELIGIBLE_APPROVER_KINDS == frozenset({ApproverKind.HUMAN, ApproverKind.COMMITTEE})
    for kind in (ApproverKind.AI, ApproverKind.SERVICE, ApproverKind.DELEGATED_POLICY):
        assert kind not in ELIGIBLE_APPROVER_KINDS


def test_an_ai_principal_is_refused_even_when_the_directory_says_eligible():
    store = memory_store(APPROVER, AI_APPROVER)
    record = _pending(store)
    with pytest.raises(EligibilityRefused, match="AI may never approve"):
        store.decide(record.approval_id, approver=AI_APPROVER, decision=ReviewDecision.GRANT,
                     as_of=T1)
    store.close()


def test_the_requester_may_not_be_the_sole_approver():
    self_approver = ApproverRef(approver_id=REQUESTER, approver_kind=ApproverKind.HUMAN, role=ROLE)
    store = memory_store(self_approver)
    record = _pending(store)
    with pytest.raises(EligibilityRefused, match="sole approver"):
        store.decide(record.approval_id, approver=self_approver, decision=ReviewDecision.GRANT,
                     as_of=T1)
    store.close()


def test_an_approver_the_directory_does_not_report_is_refused():
    store = memory_store(APPROVER)
    record = _pending(store)
    stranger = ApproverRef(approver_id="approver-9", approver_kind=ApproverKind.HUMAN, role=ROLE)
    with pytest.raises(EligibilityRefused, match="not in the directory"):
        store.decide(record.approval_id, approver=stranger, decision=ReviewDecision.GRANT, as_of=T1)
    store.close()


def test_the_wrong_role_is_refused():
    other_role = ApproverRef(approver_id="approver-3", approver_kind=ApproverKind.HUMAN,
                             role="finance-approver")
    store = memory_store(APPROVER, other_role)
    record = _pending(store)
    with pytest.raises(EligibilityRefused):
        store.decide(record.approval_id, approver=other_role, decision=ReviewDecision.GRANT,
                     as_of=T1)
    store.close()


def test_structural_rules_hold_over_whatever_the_port_reports():
    eligible = EligibilityDecision(True)
    assert structural_refusals(approver=APPROVER, requested_by=REQUESTER, required_role=ROLE,
                               decision=eligible) == ()
    refused = structural_refusals(approver=AI_APPROVER, requested_by=REQUESTER, required_role=ROLE,
                                  decision=eligible)
    assert refused and "AI" in refused[0]
    # An ineligible port answer is carried through verbatim, never overridden.
    reasons = structural_refusals(approver=APPROVER, requested_by=REQUESTER, required_role=ROLE,
                                  decision=EligibilityDecision(False, ("leave of absence",)))
    assert "leave of absence" in reasons


def test_an_eligibility_decision_is_typed_not_a_bare_boolean():
    with pytest.raises(ValueError):
        EligibilityDecision(True, ("but also a reason",))
    with pytest.raises(ValueError):
        EligibilityDecision(False)


def test_the_port_is_required_at_construction_and_the_reference_one_is_not_production():
    with pytest.raises(ContractViolation):
        InMemoryApprovalWorkflowStore(object())  # type: ignore[arg-type]
    with pytest.raises(ProductionModeRefused):
        StaticApproverEligibility((), production_mode=True)
    assert isinstance(StaticApproverEligibility(()), ApproverEligibilityPort)


def test_the_package_never_authenticates():
    """No adapter offers an authentication surface; eligibility is all it asks for."""

    for cls in (StaticApproverEligibility, InMemoryApprovalWorkflowStore):
        names = {n for n in dir(cls) if not n.startswith("_")}
        assert not names & {"authenticate", "login", "verify_identity", "resolve_identity",
                            "issue_token", "credentials"}, cls.__name__
    surface = {n for n in dir(ApproverEligibilityPort) if not n.startswith("_")}
    assert surface == {"eligible_approvers", "is_eligible"}


def test_a_second_eligible_approver_may_decide_what_another_requested():
    store = memory_store(APPROVER, SECOND_APPROVER)
    record = _pending(store)
    decided = store.decide(record.approval_id, approver=SECOND_APPROVER,
                           decision=ReviewDecision.REJECT, as_of=T1)
    assert decided.decided_by == SECOND_APPROVER.approver_id
    store.close()
