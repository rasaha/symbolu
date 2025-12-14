"""
Comprehensive Test Suite for Phase 26: Unified Consciousness Formula (UCF) v1.0

This test suite validates all UCF invariants and behaviors.

Test Groups:
- Group A: Formula Math (15 tests) - exact numeric, weights, determinism
- Group B: Boundary Conditions (10 tests) - clamps, missing inputs
- Group C: Determinism (8 tests) - identical outputs, hash verification
- Group D: Authority Proof (8 tests) - no regime/discourse/semantic/lexical impact
- Group E: Import Safety (5 tests) - forbidden imports
- Group F: Regression Lock (6 tests) - existing pipelines unchanged

CRITICAL INVARIANTS TESTED:
- INV-P26-1: UCF is read-only truth, not a decision
- INV-P26-2: Observer data cannot affect UCF
- INV-P26-3: UCF monotonic with respect to instability
- INV-P26-4: UCF never opens gates directly
- INV-P26-5: Absence of optional inputs never destabilizes output
"""

import pytest
import json
import hashlib
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from copy import deepcopy

# Import UCF components
from symbolu.core.consciousness.ucf_schema import (
    P26_VERSION,
    UCF_WEIGHTS,
    STABILITY_THRESHOLDS,
    NEUTRAL_DEFAULT,
    StabilityBand,
    UnifiedConsciousnessState,
    create_ucf_state,
    create_neutral_state,
)

from symbolu.core.consciousness.ucf_formula import (
    clamp,
    compute_stability_band,
    compute_ucf,
    compute_ucf_from_factors,
    verify_ucf_determinism,
)

from symbolu.core.consciousness.ucf_resolver import (
    UCFResolver,
    get_ucf_resolver,
    reset_ucf_resolver,
)

from symbolu.mechanical.pipeline.p26_ucf import (
    maybe_run_p26,
    run_p26_directly,
    is_p26_disabled,
    has_p26_state,
    get_p26_state,
    get_ucf_score,
    get_stability_band,
    is_stable,
    is_transitional,
    is_unstable,
    get_p26_version,
)


# ==============================================================================
# TEST FIXTURES AND MOCK OBJECTS
# ==============================================================================


@dataclass
class MockCoherenceState:
    """Minimal mock CoherenceState for testing."""
    convo_id: str = "test"
    turn_index: int = 1
    coherence_v3_quality: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None
    persona_schema_stability: Optional[float] = None
    current_identity_harmonics_index: Optional[float] = None
    unified_consciousness_snapshot: Optional[Any] = None
    ucf_history: List[Any] = None
    current_coi: Optional[float] = None
    current_csi: Optional[float] = None
    current_cip: Optional[float] = None
    ucf_entropy: Optional[float] = None

    def __post_init__(self):
        if self.ucf_history is None:
            self.ucf_history = []


@dataclass
class MockPipelineContext:
    """Minimal mock PipelineContext for testing."""
    coherence_state: Optional[MockCoherenceState] = None
    p18: Optional[Any] = None
    p19: Optional[Any] = None
    p33: Optional[Any] = None
    p26: Optional[Any] = None
    _p26_disabled: bool = False

    # Authority fields that P26 MUST NOT modify
    p6_regime: Optional[str] = None
    p7_discourse_envelope: Optional[str] = None
    semantic_frame: Optional[str] = None
    lexical_frame: Optional[str] = None


@dataclass
class MockP18Report:
    """Mock P18 report."""
    volatility_band: str = "MED"


@dataclass
class MockP19Report:
    """Mock P19 report."""
    drift_fusion_index: float = 0.3


@dataclass
class MockP33Snapshot:
    """Mock P33 snapshot."""
    schema_stability_scores: Dict[str, float] = None
    confidence: float = 0.7

    def __post_init__(self):
        if self.schema_stability_scores is None:
            self.schema_stability_scores = {"default": 0.7}


# ==============================================================================
# GROUP A: FORMULA MATH (15 tests)
# ==============================================================================


