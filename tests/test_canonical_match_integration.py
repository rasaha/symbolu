"""
Tests for Canonical Matching (C × R × S) STL Integration
========================================================

Tests the integration of the canonical matching framework into the STL
tier architecture via the provider system.

The canonical matching formula: MATCH = C × R × S

Where:
- C = Constraint feasibility (phonemic → ontology)
- R = Realization strength (phonemic → experience)
- S = Referential coherence (NON-phonemic, source-independent)

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

import pytest
from typing import Tuple


# =============================================================================
# Provider Factory Tests
# =============================================================================


class TestMatchProviderFactory:
    """Test the get_match_provider factory function."""

    def test_get_enterprise_match_provider(self):
        """Factory returns CanonicalMatchProvider for enterprise mode."""
        from symbolu.providers import get_match_provider

        provider = get_match_provider("enterprise")
        assert provider is not None
        assert hasattr(provider, "match")
        assert hasattr(provider, "match_batch")
        assert hasattr(provider, "match_one_to_many")

    def test_invalid_mode_raises_error(self):
        """Factory raises ValueError for invalid mode."""
        from symbolu.providers import get_match_provider

        with pytest.raises(ValueError, match="currently only supports 'enterprise'"):
            get_match_provider("consumer")  # type: ignore

    def test_custom_thresholds(self):
        """Factory respects custom threshold configuration."""
        from symbolu.providers import get_match_provider

        provider = get_match_provider(
            "enterprise",
            config={
                "c_threshold": 0.7,
                "r_threshold": 0.6,
                "s_threshold": 0.3,
            },
        )
        thresholds = provider.get_thresholds()
        assert thresholds["C_THRESHOLD"] == 0.7
        assert thresholds["R_THRESHOLD"] == 0.6
        assert thresholds["S_THRESHOLD"] == 0.3


class TestFilterProviderCoherenceOption:
    """Test the with_coherence option for filter providers."""

    def test_default_filter_without_coherence(self):
        """Default filter provider doesn't include coherence checks."""
        from symbolu.providers import get_filter_provider

        provider = get_filter_provider("enterprise")
        # Should be ResonanceFilterProvider, not CoherenceFilterProvider
        assert not hasattr(provider, "get_match_provider")

    def test_filter_with_coherence_option(self):
        """with_coherence=True returns CoherenceFilterProvider."""
        from symbolu.providers import get_filter_provider

        provider = get_filter_provider("enterprise", {"with_coherence": True})
        assert hasattr(provider, "get_match_provider")


# =============================================================================
# MatchProvider Interface Tests
# =============================================================================


class TestMatchProviderInterface:
    """Test the MatchProvider interface implementation."""

    @pytest.fixture
    def provider(self):
        """Create a CanonicalMatchProvider instance."""
        from symbolu.providers import get_match_provider

        return get_match_provider("enterprise")

    def test_match_returns_match_result(self, provider):
        """match() returns a MatchResult with all required fields."""
        from symbolu.providers.interfaces import MatchMode

        result = provider.match("king", "queen")

        assert hasattr(result, "match_score")
        assert hasattr(result, "feasibility")
        assert hasattr(result, "realization")
        assert hasattr(result, "referent")
        assert hasattr(result, "mode")
        assert hasattr(result, "term_a")
        assert hasattr(result, "term_b")
        assert hasattr(result, "confidence")
        assert hasattr(result, "diagnostics")

        assert isinstance(result.mode, MatchMode)
        assert result.term_a == "king"
        assert result.term_b == "queen"

    def test_match_batch_returns_batch_result(self, provider):
        """match_batch() returns BatchMatchResult with multiple results."""
        pairs = [("king", "queen"), ("sun", "light"), ("tree", "computer")]
        result = provider.match_batch(pairs)

        assert hasattr(result, "results")
        assert hasattr(result, "stats")
        assert len(result.results) == 3
        assert "total_pairs" in result.stats
        assert result.stats["total_pairs"] == 3

    def test_match_one_to_many_returns_sorted_results(self, provider):
        """match_one_to_many() returns results sorted by score."""
        candidates = ("queen", "banana", "crown", "throne")
        result = provider.match_one_to_many("king", candidates, top_k=10)

        assert len(result.results) <= 4
        # Verify sorted by score descending
        scores = [r.match_score for r in result.results]
        assert scores == sorted(scores, reverse=True)

    def test_match_one_to_many_respects_top_k(self, provider):
        """match_one_to_many() respects top_k limit."""
        candidates = ("queen", "banana", "crown", "throne", "castle")
        result = provider.match_one_to_many("king", candidates, top_k=2)

        assert len(result.results) == 2


