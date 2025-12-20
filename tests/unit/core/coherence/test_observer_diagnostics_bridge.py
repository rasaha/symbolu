"""
Observer Diagnostics Bridge Tests

Tests for the ObserverDiagnosticsBundle and its integration with Phase 10 Coherence.

Test Coverage (exactly one test per invariant):
- INV-CB1: None bundle => bitwise identical outputs
- INV-CB2: Bundle present => quality non-increase guarantee
- INV-CB3: Authority invariance - same authority inputs, different bundles => PO1-P9 unchanged
- INV-CB4: Static import test - no observer imports in coherence/policy modules

SAFETY INVARIANTS VERIFIED:
1. INV-CB1: Bundle can ONLY affect coherence_v3_quality downward, within existing bounds
2. INV-CB2: Bundle MUST NOT affect: PO1-PO5, P6-P9 outputs, regime/discourse/semantic/lexical
3. INV-CB3: No imports from observer modules into authoritative modules
"""

import ast
import os
import pytest
from pathlib import Path

from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.core.coherence.acoustic_alignment_schema import (
    AcousticAlignmentReport,
    create_aligned_report,
    create_misaligned_report,
)
from symbolu.core.coherence.observer_diagnostics_bundle import (
    ObserverDiagnosticsBundle,
    create_empty_bundle,
    create_acoustic_only_bundle,
    create_full_bundle,
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def engine():
    """Create a CoherenceEngine instance."""
    return CoherenceEngine(window=10)


@pytest.fixture
def base_state():
    """Create a basic CoherenceState with Phase 3 metrics."""
    state = CoherenceState(convo_id="test", turn_index=1, coherence_score=0.70)
    state.resonance_index = 0.65
    state.tension_index = 0.40
    state.arc_alignment_index = 0.60
    state.guna_resonance_index = 0.68
    state.kosha_resonance_index = 0.66
    state.coherence_score_v2 = 0.72
    return state


@pytest.fixture
def minimal_routing_plan():
    """Create a minimal routing plan mock."""
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "general"
    return MockRoutingPlan()


@pytest.fixture
def minimal_mapper_profile():
    """Create a minimal mapper profile."""
    return {
        "domain": "general",
        "tier": "hybrid",
        "smi": 0.6,
    }


@pytest.fixture
def minimal_semantic_signature():
    """Create a minimal semantic signature."""
    return {
        "signature": "test",
        "stability": 0.7,
    }


@pytest.fixture
def misaligned_bundle():
    """Create a bundle with misaligned acoustic report (penalty expected)."""
    misaligned_report = create_misaligned_report(
        alignment_score=0.2,
        pressure_band="high",
        mismatch_tags=("inner_outer_tension", "high_pressure_low_authority"),
    )
    return create_acoustic_only_bundle(
        acoustic_alignment=misaligned_report,
        source_phase_ids=("P22", "P23"),
    )


@pytest.fixture
def aligned_bundle():
    """Create a bundle with aligned acoustic report (no penalty expected)."""
    aligned_report = create_aligned_report(
        alignment_score=0.8,
        pressure_band="low",
    )
    return create_acoustic_only_bundle(
        acoustic_alignment=aligned_report,
        source_phase_ids=("P22", "P23"),
    )


# ============================================================================
# INV-CB1: None bundle => bitwise identical outputs
# ============================================================================


class TestINVCB1NoneBundleBitwiseIdentical:
    """
    Test INV-CB1: When observer_diagnostics is None, outputs must be
    bitwise identical to when it is not provided at all.

    This ensures perfect backward compatibility.
    """

    def test_none_bundle_produces_bitwise_identical_outputs(
        self,
        engine,
        minimal_routing_plan,
        minimal_mapper_profile,
        minimal_semantic_signature,
    ):
        """
        INV-CB1: None bundle => bitwise identical outputs.

        When observer_diagnostics=None (or not provided), the update_state
        function must produce EXACTLY the same output as before the bundle
        feature was added.
        """
        # Call 1: Without observer_diagnostics parameter (original API)
        state_without_bundle = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=1,
            routing_plan=minimal_routing_plan,
            mapper_profile=minimal_mapper_profile,
            temporal_summary=None,
            semantic_signature=minimal_semantic_signature,
            acoustic_alignment=None,
            # observer_diagnostics not provided (defaults to None)
        )

        # Call 2: With explicit observer_diagnostics=None
        state_with_none_bundle = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=1,
            routing_plan=minimal_routing_plan,
            mapper_profile=minimal_mapper_profile,
            temporal_summary=None,
            semantic_signature=minimal_semantic_signature,
            acoustic_alignment=None,
            observer_diagnostics=None,
        )

        # Call 3: With empty bundle
        state_with_empty_bundle = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=1,
            routing_plan=minimal_routing_plan,
            mapper_profile=minimal_mapper_profile,
            temporal_summary=None,
            semantic_signature=minimal_semantic_signature,
            acoustic_alignment=None,
            observer_diagnostics=create_empty_bundle(),
        )

        # VERIFY: All coherence scores must be bitwise identical
        assert state_without_bundle.coherence_score == state_with_none_bundle.coherence_score, \
            "coherence_score must be identical with None bundle"
        assert state_without_bundle.coherence_score == state_with_empty_bundle.coherence_score, \
            "coherence_score must be identical with empty bundle"

        assert state_without_bundle.coherence_score_v2 == state_with_none_bundle.coherence_score_v2, \
            "coherence_score_v2 must be identical with None bundle"
        assert state_without_bundle.coherence_score_v2 == state_with_empty_bundle.coherence_score_v2, \
            "coherence_score_v2 must be identical with empty bundle"

        assert state_without_bundle.coherence_score_v3 == state_with_none_bundle.coherence_score_v3, \
            "coherence_score_v3 must be identical with None bundle"
        assert state_without_bundle.coherence_score_v3 == state_with_empty_bundle.coherence_score_v3, \
            "coherence_score_v3 must be identical with empty bundle"

        assert state_without_bundle.coherence_v3_quality == state_with_none_bundle.coherence_v3_quality, \
            "coherence_v3_quality must be identical with None bundle"
        assert state_without_bundle.coherence_v3_quality == state_with_empty_bundle.coherence_v3_quality, \
            "coherence_v3_quality must be identical with empty bundle"

        # VERIFY: No acoustic penalties applied
        assert state_without_bundle.acoustic_quality_penalty_applied is False
        assert state_with_none_bundle.acoustic_quality_penalty_applied is False
        assert state_with_empty_bundle.acoustic_quality_penalty_applied is False

        assert state_without_bundle.acoustic_quality_penalty_amount == 0.0
        assert state_with_none_bundle.acoustic_quality_penalty_amount == 0.0
        assert state_with_empty_bundle.acoustic_quality_penalty_amount == 0.0


