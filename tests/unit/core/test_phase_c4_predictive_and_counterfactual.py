"""
Phase C4: Predictive Signals and Counterfactual Bridge Integration Tests
=========================================================================

Tests verifying:
1. Predictive signals adapter resolves P35 drift, P36 identity, P37 continuity
2. P35 drift is behavior-affecting (bounded penalty + escalation on HIGH)
3. P37 continuity has light behavior (bounded penalty on fragmenting)
4. P36 identity is audit-only (no penalty, no escalation)
5. Counterfactual bridge runs simulations and produces audit-safe output
6. Fail-safe behavior when signals are absent or malformed
7. Audit metadata includes predictive signals and counterfactual data
8. Bounded effects remain bounded (aggregate penalty cap 0.20)
9. Partial availability works correctly
"""

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pytest

try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# =========================================================================
# Direct module loading — bypass signal_adapters/__init__.py numpy chain
# =========================================================================

_SA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "agentic", "agentic_framework", "signal_adapters",
)

# Load predictive_signals_adapter directly
_PSA_PATH = os.path.join(_SA_DIR, "predictive_signals_adapter.py")
_psa_spec = importlib.util.spec_from_file_location("predictive_signals_adapter_direct", _PSA_PATH)
_psa_mod = importlib.util.module_from_spec(_psa_spec)
sys.modules["predictive_signals_adapter_direct"] = _psa_mod
_psa_spec.loader.exec_module(_psa_mod)  # type: ignore[union-attr]

resolve_predictive_signals = _psa_mod.resolve_predictive_signals
PredictiveSignalsResolution = _psa_mod.PredictiveSignalsResolution
_P35_MAX_PENALTY = _psa_mod._P35_MAX_PENALTY
_P35_HIGH_RISK_PENALTY = _psa_mod._P35_HIGH_RISK_PENALTY
_P35_MODERATE_RISK_PENALTY = _psa_mod._P35_MODERATE_RISK_PENALTY
_P37_MAX_PENALTY = _psa_mod._P37_MAX_PENALTY
_P37_FRAGMENTING_PENALTY = _psa_mod._P37_FRAGMENTING_PENALTY
_P37_STRAINED_PENALTY = _psa_mod._P37_STRAINED_PENALTY

# Load counterfactual bridge directly
_CFB_PATH = os.path.join(_SA_DIR, "counterfactual_bridge.py")
_cfb_spec = importlib.util.spec_from_file_location("counterfactual_bridge_direct", _CFB_PATH)
_cfb_mod = importlib.util.module_from_spec(_cfb_spec)
sys.modules["counterfactual_bridge_direct"] = _cfb_mod
_cfb_spec.loader.exec_module(_cfb_mod)  # type: ignore[union-attr]

run_counterfactual_simulation = _cfb_mod.run_counterfactual_simulation
create_standard_scenarios = _cfb_mod.create_standard_scenarios
CounterfactualBridgeResult = _cfb_mod.CounterfactualBridgeResult

# Import counterfactual schema (pure Python)
from agentic.core.counterfactual.cf_schema import (  # noqa: E402
    CounterfactualScenario,
    create_scenario,
)


# =========================================================================
# Duck-typed mock objects for pipeline reports/states
# =========================================================================

@dataclass(frozen=True)
class MockDriftReport:
    """Duck-typed PredictivePersonaDriftReport (P35)."""
    predicted_drift_score: float = 0.3
    drift_risk_band: str = "low"
    trend_direction: str = "stable"
    contributing_factors: Tuple[str, ...] = ()
    confidence: float = 0.8
    observer_only: bool = True


@dataclass(frozen=True)
class MockIdentityState:
    """Duck-typed IdentityResonanceMemoryState (P36)."""
    identity_resonance_index: float = 0.7
    identity_stability_band: str = "stable"
    persistence_score: float = 0.85
    volatility_index: float = 0.1
    observer_only: bool = True


@dataclass(frozen=True)
class MockContinuityReport:
    """Duck-typed AdaptiveContinuityReport (P37)."""
    continuity_score: float = 0.8
    continuity_mode: str = "stable"
    continuity_pressure: float = 0.2
    oscillation_detected: bool = False
    observer_only: bool = True


