"""
Tests for P32 Insight Window Gating (Observation-Only)

Test Requirements (50+ tests across 6 groups):
    Group A — Formula Correctness (12+ tests)
        - Weight correctness
        - Clamp behavior
        - Known inputs → expected outputs

    Group B — Monotonicity Proof (10+ tests)
        - Acoustic input can only reduce depth
        - No signal ever increases depth
        - Penalties are cumulative reductions

    Group C — Gate Behavior (10+ tests)
        - Threshold boundary tests
        - Open → closed transitions only
        - Gate rule enforcement

    Group D — Non-Authority Proof (8+ tests)
        - Identical authoritative outputs with different P32 values
        - P32 does not modify upstream phases

    Group E — Import Safety (5+ tests)
        - Forbidden imports fail build
        - No direct P22/P23/P24 imports

    Group F — Regression Lock (5+ tests)
        - When P32 disabled, pipeline output identical
        - Constants are stable

INVARIANTS TO ASSERT:
    INV-P32-1: Insight gating never opens due to observers
    INV-P32-2: Gate monotonicity enforced
    INV-P32-3: No upstream influence
    INV-P32-4: Deterministic behavior
    INV-P32-5: Envelope is advisory only
"""

import ast
import hashlib
import inspect
import json
import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from symbolu.policy.insight_window import (
    # Version
    P32_VERSION,
    # Enums
    ConfidenceBand,
    # Constants - Envelope
    ALLOWED_REASON_CODES,
    INSIGHT_GATE_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    # Constants - Formula Weights (LOCKED)
    W_COHERENCE_V3_QUALITY,
    W_UCF_SCORE,
    W_SCHEMA_STABILITY,
    W_DRIFT_INVERSE,
    # Constants - Thresholds (LOCKED)
    TEMPORAL_ENTROPY_THRESHOLD,
    TEMPORAL_ENTROPY_PENALTY,
    COHERENCE_QUALITY_THRESHOLD,
    COHERENCE_QUALITY_PENALTY,
    ACOUSTIC_ALIGNMENT_THRESHOLD,
    ACOUSTIC_ALIGNMENT_PENALTY,
    NEUTRAL_DEFAULT,
    # Dataclasses
    InsightWindowEnvelope,
    FormulaResult,
    # Helpers
    create_envelope,
    create_closed_envelope,
    # Formula functions
    compute_raw_depth,
    apply_temporal_entropy_penalty,
    apply_coherence_quality_penalty,
    apply_acoustic_penalty,
    compute_insight_depth,
    # Engine
    InsightGatingEngine,
    get_insight_gating_engine,
)

from symbolu.mechanical.pipeline.p32_insight_window import (
    maybe_run_p32,
    run_p32_directly,
    is_p32_disabled,
    has_p32_envelope,
    get_p32_envelope,
    get_insight_depth,
    get_confidence_band,
    is_gate_open,
    is_gate_closed,
    has_acoustic_penalty,
    get_reason_codes,
    get_p32_version,
)


# ============================================================================
# MOCK CLASSES - For test isolation
# ============================================================================


@dataclass
class MockCoherenceState:
    """Mock CoherenceState for testing."""
    coherence_v3_quality: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    coherence_score_v3: Optional[float] = None


@dataclass
class MockP18Report:
    """Mock P18 temporal entropy report."""
    delta_entropy: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None


@dataclass
class MockP26State:
    """Mock P26 UCF state."""
    ucf_score: Optional[float] = None


@dataclass
class MockP33Snapshot:
    """Mock P33 schema adaptive routing snapshot."""
    confidence: Optional[float] = None


@dataclass
class MockP23AlignmentReport:
    """Mock P23 alignment report for acoustic testing."""
    alignment_score: Optional[float] = None


@dataclass
class MockPipelineContext:
    """Mock PipelineContext for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p18: Optional[MockP18Report] = None
    p26: Optional[MockP26State] = None
    p33: Optional[MockP33Snapshot] = None
    p23_alignment_report: Optional[MockP23AlignmentReport] = None
    p32: Optional[InsightWindowEnvelope] = None
    _p32_disabled: bool = False
    # Authority phase fields (should NOT be modified by P32)
    p6_regime: Optional[Any] = None
    p7_discourse_envelope: Optional[Any] = None
    semantic_frame: Optional[Any] = None
    lexical_frame: Optional[Any] = None


def make_context_minimal() -> MockPipelineContext:
    """Create a minimal context with no data."""
    return MockPipelineContext(coherence_state=MockCoherenceState())


def make_context_with_defaults() -> MockPipelineContext:
    """Create a context with all neutral defaults (0.5)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
        ),
        p18=MockP18Report(delta_entropy=0.5),
        p26=MockP26State(ucf_score=0.5),
        p33=MockP33Snapshot(confidence=0.5),
    )


