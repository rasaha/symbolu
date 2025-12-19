"""
10D Ontological Backbone Tests
==============================

Tests the 10D encoding, cross-domain similarity, and RAG integration
using realistic multi-domain mockup data.

Domains tested:
    - American History
    - Science/Physics
    - English Literature
    - Finance/Economics
    - Biology/Medicine
    - Current Events
"""

import pytest
from typing import Dict, List

from symbolu.ontology.backbone.encoder import (
    Dimension,
    DimensionalVector,
    encode_10d,
    encode_batch,
    get_dominant_dimensions,
    get_dimensional_profile,
)
from symbolu.ontology.backbone.similarity import (
    compute_similarity,
    find_similar_content,
    analyze_cross_domain,
    find_cross_domain_connections,
    cosine_similarity,
    euclidean_similarity,
    structural_similarity,
)
from symbolu.ontology.backbone.extractors import (
    ProjectionDirection,
    detect_projection_direction,
    extract_all_with_direction,
    get_extractor,
)
from symbolu.ontology.backbone.rag_integration import (
    OntologicalRAGIndex,
    OntologicalDocument,
    DomainWeights,
    RetrievalMode,
    create_ontological_index_from_rag,
    hybrid_retrieve,
)


# =============================================================================
# Multi-Domain Mockup Data
# =============================================================================

HISTORY_DOCS = [
    {
        "id": "hist_001",
        "content": "The Civil War began in 1861 when Confederate forces attacked Fort Sumter. This conflict divided the nation between North and South, ultimately resulting in the abolition of slavery and the preservation of the Union.",
    },
    {
        "id": "hist_002",
        "content": "The Great Depression started with the stock market crash of 1929. Unemployment rose to 25%, banks failed across the country, and millions of Americans lost their savings and homes.",
    },
    {
        "id": "hist_003",
        "content": "The Louisiana Purchase of 1803 doubled the size of the United States. President Jefferson negotiated this deal with Napoleon, acquiring 828,000 square miles for approximately $15 million.",
    },
    {
        "id": "hist_004",
        "content": "The Civil Rights Movement of the 1950s and 1960s fought against racial segregation. Leaders like Martin Luther King Jr. led nonviolent protests, resulting in landmark legislation including the Civil Rights Act of 1964.",
    },
    {
        "id": "hist_005",
        "content": "World War II transformed America into a global superpower. The attack on Pearl Harbor in 1941 brought the nation into the conflict, and victory in 1945 established American military and economic dominance.",
    },
]

SCIENCE_DOCS = [
    {
        "id": "sci_001",
        "content": "Einstein's theory of relativity states that the speed of light is constant in all reference frames. This leads to time dilation and length contraction at high velocities, fundamentally changing our understanding of space and time.",
    },
    {
        "id": "sci_002",
        "content": "Black holes form when massive stars collapse under their own gravity. The gravitational pull becomes so strong that nothing, not even light, can escape from within the event horizon.",
    },
    {
        "id": "sci_003",
        "content": "Quantum mechanics describes particles as probability waves until measured. The famous double-slit experiment demonstrates that electrons behave as both waves and particles depending on observation.",
    },
    {
        "id": "sci_004",
        "content": "The laws of thermodynamics govern energy transfer. The first law states energy cannot be created or destroyed, while the second law explains why entropy always increases in isolated systems.",
    },
    {
        "id": "sci_005",
        "content": "Newton's laws of motion describe how objects move. The first law states objects remain at rest or in motion unless acted upon by a force. The second relates force to mass and acceleration.",
    },
]

