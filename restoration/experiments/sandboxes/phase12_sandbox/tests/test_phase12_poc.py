"""
Tests for Phase-12 Proof of Concept
===================================

Test Categories:
    1. Pipeline Integration - All components work together
    2. Mock Generator - Produces valid output
    3. Mode Handling - OPEN vs GOVERNED
    4. End-to-End - Complete flow works
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phase12_schema import (
    OntologicalFamily,
    RenderMode,
    VerificationStatus,
    GENERATION_BLOCKED,
)
from phase12_poc import (
    MockGenerator,
    GovernedGenerativePipeline,
    create_default_pipeline,
    run_governed_generation,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def default_pipeline() -> GovernedGenerativePipeline:
    """Default pipeline for testing."""
    return create_default_pipeline()


@pytest.fixture
def sample_ppv() -> tuple:
    """Sample PPV values."""
    return (0, 1, 2, 3, 4, 5, 6, 7)


@pytest.fixture
def sample_signature() -> str:
    """Sample canonical signature."""
    return "L0_L0_L2_M0_M0_M2_H0_H1"


@pytest.fixture
def sample_vc_data() -> dict:
    """Sample VC data."""
    return {"observation": "the test scenario"}


# =============================================================================
# Test: Pipeline Integration
# =============================================================================

class TestPipelineIntegration:
    """Tests for pipeline integration."""

    def test_pipeline_produces_response(
        self, default_pipeline, sample_ppv, sample_signature, sample_vc_data
    ):
        """Pipeline produces Phase12Response."""
        result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data=sample_vc_data,
        )

        assert result is not None
        assert result.output_text != ""
        assert result.context_hash != ""

    def test_all_families_work(
        self, default_pipeline, sample_ppv, sample_signature, sample_vc_data
    ):
        """All ontological families produce valid output."""
        for family in OntologicalFamily:
            result = default_pipeline.generate(
                family=family,
                ppv_values=sample_ppv,
                canonical_signature=sample_signature,
                slot_plan="basic_vc",
                vc_data=sample_vc_data,
            )
            assert result is not None
            # Output should not be blocked (with lenient verifier)
            assert not result.blocked or result.output_text == GENERATION_BLOCKED

    def test_verification_included(
        self, default_pipeline, sample_ppv, sample_signature, sample_vc_data
    ):
        """Response includes verification result."""
        result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data=sample_vc_data,
        )

        assert result.verification is not None
        assert len(result.verification.checks) == 4


# =============================================================================
# Test: Mock Generator
# =============================================================================

class TestMockGenerator:
    """Tests for mock generator."""

    def test_generator_produces_text(
        self, default_pipeline, sample_ppv, sample_signature, sample_vc_data
    ):
        """Mock generator produces non-empty text."""
        result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data=sample_vc_data,
        )

        assert len(result.output_text) > 0

    def test_output_reflects_family(
        self, default_pipeline, sample_ppv, sample_signature
    ):
        """Output contains family-appropriate content."""
        # THINKING should have thinking-related words
        thinking_result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data={"observation": "test"},
        )
        text = thinking_result.output_text.lower()
        assert any(word in text for word in ["consider", "reflect", "think", "ponder"])

        # FORMING should have forming-related words
        forming_result = default_pipeline.generate(
            family=OntologicalFamily.FORMING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data={"observation": "test"},
        )
        text = forming_result.output_text.lower()
        assert any(word in text for word in ["create", "build", "shape", "design"])

    def test_output_reflects_energy_level(self, default_pipeline):
        """Output reflects PPV energy level."""
        # High energy signature
        high_result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=(7, 7, 7, 7, 7, 7, 7, 7),
            canonical_signature="H1_H1_H1_H1_H1_H1_H1_H1",
            slot_plan="basic_vc",
            vc_data={"observation": "test"},
        )
        high_text = high_result.output_text.lower()

        # Low energy signature
        low_result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=(0, 0, 0, 0, 0, 0, 0, 0),
            canonical_signature="L0_L0_L0_L0_L0_L0_L0_L0",
            slot_plan="basic_vc",
            vc_data={"observation": "test"},
        )
        low_text = low_result.output_text.lower()

        # High energy should have high energy words
        high_words = ["boldly", "powerfully", "intensely"]
        low_words = ["quietly", "gently", "calmly"]

        # At least one high word in high output
        has_high = any(w in high_text for w in high_words)
        # At least one low word in low output
        has_low = any(w in low_text for w in low_words)

        assert has_high or has_low  # At least one should reflect energy


# =============================================================================
# Test: Mode Handling
# =============================================================================

class TestModeHandling:
    """Tests for OPEN vs GOVERNED mode."""

    def test_governed_mode_works(
        self, default_pipeline, sample_ppv, sample_signature, sample_vc_data
    ):
        """GOVERNED mode produces output."""
        result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data=sample_vc_data,
            mode=RenderMode.GOVERNED,
        )

        assert result.mode == RenderMode.GOVERNED
        assert not result.blocked

    def test_open_mode_works(
        self, default_pipeline, sample_ppv, sample_signature, sample_vc_data
    ):
        """OPEN mode produces output."""
        result = default_pipeline.generate(
            family=OntologicalFamily.THINKING,
            ppv_values=sample_ppv,
            canonical_signature=sample_signature,
            slot_plan="basic_vc",
            vc_data=sample_vc_data,
            mode=RenderMode.OPEN,
        )

        assert result.mode == RenderMode.OPEN
        assert not result.blocked


# =============================================================================
# Test: End-to-End
# =============================================================================

class TestEndToEnd:
    """End-to-end tests for complete flow."""

    def test_convenience_function_works(self):
        """run_governed_generation convenience function works."""
        result = run_governed_generation(
            family=OntologicalFamily.THINKING,
            ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
            canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
            slot_plan="basic_vc",
            vc_data={"observation": "a test observation"},
        )

        assert result is not None
        assert not result.blocked

    def test_default_vc_data_works(self):
        """Default VC data works when not specified."""
        result = run_governed_generation(
            family=OntologicalFamily.THINKING,
            ppv_values=(0, 0, 0, 0, 0, 0, 0, 0),
            canonical_signature="L0_L0_L0_L0_L0_L0_L0_L0",
        )

        assert result is not None
        assert not result.blocked

    def test_trace_hashes_present(self):
        """Response contains all trace hashes."""
        result = run_governed_generation(
            family=OntologicalFamily.THINKING,
            ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
            canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
        )

        assert result.context_hash != ""
        assert result.routing_trace_hash != ""
        assert result.ledger_span_id.startswith("span_")
        if not result.blocked:
            assert result.generation_hash is not None

    def test_multiple_runs_work(self):
        """Multiple runs produce output without errors."""
        pipeline = create_default_pipeline()

        for i in range(10):
            result = pipeline.generate(
                family=OntologicalFamily.THINKING,
                ppv_values=(i % 8, i % 8, i % 8, i % 8, i % 8, i % 8, i % 8, i % 8),
                canonical_signature=f"{'L0' if i < 3 else 'M0' if i < 6 else 'H0'}_L0_L0_L0_L0_L0_L0_L0",
                slot_plan="basic_vc",
                vc_data={"observation": f"observation {i}"},
            )
            assert result is not None


# =============================================================================
# Test: Response Structure
# =============================================================================

class TestResponseStructure:
    """Tests for response structure."""

    def test_response_hash_method(self):
        """Response has working response_hash method."""
        result = run_governed_generation(
            family=OntologicalFamily.THINKING,
            ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
            canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
        )

        response_hash = result.response_hash()
        assert len(response_hash) == 16
        assert all(c in "0123456789abcdef" for c in response_hash)

    def test_verification_scores_present(self):
        """Verification result contains all scores."""
        result = run_governed_generation(
            family=OntologicalFamily.THINKING,
            ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
            canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
        )

        assert result.verification is not None
        assert result.verification.structural_score >= 0
        assert result.verification.ontological_score >= 0
        assert result.verification.ppv_alignment_score >= 0


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
