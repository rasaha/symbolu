"""
Phase C2: Core CoherenceState Adapter Tests
=============================================

Tests verifying the Phase C2 coherence state adapter:
1. Selected CoherenceState subset is extracted correctly
2. Governance-facing contract is stable and serializable
3. Adapter handles missing/partial state safely
4. Relationship with coherence_tracker.py is explicit
5. Adapter works without importing coherence_engine
6. Audit/context wiring works
7. No regressions in existing coherence-related tests
8. No accidental coupling to coherence_engine.py

Note: The signal_adapters package transitively requires numpy (via
jepa_governance). Tests that import the adapter through the package
hierarchy are skipped when numpy is unavailable. Tests that verify
the adapter logic directly use importlib to load the module file.
"""

import importlib
import importlib.util
import os
import warnings
from dataclasses import dataclass
from typing import Optional

import pytest

try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# Direct module loading — bypasses signal_adapters/__init__.py to avoid
# transitive numpy dependency. This proves the adapter itself is pure Python.
import sys

_ADAPTER_MODULE_NAME = "coherence_state_adapter_direct"
_ADAPTER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "agentic", "agentic_framework", "signal_adapters", "coherence_state_adapter.py",
)
_spec = importlib.util.spec_from_file_location(
    _ADAPTER_MODULE_NAME, _ADAPTER_PATH,
)
_adapter = importlib.util.module_from_spec(_spec)
# Register in sys.modules BEFORE exec so @dataclass can resolve __module__
sys.modules[_ADAPTER_MODULE_NAME] = _adapter
_spec.loader.exec_module(_adapter)  # type: ignore[union-attr]

resolve_core_coherence = _adapter.resolve_core_coherence
CoreCoherenceResolution = _adapter.CoreCoherenceResolution
_MAX_PENALTY = _adapter._MAX_PENALTY


# =========================================================================
# Helper: mock CoherenceState (duck-typed, no pipeline dependency)
# =========================================================================

@dataclass
class MockCoreCoherenceState:
    """Simulates agentic.core.coherence.CoherenceState for testing.

    Only includes fields the adapter extracts. This proves the adapter
    works via duck-typing, not by importing the real pipeline class.
    """

    convo_id: str = "test-convo-001"
    turn_index: int = 5

    # Coherence
    coherence_score: float = 0.75
    coherence_v3_quality: Optional[float] = 0.80
    semantic_stability_score: float = 0.70

    # Drift
    persona_drift_score: float = 0.15
    drift_fusion_index: Optional[float] = 0.20
    drift_risk_band: Optional[str] = "low"
    current_drift_likelihood_band: Optional[str] = "low"

    # Entropy dynamics
    temporal_entropy_diff: Optional[float] = 0.05
    temporal_entropy_volatility: Optional[float] = 0.10

    # UCF
    current_coi: Optional[float] = 0.85
    current_csi: Optional[float] = 0.90

    # Continuity
    current_css: Optional[float] = 0.88
    current_continuity_band: Optional[str] = "stable"

    # Identity & predictive
    current_ims: Optional[float] = 0.82
    current_drift_magnitude_prediction: Optional[float] = 0.12

    # Audit-only
    resonance_index: Optional[float] = 0.65
    mapper_volatility_score: float = 0.08


# =========================================================================
# 1. Field extraction
# =========================================================================