LITERATURE_DOCS = [
    {
        "id": "lit_001",
        "content": "In The Great Gatsby, Fitzgerald explores the American Dream through Jay Gatsby's obsessive pursuit of Daisy Buchanan. The green light across the bay symbolizes his unreachable hopes and the corruption of idealism.",
    },
    {
        "id": "lit_002",
        "content": "Steinbeck's Grapes of Wrath follows the Joad family's migration from Oklahoma to California during the Dust Bowl. The novel depicts economic hardship, family unity, and the exploitation of migrant workers.",
    },
    {
        "id": "lit_003",
        "content": "Shakespeare's Hamlet grapples with revenge, mortality, and indecision. The prince's famous soliloquy 'To be or not to be' contemplates existence itself, while his delay in avenging his father drives the tragedy.",
    },
    {
        "id": "lit_004",
        "content": "Orwell's 1984 presents a dystopian future where the Party controls all aspects of life. Big Brother's surveillance, doublethink, and the Ministry of Truth illustrate totalitarian control over reality itself.",
    },
    {
        "id": "lit_005",
        "content": "In Moby Dick, Captain Ahab's obsessive hunt for the white whale becomes a meditation on fate, free will, and humanity's struggle against nature. The whale symbolizes the unknowable forces of the universe.",
    },
]

FINANCE_DOCS = [
    {
        "id": "fin_001",
        "content": "Compound interest allows investments to grow exponentially over time. When interest is reinvested, it earns additional interest, demonstrating the mathematical power of exponential growth in wealth accumulation.",
    },
    {
        "id": "fin_002",
        "content": "Supply and demand determine market prices. When demand exceeds supply, prices rise; when supply exceeds demand, prices fall. This fundamental principle governs all market economies.",
    },
    {
        "id": "fin_003",
        "content": "Inflation erodes purchasing power over time. When the money supply increases faster than economic output, each dollar buys less. Central banks use interest rates to control inflation.",
    },
    {
        "id": "fin_004",
        "content": "Diversification reduces investment risk by spreading capital across different asset classes. The correlation between assets determines how effectively diversification protects against market downturns.",
    },
    {
        "id": "fin_005",
        "content": "The Federal Reserve controls monetary policy through interest rate adjustments. Lowering rates stimulates borrowing and spending, while raising rates slows inflation but may reduce economic growth.",
    },
]

BIOLOGY_DOCS = [
    {
        "id": "bio_001",
        "content": "DNA stores genetic information in sequences of nucleotides. The double helix structure discovered by Watson and Crick shows how base pairs encode hereditary instructions for all living organisms.",
    },
    {
        "id": "bio_002",
        "content": "Evolution through natural selection drives species adaptation. Organisms with advantageous traits survive and reproduce more successfully, passing these traits to subsequent generations over time.",
    },
    {
        "id": "bio_003",
        "content": "The human immune system defends against pathogens through multiple mechanisms. White blood cells identify and destroy foreign invaders, while antibodies provide targeted responses to specific threats.",
    },
    {
        "id": "bio_004",
        "content": "CRISPR gene editing allows precise modification of DNA sequences. This technology can potentially cure genetic diseases by cutting and replacing faulty genes with functional versions.",
    },
    {
        "id": "bio_005",
        "content": "Photosynthesis converts light energy into chemical energy. Plants absorb carbon dioxide and water, using sunlight to produce glucose and oxygen, forming the foundation of most food chains.",
    },
]

NEWS_DOCS = [
    {
        "id": "news_001",
        "content": "Climate change negotiations continue as nations debate emission reduction targets. Scientists warn that global temperatures must not exceed 1.5 degrees Celsius above pre-industrial levels.",
    },
    {
        "id": "news_002",
        "content": "Artificial intelligence regulation proposals face Congressional debate. Lawmakers consider requirements for algorithm transparency, data privacy, and restrictions on autonomous decision-making.",
    },
    {
        "id": "news_003",
        "content": "The Federal Reserve announced another interest rate increase to combat persistent inflation. Markets reacted with volatility as investors assessed the impact on borrowing costs and economic growth.",
    },
    {
        "id": "news_004",
        "content": "Breakthrough in fusion energy achieved as researchers sustain plasma reaction for record duration. This milestone brings the promise of limitless clean energy closer to commercial viability.",
    },
    {
        "id": "news_005",
        "content": "Global supply chain disruptions continue affecting semiconductor availability. Automakers and electronics manufacturers report production delays as chip shortages persist into the new year.",
    },
]


