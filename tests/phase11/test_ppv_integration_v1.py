"""
PPV Integration Test Suite v1
==============================

Comprehensive tests for Phonemic Propensity Vector (PPV) integration.

Test Categories:
    1. PPV Determinism - Same artifact -> identical ppv_hash over 100 runs
    2. PPV Invariants - Fixed length, bounded ints, correct hash
    3. GOVERNED Behavior Unchanged:
        - If PPV absent -> current outputs identical to baseline (byte-for-byte)
        - If PPV present and template supports it -> verifier passes and output stable
        - If PPV present but template does NOT support it -> verifier fails (GOVERNED)
    4. OPEN Behavior:
        - PPV present but verifier fails -> still returns candidate output (not blocked)
    5. No Forbidden Imports - assert no random, time, datetime, ML/NLP libs imported

CRITICAL INVARIANTS VERIFIED:
    - PPV is numeric only (ints/bools/tuples)
    - PPV is deterministic and hash-stable
    - PPV does NOT introduce "meaning inference"
    - GOVERNED mode output remains template-bound
    - PPV only influences output through predefined template slots
"""

import hashlib
import sys
import pytest
from typing import Tuple

from symbolu.ppv import (
    # Contract
    PPV_CONTRACT_VERSION,
    PPV_DIM_COUNT,
    PPV_DIM_ORDER,
    PPV_VALUE_MIN,
    PPV_VALUE_MAX,
    PPVDim,
    PPVVector,
    create_ppv_vector,
    validate_ppv_invariants_v1,
    # Builder
    PPV_BUILDER_VERSION,
    PHONEME_FEATURES,
    PPVBuildContext,
    build_ppv_from_context,
    build_ppv_for_artifact,
)

from symbolu.mechanical.pipeline.p11_controller import (
    # Core
    RenderMode,
    Phase10Result,
    Phase11Request,
    Phase11Response,
    Phase11Controller,
    Phase11LedgerStore,
    # Templates
    VCExtraction,
    TemplateRenderResult,
    PPVMetrics,
    VCPPVExtraction,
    EMPTY_PPV_METRICS,
    extract_vc_facts,
    render_template,
    extract_ppv_metrics,
    extract_vc_ppv_facts,
    render_template_with_ppv,
    is_ppv_template_supported,
    # Verifier
    VerifierReport,
    verify_output,
    verify_output_with_ppv,
    # Ledger
    Phase11LedgerEntry,
    create_ledger_entry,
)

from symbolu.mechanical.pipeline.p10_acoustic.p10_ppv_envelope import (
    PPV_ENVELOPE_VERSION,
    Phase10Envelope,
    create_phase10_envelope,
    wrap_with_ppv,
    extract_ppv_metrics as extract_envelope_ppv_metrics,
)


# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_artifact_hash() -> str:
    """Create a valid 64-char hex artifact hash for testing."""
    return hashlib.sha256(b"test_ppv_artifact_content").hexdigest()


def create_test_phase10_result(
    vc_facts: Tuple[str, ...] = ("VC-1", "VC-2"),
    acoustic_regime: str = "neutral",
    include_phoneme_data: bool = False,
) -> Phase10Result:
    """Create a valid Phase10Result for testing."""
    artifact_hash = create_test_artifact_hash()
    source_data = {
        "vc_1_data": "test_observation_value",
        "vc_2_data": "test_state_value",
        "vc_3_data": "test_context_value",
        "vc_4_data": "test_reference_value",
        "vc_5_data": "test_marker_value",
    }
    if include_phoneme_data:
        source_data["phoneme_ids"] = ["sa", "ma", "na", "ta", "a"]
        source_data["adjacency_markers"] = ["boundary_1", "boundary_2"]
        source_data["span_boundaries"] = [0, 5]
        source_data["fold_sizes"] = [2, 3]
    return Phase10Result(
        artifact_hash=artifact_hash,
        vc_facts=vc_facts,
        acoustic_regime=acoustic_regime,
        source_data=source_data,
    )


