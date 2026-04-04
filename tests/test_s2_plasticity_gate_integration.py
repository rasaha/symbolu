"""
S2 Plasticity Gate Integration Tests
======================================

Tests for Phase S2-safety: PlasticityGate promotion into governance.

Test categories:
1. Adapter contract — resolution shape, determinism, serialization
2. Fail-closed — missing inputs yield zero penalty, no escalation
3. Bounded penalty — penalty never exceeds 0.04
4. Escalation logic — escalation only at critical threshold
5. Consumer-level — GovernanceService.authorize() uses plasticity signal
6. Regression — existing behavior unchanged when plasticity unavailable
"""

from __future__ import annotations

import math
import pytest

from agentic.safety.governance_patterns.plasticity_gate import (
    PlasticityGate,
    PlasticityResult,
)
from agentic.agentic_framework.signal_adapters.plasticity_adapter import (
    PlasticityResolution,
    resolve_plasticity_signal,
    _MAX_PENALTY,
    _LOW_PLASTICITY_THRESHOLD,
    _CRITICAL_PLASTICITY_THRESHOLD,
    _compute_penalty,
    _should_escalate,
)


# =============================================================================
# 1. Adapter Contract Tests
# =============================================================================

class TestPlasticityAdapterContract:
    """PlasticityResolution has correct shape and is frozen."""

    def test_resolution_is_frozen(self):
        res = resolve_plasticity_signal(coherence_score=0.8)
        with pytest.raises(AttributeError):
            res.plasticity = 0.5  # type: ignore[misc]

    def test_resolution_fields_present(self):
        res = resolve_plasticity_signal(coherence_score=0.8)
        assert hasattr(res, "plasticity")
        assert hasattr(res, "resistance")
        assert hasattr(res, "misalignment")
        assert hasattr(res, "logit")
        assert hasattr(res, "confidence_penalty")
        assert hasattr(res, "escalation_bias")
        assert hasattr(res, "reason_codes")
        assert hasattr(res, "available")
        assert hasattr(res, "source_detail")

    def test_to_audit_dict_serializable(self):
        res = resolve_plasticity_signal(
            coherence_score=0.7,
            persona_drift=0.3,
        )
        d = res.to_audit_dict()
        assert isinstance(d, dict)
        assert "plasticity" in d
        assert "reason_codes" in d
        assert isinstance(d["reason_codes"], list)
        # All values should be JSON-serializable primitives
        for v in d.values():
            assert isinstance(v, (int, float, bool, str, list, type(None)))

    def test_available_when_inputs_present(self):
        res = resolve_plasticity_signal(coherence_score=0.5)
        assert res.available is True

    def test_unavailable_when_no_inputs(self):
        res = resolve_plasticity_signal()
        assert res.available is False


# =============================================================================
# 2. Determinism Tests
# =============================================================================

class TestPlasticityDeterminism:
    """Same inputs produce identical outputs (100 runs)."""

    def test_deterministic_100_runs(self):
        results = []
        for _ in range(100):
            res = resolve_plasticity_signal(
                coherence_score=0.65,
                semantic_stability=0.70,
                persona_drift=0.15,
            )
            results.append((
                res.plasticity,
                res.resistance,
                res.misalignment,
                res.logit,
                res.confidence_penalty,
                res.escalation_bias,
            ))

        # All should be identical
        assert len(set(results)) == 1

    def test_deterministic_unavailable(self):
        results = []
        for _ in range(100):
            res = resolve_plasticity_signal()
            results.append((res.available, res.confidence_penalty, res.escalation_bias))
        assert len(set(results)) == 1


# =============================================================================
# 3. Fail-Closed Tests
# =============================================================================

class TestPlasticityFailClosed:
    """Missing/failed inputs yield neutral output."""

    def test_no_inputs_zero_penalty(self):
        res = resolve_plasticity_signal()
        assert res.confidence_penalty == 0.0
        assert res.escalation_bias is False
        assert res.available is False

    def test_none_inputs_zero_penalty(self):
        res = resolve_plasticity_signal(
            coherence_score=None,
            semantic_stability=None,
            persona_drift=None,
        )
        assert res.confidence_penalty == 0.0
        assert res.escalation_bias is False
        assert res.available is False

    def test_partial_inputs_still_available(self):
        """If at least one input available, gate computes."""
        res = resolve_plasticity_signal(coherence_score=0.6)
        assert res.available is True
        assert res.plasticity is not None

    def test_drift_only_still_available(self):
        """Persona drift alone is enough to compute."""
        res = resolve_plasticity_signal(persona_drift=0.3)
        assert res.available is True


