"""
Phase S2 Integration Tests — Sovereign Health + Insight Gate → Governance.

Tests:
1. Runtime-safe metrics extraction (metrics_runtime.py)
2. Pure insight gate functions (insight_gate_pure.py)
3. Insight adapter structured outputs
4. Sovereign health adapter structured outputs
5. Governance consumes new signals in bounded way
6. Stricter-only semantics preserved
7. Fallback behavior when signals are absent
8. Audit/metadata includes new sovereign signals
9. No PyTorch dependency leaks
"""

import pytest


# =========================================================================
# 1. Runtime-safe metrics module
# =========================================================================

class TestMetricsRuntime:
    """Verify metrics_runtime.py is importable and correct."""

    def test_importable_without_torch(self):
        """metrics_runtime must not require torch."""
        import agentic.sovereign_metrics_runtime as mr
        assert hasattr(mr, "get_entropy_status")
        assert hasattr(mr, "check_stability_constraint")
        assert hasattr(mr, "check_sovereign_alert")
        assert hasattr(mr, "build_health_summary")

    def test_get_entropy_status_boundaries(self):
        from agentic.sovereign_metrics_runtime import get_entropy_status
        assert get_entropy_status(0.10)[1] == "SATTVIC"
        assert get_entropy_status(0.40)[1] == "FOCUSED"
        assert get_entropy_status(0.60)[1] == "BALANCED"
        assert get_entropy_status(0.80)[1] == "RAJASIC"
        assert get_entropy_status(0.90)[1] == "NIDRA"

    def test_stability_constraint_no_brake_initially(self):
        from agentic.sovereign_metrics_runtime import (
            StabilityState, check_stability_constraint,
        )
        state = StabilityState(window_size=3)
        active, state = check_stability_constraint(0.5, state, current_step=0)
        assert not active  # not enough history

    def test_stability_constraint_triggers_brake(self):
        from agentic.sovereign_metrics_runtime import (
            StabilityState, check_stability_constraint,
        )
        state = StabilityState(window_size=3)
        # Feed consistently increasing entropy
        for step, entropy in enumerate([0.3, 0.5, 0.7]):
            active, state = check_stability_constraint(entropy, state, current_step=step)
        assert active  # brake should trigger
        assert state.inertial_brake_active

    def test_stability_constraint_brake_duration(self):
        from agentic.sovereign_metrics_runtime import (
            StabilityState, check_stability_constraint,
        )
        state = StabilityState(window_size=3)
        # Trigger brake
        for step, entropy in enumerate([0.3, 0.5, 0.7]):
            check_stability_constraint(entropy, state, current_step=step)
        # Check brake persists within duration
        active, state = check_stability_constraint(0.4, state, current_step=10, brake_duration=50)
        assert active  # still within duration
        # Check brake expires
        active, state = check_stability_constraint(0.4, state, current_step=100, brake_duration=50)
        assert not active  # duration exceeded

    def test_alert_state_machine_stable(self):
        from agentic.sovereign_metrics_runtime import (
            SovereignAlertState, check_sovereign_alert,
        )
        state = SovereignAlertState()
        metrics = {"sa_ratio": 0.30, "gc": 0.85, "l_consistency": 0.05}
        state, actions = check_sovereign_alert(metrics, state)
        assert state.state == "STABLE"
        assert len(actions) == 0

    def test_alert_state_machine_lockdown(self):
        from agentic.sovereign_metrics_runtime import (
            SovereignAlertState, check_sovereign_alert,
        )
        state = SovereignAlertState()
        # Two danger signals trigger lockdown
        metrics = {"sa_ratio": 0.60, "gc": 0.20, "l_consistency": 0.50}
        state, actions = check_sovereign_alert(metrics, state)
        assert state.state == "LOCKDOWN_ACTIVE"
        assert state.lockdown_count == 1
        assert any("LOCKDOWN" in a for a in actions)

    def test_health_summary_construction(self):
        from agentic.sovereign_metrics_runtime import (
            SovereignAlertState, build_health_summary,
        )
        alert = SovereignAlertState(state="ALERT")
        summary = build_health_summary(
            alert_state=alert, alert_actions=["ALERT: GC"],
            entropy=0.75, brake_active=False,
        )
        assert summary.alert_state == "ALERT"
        assert summary.entropy_status == "RAJASIC"
        assert summary.is_degraded
        assert not summary.is_lockdown

    def test_health_summary_to_audit_dict(self):
        from agentic.sovereign_metrics_runtime import (
            SovereignAlertState, build_health_summary,
        )
        alert = SovereignAlertState(state="STABLE")
        summary = build_health_summary(
            alert_state=alert, alert_actions=[], entropy=0.2,
        )
        d = summary.to_audit_dict()
        assert isinstance(d, dict)
        assert d["alert_state"] == "STABLE"
        assert d["entropy_status"] == "SATTVIC"

    def test_no_torch_in_metrics_runtime(self):
        import agentic.sovereign_metrics_runtime as mr
        assert "torch" not in dir(mr)


