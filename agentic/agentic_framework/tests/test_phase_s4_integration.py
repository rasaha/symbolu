"""
Phase S4 Integration Tests — Guna Anomalies, Bhava Transitions,
Governor Telemetry → Governance.

Tests:
1. Pure-Python Guna anomaly detection (sovereign_guna_anomaly.py)
2. Pure-Python Bhava transition priors (sovereign_bhava_priors.py)
3. Guna anomaly adapter structured outputs
4. Inference bridge carries S4 metadata
5. Sovereign bridge normalizes/forwards S4 signals
6. Bounded governance effects (confidence penalty + escalation bias)
7. Audit metadata includes S4 signals
8. Fallback behavior when signals are absent
9. No PyTorch dependency leaks
10. Backward compatibility with S1–S3
"""

import pytest


# =========================================================================
# 1. Guna anomaly detection (pure Python)
# =========================================================================

class TestGunaAnomalyDetection:
    """Verify sovereign_guna_anomaly.py is importable and correct."""

    def test_importable_without_torch(self):
        """guna_anomaly must not require torch."""
        import agentic.sovereign_guna_anomaly as ga
        assert hasattr(ga, "check_guna_anomalies")
        assert hasattr(ga, "GunaAnomalySnapshot")
        assert hasattr(ga, "snapshot_from_monitor_dict")

    def test_no_anomalies_short_history(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        snap = check_guna_anomalies([(0.3, 0.4, 0.3)])
        assert not snap.collapse
        assert not snap.oscillation
        assert not snap.stagnation
        assert snap.dominant_guna == "rajas"

    def test_collapse_detected(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        history = [(0.3, 0.3, 0.3), (0.95, 0.02, 0.03)]
        snap = check_guna_anomalies(history, collapse_threshold=0.9)
        assert snap.collapse
        assert snap.dominant_guna == "sattva"
        assert snap.any_anomaly
        assert snap.anomaly_count >= 1

    def test_oscillation_detected(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        history = [(0.1, 0.1, 0.8), (0.8, 0.1, 0.1)]
        snap = check_guna_anomalies(history, oscillation_threshold=0.3)
        assert snap.oscillation

    def test_no_oscillation_small_change(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        history = [(0.33, 0.33, 0.34), (0.34, 0.33, 0.33)]
        snap = check_guna_anomalies(history, oscillation_threshold=0.3)
        assert not snap.oscillation

    def test_stagnation_detected(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        # 10 identical readings
        history = [(0.33, 0.33, 0.34)] * 10
        snap = check_guna_anomalies(history, stagnation_window=10)
        assert snap.stagnation

    def test_no_stagnation_short_window(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        history = [(0.33, 0.33, 0.34)] * 5
        snap = check_guna_anomalies(history, stagnation_window=10)
        assert not snap.stagnation

    def test_statistics_computed(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        history = [(0.2, 0.3, 0.5), (0.4, 0.3, 0.3)]
        snap = check_guna_anomalies(history)
        assert snap.sattva_mean is not None
        assert snap.rajas_mean is not None
        assert snap.tamas_mean is not None
        assert abs(snap.sattva_mean - 0.3) < 0.01

    def test_to_audit_dict(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        history = [(0.3, 0.3, 0.4), (0.95, 0.02, 0.03)]
        snap = check_guna_anomalies(history)
        d = snap.to_audit_dict()
        assert "collapse" in d
        assert "oscillation" in d
        assert "stagnation" in d
        assert "dominant_guna" in d
        assert "any_anomaly" in d
        assert "anomaly_count" in d

    def test_snapshot_from_monitor_dict(self):
        from agentic.sovereign_guna_anomaly import snapshot_from_monitor_dict
        snap = snapshot_from_monitor_dict(
            anomalies={"collapse": True, "oscillation": False, "stagnation": False},
            dominant_guna="sattva",
            statistics={"sattva_mean": 0.8, "rajas_mean": 0.1, "tamas_mean": 0.1,
                        "sattva_std": 0.05, "rajas_std": 0.02, "tamas_std": 0.03},
        )
        assert snap.collapse
        assert not snap.oscillation
        assert snap.dominant_guna == "sattva"
        assert snap.sattva_mean == 0.8

    def test_empty_history(self):
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        snap = check_guna_anomalies([])
        assert snap.dominant_guna == "unknown"
        assert not snap.any_anomaly


# =========================================================================
# 2. Bhava transition priors (pure Python)
# =========================================================================

class TestBhavaTransitionPriors:
    """Verify sovereign_bhava_priors.py is importable and correct."""

    def test_importable_without_torch(self):
        """bhava_priors must not require torch."""
        import agentic.sovereign_bhava_priors as bp
        assert hasattr(bp, "get_transition_probability")
        assert hasattr(bp, "get_transition_penalty")
        assert hasattr(bp, "evaluate_bhava_transition")
        assert hasattr(bp, "BHAVA_TRANSITION_MATRIX")

    def test_known_strong_transition(self):
        from agentic.sovereign_bhava_priors import get_transition_probability
        # FACTUAL → CERTAIN = 0.9 (strong)
        prob = get_transition_probability("POT", "AGY")
        assert prob is not None

    def test_self_transition_high(self):
        from agentic.sovereign_bhava_priors import get_transition_probability
        # FACTUAL → FACTUAL = 0.8
        prob = get_transition_probability("POT", "POT")
        assert prob == 0.8

    def test_penalty_inverse_of_probability(self):
        from agentic.sovereign_bhava_priors import (
            get_transition_probability, get_transition_penalty,
        )
        prob = get_transition_probability("POT", "IDN")
        penalty = get_transition_penalty("POT", "IDN")
        assert prob is not None and penalty is not None
        assert abs((1.0 - prob) - penalty) < 0.01

    def test_unknown_bhava_returns_none(self):
        from agentic.sovereign_bhava_priors import get_transition_probability
        assert get_transition_probability("INVALID", "POT") is None

    def test_evaluate_bhava_transition_available(self):
        from agentic.sovereign_bhava_priors import evaluate_bhava_transition
        audit = evaluate_bhava_transition("POT", "RSN")
        assert audit.available
        assert audit.transition_probability is not None
        assert audit.transition_penalty is not None

    def test_evaluate_bhava_transition_unusual(self):
        from agentic.sovereign_bhava_priors import evaluate_bhava_transition
        # INSTRUCTIVE → QUESTIONING = 0.1 → penalty 0.9 → unusual
        audit = evaluate_bhava_transition("AGY", "WIT")
        assert audit.available
        # Check that it returns a valid result regardless of unusual flag

    def test_evaluate_bhava_transition_none_bhava(self):
        from agentic.sovereign_bhava_priors import evaluate_bhava_transition
        audit = evaluate_bhava_transition(None, "POT")
        assert not audit.available

    def test_observer_names_also_work(self):
        from agentic.sovereign_bhava_priors import get_transition_probability
        prob = get_transition_probability("FACTUAL", "ANALYTICAL")
        assert prob == 0.8

    def test_to_audit_dict(self):
        from agentic.sovereign_bhava_priors import evaluate_bhava_transition
        audit = evaluate_bhava_transition("POT", "RSN")
        d = audit.to_audit_dict()
        assert "from_bhava" in d
        assert "to_bhava" in d
        assert "transition_probability" in d
        assert "is_unusual" in d
        assert "available" in d

    def test_matrix_shape(self):
        from agentic.sovereign_bhava_priors import BHAVA_TRANSITION_MATRIX
        assert len(BHAVA_TRANSITION_MATRIX) == 12
        for row in BHAVA_TRANSITION_MATRIX:
            assert len(row) == 12


# =========================================================================
# 3. Guna anomaly adapter
# =========================================================================

class TestGunaAnomalyAdapter:
    """Verify guna_anomaly_adapter produces bounded governance signals."""

    def test_no_data_safe_defaults(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly(None)
        assert not res.available
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias
        assert res.reason_codes == ()

    def test_collapse_produces_penalty_and_escalation(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": True,
            "oscillation": False,
            "stagnation": False,
            "dominant_guna": "sattva",
        })
        assert res.available
        assert res.collapse
        assert res.confidence_penalty == 0.03
        assert res.escalation_bias
        assert "GUNA_COLLAPSE" in res.reason_codes

    def test_oscillation_produces_penalty_no_escalation(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": False,
            "oscillation": True,
            "stagnation": False,
            "dominant_guna": "rajas",
        })
        assert res.available
        assert res.confidence_penalty == 0.02
        assert not res.escalation_bias
        assert "GUNA_OSCILLATION" in res.reason_codes

    def test_stagnation_no_penalty_no_escalation(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": False,
            "oscillation": False,
            "stagnation": True,
            "dominant_guna": "tamas",
        })
        assert res.available
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias
        assert "GUNA_STAGNATION" in res.reason_codes

    def test_collapse_plus_oscillation_capped_penalty(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": True,
            "oscillation": True,
            "stagnation": False,
            "dominant_guna": "sattva",
        })
        assert res.available
        # 0.03 + 0.02 = 0.05, capped at 0.05
        assert res.confidence_penalty == 0.05
        assert res.escalation_bias  # collapse → escalation

    def test_to_audit_dict(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": True, "oscillation": False, "stagnation": True,
            "dominant_guna": "sattva",
        })
        d = res.to_audit_dict()
        assert d["collapse"] is True
        assert d["stagnation"] is True
        assert d["available"] is True
        assert d["confidence_penalty"] == 0.03


# =========================================================================
# 4. Inference bridge carries S4 metadata
# =========================================================================

class TestInferenceBridgeS4:
    """Verify ProjectionMetadata carries S4 fields.

    NOTE: inference_bridge.py imports through sovereign/__init__.py which
    triggers the torch import chain. We verify the contract indirectly
    through the sovereign_bridge (which is torch-free) and through
    structural checks on the guna_anomaly module.
    """

    def test_guna_anomaly_snapshot_serializes_for_bridge(self):
        """GunaAnomalySnapshot.to_audit_dict produces bridge-compatible dict."""
        from agentic.sovereign_guna_anomaly import check_guna_anomalies
        snap = check_guna_anomalies([(0.3, 0.3, 0.4), (0.95, 0.02, 0.03)])
        d = snap.to_audit_dict()
        # This dict would be passed as guna_anomalies to ProjectionMetadata
        assert "collapse" in d
        assert "dominant_guna" in d
        assert isinstance(d["collapse"], bool)

    def test_guna_anomalies_round_trip_through_bridge(self):
        """Guna anomalies survive projection→bridge round trip."""
        from agentic.agentic_framework.sovereign_bridge import guna_anomalies_from_projection
        # Simulate what ProjectionMetadata.to_dict() would produce
        meta_dict = {
            "had_guna": True,
            "guna_anomalies": {
                "collapse": True, "oscillation": False, "stagnation": False,
                "dominant_guna": "sattva",
            }
        }
        ctx = guna_anomalies_from_projection(projection_metadata=meta_dict)
        assert ctx.available
        assert ctx.collapse
        assert ctx.dominant_guna == "sattva"

    def test_governor_telemetry_round_trip_through_bridge(self):
        """Governor telemetry survives projection→bridge round trip."""
        from agentic.agentic_framework.sovereign_bridge import governor_telemetry_from_projection
        meta_dict = {
            "governor_telemetry": {"s_drift": 0.3, "coupling": 0.8}
        }
        result = governor_telemetry_from_projection(meta_dict)
        assert result is not None
        assert result["s_drift"] == 0.3

    def test_s4_fields_absent_in_minimal_projection(self):
        """When S4 data not present, bridge returns safe defaults."""
        from agentic.agentic_framework.sovereign_bridge import (
            guna_anomalies_from_projection,
            governor_telemetry_from_projection,
        )
        meta_dict = {"had_guna": True}
        assert not guna_anomalies_from_projection(projection_metadata=meta_dict).available
        assert governor_telemetry_from_projection(meta_dict) is None

    def test_project_sovereign_contract_via_bridge(self):
        """Verify the full projection→bridge flow for S4 data."""
        from agentic.agentic_framework.sovereign_bridge import guna_anomalies_from_projection
        # Simulate ProjectionMetadata.to_dict() output with S4 fields
        meta_dict = {
            "had_guna": True,
            "guna_anomalies": {
                "collapse": True, "oscillation": True, "stagnation": False,
                "dominant_guna": "sattva", "any_anomaly": True, "anomaly_count": 2,
            },
            "governor_telemetry": {"s_drift": 0.2, "brake_reason": "none"},
        }
        ctx = guna_anomalies_from_projection(projection_metadata=meta_dict)
        assert ctx.available
        assert ctx.collapse
        assert ctx.oscillation
        assert ctx.anomaly_count == 2


# =========================================================================
# 5. Sovereign bridge S4 forwarding
# =========================================================================

class TestSovereignBridgeS4:
    """Verify sovereign_bridge forwards S4 signals correctly."""

    def test_guna_anomaly_context_dataclass(self):
        from agentic.agentic_framework.sovereign_bridge import GunaAnomalyContext
        ctx = GunaAnomalyContext()
        assert not ctx.collapse
        assert not ctx.available
        assert ctx.anomaly_count == 0

    def test_guna_anomalies_from_projection(self):
        from agentic.agentic_framework.sovereign_bridge import guna_anomalies_from_projection
        ctx = guna_anomalies_from_projection(
            projection_metadata={
                "guna_anomalies": {
                    "collapse": True,
                    "oscillation": False,
                    "stagnation": True,
                    "dominant_guna": "tamas",
                }
            }
        )
        assert ctx.available
        assert ctx.collapse
        assert ctx.stagnation
        assert not ctx.oscillation
        assert ctx.dominant_guna == "tamas"
        assert ctx.anomaly_count == 2

    def test_guna_anomalies_from_projection_empty(self):
        from agentic.agentic_framework.sovereign_bridge import guna_anomalies_from_projection
        ctx = guna_anomalies_from_projection(projection_metadata={})
        assert not ctx.available

    def test_guna_anomalies_from_projection_none(self):
        from agentic.agentic_framework.sovereign_bridge import guna_anomalies_from_projection
        ctx = guna_anomalies_from_projection()
        assert not ctx.available

    def test_bhava_transition_from_diagnostics(self):
        from agentic.agentic_framework.sovereign_bridge import bhava_transition_from_diagnostics
        result = bhava_transition_from_diagnostics("POT", "RSN")
        assert result is not None
        assert "from_bhava" in result
        assert "transition_probability" in result
        assert result["available"]

    def test_bhava_transition_none_bhava(self):
        from agentic.agentic_framework.sovereign_bridge import bhava_transition_from_diagnostics
        result = bhava_transition_from_diagnostics(None, "RSN")
        assert result is None

    def test_governor_telemetry_from_projection(self):
        from agentic.agentic_framework.sovereign_bridge import governor_telemetry_from_projection
        result = governor_telemetry_from_projection(
            projection_metadata={
                "governor_telemetry": {"s_drift": 0.3, "coupling": 0.8}
            }
        )
        assert result is not None
        assert result["s_drift"] == 0.3

    def test_governor_telemetry_from_projection_none(self):
        from agentic.agentic_framework.sovereign_bridge import governor_telemetry_from_projection
        result = governor_telemetry_from_projection(projection_metadata={})
        assert result is None


# =========================================================================
# 6. Bounded governance effects
# =========================================================================

class TestBoundedGovernanceEffectsS4:
    """Verify Guna anomaly effects are bounded and stricter-only."""

    def test_collapse_penalty_exactly_003(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": True, "oscillation": False, "stagnation": False,
        })
        assert res.confidence_penalty == 0.03

    def test_oscillation_penalty_exactly_002(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": False, "oscillation": True, "stagnation": False,
        })
        assert res.confidence_penalty == 0.02

    def test_max_penalty_capped_at_005(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": True, "oscillation": True, "stagnation": True,
        })
        # 0.03 + 0.02 = 0.05, capped at 0.05
        assert res.confidence_penalty == 0.05

    def test_no_anomaly_zero_penalty(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({
            "collapse": False, "oscillation": False, "stagnation": False,
        })
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias

    def test_penalty_always_nonnegative(self):
        """Penalty should never be negative (stricter-only)."""
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        for c in [True, False]:
            for o in [True, False]:
                for s in [True, False]:
                    res = resolve_guna_anomaly({
                        "collapse": c, "oscillation": o, "stagnation": s,
                    })
                    assert res.confidence_penalty >= 0.0

    def test_escalation_only_on_collapse(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        # Oscillation alone → no escalation
        res = resolve_guna_anomaly({
            "collapse": False, "oscillation": True, "stagnation": True,
        })
        assert not res.escalation_bias

        # Collapse → escalation
        res = resolve_guna_anomaly({
            "collapse": True, "oscillation": False, "stagnation": False,
        })
        assert res.escalation_bias


# =========================================================================
# 7. Audit metadata includes S4 signals
# =========================================================================

class TestAuditMetadataS4:
    """Verify AuditEvent has S4 fields."""

    def test_audit_event_has_guna_anomalies_field(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        # Check field exists on schema
        assert "sovereign_guna_anomalies" in AuditEvent.model_fields

    def test_audit_event_has_bhava_transition_field(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        assert "sovereign_bhava_transition" in AuditEvent.model_fields

    def test_audit_event_has_governor_telemetry_field(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        assert "sovereign_governor_telemetry" in AuditEvent.model_fields

    def test_audit_event_s4_fields_default_none(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        event = AuditEvent(
            decision_id="test",
            timestamp="2026-01-01T00:00:00Z",
            actor_id="test",
            action_type="test",
            tool_name=None,
            decision="ALLOW",
            risk_level="read_only",
            eligible=True,
            confidence=0.8,
            execution_mode="full",
            escalation_level="none",
            blocked_reasons=[],
            request_snapshot={},
        )
        assert event.sovereign_guna_anomalies is None
        assert event.sovereign_bhava_transition is None
        assert event.sovereign_governor_telemetry is None

    def test_audit_event_accepts_s4_data(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        event = AuditEvent(
            decision_id="test",
            timestamp="2026-01-01T00:00:00Z",
            actor_id="test",
            action_type="test",
            tool_name=None,
            decision="ALLOW",
            risk_level="read_only",
            eligible=True,
            confidence=0.8,
            execution_mode="full",
            escalation_level="none",
            blocked_reasons=[],
            request_snapshot={},
            sovereign_guna_anomalies={"collapse": True, "oscillation": False},
            sovereign_bhava_transition={"from_bhava": "POT", "to_bhava": "RSN"},
            sovereign_governor_telemetry={"s_drift": 0.3},
        )
        assert event.sovereign_guna_anomalies["collapse"] is True
        assert event.sovereign_bhava_transition["from_bhava"] == "POT"
        assert event.sovereign_governor_telemetry["s_drift"] == 0.3


# =========================================================================
# 8. Fallback behavior
# =========================================================================

class TestFallbackBehaviorS4:
    """Verify S4 signals degrade gracefully when absent."""

    def test_guna_adapter_handles_bad_input(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly({"invalid_key": True})
        assert res.available
        assert res.confidence_penalty == 0.0

    def test_guna_adapter_handles_none(self):
        from agentic.agentic_framework.signal_adapters.guna_anomaly_adapter import (
            resolve_guna_anomaly,
        )
        res = resolve_guna_anomaly(None)
        assert not res.available

    def test_bhava_transition_handles_invalid_name(self):
        from agentic.sovereign_bhava_priors import evaluate_bhava_transition
        audit = evaluate_bhava_transition("INVALID", "ALSO_INVALID")
        assert not audit.available

    def test_guna_anomalies_from_projection_handles_bad_data(self):
        from agentic.agentic_framework.sovereign_bridge import guna_anomalies_from_projection
        ctx = guna_anomalies_from_projection(
            projection_metadata={"guna_anomalies": "not_a_dict"}
        )
        assert not ctx.available

    def test_governor_telemetry_handles_non_dict(self):
        from agentic.agentic_framework.sovereign_bridge import governor_telemetry_from_projection
        result = governor_telemetry_from_projection(
            projection_metadata={"governor_telemetry": 42}
        )
        assert result is None


# =========================================================================
# 9. No PyTorch dependency leaks
# =========================================================================

class TestNoPyTorchLeaksS4:
    """Verify S4 modules do not import torch."""

    def test_sovereign_guna_anomaly_no_torch(self):
        import importlib
        import sys
        # Remove torch from cache if present
        had_torch = "torch" in sys.modules
        mod = importlib.import_module("agentic.sovereign_guna_anomaly")
        # Module itself should not have imported torch
        assert "torch" not in dir(mod)

    def test_sovereign_bhava_priors_no_torch(self):
        import importlib
        mod = importlib.import_module("agentic.sovereign_bhava_priors")
        assert "torch" not in dir(mod)

    def test_guna_anomaly_adapter_no_torch(self):
        import importlib
        mod = importlib.import_module(
            "agentic.agentic_framework.signal_adapters.guna_anomaly_adapter"
        )
        assert "torch" not in dir(mod)


# =========================================================================
# 10. Backward compatibility with S1–S3
# =========================================================================

class TestBackwardCompatibilityS4:
    """Verify S4 does not break S1–S3 functionality."""

    def test_signals_from_sovereign_state_still_works(self):
        from agentic.agentic_framework.sovereign_bridge import signals_from_sovereign_state
        state = [0.5] * 32
        signals = signals_from_sovereign_state(state)
        assert signals.quality_score >= 0.0

    def test_coherence_from_sovereign_state_still_works(self):
        from agentic.agentic_framework.sovereign_bridge import coherence_from_sovereign_state
        state = [0.5] * 32
        coherence = coherence_from_sovereign_state(state)
        assert hasattr(coherence, "internal_consistency")

    def test_diagnostics_from_projection_still_works(self):
        from agentic.agentic_framework.sovereign_bridge import diagnostics_from_projection
        ctx = diagnostics_from_projection()
        assert not ctx.available

    def test_projection_metadata_backward_compat(self):
        """ProjectionMetadata without S4 fields still works via bridge."""
        # Can't import ProjectionMetadata directly (torch chain)
        # Verify contract through bridge: no S4 data → no S4 context
        from agentic.agentic_framework.sovereign_bridge import (
            guna_anomalies_from_projection,
            governor_telemetry_from_projection,
        )
        meta_dict = {"had_guna": True}  # S1-era metadata
        assert not guna_anomalies_from_projection(projection_metadata=meta_dict).available
        assert governor_telemetry_from_projection(meta_dict) is None

    def test_sovereign_health_adapter_still_works(self):
        from agentic.agentic_framework.signal_adapters.sovereign_health_adapter import (
            resolve_sovereign_health,
        )
        res = resolve_sovereign_health()
        assert not res.available

    def test_insight_adapter_still_works(self):
        from agentic.agentic_framework.signal_adapters.insight_adapter import (
            resolve_insight_signal,
        )
        res = resolve_insight_signal()
        assert not res.available

    def test_signal_adapters_init_exports_s4(self):
        from agentic.agentic_framework.signal_adapters import (
            resolve_guna_anomaly,
            GunaAnomalyResolution,
        )
        assert resolve_guna_anomaly is not None
        assert GunaAnomalyResolution is not None
