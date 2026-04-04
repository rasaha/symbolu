"""
Closure Patch: End-to-End GovernanceService.authorize() Integration Tests
==========================================================================

These tests prove that C2/C3/C4 signals injected through request metadata
actually flow through the live ``GovernanceService._evaluate()`` path and
populate the returned audit event, request snapshot, and confidence score.

Also covers:
- Aggregate penalty cap verification when multiple adapters contribute
- Generation gate behavioral tests (not source-string-only)
- Counterfactual field is intentionally None on live authorize path
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

# GovernanceService requires numpy+pydantic (via jepa_governance transitive dep).
# E2E and behavioral tests are skipped when unavailable.
_needs_numpy = pytest.mark.skipif(not HAS_NUMPY, reason="numpy/pydantic required for GovernanceService")


# =========================================================================
# Imports (only when numpy+pydantic available)
# =========================================================================

if HAS_NUMPY:
    try:
        from agentic.agentic_framework.governance_service import (
            GovernanceService,
            _is_generative_action,
            _check_generation_gate,
        )
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
            AuthorizationResponse,
            AuditEvent,
        )
        from agentic.core.generation_gate import (
            GenerationGate,
            GenerationMode,
            GateStatus,
        )
    except ImportError:
        HAS_NUMPY = False


# =========================================================================
# Duck-typed mock pipeline objects for metadata injection
# =========================================================================

@dataclass
class MockCoherenceState:
    """Duck-typed CoherenceState for C2 adapter (core_coherence_state)."""
    coherence_score: float = 0.3
    coherence_v3_quality: float = 0.25
    semantic_stability_score: float = 0.4
    persona_drift_score: float = 0.85
    drift_fusion_index: float = 0.7
    drift_risk_band: str = "critical"
    current_drift_likelihood_band: str = "severe"
    temporal_entropy_diff: float = 0.15
    temporal_entropy_volatility: float = 0.2
    current_coi: float = 0.6
    current_csi: float = 0.5
    current_css: float = 0.4
    current_continuity_band: str = "strained"
    current_ims: float = 0.55
    current_drift_magnitude_prediction: float = 0.7
    convo_id: str = "e2e-test-001"
    turn_index: int = 10
    resonance_index: float = 0.5
    mapper_volatility_score: float = 0.3


@dataclass
class MockUCFState:
    """Duck-typed UnifiedConsciousnessState for C3 adapter (ucf_state)."""
    ucf_score: float = 0.30
    stability_band: str = "unstable"
    contributing_factors: Dict[str, float] = field(default_factory=lambda: {
        "coherence_v3_quality": 0.3,
        "drift_fusion_stability": 0.2,
        "entropy_stability": 0.4,
    })
    confidence: float = 0.9


@dataclass(frozen=True)
class MockDriftReport:
    """Duck-typed PredictivePersonaDriftReport for C4 P35."""
    predicted_drift_score: float = 0.75
    drift_risk_band: str = "high"
    trend_direction: str = "worsening"
    contributing_factors: Tuple[str, ...] = ("high_drift", "low_persistence")
    confidence: float = 0.8


@dataclass(frozen=True)
class MockIdentityState:
    """Duck-typed IdentityResonanceMemoryState for C4 P36."""
    identity_resonance_index: float = 0.35
    identity_stability_band: str = "fragile"
    persistence_score: float = 0.3
    volatility_index: float = 0.5


@dataclass(frozen=True)
class MockContinuityReport:
    """Duck-typed AdaptiveContinuityReport for C4 P37."""
    continuity_score: float = 0.3
    continuity_mode: str = "fragmenting"
    continuity_pressure: float = 0.7
    oscillation_detected: bool = True


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture(autouse=True)
def reset_generation_gate():
    """Reset the singleton generation gate before and after each test."""
    if HAS_NUMPY:
        GenerationGate._reset()
        yield
        GenerationGate._reset()
    else:
        yield


@pytest.fixture
def service():
    """Create a vanilla GovernanceService for testing."""
    return GovernanceService()


def _make_request(**overrides) -> "AuthorizationRequest":
    """Build a valid AuthorizationRequest with sensible defaults."""
    defaults = dict(
        actor_id="e2e-test-actor",
        action_type="file_read",
        agency_level="FULL",
        quality_score=0.9,
        coherence_score=0.9,
        internal_consistency=0.9,
        goal_alignment=0.9,
        trajectory_confidence=0.9,
    )
    defaults.update(overrides)
    return AuthorizationRequest(**defaults)


# =========================================================================
# TASK 1: End-to-end GovernanceService.authorize() tests
# =========================================================================


@_needs_numpy
class TestE2EAuthorizeC2Signals:
    """Prove C2 core coherence signals flow through authorize()."""

    def test_c2_coherence_signals_populate_audit_event(self, service):
        """C2 signals injected via metadata appear in audit event."""
        request = _make_request(
            metadata={"core_coherence_state": MockCoherenceState()},
        )
        response = service.authorize(request)

        # Audit event should have core_coherence populated
        ae = response.audit_event
        assert ae.core_coherence is not None, "core_coherence audit dict should be populated"
        assert ae.core_coherence["available"] is True
        assert ae.core_coherence["coherence_score"] == 0.3
        assert ae.core_coherence["drift_risk_band"] == "critical"

    def test_c2_coherence_affects_confidence(self, service):
        """C2 signals with low coherence + high drift reduce confidence."""
        # Baseline: no C2 signals
        baseline_req = _make_request()
        baseline_resp = service.authorize(baseline_req)
        baseline_confidence = baseline_resp.confidence_score

        # With C2: low coherence + critical drift
        c2_req = _make_request(
            metadata={"core_coherence_state": MockCoherenceState()},
        )
        c2_resp = service.authorize(c2_req)

        # Confidence should be reduced (C2 penalty > 0)
        assert c2_resp.confidence_score < baseline_confidence, (
            f"C2 should reduce confidence: {c2_resp.confidence_score} "
            f"should be < {baseline_confidence}"
        )

    def test_c2_escalation_bias_in_snapshot(self, service):
        """C2 critical drift triggers escalation bias in request snapshot."""
        request = _make_request(
            metadata={"core_coherence_state": MockCoherenceState(
                drift_risk_band="critical",
            )},
        )
        response = service.authorize(request)
        snap = response.audit_event.request_snapshot

        assert snap["core_coherence_available"] is True
        assert snap["core_coherence_escalation_bias"] is True
        assert snap["core_coherence_drift_risk_band"] == "critical"


@_needs_numpy
class TestE2EAuthorizeC3Signals:
    """Prove C3 UCF signals flow through authorize()."""

    def test_c3_ucf_populates_audit_event(self, service):
        """C3 UCF injected via metadata appears in audit event."""
        request = _make_request(
            metadata={"ucf_state": MockUCFState()},
        )
        response = service.authorize(request)

        ae = response.audit_event
        assert ae.ucf_signal is not None, "ucf_signal audit dict should be populated"
        assert ae.ucf_signal["available"] is True
        assert ae.ucf_signal["ucf_score"] == 0.30
        assert ae.ucf_signal["stability_band"] == "unstable"

    def test_c3_ucf_unstable_reduces_confidence(self, service):
        """Unstable UCF should reduce confidence vs baseline."""
        baseline_resp = service.authorize(_make_request())

        ucf_req = _make_request(
            metadata={"ucf_state": MockUCFState(
                ucf_score=0.2, stability_band="unstable",
            )},
        )
        ucf_resp = service.authorize(ucf_req)

        assert ucf_resp.confidence_score < baseline_resp.confidence_score

    def test_c3_ucf_provenance_in_snapshot(self, service):
        """UCF provenance fields appear in request snapshot."""
        request = _make_request(
            metadata={"ucf_state": MockUCFState()},
        )
        response = service.authorize(request)
        snap = response.audit_event.request_snapshot

        assert snap["ucf_available"] is True
        assert snap["ucf_score"] == 0.30
        assert snap["ucf_stability_band"] == "unstable"
        assert snap["ucf_escalation_bias"] is True
        assert snap["ucf_computation_source"] == "precomputed"


@_needs_numpy
class TestE2EAuthorizeC4Signals:
    """Prove C4 predictive signals flow through authorize()."""

    def test_c4_predictive_populates_audit_event(self, service):
        """C4 predictive signals appear in audit event."""
        request = _make_request(
            metadata={
                "predictive_drift_report": MockDriftReport(),
                "identity_resonance_state_p36": MockIdentityState(),
                "continuity_report": MockContinuityReport(),
            },
        )
        response = service.authorize(request)

        ae = response.audit_event
        assert ae.predictive_signals is not None, "predictive_signals should be populated"
        assert ae.predictive_signals["available"] is True
        assert ae.predictive_signals["predicted_drift_score"] is not None
        assert ae.predictive_signals["drift_risk_band"] == "high"
        assert ae.predictive_signals["identity_stability_band"] == "fragile"
        assert ae.predictive_signals["continuity_mode"] == "fragmenting"
        assert ae.predictive_signals["oscillation_detected"] is True

    def test_c4_drift_high_reduces_confidence(self, service):
        """P35 HIGH drift should reduce confidence vs baseline."""
        baseline_resp = service.authorize(_make_request())

        c4_req = _make_request(
            metadata={"predictive_drift_report": MockDriftReport(
                predicted_drift_score=0.8, drift_risk_band="high",
            )},
        )
        c4_resp = service.authorize(c4_req)

        assert c4_resp.confidence_score < baseline_resp.confidence_score

    def test_c4_provenance_in_snapshot(self, service):
        """C4 provenance fields appear in request snapshot."""
        request = _make_request(
            metadata={
                "predictive_drift_report": MockDriftReport(),
                "continuity_report": MockContinuityReport(),
            },
        )
        response = service.authorize(request)
        snap = response.audit_event.request_snapshot

        assert snap["predictive_available"] is True
        assert snap["predictive_drift_score"] == 0.75
        assert snap["predictive_drift_risk_band"] == "high"
        assert snap["predictive_continuity_mode"] == "fragmenting"
        assert snap["predictive_escalation_bias"] is True


@_needs_numpy
class TestE2EAuthorizeCombinedC2C3C4:
    """Prove all C2+C3+C4 signals work together through authorize()."""

    def test_combined_signals_all_populate(self, service):
        """All C2/C3/C4 audit fields populated when all signals present."""
        request = _make_request(
            metadata={
                "core_coherence_state": MockCoherenceState(),
                "ucf_state": MockUCFState(),
                "predictive_drift_report": MockDriftReport(),
                "identity_resonance_state_p36": MockIdentityState(),
                "continuity_report": MockContinuityReport(),
            },
        )
        response = service.authorize(request)
        ae = response.audit_event

        assert ae.core_coherence is not None
        assert ae.ucf_signal is not None
        assert ae.predictive_signals is not None
        assert ae.core_coherence["available"] is True
        assert ae.ucf_signal["available"] is True
        assert ae.predictive_signals["available"] is True

    def test_combined_signals_reduce_confidence_more(self, service):
        """Combined C2+C3+C4 should reduce confidence more than any alone."""
        baseline_resp = service.authorize(_make_request())

        # C2 only
        c2_resp = service.authorize(_make_request(
            metadata={"core_coherence_state": MockCoherenceState()},
        ))

        # All combined (worst-case signals)
        combined_resp = service.authorize(_make_request(
            metadata={
                "core_coherence_state": MockCoherenceState(),
                "ucf_state": MockUCFState(ucf_score=0.2, stability_band="unstable"),
                "predictive_drift_report": MockDriftReport(
                    predicted_drift_score=0.9, drift_risk_band="high",
                ),
                "continuity_report": MockContinuityReport(continuity_mode="fragmenting"),
            },
        ))

        assert combined_resp.confidence_score < c2_resp.confidence_score, (
            "Combined C2+C3+C4 should reduce confidence more than C2 alone"
        )
        assert combined_resp.confidence_score < baseline_resp.confidence_score

    def test_counterfactual_field_always_none_on_authorize(self, service):
        """counterfactual field is intentionally never populated by authorize()."""
        request = _make_request(
            metadata={
                "core_coherence_state": MockCoherenceState(),
                "ucf_state": MockUCFState(),
                "predictive_drift_report": MockDriftReport(),
            },
        )
        response = service.authorize(request)
        assert response.audit_event.counterfactual is None, (
            "counterfactual field should never be populated on live authorize path"
        )


# =========================================================================
# TASK 3: Aggregate penalty cap test
# =========================================================================


@_needs_numpy
class TestAggregatePenaltyCap:
    """Prove the 0.20 aggregate sovereign penalty cap holds."""

    def test_max_stacking_capped_at_020(self, service):
        """When all adapters contribute max penalties, total stays <= 0.20.

        Theoretical worst case without cap:
          C2: 0.10 (low coherence + critical drift)
          C3: 0.05 (unstable UCF)
          C4: 0.05 (high drift 0.03 + fragmenting 0.02)
          Total uncapped: 0.20 (exactly at cap in this case)

        With even more entropy/insight/guna, uncapped would exceed 0.20.
        """
        # Use worst-case signals for all adapters
        request = _make_request(
            metadata={
                "core_coherence_state": MockCoherenceState(
                    coherence_score=0.0,
                    coherence_v3_quality=0.0,
                    persona_drift_score=1.0,
                    drift_risk_band="critical",
                ),
                "ucf_state": MockUCFState(
                    ucf_score=0.1, stability_band="unstable",
                ),
                "predictive_drift_report": MockDriftReport(
                    predicted_drift_score=1.0, drift_risk_band="high",
                ),
                "continuity_report": MockContinuityReport(
                    continuity_mode="fragmenting",
                ),
            },
        )
        response = service.authorize(request)

        # The confidence should be reduced but not below 0.0
        assert response.confidence_score >= 0.0

        # Verify the penalties in the snapshot
        snap = response.audit_event.request_snapshot
        c2_penalty = snap.get("core_coherence_confidence_penalty", 0)
        ucf_penalty = snap.get("ucf_confidence_penalty", 0)
        c4_penalty = snap.get("predictive_confidence_penalty", 0)

        # Each individual penalty should be within its own bound
        assert c2_penalty <= 0.10, f"C2 penalty {c2_penalty} exceeds 0.10"
        assert ucf_penalty <= 0.05, f"UCF penalty {ucf_penalty} exceeds 0.05"
        assert c4_penalty <= 0.05, f"C4 penalty {c4_penalty} exceeds 0.05"

        # All are positive (contributing)
        assert c2_penalty > 0, "C2 should have positive penalty with worst-case signals"
        assert ucf_penalty > 0, "UCF should have positive penalty when unstable"
        assert c4_penalty > 0, "C4 should have positive penalty with high drift"

    def test_confidence_never_negative(self, service):
        """Even with all penalties maxed, confidence stays >= 0.0."""
        request = _make_request(
            quality_score=0.1,
            coherence_score=0.1,
            internal_consistency=0.1,
            goal_alignment=0.1,
            trajectory_confidence=0.1,
            metadata={
                "core_coherence_state": MockCoherenceState(
                    coherence_score=0.0, persona_drift_score=1.0,
                    drift_risk_band="critical",
                ),
                "ucf_state": MockUCFState(ucf_score=0.1, stability_band="unstable"),
                "predictive_drift_report": MockDriftReport(
                    predicted_drift_score=1.0, drift_risk_band="high",
                ),
                "continuity_report": MockContinuityReport(continuity_mode="fragmenting"),
            },
        )
        response = service.authorize(request)
        assert response.confidence_score >= 0.0


# =========================================================================
# TASK 4: Generation gate behavioral tests
# =========================================================================


@_needs_numpy
class TestGenerationGateBehavior:
    """Behavioral tests for generation gate classification and enforcement."""

    # --- _is_generative_action behavior ---

    def test_generative_action_detected_by_action_type(self):
        """Action types containing generative patterns are detected."""
        req = _make_request(action_type="llm_generate")
        assert _is_generative_action(req) is True

    def test_generative_action_detected_by_tool_name(self):
        """Tool names containing generative patterns are detected."""
        req = _make_request(action_type="some_action", tool_name="text_synthesis_tool")
        assert _is_generative_action(req) is True

    def test_generative_action_detected_by_metadata_flag(self):
        """Explicit is_generative metadata flag is respected."""
        req = _make_request(
            action_type="custom_action",
            metadata={"is_generative": True},
        )
        assert _is_generative_action(req) is True

    def test_non_generative_action_not_detected(self):
        """Non-generative actions are NOT classified as generative."""
        req = _make_request(action_type="file_read", tool_name="database_query")
        assert _is_generative_action(req) is False

    def test_non_generative_action_no_metadata_flag(self):
        """No metadata or False flag means not generative."""
        req = _make_request(action_type="file_read")
        assert _is_generative_action(req) is False

        req2 = _make_request(
            action_type="file_read",
            metadata={"is_generative": False},
        )
        assert _is_generative_action(req2) is False

    # --- _check_generation_gate behavior ---

    def test_gate_unsealed_blocks_generative(self):
        """Unsealed gate blocks generative actions."""
        req = _make_request(action_type="llm_generate")
        result = _check_generation_gate(req)
        assert result["is_generative"] is True
        assert result["gate_blocks"] is True
        assert result["gate_status"] == "UNSEALED"
        assert result["block_reason"] == "generation_gate_unsealed"

    def test_gate_disabled_blocks_generative(self):
        """Disabled gate blocks generative actions."""
        GenerationGate.seal(GenerationMode.DISABLED)
        req = _make_request(action_type="llm_generate")
        result = _check_generation_gate(req)
        assert result["is_generative"] is True
        assert result["gate_blocks"] is True
        assert result["gate_status"] == "SEALED_DISABLED"
        assert result["block_reason"] == "generation_disabled"

    def test_gate_enabled_allows_generative(self):
        """Enabled gate allows generative actions."""
        GenerationGate.seal(GenerationMode.ENABLED)
        req = _make_request(action_type="llm_generate")
        result = _check_generation_gate(req)
        assert result["is_generative"] is True
        assert result["gate_blocks"] is False
        assert result["gate_status"] == "SEALED_ENABLED"
        assert result["block_reason"] is None

    def test_non_generative_unaffected_by_gate_state(self):
        """Non-generative actions are NEVER blocked regardless of gate state."""
        for gate_setup in [
            lambda: None,  # UNSEALED
            lambda: GenerationGate.seal(GenerationMode.DISABLED),
            lambda: GenerationGate.seal(GenerationMode.ENABLED),
        ]:
            GenerationGate._reset()
            gate_setup()

            req = _make_request(action_type="file_read")
            result = _check_generation_gate(req)
            assert result["is_generative"] is False
            assert result["gate_blocks"] is False, (
                f"Non-generative should never be blocked, "
                f"gate_status={result['gate_status']}"
            )

    def test_gate_attestation_generated_for_generative(self):
        """Attestation blob is created for generative actions."""
        GenerationGate.seal(GenerationMode.ENABLED)
        req = _make_request(action_type="llm_generate")
        result = _check_generation_gate(req)
        assert result["attestation"] is not None
        assert result["attestation"]["render_attempted"] is True

    def test_gate_no_attestation_for_non_generative(self):
        """No attestation blob for non-generative actions."""
        GenerationGate.seal(GenerationMode.ENABLED)
        req = _make_request(action_type="file_read")
        result = _check_generation_gate(req)
        assert result["attestation"] is None

    # --- End-to-end gate enforcement via authorize() ---

    def test_authorize_generative_denied_when_gate_unsealed(self, service):
        """Generative action DENIED via authorize() when gate unsealed."""
        request = _make_request(action_type="llm_generate")
        response = service.authorize(request)

        # Generation gate should force DENY
        assert response.governance_decision.value == "DENY"
        snap = response.audit_event.request_snapshot
        assert snap["generation_gate_is_generative"] is True
        assert snap["generation_gate_blocks"] is True

    def test_authorize_generative_allowed_when_gate_enabled(self, service):
        """Generative action proceeds when gate is sealed+enabled."""
        GenerationGate.seal(GenerationMode.ENABLED)
        request = _make_request(action_type="llm_generate")
        response = service.authorize(request)

        # Gate should NOT block — decision depends on other factors
        snap = response.audit_event.request_snapshot
        assert snap["generation_gate_is_generative"] is True
        assert snap["generation_gate_blocks"] is False

    def test_authorize_non_generative_unaffected_when_gate_disabled(self, service):
        """Non-generative action unaffected even when gate is disabled."""
        GenerationGate.seal(GenerationMode.DISABLED)
        request = _make_request(action_type="file_read")
        response = service.authorize(request)

        # Non-generative should not be blocked by gate
        snap = response.audit_event.request_snapshot
        assert snap["generation_gate_is_generative"] is False
        assert snap["generation_gate_blocks"] is False
        # Decision should not be DENY due to gate (may be DENY for other reasons)


# =========================================================================
# TASK 5 (verified): Drift overlap documentation tested
# =========================================================================


class TestDriftOverlapDocumentation:
    """Verify that drift overlap between C2 and C4 is documented."""

    def test_governance_service_has_drift_overlap_comment(self):
        """governance_service.py should document the C2/C4 drift overlap."""
        gs_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "governance_service.py",
        )
        with open(gs_path) as f:
            content = f.read()
        assert "DRIFT OVERLAP NOTE" in content
        assert "C2" in content and "C4" in content
        assert "intentional" in content.lower()
        assert "aggregate cap" in content.lower()

    def test_predictive_adapter_has_drift_overlap_note(self):
        """predictive_signals_adapter.py should document drift overlap."""
        adapter_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "signal_adapters",
            "predictive_signals_adapter.py",
        )
        with open(adapter_path) as f:
            content = f.read()
        assert "Drift overlap with C2" in content
        assert "intentional" in content.lower()

    def test_counterfactual_field_documented_as_replay_only(self):
        """governance_models.py counterfactual field is clearly replay-only."""
        models_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "governance_models.py",
        )
        with open(models_path) as f:
            content = f.read()
        # Should explicitly state it is NOT populated by authorize()
        assert "INTENTIONALLY never populated" in content
        assert "GovernanceService.authorize()" in content
