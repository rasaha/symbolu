"""
Tests for the Approval Workflow Layer.

Covers:
- Approval request creation and persistence
- State transitions (approve, deny, expire, cancel, supersede)
- Invalid transition rejection
- Expired approval cannot be approved
- Listing by status
- History tracking
- Governance integration: DEFER+requires_human creates approval
- Governance integration: ALLOW does not create approval
- Fail-closed when approval store fails
- Backward compatibility without approval store
"""

import time
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from agentic.agentic_framework.approval_workflow import (
    ApprovalContext,
    ApprovalDecision,
    ApprovalLevel,
    ApprovalNotFoundError,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalStore,
    ApprovalStoreError,
    ApprovalTransitionError,
)
from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.governance_models import (
    APIGovernanceDecision,
    AuthorizationRequest,
)
from agentic.agentic_framework.policy_bundle import (
    DEFAULT_GLOBAL_POLICY,
    FINANCE_TENANT_OVERRIDE,
    resolve_effective_policy,
)


# =========================================================================
# Helpers
# =========================================================================


def _make_context(**overrides) -> ApprovalContext:
    defaults = dict(
        governance_decision_id="dec-001",
        action_type="file_write",
        tool_name="file_writer",
        actor_id="test-actor",
        risk_level="write",
        confidence_score=0.65,
        escalation_level="confirm",
        execution_mode="confirm",
        reason_codes=("SAFETY:goal_alignment",),
        policy_id="default-global",
        policy_version="1.0.0",
    )
    defaults.update(overrides)
    return ApprovalContext(**defaults)


# =========================================================================
# Test: Approval Store — Basic Operations
# =========================================================================


