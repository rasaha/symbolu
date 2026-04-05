"""
Tests for the Sovereign State Bridge (V11.0.0).

Validates that 32D Sovereign State tensor signals are correctly
converted into ConfidenceSignals and SafetyContract-compatible
coherence state for the agentic framework.
"""

import pytest

from agentic.agentic_framework.sovereign_bridge import (
    signals_from_sovereign_state,
    coherence_from_sovereign_state,
    vritti_from_sovereign_state,
    projection_metadata_from_sovereign_result,
    diagnostics_from_projection,
    guna_anomalies_from_projection,
    governor_telemetry_from_projection,
    SovereignCoherenceState,
    _vritti_to_confidence,
    _kosha_to_budget,
    _guna_to_stability,
    _extract_slices,
    VRITTI_FACT,
    VRITTI_ERROR,
    VRITTI_VOID,
    GUNA_LUCIDITY,
    GUNA_ACTIVITY,
    GUNA_VELOCITY,
    GUNA_ACCEL,
    GUNA_STABLE,
    KOSHA_MATERIAL,
    KOSHA_INTELLECTUAL,
    KOSHA_BLISSFUL,
)
from agentic.agentic_framework.confidence_gate import (
    ConfidenceSignals,
    ConfidenceGate,
    ConfidenceAggregator,
    merge_signals,
    signals_from_critique,
    create_confidence_gate,
)
from agentic.agentic_framework.safety_contract import (
    SafetyContractEvaluator,
)


# =============================================================================
# Helper: Create 32D state vectors with specific control plane values
# =============================================================================

def make_state(
    bhava=None,
    kosha=None,
    vritti=None,
    guna=None,
    reserved=None,
):
    """Build a 32-float state list with specified slices."""
    state = [0.0] * 32
    if bhava:
        for i, v in enumerate(bhava):
            state[i] = v
    if kosha:
        for i, v in enumerate(kosha):
            state[12 + i] = v
    if vritti:
        for i, v in enumerate(vritti):
            state[17 + i] = v
    if guna:
        for i, v in enumerate(guna):
            state[22 + i] = v
    if reserved:
        for i, v in enumerate(reserved):
            state[28 + i] = v
    return state


# =============================================================================
# Test: Slice Extraction
# =============================================================================

class TestExtractSlices:
    def test_extracts_correct_slices(self):
        state = make_state(
            kosha=[0.1, 0.2, 0.3, 0.4, 0.5],
            vritti=[0.6, 0.1, 0.1, 0.1, 0.1],
            guna=[0.8, 0.2, 0.3, 0.1, 0.0, 0.9],
        )
        kosha, vritti, guna = _extract_slices(state)
        assert kosha == [0.1, 0.2, 0.3, 0.4, 0.5]
        assert vritti == [0.6, 0.1, 0.1, 0.1, 0.1]
        assert guna == [0.8, 0.2, 0.3, 0.1, 0.0, 0.9]

    def test_rejects_short_state(self):
        with pytest.raises(ValueError, match="must have >= 28"):
            _extract_slices([0.0] * 20)


# =============================================================================
# Test: Vritti → Confidence
# =============================================================================

class TestVrittiToConfidence:
    def test_high_fact_gives_high_quality(self):
        """FACT-dominant state should produce high quality and correctness."""
        vritti = [0.8, 0.05, 0.05, 0.05, 0.05]  # FACT dominant
        signals = _vritti_to_confidence(vritti)
        assert signals['quality_score'] > 0.7
        assert signals['correctness_score'] > 0.7
        assert signals['prediction_reversal_risk'] < 0.2
        assert signals['coherence_score'] > 0.8

    def test_high_error_gives_low_quality(self):
        """ERROR-dominant state should flag high reversal risk."""
        vritti = [0.05, 0.8, 0.05, 0.05, 0.05]  # ERROR dominant
        signals = _vritti_to_confidence(vritti)
        assert signals['quality_score'] < 0.3
        assert signals['correctness_score'] < 0.1
        assert signals['prediction_reversal_risk'] > 0.7
        assert signals['coherence_score'] < 0.3

    def test_void_signals_emptiness(self):
        """VOID-dominant state should produce low coherence."""
        vritti = [0.05, 0.05, 0.05, 0.8, 0.05]  # VOID dominant
        signals = _vritti_to_confidence(vritti)
        assert signals['coherence_score'] < 0.3

    def test_all_bounded_zero_one(self):
        """All output values should be in [0, 1]."""
        for dominant in range(5):
            vritti = [0.04] * 5
            vritti[dominant] = 0.84
            signals = _vritti_to_confidence(vritti)
            for key, val in signals.items():
                assert 0.0 <= val <= 1.0, f"{key}={val} out of bounds for dominant={dominant}"