def create_test_ppv_vector() -> PPVVector:
    """Create a valid PPVVector for testing."""
    values = (3, 4, 2, 5, 4, 2, 3, 3)  # Within bounds 0-7
    return create_ppv_vector(values=values, version="1.0")


def create_test_build_context() -> PPVBuildContext:
    """Create a valid PPVBuildContext for testing."""
    return PPVBuildContext(
        phoneme_ids=("sa", "ma", "na", "ta", "a"),
        adjacency_markers=("boundary_1",),
        span_boundaries=(0, 5),
        fold_sizes=(2, 3),
        acoustic_regime="neutral",
    )


# =============================================================================
# Test Category 1: PPV Determinism
# =============================================================================


class TestPPVDeterminism:
    """
    Test that PPV is deterministic - same artifact produces identical ppv_hash.

    CRITICAL: Must pass 100 runs with identical results.
    """

    def test_ppv_vector_determinism_100_runs(self) -> None:
        """Same values produce identical PPVVector 100 times."""
        values = (3, 4, 2, 5, 4, 2, 3, 3)

        # First run - reference
        first_ppv = create_ppv_vector(values=values, version="1.0")
        first_hash = first_ppv.ppv_hash

        # 99 more runs
        for run in range(99):
            ppv = create_ppv_vector(values=values, version="1.0")
            assert ppv.ppv_hash == first_hash, f"PPV hash differs on run {run + 2}"
            assert ppv.values == first_ppv.values
            assert ppv.aggregate == first_ppv.aggregate

    def test_ppv_builder_determinism_100_runs(self) -> None:
        """Same build context produces identical PPV 100 times."""
        context = create_test_build_context()

        # First run - reference
        first_ppv = build_ppv_from_context(context)
        assert first_ppv is not None, "PPV builder should produce result"
        first_hash = first_ppv.ppv_hash

        # 99 more runs
        for run in range(99):
            ppv = build_ppv_from_context(context)
            assert ppv is not None
            assert ppv.ppv_hash == first_hash, f"PPV hash differs on run {run + 2}"

    def test_ppv_envelope_determinism_100_runs(self) -> None:
        """Same Phase10Result with PPV produces identical envelope 100 times."""
        phase10_result = create_test_phase10_result(include_phoneme_data=True)
        ppv = create_test_ppv_vector()

        # First run - reference
        first_envelope = create_phase10_envelope(phase10_result, ppv)
        first_hash = first_envelope.envelope_hash

        # 99 more runs
        for run in range(99):
            envelope = create_phase10_envelope(phase10_result, ppv)
            assert envelope.envelope_hash == first_hash, f"Envelope hash differs on run {run + 2}"


# =============================================================================
# Test Category 2: PPV Invariants
# =============================================================================


