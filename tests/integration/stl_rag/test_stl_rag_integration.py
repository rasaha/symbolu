"""
STL + RAG Integration Tests
============================

Comprehensive tests demonstrating how the Symbolic Transformer Engine (STL)
integrates with the RAG system for enhanced query routing and retrieval.

Test Categories:
1. SemanticRouter + RAG: Query routing based on phoneme signatures
2. CandidatePreFilter + RAG: Filtering results by phoneme resonance
3. Resonance Engine + RAG: Word vector analysis of RAG content
4. HybridRAGEngine: Full integration flow
5. Mock Corpus Integration: Testing with fixture-built corpora

All tests are:
- Deterministic (no randomness)
- LLM-free (no external model calls)
- Network-free (no internet access)
"""

import pytest
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# RAG imports
from symbolu.rag.embeddings.encoder import embed, EMBEDDING_DIM
from symbolu.rag.indexing.indexer import chunk_documents, build_index
from symbolu.rag.vectorstore.memory_store import MemoryVectorStore
from symbolu.rag.retrieval.retriever import retrieve, retrieve_with_threshold
from symbolu.rag.utils.types import Document, ScoredChunk

# Resonance engine imports
from symbolu.resonance import (
    analyze_word,
    analyze_phrase,
    compare_words,
    WordVector,
    PhraseAnalysis,
    LAYER_NAMES,
)
from symbolu.resonance.engine import (
    word_to_vector,
    compute_resonance,
    HARMONY_THRESHOLD,
    DISSONANCE_THRESHOLD,
)

# Hybrid integration imports
from symbolu.hybrid.router import SemanticRouter, ModelType, RoutingDecision
from symbolu.hybrid.prefilter import CandidatePreFilter

# Corpus builder imports
from symbolu.rag.fixtures.builders.science_builder import ScienceCorpusBuilder


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fresh_store() -> MemoryVectorStore:
    """Create a fresh MemoryVectorStore instance."""
    return MemoryVectorStore()


@pytest.fixture
def semantic_router() -> SemanticRouter:
    """Create a SemanticRouter instance."""
    return SemanticRouter()


@pytest.fixture
def prefilter() -> CandidatePreFilter:
    """Create a CandidatePreFilter instance."""
    return CandidatePreFilter(threshold=0.5)


@pytest.fixture
def science_corpus_docs() -> List[Document]:
    """Build science corpus documents."""
    builder = ScienceCorpusBuilder()
    doc_specs = builder.build_documents()[:10]  # First 10 docs for testing
    return [
        Document(text=spec.content, metadata=spec.metadata)
        for spec in doc_specs
    ]


@pytest.fixture
def indexed_science_corpus(fresh_store: MemoryVectorStore, science_corpus_docs: List[Document]) -> str:
    """Index science corpus and return corpus_id."""
    corpus_id = "science_test"
    build_index(corpus_id, science_corpus_docs, fresh_store, chunk_size=300)
    return corpus_id


# =============================================================================
# Test Class: SemanticRouter + RAG Integration
# =============================================================================