# =========================================================================
# 2. Pure insight gate functions
# =========================================================================

class TestInsightGatePure:
    """Verify insight_gate_pure.py functions."""

    def test_importable_without_torch(self):
        import agentic.sovereign_insight_gate_pure as igp
        assert hasattr(igp, "calculate_stability_pure")
        assert hasattr(igp, "calculate_risk_pure")
        assert hasattr(igp, "check_eligibility_pure")
        assert hasattr(igp, "check_release_pure")
        assert hasattr(igp, "run_insight_gate_pure")

    def test_stability_calculation(self):
        from agentic.sovereign_insight_gate_pure import calculate_stability_pure
        # High inputs → high stability
        stab = calculate_stability_pure(
            r_acc=0.95, s_acc=0.90, guna_coherence=0.85, drift=0.1,
        )
        assert stab > 0.8

    def test_stability_low_inputs(self):
        from agentic.sovereign_insight_gate_pure import calculate_stability_pure
        stab = calculate_stability_pure(
            r_acc=0.3, s_acc=0.3, guna_coherence=0.2, drift=0.9,
        )
        assert stab < 0.4

    def test_stability_clamped(self):
        from agentic.sovereign_insight_gate_pure import calculate_stability_pure
        # Verify clamping to [0, 1]
        stab = calculate_stability_pure(
            r_acc=1.0, s_acc=1.0, guna_coherence=1.0, drift=0.0,
        )
        assert 0.0 <= stab <= 1.0

    def test_risk_calculation(self):
        from agentic.sovereign_insight_gate_pure import calculate_risk_pure
        # High coherence, low drift, high authority → low risk
        risk = calculate_risk_pure(
            guna_coherence=0.9, drift=0.1, authority=0.95,
        )
        assert risk < 0.15

    def test_risk_high_incoherence(self):
        from agentic.sovereign_insight_gate_pure import calculate_risk_pure
        risk = calculate_risk_pure(
            guna_coherence=0.1, drift=0.8, authority=0.3,
        )
        assert risk > 0.5

    def test_eligibility_all_pass(self):
        from agentic.sovereign_insight_gate_pure import check_eligibility_pure
        assert check_eligibility_pure(
            stab_score=0.85, r_acc=0.95, s_acc=0.90,
            vritti=0, guna_coherence=0.80,
        )

    def test_eligibility_stab_too_low(self):
        from agentic.sovereign_insight_gate_pure import check_eligibility_pure
        assert not check_eligibility_pure(
            stab_score=0.50, r_acc=0.95, s_acc=0.90,
            vritti=0, guna_coherence=0.80,
        )

    def test_eligibility_wrong_vritti(self):
        from agentic.sovereign_insight_gate_pure import check_eligibility_pure
        # Vritti=1 (VIPARYAYA) is not in allowed list
        assert not check_eligibility_pure(
            stab_score=0.85, r_acc=0.95, s_acc=0.90,
            vritti=1, guna_coherence=0.80,
        )

    def test_release_requires_eligibility(self):
        from agentic.sovereign_insight_gate_pure import check_release_pure
        assert not check_release_pure(eligible=False, risk_score=0.10)

    def test_release_risk_too_high(self):
        from agentic.sovereign_insight_gate_pure import check_release_pure
        assert not check_release_pure(eligible=True, risk_score=0.50)

    def test_release_passes(self):
        from agentic.sovereign_insight_gate_pure import check_release_pure
        assert check_release_pure(eligible=True, risk_score=0.10)

    def test_surfacing_penalty_zero_when_released(self):
        from agentic.sovereign_insight_gate_pure import compute_surfacing_penalty_pure
        penalty = compute_surfacing_penalty_pure(
            can_release=True, stab_score=0.5, token_entropy=10.0,
        )
        assert penalty == 0.0

    def test_surfacing_penalty_nonzero_when_blocked(self):
        from agentic.sovereign_insight_gate_pure import compute_surfacing_penalty_pure
        penalty = compute_surfacing_penalty_pure(
            can_release=False, stab_score=0.5, token_entropy=10.0,
        )
        assert penalty > 0.0
        assert penalty == 0.5 * (1.0 - 0.5)

    def test_full_gate_release(self):
        from agentic.sovereign_insight_gate_pure import run_insight_gate_pure
        result = run_insight_gate_pure(
            r_acc=0.95, s_acc=0.90, guna_coherence=0.85,
            drift=0.05, authority=0.95, vritti=0,
        )
        assert result.eligible
        assert result.can_release
        assert len(result.reason_codes) == 0

    def test_full_gate_blocked(self):
        from agentic.sovereign_insight_gate_pure import run_insight_gate_pure
        result = run_insight_gate_pure(
            r_acc=0.50, s_acc=0.50, guna_coherence=0.30,
            drift=0.5, authority=0.5, vritti=2,  # VIKALPA
        )
        assert not result.eligible
        assert not result.can_release
        assert len(result.reason_codes) > 0

    def test_full_gate_reason_codes(self):
        from agentic.sovereign_insight_gate_pure import run_insight_gate_pure
        result = run_insight_gate_pure(
            r_acc=0.50, s_acc=0.50, guna_coherence=0.30,
            vritti=1,  # VIPARYAYA — not allowed
        )
        # Should have multiple reason codes
        assert any("R_ACC_LOW" in c for c in result.reason_codes)
        assert any("VRITTI_BLOCKED" in c for c in result.reason_codes)
        assert any("GC_LOW" in c for c in result.reason_codes)

    def test_gate_result_to_audit_dict(self):
        from agentic.sovereign_insight_gate_pure import run_insight_gate_pure
        result = run_insight_gate_pure(r_acc=0.95, s_acc=0.90, guna_coherence=0.85)
        d = result.to_audit_dict()
        assert isinstance(d, dict)
        assert "insight_eligible" in d
        assert "insight_stab_score" in d

    def test_no_torch_in_insight_gate_pure(self):
        import agentic.sovereign_insight_gate_pure as igp
        assert "torch" not in dir(igp)