# =============================================================================
# 4. Bounded Penalty Tests
# =============================================================================

class TestPlasticityBoundedPenalty:
    """Penalty never exceeds _MAX_PENALTY (0.04)."""

    def test_max_penalty_bounded(self):
        assert _MAX_PENALTY == 0.04

    def test_high_stability_zero_penalty(self):
        """High coherence, low drift → gate open → zero penalty."""
        res = resolve_plasticity_signal(
            coherence_score=0.9,
            persona_drift=0.0,
        )
        assert res.confidence_penalty == 0.0
        assert res.escalation_bias is False

    def test_low_stability_high_drift_max_penalty(self):
        """Low coherence, high drift → gate closing → penalty."""
        res = resolve_plasticity_signal(
            coherence_score=0.1,
            persona_drift=0.9,
        )
        assert res.confidence_penalty > 0.0
        assert res.confidence_penalty <= _MAX_PENALTY

    def test_penalty_never_exceeds_max(self):
        """Extreme inputs still produce bounded penalty."""
        # Worst case: zero stability, max drift
        res = resolve_plasticity_signal(
            coherence_score=0.0,
            persona_drift=1.0,
        )
        assert res.confidence_penalty <= _MAX_PENALTY

    def test_penalty_monotonic_with_drift(self):
        """Higher drift → higher or equal penalty."""
        penalties = []
        for drift in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
            res = resolve_plasticity_signal(
                coherence_score=0.5,
                persona_drift=drift,
            )
            penalties.append(res.confidence_penalty)
        # Should be non-decreasing
        for i in range(len(penalties) - 1):
            assert penalties[i] <= penalties[i + 1] + 1e-9

    def test_penalty_monotonic_with_stability(self):
        """Lower stability → higher or equal penalty."""
        penalties = []
        for stability in (1.0, 0.8, 0.6, 0.4, 0.2, 0.0):
            res = resolve_plasticity_signal(
                coherence_score=stability,
                persona_drift=0.3,
            )
            penalties.append(res.confidence_penalty)
        # Should be non-decreasing (stability decreasing → penalty increasing)
        for i in range(len(penalties) - 1):
            assert penalties[i] <= penalties[i + 1] + 1e-9


# =============================================================================
# 5. Escalation Logic Tests
# =============================================================================

class TestPlasticityEscalation:
    """Escalation only triggers at critical threshold."""

    def test_no_escalation_above_critical(self):
        """Above critical threshold → no escalation."""
        res = resolve_plasticity_signal(
            coherence_score=0.7,
            persona_drift=0.1,
        )
        assert res.escalation_bias is False

    def test_escalation_at_low_plasticity(self):
        """Very low stability + high drift → escalation."""
        res = resolve_plasticity_signal(
            coherence_score=0.05,
            persona_drift=0.95,
        )
        # With default params: resistance~0.05, misalignment~0.95
        # logit = 2*0.05 - 2*0.95 + (-1) = 0.1 - 1.9 - 1 = -2.8
        # plasticity = sigmoid(-2.8) ≈ 0.057
        assert res.plasticity is not None
        assert res.plasticity < _CRITICAL_PLASTICITY_THRESHOLD
        assert res.escalation_bias is True

    def test_escalation_codes_present(self):
        res = resolve_plasticity_signal(
            coherence_score=0.05,
            persona_drift=0.95,
        )
        if res.escalation_bias:
            assert "PLASTICITY_ESCALATION" in res.reason_codes


# =============================================================================
# 6. Input Priority Tests
# =============================================================================

class TestPlasticityInputPriority:
    """semantic_stability preferred over coherence_score for resistance."""

    def test_semantic_stability_preferred(self):
        """When both available, semantic_stability is used."""
        res = resolve_plasticity_signal(
            coherence_score=0.9,  # would give high resistance
            semantic_stability=0.1,  # low stability → lower plasticity
            persona_drift=0.0,
        )
        # If semantic_stability is used (0.1), plasticity should be lower
        # than if coherence_score were used (0.9)
        res_coherence = resolve_plasticity_signal(
            coherence_score=0.9,
            persona_drift=0.0,
        )
        assert res.plasticity is not None
        assert res_coherence.plasticity is not None
        assert res.plasticity < res_coherence.plasticity

    def test_coherence_fallback(self):
        """When semantic_stability absent, coherence_score is used."""
        res = resolve_plasticity_signal(
            coherence_score=0.7,
            persona_drift=0.2,
        )
        assert res.available is True
        assert "coherence_score" in res.source_detail