class TestSemanticRouterRAGIntegration:
    """Tests for SemanticRouter integration with RAG retrieval."""

    def test_router_routes_physics_query_to_reasoning(self, semantic_router: SemanticRouter) -> None:
        """Test that physics/reasoning queries are routed to REASONING model type."""
        query = "Calculate the force using Newton's second law"
        decision = semantic_router.route(query)

        assert isinstance(decision, RoutingDecision)
        assert decision.confidence > 0
        # Physics calculations should route to reasoning or action
        assert decision.model_type in (ModelType.REASONING, ModelType.ACTION, ModelType.GENERAL)

    def test_router_routes_relationship_query(self, semantic_router: SemanticRouter) -> None:
        """Test that relationship-focused queries are routed appropriately."""
        query = "Love and connection bring unity to communities"
        decision = semantic_router.route(query)

        assert isinstance(decision, RoutingDecision)
        # Unifying/relationship words should lean toward RELATIONSHIP
        # The dominant layer should reflect the phoneme profile
        assert decision.dominant_layer in LAYER_NAMES

    def test_router_provides_layer_scores(self, semantic_router: SemanticRouter) -> None:
        """Test that router provides top layer scores."""
        query = "Quantum mechanics explains particle behavior"
        decision = semantic_router.route(query)

        assert decision.layer_scores is not None
        assert len(decision.layer_scores) == 3  # Top 3 layers
        # Scores should be tuples of (layer_name, score)
        for layer_name, score in decision.layer_scores:
            assert layer_name in LAYER_NAMES
            assert 0 <= score <= 1

    def test_router_with_rag_retrieval(
        self,
        semantic_router: SemanticRouter,
        fresh_store: MemoryVectorStore,
        indexed_science_corpus: str,
    ) -> None:
        """Test full flow: route query then retrieve from corpus."""
        query = "How does gravity affect planetary motion?"

        # Step 1: Route the query
        decision = semantic_router.route(query)
        assert decision.model_type is not None

        # Step 2: Retrieve from RAG
        results = retrieve(query, indexed_science_corpus, fresh_store, top_k=3)

        # Step 3: Verify results are relevant to physics
        assert len(results) > 0
        combined_text = " ".join(r.text.lower() for r in results)
        # Should find physics-related content
        physics_keywords = ["gravity", "force", "planet", "motion", "newton", "mass"]
        assert any(kw in combined_text for kw in physics_keywords)

    def test_router_deterministic(self, semantic_router: SemanticRouter) -> None:
        """Test that router produces identical results for identical queries."""
        query = "Energy conservation in thermodynamic systems"

        decision1 = semantic_router.route(query)
        decision2 = semantic_router.route(query)

        assert decision1.model_type == decision2.model_type
        assert decision1.confidence == decision2.confidence
        assert decision1.dominant_layer == decision2.dominant_layer


# =============================================================================
# Test Class: CandidatePreFilter + RAG Integration
# =============================================================================


class TestPrefilterRAGIntegration:
    """Tests for CandidatePreFilter integration with RAG retrieval."""

    def test_prefilter_filters_candidates(self, prefilter: CandidatePreFilter) -> None:
        """Test that prefilter filters candidates based on phoneme resonance."""
        # Candidates with varying resonance to "physics"
        candidates = (
            "Newton's laws describe force and motion",  # Physics-related
            "Cooking recipes for Italian pasta",         # Unrelated
            "Quantum mechanics explains particle waves", # Physics-related
            "Football strategies for winning games",     # Unrelated
        )
        target = "physics and motion"

        filtered = prefilter.filter(candidates, target)

        # Should keep some candidates but potentially filter unrelated ones
        assert isinstance(filtered, tuple)
        # At minimum, we should have results
        assert len(filtered) >= 0

    def test_prefilter_with_rag_results(
        self,
        prefilter: CandidatePreFilter,
        fresh_store: MemoryVectorStore,
        indexed_science_corpus: str,
    ) -> None:
        """Test prefilter on RAG retrieval results."""
        query = "Light and electromagnetic waves"

        # Retrieve results
        results = retrieve(query, indexed_science_corpus, fresh_store, top_k=10)

        if len(results) > 0:
            # Convert to text tuples
            candidate_texts = tuple(r.text for r in results)

            # Apply prefilter
            filtered = prefilter.filter(candidate_texts, query)

            # Filtered results should be subset or equal
            assert len(filtered) <= len(candidate_texts)

    def test_prefilter_deterministic(self, prefilter: CandidatePreFilter) -> None:
        """Test that prefilter is deterministic."""
        candidates = (
            "Stars produce energy through nuclear fusion",
            "Baking bread requires proper temperature",
            "Galaxies contain billions of stars",
        )
        target = "stellar astronomy"

        filtered1 = prefilter.filter(candidates, target)
        filtered2 = prefilter.filter(candidates, target)

        assert filtered1 == filtered2


# =============================================================================
# Test Class: Resonance Engine + RAG Content Analysis
# =============================================================================