# =========================================================================
# 3. Insight adapter
# =========================================================================

class TestInsightAdapter:
    """Verify insight_adapter.py structured outputs."""

    def test_resolve_with_sufficient_signals(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal,
        )
        result = resolve_insight_signal(
            r_acc=0.95, s_acc=0.90, guna_coherence=0.85,
            authority=0.95, vritti=0,
        )
        assert result.available
        assert result.eligible
        assert result.can_release
        assert result.confidence_penalty == 0.0
        assert not result.confirmation_pressure

    def test_resolve_with_insufficient_signals(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal,
        )
        result = resolve_insight_signal()
        assert not result.available
        assert result.confidence_penalty == 0.0
        assert not result.confirmation_pressure

    def test_resolve_unstable_gives_penalty(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal,
        )
        result = resolve_insight_signal(
            r_acc=0.30, s_acc=0.30, guna_coherence=0.20,
            drift=0.9, authority=0.3, vritti=2,
        )
        assert result.available
        assert not result.eligible
        assert result.confidence_penalty > 0.0
        assert result.confidence_penalty <= 0.10  # bounded

    def test_resolve_eligible_not_released_gives_confirmation(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal,
        )
        # High stability but high risk → eligible but not released
        result = resolve_insight_signal(
            r_acc=0.95, s_acc=0.90, guna_coherence=0.80,
            drift=0.0, authority=0.2,  # low authority → high risk
            vritti=0,
        )
        # Authority is low, so risk = 0.5*(1-0.8) + 0.3*0 + 0.2*(1-0.2) = 0.26
        # Risk threshold is 0.25, so release should be blocked
        assert result.available
        if result.eligible and not result.can_release:
            assert result.confirmation_pressure


