"""
Unit Tests for Signal Wiring
============================

Symbol-U v2.6.1 - Deterministic Signal Wiring Tests

Tests the deterministic wiring of Entropy (H) and Motion (M) signals
from the pipeline into the Guna modulation layer.

Test Categories:
    1. Entropy (H) computation - 3 modes
    2. Motion delta computation - semantic, structural, experiential
    3. Motion (M) computation - 4 modes
    4. Signal wiring integration
    5. Audit trail completeness
    6. Pipeline integration

All tests verify:
    - Determinism (same inputs -> same outputs)
    - Correct formula application
    - Proper normalization to [0, 1]
    - Complete audit trails
"""

import math
import pytest
from typing import Dict

from symbolu.guna_modulation import (
    # Constants
    LN_3,
    LN_5,
    LN_10,
    MAX_STRUCTURAL_JUMPS,
    EXPERIENTIAL_MOTION_INTENTS,
    # Enums
    EntropyMode,
    MotionMode,
    ModulationTier,
    # Types
    SignalWiringConfig,
    EntropyWiringAudit,
    MotionWiringAudit,
    SignalWiringAudit,
    WiredSignals,
    # Functions
    compute_H,
    compute_semantic_delta,
    compute_structural_delta,
    compute_experiential_delta,
    compute_M,
    compute_M_from_raw,
    wire_signals,
    wire_signals_simple,
    # Pipeline integration
    PipelineModulationEngine,
    IntegratedModulationResult,
    create_pipeline_engine,
    create_default_pipeline_engine,
    modulate_from_pipeline,
)


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Test that wiring constants are correctly defined."""

    def test_ln_constants_are_correct(self):
        """Verify logarithmic constants match mathematical values."""
        assert abs(LN_3 - math.log(3)) < 1e-10
        assert abs(LN_5 - math.log(5)) < 1e-10
        assert abs(LN_10 - math.log(10)) < 1e-10

    def test_max_structural_jumps_is_positive(self):
        """Verify MAX_STRUCTURAL_JUMPS is a positive integer."""
        assert MAX_STRUCTURAL_JUMPS > 0
        assert isinstance(MAX_STRUCTURAL_JUMPS, int)

    def test_experiential_intents_are_frozen(self):
        """Verify experiential intents are a frozenset."""
        assert isinstance(EXPERIENTIAL_MOTION_INTENTS, frozenset)
        assert "directive" in EXPERIENTIAL_MOTION_INTENTS
        assert "corrective" in EXPERIENTIAL_MOTION_INTENTS
        assert "inverse_jolt" in EXPERIENTIAL_MOTION_INTENTS


# =============================================================================
# Test Entropy (H) Computation
# =============================================================================

class TestComputeH:
    """Test entropy signal wiring with all three modes."""

    def test_guna_mode_formula(self):
        """Test GUNA mode: H = H_G / ln(3)."""
        H_G = 0.5  # mid-range
        H, audit = compute_H(H_G=H_G, H_D=1.0, H_K=0.5, mode=EntropyMode.GUNA)

        expected = H_G / LN_3
        assert abs(H - expected) < 1e-10
        assert audit.entropy_mode == "guna"
        assert abs(audit.H_raw - H_G) < 1e-10

    def test_dimensional_mode_formula(self):
        """Test DIMENSIONAL mode: H = H_D / ln(10)."""
        H_D = 1.5
        H, audit = compute_H(H_G=0.5, H_D=H_D, H_K=0.5, mode=EntropyMode.DIMENSIONAL)

        expected = H_D / LN_10
        assert abs(H - expected) < 1e-10
        assert audit.entropy_mode == "dimensional"
        assert abs(audit.H_raw - H_D) < 1e-10

    def test_kosha_mode_formula(self):
        """Test KOSHA mode: H = H_K / ln(5)."""
        H_K = 0.8
        H, audit = compute_H(H_G=0.5, H_D=1.0, H_K=H_K, mode=EntropyMode.KOSHA)

        expected = H_K / LN_5
        assert abs(H - expected) < 1e-10
        assert audit.entropy_mode == "kosha"
        assert abs(audit.H_raw - H_K) < 1e-10

    def test_guna_at_max_gives_H_1(self):
        """Test that H_G = ln(3) produces H = 1.0."""
        H, audit = compute_H(H_G=LN_3, H_D=0, H_K=0, mode=EntropyMode.GUNA)
        assert abs(H - 1.0) < 1e-10

    def test_dimensional_at_max_gives_H_1(self):
        """Test that H_D = ln(10) produces H = 1.0."""
        H, audit = compute_H(H_G=0, H_D=LN_10, H_K=0, mode=EntropyMode.DIMENSIONAL)
        assert abs(H - 1.0) < 1e-10

    def test_kosha_at_max_gives_H_1(self):
        """Test that H_K = ln(5) produces H = 1.0."""
        H, audit = compute_H(H_G=0, H_D=0, H_K=LN_5, mode=EntropyMode.KOSHA)
        assert abs(H - 1.0) < 1e-10

    def test_zero_entropy_gives_H_0(self):
        """Test that zero entropy produces H = 0."""
        for mode in EntropyMode:
            H, audit = compute_H(H_G=0, H_D=0, H_K=0, mode=mode)
            assert H == 0.0

    def test_clamping_below_zero(self):
        """Test that negative entropy is clamped to 0."""
        H, audit = compute_H(H_G=-1.0, H_D=0, H_K=0, mode=EntropyMode.GUNA)
        assert H == 0.0
        assert audit.H_raw == 0.0

    def test_clamping_above_max(self):
        """Test that entropy above max is clamped."""
        H, audit = compute_H(H_G=10.0, H_D=0, H_K=0, mode=EntropyMode.GUNA)
        assert H == 1.0
        assert abs(audit.H_raw - LN_3) < 1e-10

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        inputs = (0.7, 1.2, 0.9, EntropyMode.GUNA)
        H1, _ = compute_H(*inputs)
        H2, _ = compute_H(*inputs)
        assert H1 == H2

    def test_audit_record_completeness(self):
        """Test that audit record contains all required fields."""
        H, audit = compute_H(H_G=0.5, H_D=1.0, H_K=0.3, mode=EntropyMode.GUNA)

        assert hasattr(audit, "entropy_mode")
        assert hasattr(audit, "H_raw")
        assert hasattr(audit, "H_normalized")

        d = audit.to_dict()
        assert "entropy_mode" in d
        assert "H_raw" in d
        assert "H_normalized" in d


# =============================================================================
# Test Semantic Delta Computation
# =============================================================================

class TestComputeSemanticDelta:
    """Test semantic motion (delta_sem) computation."""

    def test_identical_vectors_give_zero_delta(self):
        """Test that identical vectors produce delta_sem = 0."""
        vec = {"a": 0.5, "b": 0.5}
        delta = compute_semantic_delta(vec, vec)
        assert abs(delta) < 1e-10

    def test_orthogonal_vectors_give_delta_1(self):
        """Test that orthogonal vectors produce delta_sem = 1."""
        vec_a = {"x": 1.0, "y": 0.0}
        vec_b = {"x": 0.0, "y": 1.0}
        delta = compute_semantic_delta(vec_a, vec_b)
        assert abs(delta - 1.0) < 1e-10

    def test_opposite_vectors_give_delta_2(self):
        """Test that opposite vectors produce delta_sem = 2 (clamped to 1)."""
        vec_a = {"x": 1.0}
        vec_b = {"x": -1.0}
        delta = compute_semantic_delta(vec_a, vec_b)
        # cosine_sim = -1, so delta = 1 - (-1) = 2, clamped to 1
        assert delta == 1.0

    def test_empty_vectors_give_zero(self):
        """Test that empty vectors produce delta_sem = 0."""
        delta = compute_semantic_delta({}, {})
        assert delta == 0.0

    def test_one_empty_vector_gives_max_motion(self):
        """Test that one empty vector produces delta_sem = 1 (undefined direction)."""
        # When context has zero magnitude, direction is undefined
        # This is treated as maximum motion (unknown origin)
        delta = compute_semantic_delta({"a": 1.0}, {})
        assert delta == 1.0

    def test_partial_overlap(self):
        """Test vectors with partial overlap."""
        vec_a = {"a": 1.0, "b": 0.0}
        vec_b = {"a": 0.707, "b": 0.707}

        delta = compute_semantic_delta(vec_a, vec_b)
        # Should be > 0 but < 1
        assert 0.0 < delta < 1.0

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        vec_a = {"a": 0.3, "b": 0.7}
        vec_b = {"a": 0.6, "b": 0.4}

        delta1 = compute_semantic_delta(vec_a, vec_b)
        delta2 = compute_semantic_delta(vec_a, vec_b)
        assert delta1 == delta2


# =============================================================================
# Test Structural Delta Computation
# =============================================================================

class TestComputeStructuralDelta:
    """Test structural motion (delta_str_norm) computation."""

    def test_zero_jumps_gives_zero(self):
        """Test that zero jumps produce delta_str_norm = 0."""
        delta = compute_structural_delta(0, 0)
        assert delta == 0.0

    def test_max_jumps_gives_one(self):
        """Test that max jumps produce delta_str_norm = 1."""
        delta = compute_structural_delta(MAX_STRUCTURAL_JUMPS, 0)
        assert delta == 1.0

    def test_beyond_max_is_clamped(self):
        """Test that jumps beyond max are clamped."""
        delta = compute_structural_delta(MAX_STRUCTURAL_JUMPS + 5, 0)
        assert delta == 1.0

    def test_layer_transitions_add_to_jumps(self):
        """Test that layer transitions are added to domain jumps."""
        delta1 = compute_structural_delta(1, 0)
        delta2 = compute_structural_delta(0, 1)
        delta3 = compute_structural_delta(1, 1)

        # Should be proportional
        assert abs(delta1 - delta2) < 1e-10  # Both are 1/MAX
        assert abs(delta3 - 2 * delta1) < 1e-10  # Sum is 2/MAX

    def test_normalization_formula(self):
        """Test the normalization formula is applied correctly."""
        jumps = 3
        delta = compute_structural_delta(jumps, 0)
        expected = jumps / MAX_STRUCTURAL_JUMPS
        assert abs(delta - expected) < 1e-10

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        delta1 = compute_structural_delta(2, 1)
        delta2 = compute_structural_delta(2, 1)
        assert delta1 == delta2


# =============================================================================
# Test Experiential Delta Computation
# =============================================================================

class TestComputeExperientialDelta:
    """Test experiential motion (delta_exp) computation."""

    def test_directive_gives_one(self):
        """Test that 'directive' intent produces delta_exp = 1."""
        delta = compute_experiential_delta("directive")
        assert delta == 1.0

    def test_corrective_gives_one(self):
        """Test that 'corrective' intent produces delta_exp = 1."""
        delta = compute_experiential_delta("corrective")
        assert delta == 1.0

    def test_inverse_jolt_gives_one(self):
        """Test that 'inverse_jolt' intent produces delta_exp = 1."""
        delta = compute_experiential_delta("inverse_jolt")
        assert delta == 1.0

    def test_case_insensitive(self):
        """Test that matching is case-insensitive."""
        assert compute_experiential_delta("DIRECTIVE") == 1.0
        assert compute_experiential_delta("Corrective") == 1.0

    def test_informative_gives_zero(self):
        """Test that 'informative' intent produces delta_exp = 0."""
        delta = compute_experiential_delta("informative")
        assert delta == 0.0

    def test_neutral_gives_zero(self):
        """Test that 'neutral' intent produces delta_exp = 0."""
        delta = compute_experiential_delta("neutral")
        assert delta == 0.0

    def test_empty_gives_zero(self):
        """Test that empty string produces delta_exp = 0."""
        delta = compute_experiential_delta("")
        assert delta == 0.0

    def test_unknown_gives_zero(self):
        """Test that unknown intent produces delta_exp = 0."""
        delta = compute_experiential_delta("random_intent")
        assert delta == 0.0

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        delta1 = compute_experiential_delta("directive")
        delta2 = compute_experiential_delta("directive")
        assert delta1 == delta2


# =============================================================================
# Test Motion (M) Computation
# =============================================================================

class TestComputeM:
    """Test motion signal wiring with all four modes."""

    def test_semantic_mode(self):
        """Test SEMANTIC mode: M = delta_sem."""
        delta_sem = 0.6
        M, audit = compute_M(
            semantic_delta=delta_sem,
            structural_delta=0.3,
            experiential_delta=1.0,
            mode=MotionMode.SEMANTIC,
        )
        assert abs(M - delta_sem) < 1e-10
        assert audit.motion_mode == "semantic"

    def test_structural_mode(self):
        """Test STRUCTURAL mode: M = delta_str_norm."""
        delta_str = 0.4
        M, audit = compute_M(
            semantic_delta=0.6,
            structural_delta=delta_str,
            experiential_delta=1.0,
            mode=MotionMode.STRUCTURAL,
        )
        assert abs(M - delta_str) < 1e-10
        assert audit.motion_mode == "structural"

    def test_experiential_mode(self):
        """Test EXPERIENTIAL mode: M = delta_exp."""
        delta_exp = 1.0
        M, audit = compute_M(
            semantic_delta=0.6,
            structural_delta=0.3,
            experiential_delta=delta_exp,
            mode=MotionMode.EXPERIENTIAL,
        )
        assert abs(M - delta_exp) < 1e-10
        assert audit.motion_mode == "experiential"

    def test_composite_mode_equal_weights(self):
        """Test COMPOSITE mode with equal weights."""
        d_sem, d_str, d_exp = 0.6, 0.3, 1.0
        weights = (1.0, 1.0, 1.0)

        M, audit = compute_M(
            semantic_delta=d_sem,
            structural_delta=d_str,
            experiential_delta=d_exp,
            mode=MotionMode.COMPOSITE,
            weights=weights,
        )

        expected = (d_sem + d_str + d_exp) / 3
        assert abs(M - expected) < 1e-10
        assert audit.motion_mode == "composite"
        assert audit.weights == weights

    def test_composite_mode_unequal_weights(self):
        """Test COMPOSITE mode with unequal weights."""
        d_sem, d_str, d_exp = 0.6, 0.3, 1.0
        weights = (2.0, 1.0, 0.5)

        M, audit = compute_M(
            semantic_delta=d_sem,
            structural_delta=d_str,
            experiential_delta=d_exp,
            mode=MotionMode.COMPOSITE,
            weights=weights,
        )

        expected = (2.0 * d_sem + 1.0 * d_str + 0.5 * d_exp) / 3.5
        assert abs(M - expected) < 1e-10

    def test_composite_without_weights_raises(self):
        """Test that COMPOSITE mode without weights raises error."""
        with pytest.raises(ValueError, match="requires weights"):
            compute_M(
                semantic_delta=0.5,
                structural_delta=0.5,
                experiential_delta=0.5,
                mode=MotionMode.COMPOSITE,
                weights=None,
            )

    def test_negative_weight_raises(self):
        """Test that negative weights raise error."""
        with pytest.raises(ValueError, match="must be >= 0"):
            compute_M(
                semantic_delta=0.5,
                structural_delta=0.5,
                experiential_delta=0.5,
                mode=MotionMode.COMPOSITE,
                weights=(-1.0, 1.0, 1.0),
            )

    def test_all_zero_weights_gives_zero(self):
        """Test that all-zero weights produce M = 0."""
        M, _ = compute_M(
            semantic_delta=0.5,
            structural_delta=0.5,
            experiential_delta=0.5,
            mode=MotionMode.COMPOSITE,
            weights=(0.0, 0.0, 0.0),
        )
        assert M == 0.0

    def test_clamping_to_0_1(self):
        """Test that M is clamped to [0, 1]."""
        # All modes should clamp negative inputs
        M, _ = compute_M(
            semantic_delta=-0.5,
            structural_delta=0.5,
            experiential_delta=0.5,
            mode=MotionMode.SEMANTIC,
        )
        assert M >= 0.0

    def test_audit_record_completeness(self):
        """Test that audit record contains all required fields."""
        M, audit = compute_M(
            semantic_delta=0.5,
            structural_delta=0.3,
            experiential_delta=1.0,
            mode=MotionMode.SEMANTIC,
        )

        d = audit.to_dict()
        assert "motion_mode" in d
        assert "delta_sem" in d
        assert "delta_str_norm" in d
        assert "delta_exp" in d
        assert "M" in d

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        args = {
            "semantic_delta": 0.5,
            "structural_delta": 0.3,
            "experiential_delta": 1.0,
            "mode": MotionMode.SEMANTIC,
        }
        M1, _ = compute_M(**args)
        M2, _ = compute_M(**args)
        assert M1 == M2


# =============================================================================
# Test Wire Signals Integration
# =============================================================================

class TestWireSignals:
    """Test full signal wiring integration."""

    def test_default_config(self):
        """Test wiring with default config (GUNA, SEMANTIC)."""
        wired = wire_signals(
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8, "b": 0.2},
            context_aspect_vector={"a": 0.6, "b": 0.4},
            domain_jump_count=2,
            intent="informative",
        )

        assert 0.0 <= wired.H <= 1.0
        assert 0.0 <= wired.M <= 1.0
        assert wired.audit.entropy_audit.entropy_mode == "guna"
        assert wired.audit.motion_audit.motion_mode == "semantic"

    def test_custom_config_dimensional_structural(self):
        """Test wiring with DIMENSIONAL entropy and STRUCTURAL motion."""
        config = SignalWiringConfig(
            entropy_mode=EntropyMode.DIMENSIONAL,
            motion_mode=MotionMode.STRUCTURAL,
        )

        wired = wire_signals(
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=3,
            intent="informative",
            config=config,
        )

        assert wired.audit.entropy_audit.entropy_mode == "dimensional"
        assert wired.audit.motion_audit.motion_mode == "structural"

    def test_composite_motion_with_weights(self):
        """Test wiring with COMPOSITE motion mode and weights."""
        config = SignalWiringConfig(
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.COMPOSITE,
            composite_weights=(1.0, 0.5, 2.0),
        )

        wired = wire_signals(
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.2},
            domain_jump_count=2,
            intent="directive",
            config=config,
        )

        assert wired.audit.motion_audit.motion_mode == "composite"
        assert wired.audit.motion_audit.weights is not None

    def test_experiential_intent_triggers_motion(self):
        """Test that experiential intents trigger delta_exp = 1."""
        config = SignalWiringConfig(
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.EXPERIENTIAL,
        )

        wired = wire_signals(
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=0,
            intent="directive",
            config=config,
        )

        assert wired.M == 1.0
        assert wired.audit.motion_audit.delta_exp == 1.0

    def test_to_dict_serialization(self):
        """Test that wired signals can be serialized to dict."""
        wired = wire_signals(
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=1,
            intent="neutral",
        )

        d = wired.to_dict()
        assert "H" in d
        assert "M" in d
        assert "audit" in d

    def test_determinism(self):
        """Test that same inputs produce same outputs."""
        args = {
            "H_G": 0.5,
            "H_D": 1.0,
            "H_K": 0.3,
            "candidate_aspect_vector": {"a": 0.8},
            "context_aspect_vector": {"a": 0.6},
            "domain_jump_count": 1,
            "intent": "neutral",
        }

        wired1 = wire_signals(**args)
        wired2 = wire_signals(**args)

        assert wired1.H == wired2.H
        assert wired1.M == wired2.M


# =============================================================================
# Test Pipeline Integration
# =============================================================================

class TestPipelineIntegration:
    """Test full pipeline modulation integration."""

    def test_default_pipeline_engine(self):
        """Test creating and using default pipeline engine."""
        engine = create_default_pipeline_engine()

        result = engine.modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=1,
            intent="neutral",
        )

        assert isinstance(result, IntegratedModulationResult)
        assert 0.0 <= result.output_intensity
        assert 0.0 <= result.H <= 1.0
        assert 0.0 <= result.M <= 1.0

    def test_custom_pipeline_engine(self):
        """Test creating custom pipeline engine."""
        engine = create_pipeline_engine(
            tier=ModulationTier.ENTERPRISE_TIER_2,
            entropy_mode=EntropyMode.DIMENSIONAL,
            motion_mode=MotionMode.STRUCTURAL,
        )

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.5,
            H_G=0.5,
            H_D=1.5,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=2,
            intent="neutral",
        )

        assert result.wired_signals.audit.entropy_audit.entropy_mode == "dimensional"
        assert result.wired_signals.audit.motion_audit.motion_mode == "structural"

    def test_standalone_modulate_from_pipeline(self):
        """Test standalone modulate_from_pipeline function."""
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=1,
            intent="neutral",
            entropy_mode=EntropyMode.KOSHA,
            motion_mode=MotionMode.EXPERIENTIAL,
        )

        assert result.wired_signals.audit.entropy_audit.entropy_mode == "kosha"
        assert result.wired_signals.audit.motion_audit.motion_mode == "experiential"

    def test_integrated_result_properties(self):
        """Test that IntegratedModulationResult exposes correct properties."""
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=1,
            intent="neutral",
        )

        # Test property accessors
        assert result.output_intensity == result.modulation_result.output_intensity
        assert result.E == result.modulation_result.E
        assert result.H == result.wired_signals.H
        assert result.M == result.wired_signals.M

    def test_full_audit_trail(self):
        """Test that full audit trail is captured."""
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            H_G=0.5,
            H_D=1.0,
            H_K=0.3,
            candidate_aspect_vector={"a": 0.8},
            context_aspect_vector={"a": 0.6},
            domain_jump_count=1,
            intent="neutral",
        )

        d = result.to_dict()

        # Signal wiring audit
        assert "wired_signals" in d
        wired = d["wired_signals"]
        assert "H" in wired
        assert "M" in wired
        assert "audit" in wired

        # Modulation audit
        assert "modulation_result" in d
        mod = d["modulation_result"]
        assert "guna_vector" in mod
        assert "G" in mod
        assert "P" in mod
        assert "T" in mod
        assert "E" in mod
        assert "trace" in mod

    def test_determinism_full_pipeline(self):
        """Test that full pipeline is deterministic."""
        args = {
            "base_intensity": 0.8,
            "C_s": 0.7,
            "H_G": 0.5,
            "H_D": 1.0,
            "H_K": 0.3,
            "candidate_aspect_vector": {"a": 0.8, "b": 0.2},
            "context_aspect_vector": {"a": 0.6, "b": 0.4},
            "domain_jump_count": 1,
            "intent": "neutral",
        }

        result1 = modulate_from_pipeline(**args)
        result2 = modulate_from_pipeline(**args)

        assert result1.output_intensity == result2.output_intensity
        assert result1.E == result2.E
        assert result1.H == result2.H
        assert result1.M == result2.M


# =============================================================================
# Test Wire Signals Simple
# =============================================================================

class TestWireSignalsSimple:
    """Test simplified signal wiring with pre-computed deltas."""

    def test_basic_usage(self):
        """Test basic wire_signals_simple usage."""
        wired = wire_signals_simple(
            H_raw=0.5,
            entropy_mode=EntropyMode.GUNA,
            delta_sem=0.3,
            delta_str_norm=0.2,
            delta_exp=0.0,
            motion_mode=MotionMode.SEMANTIC,
        )

        expected_H = 0.5 / LN_3
        assert abs(wired.H - expected_H) < 1e-10
        assert abs(wired.M - 0.3) < 1e-10

    def test_all_entropy_modes(self):
        """Test all entropy modes in simple wiring."""
        for mode in EntropyMode:
            wired = wire_signals_simple(
                H_raw=0.5,
                entropy_mode=mode,
                delta_sem=0.5,
                delta_str_norm=0.5,
                delta_exp=0.5,
                motion_mode=MotionMode.SEMANTIC,
            )
            assert 0.0 <= wired.H <= 1.0

    def test_all_motion_modes(self):
        """Test all motion modes in simple wiring."""
        for mode in MotionMode:
            weights = (1.0, 1.0, 1.0) if mode == MotionMode.COMPOSITE else None
            wired = wire_signals_simple(
                H_raw=0.5,
                entropy_mode=EntropyMode.GUNA,
                delta_sem=0.5,
                delta_str_norm=0.5,
                delta_exp=0.5,
                motion_mode=mode,
                weights=weights,
            )
            assert 0.0 <= wired.M <= 1.0


# =============================================================================
# Test Enum Values
# =============================================================================

class TestEnums:
    """Test enum definitions and values."""

    def test_entropy_mode_values(self):
        """Test EntropyMode enum values."""
        assert EntropyMode.GUNA.value == "guna"
        assert EntropyMode.DIMENSIONAL.value == "dimensional"
        assert EntropyMode.KOSHA.value == "kosha"

    def test_motion_mode_values(self):
        """Test MotionMode enum values."""
        assert MotionMode.SEMANTIC.value == "semantic"
        assert MotionMode.STRUCTURAL.value == "structural"
        assert MotionMode.EXPERIENTIAL.value == "experiential"
        assert MotionMode.COMPOSITE.value == "composite"

    def test_entropy_mode_count(self):
        """Test that there are exactly 3 entropy modes."""
        assert len(EntropyMode) == 3

    def test_motion_mode_count(self):
        """Test that there are exactly 4 motion modes."""
        assert len(MotionMode) == 4