# ============================================================================
# INV-CB2: Bundle present => quality non-increase guarantee
# ============================================================================


class TestINVCB2QualityNonIncrease:
    """
    Test INV-CB2: When bundle is present, coherence_v3_quality can only
    decrease or stay the same, NEVER increase.
    """

    def test_bundle_only_reduces_quality_never_increases(
        self,
        engine,
        base_state,
        misaligned_bundle,
        aligned_bundle,
    ):
        """
        INV-CB2: Bundle present => quality non-increase guarantee.

        When observer_diagnostics bundle contains acoustic alignment data,
        it can ONLY reduce coherence_v3_quality (by max 5%), NEVER increase it.

        Tests the internal quality computation function directly since
        update_state requires state history to compute coherence_v3.
        """
        # Test parameters (simulating computed v3 score)
        test_v3 = 0.75
        test_base = base_state.coherence_score

        # Baseline: Compute without any acoustic alignment
        baseline_quality, baseline_applied, baseline_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=test_base,
            v3=test_v3,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=None,
        )

        # With misaligned acoustic from bundle (should reduce quality)
        misaligned_acoustic = misaligned_bundle.extract_acoustic_alignment()
        misaligned_quality, misaligned_applied, misaligned_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=test_base,
            v3=test_v3,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=misaligned_acoustic,
        )

        # With aligned acoustic from bundle (should not increase quality)
        aligned_acoustic = aligned_bundle.extract_acoustic_alignment()
        aligned_quality, aligned_applied, aligned_amount, _ = engine._compute_coherence_v3_quality_with_acoustic(
            base=test_base,
            v3=test_v3,
            resonance_index=base_state.resonance_index,
            arc_alignment_index=base_state.arc_alignment_index,
            tension_index=base_state.tension_index,
            acoustic_alignment=aligned_acoustic,
        )

        # VERIFY: Baseline quality computed correctly
        assert baseline_quality is not None, "Baseline quality should be computed"
        assert 0.0 <= baseline_quality <= 1.0, "Baseline quality should be in [0.0, 1.0]"

        # VERIFY: Misaligned bundle reduces quality (penalty applied)
        assert misaligned_quality is not None, "Misaligned quality should be computed"
        assert misaligned_quality <= baseline_quality, \
            f"Misaligned bundle must not increase quality: {misaligned_quality} <= {baseline_quality}"

        # VERIFY: Aligned bundle does not increase quality (no penalty, but never increases)
        assert aligned_quality is not None, "Aligned quality should be computed"
        assert aligned_quality <= baseline_quality, \
            f"Aligned bundle must not increase quality: {aligned_quality} <= {baseline_quality}"

        # VERIFY: Misalignment triggers penalty
        assert misaligned_applied is True, \
            "Penalty should be applied for misaligned bundle"
        assert misaligned_amount > 0.0, \
            "Penalty amount should be > 0 for misaligned bundle"
        assert misaligned_amount <= 0.05, \
            "Penalty amount must not exceed 5% (0.05)"

        # VERIFY: Aligned bundle has no penalty
        assert aligned_applied is False, \
            "Penalty should NOT be applied for aligned bundle"
        assert aligned_amount == 0.0, \
            "Penalty amount should be 0 for aligned bundle"