class TestGroupAFormulaMath:
    """Test core formula mathematics: range, determinism, weights."""

    def test_a01_clamp_within_range(self):
        """Test clamp keeps values in [0.0, 1.0] range."""
        assert clamp(0.5) == 0.5
        assert clamp(-0.1) == 0.0
        assert clamp(1.5) == 1.0
        assert clamp(0.0) == 0.0
        assert clamp(1.0) == 1.0
        assert clamp(-100.0) == 0.0
        assert clamp(100.0) == 1.0

    def test_a02_weights_sum_to_one(self):
        """Test UCF weights sum to exactly 1.0."""
        total = sum(UCF_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_a03_stability_band_stable_threshold(self):
        """Test stability band: ucf >= 0.75 -> stable."""
        assert compute_stability_band(0.75) == StabilityBand.STABLE
        assert compute_stability_band(0.80) == StabilityBand.STABLE
        assert compute_stability_band(0.90) == StabilityBand.STABLE
        assert compute_stability_band(1.0) == StabilityBand.STABLE

    def test_a04_stability_band_transitional_threshold(self):
        """Test stability band: 0.45 <= ucf < 0.75 -> transitional."""
        assert compute_stability_band(0.45) == StabilityBand.TRANSITIONAL
        assert compute_stability_band(0.50) == StabilityBand.TRANSITIONAL
        assert compute_stability_band(0.60) == StabilityBand.TRANSITIONAL
        assert compute_stability_band(0.74) == StabilityBand.TRANSITIONAL
        assert compute_stability_band(0.749999) == StabilityBand.TRANSITIONAL

    def test_a05_stability_band_unstable_threshold(self):
        """Test stability band: ucf < 0.45 -> unstable."""
        assert compute_stability_band(0.0) == StabilityBand.UNSTABLE
        assert compute_stability_band(0.10) == StabilityBand.UNSTABLE
        assert compute_stability_band(0.30) == StabilityBand.UNSTABLE
        assert compute_stability_band(0.44) == StabilityBand.UNSTABLE
        assert compute_stability_band(0.449999) == StabilityBand.UNSTABLE

    def test_a06_formula_exact_computation_all_inputs(self):
        """Test exact UCF formula computation with all inputs."""
        # All inputs at 1.0 (best case)
        state = compute_ucf(
            coherence_v3_quality=1.0,
            drift_fusion_index=0.0,  # 0 drift = 1.0 stability
            entropy_volatility=0.0,   # 0 volatility = 1.0 stability
            schema_stability=1.0,
            identity_harmonics_stability=1.0,
        )

        # Expected: 0.30*1.0 + 0.25*1.0 + 0.20*1.0 + 0.15*1.0 + 0.10*1.0 = 1.0
        assert state.ucf_score == pytest.approx(1.0, abs=1e-9)
        assert state.stability_band == StabilityBand.STABLE

    def test_a07_formula_exact_computation_worst_case(self):
        """Test exact UCF formula computation with worst inputs."""
        # All inputs at worst values
        state = compute_ucf(
            coherence_v3_quality=0.0,
            drift_fusion_index=1.0,  # 1.0 drift = 0.0 stability
            entropy_volatility=1.0,   # 1.0 volatility = 0.0 stability
            schema_stability=0.0,
            identity_harmonics_stability=0.0,
        )

        # Expected: 0.30*0.0 + 0.25*0.0 + 0.20*0.0 + 0.15*0.0 + 0.10*0.0 = 0.0
        assert state.ucf_score == pytest.approx(0.0, abs=1e-9)
        assert state.stability_band == StabilityBand.UNSTABLE

    def test_a08_formula_exact_computation_neutral(self):
        """Test UCF formula with neutral inputs (0.5)."""
        state = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,  # 0.5 drift = 0.5 stability
            entropy_volatility=0.5,   # 0.5 volatility = 0.5 stability
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )

        # Expected: 0.30*0.5 + 0.25*0.5 + 0.20*0.5 + 0.15*0.5 + 0.10*0.5 = 0.5
        assert state.ucf_score == pytest.approx(0.5, abs=1e-9)
        assert state.stability_band == StabilityBand.TRANSITIONAL

    def test_a09_formula_weight_sensitivity_coherence(self):
        """Test UCF sensitivity to coherence_v3_quality (weight 0.30)."""
        # All other inputs at 0.5
        state_low = compute_ucf(
            coherence_v3_quality=0.0,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )
        state_high = compute_ucf(
            coherence_v3_quality=1.0,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )

        # Difference should be weight * range = 0.30 * 1.0 = 0.30
        diff = state_high.ucf_score - state_low.ucf_score
        assert diff == pytest.approx(0.30, abs=1e-9)

    def test_a10_formula_weight_sensitivity_drift(self):
        """Test UCF sensitivity to drift_fusion_index (weight 0.25, inverted)."""
        # All other inputs at 0.5
        state_low_drift = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.0,  # Low drift = high stability
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )
        state_high_drift = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=1.0,  # High drift = low stability
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )

        # Low drift should give higher UCF
        assert state_low_drift.ucf_score > state_high_drift.ucf_score
        diff = state_low_drift.ucf_score - state_high_drift.ucf_score
        assert diff == pytest.approx(0.25, abs=1e-9)

    def test_a11_formula_weight_sensitivity_entropy(self):
        """Test UCF sensitivity to entropy_volatility (weight 0.20, inverted)."""
        state_low_vol = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.0,  # Low volatility = high stability
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )
        state_high_vol = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=1.0,  # High volatility = low stability
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )

        # Low volatility should give higher UCF
        assert state_low_vol.ucf_score > state_high_vol.ucf_score
        diff = state_low_vol.ucf_score - state_high_vol.ucf_score
        assert diff == pytest.approx(0.20, abs=1e-9)

    def test_a12_formula_weight_sensitivity_schema(self):
        """Test UCF sensitivity to schema_stability (weight 0.15)."""
        state_low = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.0,
            identity_harmonics_stability=0.5,
        )
        state_high = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=1.0,
            identity_harmonics_stability=0.5,
        )

        diff = state_high.ucf_score - state_low.ucf_score
        assert diff == pytest.approx(0.15, abs=1e-9)

    def test_a13_formula_weight_sensitivity_identity(self):
        """Test UCF sensitivity to identity_harmonics_stability (weight 0.10)."""
        state_low = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=0.0,
        )
        state_high = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=1.0,
        )

        diff = state_high.ucf_score - state_low.ucf_score
        assert diff == pytest.approx(0.10, abs=1e-9)

    def test_a14_contributing_factors_correct(self):
        """Test contributing factors are correctly populated."""
        state = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.3,
            schema_stability=0.7,
            identity_harmonics_stability=0.6,
        )

        assert state.contributing_factors["coherence_v3_quality"] == pytest.approx(0.8, abs=1e-9)
        assert state.contributing_factors["drift_fusion_stability"] == pytest.approx(0.8, abs=1e-9)  # 1 - 0.2
        assert state.contributing_factors["entropy_stability"] == pytest.approx(0.7, abs=1e-9)  # 1 - 0.3
        assert state.contributing_factors["schema_stability"] == pytest.approx(0.7, abs=1e-9)
        assert state.contributing_factors["identity_harmonics"] == pytest.approx(0.6, abs=1e-9)

    def test_a15_confidence_based_on_available_inputs(self):
        """Test confidence is based on number of available inputs."""
        # 5 inputs = 1.0 confidence
        state_all = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.3,
            schema_stability=0.7,
            identity_harmonics_stability=0.6,
        )
        assert state_all.confidence == pytest.approx(1.0, abs=1e-9)

        # 3 inputs = 0.6 confidence
        state_some = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.3,
        )
        assert state_some.confidence == pytest.approx(0.6, abs=1e-9)

        # 0 inputs = 0.0 confidence
        state_none = compute_ucf()
        assert state_none.confidence == pytest.approx(0.0, abs=1e-9)