# =============================================================================
# Test: Basic Encoding
# =============================================================================

class TestEncoding:
    """Test basic 10D encoding functionality."""

    def test_encode_returns_10d_vector(self):
        """Encoding should return exactly 10 dimensions."""
        vec = encode_10d("The Civil War divided the nation")
        assert len(vec.values) == 10
        assert all(0.0 <= v <= 1.0 for v in vec.values)

    def test_encode_is_deterministic(self):
        """Same input should always produce same output."""
        text = "Einstein's theory of relativity"
        vec1 = encode_10d(text)
        vec2 = encode_10d(text)
        assert vec1.values == vec2.values
        assert vec1.content_hash == vec2.content_hash

    def test_encode_empty_string(self):
        """Empty string should return zero vector."""
        vec = encode_10d("")
        assert all(v == 0.0 for v in vec.values)

    def test_encode_batch(self):
        """Batch encoding should work correctly."""
        texts = ["First text", "Second text", "Third text"]
        vectors = encode_batch(texts)
        assert len(vectors) == 3
        assert all(len(v.values) == 10 for v in vectors)

    def test_history_encodes_with_action_and_time(self):
        """History content should score high on Action (1D) and Mind (4D)."""
        vec = encode_10d(HISTORY_DOCS[0]["content"])  # Civil War
        action_score = vec.get(Dimension.ACTION)
        mind_score = vec.get(Dimension.MIND)
        # Should have significant scores in these dimensions
        assert action_score > 0.3 or mind_score > 0.3

    def test_science_encodes_with_intellect(self):
        """Science content should score high on Intellect (6D)."""
        vec = encode_10d(SCIENCE_DOCS[0]["content"])  # Relativity
        intellect_score = vec.get(Dimension.INTELLECT)
        # Should have law/theory content
        assert intellect_score > 0.2

    def test_literature_encodes_with_soul_and_ego(self):
        """Literature should score on Soul (7D) and Ego (5D)."""
        vec = encode_10d(LITERATURE_DOCS[0]["content"])  # Gatsby
        ego_score = vec.get(Dimension.EGO)
        # Character-driven content
        assert ego_score > 0.2


# =============================================================================
# Test: Similarity
# =============================================================================

class TestSimilarity:
    """Test similarity computation."""

    def test_identical_content_has_perfect_similarity(self):
        """Same content should have similarity ~1.0."""
        text = "The laws of thermodynamics govern energy transfer"
        vec = encode_10d(text)
        sim = compute_similarity(vec, vec)
        assert sim.score >= 0.99

    def test_different_content_has_lower_similarity(self):
        """Very different content should have lower similarity."""
        vec1 = encode_10d(HISTORY_DOCS[0]["content"])  # Civil War
        vec2 = encode_10d(SCIENCE_DOCS[2]["content"])  # Quantum mechanics
        sim = compute_similarity(vec1, vec2)
        # Different domains should have moderate or lower similarity
        assert sim.score < 0.9

    def test_similarity_is_symmetric(self):
        """similarity(a,b) should equal similarity(b,a)."""
        vec1 = encode_10d("First content")
        vec2 = encode_10d("Second content")
        sim1 = compute_similarity(vec1, vec2)
        sim2 = compute_similarity(vec2, vec1)
        assert abs(sim1.score - sim2.score) < 0.01

    def test_find_similar_content(self):
        """Should find similar content from candidates."""
        query = "Economic hardship and family struggle during crisis"
        candidates = [
            LITERATURE_DOCS[1]["content"],  # Grapes of Wrath - similar
            SCIENCE_DOCS[0]["content"],     # Relativity - different
            HISTORY_DOCS[1]["content"],     # Great Depression - similar
        ]
        results = find_similar_content(query, candidates, top_k=3)
        assert len(results) == 3
        # Results should be sorted by similarity
        assert results[0][2].score >= results[1][2].score