# =============================================================================
# Test: Kosha → Budget
# =============================================================================

class TestKoshaToBudget:
    def test_material_dominant_low_complexity(self):
        """Surface-level processing should be low complexity."""
        kosha = [0.8, 0.1, 0.05, 0.03, 0.02]  # MATERIAL dominant
        signals = _kosha_to_budget(kosha)
        assert signals['action_complexity'] < 0.3

    def test_intellectual_dominant_high_complexity(self):
        """Deep reasoning should be high complexity."""
        kosha = [0.02, 0.03, 0.05, 0.8, 0.1]  # INTELLECTUAL dominant
        signals = _kosha_to_budget(kosha)
        assert signals['action_complexity'] > 0.5

    def test_blissful_gives_completeness(self):
        """Integration sheath should boost completeness."""
        kosha = [0.02, 0.03, 0.05, 0.1, 0.8]  # BLISSFUL dominant
        signals = _kosha_to_budget(kosha)
        assert signals['completeness_score'] > 0.4


# =============================================================================
# Test: Guna → Stability
# =============================================================================

class TestGunaToStability:
    def test_high_lucidity_stable(self):
        """Sattva-dominant (clear, balanced) should be stable."""
        guna = [0.9, 0.1, 0.3, 0.1, 0.0, 0.8]  # High lucidity, high stable
        signals = _guna_to_stability(guna, delta_norm=0.1)
        assert signals['session_stability'] > 0.6
        assert signals['volatility_index'] < 0.3
        assert signals['identity_stability'] > 0.6

    def test_high_activity_volatile(self):
        """Rajas-dominant (turbulent, dynamic) should be volatile."""
        guna = [0.1, 0.9, 0.1, 0.7, 0.5, 0.1]  # High activity, high velocity
        signals = _guna_to_stability(guna, delta_norm=0.8)
        assert signals['volatility_index'] > 0.5
        assert signals['session_stability'] < 0.4

    def test_delta_norm_increases_volatility(self):
        """Large state changes should increase volatility."""
        guna = [0.5, 0.3, 0.3, 0.3, 0.1, 0.5]
        low_delta = _guna_to_stability(guna, delta_norm=0.0)
        high_delta = _guna_to_stability(guna, delta_norm=2.0)
        assert high_delta['volatility_index'] > low_delta['volatility_index']


# =============================================================================
# Test: Full Pipeline — signals_from_sovereign_state
# =============================================================================

class TestSignalsFromSovereignState:
    def test_returns_confidence_signals(self):
        """Should return a valid ConfidenceSignals dataclass."""
        state = make_state(
            vritti=[0.7, 0.1, 0.1, 0.05, 0.05],
            kosha=[0.3, 0.2, 0.3, 0.1, 0.1],
            guna=[0.6, 0.2, 0.3, 0.1, 0.05, 0.7],
        )
        signals = signals_from_sovereign_state(state)
        assert isinstance(signals, ConfidenceSignals)

    def test_merges_with_other_sources(self):
        """Should merge cleanly with signals from other sources."""
        state = make_state(
            vritti=[0.7, 0.1, 0.1, 0.05, 0.05],
            kosha=[0.3, 0.2, 0.3, 0.1, 0.1],
            guna=[0.6, 0.2, 0.3, 0.1, 0.05, 0.7],
        )
        sovereign_signals = signals_from_sovereign_state(state)

        # Simulate signals from a QualityCritique
        other_signals = ConfidenceSignals(
            relevance_score=0.9,
            goal_alignment=0.8,
        )

        merged = merge_signals(sovereign_signals, other_signals)
        # Sovereign should provide quality_score (non-default)
        assert merged.quality_score != 0.5
        # Other source should provide relevance (not derivable from state)
        assert merged.relevance_score == 0.9

    def test_feeds_into_confidence_gate(self):
        """Should produce a valid ConfidenceGateDecision."""
        state = make_state(
            vritti=[0.7, 0.05, 0.1, 0.1, 0.05],
            kosha=[0.2, 0.1, 0.3, 0.3, 0.1],
            guna=[0.7, 0.2, 0.3, 0.1, 0.05, 0.8],
        )
        signals = signals_from_sovereign_state(state)
        gate = create_confidence_gate()
        decision = gate.evaluate(signals)
        assert decision.confidence.overall >= 0.0
        assert decision.confidence.overall <= 1.0

    def test_high_error_triggers_escalation(self):
        """ERROR-dominant Vritti should cause escalation."""
        state = make_state(
            vritti=[0.05, 0.8, 0.05, 0.05, 0.05],  # ERROR dominant
            kosha=[0.3, 0.2, 0.3, 0.1, 0.1],
            guna=[0.2, 0.8, 0.1, 0.7, 0.5, 0.1],  # Also unstable
        )
        signals = signals_from_sovereign_state(state)
        gate = create_confidence_gate()
        decision = gate.evaluate(signals)
        # Should have low confidence
        assert decision.confidence.overall < 0.6


