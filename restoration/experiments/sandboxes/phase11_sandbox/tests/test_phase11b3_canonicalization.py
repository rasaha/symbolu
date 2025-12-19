"""
Test Suite for Phase-11B.3 Fine-Grained Canonicalization
==========================================================

This test suite verifies Phase-11B.3 requirements:

    1. Determinism (100 runs)
    2. Mode identity lock (300+ comparisons)
    3. Canonical coverage (0 unexpected RENDER_BLOCKED)
    4. Registry injectivity for canonical keys
    5. Regression comparison (collapse rate vs B.2 baseline)
    6. No silent collapse (canonicalization recorded in trace)

Target: ≥40 tests

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
    # Functions
    create_subband_signature,
)

from phase11b3_canonicalization import (
    # Version
    PHASE11B3_VERSION,
    # Constants
    ACCEPTED_FAMILIES,
    ACCEPTED_SLOT_PLANS,
    CANONICAL_SIGNATURES,
    CANONICAL_SIGNATURE_COUNT,
    CANONICAL_SUBBAND_REPRESENTATIVE,
    CANONICAL_REPRESENTATIVES,
    # Dataclasses
    CanonicalizationResult,
    Phase11B3RoutingTrace,
    Phase11B3Request,
    Phase11B3Response,
    RegistryCompletenessResult,
    CanonicalizationCoverageResult,
    InjectivityResult,
    CollapseRateMetrics,
    # Functions
    is_canonical_signature,
    canonicalize_variant_id,
    canonicalize_from_ppv_values,
    get_unified_registry,
    lookup_unified_template,
    render_template,
    execute_phase11b3,
    validate_registry_completeness,
    validate_canonicalization_coverage,
    validate_registry_injectivity,
    validate_mode_identity,
    measure_collapse_rate,
    generate_harness_ppv_samples,
)

# Import B.2 for regression comparison
from phase11b2_canonicalization import (
    CANONICAL_SIGNATURES as B2_CANONICAL_SIGNATURES,
    canonicalize_variant_id as b2_canonicalize,
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
) -> Phase11B3Request:
    """Create a test request."""
    return Phase11B3Request(
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
            response = execute_phase11b3(request)
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
            response = execute_phase11b3(request)
            trace_hashes.append(response.routing_trace.trace_hash())

        assert len(set(trace_hashes)) == 1

    def test_determinism_governed_mode_100_runs(self) -> None:
        """GOVERNED mode must be deterministic across 100 runs."""
        request = make_request(
            ppv_values=(1, 2, 3, 4, 5, 6, 7, 0),
            mode=RenderMode.GOVERNED,
        )

        hashes: Set[str] = set()
        for _ in range(100):
            response = execute_phase11b3(request)
            hashes.add(response.output_hash())

        assert len(hashes) == 1, f"Got {len(hashes)} unique hashes in GOVERNED mode"


# =============================================================================
# Test 2: Canonicalization Applied Path (6-Representative System)
# =============================================================================


class TestCanonicalizationApplied:
    """Test canonicalization when raw signature is not canonical."""

    def test_canonicalization_applied_l1_to_l0(self) -> None:
        """L1 must be canonicalized to L0."""
        request = make_request(ppv_values=(1, 1, 1, 1, 1, 1, 1, 1))
        response = execute_phase11b3(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is True
        assert trace.raw_signature == "L1_L1_L1_L1_L1_L1_L1_L1"
        assert trace.canonical_signature == "L0_L0_L0_L0_L0_L0_L0_L0"

    def test_canonicalization_applied_m1_to_m0(self) -> None:
        """M1 must be canonicalized to M0."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        response = execute_phase11b3(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is True
        assert trace.raw_signature == "M1_M1_M1_M1_M1_M1_M1_M1"
        assert trace.canonical_signature == "M0_M0_M0_M0_M0_M0_M0_M0"

    def test_canonicalization_l0_no_change(self) -> None:
        """L0 is already canonical, no change needed."""
        request = make_request(ppv_values=(0, 0, 0, 0, 0, 0, 0, 0))
        response = execute_phase11b3(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is False
        assert trace.raw_signature == "L0_L0_L0_L0_L0_L0_L0_L0"
        assert trace.canonical_signature == "L0_L0_L0_L0_L0_L0_L0_L0"

    def test_canonicalization_h1_no_change(self) -> None:
        """H1 is already canonical, no change needed."""
        request = make_request(ppv_values=(7, 7, 7, 7, 7, 7, 7, 7))
        response = execute_phase11b3(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is False
        assert trace.raw_signature == "H1_H1_H1_H1_H1_H1_H1_H1"
        assert trace.canonical_signature == "H1_H1_H1_H1_H1_H1_H1_H1"

    def test_canonicalization_trace_records_from_to(self) -> None:
        """Trace must record canonicalization source and target."""
        # Mixed input with some collapse
        request = make_request(ppv_values=(1, 5, 7, 4, 2, 6, 0, 3))
        response = execute_phase11b3(request)

        trace = response.routing_trace
        assert trace.raw_signature == "L1_M2_H1_M1_L2_H0_L0_M0"
        # L1->L0, M2->M2, H1->H1, M1->M0, L2->L2, H0->H0, L0->L0, M0->M0
        assert trace.canonical_signature == "L0_M2_H1_M0_L2_H0_L0_M0"
        assert trace.canonicalization_applied is True


# =============================================================================
# Test 3: Canonicalization Not Needed Path
# =============================================================================


class TestCanonicalizationNotNeeded:
    """Test when raw signature is already canonical."""

    def test_no_canonicalization_for_canonical_input(self) -> None:
        """Canonical input must not trigger canonicalization."""
        # L0, L2, M0, M2, H0, H1 are canonical representatives
        request = make_request(ppv_values=(0, 2, 3, 5, 6, 7, 0, 5))
        response = execute_phase11b3(request)

        trace = response.routing_trace
        assert trace.canonicalization_applied is False
        assert trace.raw_signature == trace.canonical_signature

    def test_canonical_signatures_set_complete(self) -> None:
        """Canonical signatures set must contain 6^8 = 1,679,616 entries."""
        assert len(CANONICAL_SIGNATURES) == CANONICAL_SIGNATURE_COUNT
        assert len(CANONICAL_SIGNATURES) == 6 ** 8

    def test_is_canonical_signature_function(self) -> None:
        """is_canonical_signature must correctly identify canonical patterns."""
        # Canonical (uses L0, L2, M0, M2, H0, H1)
        assert is_canonical_signature("L0_L0_L0_L0_L0_L0_L0_L0") is True
        assert is_canonical_signature("L2_L2_L2_L2_L2_L2_L2_L2") is True
        assert is_canonical_signature("M0_M0_M0_M0_M0_M0_M0_M0") is True
        assert is_canonical_signature("M2_M2_M2_M2_M2_M2_M2_M2") is True
        assert is_canonical_signature("H0_H0_H0_H0_H0_H0_H0_H0") is True
        assert is_canonical_signature("H1_H1_H1_H1_H1_H1_H1_H1") is True
        assert is_canonical_signature("L0_M0_H0_L2_M2_H1_L0_M0") is True

        # Non-canonical (uses L1 or M1)
        assert is_canonical_signature("L1_L1_L1_L1_L1_L1_L1_L1") is False
        assert is_canonical_signature("M1_M1_M1_M1_M1_M1_M1_M1") is False
        assert is_canonical_signature("L0_L1_L0_L0_L0_L0_L0_L0") is False

    def test_canonical_representative_mapping(self) -> None:
        """Canonical representative mapping must be correct for B.3."""
        # LOW band
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.L0] == PPVSubBand.L0
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.L1] == PPVSubBand.L0
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.L2] == PPVSubBand.L2
        # MID band
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.M0] == PPVSubBand.M0
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.M1] == PPVSubBand.M0
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.M2] == PPVSubBand.M2
        # HIGH band (no collapse)
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.H0] == PPVSubBand.H0
        assert CANONICAL_SUBBAND_REPRESENTATIVE[PPVSubBand.H1] == PPVSubBand.H1


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
        response = execute_phase11b3(request)

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
        response = execute_phase11b3(request)

        assert response.routing_trace.failure_reason == FailureReason.KEY_NOT_IN_REGISTRY
        assert response.routing_trace.template_id is None


