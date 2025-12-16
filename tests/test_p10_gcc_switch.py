"""
Phase-10 GCC Switch Test Suite
==============================

Comprehensive tests for the GCC (Global Constraint Clamp) disable switch at Phase-10.

Test Categories:
    1. Determinism - Same request + same gcc_mode -> identical output
    2. Isolation - Phase 1b-9 outputs identical regardless of gcc_mode
    3. Behavioral Difference - ENABLED vs DISABLED produce different outputs
    4. Ledger Integrity - gcc_mode affects span hash, replay verification passes
    5. Fail-Closed - Invalid gcc_mode rejected, missing artifact_hash rejected

CRITICAL INVARIANTS VERIFIED:
    - gcc_mode is explicit, never inferred
    - Default behavior remains GCC ENABLED
    - No backward-compatibility break
    - Unknown gcc_mode -> HARD FAIL
    - DISABLED without explicit request -> NOT POSSIBLE
"""

import hashlib
import json
import pytest
from typing import Tuple

from symbolu.mechanical.pipeline.phase_p6.p6_schema import (
    RegimeEnvelope,
    OperationalRegime,
)
from symbolu.mechanical.pipeline.p7_discourse.p7_discourse_schema import (
    DiscourseEnvelope,
    DiscourseAct,
)
from symbolu.mechanical.pipeline.p9_lexical.p9_lexical_schema import LexicalFrame
from symbolu.mechanical.pipeline.p8_semantics.p8_semantic_schema import SemanticSlot
from symbolu.mechanical.pipeline.phase_zero.phase_zero_schema import IntentType
from symbolu.mechanical.pipeline.phase_po5.po5_schema import ExecutionEligibility
from symbolu.mechanical.pipeline.p10_acoustic.p10_acoustic_schema import (
    AcousticParameterFrame,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_mode import (
    GCCMode,
    Phase10Request,
    Phase10Response,
    validate_gcc_mode,
    is_gcc_enabled,
    is_gcc_disabled,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_resolver import (
    GCCLedgerEntry,
    P10GCCResolver,
    compute_gcc_span_id,
    compute_layers_hash,
    GCC_VERSION,
)
from symbolu.mechanical.pipeline.p10_acoustic.p10_gcc_integration import (
    run_p10_with_gcc_mode,
    create_p10_response,
    get_p10_gcc_resolver,
)
from symbolu.ontology.router.ontological_router_r1 import OntologicalLayer


# =============================================================================
# Test Fixtures
# =============================================================================


def create_test_artifact_hash() -> str:
    """Create a valid 64-char hex artifact hash for testing."""
    return hashlib.sha256(b"test_artifact_content").hexdigest()


def create_test_request(
    gcc_mode: GCCMode = GCCMode.ENABLED,
    artifact_id: str = "test_artifact",
) -> Phase10Request:
    """Create a valid Phase10Request for testing."""
    return Phase10Request(
        artifact_id=artifact_id,
        artifact_hash=create_test_artifact_hash(),
        projected_layers=(OntologicalLayer.FORMING,),
        gcc_mode=gcc_mode,
    )


def create_test_regime_envelope(
    regime: OperationalRegime = OperationalRegime.INFORM,
) -> RegimeEnvelope:
    """Create a valid RegimeEnvelope for testing."""
    return RegimeEnvelope(
        regime=regime,
        reason="TEST_REGIME",
        intent=IntentType.INFORM,
        execution_eligibility=ExecutionEligibility.PROHIBITED,
        coherence_regime="STABLE",
    )


def create_test_discourse_envelope(
    act: DiscourseAct = DiscourseAct.EXPLANATION,
) -> DiscourseEnvelope:
    """Create a valid DiscourseEnvelope for testing."""
    return DiscourseEnvelope(
        act=act,
        allowed=True,
        reason="TEST_DISCOURSE",
        intent=IntentType.INFORM,
        regime=OperationalRegime.INFORM,
    )


def create_test_lexical_frame() -> LexicalFrame:
    """Create a valid LexicalFrame for testing."""
    return LexicalFrame(
        selections={SemanticSlot.STATE: "understood"},
        allowed=True,
        reason="TEST_LEXICAL",
        source_discourse_act="EXPLANATION",
        source_regime="INFORM",
    )


# =============================================================================
# Test Category 1: Determinism
# =============================================================================


class TestDeterminism:
    """
    Test that same request + same gcc_mode produces identical output.

    CRITICAL: Must pass 100 runs with identical results.
    """

    def test_gcc_enabled_determinism_100_runs(self) -> None:
        """Same request with GCC ENABLED produces identical output 100 times."""
        request = create_test_request(gcc_mode=GCCMode.ENABLED)
        regime_envelope = create_test_regime_envelope()
        discourse_envelope = create_test_discourse_envelope()
        lexical_frame = create_test_lexical_frame()

        # First run - reference result
        first_frame, first_ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=lexical_frame,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        # 100 runs must produce identical results
        for i in range(100):
            frame, ledger = run_p10_with_gcc_mode(
                request=request,
                lexical_frame=lexical_frame,
                discourse_envelope=discourse_envelope,
                regime_envelope=regime_envelope,
            )

            # Frame must be identical
            assert frame.regime == first_frame.regime, f"Run {i}: regime mismatch"
            assert frame.speech_rate == first_frame.speech_rate, f"Run {i}: speech_rate mismatch"
            assert frame.energy_level == first_frame.energy_level, f"Run {i}: energy_level mismatch"
            assert frame.pitch_range == first_frame.pitch_range, f"Run {i}: pitch_range mismatch"
            assert frame.pause_policy == first_frame.pause_policy, f"Run {i}: pause_policy mismatch"

            # Ledger must be identical
            assert ledger.span_id == first_ledger.span_id, f"Run {i}: span_id mismatch"
            assert ledger.gcc_mode == first_ledger.gcc_mode, f"Run {i}: gcc_mode mismatch"

    def test_gcc_disabled_determinism_100_runs(self) -> None:
        """Same request with GCC DISABLED produces identical output 100 times."""
        request = create_test_request(gcc_mode=GCCMode.DISABLED)
        regime_envelope = create_test_regime_envelope()
        discourse_envelope = create_test_discourse_envelope()
        lexical_frame = create_test_lexical_frame()

        # First run - reference result
        first_frame, first_ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=lexical_frame,
            discourse_envelope=discourse_envelope,
            regime_envelope=regime_envelope,
        )

        # 100 runs must produce identical results
        for i in range(100):
            frame, ledger = run_p10_with_gcc_mode(
                request=request,
                lexical_frame=lexical_frame,
                discourse_envelope=discourse_envelope,
                regime_envelope=regime_envelope,
            )

            # Frame must be identical
            assert frame.regime == first_frame.regime, f"Run {i}: regime mismatch"
            assert frame.speech_rate == first_frame.speech_rate, f"Run {i}: speech_rate mismatch"
            assert frame.energy_level == first_frame.energy_level, f"Run {i}: energy_level mismatch"

            # Ledger must be identical
            assert ledger.span_id == first_ledger.span_id, f"Run {i}: span_id mismatch"

    def test_span_id_deterministic(self) -> None:
        """Span ID computation is deterministic."""
        artifact_hash = create_test_artifact_hash()
        layers_hash = compute_layers_hash((OntologicalLayer.FORMING,))

        # Same inputs must produce same span_id
        span_id_1 = compute_gcc_span_id(artifact_hash, GCCMode.ENABLED, layers_hash)
        span_id_2 = compute_gcc_span_id(artifact_hash, GCCMode.ENABLED, layers_hash)
        assert span_id_1 == span_id_2

        # Different gcc_mode must produce different span_id
        span_id_disabled = compute_gcc_span_id(artifact_hash, GCCMode.DISABLED, layers_hash)
        assert span_id_1 != span_id_disabled


# =============================================================================
# Test Category 2: Isolation
# =============================================================================


class TestIsolation:
    """
    Test that Phase 1b-9 outputs are identical regardless of gcc_mode.

    GCC mode ONLY affects Phase-10 consequence attenuation, not prior phases.
    """

    def test_regime_envelope_unchanged(self) -> None:
        """RegimeEnvelope (P6) is unchanged by gcc_mode."""
        regime_envelope = create_test_regime_envelope(OperationalRegime.HOLD)

        request_enabled = create_test_request(gcc_mode=GCCMode.ENABLED)
        request_disabled = create_test_request(gcc_mode=GCCMode.DISABLED)

        frame_enabled, _ = run_p10_with_gcc_mode(
            request=request_enabled,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=regime_envelope,
        )

        frame_disabled, _ = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=regime_envelope,
        )

        # Source regime must be identical (from P6)
        assert frame_enabled.source_regime == frame_disabled.source_regime
        assert frame_enabled.source_regime == "HOLD"

    def test_discourse_envelope_unchanged(self) -> None:
        """DiscourseEnvelope (P7) is unchanged by gcc_mode."""
        discourse_envelope = create_test_discourse_envelope(DiscourseAct.REFLECTION)

        request_enabled = create_test_request(gcc_mode=GCCMode.ENABLED)
        request_disabled = create_test_request(gcc_mode=GCCMode.DISABLED)

        frame_enabled, _ = run_p10_with_gcc_mode(
            request=request_enabled,
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=create_test_regime_envelope(),
        )

        frame_disabled, _ = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=None,
            discourse_envelope=discourse_envelope,
            regime_envelope=create_test_regime_envelope(),
        )

        # Source discourse act must be identical (from P7)
        assert frame_enabled.source_discourse_act == frame_disabled.source_discourse_act
        assert frame_enabled.source_discourse_act == "REFLECTION"

    def test_lexical_frame_unchanged(self) -> None:
        """LexicalFrame (P9) is read-only, unchanged by gcc_mode."""
        lexical_frame = create_test_lexical_frame()

        request_enabled = create_test_request(gcc_mode=GCCMode.ENABLED)
        request_disabled = create_test_request(gcc_mode=GCCMode.DISABLED)

        frame_enabled, _ = run_p10_with_gcc_mode(
            request=request_enabled,
            lexical_frame=lexical_frame,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        frame_disabled, _ = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=lexical_frame,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        # LexicalFrame was read-only (check via debug info)
        assert frame_enabled.debug.get("has_lexical_frame") == True
        assert frame_disabled.debug.get("has_lexical_frame") == True


# =============================================================================
# Test Category 3: Behavioral Difference
# =============================================================================


class TestBehavioralDifference:
    """
    Test that ENABLED vs DISABLED produce different Phase-10 outputs
    when clamping would apply.
    """

    def test_gcc_clamping_applied_flag_differs(self) -> None:
        """gcc_clamping_applied differs between ENABLED and DISABLED."""
        request_enabled = create_test_request(gcc_mode=GCCMode.ENABLED)
        request_disabled = create_test_request(gcc_mode=GCCMode.DISABLED)

        _, ledger_enabled = run_p10_with_gcc_mode(
            request=request_enabled,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        _, ledger_disabled = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        assert ledger_enabled.clamping_applied == True
        assert ledger_disabled.clamping_applied == False

    def test_span_id_differs_by_gcc_mode(self) -> None:
        """Span ID differs between ENABLED and DISABLED for same inputs."""
        # Use identical inputs except gcc_mode
        artifact_hash = create_test_artifact_hash()
        artifact_id = "test_artifact_same"
        projected_layers = (OntologicalLayer.FORMING,)

        request_enabled = Phase10Request(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            projected_layers=projected_layers,
            gcc_mode=GCCMode.ENABLED,
        )

        request_disabled = Phase10Request(
            artifact_id=artifact_id,
            artifact_hash=artifact_hash,
            projected_layers=projected_layers,
            gcc_mode=GCCMode.DISABLED,
        )

        _, ledger_enabled = run_p10_with_gcc_mode(
            request=request_enabled,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        _, ledger_disabled = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        # Span IDs must differ because gcc_mode is hash-participating
        assert ledger_enabled.span_id != ledger_disabled.span_id

    def test_debug_info_shows_gcc_mode(self) -> None:
        """Debug info in frame shows gcc_mode and clamping status."""
        request_disabled = create_test_request(gcc_mode=GCCMode.DISABLED)

        frame_disabled, _ = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        # Debug info should show GCC DISABLED mode
        assert frame_disabled.debug.get("gcc_mode") == "DISABLED"
        assert frame_disabled.debug.get("gcc_clamping_applied") == False


# =============================================================================
# Test Category 4: Ledger Integrity
# =============================================================================


class TestLedgerIntegrity:
    """
    Test that gcc_mode affects span hash and replay verification passes.
    """

    def test_ledger_entry_has_required_fields(self) -> None:
        """GCCLedgerEntry has all required fields per spec."""
        request = create_test_request(gcc_mode=GCCMode.ENABLED)

        _, ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        # Required fields per spec
        assert ledger.phase == "PHASE_10"
        assert ledger.gcc_mode in ("ENABLED", "DISABLED")
        assert len(ledger.artifact_hash) == 64
        assert len(ledger.span_id) > 0
        assert ledger.timestamp is None  # No timestamps
        assert ledger.gcc_version == GCC_VERSION
        assert isinstance(ledger.clamping_applied, bool)

    def test_ledger_entry_gcc_mode_is_hash_participating(self) -> None:
        """gcc_mode affects the span_id hash."""
        artifact_hash = create_test_artifact_hash()
        layers_hash = compute_layers_hash((OntologicalLayer.FORMING,))

        span_enabled = compute_gcc_span_id(artifact_hash, GCCMode.ENABLED, layers_hash)
        span_disabled = compute_gcc_span_id(artifact_hash, GCCMode.DISABLED, layers_hash)

        # gcc_mode must affect the span_id
        assert span_enabled != span_disabled

    def test_replay_with_same_inputs_identical(self) -> None:
        """Replay with same inputs produces identical span_id."""
        request = create_test_request(gcc_mode=GCCMode.ENABLED)

        _, ledger_1 = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        _, ledger_2 = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        # Replay produces identical span_id
        assert ledger_1.span_id == ledger_2.span_id
        assert ledger_1.gcc_mode == ledger_2.gcc_mode

    def test_ledger_entry_clamping_applied_invariant(self) -> None:
        """clamping_applied is True IFF gcc_mode == ENABLED."""
        request_enabled = create_test_request(gcc_mode=GCCMode.ENABLED)
        request_disabled = create_test_request(gcc_mode=GCCMode.DISABLED)

        _, ledger_enabled = run_p10_with_gcc_mode(
            request=request_enabled,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        _, ledger_disabled = run_p10_with_gcc_mode(
            request=request_disabled,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        # Invariant: clamping_applied IFF gcc_mode == ENABLED
        assert ledger_enabled.clamping_applied == True
        assert ledger_disabled.clamping_applied == False


# =============================================================================
# Test Category 5: Fail-Closed
# =============================================================================


class TestFailClosed:
    """
    Test fail-closed behavior for invalid inputs.
    """

    def test_invalid_gcc_mode_rejected(self) -> None:
        """Unknown gcc_mode causes HARD FAIL."""
        with pytest.raises(ValueError, match="gcc_mode must be GCCMode enum"):
            validate_gcc_mode("invalid")  # type: ignore

        with pytest.raises(ValueError, match="gcc_mode must be GCCMode enum"):
            validate_gcc_mode(None)  # type: ignore

        with pytest.raises(ValueError, match="gcc_mode must be GCCMode enum"):
            validate_gcc_mode(123)  # type: ignore

    def test_missing_artifact_hash_rejected(self) -> None:
        """Missing artifact_hash causes HARD FAIL."""
        with pytest.raises(ValueError, match="artifact_hash must be 64 hex chars"):
            Phase10Request(
                artifact_id="test",
                artifact_hash="",  # Empty - invalid
                projected_layers=(OntologicalLayer.FORMING,),
                gcc_mode=GCCMode.ENABLED,
            )

    def test_invalid_artifact_hash_length_rejected(self) -> None:
        """Wrong length artifact_hash causes HARD FAIL."""
        with pytest.raises(ValueError, match="artifact_hash must be 64 hex chars"):
            Phase10Request(
                artifact_id="test",
                artifact_hash="abc123",  # Too short
                projected_layers=(OntologicalLayer.FORMING,),
                gcc_mode=GCCMode.ENABLED,
            )

    def test_non_hex_artifact_hash_rejected(self) -> None:
        """Non-hex artifact_hash causes HARD FAIL."""
        with pytest.raises(ValueError, match="hex characters"):
            Phase10Request(
                artifact_id="test",
                artifact_hash="z" * 64,  # Not hex
                projected_layers=(OntologicalLayer.FORMING,),
                gcc_mode=GCCMode.ENABLED,
            )

    def test_empty_artifact_id_rejected(self) -> None:
        """Empty artifact_id causes HARD FAIL."""
        with pytest.raises(ValueError, match="artifact_id must be non-empty"):
            Phase10Request(
                artifact_id="",  # Empty - invalid
                artifact_hash=create_test_artifact_hash(),
                projected_layers=(OntologicalLayer.FORMING,),
                gcc_mode=GCCMode.ENABLED,
            )

    def test_invalid_projected_layers_rejected(self) -> None:
        """Invalid projected_layers causes HARD FAIL."""
        with pytest.raises(ValueError, match="projected_layers must be tuple"):
            Phase10Request(
                artifact_id="test",
                artifact_hash=create_test_artifact_hash(),
                projected_layers=["not", "a", "tuple"],  # type: ignore
                gcc_mode=GCCMode.ENABLED,
            )

    def test_gcc_mode_default_is_enabled(self) -> None:
        """Default gcc_mode is ENABLED (not inferred)."""
        request = Phase10Request(
            artifact_id="test",
            artifact_hash=create_test_artifact_hash(),
            projected_layers=(OntologicalLayer.FORMING,),
            # gcc_mode not specified - should default to ENABLED
        )
        assert request.gcc_mode == GCCMode.ENABLED

    def test_disabled_requires_explicit_request(self) -> None:
        """DISABLED mode requires explicit specification."""
        # This test verifies that DISABLED cannot be "inferred" or "auto-applied"

        # Only way to get DISABLED is to explicitly request it
        request_disabled = Phase10Request(
            artifact_id="test",
            artifact_hash=create_test_artifact_hash(),
            projected_layers=(OntologicalLayer.FORMING,),
            gcc_mode=GCCMode.DISABLED,  # Explicit
        )
        assert request_disabled.gcc_mode == GCCMode.DISABLED

        # Default is always ENABLED
        request_default = Phase10Request(
            artifact_id="test",
            artifact_hash=create_test_artifact_hash(),
            projected_layers=(OntologicalLayer.FORMING,),
        )
        assert request_default.gcc_mode == GCCMode.ENABLED


# =============================================================================
# Test Category 6: Phase10Response Validation
# =============================================================================


class TestPhase10Response:
    """Test Phase10Response dataclass invariants."""

    def test_response_creation(self) -> None:
        """Phase10Response can be created from request and ledger."""
        request = create_test_request(gcc_mode=GCCMode.ENABLED)

        _, ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        response = create_p10_response(request, ledger)

        assert response.artifact_id == request.artifact_id
        assert response.artifact_hash == request.artifact_hash
        assert response.gcc_mode == GCCMode.ENABLED
        assert response.gcc_clamping_applied == True
        assert response.phase_id == "PHASE_10"
        assert len(response.span_id) > 0

    def test_response_gcc_disabled(self) -> None:
        """Phase10Response correctly reflects DISABLED mode."""
        request = create_test_request(gcc_mode=GCCMode.DISABLED)

        _, ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=None,
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=create_test_regime_envelope(),
        )

        response = create_p10_response(request, ledger)

        assert response.gcc_mode == GCCMode.DISABLED
        assert response.gcc_clamping_applied == False

    def test_response_invariant_clamping_matches_mode(self) -> None:
        """Response invariant: gcc_clamping_applied matches gcc_mode."""
        # ENABLED -> clamping_applied = True
        with pytest.raises(ValueError, match="gcc_clamping_applied must be True"):
            Phase10Response(
                artifact_id="test",
                artifact_hash=create_test_artifact_hash(),
                gcc_mode=GCCMode.ENABLED,
                gcc_clamping_applied=False,  # Invalid!
                span_id="0123456789abcdef",
            )

        # DISABLED -> clamping_applied = False
        with pytest.raises(ValueError, match="gcc_clamping_applied must be False"):
            Phase10Response(
                artifact_id="test",
                artifact_hash=create_test_artifact_hash(),
                gcc_mode=GCCMode.DISABLED,
                gcc_clamping_applied=True,  # Invalid!
                span_id="0123456789abcdef",
            )


# =============================================================================
# Test Category 7: GCC Mode Helper Functions
# =============================================================================


class TestGCCModeHelpers:
    """Test GCC mode helper functions."""

    def test_is_gcc_enabled(self) -> None:
        """is_gcc_enabled returns correct value."""
        assert is_gcc_enabled(GCCMode.ENABLED) == True
        assert is_gcc_enabled(GCCMode.DISABLED) == False

    def test_is_gcc_disabled(self) -> None:
        """is_gcc_disabled returns correct value."""
        assert is_gcc_disabled(GCCMode.ENABLED) == False
        assert is_gcc_disabled(GCCMode.DISABLED) == True

    def test_validate_gcc_mode_valid(self) -> None:
        """validate_gcc_mode passes for valid modes."""
        validate_gcc_mode(GCCMode.ENABLED)  # Should not raise
        validate_gcc_mode(GCCMode.DISABLED)  # Should not raise

    def test_validate_gcc_mode_invalid(self) -> None:
        """validate_gcc_mode raises for invalid modes."""
        with pytest.raises(ValueError):
            validate_gcc_mode("ENABLED")  # type: ignore

        with pytest.raises(ValueError):
            validate_gcc_mode(None)  # type: ignore


# =============================================================================
# Test Category 8: Resolver Singleton
# =============================================================================


class TestResolverSingleton:
    """Test resolver singleton behavior."""

    def test_singleton_same_instance(self) -> None:
        """get_p10_gcc_resolver returns same instance."""
        resolver_1 = get_p10_gcc_resolver()
        resolver_2 = get_p10_gcc_resolver()
        assert resolver_1 is resolver_2


# =============================================================================
# Test Category 9: Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_missing_regime_envelope_uses_safe_default(self) -> None:
        """Missing regime envelope falls back to SAFE_DEFAULT."""
        request = create_test_request(gcc_mode=GCCMode.DISABLED)

        frame, ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=create_test_discourse_envelope(),
            regime_envelope=None,  # Missing!
        )

        # Should use SAFE_DEFAULT (HOLD/FLAT)
        assert frame.debug.get("is_safe_default") == True

    def test_missing_discourse_envelope_uses_safe_default(self) -> None:
        """Missing discourse envelope falls back to SAFE_DEFAULT."""
        request = create_test_request(gcc_mode=GCCMode.DISABLED)

        frame, ledger = run_p10_with_gcc_mode(
            request=request,
            lexical_frame=create_test_lexical_frame(),
            discourse_envelope=None,  # Missing!
            regime_envelope=create_test_regime_envelope(),
        )

        # Should use SAFE_DEFAULT
        assert frame.debug.get("is_safe_default") == True

    def test_all_regimes_work_with_gcc_disabled(self) -> None:
        """All operational regimes work with GCC DISABLED."""
        request = create_test_request(gcc_mode=GCCMode.DISABLED)

        for regime in OperationalRegime:
            regime_envelope = create_test_regime_envelope(regime)

            frame, ledger = run_p10_with_gcc_mode(
                request=request,
                lexical_frame=create_test_lexical_frame(),
                discourse_envelope=create_test_discourse_envelope(),
                regime_envelope=regime_envelope,
            )

            # Should complete without error
            assert frame is not None
            assert ledger.gcc_mode == "DISABLED"
            assert ledger.clamping_applied == False

    def test_all_discourse_acts_work_with_gcc_disabled(self) -> None:
        """All discourse acts work with GCC DISABLED."""
        request = create_test_request(gcc_mode=GCCMode.DISABLED)

        for act in DiscourseAct:
            discourse_envelope = create_test_discourse_envelope(act)

            frame, ledger = run_p10_with_gcc_mode(
                request=request,
                lexical_frame=create_test_lexical_frame(),
                discourse_envelope=discourse_envelope,
                regime_envelope=create_test_regime_envelope(),
            )

            # Should complete without error
            assert frame is not None
            assert ledger.gcc_mode == "DISABLED"