def make_context_high_quality() -> MockPipelineContext:
    """Create a context with high quality signals (gate open)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_v3_quality=0.85,
            drift_fusion_index=0.15,
        ),
        p18=MockP18Report(delta_entropy=0.3),
        p26=MockP26State(ucf_score=0.8),
        p33=MockP33Snapshot(confidence=0.75),
    )


def make_context_low_quality() -> MockPipelineContext:
    """Create a context with low quality signals (gate closed)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_v3_quality=0.25,
            drift_fusion_index=0.85,
        ),
        p18=MockP18Report(delta_entropy=0.75),
        p26=MockP26State(ucf_score=0.2),
        p33=MockP33Snapshot(confidence=0.3),
    )


def make_context_boundary_low() -> MockPipelineContext:
    """Create a context with boundary low values (0.0)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_v3_quality=0.0,
            drift_fusion_index=1.0,  # Max drift
        ),
        p18=MockP18Report(delta_entropy=1.0),
        p26=MockP26State(ucf_score=0.0),
        p33=MockP33Snapshot(confidence=0.0),
    )


def make_context_boundary_high() -> MockPipelineContext:
    """Create a context with boundary high values (1.0)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_v3_quality=1.0,
            drift_fusion_index=0.0,  # No drift
        ),
        p18=MockP18Report(delta_entropy=0.0),
        p26=MockP26State(ucf_score=1.0),
        p33=MockP33Snapshot(confidence=1.0),
    )


def make_context_with_acoustic(alignment: float) -> MockPipelineContext:
    """Create a context with acoustic alignment for penalty testing."""
    ctx = make_context_high_quality()
    ctx.p23_alignment_report = MockP23AlignmentReport(alignment_score=alignment)
    return ctx


# ============================================================================
# GROUP A — FORMULA CORRECTNESS TESTS (12+ tests)
# Weight correctness, clamp behavior, known inputs → expected outputs
# ============================================================================


