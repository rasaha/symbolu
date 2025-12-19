"""
Test Suite for Phase-11B.2 Canonicalization + Mode Identity Lock
==================================================================

This test suite verifies Phase-11B.2 requirements:

    1. Determinism (100 runs)
    2. Canonicalization applied path
    3. Canonicalization not needed path
    4. Fail-closed behavior
    5. No silent collapse for canonical keys
    6. Mode identity lock (OPEN == GOVERNED)

Target: ≥30 tests

CONSTRAINTS:
    - No external LLM calls
    - No ML/NLP imports
    - Deterministic only
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
    # Enums
    PPVSubBand,
    OntologicalFamily,
    SlotPlan,
    RenderMode,
    FailureReason,
    # Constants
    RENDER_BLOCKED,
)

from phase11b2_canonicalization import (
    # Version
    PHASE11B2_VERSION,
    # Constants
    ACCEPTED_FAMILIES,
    ACCEPTED_SLOT_PLANS,
    CANONICAL_SIGNATURES,
    CANONICAL_SUBBAND_REPRESENTATIVE,
    # Dataclasses
    CanonicalizationResult,
    Phase11B2RoutingTrace,
    Phase11B2Request,
    Phase11B2Response,
    RegistryCompletenessResult,
    CanonicalizationCoverageResult,
    InjectivityResult,
    # Functions
    is_canonical_signature,
    canonicalize_variant_id,
    canonicalize_from_ppv_values,
    get_unified_registry,
    lookup_unified_template,
    render_template,
    execute_phase11b2,
    validate_registry_completeness,
    validate_canonicalization_coverage,
    validate_registry_injectivity,
    validate_mode_identity,
)


# =============================================================================
# Test Helpers
# =============================================================================


def make_artifact_hash(seed: str = "test") -> str:
    """Create a valid 64-char hex hash."""
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def make_request(
    ppv_values: Tuple[int, ...],
    path: Tuple[str, ...] = ("THINKING",),
    mode: RenderMode = RenderMode.GOVERNED,
    artifact_id: str = "test-artifact",
) -> Phase11B2Request:
    """Create a test request."""
    return Phase11B2Request(
        artifact_id=artifact_id,
        artifact_hash=make_artifact_hash(f"{artifact_id}:{path}:{ppv_values}"),
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
# Test 1: Determinism (100 runs)
# =============================================================================


class TestDeterminism:
    """Test deterministic behavior across 100 runs."""

    def test_determinism_same_input_same_output_100_runs(self) -> None:
        """Same input must produce identical output across 100 runs."""
        request = make_request(
            ppv_values=(3, 4, 5, 2, 3, 4, 5, 6),
            path=("THINKING", "DIRECTING"),
        )

        outputs: List[str] = []
        template_ids: List[str] = []
        output_hashes: List[str] = []

        for _ in range(100):
            response = execute_phase11b2(request)
            outputs.append(response.output_text)
            template_ids.append(response.template_id)
            output_hashes.append(response.output_hash())

        assert len(set(outputs)) == 1, f"Got {len(set(outputs))} unique outputs"
        assert len(set(template_ids)) == 1, f"Got {len(set(template_ids))} template_ids"
        assert len(set(output_hashes)) == 1, f"Got {len(set(output_hashes))} hashes"

    def test_determinism_canonicalization_100_runs(self) -> None:
        """Canonicalization must produce identical results across 100 runs."""
        raw_variant = "L0_M2_H1_L2_M0_H0_L1_M1"

        results: List[str] = []
        for _ in range(100):
            result = canonicalize_variant_id(raw_variant)
            results.append(result.canonical_signature)

        assert len(set(results)) == 1

    def test_determinism_trace_hash_100_runs(self) -> None:
        """Trace hash must be deterministic across 100 runs."""
        request = make_request(ppv_values=(0, 1, 2, 3, 4, 5, 6, 7))

        trace_hashes: List[str] = []
        for _ in range(100):
            response = execute_phase11b2(request)
            trace_hashes.append(response.routing_trace.trace_hash())

        assert len(set(trace_hashes)) == 1


# =============================================================================
# Test 2: Canonicalization Applied Path
# =============================================================================


class TestCanonicalizationApplied:
    """Test canonicalization when raw signature is not in registry."""

    def test_canonicalization_applied_non_canonical_input(self) -> None:
        """Non-canonical input must be canonicalized and recorded."""
        # L0 -> L1 (canonical)
        request = make_request(ppv_values=(0, 0, 0, 0, 0, 0, 0, 0))
        response = execute_phase11b2(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is True
        assert trace.raw_signature == "L0_L0_L0_L0_L0_L0_L0_L0"
        assert trace.canonical_signature == "L1_L1_L1_L1_L1_L1_L1_L1"

    def test_canonicalization_trace_records_from_to(self) -> None:
        """Trace must record canonicalization source and target."""
        # M2 -> M1, H1 -> H0
        request = make_request(ppv_values=(5, 7, 5, 7, 5, 7, 5, 7))
        response = execute_phase11b2(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is True
        assert trace.raw_signature == "M2_H1_M2_H1_M2_H1_M2_H1"
        assert trace.canonical_signature == "M1_H0_M1_H0_M1_H0_M1_H0"

    def test_canonicalization_produces_valid_output(self) -> None:
        """Canonicalized request must produce valid (non-blocked) output."""
        # Non-canonical input that will be canonicalized
        request = make_request(ppv_values=(0, 2, 3, 5, 6, 7, 1, 4))
        response = execute_phase11b2(request)

        assert not response.is_blocked()
        assert response.template_id != ""
        assert response.routing_trace.canonicalization_applied is True

    def test_canonicalization_reduces_render_blocked(self) -> None:
        """Canonicalization should reduce RENDER_BLOCKED for valid families."""
        # Test multiple non-canonical inputs
        test_cases = [
            (0, 0, 0, 0, 0, 0, 0, 0),  # All L0 -> L1
            (2, 2, 2, 2, 2, 2, 2, 2),  # All L2 -> L1
            (7, 7, 7, 7, 7, 7, 7, 7),  # All H1 -> H0
            (3, 5, 3, 5, 3, 5, 3, 5),  # M0/M2 -> M1
        ]

        for ppv in test_cases:
            request = make_request(ppv_values=ppv, path=("THINKING",))
            response = execute_phase11b2(request)
            assert not response.is_blocked(), f"Blocked for PPV {ppv}"


# =============================================================================
# Test 3: Canonicalization Not Needed Path
# =============================================================================


class TestCanonicalizationNotNeeded:
    """Test when raw signature is already canonical."""

    def test_no_canonicalization_for_canonical_input(self) -> None:
        """Canonical input must not trigger canonicalization."""
        # L1, M1, H0 are canonical representatives
        request = make_request(ppv_values=(1, 4, 6, 1, 4, 6, 1, 4))
        response = execute_phase11b2(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is False
        assert trace.raw_signature == trace.canonical_signature

    def test_canonical_signatures_set_complete(self) -> None:
        """Canonical signatures set must contain 3^8 = 6561 entries."""
        assert len(CANONICAL_SIGNATURES) == 6561

    def test_is_canonical_signature_function(self) -> None:
        """is_canonical_signature must correctly identify canonical patterns."""
        # Canonical (uses L1, M1, H0)
        assert is_canonical_signature("L1_L1_L1_L1_L1_L1_L1_L1") is True
        assert is_canonical_signature("M1_M1_M1_M1_M1_M1_M1_M1") is True
        assert is_canonical_signature("H0_H0_H0_H0_H0_H0_H0_H0") is True
        assert is_canonical_signature("L1_M1_H0_L1_M1_H0_L1_M1") is True

        # Non-canonical (uses L0, L2, M0, M2, H1)
        assert is_canonical_signature("L0_L0_L0_L0_L0_L0_L0_L0") is False
        assert is_canonical_signature("L2_M0_H1_L2_M0_H1_L2_M0") is False

    def test_canonical_representative_mapping(self) -> None:
        """Canonical representative mapping must be correct."""
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.L0] == PPVSubBand.L1
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.L1] == PPVSubBand.L1
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.L2] == PPVSubBand.L1
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.M0] == PPVSubBand.M1
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.M1] == PPVSubBand.M1
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.M2] == PPVSubBand.M1
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.H0] == PPVSubBand.H0
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.H1] == PPVSubBand.H0


# =============================================================================
# Test 4: Fail-Closed Behavior
# =============================================================================


class TestFailClosed:
    """Test fail-closed behavior for invalid inputs."""

    def test_unknown_family_returns_render_blocked(self) -> None:
        """Unknown family (DEFAULT) must return RENDER_BLOCKED."""
        request = make_request(
            ppv_values=(4, 4, 4, 4, 4, 4, 4, 4),
            path=("UNKNOWN_LAYER",),
        )
        response = execute_phase11b2(request)

        assert response.is_blocked()
        assert response.output_text == RENDER_BLOCKED
        assert response.template_id == ""
        assert response.routing_trace.failure_reason == FailureReason.KEY_NOT_IN_REGISTRY

    def test_invalid_variant_id_raises(self) -> None:
        """Invalid variant_id format must raise ValueError."""
        with pytest.raises(ValueError):
            canonicalize_variant_id("INVALID")

        with pytest.raises(ValueError):
            canonicalize_variant_id("L0_M1_H0")  # Only 3 tokens

        with pytest.raises(ValueError):
            canonicalize_variant_id("X0_X1_X2_X3_X4_X5_X6_X7")  # Invalid tokens

    def test_failure_reason_in_trace(self) -> None:
        """Trace must include failure reason when blocked."""
        request = make_request(
            ppv_values=(4, 4, 4, 4, 4, 4, 4, 4),
            path=("NONEXISTENT_FAMILY",),
        )
        response = execute_phase11b2(request)

        assert response.routing_trace.failure_reason == FailureReason.KEY_NOT_IN_REGISTRY
        assert response.routing_trace.template_id is None


# =============================================================================
# Test 5: No Silent Collapse for Canonical Keys
# =============================================================================


class TestNoSilentCollapse:
    """Test that distinct canonical keys produce distinct template_ids."""

    def test_registry_injectivity(self) -> None:
        """Unified registry must have no template_id collisions."""
        result = validate_registry_injectivity()
        assert result.passed, f"Collisions: {result.collision_details}"

    def test_distinct_canonical_signatures_distinct_outputs(self) -> None:
        """Different canonical signatures must produce different outputs."""
        canonical_sigs = [
            "L1_L1_L1_L1_L1_L1_L1_L1",
            "M1_M1_M1_M1_M1_M1_M1_M1",
            "H0_H0_H0_H0_H0_H0_H0_H0",
            "L1_M1_H0_L1_M1_H0_L1_M1",
        ]

        outputs: Set[str] = set()
        for sig in canonical_sigs:
            # Parse signature to PPV values
            tokens = sig.split("_")
            ppv_map = {"L1": 1, "M1": 4, "H0": 6}
            ppv = tuple(ppv_map[t] for t in tokens)

            request = make_request(ppv_values=ppv, path=("THINKING",))
            response = execute_phase11b2(request)

            if not response.is_blocked():
                outputs.add(response.output_hash())

        # All outputs should be unique
        assert len(outputs) == len(canonical_sigs)

    def test_template_id_uniqueness_per_routing_key(self) -> None:
        """Each routing key must map to unique template_id."""
        registry = get_unified_registry()

        template_ids: Dict[str, Tuple[str, str, str]] = {}
        collisions = []

        for key, template in registry.items():
            tid = template.template_id
            if tid in template_ids:
                collisions.append((key, template_ids[tid], tid))
            else:
                template_ids[tid] = key

        assert len(collisions) == 0, f"Found {len(collisions)} collisions"

    def test_no_silent_collapse_trace_content_hash(self) -> None:
        """Content hash must differ for distinct canonical signatures."""
        test_inputs = [
            ((1, 1, 1, 1, 1, 1, 1, 1), ("THINKING",)),
            ((4, 4, 4, 4, 4, 4, 4, 4), ("THINKING",)),
            ((6, 6, 6, 6, 6, 6, 6, 6), ("THINKING",)),
        ]

        content_hashes: Set[str] = set()
        for ppv, path in test_inputs:
            request = make_request(ppv_values=ppv, path=path)
            response = execute_phase11b2(request)
            content_hashes.add(response.routing_trace.content_hash())

        assert len(content_hashes) == len(test_inputs)


# =============================================================================
# Test 6: Mode Identity Lock (OPEN == GOVERNED)
# =============================================================================


class TestModeIdentityLock:
    """Test that OPEN and GOVERNED produce identical outputs."""

    def test_mode_identity_same_output_text(self) -> None:
        """OPEN and GOVERNED must produce same output text."""
        ppv = (3, 4, 5, 2, 3, 4, 5, 6)
        path = ("THINKING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

        assert response_open.output_text == response_governed.output_text

    def test_mode_identity_same_template_id(self) -> None:
        """OPEN and GOVERNED must select same template."""
        ppv = (1, 4, 6, 1, 4, 6, 1, 4)
        path = ("FORMING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

        assert response_open.template_id == response_governed.template_id

    def test_mode_identity_same_output_hash(self) -> None:
        """OPEN and GOVERNED must have same output hash."""
        ppv = (0, 2, 5, 7, 1, 3, 4, 6)
        path = ("REASONING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

        assert response_open.output_hash() == response_governed.output_hash()

    def test_mode_identity_50_requests(self) -> None:
        """Mode identity must hold for 50+ different requests."""
        test_params = []
        families = ["ACTING", "TAGGING", "FORMING", "THINKING", "DIRECTING",
                   "REASONING", "PURPOSING", "META_OBSERVING", "UNIFYING", "ABSOLVING"]

        for i, family in enumerate(families):
            for j in range(5):
                ppv = tuple((i + j + k) % 8 for k in range(8))
                test_params.append(((family,), ppv))

        passed, differences = validate_mode_identity(tuple(test_params))
        assert passed, f"Mode identity failed: {differences}"

    def test_mode_only_differs_in_trace_metadata(self) -> None:
        """Trace must only differ in mode field, not content."""
        ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        path = ("THINKING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

        trace_open = response_open.routing_trace
        trace_governed = response_governed.routing_trace

        # Content fields must match
        assert trace_open.family_id == trace_governed.family_id
        assert trace_open.slot_plan_id == trace_governed.slot_plan_id
        assert trace_open.raw_signature == trace_governed.raw_signature
        assert trace_open.canonical_signature == trace_governed.canonical_signature
        assert trace_open.canonicalization_applied == trace_governed.canonicalization_applied
        assert trace_open.template_id == trace_governed.template_id
        assert trace_open.output_hash == trace_governed.output_hash
        assert trace_open.failure_reason == trace_governed.failure_reason

        # Only mode differs
        assert trace_open.mode == RenderMode.OPEN
        assert trace_governed.mode == RenderMode.GOVERNED

        # Content hash must be identical
        assert trace_open.content_hash() == trace_governed.content_hash()

    def test_mode_identity_with_canonicalization(self) -> None:
        """Mode identity must hold even when canonicalization is applied."""
        # Non-canonical input
        ppv = (0, 0, 0, 0, 0, 0, 0, 0)
        path = ("THINKING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

        # Both should apply canonicalization
        assert response_open.routing_trace.canonicalization_applied is True
        assert response_governed.routing_trace.canonicalization_applied is True

        # Outputs must be identical
        assert response_open.output_text == response_governed.output_text


# =============================================================================
# Test 7: Registry Completeness Validation
# =============================================================================


class TestRegistryCompleteness:
    """Test registry completeness and validation."""

    def test_registry_completeness_passed(self) -> None:
        """Registry must contain all expected combinations."""
        result = validate_registry_completeness()
        assert result.passed, (
            f"Missing: {result.missing_keys}, Extra: {result.extra_keys}"
        )

    def test_registry_expected_count(self) -> None:
        """Registry must have 10 * 4 * 6561 = 262,440 entries."""
        result = validate_registry_completeness()
        expected = 10 * 4 * 6561
        assert result.expected_count == expected
        assert result.actual_count == expected

    def test_accepted_families_count(self) -> None:
        """Must have 10 accepted families."""
        assert len(ACCEPTED_FAMILIES) == 10

    def test_accepted_slot_plans_count(self) -> None:
        """Must have 4 accepted slot plans."""
        assert len(ACCEPTED_SLOT_PLANS) == 4

    def test_all_families_in_accepted(self) -> None:
        """All non-DEFAULT families must be in accepted set."""
        all_families = {f for f in OntologicalFamily if f != OntologicalFamily.DEFAULT}
        assert all_families == set(ACCEPTED_FAMILIES)


# =============================================================================
# Test 8: Canonicalization Coverage Validation
# =============================================================================


class TestCanonicalizationCoverage:
    """Test canonicalization coverage for raw signatures."""

    def test_all_subband_combinations_canonicalize(self) -> None:
        """All 8^8 subband combinations must canonicalize to registry."""
        # Sample a subset of combinations (full 8^8 = 16M is too large)
        sample_signatures = []

        # All same
        for i in range(8):
            sb = list(PPVSubBand)[i]
            sample_signatures.append("_".join([sb.value] * 8))

        # Gradients
        all_sbs = [sb.value for sb in PPVSubBand]
        sample_signatures.append("_".join(all_sbs))
        sample_signatures.append("_".join(reversed(all_sbs)))

        result = validate_canonicalization_coverage(tuple(sample_signatures))
        assert result.passed, f"Failed: {result.failed_signatures}"

    def test_edge_case_signatures_canonicalize(self) -> None:
        """Edge case signatures must canonicalize correctly."""
        edge_cases = [
            "L0_L0_L0_L0_L0_L0_L0_L0",
            "L2_L2_L2_L2_L2_L2_L2_L2",
            "M0_M0_M0_M0_M0_M0_M0_M0",
            "M2_M2_M2_M2_M2_M2_M2_M2",
            "H1_H1_H1_H1_H1_H1_H1_H1",
        ]

        for sig in edge_cases:
            result = canonicalize_variant_id(sig)
            assert is_canonical_signature(result.canonical_signature), (
                f"{sig} -> {result.canonical_signature} is not canonical"
            )


# =============================================================================
# Test 9: Request/Response Contract
# =============================================================================


class TestRequestResponseContract:
    """Test Phase11B2Request and Phase11B2Response contracts."""

    def test_request_frozen(self) -> None:
        """Request must be frozen (immutable)."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        with pytest.raises(AttributeError):
            request.artifact_id = "modified"  # type: ignore

    def test_response_frozen(self) -> None:
        """Response must be frozen (immutable)."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        response = execute_phase11b2(request)
        with pytest.raises(AttributeError):
            response.output_text = "modified"  # type: ignore

    def test_request_validation(self) -> None:
        """Request validation must work correctly."""
        # Valid request
        request = make_request(ppv_values=(0, 1, 2, 3, 4, 5, 6, 7))
        assert request.artifact_id == "test-artifact"

        # Invalid PPV count
        with pytest.raises(ValueError):
            Phase11B2Request(
                artifact_id="test",
                artifact_hash=make_artifact_hash(),
                ontological_path=("THINKING",),
                ppv_values=(1, 2, 3),
                render_mode=RenderMode.GOVERNED,
            )

        # Invalid PPV value
        with pytest.raises(ValueError):
            Phase11B2Request(
                artifact_id="test",
                artifact_hash=make_artifact_hash(),
                ontological_path=("THINKING",),
                ppv_values=(1, 2, 3, 4, 5, 6, 7, 8),
                render_mode=RenderMode.GOVERNED,
            )

    def test_request_hash_mode_independent(self) -> None:
        """request_hash() must be mode-independent for content."""
        ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        path = ("THINKING",)

        request_open = Phase11B2Request(
            artifact_id="test",
            artifact_hash=make_artifact_hash("fixed"),
            ontological_path=path,
            ppv_values=ppv,
            render_mode=RenderMode.OPEN,
        )

        request_governed = Phase11B2Request(
            artifact_id="test",
            artifact_hash=make_artifact_hash("fixed"),
            ontological_path=path,
            ppv_values=ppv,
            render_mode=RenderMode.GOVERNED,
        )

        # request_hash excludes mode
        assert request_open.request_hash() == request_governed.request_hash()

        # full_request_hash includes mode
        assert request_open.full_request_hash() != request_governed.full_request_hash()


# =============================================================================
# Test 10: Trace Contract
# =============================================================================


class TestTraceContract:
    """Test Phase11B2RoutingTrace contract."""

    def test_trace_fields_complete(self) -> None:
        """Trace must have all required fields."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        response = execute_phase11b2(request)
        trace = response.routing_trace

        assert trace.family_id is not None
        assert trace.slot_plan_id is not None
        assert trace.raw_signature is not None
        assert trace.canonical_signature is not None
        assert isinstance(trace.canonicalization_applied, bool)
        assert trace.output_hash is not None
        assert isinstance(trace.failure_reason, FailureReason)
        assert isinstance(trace.mode, RenderMode)

    def test_trace_hash_deterministic(self) -> None:
        """Trace hash must be deterministic."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))

        hashes: Set[str] = set()
        for _ in range(100):
            response = execute_phase11b2(request)
            hashes.add(response.routing_trace.trace_hash())

        assert len(hashes) == 1

    def test_trace_content_hash_excludes_mode(self) -> None:
        """Content hash must exclude mode for identity lock."""
        ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        path = ("THINKING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b2(request_open)
        response_governed = execute_phase11b2(request_governed)

        assert (response_open.routing_trace.content_hash() ==
                response_governed.routing_trace.content_hash())


# =============================================================================
# Test 11: Unified Registry
# =============================================================================


class TestUnifiedRegistry:
    """Test unified registry structure."""

    def test_unified_registry_populated(self) -> None:
        """Unified registry must be populated."""
        registry = get_unified_registry()
        assert len(registry) > 0

    def test_unified_registry_key_format(self) -> None:
        """Registry keys must be (family, variant_id, slot_plan) tuples."""
        registry = get_unified_registry()
        for key in registry.keys():
            assert len(key) == 3
            assert isinstance(key[0], str)  # family
            assert isinstance(key[1], str)  # variant_id
            assert isinstance(key[2], str)  # slot_plan

    def test_lookup_unified_template(self) -> None:
        """lookup_unified_template must return correct template."""
        template = lookup_unified_template(
            OntologicalFamily.THINKING,
            "L1_L1_L1_L1_L1_L1_L1_L1",
            SlotPlan.STANDARD,
        )
        assert template is not None
        assert template.routing_key.family == OntologicalFamily.THINKING

    def test_lookup_missing_returns_none(self) -> None:
        """Lookup for missing key must return None."""
        template = lookup_unified_template(
            OntologicalFamily.DEFAULT,  # Not in ACCEPTED_FAMILIES
            "L1_L1_L1_L1_L1_L1_L1_L1",
            SlotPlan.STANDARD,
        )
        assert template is None


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