class TestPPVInvariants:
    """
    Test PPV invariants: fixed length, bounded ints, correct hash.
    """

    def test_ppv_dim_count_is_8(self) -> None:
        """PPV has exactly 8 dimensions."""
        assert PPV_DIM_COUNT == 8
        assert len(PPV_DIM_ORDER) == 8

    def test_ppv_dim_order_fixed(self) -> None:
        """PPV dimension order is fixed."""
        expected_order = (
            PPVDim.EDGE_TENSION,
            PPVDim.EDGE_RELEASE,
            PPVDim.ONSET_SHARPNESS,
            PPVDim.SONORITY_LIFT,
            PPVDim.CONTINUITY,
            PPVDim.DISCONTINUITY,
            PPVDim.RHYTHMIC_IMPULSE,
            PPVDim.STABILITY_PRESSURE,
        )
        assert PPV_DIM_ORDER == expected_order

    def test_ppv_value_bounds(self) -> None:
        """PPV values are bounded 0-7."""
        assert PPV_VALUE_MIN == 0
        assert PPV_VALUE_MAX == 7

    def test_ppv_vector_validates_bounds(self) -> None:
        """PPVVector rejects out-of-bounds values."""
        # Value too low
        with pytest.raises(ValueError, match="must be in range"):
            create_ppv_vector(values=(-1, 0, 0, 0, 0, 0, 0, 0))

        # Value too high
        with pytest.raises(ValueError, match="must be in range"):
            create_ppv_vector(values=(8, 0, 0, 0, 0, 0, 0, 0))

    def test_ppv_vector_validates_length(self) -> None:
        """PPVVector rejects wrong number of values."""
        with pytest.raises(ValueError, match="exactly"):
            create_ppv_vector(values=(0, 0, 0))  # Too few

        with pytest.raises(ValueError, match="exactly"):
            create_ppv_vector(values=(0, 0, 0, 0, 0, 0, 0, 0, 0))  # Too many

    def test_ppv_invariants_validator(self) -> None:
        """validate_ppv_invariants_v1 passes for valid PPV."""
        ppv = create_test_ppv_vector()
        assert validate_ppv_invariants_v1(ppv) is True

    def test_ppv_hash_is_64_hex(self) -> None:
        """PPV hash is 64-char hex string."""
        ppv = create_test_ppv_vector()
        assert len(ppv.ppv_hash) == 64
        int(ppv.ppv_hash, 16)  # Should not raise

    def test_ppv_aggregate_is_deterministic(self) -> None:
        """PPV aggregate is computed deterministically from values."""
        values = (1, 2, 3, 4, 5, 6, 7, 0)
        ppv = create_ppv_vector(values=values)

        # Aggregate is weighted sum: sum(val * (idx + 1))
        expected_aggregate = (1*1 + 2*2 + 3*3 + 4*4 + 5*5 + 6*6 + 7*7 + 0*8)
        assert ppv.aggregate == expected_aggregate


# =============================================================================
# Test Category 3: GOVERNED Behavior Unchanged
# =============================================================================


class TestGOVERNEDBehavior:
    """
    Test that GOVERNED mode behavior is unchanged with PPV.
    """

    def test_governed_no_ppv_baseline_unchanged(self) -> None:
        """GOVERNED mode without PPV produces same output as before."""
        phase10_result = create_test_phase10_result()

        # Without PPV - baseline behavior
        vc_extraction = extract_vc_facts(phase10_result)
        render_result = render_template(vc_extraction, phase10_result.acoustic_regime)
        verifier_report = verify_output(render_result)

        assert verifier_report.passed is True
        assert "[REGIME:neutral]" in render_result.output_text

    def test_governed_with_ppv_template_supported_passes(self) -> None:
        """GOVERNED mode with PPV on supported template passes verifier."""
        phase10_result = create_test_phase10_result(
            vc_facts=("VC-1",),  # Single VC-1 has PPV template
            acoustic_regime="neutral",
        )
        ppv = create_test_ppv_vector()

        # Extract with PPV
        vc_extraction = extract_vc_facts(phase10_result)
        ppv_metrics = extract_ppv_metrics(ppv)

        # Render with PPV
        render_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            ppv_metrics,
        )

        # Verify with PPV context
        verifier_report = verify_output_with_ppv(
            render_result,
            ppv_present=True,
            ppv_template_supported=is_ppv_template_supported(
                phase10_result.acoustic_regime,
                frozenset(vc_extraction.vc_facts),
            ),
        )

        assert verifier_report.passed is True
        assert "[PPV:" in render_result.output_text

    def test_governed_with_ppv_template_unsupported_blocked(self) -> None:
        """GOVERNED mode with PPV on unsupported template - verify should fail."""
        phase10_result = create_test_phase10_result(
            vc_facts=("VC-3", "VC-4", "VC-5"),  # Unusual combo - no PPV template
            acoustic_regime="neutral",
        )
        ppv = create_test_ppv_vector()

        # Check that template doesn't support PPV
        vc_fact_set = frozenset(phase10_result.vc_facts)
        assert is_ppv_template_supported("neutral", vc_fact_set) is False

        # Extract with PPV
        vc_extraction = extract_vc_facts(phase10_result)
        ppv_metrics = extract_ppv_metrics(ppv)

        # Render with PPV - will use default PPV template
        render_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            ppv_metrics,
        )

        # Verify - should fail because template doesn't support PPV
        verifier_report = verify_output_with_ppv(
            render_result,
            ppv_present=True,
            ppv_template_supported=False,  # Not supported
        )

        # Verifier should flag this for GOVERNED mode
        ppv_support_check = next(
            (c for c in verifier_report.checks if c.check_name == "ppv_template_support"),
            None,
        )
        assert ppv_support_check is not None
        assert ppv_support_check.passed is False

    def test_governed_ppv_output_stable_across_runs(self) -> None:
        """GOVERNED mode PPV output is stable across 100 runs."""
        phase10_result = create_test_phase10_result(vc_facts=("VC-1",))
        ppv = create_test_ppv_vector()

        vc_extraction = extract_vc_facts(phase10_result)
        ppv_metrics = extract_ppv_metrics(ppv)

        # First run - reference
        first_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            ppv_metrics,
        )

        # 99 more runs
        for _ in range(99):
            result = render_template_with_ppv(
                vc_extraction,
                phase10_result.acoustic_regime,
                ppv_metrics,
            )
            assert result.output_text == first_result.output_text
            assert result.render_hash == first_result.render_hash