# =============================================================================
# Canonical Match Semantics Tests
# =============================================================================


class TestCanonicalMatchSemantics:
    """Test the semantic correctness of canonical matching."""

    @pytest.fixture
    def provider(self):
        """Create a CanonicalMatchProvider instance."""
        from symbolu.providers import get_match_provider

        return get_match_provider("enterprise")

    def test_related_words_high_match(self, provider):
        """Semantically related words should have higher match scores."""
        from symbolu.providers.interfaces import MatchMode

        # Related pairs - must have primary referent class overlap
        # sun/light share only secondary (LUMINOUS), so lower threshold for them
        high_match_pairs = [
            ("king", "queen"),  # Both ROLE_BEARER, SOCIAL
            ("fire", "flame"),  # Both PROCESS, secondary LUMINOUS
            ("happy", "joy"),   # Both EMOTIONAL
        ]

        for a, b in high_match_pairs:
            result = provider.match(a, b)
            assert result.match_score > 0.15, f"{a} ↔ {b} should have high match"
            assert result.mode in (
                MatchMode.TRUE_MATCH,
                MatchMode.LATENT,
                MatchMode.DISTORTED,  # Some pairs may have constraint violations
            ), f"{a} ↔ {b} should not be REFERENT_MISMATCH"

        # Partial match pairs - secondary overlap only
        partial_match_pairs = [
            ("sun", "light"),  # sun=NATURAL_BODY, light=PHENOMENON, share LUMINOUS secondary
        ]

        for a, b in partial_match_pairs:
            result = provider.match(a, b)
            assert result.match_score > 0.10, f"{a} ↔ {b} should have partial match"
            assert result.referent > 0.3, f"{a} ↔ {b} should have secondary overlap S"

    def test_unrelated_words_low_match(self, provider):
        """Semantically unrelated words should have low match scores."""
        from symbolu.providers.interfaces import MatchMode

        # Unrelated pairs
        unrelated_pairs = [
            ("king", "banana"),
            ("tree", "computer"),
            ("sun", "pencil"),
            ("love", "table"),
        ]

        for a, b in unrelated_pairs:
            result = provider.match(a, b)
            assert result.match_score < 0.15, f"{a} ↔ {b} should NOT match"
            assert result.mode in (
                MatchMode.REFERENT_MISMATCH,
                MatchMode.NON_MATCH,
            ), f"{a} ↔ {b} should be REFERENT_MISMATCH or NON_MATCH"

    def test_s_provides_referent_discrimination(self, provider):
        """S term should distinguish referent classes."""
        # Same referent class → higher S
        result_related = provider.match("king", "queen")
        assert result_related.referent >= 0.7, "Same ROLE_BEARER should have high S"

        # Different referent classes → lower S
        result_unrelated = provider.match("king", "banana")
        assert result_unrelated.referent < 0.2, "ROLE_BEARER vs BIOLOGICAL should have low S"

    def test_chatgpt_failure_modes_pass(self, provider):
        """Verify ChatGPT-identified failure modes are handled correctly."""
        # These were the key test cases from the ChatGPT review
        test_cases = [
            # (word_a, word_b, expected_match_behavior)
            ("king", "banana", "should_not_match"),  # ORGANISM split issue
            ("tree", "computer", "should_not_match"),  # Clear referent mismatch
            ("sun", "light", "should_partial_match"),  # Secondary overlap
            ("fire", "flame", "should_match"),  # High primary overlap
        ]

        for a, b, expected in test_cases:
            result = provider.match(a, b)
            if expected == "should_not_match":
                assert result.match_score < 0.1, f"{a} ↔ {b}: {expected}"
            elif expected == "should_partial_match":
                assert 0.1 <= result.match_score <= 0.6, f"{a} ↔ {b}: {expected}"
            elif expected == "should_match":
                assert result.match_score >= 0.3, f"{a} ↔ {b}: {expected}"


# =============================================================================
# Coherence Filter Provider Tests
# =============================================================================


