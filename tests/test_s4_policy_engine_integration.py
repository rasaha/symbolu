"""
S4 Policy Engine Integration Tests
=====================================

Tests for Phase S4-safety: PolicyEngine promotion into governance.

Test categories:
1. Adapter contract — resolution shape, frozen, serialization
2. Deterministic behavior — same inputs → identical outputs
3. Fail-safe — no engine → allowed, no effect
4. Allow/deny logic — denylist, allowlist enforcement
5. Blackout windows — time-based blocking
6. Rate limiting — action count enforcement
7. Consumer-level — GovernanceService.authorize() uses policy engine
8. Regression — existing behavior unchanged when no engine configured
"""

from __future__ import annotations

import time
import pytest

from agentic.safety.governance_patterns.policy_engine import (
    AgentPolicy,
    BlackoutWindow,
    PolicyCheckResult,
    PolicyConfig,
    PolicyEngine,
)
from agentic.agentic_framework.signal_adapters.policy_engine_adapter import (
    AgentPolicyResolution,
    resolve_policy_check,
)


# =============================================================================
# 1. Adapter Contract Tests
# =============================================================================

class TestPolicyAdapterContract:
    """AgentPolicyResolution has correct shape and is frozen."""

    def test_resolution_is_frozen(self):
        res = resolve_policy_check(
            engine=PolicyEngine(),
            agent_id="agent-1",
            action_type="tool_execution",
        )
        with pytest.raises(AttributeError):
            res.allowed = False  # type: ignore[misc]

    def test_resolution_fields_present(self):
        res = resolve_policy_check(
            engine=PolicyEngine(),
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert hasattr(res, "allowed")
        assert hasattr(res, "hard_deny")
        assert hasattr(res, "violations")
        assert hasattr(res, "agent_id")
        assert hasattr(res, "action_type")
        assert hasattr(res, "reason_codes")
        assert hasattr(res, "available")
        assert hasattr(res, "source_detail")

    def test_to_audit_dict_serializable(self):
        res = resolve_policy_check(
            engine=PolicyEngine(),
            agent_id="agent-1",
            action_type="tool_execution",
        )
        d = res.to_audit_dict()
        assert isinstance(d, dict)
        assert "allowed" in d
        assert "violations" in d
        assert isinstance(d["violations"], list)
        for v in d.values():
            assert isinstance(v, (int, float, bool, str, list, type(None)))

    def test_available_when_engine_present(self):
        res = resolve_policy_check(
            engine=PolicyEngine(),
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert res.available is True

    def test_unavailable_when_no_engine(self):
        res = resolve_policy_check(
            engine=None,
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert res.available is False


# =============================================================================
# 2. Determinism Tests
# =============================================================================

class TestPolicyDeterminism:
    """Same inputs produce identical outputs."""

    def test_deterministic_100_runs(self):
        engine = PolicyEngine()
        results = []
        for _ in range(100):
            res = resolve_policy_check(
                engine=engine,
                agent_id="agent-1",
                action_type="tool_execution",
                current_time=1000000.0,
            )
            results.append((res.allowed, res.hard_deny, res.violations))
        assert len(set(results)) == 1


# =============================================================================
# 3. Fail-Safe Tests
# =============================================================================

class TestPolicyFailSafe:
    """No engine → allowed, no effect."""

    def test_no_engine_allowed(self):
        res = resolve_policy_check(
            engine=None,
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert res.allowed is True
        assert res.hard_deny is False
        assert res.available is False
        assert len(res.violations) == 0

    def test_default_policy_allows_all(self):
        """Default PolicyEngine (no rules) allows everything."""
        engine = PolicyEngine()
        res = resolve_policy_check(
            engine=engine,
            agent_id="any-agent",
            action_type="any_action",
        )
        assert res.allowed is True
        assert res.hard_deny is False


# =============================================================================
# 4. Allow/Deny Logic Tests
# =============================================================================

class TestPolicyAllowDeny:
    """Denylist and allowlist enforcement."""

    def test_denied_action_hard_denies(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(
                denied_actions=("dangerous_action",),
            ),
        )
        engine = PolicyEngine(config)
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="dangerous_action",
        )
        assert res.allowed is False
        assert res.hard_deny is True
        assert len(res.violations) > 0
        assert "AGENT_POLICY_DENY" in res.reason_codes

    def test_allowed_action_passes(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(
                denied_actions=("dangerous_action",),
            ),
        )
        engine = PolicyEngine(config)
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="safe_action",
        )
        assert res.allowed is True
        assert res.hard_deny is False

    def test_allowlist_blocks_unlisted(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(
                allowed_actions=("read_file", "list_files"),
            ),
        )
        engine = PolicyEngine(config)
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="delete_file",
        )
        assert res.allowed is False
        assert res.hard_deny is True

    def test_allowlist_permits_listed(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(
                allowed_actions=("read_file", "list_files"),
            ),
        )
        engine = PolicyEngine(config)
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="read_file",
        )
        assert res.allowed is True

    def test_per_agent_override(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(),  # allow all by default
            agent_overrides={
                "restricted-agent": AgentPolicy(
                    denied_actions=("write_file",),
                ),
            },
        )
        engine = PolicyEngine(config)

        # Default agent can write
        res_default = resolve_policy_check(
            engine=engine,
            agent_id="normal-agent",
            action_type="write_file",
        )
        assert res_default.allowed is True

        # Restricted agent cannot write
        res_restricted = resolve_policy_check(
            engine=engine,
            agent_id="restricted-agent",
            action_type="write_file",
        )
        assert res_restricted.allowed is False
        assert res_restricted.hard_deny is True


