"""
Symbol-U v3.0 - Core & RAG Integration Tests
=============================================
Integration tests that validate the full RAG → Core stitching pipeline:

Flow: RAG → rag.stitching.pipeline → core.stitching.stitching_engine

This test simulates the complete data flow from document indexing through
RAG retrieval to Core stitching preparation. Since Core stitching methods
are currently placeholders (NotImplementedError), we test the integration
points and data compatibility.

All tests are:
- Deterministic
- LLM-free
- Offline (no network calls)
"""

import os
import tempfile
from typing import Any, Dict, List

import pytest

# RAG imports
from symbolu.rag.stitching.pipeline import (
    index_corpus,
    run_rag,
    run_rag_multi,
    list_indexed_corpora,
    corpus_stats,
)
from symbolu.rag.vectorstore.memory_store import (
    MemoryVectorStore,
    reset_global_store,
)
from symbolu.rag.utils.types import CandidateEntry, Document
from symbolu.rag.embeddings.encoder import embed
from symbolu.rag.indexing.indexer import build_index, chunk_text
from symbolu.rag.retrieval.retriever import retrieve

# Core imports
from symbolu.core.stitching.stitching_engine import StitchingEngine
from symbolu.core.stitching.objective import StitchingObjective
from symbolu.core.stitching.penalties import PenaltyCalculator
from symbolu.core.models import (
    CandidateResponse,
    BhavaState,
    EntropyState,
    AnalysisResult,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fresh_store() -> MemoryVectorStore:
    """Create a fresh MemoryVectorStore instance."""
    return MemoryVectorStore()


@pytest.fixture(autouse=True)
def reset_store_fixture():
    """Reset global store before and after each test."""
    reset_global_store()
    yield
    reset_global_store()


@pytest.fixture
def integration_documents() -> List[Dict[str, str]]:
    """
    Create a diverse set of documents for integration testing.
    These cover multiple domains to test retrieval relevance.
    """
    return [
        {
            "filename": "philosophy_consciousness.txt",
            "content": (
                "Consciousness is the state of being aware of one's surroundings. "
                "Philosophers have debated the nature of consciousness for centuries. "
                "The hard problem of consciousness asks why we have subjective experiences. "
                "Panpsychism suggests consciousness is a fundamental feature of reality."
            )
        },
        {
            "filename": "ai_machine_learning.txt",
            "content": (
                "Artificial intelligence aims to create machines that can think. "
                "Machine learning uses data to train predictive models. "
                "Deep learning employs neural networks with many hidden layers. "
                "Reinforcement learning trains agents through rewards and penalties."
            )
        },
        {
            "filename": "yoga_meditation.txt",
            "content": (
                "Yoga is an ancient practice combining physical postures and breathing. "
                "Meditation cultivates awareness and inner peace. "
                "The eight limbs of yoga include ethical guidelines and meditation. "
                "Pranayama refers to breath control techniques in yoga."
            )
        },
        {
            "filename": "symbolism_language.txt",
            "content": (
                "Symbols carry meaning beyond their literal representation. "
                "Language uses symbols to communicate complex ideas. "
                "Metaphors connect abstract concepts to concrete experiences. "
                "Archetypes are universal symbols found across cultures."
            )
        },
    ]


@pytest.fixture
def temp_corpus_directory(integration_documents: List[Dict[str, str]]):
    """Create a temporary directory with test documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        for doc in integration_documents:
            filepath = os.path.join(tmpdir, doc["filename"])
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(doc["content"])
        yield tmpdir


@pytest.fixture
def indexed_integration_corpus(
    temp_corpus_directory: str, fresh_store: MemoryVectorStore
) -> tuple:
    """Index the integration test corpus."""
    corpus_id = "integration_test_corpus"
    chunk_count = index_corpus(
        corpus_id,
        temp_corpus_directory,
        store=fresh_store,
        chunk_size=200
    )
    return corpus_id, fresh_store, chunk_count


# =============================================================================
# RAG → Core Data Flow Tests
# =============================================================================


class TestRAGToCoreDataFlow:
    """Tests for the data flow from RAG to Core stitching."""

    def test_full_pipeline_no_exceptions(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """
        Test that the full RAG → Core pipeline runs without exceptions.

        Steps:
        1. Query RAG for relevant chunks
        2. Transform results to CandidateEntry
        3. Prepare data for Core stitching
        4. Verify Core stitching interface is callable (raises NotImplementedError)
        """
        corpus_id, store, _ = indexed_integration_corpus

        # Step 1: Run RAG query
        query = "consciousness awareness meditation"
        rag_results = run_rag(query, corpus_id, store=store, top_k=5)

        # Step 2: Verify results are CandidateEntry objects
        assert isinstance(rag_results, list)
        for entry in rag_results:
            assert isinstance(entry, CandidateEntry)

        # Step 3: Convert to Core-compatible CandidateResponse
        core_candidates = []
        for entry in rag_results:
            candidate = CandidateResponse(
                text=entry.text,
                score=entry.score,
                metadata={
                    "source": entry.source,
                    "rag_metadata": entry.metadata
                }
            )
            core_candidates.append(candidate)

        # Step 4: Verify Core stitching accepts the input format
        engine = StitchingEngine()
        # Core is a placeholder, so it raises NotImplementedError
        with pytest.raises(NotImplementedError):
            engine.score_candidates(core_candidates)

        # But we verified the data flow is correct
        assert len(core_candidates) == len(rag_results)

    def test_rag_results_structure_for_core(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test that RAG results have the structure Core expects."""
        corpus_id, store, _ = indexed_integration_corpus

        results = run_rag(
            "artificial intelligence machine learning",
            corpus_id,
            store=store,
            top_k=3
        )

        for entry in results:
            # Verify all required fields exist
            assert hasattr(entry, "text")
            assert hasattr(entry, "score")
            assert hasattr(entry, "source")
            assert hasattr(entry, "metadata")

            # Verify field types
            assert isinstance(entry.text, str)
            assert isinstance(entry.score, float)
            assert isinstance(entry.source, str)
            assert isinstance(entry.metadata, dict)

            # Verify score is in valid range
            assert 0.0 <= entry.score <= 1.0

            # Verify text is non-empty
            assert len(entry.text) > 0

    def test_candidate_response_conversion(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test converting RAG CandidateEntry to Core CandidateResponse."""
        corpus_id, store, _ = indexed_integration_corpus

        rag_results = run_rag("yoga meditation", corpus_id, store=store, top_k=2)

        for entry in rag_results:
            # Convert to CandidateResponse
            response = CandidateResponse(
                text=entry.text,
                score=entry.score,
                aspect_alignment=0.0,  # To be computed by Core
                vritti_alignment=0.0,  # To be computed by Core
                entropy_penalty=0.0,   # To be computed by Core
                metadata=entry.to_dict()
            )

            # Verify conversion preserved data
            assert response.text == entry.text
            assert response.score == entry.score
            assert response.metadata["text"] == entry.text


# =============================================================================
# Full Integration Pipeline Tests
# =============================================================================


class TestFullIntegrationPipeline:
    """Tests for the complete RAG → Core integration pipeline."""

    def test_deterministic_pipeline_execution(
        self, temp_corpus_directory: str
    ) -> None:
        """
        Test that the entire pipeline is deterministic.
        Running the same flow twice should produce identical results.
        """
        corpus_id = "deterministic_test"
        query = "consciousness philosophy awareness"

        # First run
        store1 = MemoryVectorStore()
        index_corpus(corpus_id, temp_corpus_directory, store=store1, chunk_size=150)
        results1 = run_rag(query, corpus_id, store=store1, top_k=5)

        # Second run
        store2 = MemoryVectorStore()
        index_corpus(corpus_id, temp_corpus_directory, store=store2, chunk_size=150)
        results2 = run_rag(query, corpus_id, store=store2, top_k=5)

        # Verify identical results
        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.text == r2.text
            assert r1.score == r2.score
            assert r1.source == r2.source

    def test_multi_corpus_integration(
        self, temp_corpus_directory: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test integration with multiple corpora."""
        # Index same content under different corpus IDs
        index_corpus("corpus_alpha", temp_corpus_directory, store=fresh_store)
        index_corpus("corpus_beta", temp_corpus_directory, store=fresh_store)

        # Query multiple corpora
        results = run_rag_multi(
            "symbols language metaphors",
            ["corpus_alpha", "corpus_beta"],
            store=fresh_store,
            top_k=6
        )

        # Verify results from multiple corpora
        assert len(results) > 0
        assert all(isinstance(r, CandidateEntry) for r in results)

        # Convert all to Core format
        core_candidates = [
            CandidateResponse(text=r.text, score=r.score, metadata=r.metadata)
            for r in results
        ]
        assert len(core_candidates) == len(results)

    def test_pipeline_with_varied_queries(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test pipeline with different query types."""
        corpus_id, store, _ = indexed_integration_corpus

        queries = [
            "neural networks deep learning AI",
            "meditation yoga breath",
            "symbols metaphors archetypes",
            "consciousness subjective experience",
        ]

        for query in queries:
            results = run_rag(query, corpus_id, store=store, top_k=3)

            # Each query should return valid results
            assert isinstance(results, list)
            for entry in results:
                assert isinstance(entry, CandidateEntry)
                assert len(entry.text) > 0
                assert 0.0 <= entry.score <= 1.0

    def test_empty_results_handling(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that empty results are handled gracefully throughout pipeline."""
        # Query non-existent corpus
        results = run_rag("test query", "nonexistent", store=fresh_store, top_k=5)

        assert results == []

        # Empty results should still be valid input for Core
        core_candidates = [
            CandidateResponse(text=r.text, score=r.score)
            for r in results
        ]
        assert core_candidates == []

        # Core stitching should handle empty list
        engine = StitchingEngine()
        with pytest.raises(NotImplementedError):
            engine.score_candidates(core_candidates)


# =============================================================================
# Core Stitching Interface Tests
# =============================================================================


class TestCoreStitchingInterface:
    """Tests verifying Core stitching interface compatibility."""

    def test_stitching_engine_accepts_candidate_list(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test that StitchingEngine methods accept candidate lists."""
        corpus_id, store, _ = indexed_integration_corpus

        # Get RAG results
        rag_results = run_rag("AI machine learning", corpus_id, store=store, top_k=3)

        # Convert to CandidateResponse
        candidates = [
            CandidateResponse(
                text=r.text,
                score=r.score,
                metadata={"rag_source": r.source}
            )
            for r in rag_results
        ]

        engine = StitchingEngine()

        # All methods should accept the candidate list (but raise NotImplementedError)
        with pytest.raises(NotImplementedError):
            engine.score_candidates(candidates)

        with pytest.raises(NotImplementedError):
            engine.select_best(candidates, beam_size=5)

        with pytest.raises(NotImplementedError):
            engine.apply_penalties(candidates)

    def test_stitching_objective_interface(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test StitchingObjective interface with RAG-derived data."""
        corpus_id, store, _ = indexed_integration_corpus

        rag_results = run_rag("yoga meditation", corpus_id, store=store, top_k=2)

        if len(rag_results) > 0:
            candidate = CandidateResponse(
                text=rag_results[0].text,
                score=rag_results[0].score
            )
            context = {
                "user_intent": "exploration",
                "bhava_state": BhavaState().vritti_distribution
            }

            objective = StitchingObjective()
            with pytest.raises(NotImplementedError):
                objective.compute_objective(candidate, context)

    def test_penalty_calculator_interface(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test PenaltyCalculator interface with RAG-derived data."""
        corpus_id, store, _ = indexed_integration_corpus

        rag_results = run_rag("philosophy consciousness", corpus_id, store=store, top_k=3)

        candidates = [
            CandidateResponse(text=r.text, score=r.score)
            for r in rag_results
        ]

        calculator = PenaltyCalculator()

        with pytest.raises(NotImplementedError):
            calculator.redundancy_penalty(candidates)

        if len(candidates) > 0:
            context = {"domain": "philosophy"}
            with pytest.raises(NotImplementedError):
                calculator.domain_jump_penalty(candidates[0], context)


# =============================================================================
# Data Model Compatibility Tests
# =============================================================================


class TestDataModelCompatibility:
    """Tests for data model compatibility between RAG and Core."""

    def test_candidate_entry_to_candidate_response(self) -> None:
        """Test conversion from CandidateEntry to CandidateResponse."""
        entry = CandidateEntry(
            text="Test content from RAG",
            score=0.85,
            source="test_corpus",
            metadata={"chunk_idx": 0, "doc_idx": 1}
        )

        # Convert to Core model
        response = CandidateResponse(
            text=entry.text,
            score=entry.score,
            aspect_alignment=0.0,
            vritti_alignment=0.0,
            entropy_penalty=0.0,
            metadata={
                "rag_source": entry.source,
                "rag_metadata": entry.metadata
            }
        )

        assert response.text == entry.text
        assert response.score == entry.score
        assert response.metadata["rag_source"] == entry.source

    def test_bhava_state_with_rag_context(self) -> None:
        """Test BhavaState creation with RAG-derived context."""
        # RAG might provide context that influences BhavaState
        rag_context = {
            "query": "meditation awareness",
            "top_score": 0.9,
            "result_count": 5
        }

        bhava = BhavaState(
            vritti_distribution=[0.15, 0.20, 0.25, 0.25, 0.15],
            stability_score=0.8
        )

        # BhavaState should be valid
        assert len(bhava.vritti_distribution) == 5
        assert sum(bhava.vritti_distribution) == pytest.approx(1.0, rel=1e-6)
        assert bhava.stability_score == 0.8

    def test_entropy_state_creation(self) -> None:
        """Test EntropyState creation for pipeline context."""
        entropy = EntropyState(
            H_dim=0.5,
            H_guna=0.3,
            H_kosha=0.4,
            H_combined=0.6
        )

        assert entropy.H_dim == 0.5
        assert entropy.H_combined == 0.6


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling in the integration."""

    def test_empty_query_handling(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test handling of empty query."""
        corpus_id, store, _ = indexed_integration_corpus

        results = run_rag("", corpus_id, store=store, top_k=5)
        assert results == []

    def test_very_long_query_handling(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test handling of very long query."""
        corpus_id, store, _ = indexed_integration_corpus

        # Very long query
        long_query = "consciousness " * 100
        results = run_rag(long_query, corpus_id, store=store, top_k=3)

        # Should still return results
        assert isinstance(results, list)

    def test_special_characters_in_query(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test handling of special characters in query."""
        corpus_id, store, _ = indexed_integration_corpus

        queries = [
            "consciousness & awareness",
            "yoga (meditation)",
            "AI/ML neural-networks",
            "symbols: language, metaphors",
        ]

        for query in queries:
            results = run_rag(query, corpus_id, store=store, top_k=2)
            # Should not crash, results may vary
            assert isinstance(results, list)

    def test_corpus_stats_integration(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test corpus_stats in integration context."""
        corpus_id, store, chunk_count = indexed_integration_corpus

        stats = corpus_stats(corpus_id, store=store)

        assert stats["corpus_id"] == corpus_id
        assert stats["chunk_count"] == chunk_count
        assert stats["indexed"] is True

    def test_list_corpora_integration(
        self, temp_corpus_directory: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test list_indexed_corpora in integration context."""
        # Index multiple corpora
        index_corpus("int_corpus_1", temp_corpus_directory, store=fresh_store)
        index_corpus("int_corpus_2", temp_corpus_directory, store=fresh_store)

        corpora = list_indexed_corpora(store=fresh_store)

        assert "int_corpus_1" in corpora
        assert "int_corpus_2" in corpora


# =============================================================================
# Performance and Scalability Tests
# =============================================================================


class TestPerformanceCharacteristics:
    """Tests for performance characteristics of the integration."""

    def test_repeated_queries_consistent(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test that repeated queries return consistent results."""
        corpus_id, store, _ = indexed_integration_corpus
        query = "philosophy consciousness awareness"

        results_list = []
        for _ in range(5):
            results = run_rag(query, corpus_id, store=store, top_k=3)
            results_list.append(results)

        # All iterations should produce identical results
        first_results = results_list[0]
        for results in results_list[1:]:
            assert len(results) == len(first_results)
            for r, fr in zip(results, first_results):
                assert r.text == fr.text
                assert r.score == fr.score

    def test_varying_top_k_values(
        self, indexed_integration_corpus: tuple
    ) -> None:
        """Test pipeline with varying top_k values."""
        corpus_id, store, total_chunks = indexed_integration_corpus
        query = "machine learning"

        for k in [1, 3, 5, 10]:
            results = run_rag(query, corpus_id, store=store, top_k=k)

            # Should return at most k results
            assert len(results) <= k

            # Results should be sorted by score
            for i in range(len(results) - 1):
                assert results[i].score >= results[i + 1].score