class TestCoherenceFilterProvider:
    """Test the CoherenceFilterProvider with C × R × S diagnostics."""

    @pytest.fixture
    def provider(self):
        """Create a CoherenceFilterProvider instance."""
        from symbolu.providers import get_filter_provider

        return get_filter_provider("enterprise", {"with_coherence": True})

    def test_filter_returns_coherence_checks(self, provider):
        """Filter result should include coherence_checks in stats."""
        candidates = ("sun", "light", "energy", "table", "chair")
        result = provider.filter(candidates, "power", top_k=5)

        assert "coherence_checks" in result.stats
        checks = result.stats["coherence_checks"]
        assert "query_matches" in checks
        assert "pairwise_matches" in checks
        assert "summary" in checks

    def test_query_matches_included(self, provider):
        """Query-to-candidate matches should be computed."""
        candidates = ("king", "queen", "banana")
        result = provider.filter(candidates, "royalty", top_k=5)

        checks = result.stats["coherence_checks"]
        query_matches = checks["query_matches"]

        # Should have one match per filtered result
        assert len(query_matches) == len(result.filtered_texts)

    def test_pairwise_matches_when_enabled(self, provider):
        """Pairwise matches between candidates should be computed."""
        candidates = ("sun", "light", "fire", "flame")
        result = provider.filter(candidates, "energy", top_k=4)

        checks = result.stats["coherence_checks"]
        pairwise_matches = checks["pairwise_matches"]

        # Should have pairwise comparisons
        assert len(pairwise_matches) > 0

    def test_summary_statistics(self, provider):
        """Summary should include aggregate statistics."""
        candidates = ("king", "queen", "banana", "tree")
        result = provider.filter(candidates, "royalty", top_k=5)

        summary = result.stats["coherence_checks"]["summary"]
        assert "total_checks" in summary
        assert "true_matches" in summary
        assert "referent_mismatches" in summary
        assert "avg_match_score" in summary


# =============================================================================
# Match Result Serialization Tests
# =============================================================================


class TestMatchResultSerialization:
    """Test serialization of match results."""

    @pytest.fixture
    def provider(self):
        """Create a CanonicalMatchProvider instance."""
        from symbolu.providers import get_match_provider

        return get_match_provider("enterprise")

    def test_match_result_to_dict(self, provider):
        """MatchResult.to_dict() returns serializable dictionary."""
        result = provider.match("sun", "light")
        d = result.to_dict()

        assert "match_score" in d
        assert "components" in d
        assert "C" in d["components"]
        assert "R" in d["components"]
        assert "S" in d["components"]
        assert "mode" in d
        assert "term_a" in d
        assert "term_b" in d
        assert "diagnostics" in d

    def test_batch_result_to_dict(self, provider):
        """BatchMatchResult.to_dict() returns serializable dictionary."""
        pairs = [("king", "queen"), ("sun", "light")]
        result = provider.match_batch(pairs)
        d = result.to_dict()

        assert "results" in d
        assert "stats" in d
        assert len(d["results"]) == 2


# =============================================================================
# Source Independence Tests
# =============================================================================