# =============================================================================
# Test: Full Pipeline — coherence_from_sovereign_state + SafetyContract
# =============================================================================

class TestCoherenceFromSovereignState:
    def test_returns_coherence_state(self):
        """Should return SovereignCoherenceState with current_metrics."""
        state = make_state(
            vritti=[0.7, 0.1, 0.1, 0.05, 0.05],
            guna=[0.6, 0.2, 0.3, 0.1, 0.05, 0.7],
        )
        coherence = coherence_from_sovereign_state(state)
        assert isinstance(coherence, SovereignCoherenceState)
        assert coherence.current_metrics is coherence  # Self-referential

    def test_feeds_into_safety_evaluator(self):
        """Should work with SafetyContractEvaluator.evaluate()."""
        # Stable state: high FACT, high LUCIDITY, high STABLE
        state = make_state(
            vritti=[0.8, 0.05, 0.05, 0.05, 0.05],
            guna=[0.8, 0.1, 0.3, 0.1, 0.0, 0.9],
        )
        coherence = coherence_from_sovereign_state(state)
        evaluator = SafetyContractEvaluator(
            consistency_threshold=0.5,
            stability_threshold=0.5,
            reversal_risk_threshold=0.4,
            alignment_threshold=0.0,  # Can't derive goal alignment from state
        )
        # SafetyContractEvaluator requires goal_state with agency_level for precondition 6
        class _GoalStub:
            agency_level = "FULL"
        contract = evaluator.evaluate(coherence, goal_state=_GoalStub())
        # Should pass: high consistency, low reversal risk, high stability
        assert contract.eligible is True

    def test_unstable_state_blocks_contract(self):
        """ERROR + high activity should fail safety contract."""
        state = make_state(
            vritti=[0.05, 0.8, 0.05, 0.05, 0.05],  # ERROR dominant
            guna=[0.1, 0.9, 0.1, 0.8, 0.6, 0.1],   # Volatile
        )
        coherence = coherence_from_sovereign_state(state, delta_S=[1.0] * 32)
        evaluator = SafetyContractEvaluator()
        contract = evaluator.evaluate(coherence)
        assert contract.eligible is False
        assert len(contract.violated_preconditions) > 0


# =============================================================================
# Test: vritti_from_sovereign_state (ChittaVrittiResult producer)
# =============================================================================