# =========================================================================
# Tests: Predictive Signals Adapter — Empty / Fail-Safe
# =========================================================================

class TestPredictiveSignalsEmpty:
    """Tests for fail-safe behavior when no data is available."""

    def test_no_inputs_returns_unavailable(self):
        res = resolve_predictive_signals()
        assert not res.available
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias
        assert res.reason_codes == ()
        assert not res.p35_available
        assert not res.p36_available
        assert not res.p37_available

    def test_none_inputs_returns_unavailable(self):
        res = resolve_predictive_signals(
            drift_report=None, identity_state=None, continuity_report=None,
        )
        assert not res.available
        assert res.confidence_penalty == 0.0

    def test_malformed_input_returns_unavailable(self):
        res = resolve_predictive_signals(drift_report="not a report")
        assert not res.available
        assert res.confidence_penalty == 0.0

    def test_empty_resolution_to_audit_dict(self):
        res = resolve_predictive_signals()
        d = res.to_audit_dict()
        assert d["available"] is False
        assert d["confidence_penalty"] == 0.0
        assert d["predicted_drift_score"] is None
        assert d["continuity_score"] is None
        assert d["identity_resonance_index"] is None


# =========================================================================
# Tests: P35 Predictive Drift (Behavior-Affecting)
# =========================================================================

class TestP35Drift:
    """P35 drift: behavior-affecting with bounded penalty + escalation."""

    def test_low_drift_no_penalty(self):
        report = MockDriftReport(predicted_drift_score=0.2, drift_risk_band="low")
        res = resolve_predictive_signals(drift_report=report)
        assert res.available
        assert res.p35_available
        assert res.predicted_drift_score == 0.2
        assert res.drift_risk_band == "low"
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias

    def test_moderate_drift_small_penalty(self):
        report = MockDriftReport(predicted_drift_score=0.5, drift_risk_band="moderate")
        res = resolve_predictive_signals(drift_report=report)
        assert res.confidence_penalty == _P35_MODERATE_RISK_PENALTY
        assert res.confidence_penalty == 0.01
        assert not res.escalation_bias
        assert "P35_DRIFT_PENALTY" in res.reason_codes
        assert "P35_RISK_MODERATE" in res.reason_codes

    def test_high_drift_full_penalty_and_escalation(self):
        report = MockDriftReport(predicted_drift_score=0.8, drift_risk_band="high")
        res = resolve_predictive_signals(drift_report=report)
        assert res.confidence_penalty == _P35_HIGH_RISK_PENALTY
        assert res.confidence_penalty == 0.03
        assert res.escalation_bias
        assert "P35_DRIFT_PENALTY" in res.reason_codes
        assert "P35_DRIFT_ESCALATION" in res.reason_codes
        assert "P35_RISK_HIGH" in res.reason_codes

    def test_drift_penalty_bounded(self):
        """P35 penalty must never exceed _P35_MAX_PENALTY."""
        report = MockDriftReport(predicted_drift_score=1.0, drift_risk_band="high")
        res = resolve_predictive_signals(drift_report=report)
        assert res.confidence_penalty <= _P35_MAX_PENALTY

    def test_drift_trend_captured(self):
        report = MockDriftReport(trend_direction="worsening")
        res = resolve_predictive_signals(drift_report=report)
        assert res.drift_trend == "worsening"

    def test_drift_contributing_factors_captured(self):
        report = MockDriftReport(contributing_factors=("high_drift", "low_persistence"))
        res = resolve_predictive_signals(drift_report=report)
        assert res.drift_contributing_factors == ("high_drift", "low_persistence")


# =========================================================================
# Tests: P36 Identity Resonance (Audit-Only)
# =========================================================================