# =============================================================================
# 7. Underlying Gate Tests
# =============================================================================

class TestPlasticityGateDirectly:
    """PlasticityGate itself works correctly."""

    def test_sigmoid_bounds(self):
        gate = PlasticityGate()
        result = gate.compute(resistance=0.5, misalignment=0.0)
        # plasticity should be in [0, 1]
        assert 0.0 <= result.plasticity <= 1.0

    def test_high_resistance_opens_gate(self):
        gate = PlasticityGate()
        high = gate.compute(resistance=1.0, misalignment=0.0)
        low = gate.compute(resistance=0.0, misalignment=0.0)
        # Fresh gate each time to avoid EMA contamination
        gate2 = PlasticityGate()
        high2 = gate2.compute(resistance=1.0, misalignment=0.0)
        gate3 = PlasticityGate()
        low2 = gate3.compute(resistance=0.0, misalignment=0.0)
        assert high2.plasticity > low2.plasticity

    def test_high_misalignment_closes_gate(self):
        gate1 = PlasticityGate()
        res_low = gate1.compute(resistance=0.5, misalignment=0.0)
        gate2 = PlasticityGate()
        res_high = gate2.compute(resistance=0.5, misalignment=1.0)
        assert res_low.plasticity > res_high.plasticity


# =============================================================================
# 8. Consumer-Level Test: GovernanceService.authorize()
# =============================================================================

class TestPlasticityGovernanceConsumer:
    """GovernanceService.authorize() materially uses plasticity signal."""

    def test_authorize_includes_plasticity_in_audit(self):
        """authorize() includes plasticity provenance in audit metadata."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test plasticity integration",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.3,
                    semantic_stability_score=0.2,
                    persona_drift_score=0.7,
                ),
            },
        )

        response = service.authorize(request)

        # Verify plasticity appears in audit
        audit = response.audit_event
        assert audit is not None

        # Check flat provenance fields
        snapshot = audit.request_snapshot
        assert "plasticity_available" in snapshot
        assert snapshot["plasticity_available"] is True
        assert "plasticity_value" in snapshot
        assert isinstance(snapshot["plasticity_value"], float)
        assert "plasticity_confidence_penalty" in snapshot
        assert "plasticity_escalation_bias" in snapshot

        # Check structured audit dict
        assert audit.plasticity_gate is not None
        assert "plasticity" in audit.plasticity_gate
        assert audit.plasticity_gate["available"] is True

    def test_authorize_plasticity_unavailable_no_regression(self):
        """When no coherence state, plasticity is unavailable but doesn't break."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test no plasticity",
            metadata={},  # no core_coherence_state
        )

        response = service.authorize(request)

        # Should succeed without error
        assert response is not None
        audit = response.audit_event
        snapshot = audit.request_snapshot
        assert snapshot["plasticity_available"] is False
        assert snapshot["plasticity_confidence_penalty"] == 0.0
        assert snapshot["plasticity_escalation_bias"] is False

    def test_authorize_plasticity_penalty_affects_confidence(self):
        """Low plasticity should reduce effective confidence."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service_high = GovernanceService()
        service_low = GovernanceService()

        # High stability scenario
        request_high = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="high stability",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.9,
                    semantic_stability_score=0.9,
                    persona_drift_score=0.0,
                ),
            },
        )

        # Low stability scenario (same base confidence)
        request_low = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="low stability",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.1,
                    semantic_stability_score=0.1,
                    persona_drift_score=0.9,
                ),
            },
        )

        response_high = service_high.authorize(request_high)
        response_low = service_low.authorize(request_low)

        # Low stability should have equal or lower effective confidence
        # (due to plasticity penalty + coherence penalty stacking)
        assert response_low.confidence_score <= response_high.confidence_score


# =============================================================================
# Mock helper
# =============================================================================

class _MockCoherenceState:
    """Minimal mock for CoherenceState duck-typed interface."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