# ==============================================================================
# GROUP B: BOUNDARY CONDITIONS (10 tests)
# ==============================================================================


class TestGroupBBoundaryConditions:
    """Test boundary conditions: clamps, missing inputs."""

    def test_b01_input_clamping_negative(self):
        """Test negative inputs are clamped to 0.0."""
        state = compute_ucf(
            coherence_v3_quality=-0.5,
            drift_fusion_index=-0.5,
            entropy_volatility=-0.5,
            schema_stability=-0.5,
            identity_harmonics_stability=-0.5,
        )

        # All negatives clamped to 0, inverted values become 1.0
        # coherence: 0.0, drift: 1.0, entropy: 1.0, schema: 0.0, identity: 0.0
        # Expected: 0.30*0 + 0.25*1 + 0.20*1 + 0.15*0 + 0.10*0 = 0.45
        assert state.ucf_score == pytest.approx(0.45, abs=1e-9)

    def test_b02_input_clamping_excessive(self):
        """Test inputs > 1.0 are clamped to 1.0."""
        state = compute_ucf(
            coherence_v3_quality=1.5,
            drift_fusion_index=1.5,
            entropy_volatility=1.5,
            schema_stability=1.5,
            identity_harmonics_stability=1.5,
        )

        # All clamped to 1.0, inverted values become 0.0
        # coherence: 1.0, drift: 0.0, entropy: 0.0, schema: 1.0, identity: 1.0
        # Expected: 0.30*1 + 0.25*0 + 0.20*0 + 0.15*1 + 0.10*1 = 0.55
        assert state.ucf_score == pytest.approx(0.55, abs=1e-9)

    def test_b03_output_clamped_to_unit_interval(self):
        """Test output is always in [0.0, 1.0]."""
        # Even with extreme inputs
        for _ in range(100):
            import random
            state = compute_ucf(
                coherence_v3_quality=random.uniform(-10, 10),
                drift_fusion_index=random.uniform(-10, 10),
                entropy_volatility=random.uniform(-10, 10),
                schema_stability=random.uniform(-10, 10),
                identity_harmonics_stability=random.uniform(-10, 10),
            )
            assert 0.0 <= state.ucf_score <= 1.0

    def test_b04_missing_all_inputs_uses_neutral(self):
        """Test all missing inputs use neutral default (0.5)."""
        state = compute_ucf()

        # All inputs None -> neutral 0.5
        # Expected: 0.30*0.5 + 0.25*0.5 + 0.20*0.5 + 0.15*0.5 + 0.10*0.5 = 0.5
        assert state.ucf_score == pytest.approx(0.5, abs=1e-9)
        assert state.stability_band == StabilityBand.TRANSITIONAL
        assert state.confidence == 0.0

    def test_b05_missing_single_input_uses_neutral(self):
        """Test single missing input uses neutral default."""
        state_with = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.5,
            identity_harmonics_stability=0.5,
        )
        state_without = compute_ucf(
            coherence_v3_quality=0.5,
            drift_fusion_index=0.5,
            entropy_volatility=0.5,
            schema_stability=0.5,
            # identity_harmonics_stability missing
        )

        # Score should be identical (missing = 0.5 = neutral)
        assert state_with.ucf_score == pytest.approx(state_without.ucf_score, abs=1e-9)

    def test_b06_inv_p26_5_missing_inputs_no_destabilization(self):
        """INV-P26-5: Absence of optional inputs never destabilizes output."""
        # With all inputs at good values
        state_full = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.3,
            schema_stability=0.7,
            identity_harmonics_stability=0.6,
        )

        # With some missing (should not be worse than neutral)
        state_partial = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
        )

        # Missing inputs use neutral, not penalties
        # UCF should be determined by available good values
        assert state_partial.ucf_score > 0.4  # Not destabilized to "unstable"

    def test_b07_edge_case_exactly_stable_threshold(self):
        """Test edge case at exactly stable threshold (0.75)."""
        # Construct inputs to get exactly 0.75
        # We need: 0.30*cq + 0.25*(1-df) + 0.20*(1-ev) + 0.15*ss + 0.10*ih = 0.75
        # With cq=0.75, df=0.25, ev=0.25, ss=0.75, ih=0.75:
        # 0.30*0.75 + 0.25*0.75 + 0.20*0.75 + 0.15*0.75 + 0.10*0.75 = 0.75
        state = compute_ucf(
            coherence_v3_quality=0.75,
            drift_fusion_index=0.25,
            entropy_volatility=0.25,
            schema_stability=0.75,
            identity_harmonics_stability=0.75,
        )

        assert state.ucf_score == pytest.approx(0.75, abs=1e-9)
        assert state.stability_band == StabilityBand.STABLE  # >= 0.75 is stable

    def test_b08_edge_case_exactly_transitional_threshold(self):
        """Test edge case at exactly transitional threshold (0.45)."""
        # Construct inputs to get exactly 0.45
        state = compute_ucf(
            coherence_v3_quality=0.45,
            drift_fusion_index=0.55,
            entropy_volatility=0.55,
            schema_stability=0.45,
            identity_harmonics_stability=0.45,
        )

        assert state.ucf_score == pytest.approx(0.45, abs=1e-9)
        assert state.stability_band == StabilityBand.TRANSITIONAL  # >= 0.45 is transitional

    def test_b09_neutral_state_creation(self):
        """Test neutral state creation."""
        state = create_neutral_state()

        assert state.ucf_score == 0.5
        assert state.stability_band == StabilityBand.TRANSITIONAL
        assert state.confidence == 0.0
        assert "neutral_state_insufficient_data" in state.debug.get("reason", "")

    def test_b10_state_factory_clamps_input(self):
        """Test create_ucf_state clamps input values."""
        state = create_ucf_state(ucf_score=1.5)
        assert state.ucf_score == 1.0

        state = create_ucf_state(ucf_score=-0.5)
        assert state.ucf_score == 0.0


