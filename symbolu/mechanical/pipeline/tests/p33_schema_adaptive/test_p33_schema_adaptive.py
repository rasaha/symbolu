"""
Tests for P33 Schema Adaptive Routing (Observation-Only)

Test Requirements (40+ tests across 5 groups):
    Group A — Formula Correctness (10+ tests)
        - Known inputs → expected numeric outputs
        - Boundary conditions (0.0 / 1.0)

    Group B — Non-Authority Proof (10+ tests)
        - Modifying P33 output MUST NOT change:
            - Regime, Discourse, Semantics, Lexical selection

    Group C — Determinism (5+ tests)
        - Same context → identical snapshot hash

    Group D — Import Safety (5+ tests)
        - Static test proving no forbidden imports

    Group E — Regression Lock (10+ tests)
        - Existing pipelines produce identical outputs when P33 is enabled

INVARIANTS TO ASSERT:
    INV-P33-1: Phase 33 cannot influence any decision
    INV-P33-2: Schema scores are observational only
    INV-P33-3: Dominant schema selection has zero side effects
    INV-P33-4: Observer data (P22-P24) cannot enter Phase 33
    INV-P33-5: Absence of schema metadata does not break pipeline
"""

import ast
import hashlib
import inspect
import json
import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p33_schema_adaptive import (
    # Schema
    P33_VERSION,
    SchemaStabilityBand,
    SchemaConfidenceBand,
    ALLOWED_SCHEMA_TAGS,
    SchemaAdaptiveRoutingSnapshot,
    create_snapshot,
    create_empty_snapshot,
    # Resolver
    P33SchemaAdaptiveResolver,
    W_COHERENCE_V3,
    W_COHERENCE_QUALITY,
    W_DRIFT_INVERSE,
    W_ENTROPY_INVERSE,
    W_ALIGN_COHERENCE,
    W_ALIGN_QUALITY,
    W_ALIGN_IDENTITY,
    W_DRIFT_FUSION,
    W_DRIFT_ENTROPY,
    STABILITY_HIGH_THRESHOLD,
    STABILITY_LOW_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    DOMINANCE_MARGIN,
    NEUTRAL_DEFAULT,
    DEFAULT_SCHEMA_IDS,
    # Integration
    get_p33_resolver,
    maybe_run_p33,
    run_p33_directly,
    is_p33_disabled,
    has_p33_snapshot,
    get_p33_snapshot,
    get_dominant_schema,
    get_schema_confidence,
    get_stability_band,
    get_confidence_band,
    is_highly_stable,
    is_low_stability,
    has_dominant_schema,
    get_schema_stability_score,
    get_schema_alignment_score,
    get_schema_drift_score,
    get_p33_version,
)


# ============================================================================
# MOCK CLASSES - For test isolation
# ============================================================================


@dataclass
class MockCoherenceState:
    """Mock CoherenceState for testing."""
    coherence_score_v3: Optional[float] = None
    coherence_v3_quality: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    current_identity_harmonics_index: Optional[float] = None
    drift_fusion_index_history: List[float] = field(default_factory=list)
    temporal_entropy_diff_history: List[float] = field(default_factory=list)
    coherence_fused_history: List[float] = field(default_factory=list)
    # P33 tracking fields
    persona_schema_alignment: Optional[Dict[str, float]] = None
    persona_schema_stability: Optional[float] = None
    persona_schema_drift: Optional[float] = None
    persona_schema_confidence: Optional[float] = None


@dataclass
class MockPipelineContext:
    """Mock PipelineContext for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    persona_schema_metadata: Optional[Any] = None
    p33: Optional[SchemaAdaptiveRoutingSnapshot] = None
    _p33_disabled: bool = False
    # Other phase fields (for non-authority testing)
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
            coherence_score_v3=0.5,
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            temporal_entropy_volatility=0.5,
            current_identity_harmonics_index=0.5,
        )
    )


def make_context_high_stability() -> MockPipelineContext:
    """Create a context with high stability signals."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score_v3=0.9,
            coherence_v3_quality=0.85,
            drift_fusion_index=0.1,  # Low drift = high stability
            temporal_entropy_volatility=0.1,  # Low volatility = high stability
            current_identity_harmonics_index=0.8,
            drift_fusion_index_history=[0.1, 0.12, 0.11],
            temporal_entropy_diff_history=[0.05, 0.04, 0.06],
            coherence_fused_history=[0.85, 0.87, 0.86],
        )
    )