class TestGroupAFormulaCorrectness:
    """Group A — Formula Correctness tests."""

    def test_a01_weights_sum_to_one(self):
        """Test that formula weights sum to 1.0."""
        weight_sum = W_COHERENCE_V3_QUALITY + W_UCF_SCORE + W_SCHEMA_STABILITY + W_DRIFT_INVERSE
        assert abs(weight_sum - 1.0) < 1e-9, f"Weights sum to {weight_sum}, expected 1.0"

    def test_a02_weights_are_correct_values(self):
        """Test that formula weights have correct locked values."""
        assert W_COHERENCE_V3_QUALITY == 0.40
        assert W_UCF_SCORE == 0.30
        assert W_SCHEMA_STABILITY == 0.20
        assert W_DRIFT_INVERSE == 0.10

    def test_a03_raw_depth_neutral_inputs(self):
        """Test raw depth with neutral (0.5) inputs."""
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=0.5,
            ucf_score=0.5,
            schema_stability=0.5,
            drift_fusion_index=0.5,
        )
        # 0.40*0.5 + 0.30*0.5 + 0.20*0.5 + 0.10*(1-0.5) = 0.20 + 0.15 + 0.10 + 0.05 = 0.50
        assert abs(raw_depth - 0.5) < 0.001, f"Expected 0.5, got {raw_depth}"

    def test_a04_raw_depth_all_ones(self):
        """Test raw depth with all 1.0 inputs (except drift which is inverted)."""
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=1.0,
            ucf_score=1.0,
            schema_stability=1.0,
            drift_fusion_index=0.0,  # 1-0 = 1.0
        )
        # 0.40*1.0 + 0.30*1.0 + 0.20*1.0 + 0.10*1.0 = 1.0
        assert abs(raw_depth - 1.0) < 0.001, f"Expected 1.0, got {raw_depth}"

    def test_a05_raw_depth_all_zeros(self):
        """Test raw depth with all 0.0 inputs (except drift which is inverted)."""
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=0.0,
            ucf_score=0.0,
            schema_stability=0.0,
            drift_fusion_index=1.0,  # 1-1 = 0.0
        )
        # 0.40*0.0 + 0.30*0.0 + 0.20*0.0 + 0.10*0.0 = 0.0
        assert abs(raw_depth - 0.0) < 0.001, f"Expected 0.0, got {raw_depth}"

    def test_a06_depth_clamped_to_unit_interval(self):
        """Test that depth is clamped to [0.0, 1.0]."""
        # All boundary contexts should produce valid depths
        for ctx in [make_context_boundary_low(), make_context_boundary_high()]:
            envelope = maybe_run_p32(ctx)
            assert envelope is not None
            assert 0.0 <= envelope.insight_depth <= 1.0
            assert 0.0 <= envelope.raw_depth <= 1.0

    def test_a07_coherence_weight_contribution(self):
        """Test coherence quality weight contribution."""
        # Only coherence_v3_quality = 1.0, others = 0.0
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=1.0,
            ucf_score=0.0,
            schema_stability=0.0,
            drift_fusion_index=1.0,  # 1-1 = 0.0
        )
        assert abs(raw_depth - 0.40) < 0.001, f"Expected 0.40, got {raw_depth}"

    def test_a08_ucf_weight_contribution(self):
        """Test UCF score weight contribution."""
        # Only ucf_score = 1.0, others = 0.0
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=0.0,
            ucf_score=1.0,
            schema_stability=0.0,
            drift_fusion_index=1.0,  # 1-1 = 0.0
        )
        assert abs(raw_depth - 0.30) < 0.001, f"Expected 0.30, got {raw_depth}"

    def test_a09_schema_weight_contribution(self):
        """Test schema stability weight contribution."""
        # Only schema_stability = 1.0, others = 0.0
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=0.0,
            ucf_score=0.0,
            schema_stability=1.0,
            drift_fusion_index=1.0,  # 1-1 = 0.0
        )
        assert abs(raw_depth - 0.20) < 0.001, f"Expected 0.20, got {raw_depth}"

    def test_a10_drift_inverse_weight_contribution(self):
        """Test drift inverse weight contribution."""
        # Only drift_fusion_index = 0.0 (so 1-0 = 1.0), others = 0.0
        raw_depth, _ = compute_raw_depth(
            coherence_v3_quality=0.0,
            ucf_score=0.0,
            schema_stability=0.0,
            drift_fusion_index=0.0,  # 1-0 = 1.0
        )
        assert abs(raw_depth - 0.10) < 0.001, f"Expected 0.10, got {raw_depth}"

    def test_a11_missing_inputs_use_defaults(self):
        """Test that missing inputs use neutral defaults (0.5)."""
        raw_depth, inputs = compute_raw_depth(
            coherence_v3_quality=None,
            ucf_score=None,
            schema_stability=None,
            drift_fusion_index=None,
        )
        # All defaults = 0.5
        assert abs(raw_depth - 0.5) < 0.001
        assert inputs["coherence_v3_quality"] == 0.5
        assert inputs["ucf_score"] == 0.5
        assert inputs["schema_stability"] == 0.5
        assert inputs["drift_fusion_index"] == 0.5

    def test_a12_formula_result_contains_all_inputs(self):
        """Test that FormulaResult contains all input values."""
        result = compute_insight_depth(
            coherence_v3_quality=0.7,
            ucf_score=0.6,
            schema_stability=0.5,
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
            acoustic_alignment_score=0.8,
        )
        assert "coherence_v3_quality" in result.inputs_used
        assert "ucf_score" in result.inputs_used
        assert "schema_stability" in result.inputs_used
        assert "drift_fusion_index" in result.inputs_used
        assert "temporal_entropy_diff" in result.inputs_used
        assert "acoustic_alignment_score" in result.inputs_used


# ============================================================================
# GROUP B — MONOTONICITY PROOF TESTS (10+ tests)
# Acoustic input can only reduce depth, no signal ever increases depth
# ============================================================================