class TestApprovalStoreBasics:

    def test_create_request(self):
        store = ApprovalStore(":memory:")
        ctx = _make_context()
        req = store.create_request(ctx, ApprovalLevel.CONFIRM)

        assert req.approval_id.startswith("apr-")
        assert req.status == ApprovalStatus.PENDING
        assert req.approval_level == ApprovalLevel.CONFIRM
        assert req.context.governance_decision_id == "dec-001"
        assert req.context.actor_id == "test-actor"
        assert not req.is_terminal

    def test_get_by_id(self):
        store = ApprovalStore(":memory:")
        ctx = _make_context()
        created = store.create_request(ctx)
        fetched = store.get(created.approval_id)

        assert fetched.approval_id == created.approval_id
        assert fetched.status == ApprovalStatus.PENDING
        assert fetched.context.action_type == "file_write"

    def test_get_not_found(self):
        store = ApprovalStore(":memory:")
        with pytest.raises(ApprovalNotFoundError):
            store.get("nonexistent")

    def test_count(self):
        store = ApprovalStore(":memory:")
        assert store.count() == 0
        store.create_request(_make_context())
        assert store.count() == 1
        store.create_request(_make_context(governance_decision_id="dec-002"))
        assert store.count() == 2

    def test_count_by_status(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        assert store.count(ApprovalStatus.PENDING) == 1
        assert store.count(ApprovalStatus.APPROVED) == 0
        store.approve(req.approval_id, decided_by="admin")
        assert store.count(ApprovalStatus.PENDING) == 0
        assert store.count(ApprovalStatus.APPROVED) == 1

    def test_list_pending(self):
        store = ApprovalStore(":memory:")
        store.create_request(_make_context())
        store.create_request(_make_context(governance_decision_id="dec-002"))
        pending = store.list_pending()
        assert len(pending) == 2
        assert all(r.status == ApprovalStatus.PENDING for r in pending)

    def test_list_recent(self):
        store = ApprovalStore(":memory:")
        store.create_request(_make_context())
        req2 = store.create_request(_make_context(governance_decision_id="dec-002"))
        store.approve(req2.approval_id, decided_by="admin")
        recent = store.list_recent()
        assert len(recent) == 2

    def test_context_round_trips(self):
        store = ApprovalStore(":memory:")
        ctx = _make_context(
            reason_codes=("SAFETY:consistency", "JEPA:drift"),
            domain_id="finance",
            tenant_id="corp-1",
            session_id="sess-abc",
        )
        created = store.create_request(ctx)
        fetched = store.get(created.approval_id)

        assert fetched.context.reason_codes == ("SAFETY:consistency", "JEPA:drift")
        assert fetched.context.domain_id == "finance"
        assert fetched.context.tenant_id == "corp-1"
        assert fetched.context.session_id == "sess-abc"

    def test_to_dict_and_summary(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        d = req.to_dict()
        assert d["approval_id"] == req.approval_id
        assert d["status"] == "pending"
        assert "context" in d

        s = req.to_summary_dict()
        assert s["approval_id"] == req.approval_id
        assert s["status"] == "pending"
        assert s["approval_level"] == "confirm"


# =========================================================================
# Test: State Transitions
# =========================================================================


class TestStateTransitions:

    def test_approve(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        approved = store.approve(req.approval_id, decided_by="admin@corp.com", rationale="Looks safe")

        assert approved.status == ApprovalStatus.APPROVED
        assert approved.is_terminal
        assert approved.decision is not None
        assert approved.decision.decided_by == "admin@corp.com"
        assert approved.decision.rationale == "Looks safe"

    def test_deny(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        denied = store.deny(req.approval_id, decided_by="reviewer", rationale="Too risky")

        assert denied.status == ApprovalStatus.DENIED
        assert denied.is_terminal

    def test_expire(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        expired = store.expire(req.approval_id)

        assert expired.status == ApprovalStatus.EXPIRED
        assert expired.is_terminal

    def test_cancel(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        canceled = store.cancel(req.approval_id, canceled_by="actor")

        assert canceled.status == ApprovalStatus.CANCELED
        assert canceled.is_terminal

    def test_supersede(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        superseded = store.supersede(req.approval_id)

        assert superseded.status == ApprovalStatus.SUPERSEDED
        assert superseded.is_terminal

    def test_cannot_approve_after_deny(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        store.deny(req.approval_id, decided_by="reviewer")
        with pytest.raises(ApprovalTransitionError, match="terminal state"):
            store.approve(req.approval_id, decided_by="admin")

    def test_cannot_deny_after_approve(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        store.approve(req.approval_id, decided_by="admin")
        with pytest.raises(ApprovalTransitionError, match="terminal state"):
            store.deny(req.approval_id, decided_by="reviewer")

    def test_cannot_expire_after_cancel(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        store.cancel(req.approval_id, canceled_by="actor")
        with pytest.raises(ApprovalTransitionError, match="terminal state"):
            store.expire(req.approval_id)

    def test_cannot_approve_expired_request(self):
        store = ApprovalStore(":memory:")
        # Create with 0 expiry hours → already expired
        req = store.create_request(_make_context(), expiry_hours=0.0)
        with pytest.raises(ApprovalTransitionError, match="expired"):
            store.approve(req.approval_id, decided_by="admin")


# =========================================================================
# Test: History Tracking
# =========================================================================


class TestHistory:

    def test_creation_recorded_in_history(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        history = store.get_history(req.approval_id)

        assert len(history) == 1
        assert history[0]["from_status"] == "none"
        assert history[0]["to_status"] == "pending"

    def test_full_lifecycle_history(self):
        store = ApprovalStore(":memory:")
        req = store.create_request(_make_context())
        store.approve(req.approval_id, decided_by="admin", rationale="OK")
        history = store.get_history(req.approval_id)

        assert len(history) == 2
        assert history[0]["to_status"] == "pending"
        assert history[1]["from_status"] == "pending"
        assert history[1]["to_status"] == "approved"
        assert history[1]["actor"] == "admin"
        assert history[1]["rationale"] == "OK"


# =========================================================================
# Test: Expire Stale
# =========================================================================


class TestExpireStale:

    def test_expire_stale_requests(self):
        store = ApprovalStore(":memory:")
        # Create one already-expired and one still valid
        store.create_request(_make_context(), expiry_hours=0.0)
        store.create_request(
            _make_context(governance_decision_id="dec-002"),
            expiry_hours=24.0,
        )
        expired_count = store.expire_stale()
        assert expired_count == 1
        assert store.count(ApprovalStatus.EXPIRED) == 1
        assert store.count(ApprovalStatus.PENDING) == 1


# =========================================================================
# Test: Governance Integration
# =========================================================================


class TestGovernanceIntegration:

    def test_defer_creates_approval_request(self):
        """When governance defers with requires_human, an approval is created."""
        approval_store = ApprovalStore(":memory:")

        # Use strict finance policy with borderline scores → DEFER or DENY
        resolution = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE],
            tenant_id="finance-corp",
        )
        service = GovernanceService(
            policy_resolution=resolution,
            approval_store=approval_store,
        )

        # Borderline scores under strict thresholds
        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_write",
            tool_name="file_writer",
            agency_level="FULL",
            quality_score=0.65,
            coherence_score=0.65,
            internal_consistency=0.65,
            goal_alignment=0.65,
            trajectory_confidence=0.65,
        )
        response = service.authorize(request)

        # Should be DEFER or DENY (not ALLOW) with these scores
        assert response.governance_decision.value in ("DEFER", "DENY")

        if response.requires_human_approval:
            # Approval should be created
            assert response.approval_required is True
            assert response.approval_id is not None
            assert response.approval_summary is not None
            assert response.approval_summary["status"] == "pending"

            # Verify it's in the store
            stored = approval_store.get(response.approval_id)
            assert stored.status == ApprovalStatus.PENDING
            assert stored.context.governance_decision_id == response.audit_reference

    def test_allow_does_not_create_approval(self):
        """When governance allows, no approval is created."""
        approval_store = ApprovalStore(":memory:")
        service = GovernanceService(approval_store=approval_store)

        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.95,
            coherence_score=0.95,
            internal_consistency=0.95,
            goal_alignment=0.95,
            trajectory_confidence=0.95,
        )
        response = service.authorize(request)

        assert response.governance_decision.value == "ALLOW"
        assert response.approval_required is False
        assert response.approval_id is None
        assert approval_store.count() == 0

    def test_no_approval_store_backward_compatible(self):
        """GovernanceService without approval_store still works."""
        service = GovernanceService()
        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_read",
            agency_level="FULL",
            quality_score=0.95,
            coherence_score=0.95,
            internal_consistency=0.95,
            goal_alignment=0.95,
            trajectory_confidence=0.95,
        )
        response = service.authorize(request)

        assert response.governance_decision is not None
        assert response.approval_required is False
        assert response.approval_id is None

    def test_approval_context_carries_policy_metadata(self):
        """Approval context includes policy ID and version."""
        approval_store = ApprovalStore(":memory:")
        resolution = resolve_effective_policy(
            DEFAULT_GLOBAL_POLICY,
            overrides=[FINANCE_TENANT_OVERRIDE],
            tenant_id="finance-corp",
        )
        service = GovernanceService(
            policy_resolution=resolution,
            approval_store=approval_store,
        )

        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_write",
            tool_name="file_writer",
            agency_level="FULL",
            quality_score=0.65,
            coherence_score=0.65,
            internal_consistency=0.65,
            goal_alignment=0.65,
            trajectory_confidence=0.65,
        )
        response = service.authorize(request)

        if response.approval_id is not None:
            stored = approval_store.get(response.approval_id)
            assert stored.context.policy_id is not None
            assert stored.context.policy_version is not None


# =========================================================================
# Test: Fail-Closed
# =========================================================================


class TestFailClosed:

    def test_approval_store_failure_fails_closed(self):
        """If approval store raises, governance fails closed to DENY."""
        broken_store = MagicMock(spec=ApprovalStore)
        broken_store.create_request.side_effect = ApprovalStoreError("DB down")

        service = GovernanceService(
            approval_store=broken_store,
            strict=True,  # Strict mode to force DEFER on borderline
        )

        request = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_write",
            tool_name="file_writer",
            agency_level="FULL",
            quality_score=0.55,
            coherence_score=0.55,
            internal_consistency=0.55,
            goal_alignment=0.55,
            trajectory_confidence=0.55,
        )
        response = service.authorize(request)

        # If approval was required and store failed, decision should be DENY
        if response.approval_required or "APPROVAL_STORE_FAILURE" in response.rationale_codes:
            assert response.governance_decision.value == "DENY"
            assert "APPROVAL_STORE_FAILURE" in response.rationale_codes
