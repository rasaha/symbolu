"""RA-6 driven case-state transitions (§11, §14).

ACTIVE → {EXPIRED, REVOKED, SUPERSEDED} using the leaf's guarded state machine
and existing event types. No reactivation from a terminal state (I4).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

import ra6_scenario as C
from risk_authority.domain.enums import GovernanceEventType, RiskCaseState
from risk_authority.domain.errors import IllegalTransitionError
from risk_authority.domain.risk_case import RequestedCapabilities, RiskDecisionCase
from risk_authority.services.revocation import RevocationState
from ugence_risk_authority_status_runtime import (
    expire_case_if_elapsed,
    reconcile_case_state,
    revoke_case,
    supersede_case,
)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _active_case() -> RiskDecisionCase:
    case = RiskDecisionCase(
        case_id="rdc_1", tenant_id="t", subject_id="a", model_id="m",
        purpose="p", domain="d", jurisdictions=("US",),
        requested=RequestedCapabilities(), workflow_ir_id="w",
        workflow_ir_version="1", workflow_ir_digest="dg", created_at=NOW,
        state=RiskCaseState.ACTIVE,
    )
    return case


def test_expire_transition():
    case = _active_case()
    ev = expire_case_if_elapsed(
        case, expires_at=NOW, now=NOW + timedelta(seconds=1)
    )
    assert case.state is RiskCaseState.EXPIRED
    assert ev.event_type is GovernanceEventType.CASE_STATE_CHANGED


def test_expire_noop_before_deadline():
    case = _active_case()
    ev = expire_case_if_elapsed(case, expires_at=NOW + timedelta(hours=1), now=NOW)
    assert ev is None and case.state is RiskCaseState.ACTIVE


def test_revoke_transition_emits_envelope_revoked():
    case = _active_case()
    ev = revoke_case(case, now=NOW, reason="policy breach", actor="gov")
    assert case.state is RiskCaseState.REVOKED
    assert ev.event_type is GovernanceEventType.ENVELOPE_REVOKED


def test_supersede_transition():
    case = _active_case()
    ev = supersede_case(case, now=NOW, reason="reissued", actor="ra")
    assert case.state is RiskCaseState.SUPERSEDED
    assert ev.event_type is GovernanceEventType.CASE_STATE_CHANGED


def test_terminal_state_never_reactivates():
    case = _active_case()
    revoke_case(case, now=NOW, reason="r", actor="gov")
    # No successor from REVOKED — an attempt to drive it back raises (I4).
    with pytest.raises(IllegalTransitionError):
        case.transition(
            target=RiskCaseState.ACTIVE, actor="x", reason="revive", now=NOW
        )


def test_reconcile_expiry_precedes_revocation():
    h = C.build()
    case = _active_case()
    rs = RevocationState()
    # both expired AND revoked; expiry wins by precedence
    rs.revoke_envelope(h.envelope.envelope_id)
    ev = reconcile_case_state(
        case, envelope=h.envelope, revocation_state=rs,
        now=h.envelope.expires_at + timedelta(seconds=1),
    )
    assert case.state is RiskCaseState.EXPIRED


def test_reconcile_revocation_when_not_expired():
    h = C.build()
    case = _active_case()
    rs = RevocationState()
    rs.revoke_subject(h.envelope.tenant_id, h.envelope.subject)
    ev = reconcile_case_state(
        case, envelope=h.envelope, revocation_state=rs, now=h.now
    )
    assert case.state is RiskCaseState.REVOKED


def test_reconcile_noop_when_valid():
    h = C.build()
    case = _active_case()
    ev = reconcile_case_state(
        case, envelope=h.envelope, revocation_state=RevocationState(), now=h.now
    )
    assert ev is None and case.state is RiskCaseState.ACTIVE


def test_reconcile_terminal_case_is_noop():
    h = C.build()
    case = _active_case()
    revoke_case(case, now=h.now, reason="r", actor="g")
    ev = reconcile_case_state(
        case, envelope=h.envelope, revocation_state=RevocationState(), now=h.now
    )
    assert ev is None and case.state is RiskCaseState.REVOKED
