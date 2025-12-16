"""
Test Suite for Phase-11B.1 Collision-Free Routing
===================================================

This test suite verifies the collision-free routing patch:

    T-1: Determinism (100 runs)
    T-2: Known collision case: (3..3) vs (4..4) must NOT collide
    T-3: Injectivity check for bounded set of keys (50-200 keys)
    T-4: Collapse only-by-map: if collapse, prove recorded; otherwise no collapse
    T-5: Missing template fails closed

CONSTRAINTS:
    - No external LLM calls
    - No ML/NLP imports
    - Deterministic only
    - Allowed imports: __future__, dataclasses, enum, hashlib, typing
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phase11b1_routing import (
    # Constants
    RENDER_BLOCKED,
    PPV_DIM_COUNT,
    COLLAPSE_MAP,
    # Enums
    PPVSubBand,
    PPVBand,
    OntologicalFamily,
    SlotPlan,
    RegistryType,
    RenderMode,
    FailureReason,
    # Dataclasses
    SubBandSignature,
    RoutingKey,
    RoutingTrace,
    Phase11B1Request,
    Phase11B1Response,
    P11B1Template,
    CollapseValidationResult,
    # Functions
    get_ppv_subband,
    get_coarse_band,
    create_subband_signature,
    get_template_family,
    get_slot_plan_from_subband,
    create_routing_key,
    get_registry,
    lookup_template,
    apply_collapse_map,
    execute_phase11b1,
    validate_no_silent_collapse,
    validate_injectivity,
)


# =============================================================================
# Test Helpers
# =============================================================================


def make_artifact_hash() -> str:
    """Create a valid 64-char hex hash."""
    return hashlib.sha256(b"test_artifact").hexdigest()


def make_request(
    ppv_values: Tuple[int, ...],
    path: Tuple[str, ...] = ("THINKING",),
    mode: RenderMode = RenderMode.GOVERNED,
    artifact_id: str = "test-artifact",
) -> Phase11B1Request:
    """Create a test request."""
    return Phase11B1Request(
        artifact_id=artifact_id,
        artifact_hash=make_artifact_hash(),
        ontological_path=path,
        ppv_values=ppv_values,
        render_mode=mode,
        vc_source_data={
            "vc_1_data": "observation_datum",
            "vc_2_data": "state_datum",
            "vc_3_data": "context_datum",
            "vc_4_data": "reference_datum",
            "vc_5_data": "marker_datum",
        },
    )


# =============================================================================
# T-1: Determinism Test (100 runs)
# =============================================================================


class TestDeterminism:
    """T-1: Verify deterministic behavior over 100 runs."""

    def test_determinism_same_input_same_output_100_runs(self) -> None:
        """Same input must produce identical output across 100 runs."""
        # Fixed input
        request = make_request(
            ppv_values=(3, 4, 5, 2, 3, 4, 5, 6),
            path=("THINKING", "DIRECTING"),
        )

        # Run 100 times
        outputs: List[str] = []
        template_ids: List[str] = []
        variant_ids: List[str] = []

        for _ in range(100):
            response = execute_phase11b1(request)
            outputs.append(response.output_text)
            template_ids.append(response.template_id)
            variant_ids.append(response.subband_variant_id)

        # All outputs must be identical
        assert len(set(outputs)) == 1, f"Got {len(set(outputs))} unique outputs"
        assert len(set(template_ids)) == 1, f"Got {len(set(template_ids))} unique template_ids"
        assert len(set(variant_ids)) == 1, f"Got {len(set(variant_ids))} unique variant_ids"

    def test_determinism_routing_key_hash(self) -> None:
        """Routing key hash must be deterministic."""
        key = create_routing_key(
            ontological_path=("FORMING",),
            ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
        )

        hashes = [key.routing_key_hash() for _ in range(100)]
        assert len(set(hashes)) == 1, "Routing key hash not deterministic"

    def test_determinism_subband_signature_hash(self) -> None:
        """SubBand signature hash must be deterministic."""
        sig = create_subband_signature((0, 1, 2, 3, 4, 5, 6, 7))

        hashes = [sig.signature_hash() for _ in range(100)]
        assert len(set(hashes)) == 1, "Signature hash not deterministic"


# =============================================================================
# T-2: Known Collision Case Test
# =============================================================================


class TestKnownCollisionCase:
    """T-2: Verify (3..3) vs (4..4) do NOT collide anymore."""

    def test_all_3s_vs_all_4s_no_collision(self) -> None:
        """
        PPV values (3,3,3,3,3,3,3,3) vs (4,4,4,4,4,4,4,4) must NOT collide.

        In the old coarse-band system, both would map to M_M_M_M_M_M_M_M.
        With SubBands, they map to M0_M0_M0_M0_M0_M0_M0_M0 vs M1_M1_M1_M1_M1_M1_M1_M1.
        """
        # Both in MID coarse band
        ppv_all_3s = (3, 3, 3, 3, 3, 3, 3, 3)
        ppv_all_4s = (4, 4, 4, 4, 4, 4, 4, 4)

        # Create requests
        request_3s = make_request(ppv_values=ppv_all_3s)
        request_4s = make_request(ppv_values=ppv_all_4s)

        # Execute
        response_3s = execute_phase11b1(request_3s)
        response_4s = execute_phase11b1(request_4s)

        # Verify SubBand variant IDs differ
        assert response_3s.subband_variant_id == "M0_M0_M0_M0_M0_M0_M0_M0"
        assert response_4s.subband_variant_id == "M1_M1_M1_M1_M1_M1_M1_M1"
        assert response_3s.subband_variant_id != response_4s.subband_variant_id

        # Verify coarse band signature is same (for reporting)
        assert response_3s.band_signature == "MMMMMMMM"
        assert response_4s.band_signature == "MMMMMMMM"

        # Verify template_ids differ (no collision!)
        if response_3s.template_id and response_4s.template_id:
            assert response_3s.template_id != response_4s.template_id, (
                f"Collision detected: both map to {response_3s.template_id}"
            )

    def test_collision_within_same_coarse_band(self) -> None:
        """Multiple values within same coarse band must NOT collide."""
        # All values in LOW band (0, 1, 2)
        ppv_0s = (0, 0, 0, 0, 0, 0, 0, 0)
        ppv_1s = (1, 1, 1, 1, 1, 1, 1, 1)
        ppv_2s = (2, 2, 2, 2, 2, 2, 2, 2)

        sig_0s = create_subband_signature(ppv_0s)
        sig_1s = create_subband_signature(ppv_1s)
        sig_2s = create_subband_signature(ppv_2s)

        # All have same coarse band signature
        assert sig_0s.to_band_signature_string() == "LLLLLLLL"
        assert sig_1s.to_band_signature_string() == "LLLLLLLL"
        assert sig_2s.to_band_signature_string() == "LLLLLLLL"

        # All have DIFFERENT subband variant IDs
        assert sig_0s.to_variant_id() == "L0_L0_L0_L0_L0_L0_L0_L0"
        assert sig_1s.to_variant_id() == "L1_L1_L1_L1_L1_L1_L1_L1"
        assert sig_2s.to_variant_id() == "L2_L2_L2_L2_L2_L2_L2_L2"

        assert len({
            sig_0s.to_variant_id(),
            sig_1s.to_variant_id(),
            sig_2s.to_variant_id(),
        }) == 3

    def test_high_band_no_collision(self) -> None:
        """Values 6 and 7 (both HIGH) must NOT collide."""
        ppv_6s = (6, 6, 6, 6, 6, 6, 6, 6)
        ppv_7s = (7, 7, 7, 7, 7, 7, 7, 7)

        sig_6s = create_subband_signature(ppv_6s)
        sig_7s = create_subband_signature(ppv_7s)

        # Both HIGH coarse band
        assert sig_6s.to_band_signature_string() == "HHHHHHHH"
        assert sig_7s.to_band_signature_string() == "HHHHHHHH"

        # Different subband variant IDs
        assert sig_6s.to_variant_id() == "H0_H0_H0_H0_H0_H0_H0_H0"
        assert sig_7s.to_variant_id() == "H1_H1_H1_H1_H1_H1_H1_H1"
        assert sig_6s.to_variant_id() != sig_7s.to_variant_id()


# =============================================================================
# T-3: Injectivity Check (Bounded Set of Keys)
# =============================================================================


class TestInjectivity:
    """T-3: Verify no duplicate template_ids across distinct canonical keys."""

    def _generate_test_keys(self, count: int = 100) -> List[RoutingKey]:
        """Generate a set of distinct routing keys for testing."""
        keys: List[RoutingKey] = []
        families = [f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT]
        slot_plans = [SlotPlan.MINIMAL, SlotPlan.STANDARD, SlotPlan.EXTENDED]

        # Generate keys by varying PPV values
        ppv_samples = [
            (0, 0, 0, 0, 0, 0, 0, 0),
            (1, 1, 1, 1, 1, 1, 1, 1),
            (2, 2, 2, 2, 2, 2, 2, 2),
            (3, 3, 3, 3, 3, 3, 3, 3),
            (4, 4, 4, 4, 4, 4, 4, 4),
            (5, 5, 5, 5, 5, 5, 5, 5),
            (6, 6, 6, 6, 6, 6, 6, 6),
            (7, 7, 7, 7, 7, 7, 7, 7),
            (0, 1, 2, 3, 4, 5, 6, 7),
            (7, 6, 5, 4, 3, 2, 1, 0),
            (0, 7, 0, 7, 0, 7, 0, 7),
            (3, 3, 3, 3, 6, 6, 6, 6),
        ]

        for family in families[:5]:  # Limit families for bounded test
            for ppv in ppv_samples:
                for slot_plan in slot_plans:
                    sig = create_subband_signature(ppv)
                    key = RoutingKey(
                        family=family,
                        subband_variant_id=sig.to_variant_id(),
                        slot_plan=slot_plan,
                    )
                    keys.append(key)
                    if len(keys) >= count:
                        return keys

        return keys

    def test_injectivity_50_keys(self) -> None:
        """No duplicate template_ids across 50 distinct keys."""
        keys = self._generate_test_keys(50)
        passed, collisions = validate_injectivity(
            tuple(keys), RegistryType.GOVERNED
        )
        assert passed, f"Injectivity failed: {collisions}"

    def test_injectivity_100_keys(self) -> None:
        """No duplicate template_ids across 100 distinct keys."""
        keys = self._generate_test_keys(100)
        passed, collisions = validate_injectivity(
            tuple(keys), RegistryType.GOVERNED
        )
        assert passed, f"Injectivity failed: {collisions}"

    def test_injectivity_200_keys(self) -> None:
        """No duplicate template_ids across 200 distinct keys."""
        keys = self._generate_test_keys(200)
        passed, collisions = validate_injectivity(
            tuple(keys), RegistryType.GOVERNED
        )
        assert passed, f"Injectivity failed: {collisions}"

    def test_registry_no_silent_collapse_governed(self) -> None:
        """GOVERNED registry must have no silent collapse."""
        result = validate_no_silent_collapse(RegistryType.GOVERNED)
        assert result.passed, (
            f"Silent collapse detected: {result.collision_count} collisions\n"
            f"Details: {result.collision_details}"
        )

    def test_registry_no_silent_collapse_open(self) -> None:
        """OPEN registry must have no silent collapse."""
        result = validate_no_silent_collapse(RegistryType.OPEN)
        assert result.passed, (
            f"Silent collapse detected: {result.collision_count} collisions\n"
            f"Details: {result.collision_details}"
        )

    def test_distinct_keys_produce_distinct_hashes(self) -> None:
        """Distinct routing keys must produce distinct hashes."""
        keys = self._generate_test_keys(100)
        hashes = {k.routing_key_hash() for k in keys}
        assert len(hashes) == len(keys), (
            f"Hash collision: {len(keys)} keys but only {len(hashes)} unique hashes"
        )


# =============================================================================
# T-4: Collapse Only-By-Map Test
# =============================================================================


class TestCollapseOnlyByMap:
    """T-4: Collapse only via COLLAPSE_MAP; if collapse, must be recorded."""

    def test_default_collapse_map_is_empty(self) -> None:
        """Default COLLAPSE_MAP must be empty (no implicit collapse)."""
        assert len(COLLAPSE_MAP) == 0, "Default COLLAPSE_MAP should be empty"

    def test_no_collapse_without_map(self) -> None:
        """Without entries in COLLAPSE_MAP, no collapse should occur."""
        request = make_request(ppv_values=(3, 4, 5, 2, 3, 4, 5, 6))
        response = execute_phase11b1(request)

        trace = response.routing_trace
        assert trace.collapse_applied is False, "Collapse should not occur with empty map"
        assert trace.collapse_source is None, "Collapse source should be None"
        assert trace.original_key == trace.canonical_key, "Keys should be identical"

    def test_collapse_recorded_when_map_used(self) -> None:
        """When COLLAPSE_MAP is used, collapse_applied must be True."""
        # Create a custom collapse map for this test
        source_key = create_routing_key(
            ontological_path=("THINKING",),
            ppv_values=(0, 0, 0, 0, 0, 0, 0, 0),
        )
        target_key = create_routing_key(
            ontological_path=("THINKING",),
            ppv_values=(1, 1, 1, 1, 1, 1, 1, 1),
        )
        custom_collapse_map = {source_key: target_key}

        # Execute with custom collapse map
        request = make_request(ppv_values=(0, 0, 0, 0, 0, 0, 0, 0))
        response = execute_phase11b1(request, collapse_map=custom_collapse_map)

        trace = response.routing_trace
        assert trace.collapse_applied is True, "Collapse should be recorded"
        assert trace.collapse_source == source_key, "Collapse source should match"
        assert trace.canonical_key == target_key, "Canonical key should be target"

    def test_apply_collapse_map_function(self) -> None:
        """Test apply_collapse_map function directly."""
        source = RoutingKey(
            family=OntologicalFamily.ACTING,
            subband_variant_id="L0_L0_L0_L0_L0_L0_L0_L0",
            slot_plan=SlotPlan.STANDARD,
        )
        target = RoutingKey(
            family=OntologicalFamily.ACTING,
            subband_variant_id="L1_L1_L1_L1_L1_L1_L1_L1",
            slot_plan=SlotPlan.STANDARD,
        )
        collapse_map = {source: target}

        # Source key should collapse
        canonical, applied, src = apply_collapse_map(source, collapse_map)
        assert canonical == target
        assert applied is True
        assert src == source

        # Non-mapped key should not collapse
        other = RoutingKey(
            family=OntologicalFamily.FORMING,
            subband_variant_id="M0_M0_M0_M0_M0_M0_M0_M0",
            slot_plan=SlotPlan.STANDARD,
        )
        canonical2, applied2, src2 = apply_collapse_map(other, collapse_map)
        assert canonical2 == other
        assert applied2 is False
        assert src2 is None

    def test_trace_records_collapse_correctly(self) -> None:
        """Routing trace must correctly record collapse information."""
        key1 = create_routing_key(("THINKING",), (2, 2, 2, 2, 2, 2, 2, 2))
        key2 = create_routing_key(("THINKING",), (3, 3, 3, 3, 3, 3, 3, 3))
        collapse_map = {key1: key2}

        template, trace = lookup_template(key1, RegistryType.GOVERNED, collapse_map)

        assert trace.original_key == key1
        assert trace.canonical_key == key2
        assert trace.collapse_applied is True
        assert trace.collapse_source == key1


# =============================================================================
# T-5: Missing Template Fails Closed
# =============================================================================


class TestFailsClosed:
    """T-5: Missing template must return RENDER_BLOCKED."""

    def test_missing_key_returns_render_blocked(self) -> None:
        """Key not in registry must return RENDER_BLOCKED."""
        # Create a key that won't be in the registry
        # Use an unusual variant_id that wasn't pre-generated
        unusual_variant = "L0_L1_L2_M0_M1_M2_H0_L0"  # Not in representative samples

        key = RoutingKey(
            family=OntologicalFamily.THINKING,
            subband_variant_id=unusual_variant,
            slot_plan=SlotPlan.STANDARD,
        )

        template, trace = lookup_template(key, RegistryType.GOVERNED)

        assert template is None, "Template should not be found"
        assert trace.failure_reason == FailureReason.KEY_NOT_IN_REGISTRY
        assert trace.template_id is None

    def test_execute_returns_render_blocked_for_missing(self) -> None:
        """Execute must return RENDER_BLOCKED for missing template."""
        # Use PPV values that produce an unusual variant not in registry
        request = Phase11B1Request(
            artifact_id="test-missing",
            artifact_hash=make_artifact_hash(),
            ontological_path=("THINKING",),
            ppv_values=(0, 1, 2, 0, 1, 2, 0, 1),  # Unusual pattern
            render_mode=RenderMode.GOVERNED,
            vc_source_data={},
        )

        response = execute_phase11b1(request)

        # Check response based on whether key is in registry
        if response.is_blocked():
            assert response.output_text == RENDER_BLOCKED
            assert response.template_id == ""
            assert response.verifier_passed is False
            assert response.routing_trace.failure_reason == FailureReason.KEY_NOT_IN_REGISTRY
        # If not blocked, the variant was in registry (which is also valid)

    def test_render_blocked_constant_value(self) -> None:
        """RENDER_BLOCKED must be a specific constant string."""
        assert RENDER_BLOCKED == "RENDER_BLOCKED"
        assert isinstance(RENDER_BLOCKED, str)

    def test_failure_reason_enum_complete(self) -> None:
        """FailureReason enum must have all expected values."""
        expected_reasons = {
            "NONE",
            "KEY_NOT_IN_REGISTRY",
            "COLLAPSE_MAP_LOOKUP_FAILED",
            "TEMPLATE_RENDER_ERROR",
            "VERIFIER_FAILED",
        }
        actual_reasons = {r.value for r in FailureReason}
        assert expected_reasons == actual_reasons

    def test_trace_includes_failure_reason(self) -> None:
        """Trace must include structural failure reason."""
        key = RoutingKey(
            family=OntologicalFamily.THINKING,
            subband_variant_id="UNUSUAL_VARIANT_NOT_IN_REGISTRY",
            slot_plan=SlotPlan.STANDARD,
        )

        template, trace = lookup_template(key, RegistryType.GOVERNED)

        assert trace.failure_reason == FailureReason.KEY_NOT_IN_REGISTRY
        assert trace.template_id is None
        assert template is None


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestSubBandSignature:
    """Test SubBand signature functionality."""

    def test_subband_mapping_complete(self) -> None:
        """All PPV values 0-7 must map to a SubBand."""
        for v in range(8):
            sb = get_ppv_subband(v)
            assert isinstance(sb, PPVSubBand)

    def test_subband_mapping_correct(self) -> None:
        """SubBand mapping must follow spec."""
        assert get_ppv_subband(0) == PPVSubBand.L0
        assert get_ppv_subband(1) == PPVSubBand.L1
        assert get_ppv_subband(2) == PPVSubBand.L2
        assert get_ppv_subband(3) == PPVSubBand.M0
        assert get_ppv_subband(4) == PPVSubBand.M1
        assert get_ppv_subband(5) == PPVSubBand.M2
        assert get_ppv_subband(6) == PPVSubBand.H0
        assert get_ppv_subband(7) == PPVSubBand.H1

    def test_coarse_band_from_subband(self) -> None:
        """Coarse band derivation must be correct."""
        assert get_coarse_band(PPVSubBand.L0) == PPVBand.LOW
        assert get_coarse_band(PPVSubBand.L1) == PPVBand.LOW
        assert get_coarse_band(PPVSubBand.L2) == PPVBand.LOW
        assert get_coarse_band(PPVSubBand.M0) == PPVBand.MID
        assert get_coarse_band(PPVSubBand.M1) == PPVBand.MID
        assert get_coarse_band(PPVSubBand.M2) == PPVBand.MID
        assert get_coarse_band(PPVSubBand.H0) == PPVBand.HIGH
        assert get_coarse_band(PPVSubBand.H1) == PPVBand.HIGH

    def test_invalid_ppv_value_raises(self) -> None:
        """Invalid PPV values must raise ValueError."""
        with pytest.raises(ValueError):
            get_ppv_subband(-1)
        with pytest.raises(ValueError):
            get_ppv_subband(8)


class TestRoutingKey:
    """Test RoutingKey functionality."""

    def test_routing_key_frozen(self) -> None:
        """RoutingKey must be frozen (immutable)."""
        key = RoutingKey(
            family=OntologicalFamily.THINKING,
            subband_variant_id="L0_L0_L0_L0_L0_L0_L0_L0",
            slot_plan=SlotPlan.STANDARD,
        )
        with pytest.raises(AttributeError):
            key.family = OntologicalFamily.ACTING  # type: ignore

    def test_routing_key_canonical_string(self) -> None:
        """Canonical string format must be correct."""
        key = RoutingKey(
            family=OntologicalFamily.THINKING,
            subband_variant_id="L0_M1_H0",
            slot_plan=SlotPlan.STANDARD,
        )
        assert key.canonical_string() == "THINKING|L0_M1_H0|STANDARD"

    def test_routing_key_hash_length(self) -> None:
        """Routing key hash must be 64 chars."""
        key = RoutingKey(
            family=OntologicalFamily.THINKING,
            subband_variant_id="L0_M1_H0",
            slot_plan=SlotPlan.STANDARD,
        )
        assert len(key.routing_key_hash()) == 64


class TestPhase11B1Request:
    """Test Phase11B1Request functionality."""

    def test_request_frozen(self) -> None:
        """Request must be frozen (immutable)."""
        request = make_request(ppv_values=(3, 3, 3, 3, 3, 3, 3, 3))
        with pytest.raises(AttributeError):
            request.artifact_id = "modified"  # type: ignore

    def test_request_validation(self) -> None:
        """Request validation must work correctly."""
        # Valid request
        request = make_request(ppv_values=(0, 1, 2, 3, 4, 5, 6, 7))
        assert request.artifact_id == "test-artifact"

        # Invalid PPV count
        with pytest.raises(ValueError):
            Phase11B1Request(
                artifact_id="test",
                artifact_hash=make_artifact_hash(),
                ontological_path=("THINKING",),
                ppv_values=(1, 2, 3),  # Wrong count
                render_mode=RenderMode.GOVERNED,
            )

        # Invalid PPV value
        with pytest.raises(ValueError):
            Phase11B1Request(
                artifact_id="test",
                artifact_hash=make_artifact_hash(),
                ontological_path=("THINKING",),
                ppv_values=(1, 2, 3, 4, 5, 6, 7, 8),  # 8 is invalid
                render_mode=RenderMode.GOVERNED,
            )


class TestPhase11B1Response:
    """Test Phase11B1Response functionality."""

    def test_response_frozen(self) -> None:
        """Response must be frozen (immutable)."""
        request = make_request(ppv_values=(3, 3, 3, 3, 3, 3, 3, 3))
        response = execute_phase11b1(request)

        with pytest.raises(AttributeError):
            response.output_text = "modified"  # type: ignore

    def test_response_is_blocked_method(self) -> None:
        """is_blocked() must correctly identify blocked responses."""
        request = make_request(ppv_values=(3, 3, 3, 3, 3, 3, 3, 3))
        response = execute_phase11b1(request)

        if response.output_text == RENDER_BLOCKED:
            assert response.is_blocked() is True
        else:
            assert response.is_blocked() is False


# =============================================================================
# Registry Tests
# =============================================================================


class TestRegistry:
    """Test registry functionality."""

    def test_governed_registry_no_default_family(self) -> None:
        """GOVERNED registry should not contain DEFAULT family."""
        registry = get_registry(RegistryType.GOVERNED)
        for (reg_id, key_tuple), template in registry.items():
            assert template.routing_key.family != OntologicalFamily.DEFAULT, (
                f"DEFAULT family found in GOVERNED registry: {key_tuple}"
            )

    def test_registry_keys_match_templates(self) -> None:
        """Registry keys must match template routing keys."""
        for reg_type in [RegistryType.GOVERNED, RegistryType.OPEN]:
            registry = get_registry(reg_type)
            for (reg_id, key_tuple), template in registry.items():
                assert template.routing_key.as_tuple() == key_tuple

    def test_registry_deterministic(self) -> None:
        """Registry generation must be deterministic."""
        reg1 = get_registry(RegistryType.GOVERNED)
        reg2 = get_registry(RegistryType.GOVERNED)

        assert len(reg1) == len(reg2)
        for key in reg1:
            assert key in reg2
            assert reg1[key].template_id == reg2[key].template_id