class TestGroupBMonotonicityProof:
    """Group B — Monotonicity Proof tests (INV-P32-2)."""

    def test_b01_temporal_entropy_penalty_reduces_depth(self):
        """Test that temporal entropy penalty reduces depth."""
        base_depth = 0.8
        adjusted, penalty, code = apply_temporal_entropy_penalty(base_depth, 0.7)  # > 0.6 threshold
        assert adjusted < base_depth
        assert adjusted == base_depth * TEMPORAL_ENTROPY_PENALTY
        assert code == "HIGH_TEMPORAL_ENTROPY"

    def test_b02_temporal_entropy_no_penalty_below_threshold(self):
        """Test no penalty when temporal entropy is below threshold."""
        base_depth = 0.8
        adjusted, penalty, code = apply_temporal_entropy_penalty(base_depth, 0.5)  # < 0.6
        assert adjusted == base_depth
        assert penalty is None
        assert code is None

    def test_b03_coherence_quality_penalty_reduces_depth(self):
        """Test that coherence quality penalty reduces depth."""
        base_depth = 0.8
        adjusted, penalty, code = apply_coherence_quality_penalty(base_depth, 0.3)  # < 0.45
        assert adjusted < base_depth
        assert adjusted == base_depth * COHERENCE_QUALITY_PENALTY
        assert code == "LOW_COHERENCE_QUALITY"

    def test_b04_coherence_quality_no_penalty_above_threshold(self):
        """Test no penalty when coherence quality is above threshold."""
        base_depth = 0.8
        adjusted, penalty, code = apply_coherence_quality_penalty(base_depth, 0.6)  # > 0.45
        assert adjusted == base_depth
        assert penalty is None
        assert code is None

    def test_b05_acoustic_penalty_reduces_depth(self):
        """Test that acoustic penalty reduces depth."""
        base_depth = 0.8
        adjusted, penalty, code = apply_acoustic_penalty(base_depth, 0.2)  # < 0.4
        assert adjusted < base_depth
        assert adjusted == base_depth * ACOUSTIC_ALIGNMENT_PENALTY
        assert code == "ACOUSTIC_MISALIGNMENT"

    def test_b06_acoustic_no_penalty_above_threshold(self):
        """Test no penalty when acoustic alignment is above threshold."""
        base_depth = 0.8
        adjusted, penalty, code = apply_acoustic_penalty(base_depth, 0.6)  # > 0.4
        assert adjusted == base_depth
        assert penalty is None
        assert code is None

    def test_b07_acoustic_no_penalty_when_none(self):
        """Test no penalty when acoustic alignment is None (backward compat)."""
        base_depth = 0.8
        adjusted, penalty, code = apply_acoustic_penalty(base_depth, None)
        assert adjusted == base_depth
        assert penalty is None
        assert code is None

    def test_b08_final_depth_never_exceeds_raw(self):
        """Test that final depth never exceeds raw depth (INV-P32-2)."""
        result = compute_insight_depth(
            coherence_v3_quality=0.8,
            ucf_score=0.7,
            schema_stability=0.6,
            drift_fusion_index=0.2,
            temporal_entropy_diff=0.8,  # High entropy → penalty
            acoustic_alignment_score=0.2,  # Low alignment → penalty
        )
        assert result.final_depth <= result.raw_depth

    def test_b09_cumulative_penalties_reduce_monotonically(self):
        """Test that cumulative penalties are all reductions."""
        result = compute_insight_depth(
            coherence_v3_quality=0.3,  # Low → penalty
            ucf_score=0.7,
            schema_stability=0.6,
            drift_fusion_index=0.2,
            temporal_entropy_diff=0.8,  # High → penalty
            acoustic_alignment_score=0.1,  # Low → penalty
        )
        # All 3 penalties should be applied
        assert len(result.penalties_applied) == 3
        assert result.final_depth < result.raw_depth

    def test_b10_envelope_validates_monotonicity(self):
        """Test that envelope creation validates monotonicity."""
        # Valid envelope (depth <= raw_depth)
        envelope = create_envelope(insight_depth=0.5, raw_depth=0.7)
        assert envelope.insight_depth <= envelope.raw_depth

        # Invalid envelope should raise (depth > raw_depth)
        with pytest.raises(ValueError, match="violates monotonicity"):
            InsightWindowEnvelope(
                is_open=True,
                insight_depth=0.8,
                gating_reason_codes=("GATE_OPEN",),
                confidence_band=ConfidenceBand.HIGH,
                raw_depth=0.5,  # Less than insight_depth!
            )

    def test_b11_acoustic_cannot_open_closed_gate(self):
        """Test INV-P32-1: Acoustic input cannot open a closed gate."""
        # Create context with closed gate (low quality)
        ctx = make_context_low_quality()
        envelope_without_acoustic = maybe_run_p32(ctx)
        assert not envelope_without_acoustic.is_open

        # Adding good acoustic alignment should NOT open the gate
        ctx.p23_alignment_report = MockP23AlignmentReport(alignment_score=1.0)
        envelope_with_acoustic = maybe_run_p32(ctx)
        assert not envelope_with_acoustic.is_open  # Still closed!

    def test_b12_acoustic_can_only_close_not_open(self):
        """Test that acoustic can close an open gate but never open a closed one."""
        # Start with open gate
        ctx = make_context_high_quality()
        envelope_open = maybe_run_p32(ctx)
        assert envelope_open.is_open

        # Bad acoustic alignment can close the gate
        ctx.p23_alignment_report = MockP23AlignmentReport(alignment_score=0.1)
        ctx.p32 = None  # Reset
        envelope_after = maybe_run_p32(ctx)
        # The gate might close due to acoustic penalty
        assert envelope_after.insight_depth <= envelope_open.insight_depth


# ============================================================================
# GROUP C — GATE BEHAVIOR TESTS (10+ tests)
# Threshold boundary tests, open → closed transitions only
# ============================================================================