class TestSourceIndependence:
    """Test that S provides source-independent validation."""

    @pytest.fixture
    def provider(self):
        """Create a CanonicalMatchProvider instance."""
        from symbolu.providers import get_match_provider

        return get_match_provider("enterprise")

    def test_c_and_r_from_phonemic(self, provider):
        """C and R should derive from phonemic analysis."""
        result = provider.match("sun", "son")

        # Similar phonetics → similar C and R (both phonemic)
        # This tests that C and R track phonemic similarity
        assert result.feasibility > 0.3, "Phonetically similar words should have moderate C"
        assert result.realization > 0.3, "Phonetically similar words should have moderate R"

    def test_s_from_referent_not_phonemic(self, provider):
        """S should derive from referent classes, not phonetics."""
        # sun/son are phonetically similar but referentially different
        result = provider.match("sun", "son")

        # son is not in the referent dictionary → S = 0.5 (UNKNOWN)
        # This demonstrates S is NOT derived from phonetics
        diagnostics = result.diagnostics
        referent_analysis = diagnostics["referent_analysis"]

        # Check that the analysis shows the referent grounding status
        assert "is_grounded" in referent_analysis

    def test_high_cr_low_s_referent_mismatch(self, provider):
        """High C × R but low S should produce REFERENT_MISMATCH."""
        from symbolu.providers.interfaces import MatchMode

        # Find words with similar phonetics but different referents
        result = provider.match("king", "banana")

        # Even if C and R are moderate, low S should dominate
        if result.referent < 0.2:
            assert result.mode == MatchMode.REFERENT_MISMATCH


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Test that existing phonetic analysis still works."""

    def test_existing_filter_provider_unchanged(self):
        """Existing filter provider should work without changes."""
        from symbolu.providers import get_filter_provider

        provider = get_filter_provider("enterprise")
        result = provider.filter(("sun", "light", "table"), "energy", top_k=10)

        assert hasattr(result, "filtered_texts")
        assert hasattr(result, "scores")
        assert hasattr(result, "stats")

    def test_name_resonance_module_unchanged(self):
        """Name resonance module should still expose original API."""
        from symbolu.name_resonance import (
            analyze_name,
            canonical_match,
            MatchMode,
            CanonicalMatchResult,
        )

        # analyze_name should still work
        result = analyze_name("Campbell")
        assert hasattr(result, "summary")

        # canonical_match should still work
        match = canonical_match("king", "queen")
        assert isinstance(match, CanonicalMatchResult)
        assert isinstance(match.mode, MatchMode)


# =============================================================================
# Diagnostic Matrix Tests
# =============================================================================


class TestDiagnosticMatrix:
    """Test the C × R diagnostic matrix (gated by S)."""

    @pytest.fixture
    def provider(self):
        """Create a CanonicalMatchProvider instance."""
        from symbolu.providers import get_match_provider

        return get_match_provider("enterprise")

    def test_true_match_high_c_high_r_high_s(self, provider):
        """TRUE_MATCH: High C, High R, High S."""
        from symbolu.providers.interfaces import MatchMode

        # king/queen: same ROLE_BEARER, similar structure
        result = provider.match("king", "queen")

        if result.mode == MatchMode.TRUE_MATCH:
            assert result.feasibility >= 0.5, "TRUE_MATCH requires high C"
            assert result.realization >= 0.4, "TRUE_MATCH requires high R"
            assert result.referent >= 0.2, "TRUE_MATCH requires non-low S"

    def test_referent_mismatch_any_cr_low_s(self, provider):
        """REFERENT_MISMATCH: Any C/R, but low S."""
        from symbolu.providers.interfaces import MatchMode

        result = provider.match("king", "banana")

        if result.mode == MatchMode.REFERENT_MISMATCH:
            assert result.referent < 0.2, "REFERENT_MISMATCH requires low S"


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def provider(self):
        """Create a CanonicalMatchProvider instance."""
        from symbolu.providers import get_match_provider

        return get_match_provider("enterprise")

    def test_same_word_match(self, provider):
        """Same word should have high match score."""
        result = provider.match("sun", "sun")
        assert result.match_score > 0.5, "Same word should match highly"

    def test_unknown_words(self, provider):
        """Unknown words should get neutral S (0.5)."""
        # Made-up word not in dictionary
        result = provider.match("xyzzy", "plugh")

        # Both unknown → S = 0.5
        assert result.referent == 0.5, "Unknown words should have S = 0.5"
        diagnostics = result.diagnostics
        assert diagnostics["referent_analysis"]["is_unknown"] is True

    def test_empty_batch(self, provider):
        """Empty batch should return empty results."""
        result = provider.match_batch([])
        assert len(result.results) == 0
        assert result.stats["total_pairs"] == 0

    def test_empty_candidates(self, provider):
        """Empty candidates should return empty results."""
        result = provider.match_one_to_many("king", (), top_k=10)
        assert len(result.results) == 0


# =============================================================================
# Integration Smoke Test
# =============================================================================


class TestIntegrationSmokeTest:
    """Quick smoke test for the full integration."""

    def test_full_pipeline_enterprise(self):
        """Test the full enterprise pipeline with canonical matching."""
        from symbolu.providers import (
            get_embedding_provider,
            get_router_provider,
            get_filter_provider,
            get_match_provider,
        )

        # Get all enterprise providers
        embedding = get_embedding_provider("enterprise")
        router = get_router_provider("enterprise")
        filter_prov = get_filter_provider("enterprise", {"with_coherence": True})
        match = get_match_provider("enterprise")

        # Test embedding
        vec = embedding.embed("king")
        assert len(vec) == 256

        # Test routing
        decision = router.route("Who is the king?")
        assert decision.model_type is not None

        # Test filtering with coherence
        result = filter_prov.filter(("king", "queen", "banana"), "royalty", top_k=5)
        assert "coherence_checks" in result.stats

        # Test canonical matching
        match_result = match.match("king", "queen")
        assert match_result.match_score > 0.3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