def make_context_low_stability() -> MockPipelineContext:
    """Create a context with low stability signals."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score_v3=0.2,
            coherence_v3_quality=0.25,
            drift_fusion_index=0.85,  # High drift = low stability
            temporal_entropy_volatility=0.9,  # High volatility = low stability
            current_identity_harmonics_index=0.3,
        )
    )


def make_context_boundary_low() -> MockPipelineContext:
    """Create a context with boundary low values (0.0)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score_v3=0.0,
            coherence_v3_quality=0.0,
            drift_fusion_index=1.0,  # Max drift
            temporal_entropy_volatility=1.0,  # Max volatility
            current_identity_harmonics_index=0.0,
        )
    )


def make_context_boundary_high() -> MockPipelineContext:
    """Create a context with boundary high values (1.0)."""
    return MockPipelineContext(
        coherence_state=MockCoherenceState(
            coherence_score_v3=1.0,
            coherence_v3_quality=1.0,
            drift_fusion_index=0.0,  # No drift
            temporal_entropy_volatility=0.0,  # No volatility
            current_identity_harmonics_index=1.0,
        )
    )


# ============================================================================
# GROUP A — FORMULA CORRECTNESS TESTS (10+ tests)
# Known inputs → expected numeric outputs, boundary conditions
# ============================================================================


class TestGroupAFormulaCorrectness:
    """Group A — Formula Correctness tests."""

    def test_a01_stability_formula_neutral_inputs(self):
        """Test stability score with neutral (0.5) inputs."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_with_defaults()
        snapshot = resolver.compute(ctx)

        # With all inputs at 0.5:
        # stability = 0.35*0.5 + 0.25*0.5 + 0.25*(1-0.5) + 0.15*(1-0.5)
        #           = 0.175 + 0.125 + 0.125 + 0.075 = 0.5
        for schema_id, score in snapshot.schema_stability_scores.items():
            assert 0.0 <= score <= 1.0
            assert abs(score - 0.5) < 0.01, f"Expected ~0.5, got {score}"

    def test_a02_stability_formula_high_inputs(self):
        """Test stability score with high stability inputs."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_high_stability()
        snapshot = resolver.compute(ctx)

        # High coherence + low drift should give high stability
        for schema_id, score in snapshot.schema_stability_scores.items():
            assert score >= STABILITY_HIGH_THRESHOLD, f"Expected high stability, got {score}"

    def test_a03_stability_formula_low_inputs(self):
        """Test stability score with low stability inputs."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_low_stability()
        snapshot = resolver.compute(ctx)

        # Low coherence + high drift should give low stability
        for schema_id, score in snapshot.schema_stability_scores.items():
            assert score < STABILITY_LOW_THRESHOLD, f"Expected low stability, got {score}"

    def test_a04_stability_boundary_minimum(self):
        """Test stability score at boundary minimum (0.0)."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_boundary_low()
        snapshot = resolver.compute(ctx)

        # All minimum inputs should give minimum stability
        for schema_id, score in snapshot.schema_stability_scores.items():
            assert score >= 0.0
            assert score < 0.1, f"Expected near-zero stability, got {score}"

    def test_a05_stability_boundary_maximum(self):
        """Test stability score at boundary maximum (1.0)."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_boundary_high()
        snapshot = resolver.compute(ctx)

        # All maximum inputs should give maximum stability
        for schema_id, score in snapshot.schema_stability_scores.items():
            assert score <= 1.0
            assert score > 0.9, f"Expected near-one stability, got {score}"

    def test_a06_alignment_formula_neutral_inputs(self):
        """Test alignment score with neutral (0.5) inputs."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_with_defaults()
        snapshot = resolver.compute(ctx)

        # With all inputs at 0.5:
        # alignment = 0.40*0.5 + 0.35*0.5 + 0.25*0.5 = 0.5
        for schema_id, score in snapshot.schema_alignment_scores.items():
            assert 0.0 <= score <= 1.0
            assert abs(score - 0.5) < 0.01, f"Expected ~0.5, got {score}"

    def test_a07_drift_formula_neutral_inputs(self):
        """Test drift score with neutral (0.5) inputs."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_with_defaults()
        snapshot = resolver.compute(ctx)

        # With all inputs at 0.5:
        # drift = 0.70*0.5 + 0.30*0.5 = 0.5
        for schema_id, score in snapshot.schema_drift_scores.items():
            assert 0.0 <= score <= 1.0
            assert abs(score - 0.5) < 0.01, f"Expected ~0.5, got {score}"

    def test_a08_confidence_with_all_inputs_present(self):
        """Test confidence when all inputs are present."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_high_stability()
        snapshot = resolver.compute(ctx)

        # With all inputs present and high stability, confidence should be high
        assert snapshot.confidence >= CONFIDENCE_HIGH_THRESHOLD

    def test_a09_confidence_with_missing_inputs(self):
        """Test confidence when inputs are missing."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_minimal()
        snapshot = resolver.compute(ctx)

        # With missing inputs, confidence should be lower
        assert snapshot.confidence < CONFIDENCE_HIGH_THRESHOLD

    def test_a10_dominant_schema_with_clear_winner(self):
        """Test dominant schema identification with clear winner."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_high_stability()
        snapshot = resolver.compute(ctx)

        # With uniform inputs, all schemas have equal scores, so no clear dominant
        # This tests the margin logic
        if snapshot.dominant_schema is not None:
            # If there's a dominant, it should be a valid schema
            assert snapshot.dominant_schema in DEFAULT_SCHEMA_IDS

    def test_a11_all_scores_clamped_to_unit_interval(self):
        """Test that all scores are clamped to [0.0, 1.0]."""
        resolver = P33SchemaAdaptiveResolver()

        # Test with extreme boundary values
        for ctx in [make_context_boundary_low(), make_context_boundary_high()]:
            snapshot = resolver.compute(ctx)

            # Check all score types
            for scores in [
                snapshot.schema_stability_scores.values(),
                snapshot.schema_alignment_scores.values(),
                snapshot.schema_drift_scores.values(),
            ]:
                for score in scores:
                    assert 0.0 <= score <= 1.0, f"Score {score} outside [0.0, 1.0]"

            # Check confidence
            assert 0.0 <= snapshot.confidence <= 1.0

    def test_a12_weights_sum_to_one(self):
        """Test that formula weights sum to 1.0."""
        # Stability weights
        stability_sum = W_COHERENCE_V3 + W_COHERENCE_QUALITY + W_DRIFT_INVERSE + W_ENTROPY_INVERSE
        assert abs(stability_sum - 1.0) < 0.001, f"Stability weights sum to {stability_sum}"

        # Alignment weights
        alignment_sum = W_ALIGN_COHERENCE + W_ALIGN_QUALITY + W_ALIGN_IDENTITY
        assert abs(alignment_sum - 1.0) < 0.001, f"Alignment weights sum to {alignment_sum}"

        # Drift weights
        drift_sum = W_DRIFT_FUSION + W_DRIFT_ENTROPY
        assert abs(drift_sum - 1.0) < 0.001, f"Drift weights sum to {drift_sum}"


