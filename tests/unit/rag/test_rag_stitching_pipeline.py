"""
Symbol-U RAG v3.0 - RAG Stitching Pipeline Tests
================================================
Unit tests for the rag.stitching.pipeline module:
- index_corpus()
- run_rag()
- run_rag_multi()
- list_indexed_corpora()
- corpus_stats()

These functions form the connector layer between RAG retrieval and the Core
stitching engine. All tests are deterministic, LLM-free, and offline.
"""

import os
import tempfile
from typing import List

import pytest

# Import pipeline functions
from symbolu.rag.stitching.pipeline import (
    index_corpus,
    run_rag,
    run_rag_multi,
    list_indexed_corpora,
    corpus_stats,
)

# Import supporting components
from symbolu.rag.vectorstore.memory_store import (
    MemoryVectorStore,
    get_global_store,
    reset_global_store,
)
from symbolu.rag.utils.types import CandidateEntry, Document
from symbolu.rag.ingestion.loader import load_text


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fresh_store() -> MemoryVectorStore:
    """Create a fresh MemoryVectorStore instance."""
    return MemoryVectorStore()


@pytest.fixture(autouse=True)
def reset_global_store_fixture():
    """Reset global store before and after each test."""
    reset_global_store()
    yield
    reset_global_store()


@pytest.fixture
def temp_directory_with_docs():
    """Create a temporary directory with test documents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # ML document
        ml_path = os.path.join(tmpdir, "ml_doc.txt")
        with open(ml_path, "w", encoding="utf-8") as f:
            f.write(
                "Machine learning is a subset of artificial intelligence. "
                "It involves training models on data to make predictions. "
                "Deep learning uses neural networks with many layers. "
                "Supervised learning requires labeled training data. "
                "Unsupervised learning finds patterns without labels."
            )

        # NLP document
        nlp_path = os.path.join(tmpdir, "nlp_doc.txt")
        with open(nlp_path, "w", encoding="utf-8") as f:
            f.write(
                "Natural language processing enables computers to understand human language. "
                "NLP is used in chatbots, translation, and sentiment analysis. "
                "Tokenization splits text into words or subwords. "
                "Named entity recognition identifies people, places, and organizations."
            )

        # Cooking document
        cooking_path = os.path.join(tmpdir, "cooking_doc.txt")
        with open(cooking_path, "w", encoding="utf-8") as f:
            f.write(
                "Cooking is the art of preparing food using heat. "
                "Recipes provide step-by-step instructions for making dishes. "
                "Baking involves cooking food in an oven. "
                "Grilling uses direct heat from below."
            )

        yield tmpdir


@pytest.fixture
def indexed_corpus(
    temp_directory_with_docs: str, fresh_store: MemoryVectorStore
) -> tuple:
    """Create and index a test corpus."""
    corpus_id = "indexed_test_corpus"
    chunk_count = index_corpus(
        corpus_id, temp_directory_with_docs, store=fresh_store, chunk_size=200
    )
    return corpus_id, fresh_store, chunk_count


# =============================================================================
# index_corpus Tests
# =============================================================================


class TestIndexCorpus:
    """Tests for index_corpus() function."""

    def test_index_corpus_basic(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test basic corpus indexing."""
        corpus_id = "test_corpus"
        count = index_corpus(
            corpus_id, temp_directory_with_docs, store=fresh_store
        )

        assert count > 0
        assert fresh_store.count(corpus_id) == count

    def test_index_corpus_with_custom_chunk_size(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test indexing with custom chunk size."""
        corpus_id = "custom_chunk_corpus"

        # Smaller chunks should produce more chunks
        count_small = index_corpus(
            corpus_id + "_small",
            temp_directory_with_docs,
            store=fresh_store,
            chunk_size=100
        )

        count_large = index_corpus(
            corpus_id + "_large",
            temp_directory_with_docs,
            store=fresh_store,
            chunk_size=500
        )

        # More chunks with smaller chunk_size
        assert count_small >= count_large

    def test_index_corpus_with_global_store(
        self, temp_directory_with_docs: str
    ) -> None:
        """Test indexing using global store (store=None)."""
        corpus_id = "global_store_corpus"
        count = index_corpus(corpus_id, temp_directory_with_docs, store=None)

        assert count > 0

        # Verify via global store
        global_store = get_global_store()
        assert global_store.count(corpus_id) == count

    def test_index_corpus_nonexistent_path(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test indexing with non-existent path raises error."""
        with pytest.raises(FileNotFoundError):
            index_corpus(
                "error_corpus",
                "/nonexistent/path/to/docs",
                store=fresh_store
            )

    def test_index_corpus_deterministic(
        self, temp_directory_with_docs: str
    ) -> None:
        """Test that indexing is deterministic."""
        store1 = MemoryVectorStore()
        store2 = MemoryVectorStore()

        count1 = index_corpus(
            "corpus1", temp_directory_with_docs, store=store1, chunk_size=150
        )
        count2 = index_corpus(
            "corpus2", temp_directory_with_docs, store=store2, chunk_size=150
        )

        assert count1 == count2

    def test_index_corpus_multiple_corpora(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test indexing multiple corpora in the same store."""
        count1 = index_corpus(
            "corpus_a", temp_directory_with_docs, store=fresh_store
        )
        count2 = index_corpus(
            "corpus_b", temp_directory_with_docs, store=fresh_store
        )

        assert count1 > 0
        assert count2 > 0
        assert fresh_store.count("corpus_a") == count1
        assert fresh_store.count("corpus_b") == count2


# =============================================================================
# run_rag Tests
# =============================================================================


class TestRunRag:
    """Tests for run_rag() function."""

    def test_run_rag_basic(
        self, indexed_corpus: tuple
    ) -> None:
        """Test basic RAG retrieval."""
        corpus_id, store, _ = indexed_corpus

        results = run_rag(
            "machine learning artificial intelligence",
            corpus_id,
            store=store,
            top_k=3
        )

        assert len(results) <= 3
        assert all(isinstance(r, CandidateEntry) for r in results)

    def test_run_rag_returns_relevant_results(
        self, indexed_corpus: tuple
    ) -> None:
        """Test that run_rag returns relevant results."""
        corpus_id, store, _ = indexed_corpus

        # Query about ML
        results = run_rag(
            "neural networks deep learning",
            corpus_id,
            store=store,
            top_k=5
        )

        # Best result should contain ML-related keywords
        if len(results) > 0:
            best = results[0]
            text_lower = best.text.lower()
            has_ml_keyword = any(
                kw in text_lower
                for kw in ["learning", "neural", "model", "data", "training"]
            )
            assert has_ml_keyword, f"Expected ML keywords in: {best.text[:100]}"

    def test_run_rag_sorted_by_score(
        self, indexed_corpus: tuple
    ) -> None:
        """Test that run_rag returns results sorted by score descending."""
        corpus_id, store, _ = indexed_corpus

        results = run_rag("natural language", corpus_id, store=store, top_k=5)

        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_run_rag_deterministic(
        self, indexed_corpus: tuple
    ) -> None:
        """Test that run_rag is deterministic."""
        corpus_id, store, _ = indexed_corpus
        query = "machine learning models"

        results1 = run_rag(query, corpus_id, store=store, top_k=3)
        results2 = run_rag(query, corpus_id, store=store, top_k=3)

        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.text == r2.text
            assert r1.score == r2.score
            assert r1.source == r2.source

    def test_run_rag_empty_query(
        self, indexed_corpus: tuple
    ) -> None:
        """Test run_rag with empty query."""
        corpus_id, store, _ = indexed_corpus

        results = run_rag("", corpus_id, store=store, top_k=3)
        assert results == []

    def test_run_rag_nonexistent_corpus(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test run_rag with non-existent corpus."""
        results = run_rag(
            "test query",
            "nonexistent_corpus",
            store=fresh_store,
            top_k=5
        )
        assert results == []

    def test_run_rag_candidate_entry_structure(
        self, indexed_corpus: tuple
    ) -> None:
        """Test that run_rag returns proper CandidateEntry objects."""
        corpus_id, store, _ = indexed_corpus

        results = run_rag("cooking recipes", corpus_id, store=store, top_k=2)

        if len(results) > 0:
            entry = results[0]
            assert hasattr(entry, "text")
            assert hasattr(entry, "score")
            assert hasattr(entry, "source")
            assert hasattr(entry, "metadata")
            assert isinstance(entry.text, str)
            assert isinstance(entry.score, float)
            assert 0.0 <= entry.score <= 1.0

    def test_run_rag_with_global_store(
        self, temp_directory_with_docs: str
    ) -> None:
        """Test run_rag using global store."""
        corpus_id = "global_rag_test"
        index_corpus(corpus_id, temp_directory_with_docs, store=None)

        results = run_rag("machine learning", corpus_id, store=None, top_k=3)

        assert len(results) > 0


# =============================================================================
# run_rag_multi Tests
# =============================================================================


class TestRunRagMulti:
    """Tests for run_rag_multi() function."""

    def test_run_rag_multi_basic(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test basic multi-corpus RAG."""
        # Index two corpora from the same source (for simplicity)
        index_corpus("corpus_a", temp_directory_with_docs, store=fresh_store)
        index_corpus("corpus_b", temp_directory_with_docs, store=fresh_store)

        results = run_rag_multi(
            "machine learning",
            ["corpus_a", "corpus_b"],
            store=fresh_store,
            top_k=5
        )

        assert len(results) > 0
        assert all(isinstance(r, CandidateEntry) for r in results)

    def test_run_rag_multi_combines_results(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that run_rag_multi combines results from multiple corpora."""
        # Index same docs under different corpus IDs
        index_corpus("multi_a", temp_directory_with_docs, store=fresh_store)
        index_corpus("multi_b", temp_directory_with_docs, store=fresh_store)

        # Single corpus results
        results_a = run_rag("cooking", "multi_a", store=fresh_store, top_k=10)
        results_b = run_rag("cooking", "multi_b", store=fresh_store, top_k=10)

        # Multi corpus results
        results_multi = run_rag_multi(
            "cooking", ["multi_a", "multi_b"], store=fresh_store, top_k=10
        )

        # Multi should have results from both
        assert len(results_multi) > 0

    def test_run_rag_multi_sorted_by_score(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that run_rag_multi returns sorted results."""
        index_corpus("sorted_a", temp_directory_with_docs, store=fresh_store)
        index_corpus("sorted_b", temp_directory_with_docs, store=fresh_store)

        results = run_rag_multi(
            "neural networks",
            ["sorted_a", "sorted_b"],
            store=fresh_store,
            top_k=10
        )

        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_run_rag_multi_empty_corpus_list(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test run_rag_multi with empty corpus list."""
        results = run_rag_multi("query", [], store=fresh_store, top_k=5)
        assert results == []

    def test_run_rag_multi_deterministic(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that run_rag_multi is deterministic."""
        index_corpus("det_a", temp_directory_with_docs, store=fresh_store)
        index_corpus("det_b", temp_directory_with_docs, store=fresh_store)

        query = "artificial intelligence"
        corpus_ids = ["det_a", "det_b"]

        results1 = run_rag_multi(query, corpus_ids, store=fresh_store, top_k=5)
        results2 = run_rag_multi(query, corpus_ids, store=fresh_store, top_k=5)

        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.text == r2.text
            assert r1.score == r2.score


# =============================================================================
# list_indexed_corpora Tests
# =============================================================================


class TestListIndexedCorpora:
    """Tests for list_indexed_corpora() function."""

    def test_list_indexed_corpora_empty(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test list_indexed_corpora with no corpora."""
        corpora = list_indexed_corpora(store=fresh_store)
        assert corpora == []

    def test_list_indexed_corpora_single(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test list_indexed_corpora with single corpus."""
        index_corpus("single_corpus", temp_directory_with_docs, store=fresh_store)

        corpora = list_indexed_corpora(store=fresh_store)
        assert "single_corpus" in corpora

    def test_list_indexed_corpora_multiple(
        self, temp_directory_with_docs: str, fresh_store: MemoryVectorStore
    ) -> None:
        """Test list_indexed_corpora with multiple corpora."""
        index_corpus("corpus_x", temp_directory_with_docs, store=fresh_store)
        index_corpus("corpus_y", temp_directory_with_docs, store=fresh_store)
        index_corpus("corpus_z", temp_directory_with_docs, store=fresh_store)

        corpora = list_indexed_corpora(store=fresh_store)

        assert "corpus_x" in corpora
        assert "corpus_y" in corpora
        assert "corpus_z" in corpora

    def test_list_indexed_corpora_global_store(
        self, temp_directory_with_docs: str
    ) -> None:
        """Test list_indexed_corpora with global store."""
        index_corpus("global_list_test", temp_directory_with_docs, store=None)

        corpora = list_indexed_corpora(store=None)
        assert "global_list_test" in corpora


# =============================================================================
# corpus_stats Tests
# =============================================================================


class TestCorpusStats:
    """Tests for corpus_stats() function."""

    def test_corpus_stats_indexed_corpus(
        self, indexed_corpus: tuple
    ) -> None:
        """Test corpus_stats for indexed corpus."""
        corpus_id, store, expected_count = indexed_corpus

        stats = corpus_stats(corpus_id, store=store)

        assert stats["corpus_id"] == corpus_id
        assert stats["chunk_count"] == expected_count
        assert stats["indexed"] is True

    def test_corpus_stats_nonexistent_corpus(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test corpus_stats for non-existent corpus."""
        stats = corpus_stats("nonexistent", store=fresh_store)

        assert stats["corpus_id"] == "nonexistent"
        assert stats["chunk_count"] == 0
        assert stats["indexed"] is False

    def test_corpus_stats_structure(
        self, indexed_corpus: tuple
    ) -> None:
        """Test corpus_stats returns expected structure."""
        corpus_id, store, _ = indexed_corpus

        stats = corpus_stats(corpus_id, store=store)

        assert "corpus_id" in stats
        assert "chunk_count" in stats
        assert "indexed" in stats
        assert isinstance(stats["corpus_id"], str)
        assert isinstance(stats["chunk_count"], int)
        assert isinstance(stats["indexed"], bool)


# =============================================================================
# Integration with Core Stitching Tests
# =============================================================================


class TestPipelineOutputForCoreStitching:
    """Tests verifying pipeline output is compatible with Core stitching."""

    def test_candidate_entry_compatible_with_core(
        self, indexed_corpus: tuple
    ) -> None:
        """Test that CandidateEntry is compatible with Core stitching expectations."""
        corpus_id, store, _ = indexed_corpus

        results = run_rag("machine learning", corpus_id, store=store, top_k=3)

        if len(results) > 0:
            entry = results[0]

            # CandidateEntry should have fields expected by Core
            assert hasattr(entry, "text")
            assert hasattr(entry, "score")
            assert hasattr(entry, "metadata")

            # to_dict should produce dict usable by Core
            entry_dict = entry.to_dict()
            assert "text" in entry_dict
            assert "score" in entry_dict

    def test_pipeline_produces_list_output(
        self, indexed_corpus: tuple
    ) -> None:
        """Test that pipeline produces list output for Core processing."""
        corpus_id, store, _ = indexed_corpus

        results = run_rag("cooking food", corpus_id, store=store, top_k=5)

        assert isinstance(results, list)
        # Core stitching expects a list of candidates
        assert all(hasattr(r, "text") for r in results)
        assert all(hasattr(r, "score") for r in results)

    def test_empty_results_handled_gracefully(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that empty results are handled gracefully for Core."""
        results = run_rag("query", "nonexistent", store=fresh_store, top_k=5)

        # Empty list is a valid input for Core stitching
        assert results == []
        assert isinstance(results, list)