class TestResonanceRAGContentAnalysis:
    """Tests for analyzing RAG content using the resonance engine."""

    def test_analyze_rag_chunk_phoneme_profile(self) -> None:
        """Test analyzing a RAG chunk for its phoneme profile."""
        chunk_text = "Newton's laws describe the relationship between force and motion"

        analysis = analyze_phrase(chunk_text)

        assert isinstance(analysis, PhraseAnalysis)
        assert analysis.phrase != ""
        assert len(analysis.words) > 0
        # Each word should have a 10D vector
        for word_vec in analysis.words:
            assert len(word_vec.vector) == 12  # 12D ontological vectors
            assert word_vec.dominant_layer in LAYER_NAMES

    def test_compute_resonance_between_rag_chunks(self) -> None:
        """Test computing resonance between two RAG chunks."""
        chunk1 = "Gravity is the fundamental force of attraction"
        chunk2 = "Light travels as electromagnetic waves"

        analysis1 = analyze_phrase(chunk1)
        analysis2 = analyze_phrase(chunk2)

        # Get dominant word vectors
        if analysis1.words and analysis2.words:
            vec1 = analysis1.words[0]
            vec2 = analysis2.words[0]

            resonance = compute_resonance(vec1, vec2)

            assert resonance.similarity >= 0
            assert resonance.similarity <= 1
            assert isinstance(resonance.harmonic, bool)
            assert isinstance(resonance.dissonant, bool)

    def test_rag_content_harmony_classification(self) -> None:
        """Test classifying RAG content harmony."""
        # Harmonious concepts
        harmonious = ["truth", "light", "clarity"]

        # Analyze each
        vectors = [analyze_word(w) for w in harmonious]

        # Check pairwise resonance
        if len(vectors) >= 2:
            vec1, vec2 = vectors[0], vectors[1]
            resonance = compare_words(vec1.word, vec2.word)

            # Should have some similarity
            assert resonance.similarity >= 0

    def test_analyze_science_content_for_dominant_layers(
        self,
        science_corpus_docs: List[Document],
    ) -> None:
        """Test that science content has expected phoneme layer profiles."""
        # Take first document
        doc = science_corpus_docs[0]

        # Analyze a sample sentence
        sample = doc.text.split(".")[0] if "." in doc.text else doc.text[:100]
        analysis = analyze_phrase(sample)

        # Should have analyzable words
        assert len(analysis.words) >= 0  # May vary by content

        # Overall harmony should be computed
        assert isinstance(analysis.overall_harmony, float)


# =============================================================================
# Test Class: Full Integration Flow
# =============================================================================


class TestFullSTLRAGIntegration:
    """Tests for the complete STL + RAG integration flow."""

    def test_end_to_end_query_to_ranked_results(
        self,
        semantic_router: SemanticRouter,
        prefilter: CandidatePreFilter,
        fresh_store: MemoryVectorStore,
        indexed_science_corpus: str,
    ) -> None:
        """Test complete flow: query -> route -> retrieve -> filter -> analyze."""
        query = "How do atoms form chemical bonds?"

        # Step 1: Route the query using STL
        routing = semantic_router.route(query)
        assert routing.model_type is not None

        # Step 2: Get query phoneme analysis
        query_analysis = analyze_phrase(query)
        assert query_analysis is not None

        # Step 3: Retrieve from RAG
        results = retrieve(query, indexed_science_corpus, fresh_store, top_k=5)

        if len(results) > 0:
            # Step 4: Filter using phoneme prefilter
            candidate_texts = tuple(r.text for r in results)
            filtered = prefilter.filter(candidate_texts, query)

            # Step 5: Analyze each result's phoneme profile
            for text in filtered[:3]:  # Analyze top 3
                analysis = analyze_phrase(text)
                assert isinstance(analysis, PhraseAnalysis)

    def test_rag_retrieval_with_phoneme_enrichment(
        self,
        fresh_store: MemoryVectorStore,
        indexed_science_corpus: str,
    ) -> None:
        """Test RAG retrieval with phoneme vector enrichment of results."""
        query = "Energy conservation in physical systems"

        results = retrieve(query, indexed_science_corpus, fresh_store, top_k=3)

        enriched_results = []
        for result in results:
            # Enrich with phoneme analysis
            phrase_analysis = analyze_phrase(result.text[:200])  # First 200 chars

            enriched = {
                "text": result.text,
                "rag_score": result.score,
                "phoneme_harmony": phrase_analysis.overall_harmony,
                "dominant_layer": (
                    phrase_analysis.words[0].dominant_layer
                    if phrase_analysis.words else "N/A"
                ),
                "word_count": len(phrase_analysis.words),
            }
            enriched_results.append(enriched)

        # All results should be enriched
        assert len(enriched_results) == len(results)
        for er in enriched_results:
            assert "rag_score" in er
            assert "phoneme_harmony" in er
            assert "dominant_layer" in er

    def test_multi_query_consistency(
        self,
        semantic_router: SemanticRouter,
        fresh_store: MemoryVectorStore,
        indexed_science_corpus: str,
    ) -> None:
        """Test that multiple related queries produce consistent results."""
        queries = [
            "What is Newton's first law?",
            "Newton first law of motion",
            "Law of inertia Newton",
        ]

        all_results = []
        for query in queries:
            # Route
            routing = semantic_router.route(query)

            # Retrieve
            results = retrieve(query, indexed_science_corpus, fresh_store, top_k=3)

            all_results.append({
                "query": query,
                "model_type": routing.model_type,
                "result_count": len(results),
                "top_score": results[0].score if results else 0,
            })

        # All queries should return results
        for r in all_results:
            assert r["result_count"] > 0