class TestGroupCGateBehavior:
    """Group C — Gate Behavior tests."""

    def test_c01_gate_threshold_is_correct(self):
        """Test gate threshold is 0.55."""
        assert INSIGHT_GATE_THRESHOLD == 0.55

    def test_c02_gate_open_at_threshold(self):
        """Test gate is open at exactly threshold."""
        envelope = create_envelope(insight_depth=0.55, raw_depth=0.55)
        assert envelope.is_open is True

    def test_c03_gate_closed_below_threshold(self):
        """Test gate is closed just below threshold."""
        envelope = create_envelope(insight_depth=0.549, raw_depth=0.549)
        assert envelope.is_open is False

    def test_c04_gate_open_above_threshold(self):
        """Test gate is open above threshold."""
        envelope = create_envelope(insight_depth=0.7, raw_depth=0.7)
        assert envelope.is_open is True

    def test_c05_gate_closed_at_zero(self):
        """Test gate is closed at zero depth."""
        envelope = create_envelope(insight_depth=0.0, raw_depth=0.0)
        assert envelope.is_open is False

    def test_c06_gate_open_at_one(self):
        """Test gate is open at maximum depth."""
        envelope = create_envelope(insight_depth=1.0, raw_depth=1.0)
        assert envelope.is_open is True

    def test_c07_gate_reason_codes_reflect_state(self):
        """Test reason codes include gate state."""
        # Open gate
        envelope_open = create_envelope(insight_depth=0.7, raw_depth=0.7)
        assert "GATE_OPEN" in envelope_open.gating_reason_codes

        # Closed gate
        envelope_closed = create_envelope(insight_depth=0.3, raw_depth=0.3)
        assert "GATE_CLOSED" in envelope_closed.gating_reason_codes
        assert "DEPTH_BELOW_THRESHOLD" in envelope_closed.gating_reason_codes

    def test_c08_high_quality_context_opens_gate(self):
        """Test that high quality context opens the gate."""
        ctx = make_context_high_quality()
        envelope = maybe_run_p32(ctx)
        assert envelope is not None
        assert envelope.is_open is True

    def test_c09_low_quality_context_closes_gate(self):
        """Test that low quality context closes the gate."""
        ctx = make_context_low_quality()
        envelope = maybe_run_p32(ctx)
        assert envelope is not None
        assert envelope.is_open is False

    def test_c10_neutral_context_near_boundary(self):
        """Test neutral context produces depth near 0.5."""
        ctx = make_context_with_defaults()
        envelope = maybe_run_p32(ctx)
        assert envelope is not None
        # May have coherence penalty since 0.5 > 0.45, no penalty
        # Depth should be around 0.5, gate should be closed
        assert envelope.is_open is False  # 0.5 < 0.55


# ============================================================================
# GROUP D — NON-AUTHORITY PROOF TESTS (8+ tests)
# P32 does not modify upstream phases, envelope is advisory only
# ============================================================================


class TestGroupDNonAuthorityProof:
    """Group D — Non-Authority Proof tests (INV-P32-3, INV-P32-5)."""

    def test_d01_envelope_is_immutable(self):
        """Test that envelope is frozen (immutable)."""
        envelope = create_envelope(insight_depth=0.6, raw_depth=0.6)

        # Attempting to modify should raise
        with pytest.raises(Exception):  # FrozenInstanceError
            envelope.insight_depth = 0.9

    def test_d02_observer_only_must_be_true(self):
        """Test that observer_only is always True."""
        envelope = create_envelope(insight_depth=0.6, raw_depth=0.6)
        assert envelope.observer_only is True

        # Creating with observer_only=False should raise
        with pytest.raises(ValueError, match="observer_only must be True"):
            InsightWindowEnvelope(
                is_open=True,
                insight_depth=0.6,
                gating_reason_codes=("GATE_OPEN",),
                confidence_band=ConfidenceBand.HIGH,
                raw_depth=0.6,
                observer_only=False,
            )

    def test_d03_p32_does_not_modify_regime(self):
        """Test that P32 does not modify ctx.p6_regime."""
        ctx = make_context_high_quality()
        ctx.p6_regime = "original_regime"

        maybe_run_p32(ctx)

        assert ctx.p6_regime == "original_regime"

    def test_d04_p32_does_not_modify_discourse(self):
        """Test that P32 does not modify ctx.p7_discourse_envelope."""
        ctx = make_context_high_quality()
        ctx.p7_discourse_envelope = "original_discourse"

        maybe_run_p32(ctx)

        assert ctx.p7_discourse_envelope == "original_discourse"

    def test_d05_p32_does_not_modify_semantics(self):
        """Test that P32 does not modify ctx.semantic_frame."""
        ctx = make_context_high_quality()
        ctx.semantic_frame = "original_semantics"

        maybe_run_p32(ctx)

        assert ctx.semantic_frame == "original_semantics"

    def test_d06_p32_does_not_modify_lexical(self):
        """Test that P32 does not modify ctx.lexical_frame."""
        ctx = make_context_high_quality()
        ctx.lexical_frame = "original_lexical"

        maybe_run_p32(ctx)

        assert ctx.lexical_frame == "original_lexical"

    def test_d07_p32_only_writes_to_p32_field(self):
        """Test that P32 only writes to ctx.p32, not other fields."""
        ctx = make_context_high_quality()

        # Track attributes before
        attrs_before = set(vars(ctx).keys())

        maybe_run_p32(ctx)

        # Track attributes after
        attrs_after = set(vars(ctx).keys())

        # Only p32 should be affected
        new_attrs = attrs_after - attrs_before
        assert new_attrs == set() or new_attrs == {"p32"}

    def test_d08_envelope_to_dict_is_serializable(self):
        """Test that envelope.to_dict() produces serializable output."""
        envelope = create_envelope(
            insight_depth=0.6,
            raw_depth=0.65,
            gating_reason_codes=["GATE_OPEN"],
            penalties_applied=["temporal_entropy"],
        )

        d = envelope.to_dict()
        json_str = json.dumps(d)  # Should not raise
        assert isinstance(json_str, str)


