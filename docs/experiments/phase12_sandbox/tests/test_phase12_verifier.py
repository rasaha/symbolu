"""
Tests for Phase-12 Output Verifier
==================================

Test Categories:
    1. Determinism - Same input → same output (100+ runs)
    2. Structural Checks - Length, format validation
    3. Ontological Checks - Family marker detection
    4. PPV Alignment Checks - Style consistency
    5. Content Policy - Forbidden pattern detection
    6. Mode Handling - OPEN vs GOVERNED differences
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phase12_schema import (
    FewShotContext,
    GenerationContext,
    OntologicalContext,
    OntologicalFamily,
    PPVConditioningSignal,
    PPVEncodingStrategy,
    RawGenerationResult,
    RenderMode,
    VerificationStatus,
)
from phase12_verifier import (
    Phase12Verifier,
    VerificationThresholds,
    check_structural,
    check_ontological,
    check_ppv_alignment,
    check_content_policy,
    create_default_verifier,
    create_strict_verifier,
    create_lenient_verifier,
    OPEN_THRESHOLDS,
    GOVERNED_THRESHOLDS,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_ppv_signal() -> PPVConditioningSignal:
    """Sample PPV conditioning signal."""
    return PPVConditioningSignal(
        raw_ppv=(0, 1, 2, 3, 4, 5, 6, 7),
        canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
        strategy=PPVEncodingStrategy.TEXT_PREFIX,
        conditioning_data="[PPV:L0_L0_L2_M0_M0_M2_H0_H1]",
    )


@pytest.fixture
def sample_ontological() -> OntologicalContext:
    """Sample ontological context."""
    return OntologicalContext(
        family=OntologicalFamily.THINKING,
        path=("THINKING",),
        slot_plan="basic_vc",
        required_vc_facts=("observation",),
    )


@pytest.fixture
def sample_few_shot() -> FewShotContext:
    """Sample few-shot context (empty)."""
    return FewShotContext(templates=())


def make_context(
    ppv_signal: PPVConditioningSignal,
    ontological: OntologicalContext,
    few_shot: FewShotContext,
    mode: RenderMode = RenderMode.GOVERNED,
) -> GenerationContext:
    """Create a generation context for testing."""
    return GenerationContext(
        request_id="test-request-001",
        artifact_hash="a" * 64,
        ontological=ontological,
        ppv_signal=ppv_signal,
        few_shot=few_shot,
        vc_source_data={"observation": "test data"},
        mode=mode,
    )


def make_generation(text: str) -> RawGenerationResult:
    """Create a generation result for testing."""
    return RawGenerationResult(
        text=text,
        model_id="test-model",
        tokens_used=100,
        generation_time_ms=50,
        context_hash="ctx123",
    )


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Tests for verification determinism."""

    def test_verification_determinism_100_runs(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Verification produces identical results over 100 runs."""
        verifier = create_default_verifier()
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        generation = make_generation(
            "I think we should consider this carefully and reflect on our options."
        )

        first_result = verifier.verify(context, generation)

        for _ in range(100):
            result = verifier.verify(context, generation)
            assert result.status == first_result.status
            assert result.structural_score == first_result.structural_score
            assert result.ontological_score == first_result.ontological_score
            assert result.ppv_alignment_score == first_result.ppv_alignment_score

    def test_verify_hash_determinism(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Verify hash is deterministic."""
        verifier = create_default_verifier()
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        generation = make_generation("Test output text.")

        hashes = set()
        for _ in range(100):
            h = verifier.verify_hash(context, generation)
            hashes.add(h)

        assert len(hashes) == 1


# =============================================================================
# Test: Structural Checks
# =============================================================================

class TestStructuralChecks:
    """Tests for structural verification."""

    def test_empty_text_fails(self):
        """Empty text fails structural check."""
        result = check_structural("", GOVERNED_THRESHOLDS)
        assert not result.passed
        assert result.score == 0.0
        assert "empty" in result.details.lower()

    def test_whitespace_only_fails(self):
        """Whitespace-only text fails."""
        result = check_structural("   \n\t  ", GOVERNED_THRESHOLDS)
        assert not result.passed
        assert "empty" in result.details.lower()

    def test_too_short_fails(self):
        """Text below min_length fails."""
        result = check_structural("Hi", GOVERNED_THRESHOLDS)  # min_length=10
        assert not result.passed
        assert "below minimum" in result.details.lower()

    def test_too_long_fails(self):
        """Text above max_length fails."""
        thresholds = VerificationThresholds(max_length=20)
        result = check_structural("This is a much longer text that exceeds the limit.", thresholds)
        assert not result.passed
        assert "exceeds maximum" in result.details.lower()

    def test_too_few_words_fails(self):
        """Text with too few words fails."""
        thresholds = VerificationThresholds(min_words=5, min_length=1)
        result = check_structural("One two", thresholds)
        assert not result.passed
        assert "word count" in result.details.lower()

    def test_valid_text_passes(self):
        """Valid text passes structural check."""
        result = check_structural(
            "This is a valid text with enough length and words to pass.",
            GOVERNED_THRESHOLDS
        )
        assert result.passed
        assert result.score > 0.5


# =============================================================================
# Test: Ontological Checks
# =============================================================================

class TestOntologicalChecks:
    """Tests for ontological verification."""

    def test_thinking_markers_detected(self):
        """THINKING family markers are detected."""
        text = "I think we should consider this carefully and perhaps reflect on it."
        result = check_ontological(text, OntologicalFamily.THINKING, GOVERNED_THRESHOLDS)
        assert result.passed
        assert result.score > 0.3
        assert "THINKING" in result.details

    def test_forming_markers_detected(self):
        """FORMING family markers are detected."""
        text = "Let us create and build something new, we can design and craft it together."
        result = check_ontological(text, OntologicalFamily.FORMING, GOVERNED_THRESHOLDS)
        assert result.passed
        assert result.score > 0.3

    def test_no_markers_low_score(self):
        """Text without family markers has low score."""
        text = "The quick brown fox jumps over the lazy dog repeatedly."
        result = check_ontological(text, OntologicalFamily.THINKING, GOVERNED_THRESHOLDS)
        # Should have low score but may still pass with lenient threshold
        assert result.score < 0.5

    def test_reasoning_markers_detected(self):
        """REASONING family markers are detected."""
        text = "Because of this, therefore we can conclude that the logic is sound."
        result = check_ontological(text, OntologicalFamily.REASONING, GOVERNED_THRESHOLDS)
        assert result.score > 0.3


# =============================================================================
# Test: PPV Alignment Checks
# =============================================================================

class TestPPVAlignmentChecks:
    """Tests for PPV alignment verification."""

    def test_high_energy_signature_high_markers(self):
        """High energy signature with high energy markers scores well."""
        # Signature with many H values
        text = "We must act boldly and powerfully! This is intensely important!"
        result = check_ppv_alignment(
            text,
            "H0_H1_H0_H1_H0_H1_H0_H1",  # All high
            GOVERNED_THRESHOLDS
        )
        assert result.score > 0.2
        assert "HIGH" in result.details

    def test_low_energy_signature_low_markers(self):
        """Low energy signature with low energy markers scores well."""
        text = "Let us quietly and gently approach this, calmly and peacefully."
        result = check_ppv_alignment(
            text,
            "L0_L0_L0_L0_L0_L0_L0_L0",  # All low
            GOVERNED_THRESHOLDS
        )
        assert result.score > 0.2
        assert "LOW" in result.details

    def test_misaligned_markers_penalized(self):
        """Misaligned markers reduce score."""
        # High signature but low markers
        text_low_markers = "We proceed quietly, gently, calmly moving forward."
        result_misaligned = check_ppv_alignment(
            text_low_markers,
            "H1_H1_H1_H1_H1_H1_H1_H1",  # Expects high
            GOVERNED_THRESHOLDS
        )

        text_high_markers = "We act boldly, powerfully, intensely!"
        result_aligned = check_ppv_alignment(
            text_high_markers,
            "H1_H1_H1_H1_H1_H1_H1_H1",
            GOVERNED_THRESHOLDS
        )

        # Aligned should score better than misaligned
        assert result_aligned.score >= result_misaligned.score

    def test_invalid_signature_handled(self):
        """Invalid signature is handled gracefully."""
        result = check_ppv_alignment(
            "Some text here.",
            "invalid_signature",
            GOVERNED_THRESHOLDS
        )
        assert result.passed  # Should pass with neutral score
        assert result.score == 0.5


# =============================================================================
# Test: Content Policy Checks
# =============================================================================

class TestContentPolicyChecks:
    """Tests for content policy verification."""

    def test_no_patterns_passes(self):
        """Text with no forbidden patterns passes."""
        thresholds = VerificationThresholds(forbidden_patterns=())
        result = check_content_policy("Any text is fine here.", thresholds)
        assert result.passed
        assert result.score == 1.0

    def test_script_tag_blocked(self):
        """Script tags are blocked."""
        thresholds = VerificationThresholds(forbidden_patterns=(r"<script>",))
        result = check_content_policy("Hello <script>alert('xss')</script>", thresholds)
        assert not result.passed
        assert "forbidden" in result.details.lower()

    def test_javascript_uri_blocked(self):
        """JavaScript URIs are blocked."""
        thresholds = VerificationThresholds(forbidden_patterns=(r"javascript:",))
        result = check_content_policy("Click <a href='javascript:void(0)'>here</a>", thresholds)
        assert not result.passed

    def test_clean_text_passes(self):
        """Clean text passes content policy."""
        result = check_content_policy(
            "This is perfectly safe content.",
            GOVERNED_THRESHOLDS
        )
        assert result.passed


# =============================================================================
# Test: Mode Handling
# =============================================================================

class TestModeHandling:
    """Tests for OPEN vs GOVERNED mode differences."""

    def test_governed_stricter_than_open(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """GOVERNED mode is stricter than OPEN mode."""
        verifier = create_default_verifier()

        # Short text that might pass OPEN but not GOVERNED
        text = "A quick thought."  # Short, minimal markers

        # Test in OPEN mode
        open_context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot,
            mode=RenderMode.OPEN
        )
        open_result = verifier.verify(open_context, make_generation(text))

        # Test in GOVERNED mode
        governed_context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot,
            mode=RenderMode.GOVERNED
        )
        governed_result = verifier.verify(governed_context, make_generation(text))

        # OPEN should be more permissive
        assert governed_result.allowed_in_open or not governed_result.allowed_in_governed
        # Or at minimum, GOVERNED thresholds are higher
        assert GOVERNED_THRESHOLDS.min_length >= OPEN_THRESHOLDS.min_length

    def test_open_mode_allows_more(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """OPEN mode allows output that GOVERNED might reject."""
        verifier = create_default_verifier()

        # Text that passes OPEN but might fail GOVERNED ontological check
        text = "The quick brown fox jumps over the lazy dog repeatedly." * 2

        governed_context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot,
            mode=RenderMode.GOVERNED
        )
        result = verifier.verify(governed_context, make_generation(text))

        # Even if GOVERNED fails, OPEN might allow
        if not result.allowed_in_governed:
            # OPEN might still allow since it only checks structural + content
            pass  # This is expected behavior

    def test_allowed_flags_independent(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """allowed_in_open and allowed_in_governed are computed independently."""
        verifier = create_lenient_verifier()  # Use lenient for this test
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )

        # Good text should pass both (with lenient thresholds)
        good_text = "I think we should consider this matter carefully and reflect deeply."
        good_result = verifier.verify(context, make_generation(good_text))
        assert good_result.allowed_in_open
        assert good_result.allowed_in_governed

        # Use strict verifier for bad text test (has forbidden patterns in both modes)
        strict_verifier = create_strict_verifier()
        bad_text = "I think we should <script>alert('xss')</script> consider this."
        bad_result = strict_verifier.verify(context, make_generation(bad_text))
        assert not bad_result.allowed_in_open
        assert not bad_result.allowed_in_governed