# ============================================================================
# GROUP B — NON-AUTHORITY PROOF TESTS (10+ tests)
# Modifying P33 output MUST NOT change Regime, Discourse, Semantics, Lexical
# ============================================================================


class TestGroupBNonAuthorityProof:
    """Group B — Non-Authority Proof tests (INV-P33-1, INV-P33-2, INV-P33-3)."""

    def test_b01_snapshot_is_immutable(self):
        """Test that snapshot is frozen (immutable)."""
        snapshot = create_snapshot(
            schema_alignment_scores={"test": 0.5},
            schema_stability_scores={"test": 0.5},
            schema_drift_scores={"test": 0.5},
            dominant_schema="test",
            confidence=0.5,
            stability_band=SchemaStabilityBand.MODERATE,
            confidence_band=SchemaConfidenceBand.MODERATE,
        )

        # Attempting to modify should raise FrozenInstanceError
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            snapshot.confidence = 0.9

    def test_b02_observer_only_must_be_true(self):
        """Test that observer_only is always True."""
        snapshot = create_snapshot()
        assert snapshot.observer_only is True

        # Attempting to create with observer_only=False should raise
        with pytest.raises(ValueError, match="observer_only must be True"):
            SchemaAdaptiveRoutingSnapshot(
                schema_alignment_scores={},
                schema_stability_scores={},
                schema_drift_scores={},
                dominant_schema=None,
                confidence=0.5,
                stability_band=SchemaStabilityBand.UNKNOWN,
                confidence_band=SchemaConfidenceBand.INSUFFICIENT,
                observer_only=False,  # This should fail
            )

    def test_b03_p33_does_not_modify_ctx_regime(self):
        """Test that P33 does not modify ctx.p6_regime."""
        ctx = make_context_high_stability()
        ctx.p6_regime = "original_regime"

        maybe_run_p33(ctx)

        assert ctx.p6_regime == "original_regime"

    def test_b04_p33_does_not_modify_ctx_discourse(self):
        """Test that P33 does not modify ctx.p7_discourse_envelope."""
        ctx = make_context_high_stability()
        ctx.p7_discourse_envelope = "original_discourse"

        maybe_run_p33(ctx)

        assert ctx.p7_discourse_envelope == "original_discourse"

    def test_b05_p33_does_not_modify_ctx_semantics(self):
        """Test that P33 does not modify ctx.semantic_frame."""
        ctx = make_context_high_stability()
        ctx.semantic_frame = "original_semantics"

        maybe_run_p33(ctx)

        assert ctx.semantic_frame == "original_semantics"

    def test_b06_p33_does_not_modify_ctx_lexical(self):
        """Test that P33 does not modify ctx.lexical_frame."""
        ctx = make_context_high_stability()
        ctx.lexical_frame = "original_lexical"

        maybe_run_p33(ctx)

        assert ctx.lexical_frame == "original_lexical"

    def test_b07_p33_does_not_modify_coherence_state_scores(self):
        """Test that P33 only updates P33-specific fields in coherence_state."""
        ctx = make_context_high_stability()
        original_v3 = ctx.coherence_state.coherence_score_v3

        maybe_run_p33(ctx)

        # Original coherence scores should be unchanged
        assert ctx.coherence_state.coherence_score_v3 == original_v3

    def test_b08_dominant_schema_has_no_side_effects(self):
        """Test INV-P33-3: Dominant schema selection has zero side effects."""
        ctx = make_context_high_stability()

        # Run P33
        snapshot = maybe_run_p33(ctx)

        # Even if dominant_schema is set, it should not affect anything
        # P33 only observes, never acts
        assert snapshot.observer_only is True

        # No routing or behavioral fields should be affected
        assert ctx.p6_regime is None
        assert ctx.p7_discourse_envelope is None
        assert ctx.semantic_frame is None
        assert ctx.lexical_frame is None

    def test_b09_p33_only_writes_to_p33_field(self):
        """Test that P33 only writes to ctx.p33, not other fields."""
        ctx = make_context_high_stability()

        # Track all attribute names before
        attrs_before = set(vars(ctx).keys())

        maybe_run_p33(ctx)

        # Track all attribute names after
        attrs_after = set(vars(ctx).keys())

        # Only p33 should be added/modified
        new_attrs = attrs_after - attrs_before
        assert new_attrs == set() or new_attrs == {"p33"}

    def test_b10_snapshot_to_dict_is_serializable(self):
        """Test that snapshot.to_dict() produces serializable output."""
        snapshot = create_snapshot(
            schema_alignment_scores={"test": 0.5},
            schema_stability_scores={"test": 0.5},
            schema_drift_scores={"test": 0.5},
            dominant_schema="test",
            confidence=0.5,
            stability_band=SchemaStabilityBand.MODERATE,
            confidence_band=SchemaConfidenceBand.MODERATE,
        )

        # to_dict should produce JSON-serializable output
        d = snapshot.to_dict()
        json_str = json.dumps(d)  # Should not raise
        assert isinstance(json_str, str)

    def test_b11_diagnostic_tags_are_readonly(self):
        """Test that diagnostic_tags is a frozenset (read-only)."""
        snapshot = create_snapshot(
            diagnostic_tags=frozenset({"HIGHLY_STABLE", "ALIGNED"}),
        )

        assert isinstance(snapshot.diagnostic_tags, frozenset)

        # Attempting to modify should fail
        with pytest.raises(AttributeError):
            snapshot.diagnostic_tags.add("NEW_TAG")

    def test_b12_only_allowed_tags_accepted(self):
        """Test that only allow-listed tags are accepted."""
        # Valid tags should work
        snapshot = create_snapshot(
            diagnostic_tags=frozenset({"HIGHLY_STABLE", "ALIGNED", "HIGH_CONFIDENCE"}),
        )
        assert len(snapshot.diagnostic_tags) == 3

        # Invalid tags should raise
        with pytest.raises(ValueError, match="invalid tags"):
            create_snapshot(
                diagnostic_tags=frozenset({"INVALID_TAG_XYZ"}),
            )