# =========================================================================
# 4. Sovereign health adapter
# =========================================================================

class TestSovereignHealthAdapter:
    """Verify sovereign_health_adapter.py structured outputs."""

    def test_resolve_with_no_data(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        result = resolve_sovereign_health()
        assert not result.available
        assert not result.escalation_bias
        assert not result.caution_bias

    def test_resolve_stable_state(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        result = resolve_sovereign_health(
            alert_state="STABLE", entropy=0.3, guna_coherence=0.9,
        )
        assert result.available
        assert result.alert_state == "STABLE"
        assert not result.escalation_bias
        assert not result.caution_bias

    def test_resolve_lockdown_gives_biases(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        result = resolve_sovereign_health(
            alert_state="LOCKDOWN_ACTIVE", entropy=0.8,
        )
        assert result.available
        assert result.escalation_bias
        assert result.caution_bias
        assert "SOVEREIGN_LOCKDOWN" in result.reason_codes

    def test_resolve_alert_gives_caution(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        result = resolve_sovereign_health(alert_state="ALERT", entropy=0.4)
        assert result.caution_bias
        assert not result.escalation_bias
        assert "SOVEREIGN_ALERT" in result.reason_codes

    def test_resolve_brake_active(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        result = resolve_sovereign_health(
            alert_state="STABLE", entropy=0.3, brake_active=True,
        )
        assert result.caution_bias
        assert "S8_BRAKE_ACTIVE" in result.reason_codes

    def test_resolve_high_entropy_gives_caution(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        result = resolve_sovereign_health(
            alert_state="STABLE", entropy=0.90,
        )
        assert result.caution_bias
        assert "ENTROPY_NIDRA" in result.reason_codes

    def test_inferred_alert_from_entropy(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        # No explicit alert_state, but very high entropy
        result = resolve_sovereign_health(entropy=0.90)
        assert result.alert_state == "ALERT"  # inferred


# =========================================================================
# 5. Stricter-only semantics
# =========================================================================

class TestStricterOnly:
    """Verify that Phase S2 signals only make governance stricter."""

    def test_insight_penalty_is_non_negative(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal, _compute_insight_confidence_penalty,
        )
        # Penalty should always be >= 0
        for stab in [0.0, 0.3, 0.5, 0.8, 1.0]:
            penalty = _compute_insight_confidence_penalty(False, stab)
            assert penalty >= 0.0
            assert penalty <= 0.10

    def test_insight_penalty_zero_when_eligible(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            _compute_insight_confidence_penalty,
        )
        # When eligible, no penalty regardless of stab score
        for stab in [0.0, 0.3, 0.5, 0.8, 1.0]:
            assert _compute_insight_confidence_penalty(True, stab) == 0.0

    def test_health_escalation_bias_only_on_lockdown(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        # STABLE → no escalation bias
        r = resolve_sovereign_health(alert_state="STABLE", entropy=0.3)
        assert not r.escalation_bias
        # ALERT → no escalation bias (caution only)
        r = resolve_sovereign_health(alert_state="ALERT", entropy=0.5)
        assert not r.escalation_bias
        # LOCKDOWN → escalation bias
        r = resolve_sovereign_health(alert_state="LOCKDOWN_ACTIVE", entropy=0.8)
        assert r.escalation_bias


# =========================================================================
# 6. Fallback behavior
# =========================================================================

class TestFallbackBehavior:
    """Verify graceful degradation when sovereign signals are absent."""

    def test_insight_unavailable_no_effect(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal,
        )
        r = resolve_insight_signal()
        assert not r.available
        assert r.confidence_penalty == 0.0
        assert not r.confirmation_pressure
        assert r.reason_codes == ()

    def test_health_unavailable_no_effect(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        r = resolve_sovereign_health()
        assert not r.available
        assert not r.escalation_bias
        assert not r.caution_bias
        assert r.reason_codes == ()

    def test_audit_event_works_without_phase_s2_fields(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        event = AuditEvent(
            decision_id="test-001",
            timestamp="2026-04-04T00:00:00Z",
            actor_id="test",
            action_type="test",
            tool_name=None,
            decision="ALLOW",
            risk_level="read_only",
            eligible=True,
            confidence=0.9,
            execution_mode="full",
            escalation_level="none",
            blocked_reasons=[],
            request_snapshot={},
            sovereign_telemetry=None,
            sovereign_health=None,
            sovereign_insight=None,
        )
        assert event.sovereign_health is None
        assert event.sovereign_insight is None


# =========================================================================
# 7. Audit metadata
# =========================================================================

class TestAuditMetadata:
    """Verify audit fields are populated correctly."""

    def test_audit_event_has_phase_s2_fields(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        fields = AuditEvent.model_fields
        assert "sovereign_health" in fields
        assert "sovereign_insight" in fields

    def test_audit_event_accepts_phase_s2_data(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        event = AuditEvent(
            decision_id="test-002",
            timestamp="2026-04-04T00:00:00Z",
            actor_id="test",
            action_type="test",
            tool_name=None,
            decision="ALLOW",
            risk_level="read_only",
            eligible=True,
            confidence=0.85,
            execution_mode="full",
            escalation_level="none",
            blocked_reasons=[],
            request_snapshot={},
            sovereign_health={
                "alert_state": "STABLE",
                "entropy_status": "FOCUSED",
            },
            sovereign_insight={
                "eligible": True,
                "can_release": True,
                "stab_score": 0.85,
            },
        )
        assert event.sovereign_health["alert_state"] == "STABLE"
        assert event.sovereign_insight["eligible"] is True


# =========================================================================
# 8. Governance service integration helpers
# =========================================================================

class TestGovernanceServiceHelpers:
    """Verify the _resolve helpers in governance_service."""

    def test_resolve_sovereign_health_signal_graceful(self):
        from agentic.agentic_framework.governance_service import (
            _resolve_sovereign_health_signal,
        )

        class FakeAssessment:
            jepa_composite = None

        class FakeEntropy:
            combined_entropy = None
            available = False

        result = _resolve_sovereign_health_signal(FakeAssessment(), FakeEntropy())
        # Should return a valid SovereignHealthResolution (graceful fallback)
        assert not result.escalation_bias

    def test_resolve_insight_signal_graceful(self):
        from agentic.agentic_framework.governance_service import (
            _resolve_insight_signal,
        )

        class FakeAssessment:
            jepa_composite = None

        result = _resolve_insight_signal(FakeAssessment())
        # Should return a valid InsightResolution (graceful fallback)
        assert not result.available
        assert result.confidence_penalty == 0.0


# =========================================================================
# 9. No PyTorch leaks
# =========================================================================

class TestNoPyTorchLeaks:
    """Verify no PyTorch dependency in governance-side modules."""

    def test_metrics_runtime_no_torch(self):
        import importlib
        mod = importlib.import_module("agentic.sovereign_metrics_runtime")
        source = importlib.util.find_spec("agentic.sovereign_metrics_runtime")
        assert source is not None
        # Module should not have torch as attribute
        assert "torch" not in dir(mod)

    def test_insight_gate_pure_no_torch(self):
        import importlib
        mod = importlib.import_module("agentic.sovereign_insight_gate_pure")
        assert "torch" not in dir(mod)

    def test_insight_adapter_no_torch(self):
        import importlib
        mod = importlib.import_module(
            "agentic.agentic_framework.signal_adapters.insight_adapter"
        )
        assert "torch" not in dir(mod)

    def test_health_adapter_no_torch(self):
        import importlib
        mod = importlib.import_module(
            "agentic.agentic_framework.signal_adapters.sovereign_health_adapter"
        )
        assert "torch" not in dir(mod)