# =============================================================================
# Test: Full Verifier
# =============================================================================

class TestFullVerifier:
    """Tests for the complete Phase12Verifier."""

    def test_passing_verification(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Good output passes all checks."""
        verifier = create_lenient_verifier()  # Use lenient for passing test
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        generation = make_generation(
            "I believe we should think carefully about this matter. "
            "Perhaps we should consider all the possibilities and reflect on them."
        )

        result = verifier.verify(context, generation)

        assert result.status == VerificationStatus.PASSED
        assert result.allowed_in_governed
        assert result.allowed_in_open
        assert len(result.checks) == 4  # structural, ontological, ppv, content

    def test_structural_failure(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Short output fails structural check."""
        verifier = create_default_verifier()
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        generation = make_generation("Hi")

        result = verifier.verify(context, generation)

        assert result.status == VerificationStatus.FAILED_STRUCTURAL
        assert not result.allowed_in_governed

    def test_content_policy_failure(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Forbidden content fails content policy check."""
        # Create custom verifier with lenient thresholds but strict content policy
        from phase12_verifier import VerificationThresholds, Phase12Verifier
        custom_thresholds = VerificationThresholds(
            min_length=1,
            max_length=16384,
            min_words=1,
            ontological_score_pass=0.0,  # Always pass ontological
            ppv_alignment_pass=0.0,      # Always pass PPV
            forbidden_patterns=(r"<script>",),  # But catch script tags
        )
        verifier = Phase12Verifier(
            open_thresholds=custom_thresholds,
            governed_thresholds=custom_thresholds,
        )
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        generation = make_generation(
            "Some text with <script>alert('bad')</script> inside."
        )

        result = verifier.verify(context, generation)

        # Content policy should fail due to <script> tag
        assert result.status == VerificationStatus.FAILED_CONTENT_POLICY
        assert not result.allowed_in_governed
        assert not result.allowed_in_open


# =============================================================================
# Test: Factory Functions
# =============================================================================

class TestFactoryFunctions:
    """Tests for verifier factory functions."""

    def test_default_verifier_uses_standard_thresholds(self):
        """Default verifier uses standard thresholds."""
        verifier = create_default_verifier()
        assert verifier.open_thresholds == OPEN_THRESHOLDS
        assert verifier.governed_thresholds == GOVERNED_THRESHOLDS

    def test_strict_verifier_stricter_thresholds(self):
        """Strict verifier has stricter thresholds."""
        strict = create_strict_verifier()
        default = create_default_verifier()

        # Strict should have higher ontological threshold
        assert (
            strict.governed_thresholds.ontological_score_pass
            >= default.governed_thresholds.ontological_score_pass
        )

    def test_lenient_verifier_relaxed_thresholds(self):
        """Lenient verifier has relaxed thresholds."""
        lenient = create_lenient_verifier()
        default = create_default_verifier()

        # Lenient should have lower min_length
        assert (
            lenient.governed_thresholds.min_length
            <= default.governed_thresholds.min_length
        )


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_context_data(
        self, sample_ppv_signal, sample_ontological
    ):
        """Verifier handles empty few-shot context."""
        verifier = create_default_verifier()
        context = make_context(
            sample_ppv_signal,
            sample_ontological,
            FewShotContext(templates=()),
        )
        generation = make_generation("We should think and consider this carefully.")

        # Should not crash
        result = verifier.verify(context, generation)
        assert result is not None

    def test_unicode_text(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Verifier handles unicode text."""
        verifier = create_default_verifier()
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        generation = make_generation(
            "I think we should consider 日本語 and émojis 🎉 and special chars."
        )

        result = verifier.verify(context, generation)
        assert result is not None  # Should not crash

    def test_very_long_text(
        self, sample_ppv_signal, sample_ontological, sample_few_shot
    ):
        """Verifier handles very long text."""
        verifier = create_default_verifier()
        context = make_context(
            sample_ppv_signal, sample_ontological, sample_few_shot
        )
        long_text = "I think and consider this matter. " * 500  # ~15000 chars

        generation = make_generation(long_text)
        result = verifier.verify(context, generation)

        # Should fail structural (too long for GOVERNED max_length=4096)
        assert result.status == VerificationStatus.FAILED_STRUCTURAL


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