class TestP36Identity:
    """P36 identity: audit-only, no penalty or escalation ever."""

    def test_stable_identity_no_penalty(self):
        state = MockIdentityState(identity_stability_band="stable")
        res = resolve_predictive_signals(identity_state=state)
        assert res.available
        assert res.p36_available
        assert res.identity_resonance_index == 0.7
        assert res.identity_stability_band == "stable"
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias

    def test_fragile_identity_no_penalty(self):
        """Even fragile identity produces zero penalty (audit-only)."""
        state = MockIdentityState(
            identity_resonance_index=0.3,
            identity_stability_band="fragile",
            persistence_score=0.3,
            volatility_index=0.5,
        )
        res = resolve_predictive_signals(identity_state=state)
        assert res.confidence_penalty == 0.0
        assert not res.escalation_bias
        assert res.identity_stability_band == "fragile"
        assert "P36_IDENTITY_FRAGILE" in res.reason_codes
        assert "P36_IDENTITY_FRAGILE_WARN" in res.reason_codes

    def test_soft_identity_captured(self):
        state = MockIdentityState(identity_stability_band="soft")
        res = resolve_predictive_signals(identity_state=state)
        assert res.identity_stability_band == "soft"
        assert "P36_IDENTITY_SOFT" in res.reason_codes

    def test_identity_fields_in_audit(self):
        state = MockIdentityState(
            persistence_score=0.9, volatility_index=0.05,
        )
        res = resolve_predictive_signals(identity_state=state)
        d = res.to_audit_dict()
        assert d["persistence_score"] is not None
        assert d["volatility_index"] is not None


# =========================================================================
# Tests: P37 Adaptive Continuity (Light Behavior)
# =========================================================================

class TestP37Continuity:
    """P37 continuity: light behavior with bounded penalty."""

    def test_stable_continuity_no_penalty(self):
        report = MockContinuityReport(continuity_mode="stable")
        res = resolve_predictive_signals(continuity_report=report)
        assert res.available
        assert res.p37_available
        assert res.continuity_score == 0.8
        assert res.continuity_mode == "stable"
        assert res.confidence_penalty == 0.0

    def test_strained_continuity_small_penalty(self):
        report = MockContinuityReport(
            continuity_score=0.55, continuity_mode="strained",
            continuity_pressure=0.45,
        )
        res = resolve_predictive_signals(continuity_report=report)
        assert res.confidence_penalty == _P37_STRAINED_PENALTY
        assert res.confidence_penalty == 0.005
        assert "P37_CONTINUITY_PENALTY" in res.reason_codes
        assert "P37_MODE_STRAINED" in res.reason_codes

    def test_fragmenting_continuity_full_penalty(self):
        report = MockContinuityReport(
            continuity_score=0.3, continuity_mode="fragmenting",
            continuity_pressure=0.7, oscillation_detected=True,
        )
        res = resolve_predictive_signals(continuity_report=report)
        assert res.confidence_penalty == _P37_FRAGMENTING_PENALTY
        assert res.confidence_penalty == 0.02
        assert "P37_CONTINUITY_PENALTY" in res.reason_codes
        assert "P37_MODE_FRAGMENTING" in res.reason_codes
        assert "P37_OSCILLATION_DETECTED" in res.reason_codes

    def test_continuity_penalty_bounded(self):
        """P37 penalty must never exceed _P37_MAX_PENALTY."""
        report = MockContinuityReport(continuity_mode="fragmenting")
        res = resolve_predictive_signals(continuity_report=report)
        assert res.confidence_penalty <= _P37_MAX_PENALTY

    def test_oscillation_detected_captured(self):
        report = MockContinuityReport(oscillation_detected=True)
        res = resolve_predictive_signals(continuity_report=report)
        assert res.oscillation_detected is True


# =========================================================================
# Tests: Combined signals
# =========================================================================