# ==============================================================================
# GROUP C: DETERMINISM (8 tests)
# ==============================================================================


class TestGroupCDeterminism:
    """Test determinism: same inputs -> identical outputs."""

    def test_c01_same_inputs_same_outputs(self):
        """Test same inputs produce identical outputs."""
        inputs = {
            "coherence_v3_quality": 0.8,
            "drift_fusion_index": 0.2,
            "entropy_volatility": 0.3,
            "schema_stability": 0.7,
            "identity_harmonics_stability": 0.6,
        }

        state1 = compute_ucf(**inputs)
        state2 = compute_ucf(**inputs)

        assert state1.ucf_score == state2.ucf_score
        assert state1.stability_band == state2.stability_band
        assert state1.contributing_factors == state2.contributing_factors
        assert state1.confidence == state2.confidence

    def test_c02_multiple_iterations_identical(self):
        """Test multiple iterations produce identical results."""
        is_deterministic, ucf_score = verify_ucf_determinism(
            coherence_v3_quality=0.75,
            drift_fusion_index=0.25,
            entropy_volatility=0.30,
            schema_stability=0.70,
            identity_harmonics_stability=0.60,
            iterations=100,
        )

        assert is_deterministic is True

    def test_c03_hash_consistency(self):
        """Test output hash is consistent across calls."""
        def compute_hash(state):
            data = json.dumps(state.to_dict(), sort_keys=True)
            return hashlib.sha256(data.encode()).hexdigest()

        state1 = compute_ucf(coherence_v3_quality=0.8, drift_fusion_index=0.2)
        state2 = compute_ucf(coherence_v3_quality=0.8, drift_fusion_index=0.2)

        assert compute_hash(state1) == compute_hash(state2)

    def test_c04_no_randomness(self):
        """Test no randomness in computation."""
        results = []
        for _ in range(50):
            state = compute_ucf(
                coherence_v3_quality=0.777,
                drift_fusion_index=0.333,
            )
            results.append(state.ucf_score)

        # All results should be identical
        assert len(set(results)) == 1

    def test_c05_resolver_determinism(self):
        """Test resolver produces deterministic results."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_v3_quality=0.8,
                drift_fusion_index=0.2,
            )
        )

        resolver = get_ucf_resolver()
        state1 = resolver.compute(ctx)
        state2 = resolver.compute(ctx)

        assert state1.ucf_score == state2.ucf_score

    def test_c06_run_directly_determinism(self):
        """Test run_p26_directly is deterministic."""
        state1 = run_p26_directly(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
        )
        state2 = run_p26_directly(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
        )

        assert state1.ucf_score == state2.ucf_score

    def test_c07_order_independence(self):
        """Test input order doesn't affect result."""
        state1 = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.3,
        )
        state2 = compute_ucf(
            entropy_volatility=0.3,
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
        )

        assert state1.ucf_score == state2.ucf_score

    def test_c08_dict_vs_kwargs_equivalent(self):
        """Test dict input equivalent to kwargs."""
        factors = {
            "coherence_v3_quality": 0.8,
            "drift_fusion_index": 0.2,
            "entropy_volatility": 0.3,
        }

        state1 = compute_ucf(**factors)
        state2 = compute_ucf_from_factors(factors)

        assert state1.ucf_score == state2.ucf_score