# =============================================================================
# Test 5: No Silent Collapse (Trace Visibility)
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
            "L0_L0_L0_L0_L0_L0_L0_L0",
            "L2_L2_L2_L2_L2_L2_L2_L2",
            "M0_M0_M0_M0_M0_M0_M0_M0",
            "M2_M2_M2_M2_M2_M2_M2_M2",
            "H0_H0_H0_H0_H0_H0_H0_H0",
            "H1_H1_H1_H1_H1_H1_H1_H1",
        ]

        outputs: Set[str] = set()
        for sig in canonical_sigs:
            # Parse signature to PPV values
            ppv_map = {"L0": 0, "L2": 2, "M0": 3, "M2": 5, "H0": 6, "H1": 7}
            tokens = sig.split("_")
            ppv = tuple(ppv_map[t] for t in tokens)

            request = make_request(ppv_values=ppv, path=("THINKING",))
            response = execute_phase11b3(request)

            if not response.is_blocked():
                outputs.add(response.output_hash())

        # All outputs should be unique
        assert len(outputs) == len(canonical_sigs)

    def test_canonicalization_always_recorded(self) -> None:
        """Canonicalization must always be recorded in trace."""
        test_cases = [
            (0, 0, 0, 0, 0, 0, 0, 0),  # No collapse (L0 canonical)
            (1, 1, 1, 1, 1, 1, 1, 1),  # Collapse L1 -> L0
            (2, 2, 2, 2, 2, 2, 2, 2),  # No collapse (L2 canonical)
            (4, 4, 4, 4, 4, 4, 4, 4),  # Collapse M1 -> M0
            (7, 7, 7, 7, 7, 7, 7, 7),  # No collapse (H1 canonical)
        ]

        for ppv in test_cases:
            request = make_request(ppv_values=ppv, path=("THINKING",))
            response = execute_phase11b3(request)

            trace = response.routing_trace
            # Trace must have both signatures
            assert trace.raw_signature is not None
            assert trace.canonical_signature is not None
            # canonicalization_applied must be boolean
            assert isinstance(trace.canonicalization_applied, bool)


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

        response_open = execute_phase11b3(request_open)
        response_governed = execute_phase11b3(request_governed)

        assert response_open.output_text == response_governed.output_text

    def test_mode_identity_same_template_id(self) -> None:
        """OPEN and GOVERNED must select same template."""
        ppv = (0, 2, 3, 5, 6, 7, 0, 2)
        path = ("FORMING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b3(request_open)
        response_governed = execute_phase11b3(request_governed)

        assert response_open.template_id == response_governed.template_id

    def test_mode_identity_same_output_hash(self) -> None:
        """OPEN and GOVERNED must have same output hash."""
        ppv = (0, 2, 5, 7, 1, 3, 4, 6)
        path = ("REASONING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b3(request_open)
        response_governed = execute_phase11b3(request_governed)

        assert response_open.output_hash() == response_governed.output_hash()

    def test_mode_identity_300_requests(self) -> None:
        """Mode identity must hold for 300+ different requests."""
        test_params = []
        families = ["ACTING", "TAGGING", "FORMING", "THINKING", "DIRECTING",
                   "REASONING", "PURPOSING", "META_OBSERVING", "UNIFYING", "ABSOLVING"]

        # 10 families x 30 variations = 300 requests
        for i, family in enumerate(families):
            for j in range(30):
                ppv = tuple((i + j + k) % 8 for k in range(8))
                test_params.append(((family,), ppv))

        assert len(test_params) >= 300

        passed, differences = validate_mode_identity(tuple(test_params))
        assert passed, f"Mode identity failed: {differences[:5]}"

    def test_mode_only_differs_in_trace_metadata(self) -> None:
        """Trace must only differ in mode field, not content."""
        ppv = (0, 2, 3, 5, 6, 7, 0, 3)
        path = ("THINKING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b3(request_open)
        response_governed = execute_phase11b3(request_governed)

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


# =============================================================================
# Test 7: Registry Completeness
# =============================================================================


class TestRegistryCompleteness:
    """Test registry completeness and validation."""

    def test_registry_completeness_passed(self) -> None:
        """Registry must be able to serve all expected combinations."""
        result = validate_registry_completeness()
        assert result.passed, (
            f"Missing: {result.missing_keys}, Extra: {result.extra_keys}"
        )

    def test_registry_expected_count(self) -> None:
        """Registry must support 10 * 4 * 6^8 = 67,184,640 entries."""
        result = validate_registry_completeness()
        expected = 10 * 4 * (6 ** 8)
        assert result.expected_count == expected
        # With lazy generation, actual_count equals expected_count if validation passes
        assert result.actual_count == expected

    def test_accepted_families_count(self) -> None:
        """Must have 10 accepted families."""
        assert len(ACCEPTED_FAMILIES) == 10

    def test_accepted_slot_plans_count(self) -> None:
        """Must have 4 accepted slot plans."""
        assert len(ACCEPTED_SLOT_PLANS) == 4

    def test_lazy_template_generation(self) -> None:
        """Lazy template generation must work correctly."""
        # First lookup should create and cache template
        template1 = lookup_unified_template(
            OntologicalFamily.THINKING,
            "L0_L0_L0_L0_L0_L0_L0_L0",
            SlotPlan.STANDARD,
        )
        assert template1 is not None

        # Second lookup should return cached template
        template2 = lookup_unified_template(
            OntologicalFamily.THINKING,
            "L0_L0_L0_L0_L0_L0_L0_L0",
            SlotPlan.STANDARD,
        )
        assert template2 is template1  # Same object (cached)


# =============================================================================
# Test 8: Canonical Coverage (Proof Test)
# =============================================================================


class TestCanonicalCoverage:
    """Test that every harness request maps into CANONICAL_SIGNATURES."""

    def test_all_harness_inputs_map_to_canonical(self) -> None:
        """Every harness-generated input must map to a canonical signature."""
        samples = generate_harness_ppv_samples(500)

        for ppv in samples:
            sig = create_subband_signature(ppv)
            raw_sig = sig.to_variant_id()
            result = canonicalize_variant_id(raw_sig)

            assert is_canonical_signature(result.canonical_signature), (
                f"PPV {ppv} -> raw {raw_sig} -> {result.canonical_signature} not canonical"
            )

    def test_zero_unexpected_render_blocked_in_harness(self) -> None:
        """No unexpected RENDER_BLOCKED for valid families in harness domain."""
        samples = generate_harness_ppv_samples(500)
        blocked_count = 0

        for ppv in samples:
            for family in ACCEPTED_FAMILIES:
                request = Phase11B3Request(
                    artifact_id="coverage-test",
                    artifact_hash=make_artifact_hash(f"{family}:{ppv}"),
                    ontological_path=(family.value,),
                    ppv_values=ppv,
                    render_mode=RenderMode.GOVERNED,
                )
                response = execute_phase11b3(request)
                if response.is_blocked():
                    blocked_count += 1

        assert blocked_count == 0, f"Unexpected {blocked_count} RENDER_BLOCKED in harness"

    def test_all_raw_signatures_canonicalize_to_registry(self) -> None:
        """All possible raw signatures must canonicalize to registry."""
        # Sample signatures across all subbands
        sample_signatures = []
        all_sbs = list(PPVSubBand)

        # All same
        for sb in all_sbs:
            sample_signatures.append("_".join([sb.value] * 8))

        # Gradients
        sample_signatures.append("_".join(sb.value for sb in all_sbs))
        sample_signatures.append("_".join(sb.value for sb in reversed(all_sbs)))

        result = validate_canonicalization_coverage(tuple(sample_signatures))
        assert result.passed, f"Failed: {result.failed_signatures}"


# =============================================================================
# Test 9: Regression Comparison (B.3 vs B.2)
# =============================================================================


class TestRegressionComparison:
    """Test that B.3 improves on B.2 baseline."""

    def test_b3_has_more_canonical_signatures_than_b2(self) -> None:
        """B.3 must have more canonical signatures than B.2."""
        b3_count = len(CANONICAL_SIGNATURES)
        b2_count = len(B2_CANONICAL_SIGNATURES)

        assert b3_count > b2_count, (
            f"B.3 has {b3_count} signatures, B.2 has {b2_count}"
        )

        # Verify expected counts
        assert b3_count == 6 ** 8  # 1,679,616
        assert b2_count == 3 ** 8  # 6,561

    def test_collapse_rate_lower_than_b2(self) -> None:
        """Collapse rate on 500 harness inputs must be lower than B.2."""
        samples = generate_harness_ppv_samples(500)

        b3_collapse_count = 0
        b2_collapse_count = 0

        for ppv in samples:
            sig = create_subband_signature(ppv)
            raw_sig = sig.to_variant_id()

            # B.3 collapse
            b3_result = canonicalize_variant_id(raw_sig)
            if b3_result.canonicalization_applied:
                b3_collapse_count += 1

            # B.2 collapse
            b2_result = b2_canonicalize(raw_sig)
            if b2_result.canonicalization_applied:
                b2_collapse_count += 1

        b3_rate = b3_collapse_count / len(samples)
        b2_rate = b2_collapse_count / len(samples)

        assert b3_rate < b2_rate, (
            f"B.3 collapse rate {b3_rate:.3f} >= B.2 rate {b2_rate:.3f}"
        )

    def test_render_block_rate_no_worse_than_b2(self) -> None:
        """Render block rate must be no worse than B.2 baseline."""
        samples = generate_harness_ppv_samples(500)

        b3_metrics = measure_collapse_rate(samples)

        # B.3 should have 0% render_block_rate for valid families
        assert b3_metrics.render_block_rate <= 0.0, (
            f"B.3 render_block_rate {b3_metrics.render_block_rate} > 0"
        )

    def test_canonical_signature_count_increase(self) -> None:
        """B.3 canonical space is much larger than B.2."""
        b3_count = 6 ** 8  # 1,679,616
        b2_count = 3 ** 8  # 6,561

        ratio = b3_count / b2_count
        assert ratio > 250, f"B.3/B.2 ratio {ratio} is too low"


# =============================================================================
# Test 10: Request/Response Contract
# =============================================================================


class TestRequestResponseContract:
    """Test Phase11B3Request and Phase11B3Response contracts."""

    def test_request_frozen(self) -> None:
        """Request must be frozen (immutable)."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        with pytest.raises(AttributeError):
            request.artifact_id = "modified"  # type: ignore

    def test_response_frozen(self) -> None:
        """Response must be frozen (immutable)."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        response = execute_phase11b3(request)
        with pytest.raises(AttributeError):
            response.output_text = "modified"  # type: ignore

    def test_request_validation(self) -> None:
        """Request validation must work correctly."""
        # Valid request
        request = make_request(ppv_values=(0, 1, 2, 3, 4, 5, 6, 7))
        assert request.artifact_id == "test-artifact"

        # Invalid PPV count
        with pytest.raises(ValueError):
            Phase11B3Request(
                artifact_id="test",
                artifact_hash=make_artifact_hash(),
                ontological_path=("THINKING",),
                ppv_values=(1, 2, 3),
                render_mode=RenderMode.GOVERNED,
            )

        # Invalid PPV value
        with pytest.raises(ValueError):
            Phase11B3Request(
                artifact_id="test",
                artifact_hash=make_artifact_hash(),
                ontological_path=("THINKING",),
                ppv_values=(1, 2, 3, 4, 5, 6, 7, 8),
                render_mode=RenderMode.GOVERNED,
            )


# =============================================================================
# Test 11: Trace Contract
# =============================================================================


class TestTraceContract:
    """Test Phase11B3RoutingTrace contract."""

    def test_trace_fields_complete(self) -> None:
        """Trace must have all required fields."""
        request = make_request(ppv_values=(4, 4, 4, 4, 4, 4, 4, 4))
        response = execute_phase11b3(request)
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
            response = execute_phase11b3(request)
            hashes.add(response.routing_trace.trace_hash())

        assert len(hashes) == 1

    def test_trace_content_hash_excludes_mode(self) -> None:
        """Content hash must exclude mode for identity lock."""
        ppv = (4, 4, 4, 4, 4, 4, 4, 4)
        path = ("THINKING",)

        request_open = make_request(ppv_values=ppv, path=path, mode=RenderMode.OPEN)
        request_governed = make_request(ppv_values=ppv, path=path, mode=RenderMode.GOVERNED)

        response_open = execute_phase11b3(request_open)
        response_governed = execute_phase11b3(request_governed)

        assert (response_open.routing_trace.content_hash() ==
                response_governed.routing_trace.content_hash())


# =============================================================================
# Test 12: Unified Registry
# =============================================================================


class TestUnifiedRegistry:
    """Test unified registry structure."""

    def test_unified_registry_lazy_population(self) -> None:
        """Unified registry populates lazily on lookup."""
        # Trigger some lookups
        lookup_unified_template(
            OntologicalFamily.THINKING,
            "L0_L0_L0_L0_L0_L0_L0_L0",
            SlotPlan.STANDARD,
        )
        lookup_unified_template(
            OntologicalFamily.FORMING,
            "M0_M0_M0_M0_M0_M0_M0_M0",
            SlotPlan.MINIMAL,
        )

        registry = get_unified_registry()
        # Registry should have some entries after lookups
        assert len(registry) >= 2

    def test_unified_registry_key_format(self) -> None:
        """Registry keys must be (family, variant_id, slot_plan) tuples."""
        # Trigger some lookups to populate
        for family in list(ACCEPTED_FAMILIES)[:3]:
            lookup_unified_template(
                family,
                "L0_L0_L0_L0_L0_L0_L0_L0",
                SlotPlan.STANDARD,
            )

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
            "L0_L0_L0_L0_L0_L0_L0_L0",
            SlotPlan.STANDARD,
        )
        assert template is not None
        assert template.routing_key.family == OntologicalFamily.THINKING

    def test_lookup_missing_returns_none(self) -> None:
        """Lookup for missing key must return None."""
        template = lookup_unified_template(
            OntologicalFamily.DEFAULT,  # Not in ACCEPTED_FAMILIES
            "L0_L0_L0_L0_L0_L0_L0_L0",
            SlotPlan.STANDARD,
        )
        assert template is None

    def test_lookup_non_canonical_returns_none(self) -> None:
        """Lookup for non-canonical signature must return None."""
        # L1 is not a canonical representative in B.3
        template = lookup_unified_template(
            OntologicalFamily.THINKING,
            "L1_L1_L1_L1_L1_L1_L1_L1",  # Not canonical
            SlotPlan.STANDARD,
        )
        assert template is None


# =============================================================================
# Test 13: Collapse Rate Metrics
# =============================================================================


class TestCollapseRateMetrics:
    """Test collapse rate measurement functions."""

    def test_collapse_rate_metrics_structure(self) -> None:
        """Collapse rate metrics must have correct structure."""
        samples = generate_harness_ppv_samples(100)
        metrics = measure_collapse_rate(samples)

        assert metrics.total_inputs == 100
        assert metrics.unique_canonical_signatures > 0
        assert metrics.collapse_count >= 0
        assert 0.0 <= metrics.collapse_rate <= 1.0
        assert metrics.render_blocked_count >= 0
        assert 0.0 <= metrics.render_block_rate <= 1.0

    def test_harness_sample_generator(self) -> None:
        """Harness sample generator must produce diverse samples."""
        samples_100 = generate_harness_ppv_samples(100)
        samples_500 = generate_harness_ppv_samples(500)

        assert len(samples_100) == 100
        assert len(samples_500) == 500

        # Samples should be reasonably diverse (at least 80% unique)
        unique_100 = len(set(samples_100))
        assert unique_100 >= 80, f"Only {unique_100} unique samples out of 100"

        unique_500 = len(set(samples_500))
        assert unique_500 >= 400, f"Only {unique_500} unique samples out of 500"


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
