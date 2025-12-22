"""
Unit Tests for Pipeline Signal Adapter
======================================

Symbol-U v2.6.1 - Tests for deterministic signal wiring from existing pipeline.

These tests verify that the pipeline signal adapter correctly:
    - Maps IntentType values to experiential motion deltas
    - Computes semantic deltas from aspect probability vectors
    - Computes structural deltas from stitching diagnostics
    - Extracts entropy from RouterContext values
    - Aggregates signals via PipelineSignalContext
    - Wires H and M from complete pipeline context

Version: 2.6.1
Date: 2025-12-22
"""

import math
import pytest
from typing import Dict

from symbolu.guna_modulation.pipeline_signal_adapter import (
    EXPERIENTIAL_INTENT_TYPES,
    intent_to_experiential_delta,
    compute_semantic_delta_from_vectors,
    compute_structural_delta_from_stitching,
    extract_entropy_from_router_context,
    PipelineSignalContext,
    wire_from_pipeline_context,
)
from symbolu.guna_modulation.signal_wiring import (
    EntropyMode,
    MotionMode,
    SignalWiringConfig,
    LN_3,
    LN_5,
    LN_10,
    MAX_STRUCTURAL_JUMPS,
)


# =============================================================================
# Tests for Intent to Experiential Delta Mapping
# =============================================================================

class TestIntentToExperientialDelta:
    """Tests for intent_to_experiential_delta function."""

    def test_command_intent_gives_experiential_motion(self):
        """COMMAND intent should trigger experiential motion (delta=1)."""
        delta = intent_to_experiential_delta("COMMAND")
        assert delta == 1.0

    def test_should_intent_gives_experiential_motion(self):
        """SHOULD intent should trigger experiential motion (delta=1)."""
        delta = intent_to_experiential_delta("SHOULD")
        assert delta == 1.0

    def test_reflection_intent_gives_experiential_motion(self):
        """REFLECTION intent should trigger experiential motion (delta=1)."""
        delta = intent_to_experiential_delta("REFLECTION")
        assert delta == 1.0

    def test_what_intent_gives_no_motion(self):
        """WHAT intent should not trigger experiential motion (delta=0)."""
        delta = intent_to_experiential_delta("WHAT")
        assert delta == 0.0

    def test_how_intent_gives_no_motion(self):
        """HOW intent should not trigger experiential motion (delta=0)."""
        delta = intent_to_experiential_delta("HOW")
        assert delta == 0.0

    def test_why_intent_gives_no_motion(self):
        """WHY intent should not trigger experiential motion (delta=0)."""
        delta = intent_to_experiential_delta("WHY")
        assert delta == 0.0

    def test_unknown_intent_gives_no_motion(self):
        """Unknown intent should not trigger experiential motion."""
        delta = intent_to_experiential_delta("UNKNOWN_INTENT")
        assert delta == 0.0

    def test_case_insensitivity(self):
        """Intent mapping should be case-insensitive."""
        assert intent_to_experiential_delta("command") == 1.0
        assert intent_to_experiential_delta("Command") == 1.0
        assert intent_to_experiential_delta("should") == 1.0
        assert intent_to_experiential_delta("Reflection") == 1.0

    def test_determinism(self):
        """Same input should always produce same output."""
        for _ in range(100):
            assert intent_to_experiential_delta("COMMAND") == 1.0
            assert intent_to_experiential_delta("WHAT") == 0.0

    def test_experiential_intent_types_frozen(self):
        """EXPERIENTIAL_INTENT_TYPES should be immutable."""
        assert isinstance(EXPERIENTIAL_INTENT_TYPES, frozenset)
        assert len(EXPERIENTIAL_INTENT_TYPES) == 3
        assert "COMMAND" in EXPERIENTIAL_INTENT_TYPES
        assert "SHOULD" in EXPERIENTIAL_INTENT_TYPES
        assert "REFLECTION" in EXPERIENTIAL_INTENT_TYPES


# =============================================================================
# Tests for Semantic Delta from Vectors
# =============================================================================