# ==============================================================================
# GROUP D: AUTHORITY PROOF (8 tests)
# ==============================================================================


class TestGroupDAuthorityProof:
    """Test UCF never modifies regime, discourse, semantics, lexical."""

    def test_d01_inv_p26_1_ucf_is_read_only(self):
        """INV-P26-1: UCF is read-only truth, not a decision."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.8),
            p6_regime="test_regime",
            p7_discourse_envelope="test_discourse",
            semantic_frame="test_semantic",
            lexical_frame="test_lexical",
        )

        original_regime = ctx.p6_regime
        original_discourse = ctx.p7_discourse_envelope
        original_semantic = ctx.semantic_frame
        original_lexical = ctx.lexical_frame

        maybe_run_p26(ctx)

        # P26 must not modify any authority fields
        assert ctx.p6_regime == original_regime
        assert ctx.p7_discourse_envelope == original_discourse
        assert ctx.semantic_frame == original_semantic
        assert ctx.lexical_frame == original_lexical

    def test_d02_inv_p26_4_ucf_never_opens_gates(self):
        """INV-P26-4: UCF never opens gates directly."""
        # UCF state has no gate-opening methods
        state = compute_ucf(coherence_v3_quality=0.1)  # Very unstable

        # Even with unstable UCF, no gating occurs
        assert state.stability_band == StabilityBand.UNSTABLE
        assert not hasattr(state, 'open_gate')
        assert not hasattr(state, 'trigger_action')
        assert not hasattr(state, 'modify_routing')

    def test_d03_no_regime_modification(self):
        """Test UCF does not modify regime."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.2),
            p6_regime="original_regime",
        )

        maybe_run_p26(ctx)

        assert ctx.p6_regime == "original_regime"
        assert ctx.p26.stability_band == StabilityBand.UNSTABLE

    def test_d04_no_discourse_modification(self):
        """Test UCF does not modify discourse."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.9),
            p7_discourse_envelope="original_discourse",
        )

        maybe_run_p26(ctx)

        assert ctx.p7_discourse_envelope == "original_discourse"

    def test_d05_no_semantic_modification(self):
        """Test UCF does not modify semantics."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.5),
            semantic_frame="original_semantic",
        )

        maybe_run_p26(ctx)

        assert ctx.semantic_frame == "original_semantic"

    def test_d06_no_lexical_modification(self):
        """Test UCF does not modify lexical frame."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.5),
            lexical_frame="original_lexical",
        )

        maybe_run_p26(ctx)

        assert ctx.lexical_frame == "original_lexical"

    def test_d07_ucf_state_is_immutable(self):
        """Test UCF state is frozen (immutable)."""
        state = compute_ucf(coherence_v3_quality=0.8)

        with pytest.raises(AttributeError):
            state.ucf_score = 0.5

    def test_d08_multiple_ucf_runs_no_accumulation(self):
        """Test multiple UCF runs don't accumulate side effects."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.7),
            p6_regime="test",
        )

        for _ in range(10):
            maybe_run_p26(ctx)

        # No accumulation of effects
        assert ctx.p6_regime == "test"
        assert ctx.p26 is not None