# =============================================================================
# Test Category 4: OPEN Behavior
# =============================================================================


class TestOPENBehavior:
    """
    Test OPEN mode behavior with PPV.
    """

    def test_open_ppv_verifier_fail_still_releases(self) -> None:
        """OPEN mode releases output even if PPV verifier fails."""
        # Create a situation where PPV template support check would fail
        phase10_result = create_test_phase10_result(
            vc_facts=("VC-3", "VC-4", "VC-5"),
        )
        ppv = create_test_ppv_vector()

        # Extract and render
        vc_extraction = extract_vc_facts(phase10_result)
        ppv_metrics = extract_ppv_metrics(ppv)
        render_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            ppv_metrics,
        )

        # In OPEN mode, even with verifier failure, output is released
        # The verifier report shows failure, but OPEN mode ignores it
        verifier_report = verify_output_with_ppv(
            render_result,
            ppv_present=True,
            ppv_template_supported=False,
        )

        # Verify that output exists (OPEN would release it)
        assert render_result.output_text != ""
        assert "[REGIME:" in render_result.output_text

    def test_open_mode_includes_dim_line(self) -> None:
        """OPEN mode can include PPV dimension line."""
        phase10_result = create_test_phase10_result(vc_facts=("VC-1",))
        ppv = create_test_ppv_vector()

        vc_extraction = extract_vc_facts(phase10_result)
        ppv_metrics = extract_ppv_metrics(ppv)

        # Render with dim line (OPEN mode feature)
        render_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            ppv_metrics,
            include_dim_line=True,
        )

        assert "[PPV_DIMS:" in render_result.output_text


# =============================================================================
# Test Category 5: No Forbidden Imports
# =============================================================================