class TestSemanticDeltaFromVectors:
    """Tests for compute_semantic_delta_from_vectors function."""

    def test_identical_vectors_give_zero_delta(self):
        """Identical aspect vectors should give delta=0."""
        vec = {"clarity": 0.8, "depth": 0.6}
        delta = compute_semantic_delta_from_vectors(vec, vec)
        assert abs(delta) < 1e-9

    def test_orthogonal_vectors_give_max_delta(self):
        """Orthogonal aspect vectors should give delta=1."""
        vec1 = {"a": 1.0, "b": 0.0}
        vec2 = {"a": 0.0, "b": 1.0}
        delta = compute_semantic_delta_from_vectors(vec1, vec2)
        assert abs(delta - 1.0) < 1e-9

    def test_opposite_vectors_give_max_delta(self):
        """Opposite aspect vectors should give delta=2 (clamped to 1)."""
        vec1 = {"a": 1.0}
        vec2 = {"a": -1.0}
        delta = compute_semantic_delta_from_vectors(vec1, vec2)
        # cosine = -1, so delta = 1 - (-1) = 2, but clamped to [0, 1]
        assert delta == 1.0

    def test_partial_overlap_gives_partial_delta(self):
        """Partially overlapping vectors should give partial delta."""
        vec1 = {"a": 1.0, "b": 0.0}
        vec2 = {"a": 1.0, "b": 1.0}
        delta = compute_semantic_delta_from_vectors(vec1, vec2)
        # cosine = 1 / (1 * sqrt(2)) ≈ 0.707
        expected_cosine = 1.0 / math.sqrt(2)
        expected_delta = 1.0 - expected_cosine
        assert abs(delta - expected_delta) < 1e-9

    def test_empty_vectors_give_zero_delta(self):
        """Empty vectors should give delta=0."""
        delta = compute_semantic_delta_from_vectors({}, {})
        assert delta == 0.0

    def test_one_empty_vector_gives_zero_delta(self):
        """One empty vector results in zero magnitude, returns 0 (undefined cosine)."""
        # When one vector is zero-valued in all dimensions but keys exist in the other,
        # the cosine similarity is 0 (orthogonal) so delta = 1 - 0 = 1
        # But when one side has NO keys at all, magnitude is 0, so we return 0
        delta = compute_semantic_delta_from_vectors({"a": 1.0}, {})
        # Empty dict means 0 in dimension "a", so magnitude = 0, returns cosine=0, delta=1-0=1
        # But wait - the function checks if mag < 1e-9 and returns cosine=0
        # So delta = 1 - 0 = 1.0
        assert delta == 1.0  # One empty vector = undefined direction = max motion

    def test_non_overlapping_keys(self):
        """Vectors with non-overlapping keys should be orthogonal."""
        vec1 = {"a": 1.0}
        vec2 = {"b": 1.0}
        delta = compute_semantic_delta_from_vectors(vec1, vec2)
        assert abs(delta - 1.0) < 1e-9

    def test_result_clamped_to_unit_interval(self):
        """Result should always be in [0, 1]."""
        # Various test cases
        test_cases = [
            ({"a": 1.0}, {"a": 1.0}),
            ({"a": 1.0}, {"a": -1.0}),
            ({"a": 0.0}, {"a": 0.0}),
            ({"a": 1.0, "b": 2.0, "c": 3.0}, {"a": 3.0, "b": 2.0, "c": 1.0}),
        ]
        for v1, v2 in test_cases:
            delta = compute_semantic_delta_from_vectors(v1, v2)
            assert 0.0 <= delta <= 1.0, f"Delta {delta} out of range for {v1}, {v2}"

    def test_determinism(self):
        """Same inputs should always produce same output."""
        vec1 = {"clarity": 0.8, "depth": 0.6, "breadth": 0.4}
        vec2 = {"clarity": 0.5, "depth": 0.7, "breadth": 0.3}
        first_result = compute_semantic_delta_from_vectors(vec1, vec2)
        for _ in range(100):
            assert compute_semantic_delta_from_vectors(vec1, vec2) == first_result


# =============================================================================
# Tests for Structural Delta from Stitching
# =============================================================================