class TestCombinedSignals:
    """Tests for all three signals provided together."""

    def test_all_signals_available(self):
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(),
            identity_state=MockIdentityState(),
            continuity_report=MockContinuityReport(),
        )
        assert res.available
        assert res.p35_available
        assert res.p36_available
        assert res.p37_available
        assert res.predicted_drift_score is not None
        assert res.identity_resonance_index is not None
        assert res.continuity_score is not None

    def test_combined_penalty_is_additive(self):
        """P35 + P37 penalties are additive (P36 = 0)."""
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(drift_risk_band="high"),
            identity_state=MockIdentityState(identity_stability_band="fragile"),
            continuity_report=MockContinuityReport(continuity_mode="fragmenting"),
        )
        expected = _P35_HIGH_RISK_PENALTY + _P37_FRAGMENTING_PENALTY
        assert res.confidence_penalty == pytest.approx(expected)
        assert res.confidence_penalty == pytest.approx(0.05)

    def test_combined_max_penalty_bounded(self):
        """Even with worst-case P35+P37, penalty is bounded."""
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(drift_risk_band="high"),
            continuity_report=MockContinuityReport(continuity_mode="fragmenting"),
        )
        assert res.confidence_penalty <= (_P35_MAX_PENALTY + _P37_MAX_PENALTY)
        assert res.confidence_penalty <= 0.05

    def test_partial_p35_only(self):
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(),
        )
        assert res.available
        assert res.p35_available
        assert not res.p36_available
        assert not res.p37_available
        assert res.predicted_drift_score is not None
        assert res.identity_resonance_index is None
        assert res.continuity_score is None

    def test_partial_p36_only(self):
        res = resolve_predictive_signals(
            identity_state=MockIdentityState(),
        )
        assert res.available
        assert not res.p35_available
        assert res.p36_available
        assert not res.p37_available
        assert res.confidence_penalty == 0.0  # audit-only

    def test_partial_p37_only(self):
        res = resolve_predictive_signals(
            continuity_report=MockContinuityReport(continuity_mode="fragmenting"),
        )
        assert res.available
        assert not res.p35_available
        assert not res.p36_available
        assert res.p37_available
        assert res.confidence_penalty == _P37_FRAGMENTING_PENALTY

    def test_source_detail_contains_all_parts(self):
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(),
            identity_state=MockIdentityState(),
            continuity_report=MockContinuityReport(),
        )
        assert "P35" in res.source_detail
        assert "P36" in res.source_detail
        assert "P37" in res.source_detail


# =========================================================================
# Tests: Audit dict serialization
# =========================================================================

class TestAuditDict:
    """Tests for to_audit_dict() serialization."""

    def test_full_audit_dict(self):
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(drift_risk_band="moderate"),
            identity_state=MockIdentityState(),
            continuity_report=MockContinuityReport(),
        )
        d = res.to_audit_dict()
        assert isinstance(d, dict)
        assert d["available"] is True
        assert d["predicted_drift_score"] is not None
        assert d["drift_risk_band"] == "moderate"
        assert d["identity_resonance_index"] is not None
        assert d["continuity_score"] is not None
        assert isinstance(d["reason_codes"], list)

    def test_audit_dict_values_rounded(self):
        res = resolve_predictive_signals(
            drift_report=MockDriftReport(predicted_drift_score=0.123456789),
        )
        d = res.to_audit_dict()
        # Should be rounded to 6 decimal places
        assert d["predicted_drift_score"] == round(0.123456789, 6)


# =========================================================================
# Tests: Resolution contract stability
# =========================================================================

class TestContractStability:
    """Verify the PredictiveSignalsResolution dataclass contract."""

    def test_resolution_is_frozen(self):
        res = resolve_predictive_signals()
        with pytest.raises(AttributeError):
            res.available = True  # type: ignore[misc]

    def test_resolution_has_expected_fields(self):
        expected_fields = {
            "predicted_drift_score", "drift_risk_band", "drift_trend",
            "drift_contributing_factors",
            "continuity_score", "continuity_mode", "continuity_pressure",
            "oscillation_detected",
            "identity_resonance_index", "identity_stability_band",
            "persistence_score", "volatility_index",
            "confidence_penalty", "escalation_bias", "reason_codes",
            "available", "source_detail",
            "p35_available", "p36_available", "p37_available",
        }
        actual_fields = {f.name for f in PredictiveSignalsResolution.__dataclass_fields__.values()}
        assert expected_fields == actual_fields

    def test_reason_codes_are_tuple(self):
        res = resolve_predictive_signals(drift_report=MockDriftReport(drift_risk_band="high"))
        assert isinstance(res.reason_codes, tuple)


# =========================================================================
# Tests: Counterfactual Bridge
# =========================================================================

