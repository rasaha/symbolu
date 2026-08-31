"""RiskDecisionCase state machine legality + event emission (spec §8.3, AC-02)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_authority.domain import (
    IllegalTransitionError,
    RequestedCapabilities,
    RiskCaseState,
    RiskClass,
    RiskDecisionCase,
)

NOW = datetime(2026, 8, 10, tzinfo=timezone.utc)


def _case() -> RiskDecisionCase:
    return RiskDecisionCase(
        case_id="rdc_1",
        tenant_id="t",
        subject_id="a",
        model_id="m",
        purpose="p",
        domain="FINANCE",
        jurisdictions=("US",),
        requested=RequestedCapabilities(tools=("crm.read",), autonomy_level=1),
        workflow_ir_id="w",
        workflow_ir_version="1",
        workflow_ir_digest="sha256:x",
        created_at=NOW,
    )


def test_state_has_no_public_setter():
    case = _case()
    with pytest.raises(AttributeError):
        case.state = RiskCaseState.APPROVED  # type: ignore[misc]


def test_legal_happy_path():
    case = _case()
    case.classify(inherent=RiskClass.HIGH, residual=RiskClass.MEDIUM, actor="e", now=NOW)
    case.set_required_controls(("A",), actor="e", now=NOW)
    for target in (
        RiskCaseState.EVIDENCE_PENDING,
        RiskCaseState.EVIDENCE_COMPLETE,
        RiskCaseState.CONTROL_EVALUATED,
        RiskCaseState.AUTHORITY_REVIEW,
        RiskCaseState.APPROVED,
        RiskCaseState.ENVELOPE_ISSUED,
        RiskCaseState.ACTIVE,
    ):
        case.transition(target=target, actor="x", reason="step", now=NOW)
    assert case.state is RiskCaseState.ACTIVE


def test_cannot_skip_states():
    case = _case()
    with pytest.raises(IllegalTransitionError):
        case.transition(
            target=RiskCaseState.APPROVED, actor="x", reason="skip", now=NOW
        )


def test_cannot_issue_authority_before_review():
    # A case that has not reached AUTHORITY_REVIEW cannot go to APPROVED.
    case = _case()
    case.classify(inherent=RiskClass.LOW, residual=RiskClass.LOW, actor="e", now=NOW)
    with pytest.raises(IllegalTransitionError):
        case.transition(
            target=RiskCaseState.APPROVED, actor="x", reason="early", now=NOW
        )


def test_terminal_denied_has_no_successors():
    case = _case()
    case.classify(inherent=RiskClass.HIGH, residual=RiskClass.HIGH, actor="e", now=NOW)
    case.set_required_controls(("A",), actor="e", now=NOW)
    case.transition(target=RiskCaseState.EVIDENCE_PENDING, actor="x", reason="", now=NOW)
    case.transition(target=RiskCaseState.EVIDENCE_COMPLETE, actor="x", reason="", now=NOW)
    case.transition(target=RiskCaseState.CONTROL_EVALUATED, actor="x", reason="", now=NOW)
    case.transition(target=RiskCaseState.AUTHORITY_REVIEW, actor="x", reason="", now=NOW)
    case.transition(target=RiskCaseState.DENIED, actor="x", reason="deny", now=NOW)
    with pytest.raises(IllegalTransitionError):
        case.transition(
            target=RiskCaseState.ENVELOPE_ISSUED, actor="x", reason="", now=NOW
        )


def test_each_transition_emits_chained_event():
    case = _case()
    case.classify(inherent=RiskClass.HIGH, residual=RiskClass.MEDIUM, actor="e", now=NOW)
    case.set_required_controls(("A",), actor="e", now=NOW)
    assert len(case.events) == 2
    # Events chain via prev_digest.
    assert case.events[1].prev_digest == case.events[0].payload_digest