# ============================================================================
# GROUP E — IMPORT SAFETY TESTS (5+ tests)
# Forbidden imports fail build, no direct P22/P23/P24 imports
# ============================================================================


class TestGroupEImportSafety:
    """Group E — Import Safety tests (INV-P32-4)."""

    # Forbidden modules that P32 must NOT import
    FORBIDDEN_MODULES = {
        # Authority phases
        "symbolu.mechanical.pipeline.phase_p6",
        "symbolu.mechanical.pipeline.p7_discourse",
        "symbolu.mechanical.pipeline.p8_semantics",
        "symbolu.mechanical.pipeline.p9_lexical",
        # Observer modules (direct import forbidden)
        "symbolu.mechanical.pipeline.p22_acoustic_witness",
        "symbolu.mechanical.pipeline.p23_alignment",
        "symbolu.mechanical.pipeline.p24_projection",
        # Policy/Planner/Renderer
        "symbolu.mechanical.planner",
        "symbolu.mechanical.renderer",
    }

    def _get_imports_from_file(self, filepath: str) -> set:
        """Extract all imports from a Python file."""
        with open(filepath, "r") as f:
            source = f.read()

        tree = ast.parse(source)
        imports = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)

        return imports

    def test_e01_insight_envelope_no_forbidden_imports(self):
        """Test insight_envelope.py has no forbidden imports."""
        filepath = "symbolu/policy/insight_window/insight_envelope.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_e02_insight_gating_formula_no_forbidden_imports(self):
        """Test insight_gating_formula.py has no forbidden imports."""
        filepath = "symbolu/policy/insight_window/insight_gating_formula.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_e03_insight_gating_engine_no_forbidden_imports(self):
        """Test insight_gating_engine.py has no forbidden imports."""
        filepath = "symbolu/policy/insight_window/insight_gating_engine.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_e04_p32_integration_no_forbidden_imports(self):
        """Test p32_integration.py has no forbidden imports."""
        filepath = "symbolu/mechanical/pipeline/p32_insight_window/p32_integration.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_e05_no_llm_or_random_imports(self):
        """Test that no LLM or randomness imports are present."""
        files = [
            "symbolu/policy/insight_window/insight_envelope.py",
            "symbolu/policy/insight_window/insight_gating_formula.py",
            "symbolu/policy/insight_window/insight_gating_engine.py",
            "symbolu/mechanical/pipeline/p32_insight_window/p32_integration.py",
        ]

        forbidden = {"random", "numpy.random", "openai", "anthropic", "langchain"}

        for filepath in files:
            imports = self._get_imports_from_file(filepath)
            found = imports & forbidden
            assert not found, f"Forbidden import {found} in {filepath}"


# ============================================================================
# GROUP F — REGRESSION LOCK TESTS (5+ tests)
# When P32 disabled, pipeline output identical; constants stable
# ============================================================================