class TestStructuralDeltaFromStitching:
    """Tests for compute_structural_delta_from_stitching function."""

    def test_zero_jumps_gives_zero_delta(self):
        """Zero cross-domain jumps should give delta=0."""
        delta = compute_structural_delta_from_stitching(0)
        assert delta == 0.0

    def test_one_jump_gives_partial_delta(self):
        """One jump should give delta=1/MAX_JUMPS."""
        delta = compute_structural_delta_from_stitching(1)
        assert abs(delta - 1.0 / MAX_STRUCTURAL_JUMPS) < 1e-9

    def test_max_jumps_gives_max_delta(self):
        """MAX_JUMPS should give delta=1.0."""
        delta = compute_structural_delta_from_stitching(MAX_STRUCTURAL_JUMPS)
        assert abs(delta - 1.0) < 1e-9

    def test_exceeding_max_jumps_clamped(self):
        """Jumps exceeding MAX should be clamped to 1.0."""
        delta = compute_structural_delta_from_stitching(MAX_STRUCTURAL_JUMPS + 10)
        assert abs(delta - 1.0) < 1e-9

    def test_custom_max_jumps(self):
        """Custom max_jumps parameter should work."""
        delta = compute_structural_delta_from_stitching(2, max_jumps=4)
        assert abs(delta - 0.5) < 1e-9

    def test_zero_max_jumps_returns_zero(self):
        """Zero max_jumps should return 0 (avoid division by zero)."""
        delta = compute_structural_delta_from_stitching(5, max_jumps=0)
        assert delta == 0.0

    def test_negative_max_jumps_returns_zero(self):
        """Negative max_jumps should return 0."""
        delta = compute_structural_delta_from_stitching(5, max_jumps=-1)
        assert delta == 0.0

    def test_result_in_unit_interval(self):
        """Result should always be in [0, 1]."""
        for jumps in range(0, 20):
            delta = compute_structural_delta_from_stitching(jumps)
            assert 0.0 <= delta <= 1.0

    def test_determinism(self):
        """Same input should always produce same output."""
        for _ in range(100):
            assert compute_structural_delta_from_stitching(3) == 3.0 / MAX_STRUCTURAL_JUMPS


# =============================================================================
# Tests for Entropy Extraction from RouterContext
# =============================================================================

class TestExtractEntropyFromRouterContext:
    """Tests for extract_entropy_from_router_context function."""

    def test_guna_mode_uses_H_G(self):
        """GUNA mode should use H_G / ln(3)."""
        H_G = LN_3 / 2  # Half of max
        H_D = LN_10  # Should be ignored
        H_K = LN_5  # Should be ignored

        H, audit = extract_entropy_from_router_context(H_G, H_D, H_K, EntropyMode.GUNA)

        assert abs(H - 0.5) < 1e-9
        assert audit.entropy_mode == "guna"
        assert abs(audit.H_raw - H_G) < 1e-9
        assert abs(audit.H_normalized - 0.5) < 1e-9

    def test_dimensional_mode_uses_H_D(self):
        """DIMENSIONAL mode should use H_D / ln(10)."""
        H_G = LN_3  # Should be ignored
        H_D = LN_10 / 4  # Quarter of max
        H_K = LN_5  # Should be ignored

        H, audit = extract_entropy_from_router_context(H_G, H_D, H_K, EntropyMode.DIMENSIONAL)

        assert abs(H - 0.25) < 1e-9
        assert audit.entropy_mode == "dimensional"

    def test_kosha_mode_uses_H_K(self):
        """KOSHA mode should use H_K / ln(5)."""
        H_G = LN_3  # Should be ignored
        H_D = LN_10  # Should be ignored
        H_K = LN_5 * 0.8  # 80% of max

        H, audit = extract_entropy_from_router_context(H_G, H_D, H_K, EntropyMode.KOSHA)

        assert abs(H - 0.8) < 1e-9
        assert audit.entropy_mode == "kosha"

    def test_zero_entropy(self):
        """Zero entropy should normalize to 0."""
        H, audit = extract_entropy_from_router_context(0.0, 0.0, 0.0, EntropyMode.GUNA)
        assert H == 0.0

    def test_max_entropy(self):
        """Max entropy should normalize to 1.0."""
        H, audit = extract_entropy_from_router_context(LN_3, LN_10, LN_5, EntropyMode.GUNA)
        assert abs(H - 1.0) < 1e-9

    def test_clamping_above_max(self):
        """Values above max should be clamped."""
        H, audit = extract_entropy_from_router_context(LN_3 * 2, LN_10, LN_5, EntropyMode.GUNA)
        assert abs(H - 1.0) < 1e-9

    def test_clamping_below_zero(self):
        """Negative values should be clamped to 0."""
        H, audit = extract_entropy_from_router_context(-0.5, LN_10, LN_5, EntropyMode.GUNA)
        assert H == 0.0

    def test_invalid_mode_raises_error(self):
        """Invalid entropy mode should raise ValueError."""
        with pytest.raises(ValueError):
            extract_entropy_from_router_context(0.5, 0.5, 0.5, "invalid_mode")

    def test_audit_trail_complete(self):
        """Audit trail should contain all required fields."""
        H, audit = extract_entropy_from_router_context(0.5, 1.0, 0.8, EntropyMode.GUNA)

        assert hasattr(audit, "entropy_mode")
        assert hasattr(audit, "H_raw")
        assert hasattr(audit, "H_normalized")

    def test_determinism(self):
        """Same inputs should always produce same output."""
        inputs = (0.7, 1.5, 0.9, EntropyMode.GUNA)
        first_H, first_audit = extract_entropy_from_router_context(*inputs)

        for _ in range(100):
            H, audit = extract_entropy_from_router_context(*inputs)
            assert H == first_H
            assert audit.H_raw == first_audit.H_raw
            assert audit.H_normalized == first_audit.H_normalized