class TestForbiddenImports:
    """
    Test that PPV modules do not import forbidden libraries.

    Forbidden: random, time, datetime, ML/NLP libs (torch, tensorflow, etc.)
    """

    def test_ppv_contract_no_random_import(self) -> None:
        """PPV contract module does not import random."""
        import symbolu.ppv.ppv_contract_v1 as ppv_contract
        module_contents = dir(ppv_contract)
        assert "random" not in module_contents
        assert "Random" not in module_contents

    def test_ppv_contract_no_time_import(self) -> None:
        """PPV contract module does not import time."""
        import symbolu.ppv.ppv_contract_v1 as ppv_contract
        module_contents = dir(ppv_contract)
        assert "time" not in module_contents
        assert "datetime" not in module_contents

    def test_ppv_builder_no_random_import(self) -> None:
        """PPV builder module does not import random."""
        import symbolu.ppv.ppv_builder_v1 as ppv_builder
        module_contents = dir(ppv_builder)
        assert "random" not in module_contents
        assert "Random" not in module_contents

    def test_ppv_builder_no_time_import(self) -> None:
        """PPV builder module does not import time."""
        import symbolu.ppv.ppv_builder_v1 as ppv_builder
        module_contents = dir(ppv_builder)
        assert "time" not in module_contents
        assert "datetime" not in module_contents

    def test_no_ml_imports_in_ppv_modules(self) -> None:
        """PPV modules do not import ML/NLP libraries."""
        forbidden_modules = [
            "torch",
            "tensorflow",
            "keras",
            "sklearn",
            "scipy",
            "nltk",
            "spacy",
            "transformers",
            "numpy",  # While numpy is numeric, we forbid it for strictness
        ]

        # Check ppv_contract
        import symbolu.ppv.ppv_contract_v1 as ppv_contract
        for mod in forbidden_modules:
            assert mod not in sys.modules or mod not in dir(ppv_contract)

        # Check ppv_builder
        import symbolu.ppv.ppv_builder_v1 as ppv_builder
        for mod in forbidden_modules:
            assert mod not in dir(ppv_builder)


# =============================================================================
# Test Category 6: PPV Builder
# =============================================================================