# =============================================================================
# 5. Blackout Window Tests
# =============================================================================

class TestPolicyBlackout:
    """Time-based action blocking."""

    def test_blackout_blocks_during_window(self):
        import datetime as _dt

        # Create a blackout window for hour 10-12
        config = PolicyConfig(
            default_policy=AgentPolicy(
                blackout_windows=(
                    BlackoutWindow(
                        start_hour=10,
                        end_hour=12,
                        reason="maintenance window",
                    ),
                ),
            ),
        )
        engine = PolicyEngine(config)

        # Time at hour 11 UTC
        dt_in = _dt.datetime(2026, 4, 4, 11, 0, tzinfo=_dt.timezone.utc)
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="tool_execution",
            current_time=dt_in.timestamp(),
        )
        assert res.allowed is False
        assert res.hard_deny is True
        assert any("blackout" in v for v in res.violations)

    def test_blackout_allows_outside_window(self):
        import datetime as _dt

        config = PolicyConfig(
            default_policy=AgentPolicy(
                blackout_windows=(
                    BlackoutWindow(start_hour=10, end_hour=12),
                ),
            ),
        )
        engine = PolicyEngine(config)

        # Time at hour 8 UTC (outside window)
        dt_out = _dt.datetime(2026, 4, 4, 8, 0, tzinfo=_dt.timezone.utc)
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="tool_execution",
            current_time=dt_out.timestamp(),
        )
        assert res.allowed is True


# =============================================================================
# 6. Rate Limiting Tests
# =============================================================================

class TestPolicyRateLimit:
    """Action count enforcement."""

    def test_rate_limit_blocks_after_max(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(
                max_actions_per_window=3,
                rate_limit_window_seconds=60.0,
            ),
        )
        engine = PolicyEngine(config)
        now = 1000000.0

        # Record 3 actions
        for i in range(3):
            engine.record_action("agent-1", "tool_execution", timestamp=now + i)

        # 4th should be blocked
        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="tool_execution",
            current_time=now + 10,
        )
        assert res.allowed is False
        assert res.hard_deny is True
        assert any("rate limit" in v for v in res.violations)

    def test_rate_limit_allows_within_limit(self):
        config = PolicyConfig(
            default_policy=AgentPolicy(
                max_actions_per_window=5,
                rate_limit_window_seconds=60.0,
            ),
        )
        engine = PolicyEngine(config)
        now = 1000000.0

        # Record 2 actions (well under limit)
        engine.record_action("agent-1", "tool_execution", timestamp=now)
        engine.record_action("agent-1", "tool_execution", timestamp=now + 1)

        res = resolve_policy_check(
            engine=engine,
            agent_id="agent-1",
            action_type="tool_execution",
            current_time=now + 10,
        )
        assert res.allowed is True