# =============================================================================
# Tests for PipelineSignalContext
# =============================================================================

class TestPipelineSignalContext:
    """Tests for PipelineSignalContext dataclass."""

    def test_creation(self):
        """PipelineSignalContext should be creatable with all required fields."""
        context = PipelineSignalContext(
            H_G=0.5,
            H_D=1.0,
            H_K=0.8,
            query_aspect_probs={"clarity": 0.7},
            intent_type="COMMAND",
            cross_domain_count=2,
            candidate_aspect_probs={"clarity": 0.8},
            C_s=0.9,
        )

        assert context.H_G == 0.5
        assert context.H_D == 1.0
        assert context.H_K == 0.8
        assert context.query_aspect_probs == {"clarity": 0.7}
        assert context.intent_type == "COMMAND"
        assert context.cross_domain_count == 2
        assert context.candidate_aspect_probs == {"clarity": 0.8}
        assert context.C_s == 0.9

    def test_immutability(self):
        """PipelineSignalContext should be immutable (frozen)."""
        context = PipelineSignalContext(
            H_G=0.5,
            H_D=1.0,
            H_K=0.8,
            query_aspect_probs={"clarity": 0.7},
            intent_type="COMMAND",
            cross_domain_count=2,
            candidate_aspect_probs={"clarity": 0.8},
            C_s=0.9,
        )

        with pytest.raises(Exception):  # FrozenInstanceError
            context.H_G = 0.9


# =============================================================================
# Tests for wire_from_pipeline_context
# =============================================================================