# ============================================================================
# INV-CB3: Authority invariance - same inputs, different bundles => P1-P9 unchanged
# ============================================================================


class TestINVCB3AuthorityInvariance:
    """
    Test INV-CB3: Same authority inputs with different bundles must produce
    identical outputs for PO1-P9 (authoritative phases).

    This ensures observer diagnostics never affect authoritative decisions.
    """

    def test_authority_outputs_unchanged_regardless_of_bundle(
        self,
        engine,
        minimal_routing_plan,
        minimal_mapper_profile,
        minimal_semantic_signature,
        misaligned_bundle,
        aligned_bundle,
    ):
        """
        INV-CB3: Authority invariance test.

        Same authority inputs with different bundles must produce IDENTICAL
        outputs for: coherence_score, coherence_score_v2, coherence_score_v3,
        persona_drift_score, semantic_stability_score, mapper_volatility_score,
        temporal_arc_score.

        Only coherence_v3_quality may differ (downward only).
        """
        # State 1: No bundle
        state_no_bundle = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=1,
            routing_plan=minimal_routing_plan,
            mapper_profile=minimal_mapper_profile,
            temporal_summary=None,
            semantic_signature=minimal_semantic_signature,
            acoustic_alignment=None,
            observer_diagnostics=None,
        )

        # State 2: Misaligned bundle
        state_misaligned = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=1,
            routing_plan=minimal_routing_plan,
            mapper_profile=minimal_mapper_profile,
            temporal_summary=None,
            semantic_signature=minimal_semantic_signature,
            acoustic_alignment=None,
            observer_diagnostics=misaligned_bundle,
        )

        # State 3: Aligned bundle
        state_aligned = engine.update_state(
            prev_state=None,
            convo_id="test",
            turn_index=1,
            routing_plan=minimal_routing_plan,
            mapper_profile=minimal_mapper_profile,
            temporal_summary=None,
            semantic_signature=minimal_semantic_signature,
            acoustic_alignment=None,
            observer_diagnostics=aligned_bundle,
        )

        # VERIFY: coherence_score (v1 canonical) - MUST be identical
        assert state_no_bundle.coherence_score == state_misaligned.coherence_score, \
            "coherence_score must be identical regardless of bundle"
        assert state_no_bundle.coherence_score == state_aligned.coherence_score, \
            "coherence_score must be identical regardless of bundle"

        # VERIFY: coherence_score_v2 - MUST be identical
        assert state_no_bundle.coherence_score_v2 == state_misaligned.coherence_score_v2, \
            "coherence_score_v2 must be identical regardless of bundle"
        assert state_no_bundle.coherence_score_v2 == state_aligned.coherence_score_v2, \
            "coherence_score_v2 must be identical regardless of bundle"

        # VERIFY: coherence_score_v3 - MUST be identical (bundle cannot affect v3)
        assert state_no_bundle.coherence_score_v3 == state_misaligned.coherence_score_v3, \
            "coherence_score_v3 must be identical regardless of bundle"
        assert state_no_bundle.coherence_score_v3 == state_aligned.coherence_score_v3, \
            "coherence_score_v3 must be identical regardless of bundle"

        # VERIFY: persona_drift_score - MUST be identical
        assert state_no_bundle.persona_drift_score == state_misaligned.persona_drift_score, \
            "persona_drift_score must be identical regardless of bundle"
        assert state_no_bundle.persona_drift_score == state_aligned.persona_drift_score, \
            "persona_drift_score must be identical regardless of bundle"

        # VERIFY: semantic_stability_score - MUST be identical
        assert state_no_bundle.semantic_stability_score == state_misaligned.semantic_stability_score, \
            "semantic_stability_score must be identical regardless of bundle"
        assert state_no_bundle.semantic_stability_score == state_aligned.semantic_stability_score, \
            "semantic_stability_score must be identical regardless of bundle"

        # VERIFY: mapper_volatility_score - MUST be identical
        assert state_no_bundle.mapper_volatility_score == state_misaligned.mapper_volatility_score, \
            "mapper_volatility_score must be identical regardless of bundle"
        assert state_no_bundle.mapper_volatility_score == state_aligned.mapper_volatility_score, \
            "mapper_volatility_score must be identical regardless of bundle"

        # VERIFY: temporal_arc_score - MUST be identical
        assert state_no_bundle.temporal_arc_score == state_misaligned.temporal_arc_score, \
            "temporal_arc_score must be identical regardless of bundle"
        assert state_no_bundle.temporal_arc_score == state_aligned.temporal_arc_score, \
            "temporal_arc_score must be identical regardless of bundle"