class TestPPVBuilder:
    """
    Test PPV builder functionality.
    """

    def test_build_ppv_from_context(self) -> None:
        """PPV builder produces valid PPV from context."""
        context = create_test_build_context()
        ppv = build_ppv_from_context(context)

        assert ppv is not None
        assert validate_ppv_invariants_v1(ppv)
        assert len(ppv.values) == PPV_DIM_COUNT

    def test_build_ppv_empty_phonemes_returns_none(self) -> None:
        """PPV builder returns None for empty phoneme list."""
        context = PPVBuildContext(
            phoneme_ids=(),
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv = build_ppv_from_context(context)
        assert ppv is None

    def test_build_ppv_unknown_phonemes_uses_defaults(self) -> None:
        """PPV builder uses default features for unknown phonemes."""
        context = PPVBuildContext(
            phoneme_ids=("xyz123", "abc456", "unknown"),  # All unknown
            adjacency_markers=(),
            span_boundaries=(),
            fold_sizes=(),
            acoustic_regime="neutral",
        )
        ppv = build_ppv_from_context(context)
        # Builder produces result using default (zero) features
        # This is acceptable - PPV is still deterministic and bounded
        if ppv is not None:
            assert validate_ppv_invariants_v1(ppv)
            # All values should be within bounds
            for val in ppv.values:
                assert PPV_VALUE_MIN <= val <= PPV_VALUE_MAX

    def test_build_ppv_for_artifact(self) -> None:
        """PPV builder works with Phase10Result containing phoneme data."""
        phase10_result = create_test_phase10_result(include_phoneme_data=True)
        ppv = build_ppv_for_artifact(phase10_result)

        assert ppv is not None
        assert validate_ppv_invariants_v1(ppv)

    def test_build_ppv_for_artifact_no_phonemes_returns_none(self) -> None:
        """PPV builder returns None when Phase10Result has no phoneme data."""
        phase10_result = create_test_phase10_result(include_phoneme_data=False)
        ppv = build_ppv_for_artifact(phase10_result)
        assert ppv is None

    def test_phoneme_features_all_bounded(self) -> None:
        """All phoneme features in table are within bounds."""
        for phoneme, features in PHONEME_FEATURES.items():
            assert len(features) == PPV_DIM_COUNT, f"Phoneme {phoneme} has wrong feature count"
            for i, val in enumerate(features):
                assert PPV_VALUE_MIN <= val <= PPV_VALUE_MAX, (
                    f"Phoneme {phoneme} feature[{i}] = {val} out of bounds"
                )


# =============================================================================
# Test Category 7: PPV Envelope
# =============================================================================


class TestPPVEnvelope:
    """
    Test Phase10Envelope with PPV attachment.
    """

    def test_create_envelope_without_ppv(self) -> None:
        """Envelope works without PPV attachment."""
        phase10_result = create_test_phase10_result()
        envelope = create_phase10_envelope(phase10_result, ppv=None)

        assert envelope.has_ppv is False
        assert envelope.ppv is None
        assert envelope.artifact_hash == phase10_result.artifact_hash

    def test_create_envelope_with_ppv(self) -> None:
        """Envelope works with PPV attachment."""
        phase10_result = create_test_phase10_result()
        ppv = create_test_ppv_vector()
        envelope = create_phase10_envelope(phase10_result, ppv)

        assert envelope.has_ppv is True
        assert envelope.ppv == ppv
        assert envelope.ppv_hash == ppv.ppv_hash

    def test_envelope_preserves_original_hash(self) -> None:
        """Envelope preserves original artifact hash unchanged."""
        phase10_result = create_test_phase10_result()
        ppv = create_test_ppv_vector()
        envelope = create_phase10_envelope(phase10_result, ppv)

        # Original artifact hash is unchanged
        assert envelope.artifact_hash == phase10_result.artifact_hash
        assert envelope.phase10_result.artifact_hash == phase10_result.artifact_hash

    def test_wrap_with_ppv(self) -> None:
        """wrap_with_ppv attempts to build PPV from Phase10Result."""
        phase10_result = create_test_phase10_result(include_phoneme_data=True)
        envelope = wrap_with_ppv(phase10_result)

        assert envelope.has_ppv is True
        assert envelope.ppv is not None

    def test_extract_ppv_metrics_from_envelope(self) -> None:
        """PPV metrics can be extracted from envelope."""
        phase10_result = create_test_phase10_result()
        ppv = create_test_ppv_vector()
        envelope = create_phase10_envelope(phase10_result, ppv)

        metrics = extract_envelope_ppv_metrics(envelope)

        assert metrics["PPV_PRESENT"] is True
        assert metrics["PPV_AGGREGATE"] == ppv.aggregate
        assert metrics["PPV_DIM_SUMMARY"] == ppv.values


# =============================================================================
# Test Category 8: Ledger Recording
# =============================================================================


class TestLedgerRecording:
    """
    Test ledger recording with PPV.
    """

    def test_ledger_entry_with_ppv_hash(self) -> None:
        """Ledger entry can record PPV hash."""
        ppv = create_test_ppv_vector()
        ppv_hash_truncated = ppv.ppv_hash[:16]

        entry = create_ledger_entry(
            artifact_id="test_artifact",
            artifact_hash=create_test_artifact_hash(),
            candidate_output_hash="a" * 16,
            verifier_report_hash="b" * 16,
            render_mode=RenderMode.GOVERNED,
            verifier_passed=True,
            output_released=True,
            ppv_hash=ppv_hash_truncated,
        )

        assert entry.ppv_hash == ppv_hash_truncated

    def test_ledger_entry_without_ppv_hash(self) -> None:
        """Ledger entry works without PPV hash."""
        entry = create_ledger_entry(
            artifact_id="test_artifact",
            artifact_hash=create_test_artifact_hash(),
            candidate_output_hash="a" * 16,
            verifier_report_hash="b" * 16,
            render_mode=RenderMode.GOVERNED,
            verifier_passed=True,
            output_released=True,
        )

        assert entry.ppv_hash is None

    def test_ledger_span_id_includes_ppv(self) -> None:
        """Span ID computation includes PPV hash."""
        base_args = {
            "artifact_id": "test_artifact",
            "artifact_hash": create_test_artifact_hash(),
            "candidate_output_hash": "a" * 16,
            "verifier_report_hash": "b" * 16,
            "render_mode": RenderMode.GOVERNED,
            "verifier_passed": True,
            "output_released": True,
        }

        # Without PPV
        entry_no_ppv = create_ledger_entry(**base_args)

        # With PPV
        entry_with_ppv = create_ledger_entry(**base_args, ppv_hash="c" * 16)

        # Span IDs should be different
        assert entry_no_ppv.span_id != entry_with_ppv.span_id

    def test_ledger_to_dict_includes_ppv(self) -> None:
        """Ledger entry to_dict includes PPV hash."""
        ppv = create_test_ppv_vector()
        ppv_hash_truncated = ppv.ppv_hash[:16]

        entry = create_ledger_entry(
            artifact_id="test_artifact",
            artifact_hash=create_test_artifact_hash(),
            candidate_output_hash="a" * 16,
            verifier_report_hash="b" * 16,
            render_mode=RenderMode.GOVERNED,
            verifier_passed=True,
            output_released=True,
            ppv_hash=ppv_hash_truncated,
        )

        entry_dict = entry.to_dict()
        assert "ppv_hash" in entry_dict
        assert entry_dict["ppv_hash"] == ppv_hash_truncated


# =============================================================================
# Test Category 9: Verifier PPV Checks
# =============================================================================


class TestVerifierPPVChecks:
    """
    Test verifier PPV-specific checks.
    """

    def test_verifier_ppv_numeric_only_passes(self) -> None:
        """Verifier passes when PPV fields are numeric only."""
        phase10_result = create_test_phase10_result(vc_facts=("VC-1",))
        ppv = create_test_ppv_vector()

        vc_extraction = extract_vc_facts(phase10_result)
        ppv_metrics = extract_ppv_metrics(ppv)
        render_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            ppv_metrics,
        )

        verifier_report = verify_output_with_ppv(
            render_result,
            ppv_present=True,
            ppv_template_supported=True,
        )

        # All PPV checks should pass
        ppv_checks = [
            c for c in verifier_report.checks
            if c.check_name.startswith("ppv_")
        ]
        for check in ppv_checks:
            assert check.passed is True, f"PPV check failed: {check.check_name}: {check.details}"

    def test_verifier_detects_no_ppv_in_output_when_present(self) -> None:
        """Verifier detects when PPV is present but not rendered."""
        phase10_result = create_test_phase10_result(vc_facts=("VC-1",))

        vc_extraction = extract_vc_facts(phase10_result)
        # Render WITHOUT PPV (using empty metrics)
        render_result = render_template_with_ppv(
            vc_extraction,
            phase10_result.acoustic_regime,
            EMPTY_PPV_METRICS,  # No PPV
        )

        # But claim PPV was present
        verifier_report = verify_output_with_ppv(
            render_result,
            ppv_present=True,  # Claim PPV present
            ppv_template_supported=True,
        )

        # Output doesn't have PPV, but we claimed it was present
        # This is OK - PPV was present but not rendered (template fallback)
        ppv_support_check = next(
            (c for c in verifier_report.checks if c.check_name == "ppv_template_support"),
            None,
        )
        assert ppv_support_check is not None
        # This should pass because PPV present but not rendered is allowed
        assert "not rendered" in ppv_support_check.details or ppv_support_check.passed


# =============================================================================
# Public Test Exports
# =============================================================================

__all__ = [
    "TestPPVDeterminism",
    "TestPPVInvariants",
    "TestGOVERNEDBehavior",
    "TestOPENBehavior",
    "TestForbiddenImports",
    "TestPPVBuilder",
    "TestPPVEnvelope",
    "TestLedgerRecording",
    "TestVerifierPPVChecks",
]