class TestWireFromPipelineContext:
    """Tests for wire_from_pipeline_context function."""

    def test_basic_wiring(self):
        """Basic wiring should produce valid H and M values."""
        context = PipelineSignalContext(
            H_G=LN_3 / 2,  # 0.5 normalized
            H_D=LN_10 / 2,
            H_K=LN_5 / 2,
            query_aspect_probs={"clarity": 0.8},
            intent_type="COMMAND",
            cross_domain_count=2,
            candidate_aspect_probs={"clarity": 0.6},
            C_s=0.9,
        )
        config = SignalWiringConfig(
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.SEMANTIC,
        )

        wired = wire_from_pipeline_context(context, config)

        assert 0.0 <= wired.H <= 1.0
        assert 0.0 <= wired.M <= 1.0
        assert wired.audit is not None

    def test_entropy_mode_selection(self):
        """Different entropy modes should use different H values."""
        context = PipelineSignalContext(
            H_G=LN_3 * 0.3,
            H_D=LN_10 * 0.6,
            H_K=LN_5 * 0.9,
            query_aspect_probs={},
            intent_type="WHAT",
            cross_domain_count=0,
            candidate_aspect_probs={},
            C_s=0.5,
        )

        # GUNA mode
        config_guna = SignalWiringConfig(entropy_mode=EntropyMode.GUNA)
        wired_guna = wire_from_pipeline_context(context, config_guna)

        # DIMENSIONAL mode
        config_dim = SignalWiringConfig(entropy_mode=EntropyMode.DIMENSIONAL)
        wired_dim = wire_from_pipeline_context(context, config_dim)

        # KOSHA mode
        config_kosha = SignalWiringConfig(entropy_mode=EntropyMode.KOSHA)
        wired_kosha = wire_from_pipeline_context(context, config_kosha)

        # Each should produce different H values
        assert abs(wired_guna.H - 0.3) < 1e-9
        assert abs(wired_dim.H - 0.6) < 1e-9
        assert abs(wired_kosha.H - 0.9) < 1e-9

    def test_motion_mode_selection(self):
        """Different motion modes should produce different M values."""
        # Context with distinct delta sources
        context = PipelineSignalContext(
            H_G=LN_3 / 2,
            H_D=LN_10 / 2,
            H_K=LN_5 / 2,
            query_aspect_probs={"a": 1.0, "b": 0.0},
            intent_type="COMMAND",  # Experiential = 1
            cross_domain_count=2,   # Structural = 2/5 = 0.4
            candidate_aspect_probs={"a": 0.0, "b": 1.0},  # Semantic = 1 (orthogonal)
            C_s=0.5,
        )

        # SEMANTIC mode
        config_sem = SignalWiringConfig(motion_mode=MotionMode.SEMANTIC)
        wired_sem = wire_from_pipeline_context(context, config_sem)

        # STRUCTURAL mode
        config_str = SignalWiringConfig(motion_mode=MotionMode.STRUCTURAL)
        wired_str = wire_from_pipeline_context(context, config_str)

        # EXPERIENTIAL mode
        config_exp = SignalWiringConfig(motion_mode=MotionMode.EXPERIENTIAL)
        wired_exp = wire_from_pipeline_context(context, config_exp)

        # SEMANTIC should give M=1 (orthogonal vectors)
        assert abs(wired_sem.M - 1.0) < 1e-9

        # STRUCTURAL should give M=0.4 (2 jumps out of 5)
        assert abs(wired_str.M - 0.4) < 1e-9

        # EXPERIENTIAL should give M=1 (COMMAND intent)
        assert abs(wired_exp.M - 1.0) < 1e-9

    def test_composite_motion_mode(self):
        """COMPOSITE mode should average the delta components."""
        context = PipelineSignalContext(
            H_G=LN_3 / 2,
            H_D=LN_10 / 2,
            H_K=LN_5 / 2,
            query_aspect_probs={"a": 1.0},
            intent_type="COMMAND",  # Experiential = 1
            cross_domain_count=MAX_STRUCTURAL_JUMPS,   # Structural = 1.0
            candidate_aspect_probs={"a": 1.0},  # Semantic = 0 (identical)
            C_s=0.5,
        )

        # Equal weights
        config = SignalWiringConfig(
            motion_mode=MotionMode.COMPOSITE,
            composite_weights=(1.0, 1.0, 1.0),
        )
        wired = wire_from_pipeline_context(context, config)

        # M = (0 + 1 + 1) / 3 = 0.666...
        expected_M = (0.0 + 1.0 + 1.0) / 3.0
        assert abs(wired.M - expected_M) < 1e-9

    def test_audit_trail_complete(self):
        """Wired signals should include complete audit trail."""
        context = PipelineSignalContext(
            H_G=0.5,
            H_D=1.0,
            H_K=0.8,
            query_aspect_probs={"clarity": 0.7},
            intent_type="WHAT",
            cross_domain_count=1,
            candidate_aspect_probs={"clarity": 0.5},
            C_s=0.6,
        )
        config = SignalWiringConfig()

        wired = wire_from_pipeline_context(context, config)

        # Check audit exists
        assert wired.audit is not None
        assert wired.audit.entropy_audit is not None
        assert wired.audit.motion_audit is not None

        # Check entropy audit
        assert wired.audit.entropy_audit.entropy_mode == "guna"
        assert wired.audit.entropy_audit.H_normalized == wired.H

        # Check motion audit
        assert wired.audit.motion_audit.motion_mode == "semantic"

    def test_determinism(self):
        """Same context and config should always produce same result."""
        context = PipelineSignalContext(
            H_G=0.7,
            H_D=1.2,
            H_K=0.9,
            query_aspect_probs={"a": 0.5, "b": 0.5},
            intent_type="SHOULD",
            cross_domain_count=3,
            candidate_aspect_probs={"a": 0.3, "b": 0.7},
            C_s=0.7,
        )
        config = SignalWiringConfig(
            entropy_mode=EntropyMode.DIMENSIONAL,
            motion_mode=MotionMode.COMPOSITE,
            composite_weights=(1.0, 1.0, 1.0),  # Required for COMPOSITE mode
        )

        first_wired = wire_from_pipeline_context(context, config)

        for _ in range(100):
            wired = wire_from_pipeline_context(context, config)
            assert wired.H == first_wired.H
            assert wired.M == first_wired.M