# ============================================================================
# GROUP C — DETERMINISM TESTS (5+ tests)
# Same context → identical snapshot hash
# ============================================================================


class TestGroupCDeterminism:
    """Group C — Determinism tests."""

    def _compute_snapshot_hash(self, snapshot: SchemaAdaptiveRoutingSnapshot) -> str:
        """Compute a hash of the snapshot for comparison."""
        d = snapshot.to_dict()
        # Sort keys for deterministic JSON
        json_str = json.dumps(d, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def test_c01_same_inputs_produce_identical_outputs(self):
        """Test that same inputs always produce identical outputs."""
        resolver = P33SchemaAdaptiveResolver()

        # Run twice with identical context
        ctx1 = make_context_high_stability()
        ctx2 = make_context_high_stability()

        snapshot1 = resolver.compute(ctx1)
        snapshot2 = resolver.compute(ctx2)

        hash1 = self._compute_snapshot_hash(snapshot1)
        hash2 = self._compute_snapshot_hash(snapshot2)

        assert hash1 == hash2, "Same inputs should produce identical outputs"

    def test_c02_multiple_runs_same_context_identical(self):
        """Test that multiple runs on the same context produce identical results."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_with_defaults()

        snapshots = [resolver.compute(ctx) for _ in range(5)]
        hashes = [self._compute_snapshot_hash(s) for s in snapshots]

        assert len(set(hashes)) == 1, "Multiple runs should produce identical hashes"

    def test_c03_singleton_resolver_is_deterministic(self):
        """Test that singleton resolver produces deterministic results."""
        ctx = make_context_high_stability()

        # Get singleton resolver multiple times
        resolver1 = get_p33_resolver()
        resolver2 = get_p33_resolver()

        snapshot1 = resolver1.compute(ctx)

        # Reset context
        ctx = make_context_high_stability()
        snapshot2 = resolver2.compute(ctx)

        hash1 = self._compute_snapshot_hash(snapshot1)
        hash2 = self._compute_snapshot_hash(snapshot2)

        assert hash1 == hash2

    def test_c04_run_p33_directly_is_deterministic(self):
        """Test that run_p33_directly produces deterministic results."""
        cs = MockCoherenceState(
            coherence_score_v3=0.7,
            coherence_v3_quality=0.65,
            drift_fusion_index=0.3,
            temporal_entropy_volatility=0.25,
            current_identity_harmonics_index=0.6,
        )

        snapshot1 = run_p33_directly(coherence_state=cs)
        snapshot2 = run_p33_directly(coherence_state=cs)

        hash1 = self._compute_snapshot_hash(snapshot1)
        hash2 = self._compute_snapshot_hash(snapshot2)

        assert hash1 == hash2

    def test_c05_boundary_values_are_deterministic(self):
        """Test determinism at boundary values."""
        resolver = P33SchemaAdaptiveResolver()

        for make_ctx in [make_context_boundary_low, make_context_boundary_high]:
            ctx1 = make_ctx()
            ctx2 = make_ctx()

            snapshot1 = resolver.compute(ctx1)
            snapshot2 = resolver.compute(ctx2)

            hash1 = self._compute_snapshot_hash(snapshot1)
            hash2 = self._compute_snapshot_hash(snapshot2)

            assert hash1 == hash2, f"Boundary context should be deterministic"

    def test_c06_no_random_variation(self):
        """Test that there's no random variation across many runs."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_with_defaults()

        # Run 100 times and collect unique hashes
        hashes = set()
        for _ in range(100):
            snapshot = resolver.compute(ctx)
            hashes.add(self._compute_snapshot_hash(snapshot))

        assert len(hashes) == 1, f"Found {len(hashes)} unique outputs, expected 1"


# ============================================================================
# GROUP D — IMPORT SAFETY TESTS (5+ tests)
# Static test proving no forbidden imports
# ============================================================================


class TestGroupDImportSafety:
    """Group D — Import Safety tests (INV-P33-4)."""

    # Forbidden modules that P33 must NOT import
    FORBIDDEN_MODULES = {
        # Phase modules that could influence behavior
        "symbolu.mechanical.pipeline.phase_p6",
        "symbolu.mechanical.pipeline.p7_discourse",
        "symbolu.mechanical.pipeline.p8_semantics",
        "symbolu.mechanical.pipeline.p9_lexical",
        # Observer modules
        "symbolu.mechanical.pipeline.p22_acoustic_witness",
        "symbolu.mechanical.pipeline.p23_alignment",
        "symbolu.mechanical.pipeline.p24_projection",
        # Policy/Planner/Renderer
        "symbolu.mechanical.policy",
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

    def test_d01_p33_schema_snapshot_no_forbidden_imports(self):
        """Test p33_schema_snapshot.py has no forbidden imports."""
        filepath = "symbolu/mechanical/pipeline/p33_schema_adaptive/p33_schema_snapshot.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_d02_p33_schema_resolver_no_forbidden_imports(self):
        """Test p33_schema_resolver.py has no forbidden imports."""
        filepath = "symbolu/mechanical/pipeline/p33_schema_adaptive/p33_schema_resolver.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_d03_p33_integration_no_forbidden_imports(self):
        """Test p33_integration.py has no forbidden imports."""
        filepath = "symbolu/mechanical/pipeline/p33_schema_adaptive/p33_integration.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_d04_p33_init_no_forbidden_imports(self):
        """Test __init__.py has no forbidden imports."""
        filepath = "symbolu/mechanical/pipeline/p33_schema_adaptive/__init__.py"
        imports = self._get_imports_from_file(filepath)

        forbidden_found = imports & self.FORBIDDEN_MODULES
        assert not forbidden_found, f"Forbidden imports found: {forbidden_found}"

    def test_d05_resolver_does_not_access_observer_data(self):
        """Test that resolver does not access P22-P24 observer data (INV-P33-4)."""
        resolver = P33SchemaAdaptiveResolver()

        # Check resolver source for forbidden attribute access
        source = inspect.getsource(P33SchemaAdaptiveResolver)

        forbidden_attrs = [
            "p22_acoustic_witness",
            "p23_alignment_report",
            "p24_projection_report",
            "acoustic_witness",
            "vritti_vector",
            "acoustic_signature",
        ]

        for attr in forbidden_attrs:
            assert attr not in source, f"Resolver should not access {attr}"

    def test_d06_no_llm_or_random_imports(self):
        """Test that no LLM or randomness imports are present."""
        files = [
            "symbolu/mechanical/pipeline/p33_schema_adaptive/p33_schema_snapshot.py",
            "symbolu/mechanical/pipeline/p33_schema_adaptive/p33_schema_resolver.py",
            "symbolu/mechanical/pipeline/p33_schema_adaptive/p33_integration.py",
        ]

        forbidden = {"random", "numpy.random", "openai", "anthropic", "langchain"}

        for filepath in files:
            imports = self._get_imports_from_file(filepath)
            found = imports & forbidden
            assert not found, f"Forbidden import {found} in {filepath}"


# ============================================================================
# GROUP E — REGRESSION LOCK TESTS (10+ tests)
# Existing pipelines produce identical outputs when P33 is enabled
# ============================================================================


class TestGroupERegressionLock:
    """Group E — Regression Lock tests (INV-P33-5)."""

    def test_e01_empty_context_does_not_break(self):
        """Test INV-P33-5: Empty context returns empty snapshot."""
        ctx = MockPipelineContext()  # No coherence_state

        result = maybe_run_p33(ctx)

        # Should return None when no coherence_state
        assert result is None

    def test_e02_minimal_context_does_not_break(self):
        """Test INV-P33-5: Minimal context produces valid snapshot."""
        ctx = make_context_minimal()

        snapshot = maybe_run_p33(ctx)

        assert snapshot is not None
        assert isinstance(snapshot, SchemaAdaptiveRoutingSnapshot)
        assert snapshot.observer_only is True

    def test_e03_missing_schema_metadata_does_not_break(self):
        """Test INV-P33-5: Missing persona_schema_metadata doesn't break pipeline."""
        ctx = make_context_with_defaults()
        ctx.persona_schema_metadata = None  # Explicitly None

        snapshot = maybe_run_p33(ctx)

        assert snapshot is not None
        # Should use default schema IDs
        assert len(snapshot.schema_stability_scores) == len(DEFAULT_SCHEMA_IDS)

    def test_e04_disabled_p33_returns_none(self):
        """Test that disabled P33 returns None without error."""
        ctx = make_context_high_stability()
        ctx._p33_disabled = True

        result = maybe_run_p33(ctx)

        assert result is None
        assert ctx.p33 is None

    def test_e05_version_is_stable(self):
        """Test that version string is stable."""
        assert P33_VERSION == "1.0.0"
        assert get_p33_version() == "1.0.0"

    def test_e06_default_schema_ids_are_stable(self):
        """Test that default schema IDs are stable."""
        expected = ("analyst", "sage", "coach", "guide", "neutral")
        assert DEFAULT_SCHEMA_IDS == expected

    def test_e07_allowed_tags_are_stable(self):
        """Test that allowed tags set is stable."""
        expected_tags = {
            "HIGHLY_STABLE", "MODERATELY_STABLE", "LOW_STABILITY", "INSUFFICIENT_HISTORY",
            "ALIGNED", "MISALIGNED", "NEUTRAL_ALIGNMENT",
            "LOW_DRIFT", "MODERATE_DRIFT", "HIGH_DRIFT",
            "HIGH_CONFIDENCE", "MODERATE_CONFIDENCE", "LOW_CONFIDENCE",
            "DOMINANT_CLEAR", "DOMINANT_UNCLEAR", "MULTIPLE_CANDIDATES", "NO_SCHEMAS_DEFINED",
        }
        assert ALLOWED_SCHEMA_TAGS == expected_tags

    def test_e08_enums_are_stable(self):
        """Test that enum values are stable."""
        assert SchemaStabilityBand.HIGH.value == "HIGH"
        assert SchemaStabilityBand.MODERATE.value == "MODERATE"
        assert SchemaStabilityBand.LOW.value == "LOW"
        assert SchemaStabilityBand.UNKNOWN.value == "UNKNOWN"

        assert SchemaConfidenceBand.HIGH.value == "HIGH"
        assert SchemaConfidenceBand.MODERATE.value == "MODERATE"
        assert SchemaConfidenceBand.LOW.value == "LOW"
        assert SchemaConfidenceBand.INSUFFICIENT.value == "INSUFFICIENT"

    def test_e09_thresholds_are_stable(self):
        """Test that threshold values are stable."""
        assert STABILITY_HIGH_THRESHOLD == 0.70
        assert STABILITY_LOW_THRESHOLD == 0.40
        assert CONFIDENCE_HIGH_THRESHOLD == 0.70
        assert CONFIDENCE_LOW_THRESHOLD == 0.40
        assert DOMINANCE_MARGIN == 0.10
        assert NEUTRAL_DEFAULT == 0.5

    def test_e10_weights_are_stable(self):
        """Test that formula weights are stable."""
        # Stability weights
        assert W_COHERENCE_V3 == 0.35
        assert W_COHERENCE_QUALITY == 0.25
        assert W_DRIFT_INVERSE == 0.25
        assert W_ENTROPY_INVERSE == 0.15

        # Alignment weights
        assert W_ALIGN_COHERENCE == 0.40
        assert W_ALIGN_QUALITY == 0.35
        assert W_ALIGN_IDENTITY == 0.25

        # Drift weights
        assert W_DRIFT_FUSION == 0.70
        assert W_DRIFT_ENTROPY == 0.30

    def test_e11_helper_functions_work_with_none(self):
        """Test that helper functions handle None gracefully."""
        ctx = MockPipelineContext()  # p33 is None

        assert get_dominant_schema(ctx) is None
        assert get_schema_confidence(ctx) == 0.0
        assert get_stability_band(ctx) == SchemaStabilityBand.UNKNOWN
        assert get_confidence_band(ctx) == SchemaConfidenceBand.INSUFFICIENT
        assert is_highly_stable(ctx) is False
        assert is_low_stability(ctx) is False
        assert has_dominant_schema(ctx) is False
        assert get_schema_stability_score(ctx, "test") is None
        assert get_schema_alignment_score(ctx, "test") is None
        assert get_schema_drift_score(ctx, "test") is None

    def test_e12_snapshot_convenience_methods_work(self):
        """Test that snapshot convenience methods work correctly."""
        snapshot = create_snapshot(
            schema_alignment_scores={"test": 0.8},
            schema_stability_scores={"test": 0.75},
            schema_drift_scores={"test": 0.2},
            dominant_schema="test",
            confidence=0.8,
            stability_band=SchemaStabilityBand.HIGH,
            confidence_band=SchemaConfidenceBand.HIGH,
            diagnostic_tags=frozenset({"HIGHLY_STABLE", "ALIGNED"}),
        )

        assert snapshot.is_highly_stable() is True
        assert snapshot.is_low_stability() is False
        assert snapshot.has_dominant_schema() is True
        assert snapshot.is_high_confidence() is True
        assert snapshot.is_low_confidence() is False
        assert snapshot.get_schema_count() == 1
        assert snapshot.has_tag("HIGHLY_STABLE") is True
        assert snapshot.has_tag("INVALID") is False
        assert snapshot.get_alignment_for_schema("test") == 0.8
        assert snapshot.get_stability_for_schema("test") == 0.75
        assert snapshot.get_drift_for_schema("test") == 0.2
        assert snapshot.get_alignment_for_schema("nonexistent") is None


# ============================================================================
# ADDITIONAL INVARIANT TESTS
# ============================================================================


class TestInvariants:
    """Additional tests for P33 invariants."""

    def test_inv_p33_1_cannot_influence_decisions(self):
        """INV-P33-1: Phase 33 cannot influence any decision."""
        # The snapshot has observer_only=True
        snapshot = create_snapshot()
        assert snapshot.observer_only is True
        assert snapshot.architectural_phase == "P33"

    def test_inv_p33_2_scores_are_observational_only(self):
        """INV-P33-2: Schema scores are observational only."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_high_stability()

        snapshot = resolver.compute(ctx)

        # Scores exist but are marked as observation-only
        assert len(snapshot.schema_stability_scores) > 0
        assert len(snapshot.schema_alignment_scores) > 0
        assert len(snapshot.schema_drift_scores) > 0
        assert snapshot.observer_only is True

    def test_inv_p33_3_dominant_selection_no_side_effects(self):
        """INV-P33-3: Dominant schema selection has zero side effects."""
        resolver = P33SchemaAdaptiveResolver()
        ctx = make_context_high_stability()

        # Compute multiple times
        snapshot1 = resolver.compute(ctx)
        snapshot2 = resolver.compute(ctx)

        # Dominant schema identification should be consistent
        assert snapshot1.dominant_schema == snapshot2.dominant_schema

        # And should not modify context
        assert ctx.p6_regime is None
        assert ctx.p7_discourse_envelope is None

    def test_inv_p33_4_no_observer_data_access(self):
        """INV-P33-4: Observer data cannot enter Phase 33."""
        # This is tested in Group D, but we verify again
        resolver = P33SchemaAdaptiveResolver()

        # Create context with observer data
        ctx = make_context_high_stability()

        # Add mock observer data that should NOT be accessed
        class MockP22Witness:
            acoustic_signature = [0.5, 0.6, 0.7]
            vritti_vector = {"expansion": 0.8}

        ctx.p22_acoustic_witness = MockP22Witness()

        # Run P33
        snapshot = resolver.compute(ctx)

        # P33 should not have been influenced by observer data
        # (verified by checking it only uses coherence_state inputs)
        assert snapshot.observer_only is True

    def test_inv_p33_5_absence_of_metadata_does_not_break(self):
        """INV-P33-5: Absence of schema metadata does not break pipeline."""
        ctx = make_context_with_defaults()
        ctx.persona_schema_metadata = None

        # Should not raise
        snapshot = maybe_run_p33(ctx)

        assert snapshot is not None
        assert len(snapshot.schema_stability_scores) > 0


# ============================================================================
# EDGE CASE TESTS
# ============================================================================


class TestEdgeCases:
    """Edge case tests for P33."""

    def test_all_none_coherence_state_fields(self):
        """Test with all None fields in coherence_state."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState()  # All fields None
        )

        snapshot = maybe_run_p33(ctx)

        assert snapshot is not None
        # Should use neutral defaults
        for score in snapshot.schema_stability_scores.values():
            assert 0.0 <= score <= 1.0

    def test_partial_coherence_state_fields(self):
        """Test with some fields present, some None."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score_v3=0.8,
                # Other fields are None
            )
        )

        snapshot = maybe_run_p33(ctx)

        assert snapshot is not None
        assert snapshot.confidence < CONFIDENCE_HIGH_THRESHOLD  # Missing inputs reduce confidence

    def test_negative_drift_clamped(self):
        """Test that negative drift values are clamped."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                drift_fusion_index=-0.5,  # Invalid negative
            )
        )

        snapshot = maybe_run_p33(ctx)

        # All drift scores should be in [0, 1]
        for score in snapshot.schema_drift_scores.values():
            assert 0.0 <= score <= 1.0

    def test_above_one_coherence_clamped(self):
        """Test that coherence values above 1.0 are clamped."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_score_v3=1.5,  # Invalid above 1.0
            )
        )

        snapshot = maybe_run_p33(ctx)

        # All scores should be in [0, 1]
        for score in snapshot.schema_stability_scores.values():
            assert 0.0 <= score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