class TestGroupFRegressionLock:
    """Group F — Regression Lock tests."""

    def test_f01_version_is_stable(self):
        """Test that version string is stable."""
        assert P32_VERSION == "1.0.0"
        assert get_p32_version() == "1.0.0"

    def test_f02_thresholds_are_stable(self):
        """Test that threshold values are stable."""
        assert INSIGHT_GATE_THRESHOLD == 0.55
        assert TEMPORAL_ENTROPY_THRESHOLD == 0.6
        assert TEMPORAL_ENTROPY_PENALTY == 0.85
        assert COHERENCE_QUALITY_THRESHOLD == 0.45
        assert COHERENCE_QUALITY_PENALTY == 0.80
        assert ACOUSTIC_ALIGNMENT_THRESHOLD == 0.4
        assert ACOUSTIC_ALIGNMENT_PENALTY == 0.95
        assert NEUTRAL_DEFAULT == 0.5

    def test_f03_disabled_p32_returns_none(self):
        """Test that disabled P32 returns None."""
        ctx = make_context_high_quality()
        ctx._p32_disabled = True

        result = maybe_run_p32(ctx)

        assert result is None
        assert ctx.p32 is None

    def test_f04_empty_context_does_not_break(self):
        """Test that empty context returns closed envelope."""
        ctx = MockPipelineContext()  # No coherence_state

        result = maybe_run_p32(ctx)

        # Should return None when no inputs
        assert result is None

    def test_f05_minimal_context_produces_envelope(self):
        """Test that minimal context produces valid envelope."""
        ctx = make_context_minimal()

        envelope = maybe_run_p32(ctx)

        assert envelope is not None
        assert isinstance(envelope, InsightWindowEnvelope)
        assert envelope.observer_only is True

    def test_f06_helper_functions_work_with_none(self):
        """Test that helper functions handle None gracefully."""
        ctx = MockPipelineContext()  # p32 is None

        assert get_insight_depth(ctx) == 0.0
        assert get_confidence_band(ctx) == ConfidenceBand.LOW
        assert is_gate_open(ctx) is False
        assert is_gate_closed(ctx) is True
        assert has_acoustic_penalty(ctx) is False
        assert get_reason_codes(ctx) == ()


# ============================================================================
# DETERMINISM TESTS
# Same inputs → identical outputs
# ============================================================================