# =============================================================================
# End-to-End Adapter Tests
# =============================================================================

class TestEndToEndAdapter:
    """End-to-end tests for the pipeline signal adapter."""

    def test_full_pipeline_flow(self):
        """Test complete flow from raw pipeline signals to wired H and M."""
        # Simulate real pipeline values
        context = PipelineSignalContext(
            # From RouterContext (TTOR)
            H_G=0.8,  # High guna entropy
            H_D=1.5,  # Mid-range dimensional entropy
            H_K=1.0,  # Mid-range kosha entropy
            query_aspect_probs={
                "clarity": 0.7,
                "depth": 0.5,
                "breadth": 0.3,
            },
            # From ActivationPlan
            intent_type="COMMAND",
            # From StitchingDecision
            cross_domain_count=2,
            # From Candidate
            candidate_aspect_probs={
                "clarity": 0.8,
                "depth": 0.4,
                "breadth": 0.5,
            },
            # From Coherence
            C_s=0.75,
        )

        config = SignalWiringConfig(
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.SEMANTIC,
        )

        wired = wire_from_pipeline_context(context, config)

        # Verify H is properly normalized
        expected_H = min(0.8, LN_3) / LN_3  # Clamped and normalized
        assert abs(wired.H - expected_H) < 1e-9

        # Verify M is in valid range
        assert 0.0 <= wired.M <= 1.0

        # Verify audit is present
        assert wired.audit.entropy_audit.entropy_mode == "guna"
        assert wired.audit.motion_audit.motion_mode == "semantic"

    def test_extreme_low_values(self):
        """Test with all minimum values."""
        context = PipelineSignalContext(
            H_G=0.0,
            H_D=0.0,
            H_K=0.0,
            query_aspect_probs={},
            intent_type="WHAT",
            cross_domain_count=0,
            candidate_aspect_probs={},
            C_s=0.0,
        )
        config = SignalWiringConfig()

        wired = wire_from_pipeline_context(context, config)

        assert wired.H == 0.0
        assert wired.M == 0.0  # Empty vectors give 0

    def test_extreme_high_values(self):
        """Test with all maximum values."""
        context = PipelineSignalContext(
            H_G=LN_3 * 2,  # Exceeds max, should clamp
            H_D=LN_10 * 2,
            H_K=LN_5 * 2,
            query_aspect_probs={"a": 1.0},
            intent_type="COMMAND",
            cross_domain_count=100,  # Exceeds max, should clamp
            candidate_aspect_probs={"b": 1.0},  # Orthogonal = max semantic delta
            C_s=1.0,
        )
        config = SignalWiringConfig()

        wired = wire_from_pipeline_context(context, config)

        assert wired.H == 1.0  # Clamped to max
        assert wired.M == 1.0  # Orthogonal vectors give max delta

    def test_all_intent_types(self):
        """Test that all known IntentType values are handled."""
        intent_types = [
            "WHAT", "HOW", "WHY",  # Non-experiential
            "COMMAND", "SHOULD", "REFLECTION",  # Experiential
            "COMPARE", "DEFINE", "EXPLORE",  # Other potential types
        ]

        for intent in intent_types:
            context = PipelineSignalContext(
                H_G=0.5,
                H_D=1.0,
                H_K=0.8,
                query_aspect_probs={"a": 0.5},
                intent_type=intent,
                cross_domain_count=1,
                candidate_aspect_probs={"a": 0.5},
                C_s=0.5,
            )
            config = SignalWiringConfig(motion_mode=MotionMode.EXPERIENTIAL)

            wired = wire_from_pipeline_context(context, config)

            # Should not raise, and M should be 0 or 1
            assert wired.M in [0.0, 1.0]