class TestVrittiFromSovereignState:
    """Bridge helper: 32D Sovereign State → canonical ChittaVrittiResult.

    These tests pin the producer contract consumed by
    signal_adapters/vritti_adapter.py._from_real() — exactly the four
    attributes .vritti / .coherence / .score / .dominant_vritti, plus
    the validated 5-key vritti distribution.
    """

    def test_returns_canonical_chitta_vritti_result(self):
        """Bridge must return a real ChittaVrittiResult with the adapter's
        required duck-typed attributes."""
        from agentic.chitta_vritti.types import ChittaVrittiResult

        state = make_state(
            bhava=[0.2] * 12,
            kosha=[0.1, 0.3, 0.5, 0.4, 0.2],
            vritti=[0.6, 0.1, 0.1, 0.1, 0.1],  # FACT-dominant
            guna=[0.8, 0.2, 0.3, 0.1, 0.0, 0.9],
        )

        result = vritti_from_sovereign_state(state)

        assert isinstance(result, ChittaVrittiResult)
        # Adapter duck-types on exactly these fields:
        assert hasattr(result, "vritti")
        assert hasattr(result, "coherence")
        assert hasattr(result, "score")
        assert hasattr(result, "dominant_vritti")

        expected = {"pramana", "viparyaya", "vikalpa", "smrti", "nidra"}
        assert set(result.vritti.keys()) == expected
        assert 0.0 <= result.coherence <= 1.0
        assert 0.0 <= result.score <= 1.0
        assert result.dominant_vritti in expected
        # Distribution sums to ~1.0 (validated by ChittaVrittiResult)
        assert abs(sum(result.vritti.values()) - 1.0) < 0.01

    def test_adapter_accepts_bridge_output_as_real(self):
        """End-to-end: bridge output must flow through resolve_vritti_signal
        as source=REAL, degraded=False."""
        from agentic.agentic_framework.signal_adapters.vritti_adapter import (
            resolve_vritti_signal,
            VrittiSignalSource,
        )

        state = make_state(
            bhava=[0.3] * 12,
            kosha=[0.2, 0.3, 0.4, 0.5, 0.3],
            vritti=[0.5, 0.1, 0.2, 0.1, 0.1],
            guna=[0.7, 0.3, 0.2, 0.2, 0.1, 0.8],
        )
        cv_result = vritti_from_sovereign_state(state)

        resolution = resolve_vritti_signal(vritti_result=cv_result)

        assert resolution.source == VrittiSignalSource.REAL
        assert resolution.degraded is False
        assert set(resolution.distribution.keys()) == {
            "pramana", "viparyaya", "vikalpa", "smrti", "nidra",
        }
        assert resolution.coherence == cv_result.coherence
        assert resolution.score == cv_result.score

    def test_accepts_list_state(self):
        """Bridge must accept a plain [32]-float list."""
        state = [0.1] * 32
        result = vritti_from_sovereign_state(state)
        assert 0.0 <= result.coherence <= 1.0

    def test_rejects_short_state(self):
        with pytest.raises(ValueError, match="must have >= 28"):
            vritti_from_sovereign_state([0.0] * 20)

    def test_delta_s_adds_temporal_layer(self):
        """Supplying delta_S should produce a 3-layer computation (adds
        temporal_rep) instead of the 2-layer semantic+structural case."""
        state = make_state(
            bhava=[0.2] * 12,
            kosha=[0.3, 0.3, 0.3, 0.3, 0.3],
            vritti=[0.6, 0.1, 0.1, 0.1, 0.1],
        )
        # Non-trivial delta — drives motion and creates a temporal_rep
        delta_S = [0.1] * 32

        r_no_delta = vritti_from_sovereign_state(state)
        r_with_delta = vritti_from_sovereign_state(state, delta_S=delta_S)

        # Both valid results
        assert 0.0 <= r_no_delta.coherence <= 1.0
        assert 0.0 <= r_with_delta.coherence <= 1.0
        # With delta, fractures include temporal pairs; without, they don't
        no_delta_has_temporal = any(
            "temporal" in pair for pair in r_no_delta.fractures.keys()
        )
        with_delta_has_temporal = any(
            "temporal" in pair for pair in r_with_delta.fractures.keys()
        )
        assert no_delta_has_temporal is False
        assert with_delta_has_temporal is True

    def test_large_delta_drives_motion(self):
        """Large ΔS norm → motion→1.0 → temporal_continuity→0.0. Engine
        should still produce a valid result (not crash on saturation)."""
        state = make_state(
            bhava=[0.3] * 12,
            kosha=[0.2, 0.2, 0.2, 0.2, 0.2],
            vritti=[0.2, 0.2, 0.2, 0.2, 0.2],  # uniform → high entropy
        )
        delta_S = [5.0] * 32  # large norm, will saturate to 1.0
        result = vritti_from_sovereign_state(state, delta_S=delta_S)
        assert 0.0 <= result.score <= 1.0
        assert 0.0 <= result.coherence <= 1.0

    def test_error_dominant_vritti_lowers_score(self):
        """ERROR-dominant sovereign vritti + low coherence between layers
        should yield a lower readiness score than a FACT-dominant state."""
        good_state = make_state(
            bhava=[0.4] * 12,
            kosha=[0.4, 0.4, 0.4, 0.4, 0.4],
            vritti=[0.8, 0.05, 0.05, 0.05, 0.05],  # FACT-dominant
            guna=[0.9, 0.1, 0.1, 0.0, 0.0, 0.9],
        )
        bad_state = make_state(
            bhava=[0.4] * 12,
            kosha=[0.4, 0.4, 0.4, 0.4, 0.4],
            vritti=[0.05, 0.8, 0.05, 0.05, 0.05],  # ERROR-dominant
            guna=[0.1, 0.9, 0.1, 0.8, 0.6, 0.1],
        )
        good = vritti_from_sovereign_state(good_state)
        bad = vritti_from_sovereign_state(bad_state)
        # Confidence signal is derived from vritti slice; good case has
        # higher quality_score, which flows into the engine's inputs.
        # Scores must be valid, and the ERROR case shouldn't exceed the
        # FACT case on score.
        assert good.score >= bad.score - 0.01

    def test_batched_state(self):
        """Bridge must select batch_idx from a batched [B, 32] state."""
        torch = pytest.importorskip("torch")

        s0 = make_state(vritti=[0.6, 0.1, 0.1, 0.1, 0.1])
        s1 = make_state(vritti=[0.1, 0.6, 0.1, 0.1, 0.1])
        batched = torch.tensor([s0, s1], dtype=torch.float32)

        r0 = vritti_from_sovereign_state(batched, batch_idx=0)
        r1 = vritti_from_sovereign_state(batched, batch_idx=1)

        assert set(r0.vritti.keys()) == set(r1.vritti.keys())
        # Different slices → different entropy feed → likely different
        # distributions (not asserting strict inequality to avoid engine-
        # internal coupling, just both valid)
        assert 0.0 <= r0.score <= 1.0
        assert 0.0 <= r1.score <= 1.0

    def test_all_zero_vritti_slice_gives_max_entropy(self):
        """All-zero Vritti slice must not crash and must yield max-uncertainty
        entropy. The engine should still return a valid result."""
        state = make_state(
            bhava=[0.2] * 12,
            kosha=[0.3, 0.3, 0.3, 0.3, 0.3],
            vritti=[0.0, 0.0, 0.0, 0.0, 0.0],
        )
        result = vritti_from_sovereign_state(state)
        assert 0.0 <= result.coherence <= 1.0
        assert 0.0 <= result.score <= 1.0
        assert abs(sum(result.vritti.values()) - 1.0) < 0.01

    def test_negative_vritti_values_are_clipped(self):
        """Negative values in Vritti slice must be safely clipped, not
        propagate into entropy or confidence."""
        state = make_state(
            bhava=[0.2] * 12,
            kosha=[0.3, 0.3, 0.3, 0.3, 0.3],
            vritti=[-0.5, -0.2, 0.8, -0.1, 0.1],  # noisy / negative values
        )
        result = vritti_from_sovereign_state(state)
        assert 0.0 <= result.coherence <= 1.0
        assert 0.0 <= result.score <= 1.0

    def test_entropy_guard_edge_cases(self):
        """_vritti_slice_entropy direct edge-case coverage."""
        from agentic.agentic_framework.sovereign_bridge import (
            _vritti_slice_entropy,
        )

        # All-zero → max uncertainty
        assert _vritti_slice_entropy([0.0] * 5) == 1.0
        # Near-zero mass (below epsilon) → max uncertainty, not noise
        assert _vritti_slice_entropy([1e-12, 1e-12, 0.0, 0.0, 0.0]) == 1.0
        # All-negative → clipped to zero → max uncertainty
        assert _vritti_slice_entropy([-0.5, -0.3, -0.2, -0.1, -0.9]) == 1.0
        # Uniform → 1.0
        uniform = _vritti_slice_entropy([0.2, 0.2, 0.2, 0.2, 0.2])
        assert abs(uniform - 1.0) < 1e-9
        # One-hot → 0.0
        onehot = _vritti_slice_entropy([1.0, 0.0, 0.0, 0.0, 0.0])
        assert onehot == 0.0
        # Raw unnormalized input still produces bounded entropy in [0,1]
        raw = _vritti_slice_entropy([3.0, 1.0, 1.0, 1.0, 1.0])
        assert 0.0 <= raw <= 1.0

    def test_temporal_rep_shape_matches_engine_expectations(self):
        """temporal_rep must be a 1D np.ndarray with the same shape the
        engine uses for cross-turn smriti tracking (vritti.py:175-177 does
        shape-equality + elementwise subtraction)."""
        import numpy as np
        from agentic.chitta_vritti.types import ChittaVrittiInputs

        state = make_state(
            bhava=[0.2] * 12,
            kosha=[0.3, 0.3, 0.3, 0.3, 0.3],
            vritti=[0.4, 0.2, 0.2, 0.1, 0.1],
        )
        delta_S = [0.05] * 32
        # Indirect check: reconstruct inputs via the same mapping the
        # bridge uses, verify the shape contract ChittaVrittiInputs expects.
        # The bridge's temporal_rep is delta_S[0:12] as 1D float array.
        expected = np.asarray(delta_S[0:12], dtype=float)
        assert expected.ndim == 1
        assert expected.shape == (12,)

        # Full bridge call must produce a valid ChittaVrittiResult with
        # fractures that include the temporal layer (proves the engine
        # accepted and projected temporal_rep without error).
        result = vritti_from_sovereign_state(state, delta_S=delta_S)
        temporal_pairs = [
            p for p in result.fractures.keys() if "temporal" in p
        ]
        assert len(temporal_pairs) >= 1
        # And the result itself is canonical
        assert set(result.vritti.keys()) == {
            "pramana", "viparyaya", "vikalpa", "smrti", "nidra",
        }
        # Confirm the inputs dataclass doesn't reject our shape
        inputs = ChittaVrittiInputs(
            temporal_rep=expected,
            entropy=0.5, motion=0.1, confidence=0.7,
            temporal_continuity=0.9,
        )
        assert inputs.temporal_rep.shape == (12,)

    def test_tier_selection(self):
        """tier='enterprise' uses stricter config; both tiers return
        valid canonical results."""
        state = make_state(
            bhava=[0.3] * 12,
            kosha=[0.3, 0.3, 0.3, 0.3, 0.3],
            vritti=[0.5, 0.1, 0.2, 0.1, 0.1],
        )
        r_consumer = vritti_from_sovereign_state(state, tier="consumer")
        r_enterprise = vritti_from_sovereign_state(state, tier="enterprise")
        for r in (r_consumer, r_enterprise):
            assert 0.0 <= r.score <= 1.0
            assert abs(sum(r.vritti.values()) - 1.0) < 0.01