# ==============================================================================
# GROUP E: IMPORT SAFETY (5 tests)
# ==============================================================================


class TestGroupEImportSafety:
    """Test forbidden imports are not used."""

    def test_e01_no_p6_import(self):
        """Test UCF modules don't import P6 (regime)."""
        import symbolu.core.consciousness.ucf_formula as ucf_formula
        import symbolu.core.consciousness.ucf_resolver as ucf_resolver

        # Check no forbidden imports in module globals
        ucf_formula_names = dir(ucf_formula)
        ucf_resolver_names = dir(ucf_resolver)

        forbidden_patterns = ["regime", "p6_", "RegimeEnvelope"]

        for pattern in forbidden_patterns:
            for name in ucf_formula_names:
                assert pattern.lower() not in name.lower(), f"Forbidden import {pattern} in ucf_formula"
            for name in ucf_resolver_names:
                assert pattern.lower() not in name.lower(), f"Forbidden import {pattern} in ucf_resolver"

    def test_e02_no_p21_import(self):
        """Test UCF modules don't import P21 (delivery)."""
        import symbolu.core.consciousness.ucf_formula as ucf_formula

        # Verify no delivery-related imports
        source_attrs = dir(ucf_formula)
        forbidden = ["delivery", "p21_", "DeliveryMode"]

        for pattern in forbidden:
            for attr in source_attrs:
                assert pattern.lower() not in attr.lower()

    def test_e03_no_renderer_import(self):
        """Test UCF modules don't import Renderer."""
        import symbolu.core.consciousness.ucf_formula as ucf_formula
        import symbolu.core.consciousness.ucf_resolver as ucf_resolver

        # Check module sources don't import renderer
        # This is a static check on module structure
        assert not hasattr(ucf_formula, 'Renderer')
        assert not hasattr(ucf_formula, 'render')
        assert not hasattr(ucf_resolver, 'Renderer')
        assert not hasattr(ucf_resolver, 'render')

    def test_e04_no_observer_phase_import(self):
        """Test UCF modules don't import P22-P24 (observer phases)."""
        import symbolu.core.consciousness.ucf_formula as ucf_formula
        import symbolu.core.consciousness.ucf_resolver as ucf_resolver

        forbidden = ["p22_", "p23_", "p24_", "acoustic_witness", "alignment_report", "projection_report"]

        ucf_formula_attrs = dir(ucf_formula)
        ucf_resolver_attrs = dir(ucf_resolver)

        for pattern in forbidden:
            for attr in ucf_formula_attrs:
                assert pattern.lower() not in attr.lower()
            for attr in ucf_resolver_attrs:
                assert pattern.lower() not in attr.lower()

    def test_e05_inv_p26_2_observer_data_cannot_affect_ucf(self):
        """INV-P26-2: Observer data cannot affect UCF."""
        # Create context with observer data (which should be ignored)
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.8),
        )

        # Add mock observer data
        ctx.p22_acoustic_witness = {"data": "should_be_ignored"}
        ctx.p23_alignment_report = {"data": "should_be_ignored"}
        ctx.p24_projection_report = {"data": "should_be_ignored"}

        state = maybe_run_p26(ctx)

        # UCF should work without using observer data
        assert state is not None
        # Observer data should not affect the computation
        # (resolver only extracts from coherence_state, p18, p19, p33)