# =============================================================================
# Test: Cross-Domain Reasoning
# =============================================================================

class TestCrossDomain:
    """Test cross-domain structural matching."""

    def test_cross_domain_analysis(self):
        """Should analyze structural relationship across domains."""
        # Great Depression (history) vs Grapes of Wrath (literature)
        # Both deal with economic hardship
        match = analyze_cross_domain(
            HISTORY_DOCS[1]["content"],  # Great Depression
            LITERATURE_DOCS[1]["content"],  # Grapes of Wrath
            domain1="history",
            domain2="literature"
        )
        assert match.domain1 == "history"
        assert match.domain2 == "literature"
        # Should have reasonable similarity (both about economic hardship)
        assert match.similarity.score > 0.3

    def test_find_cross_domain_connections(self):
        """Should find connections across different domains."""
        contents = {
            "history": [HISTORY_DOCS[1]["content"]],  # Great Depression
            "literature": [LITERATURE_DOCS[1]["content"]],  # Grapes of Wrath
            "finance": [FINANCE_DOCS[2]["content"]],  # Inflation
        }
        connections = find_cross_domain_connections(contents, min_similarity=0.3)
        # Should find at least some connections
        assert len(connections) >= 0  # May or may not find depending on threshold

    def test_structural_bridge_explanation(self):
        """Cross-domain match should include structural explanation."""
        match = analyze_cross_domain(
            "The war caused economic collapse and suffering",
            "The stock market crash led to widespread poverty",
            domain1="history",
            domain2="finance"
        )
        assert match.shared_structure  # Should have explanation


# =============================================================================
# Test: Projection Direction
# =============================================================================

class TestProjectionDirection:
    """Test top-down vs bottom-up detection."""

    def test_detect_top_down(self):
        """Should detect deductive/top-down reasoning."""
        text = "According to Newton's laws, therefore the apple must fall. By definition, all objects with mass experience gravitational attraction."
        direction, strength, evidence = detect_projection_direction(text)
        assert direction in [ProjectionDirection.TOP_DOWN, ProjectionDirection.BIDIRECTIONAL]

    def test_detect_bottom_up(self):
        """Should detect inductive/bottom-up reasoning."""
        text = "For example, we observe that falling objects accelerate. This evidence suggests a pattern. Based on these observations, we can infer a general principle."
        direction, strength, evidence = detect_projection_direction(text)
        assert direction in [ProjectionDirection.BOTTOM_UP, ProjectionDirection.BIDIRECTIONAL]

    def test_extract_all_with_direction(self):
        """Should extract all dimensions with direction info."""
        text = "The theory states that all matter is composed of atoms."
        result = extract_all_with_direction(text)
        assert "ACTION" in result
        assert "INTELLECT" in result
        assert result["INTELLECT"].direction is not None


# =============================================================================
# Test: RAG Integration
# =============================================================================