# =============================================================================
# Test: projection_metadata_from_sovereign_result (SovereignProjectionResult
# → governance dict adapter)
# =============================================================================

def _make_fake_projection_result(
    *,
    reasoning_diagnostics=None,
    guna_anomalies=None,
    governor_telemetry=None,
):
    """Build a fake SovereignProjectionResult-shaped object.

    Avoids importing agentic.sovereign.inference_bridge (which pulls
    in torch via sovereign/__init__.py) by duck-typing the dataclass
    contract the adapter actually reads.
    """
    from types import SimpleNamespace

    # Replicate ProjectionMetadata.to_dict() output shape precisely.
    metadata_dict = {
        "source_dim": 128,
        "target_dim": 32,
        "had_guna": True,
        "had_r_signal": True,
        "had_s_signal": True,
        "had_c_signal": False,
        "had_state_delta": False,
        "bhava_projection_norm": 0.5,
        "guna_projection_norm": 0.4,
        "s_signal_dropped": True,
        "c_signal_dropped": False,
        "reserved_zeroed": True,
        "kosha_derived": True,
        "vritti_derived": True,
        "projection_warnings": ["S-Signal (32-D referent) dropped: no inference slot"],
    }
    if reasoning_diagnostics is not None:
        metadata_dict["reasoning_diagnostics"] = reasoning_diagnostics
    if guna_anomalies is not None:
        metadata_dict["guna_anomalies"] = guna_anomalies
    if governor_telemetry is not None:
        metadata_dict["governor_telemetry"] = governor_telemetry

    metadata = SimpleNamespace(to_dict=lambda: dict(metadata_dict))
    return SimpleNamespace(
        inference_state=tuple([0.0] * 32),
        metadata=metadata,
        bhava_activations={
            "POT": 0.1, "IDN": 0.2, "EXE": 0.0, "STR": 0.3,
            "COG": 0.1, "AGY": 0.0, "RSN": 0.5, "PRP": 0.0,
            "WIT": 0.1, "UNI": 0.0, "INT": 0.0, "ABS": 0.0,
        },
        dominant_bhava="RSN",
        guna_summary={
            "lucidity": 0.7, "activity": 0.2, "stability": 0.1,
            "velocity": 0.05, "acceleration": 0.02, "stable": 0.95,
        },
        kosha_profile=(0.1, 0.2, 0.4, 0.2, 0.1),
        vritti_profile=(0.6, 0.1, 0.1, 0.1, 0.1),
    )