class TestFieldExtraction:
    """Verify the adapter extracts the correct governance subset."""

    def test_healthy_state_extraction(self):

        state = MockCoreCoherenceState()
        res = resolve_core_coherence(core_coherence_state=state)

        assert res.available is True
        assert res.coherence_score == 0.75
        assert res.coherence_v3_quality == 0.80
        assert res.semantic_stability == 0.70
        assert res.persona_drift == 0.15
        assert res.drift_fusion_index == 0.20
        assert res.drift_risk_band == "low"
        assert res.drift_likelihood_band == "low"
        assert res.temporal_entropy_diff == 0.05
        assert res.temporal_entropy_vol == 0.10
        assert res.ucf_coi == 0.85
        assert res.ucf_csi == 0.90
        assert res.continuity_score == 0.88
        assert res.continuity_band == "stable"
        assert res.identity_memory_score == 0.82
        assert res.drift_magnitude_pred == 0.12
        assert res.convo_id == "test-convo-001"
        assert res.turn_index == 5
        assert res.resonance_index == 0.65
        assert res.mapper_volatility == 0.08

    def test_float_clamping(self):
        """Values outside [0, 1] should be clamped for bounded fields."""

        state = MockCoreCoherenceState(
            coherence_score=1.5,
            persona_drift_score=-0.2,
        )
        res = resolve_core_coherence(core_coherence_state=state)

        assert res.coherence_score == 1.0
        assert res.persona_drift == 0.0

    def test_unbounded_fields_not_clamped(self):
        """temporal_entropy_diff and resonance_index are not clamped."""

        state = MockCoreCoherenceState(
            temporal_entropy_diff=-0.5,
            temporal_entropy_volatility=2.3,
            resonance_index=-0.1,
        )
        res = resolve_core_coherence(core_coherence_state=state)

        assert res.temporal_entropy_diff == -0.5
        assert res.temporal_entropy_vol == 2.3
        assert res.resonance_index == -0.1


# =========================================================================
# 2. Contract stability and serialization
# =========================================================================


class TestContractStability:
    """Verify the CoreCoherenceResolution contract is stable and serializable."""

    def test_frozen_immutability(self):

        res = resolve_core_coherence(core_coherence_state=MockCoreCoherenceState())
        with pytest.raises(AttributeError):
            res.coherence_score = 0.5  # type: ignore[misc]

    def test_to_audit_dict(self):

        res = resolve_core_coherence(core_coherence_state=MockCoreCoherenceState())
        d = res.to_audit_dict()

        assert isinstance(d, dict)
        assert d["available"] is True
        assert d["coherence_score"] == 0.75
        assert d["persona_drift"] == 0.15
        assert d["convo_id"] == "test-convo-001"
        assert isinstance(d["reason_codes"], list)

    def test_audit_dict_has_all_signal_fields(self):

        res = resolve_core_coherence(core_coherence_state=MockCoreCoherenceState())
        d = res.to_audit_dict()

        expected_keys = {
            "coherence_score", "coherence_v3_quality", "semantic_stability",
            "persona_drift", "drift_fusion_index", "drift_risk_band",
            "drift_likelihood_band", "temporal_entropy_diff",
            "temporal_entropy_vol", "ucf_coi", "ucf_csi",
            "continuity_score", "continuity_band",
            "identity_memory_score", "drift_magnitude_pred",
            "convo_id", "turn_index", "resonance_index", "mapper_volatility",
            "confidence_penalty", "escalation_bias",
            "available", "source_detail", "reason_codes",
        }
        assert expected_keys == set(d.keys())


# =========================================================================
# 3. Missing/partial state handling
# =========================================================================


class TestFailClosedBehavior:
    """Verify fail-closed semantics: missing = zero penalty, no escalation."""

    def test_none_input(self):

        res = resolve_core_coherence(core_coherence_state=None)
        assert res.available is False
        assert res.confidence_penalty == 0.0
        assert res.escalation_bias is False
        assert res.reason_codes == ()
        assert res.coherence_score is None

    def test_no_arguments(self):

        res = resolve_core_coherence()
        assert res.available is False
        assert res.confidence_penalty == 0.0

    def test_malformed_input(self):
        """Non-object input should not crash."""

        res = resolve_core_coherence(core_coherence_state="not a state")
        # Should either extract what it can or fail safely
        assert res.confidence_penalty >= 0.0
        assert isinstance(res.available, bool)

    def test_partial_state_missing_optional_fields(self):
        """State with only some fields should resolve gracefully."""

        @dataclass
        class PartialState:
            coherence_score: float = 0.6
            persona_drift_score: float = 0.3
            # Everything else missing

        res = resolve_core_coherence(core_coherence_state=PartialState())
        assert res.available is True
        assert res.coherence_score == 0.6
        assert res.persona_drift == 0.3
        assert res.ucf_coi is None
        assert res.drift_risk_band is None
        assert res.continuity_band is None

    def test_empty_object(self):
        """Object with no matching attributes should still work."""

        res = resolve_core_coherence(core_coherence_state=object())
        # All fields None, penalty 0, available True (extraction succeeded)
        assert res.coherence_score is None
        assert res.confidence_penalty == 0.0