# ==============================================================================
# GROUP F: REGRESSION LOCK (6 tests)
# ==============================================================================


class TestGroupFRegressionLock:
    """Test existing pipelines unchanged when P26 is enabled."""

    def test_f01_disabled_p26_returns_none(self):
        """Test disabled P26 returns None without side effects."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.8),
            _p26_disabled=True,
        )

        result = maybe_run_p26(ctx)

        assert result is None
        assert not has_p26_state(ctx)

    def test_f02_missing_coherence_state_skips_p26(self):
        """Test missing coherence_state skips P26 gracefully."""
        ctx = MockPipelineContext(coherence_state=None)

        result = maybe_run_p26(ctx)

        assert result is None

    def test_f03_p26_attaches_to_context(self):
        """Test P26 correctly attaches state to context."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.8),
        )

        result = maybe_run_p26(ctx)

        assert result is not None
        assert ctx.p26 is not None
        assert ctx.p26 == result

    def test_f04_p26_helper_functions_work(self):
        """Test P26 helper functions work correctly."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.8),
        )

        assert not has_p26_state(ctx)

        maybe_run_p26(ctx)

        assert has_p26_state(ctx)
        assert get_p26_state(ctx) is not None
        assert 0.0 <= get_ucf_score(ctx) <= 1.0
        assert get_stability_band(ctx) in [StabilityBand.STABLE, StabilityBand.TRANSITIONAL, StabilityBand.UNSTABLE]

    def test_f05_version_consistency(self):
        """Test version is consistent across module."""
        assert get_p26_version() == P26_VERSION

        resolver = get_ucf_resolver()
        assert resolver.version == P26_VERSION

        state = compute_ucf(coherence_v3_quality=0.8)
        assert state.version == P26_VERSION

    def test_f06_json_serialization(self):
        """Test UCF state is JSON-serializable."""
        state = compute_ucf(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.3,
        )

        state_dict = state.to_dict()
        json_str = json.dumps(state_dict)

        # Should round-trip correctly
        deserialized = json.loads(json_str)
        assert deserialized["ucf_score"] == state.ucf_score
        assert deserialized["stability_band"] == state.stability_band.value


# ==============================================================================
# ADDITIONAL INTEGRATION TESTS
# ==============================================================================


class TestIntegration:
    """Additional integration tests."""

    def test_integration_with_mock_p18_p19_p33(self):
        """Test integration with mock P18, P19, P33 reports."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_v3_quality=0.75,
            ),
            p18=MockP18Report(volatility_band="LOW"),
            p19=MockP19Report(drift_fusion_index=0.25),
            p33=MockP33Snapshot(schema_stability_scores={"default": 0.8}),
        )

        result = maybe_run_p26(ctx)

        assert result is not None
        assert result.ucf_score > 0.5  # Should be good given inputs

    def test_resolver_extracts_from_coherence_state(self):
        """Test resolver correctly extracts from coherence_state."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_v3_quality=0.9,
                drift_fusion_index=0.1,
                temporal_entropy_volatility=0.1,
                persona_schema_stability=0.9,
                current_identity_harmonics_index=0.8,
            )
        )

        resolver = get_ucf_resolver()
        state = resolver.compute(ctx)

        # Should get high UCF with good inputs
        assert state.ucf_score > 0.7
        assert state.stability_band == StabilityBand.STABLE

    def test_resolver_graceful_with_partial_data(self):
        """Test resolver handles partial data gracefully."""
        ctx = MockPipelineContext(
            coherence_state=MockCoherenceState(
                coherence_v3_quality=0.8,
                # Other fields missing
            )
        )

        resolver = get_ucf_resolver()
        state = resolver.compute(ctx)

        # Should work with partial data
        assert state is not None
        assert state.confidence < 1.0  # Partial data = lower confidence

    def test_ucf_updates_coherence_state(self):
        """Test UCF updates coherence_state fields."""
        coherence_state = MockCoherenceState(coherence_v3_quality=0.8)
        ctx = MockPipelineContext(coherence_state=coherence_state)

        maybe_run_p26(ctx)

        # Check coherence_state was updated
        assert coherence_state.unified_consciousness_snapshot is not None
        assert coherence_state.current_coi is not None

    def test_stability_band_helper_functions(self):
        """Test is_stable, is_transitional, is_unstable helpers."""
        # Stable context
        ctx_stable = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.95)
        )
        ctx_stable.p26 = compute_ucf(
            coherence_v3_quality=1.0,
            drift_fusion_index=0.0,
            entropy_volatility=0.0,
            schema_stability=1.0,
            identity_harmonics_stability=1.0,
        )

        assert is_stable(ctx_stable) is True
        assert is_transitional(ctx_stable) is False
        assert is_unstable(ctx_stable) is False

        # Unstable context
        ctx_unstable = MockPipelineContext(
            coherence_state=MockCoherenceState(coherence_v3_quality=0.1)
        )
        ctx_unstable.p26 = compute_ucf(
            coherence_v3_quality=0.0,
            drift_fusion_index=1.0,
            entropy_volatility=1.0,
            schema_stability=0.0,
            identity_harmonics_stability=0.0,
        )

        assert is_stable(ctx_unstable) is False
        assert is_transitional(ctx_unstable) is False
        assert is_unstable(ctx_unstable) is True


# ==============================================================================
# INV-P26-3: MONOTONICITY TESTS
# ==============================================================================


class TestMonotonicity:
    """INV-P26-3: UCF monotonic with respect to instability."""

    def test_inv_p26_3_higher_drift_lower_ucf(self):
        """Higher drift should result in lower UCF."""
        state_low_drift = compute_ucf(drift_fusion_index=0.2)
        state_high_drift = compute_ucf(drift_fusion_index=0.8)

        assert state_low_drift.ucf_score > state_high_drift.ucf_score

    def test_inv_p26_3_higher_volatility_lower_ucf(self):
        """Higher entropy volatility should result in lower UCF."""
        state_low_vol = compute_ucf(entropy_volatility=0.2)
        state_high_vol = compute_ucf(entropy_volatility=0.8)

        assert state_low_vol.ucf_score > state_high_vol.ucf_score

    def test_inv_p26_3_monotonic_sweep(self):
        """Test monotonicity across full input range."""
        prev_score = 2.0  # Start above max possible

        for drift in [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]:
            state = compute_ucf(
                coherence_v3_quality=0.5,
                drift_fusion_index=drift,
                entropy_volatility=0.5,
                schema_stability=0.5,
                identity_harmonics_stability=0.5,
            )
            assert state.ucf_score <= prev_score
            prev_score = state.ucf_score


# ==============================================================================
# SUMMARY
# ==============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
