"""
Tests for Phase-12 Template Retriever
=====================================

Test Categories:
    1. Determinism - Same input → same output (100+ runs)
    2. Similarity Calculation - Correct scoring
    3. Retrieval - Templates retrieved in correct order
    4. FewShotContext - Context built correctly
    5. Edge Cases - Boundary conditions
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from phase12_schema import (
    FewShotContext,
    OntologicalFamily,
    RetrievedTemplate,
)
from phase12_retriever import (
    Phase12TemplateRetriever,
    calculate_template_similarity,
    create_default_retriever,
    create_expanded_retriever,
    build_few_shot_context,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_signature() -> str:
    """Sample canonical signature."""
    return "L0_L0_L2_M0_M0_M2_H0_H1"


@pytest.fixture
def all_low_signature() -> str:
    """All-low canonical signature."""
    return "L0_L0_L0_L0_L0_L0_L0_L0"


@pytest.fixture
def all_high_signature() -> str:
    """All-high canonical signature."""
    return "H1_H1_H1_H1_H1_H1_H1_H1"


# =============================================================================
# Test: Determinism
# =============================================================================

class TestDeterminism:
    """Tests for retrieval determinism."""

    def test_retrieval_determinism_100_runs(self, sample_signature):
        """Retrieval produces identical results over 100 runs."""
        retriever = create_default_retriever()

        first_result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            top_k=5,
        )

        for _ in range(100):
            result = retriever.retrieve(
                OntologicalFamily.THINKING,
                sample_signature,
                "basic_vc",
                top_k=5,
            )
            assert len(result) == len(first_result)
            for r, f in zip(result, first_result):
                assert r.template_id == f.template_id
                assert r.similarity_score == f.similarity_score

    def test_retrieval_hash_determinism(self, sample_signature):
        """Retrieval hash is deterministic."""
        retriever = create_default_retriever()

        hashes = set()
        for _ in range(100):
            h = retriever.retrieval_hash(
                OntologicalFamily.THINKING,
                sample_signature,
                "basic_vc",
            )
            hashes.add(h)

        assert len(hashes) == 1

    def test_different_inputs_different_results(
        self, sample_signature, all_low_signature, all_high_signature
    ):
        """Different inputs produce different retrieval results."""
        retriever = create_default_retriever()

        result_1 = retriever.retrieve(
            OntologicalFamily.THINKING, sample_signature, "basic_vc"
        )
        result_2 = retriever.retrieve(
            OntologicalFamily.THINKING, all_low_signature, "basic_vc"
        )
        result_3 = retriever.retrieve(
            OntologicalFamily.THINKING, all_high_signature, "basic_vc"
        )

        # First template should be different (exact match differs)
        assert result_1[0].template_id != result_2[0].template_id
        assert result_2[0].template_id != result_3[0].template_id


# =============================================================================
# Test: Similarity Calculation
# =============================================================================

class TestSimilarityCalculation:
    """Tests for similarity scoring."""

    def test_exact_match_high_similarity(self, sample_signature):
        """Exact match has similarity 1.0."""
        sim = calculate_template_similarity(
            sample_signature, "basic_vc",
            sample_signature, "basic_vc",
        )
        assert sim == 1.0

    def test_different_signature_lower_similarity(self, sample_signature):
        """Different signature has lower similarity."""
        sim = calculate_template_similarity(
            sample_signature, "basic_vc",
            "H1_H1_H1_H1_H1_H1_H1_H1", "basic_vc",
        )
        assert sim < 1.0

    def test_different_slot_plan_lower_similarity(self, sample_signature):
        """Different slot plan has lower similarity."""
        sim_same = calculate_template_similarity(
            sample_signature, "basic_vc",
            sample_signature, "basic_vc",
        )
        sim_diff = calculate_template_similarity(
            sample_signature, "basic_vc",
            sample_signature, "extended_vc",
        )
        assert sim_diff < sim_same

    def test_single_subband_difference(self, sample_signature):
        """Single subband difference has high but not perfect similarity."""
        # Change just one subband
        modified = "L0_L0_L2_M0_M0_M2_H0_H0"  # Last H1 → H0
        sim = calculate_template_similarity(
            sample_signature, "basic_vc",
            modified, "basic_vc",
        )
        assert 0.7 < sim < 1.0  # Should be high but not 1.0

    def test_all_different_low_similarity(self, all_low_signature, all_high_signature):
        """Completely different signatures have low similarity."""
        sim = calculate_template_similarity(
            all_low_signature, "basic_vc",
            all_high_signature, "basic_vc",
        )
        # Band similarity should still give some score (both are consistent)
        assert sim < 0.5  # But overall low


# =============================================================================
# Test: Retrieval
# =============================================================================

class TestRetrieval:
    """Tests for template retrieval."""

    def test_retrieves_correct_count(self, sample_signature):
        """Retrieves requested number of templates."""
        retriever = create_default_retriever()

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            top_k=3,
        )
        assert len(result) == 3

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            top_k=7,
        )
        assert len(result) == 7

    def test_ordered_by_similarity(self, sample_signature):
        """Templates are ordered by similarity (descending)."""
        retriever = create_default_retriever()

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            top_k=10,
        )

        # Verify descending order
        for i in range(len(result) - 1):
            assert result[i].similarity_score >= result[i + 1].similarity_score

    def test_first_result_is_exact_match(self, sample_signature):
        """First result should be exact match with similarity 1.0."""
        retriever = create_default_retriever()

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
        )

        assert result[0].similarity_score == 1.0
        assert result[0].variant_id == sample_signature

    def test_all_families_supported(self, sample_signature):
        """All ontological families return valid templates."""
        retriever = create_default_retriever()

        for family in OntologicalFamily:
            result = retriever.retrieve(
                family,
                sample_signature,
                "basic_vc",
                top_k=3,
            )
            assert len(result) == 3
            assert all(t.family == family.value for t in result)

    def test_template_has_correct_structure(self, sample_signature):
        """Retrieved templates have correct structure."""
        retriever = create_default_retriever()

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
        )

        for template in result:
            assert isinstance(template, RetrievedTemplate)
            assert template.template_id.startswith("tpl_")
            assert len(template.template_text) > 0
            assert 0.0 <= template.similarity_score <= 1.0
            assert template.family == "THINKING"


# =============================================================================
# Test: Caching
# =============================================================================

class TestCaching:
    """Tests for retriever caching."""

    def test_cache_returns_same_objects(self, sample_signature):
        """Cache returns same tuple objects."""
        retriever = create_default_retriever()

        result1 = retriever.retrieve(
            OntologicalFamily.THINKING, sample_signature, "basic_vc", 5
        )
        result2 = retriever.retrieve(
            OntologicalFamily.THINKING, sample_signature, "basic_vc", 5
        )

        # Should be same tuple object (cached)
        assert result1 is result2

    def test_clear_cache_works(self, sample_signature):
        """Clearing cache causes new retrieval."""
        retriever = create_default_retriever()

        result1 = retriever.retrieve(
            OntologicalFamily.THINKING, sample_signature, "basic_vc", 5
        )
        retriever.clear_cache()
        result2 = retriever.retrieve(
            OntologicalFamily.THINKING, sample_signature, "basic_vc", 5
        )

        # Should be different tuple objects (not cached)
        assert result1 is not result2
        # But same content
        assert result1 == result2


# =============================================================================
# Test: FewShotContext Building
# =============================================================================

class TestFewShotContextBuilding:
    """Tests for FewShotContext building."""

    def test_build_few_shot_context(self, sample_signature):
        """build_few_shot_context creates valid context."""
        retriever = create_default_retriever()

        context = build_few_shot_context(
            retriever,
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            max_examples=3,
        )

        assert isinstance(context, FewShotContext)
        assert len(context.templates) >= 3
        assert context.max_examples == 3

    def test_get_top_k_from_context(self, sample_signature):
        """FewShotContext.get_top_k works correctly."""
        retriever = create_default_retriever()

        context = build_few_shot_context(
            retriever,
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            max_examples=5,
        )

        top_3 = context.get_top_k(3)
        assert len(top_3) == 3

        top_default = context.get_top_k()  # Uses max_examples
        assert len(top_default) == 5


# =============================================================================
# Test: Factory Functions
# =============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_default_retriever(self):
        """Default retriever has standard settings."""
        retriever = create_default_retriever()
        assert retriever.num_candidates == 20

    def test_expanded_retriever(self):
        """Expanded retriever has more candidates."""
        retriever = create_expanded_retriever(50)
        assert retriever.num_candidates == 50


# =============================================================================
# Test: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_top_k_zero(self, sample_signature):
        """top_k=0 returns empty tuple."""
        retriever = create_default_retriever()

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            top_k=0,
        )
        assert result == ()

    def test_top_k_exceeds_candidates(self, sample_signature):
        """top_k exceeding candidates returns all available."""
        retriever = Phase12TemplateRetriever(num_candidates=5)

        result = retriever.retrieve(
            OntologicalFamily.THINKING,
            sample_signature,
            "basic_vc",
            top_k=100,  # More than candidates
        )
        assert len(result) <= 100

    def test_template_text_contains_family_info(self, sample_signature):
        """Template text contains relevant family information."""
        retriever = create_default_retriever()

        for family in [OntologicalFamily.THINKING, OntologicalFamily.FORMING]:
            result = retriever.retrieve(family, sample_signature, "basic_vc", 1)
            # Template should contain family-relevant keywords
            text = result[0].template_text.lower()
            if family == OntologicalFamily.THINKING:
                assert any(word in text for word in ["think", "consider", "reflect"])
            elif family == OntologicalFamily.FORMING:
                assert any(word in text for word in ["create", "build", "shape"])

    def test_energy_level_reflected_in_template(
        self, all_low_signature, all_high_signature
    ):
        """Template text reflects energy level from signature."""
        retriever = create_default_retriever()

        low_result = retriever.retrieve(
            OntologicalFamily.THINKING,
            all_low_signature,
            "basic_vc",
            top_k=1,
        )
        high_result = retriever.retrieve(
            OntologicalFamily.THINKING,
            all_high_signature,
            "basic_vc",
            top_k=1,
        )

        # Low energy template should contain low energy words
        assert "LOW" in low_result[0].template_text or "quietly" in low_result[0].template_text.lower()
        # High energy template should contain high energy words
        assert "HIGH" in high_result[0].template_text or "boldly" in high_result[0].template_text.lower()


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