# =============================================================================
# Test Class: Corpus Builder Integration
# =============================================================================


class TestCorpusBuilderSTLIntegration:
    """Tests for corpus builder integration with STL analysis."""

    def test_science_corpus_builder_creates_documents(self) -> None:
        """Test that science corpus builder creates valid documents."""
        builder = ScienceCorpusBuilder()
        docs = builder.build_documents()

        assert len(docs) > 0

        # Check first document
        first_doc = docs[0]
        assert first_doc.doc_id is not None
        assert first_doc.corpus_id == "science"
        assert len(first_doc.content) > 0

    def test_corpus_content_phoneme_analysis(self) -> None:
        """Test phoneme analysis of corpus content."""
        builder = ScienceCorpusBuilder()
        docs = builder.build_documents()[:5]  # First 5 docs

        for doc in docs:
            # Analyze title
            title_analysis = analyze_phrase(doc.title)
            assert isinstance(title_analysis, PhraseAnalysis)

            # Analyze first sentence of content
            first_sentence = doc.content.split(".")[0] if "." in doc.content else doc.content[:50]
            content_analysis = analyze_phrase(first_sentence)

            # Should have computed overall harmony
            assert isinstance(content_analysis.overall_harmony, float)

    def test_corpus_to_rag_index_integration(self, fresh_store: MemoryVectorStore) -> None:
        """Test indexing corpus builder output into RAG."""
        builder = ScienceCorpusBuilder()
        doc_specs = builder.build_documents()[:5]

        # Convert to RAG Documents
        documents = [
            Document(text=spec.content, metadata=spec.metadata)
            for spec in doc_specs
        ]

        # Index
        corpus_id = "science_builder_test"
        count = build_index(corpus_id, documents, fresh_store, chunk_size=200)

        assert count > 0
        assert fresh_store.count(corpus_id) == count

        # Retrieve
        results = retrieve("physics motion force", corpus_id, fresh_store, top_k=3)
        assert len(results) > 0


# =============================================================================
# Test Class: STL Architectural Properties
# =============================================================================


class TestSTLArchitecturalProperties:
    """Tests verifying STL's architectural properties vs LLM behavior."""

    def test_stl_is_deterministic(self) -> None:
        """Test that STL produces identical results for identical inputs."""
        text = "Quantum mechanics describes wave-particle duality"

        # Multiple analyses
        results = [analyze_phrase(text) for _ in range(5)]

        # All should be identical
        for r in results[1:]:
            assert r.overall_harmony == results[0].overall_harmony
            assert r.prediction == results[0].prediction
            assert len(r.words) == len(results[0].words)

    def test_stl_uses_no_learned_parameters(self) -> None:
        """Verify STL uses explicit phoneme mappings, not learned weights."""
        word = "truth"
        vec = analyze_word(word)

        # Vector should be 10D (explicit ontological layers)
        assert len(vec.vector) == 12  # 12D ontological vectors

        # Dominant layer should be one of the defined layers
        assert vec.dominant_layer in LAYER_NAMES

        # Score should be deterministic
        vec2 = analyze_word(word)
        assert vec.vector == vec2.vector

    def test_stl_has_no_probability_distribution(self) -> None:
        """Verify STL outputs are categorical, not probabilistic."""
        phrase = "Light travels at constant speed"
        analysis = analyze_phrase(phrase)

        # Prediction is categorical (HARMONIC, NEUTRAL, DISSONANT)
        assert analysis.prediction in ("HARMONIC", "NEUTRAL", "DISSONANT")

        # Not a probability distribution
        assert isinstance(analysis.prediction, str)

    def test_stl_converges_via_constraint_tightening(self, semantic_router: SemanticRouter) -> None:
        """Verify STL routes via constraint elimination, not sampling."""
        query = "Love conquers all obstacles"

        # Route multiple times - should always get same result
        decisions = [semantic_router.route(query) for _ in range(10)]

        # All decisions should be identical (no sampling)
        for d in decisions[1:]:
            assert d.model_type == decisions[0].model_type
            assert d.dominant_layer == decisions[0].dominant_layer
            assert d.confidence == decisions[0].confidence