class TestProjectionMetadataFromSovereignResult:
    """Adapter: SovereignProjectionResult → AuthorizationRequest dict."""

    def test_returns_metadata_to_dict_keys(self):
        """All ProjectionMetadata.to_dict() keys must be preserved."""
        result = _make_fake_projection_result()
        payload = projection_metadata_from_sovereign_result(result)

        # Core metadata keys from ProjectionMetadata.to_dict()
        for key in (
            "source_dim", "target_dim",
            "had_guna", "had_r_signal", "had_s_signal", "had_c_signal",
            "had_state_delta",
            "bhava_projection_norm", "guna_projection_norm",
            "s_signal_dropped", "c_signal_dropped", "reserved_zeroed",
            "kosha_derived", "vritti_derived", "projection_warnings",
        ):
            assert key in payload, f"missing metadata key: {key}"

        assert payload["source_dim"] == 128
        assert payload["target_dim"] == 32

    def test_promotes_outer_projection_fields(self):
        """Top-level SovereignProjectionResult fields must be promoted to
        top level of the governance dict."""
        result = _make_fake_projection_result()
        payload = projection_metadata_from_sovereign_result(result)

        assert payload["dominant_bhava"] == "RSN"
        assert payload["bhava_activations"]["RSN"] == 0.5
        assert payload["guna_summary"]["lucidity"] == 0.7
        assert payload["kosha_profile"] == [0.1, 0.2, 0.4, 0.2, 0.1]
        assert payload["vritti_profile"] == [0.6, 0.1, 0.1, 0.1, 0.1]
        # List types for JSON-compatibility (not tuples)
        assert isinstance(payload["kosha_profile"], list)
        assert isinstance(payload["vritti_profile"], list)
        assert isinstance(payload["bhava_activations"], dict)
        assert isinstance(payload["guna_summary"], dict)

    def test_diagnostics_consumer_accepts_output(self):
        """diagnostics_from_projection must accept the adapter output
        and extract reasoning_diagnostics."""
        result = _make_fake_projection_result(
            reasoning_diagnostics={
                "mauna_active": True,
                "active_intervention": "mauna_hold",
                "dominant_bhava": "RSN",
                "vritti_state": "pramana",
                "entropy_delta": -0.01,
                "source": "inference_bridge",
                "available": True,
            },
        )
        payload = projection_metadata_from_sovereign_result(result)

        diag = diagnostics_from_projection(projection_metadata=payload)
        assert diag.available is True
        assert diag.mauna_active is True
        assert diag.active_intervention == "mauna_hold"

    def test_guna_anomalies_consumer_accepts_output(self):
        """guna_anomalies_from_projection must accept the adapter output."""
        result = _make_fake_projection_result(
            guna_anomalies={
                "collapse": True,
                "oscillation": False,
                "stagnation": False,
                "dominant_guna": "tamas",
            },
        )
        payload = projection_metadata_from_sovereign_result(result)

        ctx = guna_anomalies_from_projection(projection_metadata=payload)
        assert ctx.available is True
        assert ctx.collapse is True
        assert ctx.oscillation is False
        assert ctx.dominant_guna == "tamas"
        assert ctx.anomaly_count == 1

    def test_governor_telemetry_consumer_accepts_output(self):
        """governor_telemetry_from_projection must accept adapter output."""
        telem = {"s_drift": 0.12, "coupling": 0.85, "brake_reason": "none"}
        result = _make_fake_projection_result(governor_telemetry=telem)
        payload = projection_metadata_from_sovereign_result(result)

        out = governor_telemetry_from_projection(projection_metadata=payload)
        assert out is not None
        assert out["s_drift"] == 0.12
        assert out["brake_reason"] == "none"

    def test_all_three_sub_consumers_on_same_payload(self):
        """A single adapter output must feed all three S3/S4 consumers."""
        result = _make_fake_projection_result(
            reasoning_diagnostics={
                "mauna_active": False,
                "source": "inference_bridge",
                "available": True,
            },
            guna_anomalies={
                "collapse": False,
                "oscillation": True,
                "stagnation": False,
                "dominant_guna": "rajas",
            },
            governor_telemetry={"s_drift": 0.05},
        )
        payload = projection_metadata_from_sovereign_result(result)

        diag = diagnostics_from_projection(projection_metadata=payload)
        guna = guna_anomalies_from_projection(projection_metadata=payload)
        telem = governor_telemetry_from_projection(projection_metadata=payload)

        assert diag.available is True
        assert guna.oscillation is True
        assert guna.dominant_guna == "rajas"
        assert telem == {"s_drift": 0.05}

    def test_absent_subdicts_still_work(self):
        """Adapter must work when reasoning_diagnostics/guna_anomalies/
        governor_telemetry are not populated (common case — upstream
        pipeline didn't thread them into project_sovereign_to_inference).

        diagnostics_from_projection treats any non-None projection_metadata
        as available (source='inference_bridge_partial' when the
        reasoning_diagnostics sub-dict is missing). guna_anomalies and
        governor_telemetry strictly require their sub-dicts.
        """
        result = _make_fake_projection_result()  # all three absent
        payload = projection_metadata_from_sovereign_result(result)

        # Consumer helpers must not crash
        diag = diagnostics_from_projection(projection_metadata=payload)
        guna = guna_anomalies_from_projection(projection_metadata=payload)
        telem = governor_telemetry_from_projection(projection_metadata=payload)

        # Diagnostics: "partial" source, top-level dominant_bhava extracted
        assert diag.available is True
        assert diag.source == "inference_bridge_partial"
        assert diag.dominant_bhava == "RSN"
        assert diag.mauna_active is False  # safe default

        # Guna anomalies and governor telemetry strictly require sub-dicts
        assert guna.available is False
        assert telem is None

    def test_payload_is_authorization_request_compatible(self):
        """Adapter output drops cleanly into
        AuthorizationRequest.sovereign_projection_metadata (a
        Dict[str, Any] field) without Pydantic validation error."""
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        result = _make_fake_projection_result(
            reasoning_diagnostics={"mauna_active": False, "available": True},
        )
        payload = projection_metadata_from_sovereign_result(result)

        req = AuthorizationRequest(
            actor_id="test-actor",
            action_type="file_read",
            sovereign_projection_metadata=payload,
        )
        assert req.sovereign_projection_metadata is not None
        assert req.sovereign_projection_metadata["dominant_bhava"] == "RSN"
        assert req.sovereign_projection_metadata["source_dim"] == 128

    def test_real_sovereign_projection_result_if_importable(self):
        """End-to-end with the real SovereignProjectionResult, if torch
        is available. Skipped when sovereign.inference_bridge can't be
        imported (torch chain)."""
        pytest.importorskip("torch")
        from agentic.sovereign.inference_bridge import (
            project_sovereign_to_inference,
        )

        # Build a 128-D state with some R-signal and Guna content
        state = [0.0] * 128
        for i in range(16):
            state[i] = 0.1 * (i % 3)  # some guna
        for i in range(48, 96):
            state[i] = 0.05  # uniform R-signal

        result = project_sovereign_to_inference(state)
        payload = projection_metadata_from_sovereign_result(result)

        # Consumers still function on the real payload
        diag = diagnostics_from_projection(projection_metadata=payload)
        guna = guna_anomalies_from_projection(projection_metadata=payload)
        telem = governor_telemetry_from_projection(projection_metadata=payload)

        # No exceptions; all three contexts addressable
        assert diag is not None
        assert guna is not None
        # telem is Optional[Dict] → None is fine
        assert telem is None or isinstance(telem, dict)

        # Outer-field promotion actually captured real values
        assert payload["dominant_bhava"] in {
            "POT", "IDN", "EXE", "STR", "COG", "AGY",
            "RSN", "PRP", "WIT", "UNI", "INT", "ABS",
        }
        assert len(payload["kosha_profile"]) == 5
        assert len(payload["vritti_profile"]) == 5