# =============================================================================
# 7. Consumer-Level Tests: GovernanceService.authorize()
# =============================================================================

class TestPolicyGovernanceConsumer:
    """GovernanceService.authorize() uses policy engine."""

    def test_authorize_no_engine_no_effect(self):
        """Without engine, authorize works normally (no policy audit)."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()  # no agent_policy_engine
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test no policy",
        )

        response = service.authorize(request)
        assert response is not None
        snapshot = response.audit_event.request_snapshot
        assert snapshot["agent_policy_available"] is False
        assert snapshot["agent_policy_allowed"] is True
        assert snapshot["agent_policy_hard_deny"] is False

    def test_authorize_with_engine_allows(self):
        """Engine configured, action allowed → normal governance."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        engine = PolicyEngine()  # default: allow all
        service = GovernanceService(agent_policy_engine=engine)
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test policy allows",
        )

        response = service.authorize(request)
        snapshot = response.audit_event.request_snapshot
        assert snapshot["agent_policy_available"] is True
        assert snapshot["agent_policy_allowed"] is True
        assert snapshot["agent_policy_hard_deny"] is False

        # Structured audit dict present
        assert response.audit_event.agent_policy is not None
        assert response.audit_event.agent_policy["allowed"] is True

    def test_authorize_with_engine_denies(self):
        """Engine configured, action denied → hard DENY override."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        config = PolicyConfig(
            default_policy=AgentPolicy(
                denied_actions=("dangerous_action",),
            ),
        )
        engine = PolicyEngine(config)
        service = GovernanceService(agent_policy_engine=engine)

        request = AuthorizationRequest(
            action_type="dangerous_action",
            actor_id="test-actor",
            confidence_score=0.9,  # high confidence, but policy denies
            context_summary="test policy denies",
        )

        response = service.authorize(request)
        assert response.governance_decision == "DENY"
        assert response.eligible is False

        snapshot = response.audit_event.request_snapshot
        assert snapshot["agent_policy_available"] is True
        assert snapshot["agent_policy_allowed"] is False
        assert snapshot["agent_policy_hard_deny"] is True
        assert len(snapshot["agent_policy_violations"]) > 0

    def test_authorize_per_agent_policy(self):
        """Per-agent overrides work through governance."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        config = PolicyConfig(
            default_policy=AgentPolicy(),  # allow all
            agent_overrides={
                "restricted-agent": AgentPolicy(
                    denied_actions=("write_file",),
                ),
            },
        )
        engine = PolicyEngine(config)
        service = GovernanceService(agent_policy_engine=engine)

        # Normal agent: allowed
        req_normal = AuthorizationRequest(
            action_type="write_file",
            actor_id="normal-agent",
            confidence_score=0.8,
            context_summary="normal agent writes",
        )
        resp_normal = service.authorize(req_normal)
        assert resp_normal.audit_event.request_snapshot["agent_policy_allowed"] is True

        # Restricted agent: denied
        req_restricted = AuthorizationRequest(
            action_type="write_file",
            actor_id="restricted-agent",
            confidence_score=0.8,
            context_summary="restricted agent writes",
        )
        resp_restricted = service.authorize(req_restricted)
        assert resp_restricted.governance_decision == "DENY"
        assert resp_restricted.audit_event.request_snapshot["agent_policy_allowed"] is False

    def test_authorize_policy_deny_overrides_high_confidence(self):
        """Policy deny takes effect even with very high confidence."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        config = PolicyConfig(
            default_policy=AgentPolicy(
                denied_actions=("forbidden_action",),
            ),
        )
        engine = PolicyEngine(config)
        service = GovernanceService(agent_policy_engine=engine)

        request = AuthorizationRequest(
            action_type="forbidden_action",
            actor_id="test-actor",
            confidence_score=1.0,  # maximum confidence
            context_summary="high confidence but policy forbids",
        )

        response = service.authorize(request)
        assert response.governance_decision == "DENY"
        assert response.eligible is False