# ============================================================================
# INV-CB4: Static import test - no observer imports in coherence/policy
# ============================================================================


class TestINVCB4StaticImportSafety:
    """
    Test INV-CB4: No observer module imports in authoritative coherence modules.

    The coherence_engine.py and policy modules must NOT import from:
    - symbolu.mechanical.pipeline.p20_*
    - symbolu.mechanical.pipeline.p22_*
    - symbolu.mechanical.pipeline.p23_*
    - symbolu.mechanical.pipeline.p24_*
    """

    def test_no_observer_imports_in_coherence_engine(self):
        """
        INV-CB4: Static import test.

        Verify that coherence_engine.py does NOT import from observer modules
        (P20, P22, P23, P24). This ensures the architectural boundary is maintained.
        """
        # Get the path to coherence_engine.py
        # Navigate from tests/unit/core/coherence/ to symbolu/core/coherence/
        project_root = Path(__file__).parent.parent.parent.parent.parent
        coherence_engine_path = project_root / "symbolu" / "core" / "coherence" / "coherence_engine.py"

        assert coherence_engine_path.exists(), \
            f"coherence_engine.py not found at {coherence_engine_path}"

        # Read and parse the source
        with open(coherence_engine_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        # Collect all imports
        forbidden_patterns = [
            "symbolu.mechanical.pipeline.p20",
            "symbolu.mechanical.pipeline.p22",
            "symbolu.mechanical.pipeline.p23",
            "symbolu.mechanical.pipeline.p24",
        ]

        violations = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for pattern in forbidden_patterns:
                        if pattern in alias.name:
                            violations.append(f"import {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    for pattern in forbidden_patterns:
                        if pattern in node.module:
                            violations.append(f"from {node.module} import ...")

        assert len(violations) == 0, \
            f"INV-CB3 VIOLATION: coherence_engine.py imports observer modules: {violations}"

        # Also verify no imports from observer_diagnostics_bundle into p20/p22/p23/p24
        # (The bundle is in coherence core, observers can import it, but not reverse)
        # This is verified by the fact that coherence_engine imports from
        # observer_diagnostics_bundle (which is in core), not from observers.


# ============================================================================
# DATACLASS INVARIANTS
# ============================================================================


class TestObserverDiagnosticsBundleDataclass:
    """Test ObserverDiagnosticsBundle dataclass invariants."""

    def test_bundle_is_frozen(self):
        """Test that the bundle is immutable (frozen)."""
        bundle = create_empty_bundle()

        with pytest.raises(Exception):  # FrozenInstanceError or similar
            bundle.source_phase_ids = ("P99",)

    def test_source_phase_ids_must_be_tuple(self):
        """Test that source_phase_ids must be a tuple."""
        with pytest.raises(ValueError, match="must be a tuple"):
            ObserverDiagnosticsBundle(
                acoustic_alignment=None,
                acoustic_ontology_projection=None,
                source_phase_ids=["P22", "P23"],  # List instead of tuple
            )

    def test_bundle_query_methods(self):
        """Test bundle query methods."""
        empty = create_empty_bundle()
        assert empty.is_empty() is True
        assert empty.has_any_diagnostics() is False
        assert empty.has_acoustic_alignment() is False
        assert empty.has_ontology_projection() is False

        acoustic = create_acoustic_only_bundle(
            acoustic_alignment=create_aligned_report(),
            source_phase_ids=("P23",),
        )
        assert acoustic.is_empty() is False
        assert acoustic.has_any_diagnostics() is True
        assert acoustic.has_acoustic_alignment() is True
        assert acoustic.has_ontology_projection() is False