# =========================================================================
# 4. Confidence penalty computation
# =========================================================================


class TestConfidencePenalty:
    """Verify bounded penalty computation."""

    def test_healthy_state_zero_penalty(self):

        state = MockCoreCoherenceState(
            coherence_score=0.8,
            coherence_v3_quality=0.85,
            persona_drift_score=0.1,
            drift_risk_band="low",
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.confidence_penalty == 0.0

    def test_low_coherence_penalty(self):

        state = MockCoreCoherenceState(
            coherence_score=0.2,
            coherence_v3_quality=0.2,
            persona_drift_score=0.1,
            drift_risk_band="low",
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.confidence_penalty > 0.0
        assert res.confidence_penalty <= 0.05  # coherence-only contribution

    def test_high_drift_penalty(self):

        state = MockCoreCoherenceState(
            coherence_score=0.8,
            persona_drift_score=0.9,
            drift_risk_band="high",
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.confidence_penalty > 0.0
        assert res.confidence_penalty <= 0.05  # drift-only contribution

    def test_combined_penalty_capped(self):

        state = MockCoreCoherenceState(
            coherence_score=0.0,
            coherence_v3_quality=0.0,
            persona_drift_score=1.0,
            drift_risk_band="critical",
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.confidence_penalty <= _MAX_PENALTY
        assert res.confidence_penalty == _MAX_PENALTY  # Both at maximum

    def test_penalty_never_negative(self):

        state = MockCoreCoherenceState(
            coherence_score=1.0,
            persona_drift_score=0.0,
            drift_risk_band="low",
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.confidence_penalty >= 0.0


# =========================================================================
# 5. Escalation bias
# =========================================================================


class TestEscalationBias:
    """Verify escalation triggers on critical/severe drift."""

    def test_no_escalation_normal_drift(self):

        state = MockCoreCoherenceState(drift_risk_band="moderate")
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.escalation_bias is False

    def test_escalation_critical_drift(self):

        state = MockCoreCoherenceState(drift_risk_band="critical")
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.escalation_bias is True
        assert "CORE_COHERENCE_ESCALATION" in res.reason_codes

    def test_escalation_severe_likelihood(self):

        state = MockCoreCoherenceState(
            drift_risk_band="low",
            current_drift_likelihood_band="severe",
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.escalation_bias is True

    def test_no_escalation_none_bands(self):

        state = MockCoreCoherenceState(
            drift_risk_band=None,
            current_drift_likelihood_band=None,
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert res.escalation_bias is False


# =========================================================================
# 6. Reason codes
# =========================================================================


class TestReasonCodes:
    """Verify reason codes are populated correctly."""

    def test_reason_codes_on_penalty(self):

        state = MockCoreCoherenceState(coherence_score=0.1, coherence_v3_quality=0.1)
        res = resolve_core_coherence(core_coherence_state=state)
        assert "CORE_COHERENCE_PENALTY" in res.reason_codes

    def test_drift_band_code(self):

        state = MockCoreCoherenceState(drift_risk_band="high")
        res = resolve_core_coherence(core_coherence_state=state)
        assert "DRIFT_BAND_HIGH" in res.reason_codes

    def test_no_codes_when_healthy(self):

        state = MockCoreCoherenceState(
            coherence_score=0.9,
            persona_drift_score=0.05,
            drift_risk_band=None,
        )
        res = resolve_core_coherence(core_coherence_state=state)
        assert len(res.reason_codes) == 0


# =========================================================================
# 7. No coupling to coherence_engine.py
# =========================================================================


class TestNoCouplingToEngine:
    """Verify the adapter has no dependency on the pipeline engine."""

    def test_adapter_module_is_pure_python(self):
        """The adapter module file should load without numpy/torch."""
        # _adapter was loaded via importlib at module level — if we got
        # here, it loaded successfully without numpy.
        assert hasattr(_adapter, "resolve_core_coherence")
        assert hasattr(_adapter, "CoreCoherenceResolution")
        assert not hasattr(_adapter, "CoherenceEngine")

    def test_adapter_uses_duck_typing(self):
        """Adapter should work with any object that has the right attributes."""

        # Simple namespace object, not a real CoherenceState
        class FakeState:
            coherence_score = 0.7
            persona_drift_score = 0.2

        res = resolve_core_coherence(core_coherence_state=FakeState())
        assert res.available is True
        assert res.coherence_score == 0.7


# =========================================================================
# 8. coherence_tracker.py relationship is documented
# =========================================================================


class TestCoherenceTrackerRelationship:
    """Verify the relationship between tracker and adapter is explicit."""

    def test_tracker_docstring_references_adapter(self):
        """coherence_tracker.py docstring should reference the adapter."""
        tracker_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "coherence_tracker.py",
        )
        with open(tracker_path) as f:
            content = f.read()
        assert "coherence_state_adapter" in content
        assert "complementary" in content.lower()

    def test_adapter_docstring_references_tracker(self):
        """coherence_state_adapter.py docstring should reference the tracker."""
        assert "coherence_tracker" in _adapter.__doc__
        assert "complementary" in _adapter.__doc__.lower()

    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available (transitive dep)")
    def test_both_importable_independently(self):
        """Both modules should be importable without cross-dependency."""
        from agentic.agentic_framework.coherence_tracker import CoherenceEngine  # noqa: F401
        from agentic.agentic_framework.signal_adapters.coherence_state_adapter import (
            resolve_core_coherence,  # noqa: F401
        )

    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available (transitive dep)")
    def test_tracker_still_functional(self):
        """coherence_tracker should still work after docstring update."""
        from agentic.agentic_framework.coherence_tracker import (
            CoherenceEngine,
            create_initial_state,
        )

        engine = CoherenceEngine(window=5)
        state = create_initial_state("test-session")
        assert state.session_id == "test-session"
        assert state.current_turn == 0


# =========================================================================
# 9. Package exports
# =========================================================================


class TestPackageExports:
    """Verify the adapter is properly exported from signal_adapters."""

    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available (transitive dep)")
    def test_exported_from_signal_adapters(self):
        from agentic.agentic_framework.signal_adapters import (
            resolve_core_coherence,
            CoreCoherenceResolution,
        )
        assert resolve_core_coherence is not None
        assert CoreCoherenceResolution is not None

    def test_in_signal_adapters_init_source(self):
        """signal_adapters/__init__.py should list the new adapter in __all__."""
        init_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "signal_adapters", "__init__.py",
        )
        with open(init_path) as f:
            content = f.read()
        assert "resolve_core_coherence" in content
        assert "CoreCoherenceResolution" in content


# =========================================================================
# 10. Source detail provenance
# =========================================================================


class TestSourceDetail:
    """Verify source_detail carries useful provenance."""

    def test_healthy_state_detail(self):

        state = MockCoreCoherenceState()
        res = resolve_core_coherence(core_coherence_state=state)
        assert "core CoherenceState" in res.source_detail
        assert "coherence=" in res.source_detail
        assert "turn=5" in res.source_detail

    def test_empty_state_detail(self):

        res = resolve_core_coherence()
        assert "no core coherence state available" in res.source_detail