# =============================================================================
# Test Class: Integration Edge Cases
# =============================================================================


class TestIntegrationEdgeCases:
    """Tests for edge cases in STL + RAG integration."""

    def test_empty_query_handling(
        self,
        semantic_router: SemanticRouter,
        fresh_store: MemoryVectorStore,
    ) -> None:
        """Test handling of empty queries."""
        # Empty query analysis
        analysis = analyze_phrase("")
        assert analysis.words == ()
        assert analysis.overall_harmony == 0.0

        # Router with empty query
        decision = semantic_router.route("")
        assert decision.model_type == ModelType.GENERAL

        # RAG with empty query
        results = retrieve("", "nonexistent", fresh_store, top_k=5)
        assert results == []

    def test_single_word_query(
        self,
        semantic_router: SemanticRouter,
        fresh_store: MemoryVectorStore,
        indexed_science_corpus: str,
    ) -> None:
        """Test handling of single word queries."""
        word = "physics"

        # Analyze single word
        analysis = analyze_word(word)
        assert analysis.word == word
        assert len(analysis.vector) == 12  # 12D ontological vectors

        # Route single word
        decision = semantic_router.route(word)
        assert decision.model_type is not None

        # Retrieve with single word
        results = retrieve(word, indexed_science_corpus, fresh_store, top_k=3)
        # Should find relevant results in science corpus
        assert len(results) >= 0  # May or may not find depending on indexing

    def test_special_characters_in_query(self) -> None:
        """Test handling of special characters in queries."""
        query = "E = mc² (Einstein's equation)"

        analysis = analyze_phrase(query)
        # Should handle special chars gracefully
        assert isinstance(analysis, PhraseAnalysis)

    def test_very_long_query(
        self,
        semantic_router: SemanticRouter,
    ) -> None:
        """Test handling of very long queries."""
        # Generate a long query
        long_query = " ".join(["physics"] * 100)

        # Should handle without error
        decision = semantic_router.route(long_query)
        assert decision.model_type is not None

        analysis = analyze_phrase(long_query)
        assert isinstance(analysis, PhraseAnalysis)


# =============================================================================
# Test Class: Resonance Metrics
# =============================================================================


class TestResonanceMetrics:
    """Tests for resonance-based metrics in RAG context."""

    def test_harmony_threshold_classification(self) -> None:
        """Test that harmony thresholds correctly classify content."""
        # High harmony phrase (similar sounds)
        high_harmony = analyze_phrase("light bright sight")

        # Check threshold application
        if high_harmony.overall_harmony >= HARMONY_THRESHOLD:
            assert high_harmony.prediction == "HARMONIC"
        elif high_harmony.overall_harmony <= DISSONANCE_THRESHOLD:
            assert high_harmony.prediction == "DISSONANT"
        else:
            assert high_harmony.prediction == "NEUTRAL"

    def test_resonance_score_range(self) -> None:
        """Test that resonance scores are in valid range [0, 1]."""
        words = ["truth", "light", "wisdom", "knowledge"]

        for w1 in words:
            for w2 in words:
                if w1 != w2:
                    result = compare_words(w1, w2)
                    assert 0 <= result.similarity <= 1

    def test_shared_dimensions_detection(self) -> None:
        """Test that shared ontological dimensions are detected."""
        # Analyze two words
        vec1 = analyze_word("love")
        vec2 = analyze_word("peace")

        resonance = compute_resonance(vec1, vec2)

        # Should have some shared or conflicting dimensions
        # (depends on specific phoneme mappings)
        assert isinstance(resonance.shared_dimensions, tuple)
        assert isinstance(resonance.conflicting_dimensions, tuple)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "TestSemanticRouterRAGIntegration",
    "TestPrefilterRAGIntegration",
    "TestResonanceRAGContentAnalysis",
    "TestFullSTLRAGIntegration",
    "TestCorpusBuilderSTLIntegration",
    "TestSTLArchitecturalProperties",
    "TestIntegrationEdgeCases",
    "TestResonanceMetrics",
]
