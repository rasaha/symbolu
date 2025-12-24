"""
Phase-11B Controller Test Suite
================================

Comprehensive tests for the Phase-11B governed structural generator.

Test Categories:
    1. Structural Tests - No silent collapse, distinct inputs → distinct outputs
    2. Stability Tests - Determinism in GOVERNED mode
    3. Ceiling Tests - Differentiation depth and clustering

SUCCESS CRITERIA:
    - Overall differentiation score: ~0.85+ (up from ~0.29 in 11A)
    - Stability: >= 0.95
    - No silent collapse detected
    - Ontological path is strongest clustering axis
    - PPV dimensions produce distinct structural effects
"""

import hashlib
from typing import Dict, List, Set, Tuple

import pytest

from symbolu.mechanical.pipeline.p11_controller.p11_schema import (
    Phase10Result,
    RenderMode,
)
from symbolu.mechanical.pipeline.p11b_controller import (
    # Enums
    OntologicalFamily,
    PPVBand,
    SlotPlan,
    RegistryType,
    # Schema
    PPVBandSignature,
    TemplateKey,
    Phase11BRequest,
    Phase11BResponse,
    # Controller
    Phase11BController,
    run_phase11b_controller,
    create_phase11b_governed_request,
    create_phase11b_open_request,
    # Schema Functions
    get_template_family,
    get_ppv_band,
    create_ppv_band_signature,
    compute_variant_id,
    get_slot_plan_from_ppv,
    create_template_key,
    # Template Functions
    get_registry,
    lookup_template,
    validate_no_silent_collapse,
    validate_registry_completeness,
    get_registry_stats,
    # Controller Functions
    verify_structural_differentiation,
    get_differentiation_axes,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def make_artifact_hash() -> str:
    """Create a valid 64-char hex hash."""
    return hashlib.sha256(b"test_artifact").hexdigest()


def make_phase10_result(
    vc_facts: Tuple[str, ...] = ("VC-1", "VC-2"),
    acoustic_regime: str = "neutral",
    source_data: Dict = None,
) -> Phase10Result:
    """Create a valid Phase10Result for testing."""
    if source_data is None:
        source_data = {
            "vc_1_data": "observation_data",
            "vc_2_data": "state_data",
            "vc_3_data": "context_data",
            "vc_4_data": "reference_data",
            "vc_5_data": "marker_data",
        }
    return Phase10Result(
        artifact_hash=make_artifact_hash(),
        vc_facts=vc_facts,
        acoustic_regime=acoustic_regime,
        source_data=source_data,
    )


def make_request(
    ontological_path: Tuple[str, ...] = ("THINKING", "DIRECTING"),
    ppv_values: Tuple[int, ...] = (3, 3, 3, 3, 3, 3, 3, 3),
    render_mode: RenderMode = RenderMode.GOVERNED,
) -> Phase11BRequest:
    """Create a valid Phase11BRequest for testing."""
    return Phase11BRequest(
        artifact_id="test-artifact",
        artifact_hash=make_artifact_hash(),
        phase10_result=make_phase10_result(),
        ontological_path=ontological_path,
        ppv_values=ppv_values,
        render_mode=render_mode,
    )


# =============================================================================
# PPV Banding Tests
# =============================================================================


class TestPPVBanding:
    """Tests for PPV band system."""

    def test_band_low_values(self):
        """Values 0-2 should map to LOW band."""
        for val in [0, 1, 2]:
            assert get_ppv_band(val) == PPVBand.LOW

    def test_band_mid_values(self):
        """Values 3-5 should map to MID band."""
        for val in [3, 4, 5]:
            assert get_ppv_band(val) == PPVBand.MID

    def test_band_high_values(self):
        """Values 6-7 should map to HIGH band."""
        for val in [6, 7]:
            assert get_ppv_band(val) == PPVBand.HIGH

    def test_band_out_of_range(self):
        """Values outside 0-7 should raise ValueError."""
        with pytest.raises(ValueError):
            get_ppv_band(-1)
        with pytest.raises(ValueError):
            get_ppv_band(8)

    def test_band_signature_creation(self):
        """Band signature should be created from 8 values."""
        values = (0, 3, 6, 1, 4, 7, 2, 5)
        sig = create_ppv_band_signature(values)

        assert sig.edge_tension == PPVBand.LOW      # 0
        assert sig.edge_release == PPVBand.MID     # 3
        assert sig.onset_sharpness == PPVBand.HIGH # 6
        assert sig.sonority_lift == PPVBand.LOW    # 1
        assert sig.continuity == PPVBand.MID       # 4
        assert sig.discontinuity == PPVBand.HIGH   # 7
        assert sig.rhythmic_impulse == PPVBand.LOW # 2
        assert sig.stability_pressure == PPVBand.MID # 5

    def test_band_signature_string(self):
        """Band signature should produce string representation."""
        values = (0, 0, 0, 0, 0, 0, 0, 0)  # All LOW
        sig = create_ppv_band_signature(values)
        assert sig.as_string() == "LLLLLLLL"

        values = (7, 7, 7, 7, 7, 7, 7, 7)  # All HIGH
        sig = create_ppv_band_signature(values)
        assert sig.as_string() == "HHHHHHHH"

    def test_variant_id_computation(self):
        """Variant ID should be computed from band signature."""
        values = (3, 3, 3, 3, 3, 3, 3, 3)  # All MID
        sig = create_ppv_band_signature(values)
        variant_id = compute_variant_id(sig)

        assert variant_id == "M_M_M_M_M_M_M_M"

    def test_different_ppv_different_variant_id(self):
        """Different PPV values should produce different variant IDs."""
        values1 = (0, 0, 0, 0, 0, 0, 0, 0)
        values2 = (7, 7, 7, 7, 7, 7, 7, 7)

        sig1 = create_ppv_band_signature(values1)
        sig2 = create_ppv_band_signature(values2)

        variant_id1 = compute_variant_id(sig1)
        variant_id2 = compute_variant_id(sig2)

        assert variant_id1 != variant_id2


# =============================================================================
# Ontological Path Tests
# =============================================================================


class TestOntologicalPath:
    """Tests for ontological path → template family routing."""

    def test_family_from_path(self):
        """Each layer should map to its family."""
        test_cases = [
            (("ACTING",), OntologicalFamily.ACTING),
            (("TAGGING",), OntologicalFamily.TAGGING),
            (("FORMING",), OntologicalFamily.FORMING),
            (("THINKING",), OntologicalFamily.THINKING),
            (("DIRECTING",), OntologicalFamily.DIRECTING),
            (("REASONING",), OntologicalFamily.REASONING),
            (("PURPOSING",), OntologicalFamily.PURPOSING),
            (("META_OBSERVING",), OntologicalFamily.META_OBSERVING),
            (("UNIFYING",), OntologicalFamily.UNIFYING),
            (("ABSOLVING",), OntologicalFamily.ABSOLVING),
        ]

        for path, expected_family in test_cases:
            assert get_template_family(path) == expected_family

    def test_family_uses_first_layer(self):
        """Family should be determined by path[0] only."""
        # Multi-layer path - only first layer matters
        path = ("THINKING", "DIRECTING", "REASONING")
        assert get_template_family(path) == OntologicalFamily.THINKING

        path = ("DIRECTING", "THINKING", "REASONING")
        assert get_template_family(path) == OntologicalFamily.DIRECTING

    def test_unknown_path_returns_default(self):
        """Unknown path should return DEFAULT family (fail-closed)."""
        assert get_template_family(("UNKNOWN",)) == OntologicalFamily.DEFAULT
        assert get_template_family(()) == OntologicalFamily.DEFAULT

    def test_different_paths_different_families(self):
        """Different primary layers should produce different families."""
        path1 = ("THINKING", "DIRECTING")
        path2 = ("ACTING", "DIRECTING")

        family1 = get_template_family(path1)
        family2 = get_template_family(path2)

        assert family1 != family2


# =============================================================================
# Template Key Tests
# =============================================================================


class TestTemplateKey:
    """Tests for template key construction."""

    def test_template_key_creation(self):
        """Template key should be created from path and PPV."""
        path = ("THINKING", "DIRECTING")
        ppv = (3, 3, 3, 3, 3, 3, 3, 3)

        key = create_template_key(path, ppv)

        assert key.family == OntologicalFamily.THINKING
        assert "_" in key.variant_id  # Composite variant ID
        assert isinstance(key.slot_plan, SlotPlan)

    def test_same_inputs_same_key(self):
        """Same inputs should produce same template key."""
        path = ("FORMING",)
        ppv = (1, 2, 3, 4, 5, 6, 7, 0)

        key1 = create_template_key(path, ppv)
        key2 = create_template_key(path, ppv)

        assert key1.as_tuple() == key2.as_tuple()
        assert key1.key_hash() == key2.key_hash()

    def test_different_path_different_key(self):
        """Different paths should produce different template keys."""
        ppv = (3, 3, 3, 3, 3, 3, 3, 3)

        key1 = create_template_key(("THINKING",), ppv)
        key2 = create_template_key(("ACTING",), ppv)

        assert key1.family != key2.family
        assert key1.as_tuple() != key2.as_tuple()

    def test_different_ppv_different_key(self):
        """Different PPV should produce different template keys."""
        path = ("THINKING",)

        key1 = create_template_key(path, (0, 0, 0, 0, 0, 0, 0, 0))
        key2 = create_template_key(path, (7, 7, 7, 7, 7, 7, 7, 7))

        assert key1.variant_id != key2.variant_id
        assert key1.as_tuple() != key2.as_tuple()


# =============================================================================
# Registry Tests
# =============================================================================


class TestRegistry:
    """Tests for template registry."""

    def test_governed_registry_exists(self):
        """GOVERNED registry should exist and have entries."""
        registry = get_registry(RegistryType.GOVERNED)
        assert len(registry) > 0

    def test_open_registry_exists(self):
        """OPEN registry should exist and have entries."""
        registry = get_registry(RegistryType.OPEN)
        assert len(registry) > 0

    def test_open_superset_of_governed(self):
        """OPEN registry should be superset of GOVERNED."""
        governed = get_registry(RegistryType.GOVERNED)
        open_reg = get_registry(RegistryType.OPEN)

        assert len(open_reg) >= len(governed)

        # All GOVERNED keys should be in OPEN
        for key in governed.keys():
            assert key in open_reg

    def test_registry_stats(self):
        """Registry stats should provide accurate counts."""
        stats = get_registry_stats(RegistryType.GOVERNED)

        assert stats["registry_type"] == "GOVERNED"
        assert stats["total_templates"] > 0
        assert stats["unique_template_ids"] > 0
        assert "family_counts" in stats
        assert "slot_plan_counts" in stats

    def test_template_lookup(self):
        """Template lookup should return valid templates."""
        key = TemplateKey(
            family=OntologicalFamily.THINKING,
            variant_id="M_M_M_M_M_M_M_M",
            slot_plan=SlotPlan.STANDARD,
        )

        template = lookup_template(key, RegistryType.GOVERNED)

        assert template is not None
        assert template.template_id is not None
        assert template.template_string is not None


# =============================================================================
# Silent Collapse Prevention Tests
# =============================================================================


class TestSilentCollapsePrevention:
    """Tests for silent collapse prevention."""

    def test_no_silent_collapse_governed(self):
        """GOVERNED registry should have no silent collapse."""
        result = validate_no_silent_collapse(RegistryType.GOVERNED)

        assert result.passed, f"Silent collapse detected: {result.collision_details}"
        assert result.collision_count == 0
        assert result.total_template_ids == result.total_keys

    def test_no_silent_collapse_open(self):
        """OPEN registry should have no silent collapse."""
        result = validate_no_silent_collapse(RegistryType.OPEN)

        assert result.passed, f"Silent collapse detected: {result.collision_details}"
        assert result.collision_count == 0

    def test_distinct_keys_distinct_template_ids(self):
        """Distinct template keys should produce distinct template IDs."""
        template_ids: Set[str] = set()

        # Generate various keys
        paths = [("THINKING",), ("ACTING",), ("FORMING",)]
        ppv_sets = [
            (0, 0, 0, 0, 0, 0, 0, 0),
            (3, 3, 3, 3, 3, 3, 3, 3),
            (7, 7, 7, 7, 7, 7, 7, 7),
        ]

        for path in paths:
            for ppv in ppv_sets:
                key = create_template_key(path, ppv)
                template = lookup_template(key, RegistryType.GOVERNED)
                template_ids.add(template.template_id)

        # Should have 9 distinct template IDs (3 paths × 3 PPV sets)
        assert len(template_ids) == 9

    def test_registry_completeness(self):
        """Registry should have expected coverage."""
        # Check GOVERNED completeness for sample families
        is_complete = validate_registry_completeness(
            RegistryType.GOVERNED,
            families=[OntologicalFamily.THINKING, OntologicalFamily.ACTING],
            variant_ids=["M_M_M_M_M_M_M_M", "L_L_L_L_L_L_L_L"],
            slot_plans=[SlotPlan.MINIMAL, SlotPlan.STANDARD],
        )

        assert is_complete


# =============================================================================
# Controller Tests
# =============================================================================


class TestPhase11BController:
    """Tests for Phase-11B controller."""

    def test_controller_execution(self):
        """Controller should execute and return valid response."""
        request = make_request()
        controller = Phase11BController()

        response = controller.execute(request)

        assert isinstance(response, Phase11BResponse)
        assert response.template_id is not None
        assert response.template_key is not None
        assert response.output_text is not None

    def test_governed_mode_deterministic(self):
        """GOVERNED mode should be fully deterministic."""
        request = make_request(render_mode=RenderMode.GOVERNED)

        # Run 10 times
        responses = [
            run_phase11b_controller(request)
            for _ in range(10)
        ]

        # All outputs should be identical
        hashes = [r.candidate_output_hash for r in responses]
        assert len(set(hashes)) == 1, "GOVERNED mode is not deterministic!"

    def test_different_paths_different_outputs(self):
        """Different ontological paths should produce different outputs."""
        request1 = make_request(ontological_path=("THINKING",))
        request2 = make_request(ontological_path=("ACTING",))

        response1 = run_phase11b_controller(request1)
        response2 = run_phase11b_controller(request2)

        # Template IDs should differ
        assert response1.template_id != response2.template_id

        # Output hashes should differ
        assert response1.candidate_output_hash != response2.candidate_output_hash

    def test_different_ppv_different_outputs(self):
        """Different PPV values should produce different outputs."""
        request1 = make_request(ppv_values=(0, 0, 0, 0, 0, 0, 0, 0))
        request2 = make_request(ppv_values=(7, 7, 7, 7, 7, 7, 7, 7))

        response1 = run_phase11b_controller(request1)
        response2 = run_phase11b_controller(request2)

        # Template IDs should differ (different variant IDs)
        assert response1.template_id != response2.template_id

    def test_mode_affects_registry(self):
        """Different modes should use different registries."""
        base_request = Phase11BRequest(
            artifact_id="test",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(),
            ontological_path=("THINKING",),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            render_mode=RenderMode.GOVERNED,
        )

        governed_response = run_phase11b_controller(base_request)
        assert governed_response.registry_used == RegistryType.GOVERNED

        open_request = Phase11BRequest(
            artifact_id="test",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(),
            ontological_path=("THINKING",),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
            render_mode=RenderMode.OPEN,
        )

        open_response = run_phase11b_controller(open_request)
        assert open_response.registry_used == RegistryType.OPEN

    def test_structural_differentiation_verification(self):
        """Structural differentiation verification should detect differences."""
        request1 = make_request(ontological_path=("THINKING",))
        request2 = make_request(ontological_path=("ACTING",))

        # Should detect differentiation
        is_different = verify_structural_differentiation(request1, request2)
        assert is_different

    def test_differentiation_axes_detection(self):
        """Should correctly identify which axes differ."""
        request1 = make_request(
            ontological_path=("THINKING",),
            ppv_values=(0, 0, 0, 0, 0, 0, 0, 0),
        )
        request2 = make_request(
            ontological_path=("ACTING",),
            ppv_values=(7, 7, 7, 7, 7, 7, 7, 7),
        )

        axes = get_differentiation_axes(request1, request2)

        assert axes["ontological_path"] is True
        assert axes["ontological_family"] is True
        assert axes["ppv_band_signature"] is True


# =============================================================================
# Stability Tests
# =============================================================================


class TestStability:
    """Tests for output stability."""

    def test_same_input_same_output_governed(self):
        """Same input should produce byte-identical output in GOVERNED."""
        request = make_request(render_mode=RenderMode.GOVERNED)

        outputs = [
            run_phase11b_controller(request).output_text
            for _ in range(100)
        ]

        # All outputs should be identical
        assert len(set(outputs)) == 1

    def test_hash_stability(self):
        """Output hash should be stable across runs."""
        request = make_request()

        hashes = [
            run_phase11b_controller(request).candidate_output_hash
            for _ in range(50)
        ]

        assert len(set(hashes)) == 1


# =============================================================================
# Differentiation Depth Tests (Ceiling Tests)
# =============================================================================


class TestDifferentiationDepth:
    """Tests for differentiation depth (ceiling tests)."""

    def test_path_variation_uniqueness(self):
        """Path variations should produce unique outputs."""
        paths = [
            ("ACTING",),
            ("TAGGING",),
            ("FORMING",),
            ("THINKING",),
            ("DIRECTING",),
            ("REASONING",),
            ("PURPOSING",),
            ("META_OBSERVING",),
            ("UNIFYING",),
            ("ABSOLVING",),
        ]

        template_ids = set()
        output_hashes = set()

        for path in paths:
            request = make_request(ontological_path=path)
            response = run_phase11b_controller(request)
            template_ids.add(response.template_id)
            output_hashes.add(response.candidate_output_hash)

        # Should have 10 unique template IDs (one per family)
        assert len(template_ids) == 10
        assert len(output_hashes) == 10

    def test_ppv_dimension_variation_produces_effects(self):
        """Varying single PPV dimensions should produce effects."""
        base_ppv = [3, 3, 3, 3, 3, 3, 3, 3]
        variant_ids = set()

        # Test varying each dimension to extreme
        for dim in range(8):
            # Low extreme
            ppv_low = base_ppv.copy()
            ppv_low[dim] = 0
            sig_low = create_ppv_band_signature(tuple(ppv_low))
            variant_ids.add(compute_variant_id(sig_low))

            # High extreme
            ppv_high = base_ppv.copy()
            ppv_high[dim] = 7
            sig_high = create_ppv_band_signature(tuple(ppv_high))
            variant_ids.add(compute_variant_id(sig_high))

        # Should have multiple distinct variant IDs
        # (8 dimensions × 2 extremes = 16, but some may share same band pattern)
        assert len(variant_ids) >= 10

    def test_cross_axis_differentiation(self):
        """Cross-axis variations should be distinguishable."""
        configs: List[Tuple[Tuple[str, ...], Tuple[int, ...]]] = [
            # Vary path only
            (("THINKING",), (3, 3, 3, 3, 3, 3, 3, 3)),
            (("ACTING",), (3, 3, 3, 3, 3, 3, 3, 3)),

            # Vary PPV only
            (("FORMING",), (0, 0, 0, 0, 0, 0, 0, 0)),
            (("FORMING",), (7, 7, 7, 7, 7, 7, 7, 7)),

            # Vary both
            (("DIRECTING",), (0, 0, 0, 0, 0, 0, 0, 0)),
            (("REASONING",), (7, 7, 7, 7, 7, 7, 7, 7)),
        ]

        outputs = set()
        for path, ppv in configs:
            request = make_request(ontological_path=path, ppv_values=ppv)
            response = run_phase11b_controller(request)
            outputs.add(response.candidate_output_hash)

        # All 6 configurations should produce unique outputs
        assert len(outputs) == 6

    def test_differentiation_score_target(self):
        """
        Differentiation score should meet target (~0.85+).

        This test measures the ratio of unique outputs to total outputs.
        """
        all_paths = [
            ("ACTING",), ("TAGGING",), ("FORMING",), ("THINKING",),
            ("DIRECTING",), ("REASONING",), ("PURPOSING",),
            ("META_OBSERVING",), ("UNIFYING",), ("ABSOLVING",),
        ]

        ppv_variants = [
            (0, 0, 0, 0, 0, 0, 0, 0),
            (3, 3, 3, 3, 3, 3, 3, 3),
            (7, 7, 7, 7, 7, 7, 7, 7),
            (0, 3, 6, 0, 3, 6, 0, 3),
            (6, 3, 0, 6, 3, 0, 6, 3),
        ]

        output_hashes = set()
        total_runs = 0

        for path in all_paths:
            for ppv in ppv_variants:
                request = make_request(ontological_path=path, ppv_values=ppv)
                response = run_phase11b_controller(request)
                output_hashes.add(response.candidate_output_hash)
                total_runs += 1

        # Calculate differentiation score
        differentiation_score = len(output_hashes) / total_runs

        # Target: ~0.85+ (Phase-11A was ~0.29)
        assert differentiation_score >= 0.85, (
            f"Differentiation score {differentiation_score:.2f} < 0.85 target"
        )


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_create_governed_request(self):
        """create_phase11b_governed_request should create GOVERNED request."""
        request = create_phase11b_governed_request(
            artifact_id="test",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(),
            ontological_path=("THINKING",),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
        )

        assert request.render_mode == RenderMode.GOVERNED

    def test_create_open_request(self):
        """create_phase11b_open_request should create OPEN request."""
        request = create_phase11b_open_request(
            artifact_id="test",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(),
            ontological_path=("THINKING",),
            ppv_values=(3, 3, 3, 3, 3, 3, 3, 3),
        )

        assert request.render_mode == RenderMode.OPEN


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests for Phase-11B."""

    def test_full_pipeline_governed(self):
        """Full pipeline should work in GOVERNED mode."""
        request = create_phase11b_governed_request(
            artifact_id="integration-test-1",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(
                vc_facts=("VC-1", "VC-2", "VC-3"),
                source_data={
                    "vc_1_data": "test_observation",
                    "vc_2_data": "test_state",
                    "vc_3_data": "test_context",
                },
            ),
            ontological_path=("THINKING", "DIRECTING", "REASONING"),
            ppv_values=(2, 4, 6, 1, 3, 5, 7, 0),
        )

        response = run_phase11b_controller(request)

        # Verify response structure
        assert not response.is_blocked()
        assert response.was_governed()
        assert response.template_key.family == OntologicalFamily.THINKING
        assert response.registry_used == RegistryType.GOVERNED
        assert len(response.candidate_output_hash) == 16
        assert len(response.ledger_span_id) > 0

        # Verify output contains expected markers
        assert "[FAMILY:THINKING]" in response.output_text
        assert "[VARIANT:" in response.output_text

    def test_full_pipeline_open(self):
        """Full pipeline should work in OPEN mode."""
        request = create_phase11b_open_request(
            artifact_id="integration-test-2",
            artifact_hash=make_artifact_hash(),
            phase10_result=make_phase10_result(),
            ontological_path=("ACTING",),
            ppv_values=(5, 5, 5, 5, 5, 5, 5, 5),
        )

        response = run_phase11b_controller(request)

        assert not response.was_governed()
        assert response.registry_used == RegistryType.OPEN
        assert response.template_key.family == OntologicalFamily.ACTING

    def test_ledger_recording(self):
        """Controller should record to ledger."""
        controller = Phase11BController()
        request = make_request()

        initial_count = len(controller.ledger_store)
        controller.execute(request)

        assert len(controller.ledger_store) == initial_count + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