class TestCounterfactualBridge:
    """Tests for the counterfactual simulation bridge."""

    def test_no_scenarios_returns_unavailable(self):
        result = run_counterfactual_simulation()
        assert not result.available
        assert result.scenario_count == 0
        assert result.error is not None

    def test_empty_scenario_list_returns_unavailable(self):
        result = run_counterfactual_simulation(scenarios=[])
        assert not result.available

    def test_single_scenario_simulation(self):
        scenario = create_scenario("test_drop", delta_coherence=-0.2)
        result = run_counterfactual_simulation(
            scenarios=[scenario],
            baseline_coherence=0.8,
            baseline_drift=0.3,
            baseline_entropy=0.4,
        )
        assert result.available
        assert result.scenario_count == 1
        assert result.report is not None
        assert result.summary is not None

    def test_multiple_scenarios(self):
        scenarios = [
            create_scenario("drop", delta_coherence=-0.3),
            create_scenario("spike", delta_entropy=0.3),
            create_scenario("drift", delta_drift=0.3),
        ]
        result = run_counterfactual_simulation(
            scenarios=scenarios,
            baseline_coherence=0.7,
        )
        assert result.available
        assert result.scenario_count == 3

    def test_standard_scenarios_generation(self):
        scenarios = create_standard_scenarios(delta_magnitude=0.2)
        assert len(scenarios) == 8
        ids = [s.scenario_id for s in scenarios]
        assert "coherence_drop" in ids
        assert "entropy_spike" in ids
        assert "combined_stress" in ids

    def test_standard_scenarios_simulation(self):
        scenarios = create_standard_scenarios()
        result = run_counterfactual_simulation(
            scenarios=scenarios,
            baseline_coherence=0.7,
            baseline_drift=0.3,
            baseline_entropy=0.4,
            baseline_schema_stability=0.8,
            baseline_identity_harmonics=0.7,
        )
        assert result.available
        assert result.scenario_count == 8

    def test_risk_flags_counted(self):
        scenarios = [
            create_scenario("big_drop", delta_coherence=-0.5, delta_entropy=0.5, delta_drift=0.5),
        ]
        result = run_counterfactual_simulation(
            scenarios=scenarios,
            baseline_coherence=0.8,
            baseline_drift=0.2,
            baseline_entropy=0.2,
        )
        assert result.available
        assert result.risk_flag_count >= 0  # May or may not trigger flags

    def test_bridge_result_to_audit_dict(self):
        scenarios = [create_scenario("test", delta_coherence=-0.1)]
        result = run_counterfactual_simulation(
            scenarios=scenarios,
            baseline_coherence=0.7,
        )
        d = result.to_audit_dict()
        assert isinstance(d, dict)
        assert d["available"] is True
        assert d["scenario_count"] == 1
        assert "baseline_ucf" in d

    def test_empty_result_to_audit_dict(self):
        result = run_counterfactual_simulation()
        d = result.to_audit_dict()
        assert d["available"] is False
        assert d["baseline_ucf"] is None

    def test_bridge_result_is_frozen(self):
        result = run_counterfactual_simulation()
        with pytest.raises(AttributeError):
            result.available = True  # type: ignore[misc]

    def test_boundary_scenarios_returned(self):
        scenarios = create_standard_scenarios(delta_magnitude=0.3)
        result = run_counterfactual_simulation(
            scenarios=scenarios,
            baseline_coherence=0.7,
            baseline_drift=0.3,
        )
        assert result.available
        assert result.boundary_scenarios is not None


# =========================================================================
# Tests: Governance Models — Audit Event Fields
# =========================================================================

class TestGovernanceModelsC4Fields:
    """Verify C4 fields exist on the AuditEvent model."""

    @pytest.mark.skipif(not HAS_NUMPY, reason="governance_models needs numpy chain")
    def test_audit_event_has_predictive_signals_field(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        fields = {f for f in AuditEvent.model_fields}
        assert "predictive_signals" in fields

    @pytest.mark.skipif(not HAS_NUMPY, reason="governance_models needs numpy chain")
    def test_audit_event_has_counterfactual_field(self):
        from agentic.agentic_framework.governance_models import AuditEvent
        fields = {f for f in AuditEvent.model_fields}
        assert "counterfactual" in fields

    def test_predictive_signals_field_exists_in_source(self):
        """Verify field exists by reading source — no numpy needed."""
        import ast
        models_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "governance_models.py",
        )
        with open(models_path) as f:
            source = f.read()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "AuditEvent":
                field_names = [
                    stmt.target.id
                    for stmt in node.body
                    if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
                ]
                assert "predictive_signals" in field_names
                assert "counterfactual" in field_names
                return
        pytest.fail("AuditEvent class not found in governance_models.py")