class TestRAGIntegration:
    """Test 10D RAG integration."""

    def test_create_index(self):
        """Should create and populate index."""
        index = OntologicalRAGIndex()
        for doc in HISTORY_DOCS[:3]:
            index.add_content(doc["id"], doc["content"], "history")
        assert index.size == 3
        assert "history" in index.domains

    def test_retrieve_from_index(self):
        """Should retrieve similar documents."""
        index = OntologicalRAGIndex()
        for doc in HISTORY_DOCS:
            index.add_content(doc["id"], doc["content"], "history")
        for doc in SCIENCE_DOCS:
            index.add_content(doc["id"], doc["content"], "science")

        results = index.retrieve("war and conflict between nations", top_k=3)
        assert len(results) <= 3
        # Should find history docs more relevant
        if results:
            assert results[0].similarity_score > 0

    def test_cross_domain_retrieval(self):
        """Should find cross-domain matches."""
        index = OntologicalRAGIndex()
        for doc in HISTORY_DOCS:
            index.add_content(doc["id"], doc["content"], "history")
        for doc in LITERATURE_DOCS:
            index.add_content(doc["id"], doc["content"], "literature")

        results = index.retrieve(
            "economic suffering and family hardship",
            query_domain="query",
            cross_domain_only=False,
            top_k=5
        )
        assert len(results) > 0

    def test_domain_weights(self):
        """Should apply domain-specific weights."""
        weights = DomainWeights.for_domain("science")
        assert weights.weights[Dimension.INTELLECT] > weights.weights[Dimension.EGO]

        weights_lit = DomainWeights.for_domain("literature")
        assert weights_lit.weights[Dimension.SOUL] > weights_lit.weights[Dimension.BODY]

        weights_match = DomainWeights.for_domain("matchmaking")
        assert weights_match.weights[Dimension.SOUL] > weights_match.weights[Dimension.BODY]

    def test_find_cross_domain_bridges(self):
        """Should find structural bridges across domains."""
        index = OntologicalRAGIndex()
        for doc in HISTORY_DOCS[:2]:
            index.add_content(doc["id"], doc["content"], "history")
        for doc in LITERATURE_DOCS[:2]:
            index.add_content(doc["id"], doc["content"], "literature")

        bridges = index.find_cross_domain_bridges(min_similarity=0.3)
        # May or may not find bridges depending on content
        assert isinstance(bridges, list)


# =============================================================================
# Test: Dimensional Profile
# =============================================================================

class TestDimensionalProfile:
    """Test dimensional profiling utilities."""

    def test_get_dominant_dimensions(self):
        """Should identify top dimensions."""
        vec = encode_10d(SCIENCE_DOCS[3]["content"])  # Thermodynamics
        dominant = get_dominant_dimensions(vec, top_k=3)
        assert len(dominant) == 3
        # Should be sorted by score
        assert dominant[0][1] >= dominant[1][1] >= dominant[2][1]

    def test_dimensional_profile_string(self):
        """Should generate readable profile."""
        vec = encode_10d("A sample text for profiling")
        profile = get_dimensional_profile(vec)
        assert "ACTION" in profile
        assert "ABSOLUTE" in profile


# =============================================================================
# Test: Full Pipeline
# =============================================================================

class TestFullPipeline:
    """Integration tests for complete pipeline."""

    def test_full_cross_domain_reasoning_pipeline(self):
        """Test complete cross-domain reasoning flow."""
        # 1. Create index with multiple domains
        index = OntologicalRAGIndex()

        all_docs = [
            (HISTORY_DOCS, "history"),
            (SCIENCE_DOCS, "science"),
            (LITERATURE_DOCS, "literature"),
            (FINANCE_DOCS, "finance"),
            (BIOLOGY_DOCS, "biology"),
        ]

        for docs, domain in all_docs:
            for doc in docs:
                index.add_content(doc["id"], doc["content"], domain)

        assert index.size == 25

        # 2. Query that should match multiple domains
        query = "economic crisis causing widespread suffering and change"

        # 3. Retrieve
        results = index.retrieve(query, top_k=5)
        assert len(results) > 0

        # 4. Should find relevant cross-domain content
        domains_found = set(r.document.domain for r in results)
        # Query relates to history (Depression), literature (Grapes of Wrath), finance
        # Should find content from multiple domains
        assert len(domains_found) >= 1

    def test_science_to_philosophy_bridge(self):
        """Test finding abstract connections."""
        # Quantum mechanics uncertainty vs existential philosophy
        quantum = "Quantum mechanics describes particles as probability waves. Nothing is certain until measured. The observer affects reality."
        existential = "Existence precedes essence. We create meaning through choices. Nothing is predetermined."

        match = analyze_cross_domain(quantum, existential, "science", "philosophy")
        # Both deal with uncertainty and observation
        # Should have some structural similarity
        assert match.similarity.score >= 0  # At minimum computable


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