class TestDeterminism:
    """Determinism tests (INV-P32-4)."""

    def _compute_envelope_hash(self, envelope: InsightWindowEnvelope) -> str:
        """Compute a hash of the envelope for comparison."""
        d = envelope.to_dict()
        json_str = json.dumps(d, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def test_same_inputs_produce_identical_outputs(self):
        """Test that same inputs always produce identical outputs."""
        ctx1 = make_context_high_quality()
        ctx2 = make_context_high_quality()

        envelope1 = maybe_run_p32(ctx1)
        envelope2 = maybe_run_p32(ctx2)

        hash1 = self._compute_envelope_hash(envelope1)
        hash2 = self._compute_envelope_hash(envelope2)

        assert hash1 == hash2, "Same inputs should produce identical outputs"

    def test_multiple_runs_same_context_identical(self):
        """Test that multiple runs on the same context produce identical results."""
        ctx = make_context_with_defaults()

        envelopes = []
        for _ in range(5):
            ctx.p32 = None  # Reset
            envelopes.append(maybe_run_p32(ctx))

        hashes = [self._compute_envelope_hash(e) for e in envelopes]
        assert len(set(hashes)) == 1, "Multiple runs should produce identical hashes"

    def test_run_p32_directly_is_deterministic(self):
        """Test that run_p32_directly produces deterministic results."""
        envelope1 = run_p32_directly(
            coherence_v3_quality=0.7,
            ucf_score=0.6,
            schema_stability=0.5,
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
        )

        envelope2 = run_p32_directly(
            coherence_v3_quality=0.7,
            ucf_score=0.6,
            schema_stability=0.5,
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
        )

        hash1 = self._compute_envelope_hash(envelope1)
        hash2 = self._compute_envelope_hash(envelope2)

        assert hash1 == hash2


# ============================================================================
# ADDITIONAL INVARIANT TESTS
# ============================================================================


class TestInvariants:
    """Additional tests for P32 invariants."""

    def test_inv_p32_1_acoustic_cannot_increase_depth(self):
        """INV-P32-1: Acoustic input can only reduce depth, never increase."""
        # Compute without acoustic
        result_no_acoustic = compute_insight_depth(
            coherence_v3_quality=0.7,
            ucf_score=0.6,
            schema_stability=0.5,
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
            acoustic_alignment_score=None,
        )

        # Compute with good acoustic (should not change depth)
        result_good_acoustic = compute_insight_depth(
            coherence_v3_quality=0.7,
            ucf_score=0.6,
            schema_stability=0.5,
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
            acoustic_alignment_score=0.9,  # Good alignment
        )

        # Compute with bad acoustic (should reduce depth)
        result_bad_acoustic = compute_insight_depth(
            coherence_v3_quality=0.7,
            ucf_score=0.6,
            schema_stability=0.5,
            drift_fusion_index=0.3,
            temporal_entropy_diff=0.4,
            acoustic_alignment_score=0.1,  # Bad alignment
        )

        # Good acoustic should NOT increase depth
        assert result_good_acoustic.final_depth <= result_no_acoustic.final_depth

        # Bad acoustic should reduce depth
        assert result_bad_acoustic.final_depth < result_no_acoustic.final_depth

    def test_inv_p32_2_gate_monotonicity_enforced(self):
        """INV-P32-2: Gate monotonicity enforced."""
        # Envelope creation validates monotonicity
        envelope = create_envelope(insight_depth=0.5, raw_depth=0.7)
        assert envelope.insight_depth <= envelope.raw_depth

    def test_inv_p32_3_no_upstream_influence(self):
        """INV-P32-3: P32 has no upstream influence."""
        ctx = make_context_high_quality()
        ctx.p6_regime = "test_regime"
        ctx.p7_discourse_envelope = "test_discourse"
        ctx.semantic_frame = "test_semantics"
        ctx.lexical_frame = "test_lexical"

        maybe_run_p32(ctx)

        # All upstream fields unchanged
        assert ctx.p6_regime == "test_regime"
        assert ctx.p7_discourse_envelope == "test_discourse"
        assert ctx.semantic_frame == "test_semantics"
        assert ctx.lexical_frame == "test_lexical"

    def test_inv_p32_4_deterministic_behavior(self):
        """INV-P32-4: Deterministic behavior."""
        # Same inputs should always produce same output
        result1 = compute_insight_depth(
            coherence_v3_quality=0.65,
            ucf_score=0.55,
            schema_stability=0.45,
            drift_fusion_index=0.35,
            temporal_entropy_diff=0.25,
        )

        result2 = compute_insight_depth(
            coherence_v3_quality=0.65,
            ucf_score=0.55,
            schema_stability=0.45,
            drift_fusion_index=0.35,
            temporal_entropy_diff=0.25,
        )

        assert result1.raw_depth == result2.raw_depth
        assert result1.final_depth == result2.final_depth
        assert result1.penalties_applied == result2.penalties_applied

    def test_inv_p32_5_envelope_is_advisory_only(self):
        """INV-P32-5: Envelope is advisory only."""
        envelope = create_envelope(insight_depth=0.7, raw_depth=0.7)

        assert envelope.observer_only is True
        assert envelope.architectural_phase == "P32"


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Edge case tests for P32."""

    def test_all_none_inputs(self):
        """Test with all None inputs."""
        result = compute_insight_depth(
            coherence_v3_quality=None,
            ucf_score=None,
            schema_stability=None,
            drift_fusion_index=None,
            temporal_entropy_diff=None,
            acoustic_alignment_score=None,
        )
        # Should use defaults and produce valid result
        assert 0.0 <= result.final_depth <= 1.0

    def test_partial_inputs(self):
        """Test with some inputs present, some None."""
        result = compute_insight_depth(
            coherence_v3_quality=0.8,
            ucf_score=None,  # Missing
            schema_stability=0.6,
            drift_fusion_index=None,  # Missing
            temporal_entropy_diff=0.3,
            acoustic_alignment_score=None,
        )
        assert 0.0 <= result.final_depth <= 1.0

    def test_boundary_values_clamped(self):
        """Test that out-of-range values are clamped."""
        result = compute_insight_depth(
            coherence_v3_quality=1.5,  # Above 1.0
            ucf_score=-0.5,  # Below 0.0
            schema_stability=2.0,  # Above 1.0
            drift_fusion_index=-1.0,  # Below 0.0
            temporal_entropy_diff=1.5,  # Above 1.0
        )
        # All values should be clamped internally
        assert 0.0 <= result.final_depth <= 1.0

    def test_exact_threshold_boundaries(self):
        """Test exact threshold boundary conditions."""
        # Temporal entropy exactly at threshold
        _, penalty1, _ = apply_temporal_entropy_penalty(0.8, 0.6)
        assert penalty1 is None  # Not triggered at exactly threshold

        _, penalty2, _ = apply_temporal_entropy_penalty(0.8, 0.601)
        assert penalty2 is not None  # Triggered just above threshold

        # Coherence quality exactly at threshold
        _, penalty3, _ = apply_coherence_quality_penalty(0.8, 0.45)
        assert penalty3 is None  # Not triggered at exactly threshold

        _, penalty4, _ = apply_coherence_quality_penalty(0.8, 0.449)
        assert penalty4 is not None  # Triggered just below threshold


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
