"""
Symbol-U RAG v3.0 - RAG Engine Tests
====================================
Comprehensive pytest tests for the RAG engine components:
- Embeddings (encoder.py)
- Indexing (indexer.py)
- Vector Store (memory_store.py)
- Retrieval (retriever.py)
- Document Loading (loader.py)

All tests are deterministic, LLM-free, and require no network calls.
"""

import os
import tempfile
from typing import List

import pytest

# Import RAG components
from symbolu.rag.embeddings.encoder import (
    embed,
    embed_chunks,
    get_embedding_dim,
    _tokenize,
    _hash_token,
    _normalize,
    EMBEDDING_DIM,
)
from symbolu.rag.indexing.indexer import (
    chunk_text,
    chunk_documents,
    build_index,
)
from symbolu.rag.vectorstore.memory_store import (
    MemoryVectorStore,
    get_global_store,
    reset_global_store,
    _cosine_similarity,
)
from symbolu.rag.retrieval.retriever import (
    retrieve,
    retrieve_with_threshold,
)
from symbolu.rag.ingestion.loader import (
    load_documents,
    load_text,
)
from symbolu.rag.utils.types import (
    Document,
    Chunk,
    ScoredChunk,
    CandidateEntry,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def fresh_store() -> MemoryVectorStore:
    """Create a fresh MemoryVectorStore instance."""
    return MemoryVectorStore()


@pytest.fixture(autouse=True)
def reset_global_store_fixture():
    """Reset global store before each test."""
    reset_global_store()
    yield
    reset_global_store()


@pytest.fixture
def sample_documents() -> List[Document]:
    """Create sample documents for testing."""
    return [
        Document(
            text="Machine learning is a subset of artificial intelligence. "
                 "It involves training models on data to make predictions.",
            metadata={"source": "ml_doc", "topic": "AI"}
        ),
        Document(
            text="Natural language processing enables computers to understand human language. "
                 "It is used in chatbots, translation, and sentiment analysis.",
            metadata={"source": "nlp_doc", "topic": "AI"}
        ),
        Document(
            text="Cooking is the art of preparing food using heat. "
                 "Recipes provide step-by-step instructions for making dishes.",
            metadata={"source": "cooking_doc", "topic": "Food"}
        ),
    ]


@pytest.fixture
def sample_corpus_id() -> str:
    """Corpus ID for testing."""
    return "test_corpus"


@pytest.fixture
def temp_directory_with_files():
    """Create a temporary directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create ML document
        ml_path = os.path.join(tmpdir, "ml_doc.txt")
        with open(ml_path, "w", encoding="utf-8") as f:
            f.write(
                "Machine learning is a subset of artificial intelligence. "
                "It involves training models on data to make predictions. "
                "Deep learning uses neural networks with many layers."
            )

        # Create NLP document
        nlp_path = os.path.join(tmpdir, "nlp_doc.txt")
        with open(nlp_path, "w", encoding="utf-8") as f:
            f.write(
                "Natural language processing enables computers to understand human language. "
                "It is used in chatbots, translation, and sentiment analysis."
            )

        # Create cooking document
        cooking_path = os.path.join(tmpdir, "cooking_doc.md")
        with open(cooking_path, "w", encoding="utf-8") as f:
            f.write(
                "Cooking is the art of preparing food using heat. "
                "Recipes provide step-by-step instructions for making dishes."
            )

        yield tmpdir


# =============================================================================
# Embedding Tests
# =============================================================================


class TestEmbedFunction:
    """Tests for the embed() function."""

    def test_embed_returns_list_of_floats(self) -> None:
        """Test that embed returns a list of floats."""
        result = embed("Hello world")
        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)

    def test_embed_returns_correct_dimension(self) -> None:
        """Test that embed returns vector of correct dimension."""
        result = embed("Test text")
        assert len(result) == EMBEDDING_DIM
        assert len(result) == 256

    def test_embed_is_deterministic(self) -> None:
        """Test that embed produces identical results for identical inputs."""
        text = "This is a deterministic test"
        emb1 = embed(text)
        emb2 = embed(text)
        assert emb1 == emb2

    def test_embed_different_texts_produce_different_embeddings(self) -> None:
        """Test that different texts produce different embeddings."""
        emb1 = embed("Machine learning")
        emb2 = embed("Cooking recipes")
        assert emb1 != emb2

    def test_embed_returns_normalized_vector(self) -> None:
        """Test that embed returns an L2-normalized vector."""
        result = embed("Test normalization")
        # L2 norm should be approximately 1.0
        norm = sum(x ** 2 for x in result) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_embed_empty_string(self) -> None:
        """Test embed with empty string."""
        result = embed("")
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIM

    def test_embed_whitespace_only(self) -> None:
        """Test embed with whitespace-only string."""
        result = embed("   ")
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIM


class TestEmbedChunksFunction:
    """Tests for the embed_chunks() function."""

    def test_embed_chunks_returns_list_of_embeddings(self) -> None:
        """Test that embed_chunks returns list of embedding vectors."""
        chunks = ["Chunk one", "Chunk two", "Chunk three"]
        result = embed_chunks(chunks)
        assert isinstance(result, list)
        assert len(result) == 3
        assert all(len(emb) == EMBEDDING_DIM for emb in result)

    def test_embed_chunks_is_deterministic(self) -> None:
        """Test that embed_chunks produces identical results."""
        chunks = ["First chunk", "Second chunk"]
        result1 = embed_chunks(chunks)
        result2 = embed_chunks(chunks)
        assert result1 == result2

    def test_embed_chunks_empty_list(self) -> None:
        """Test embed_chunks with empty list."""
        result = embed_chunks([])
        assert result == []

    def test_embed_chunks_single_chunk(self) -> None:
        """Test embed_chunks with single chunk."""
        result = embed_chunks(["Single chunk"])
        assert len(result) == 1
        assert len(result[0]) == EMBEDDING_DIM


class TestEmbeddingHelpers:
    """Tests for embedding helper functions."""

    def test_get_embedding_dim(self) -> None:
        """Test get_embedding_dim returns correct value."""
        assert get_embedding_dim() == 256
        assert get_embedding_dim() == EMBEDDING_DIM

    def test_tokenize_basic(self) -> None:
        """Test _tokenize function."""
        tokens = _tokenize("Hello world test")
        assert isinstance(tokens, list)
        assert all(isinstance(t, str) for t in tokens)
        # All tokens should be lowercase
        assert all(t.islower() for t in tokens if t)

    def test_tokenize_filters_short_tokens(self) -> None:
        """Test that _tokenize filters tokens shorter than 2 chars."""
        tokens = _tokenize("a b c hello world")
        # 'a', 'b', 'c' should be filtered out
        assert "a" not in tokens
        assert "b" not in tokens
        assert "c" not in tokens

    def test_hash_token_deterministic(self) -> None:
        """Test _hash_token is deterministic."""
        token = "machine"
        hash1 = _hash_token(token)
        hash2 = _hash_token(token)
        assert hash1 == hash2

    def test_hash_token_different_tokens(self) -> None:
        """Test _hash_token produces different hashes for different tokens."""
        hash1 = _hash_token("hello")
        hash2 = _hash_token("world")
        assert hash1 != hash2

    def test_normalize_function(self) -> None:
        """Test _normalize produces unit vector."""
        vector = [3.0, 4.0, 0.0]
        normalized = _normalize(vector)
        norm = sum(x ** 2 for x in normalized) ** 0.5
        assert abs(norm - 1.0) < 1e-6


# =============================================================================
# Indexing Tests
# =============================================================================


class TestChunkText:
    """Tests for chunk_text() function."""

    def test_chunk_text_short_text(self) -> None:
        """Test chunk_text with short text (single chunk)."""
        text = "Short text"
        chunks = chunk_text(text, chunk_size=300)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_long_text(self) -> None:
        """Test chunk_text with long text (multiple chunks)."""
        text = "This is sentence one. " * 50  # ~1100 chars
        chunks = chunk_text(text, chunk_size=300)
        assert len(chunks) > 1

    def test_chunk_text_respects_approximate_size(self) -> None:
        """Test that chunks are approximately the specified size."""
        text = "Word " * 200  # ~1000 chars
        chunks = chunk_text(text, chunk_size=200)
        # Chunks should not be excessively larger than chunk_size
        for chunk in chunks:
            assert len(chunk) < 400  # Allow some tolerance

    def test_chunk_text_deterministic(self) -> None:
        """Test that chunk_text is deterministic."""
        text = "This is a test text. " * 30
        chunks1 = chunk_text(text, chunk_size=100)
        chunks2 = chunk_text(text, chunk_size=100)
        assert chunks1 == chunks2

    def test_chunk_text_empty_string(self) -> None:
        """Test chunk_text with empty string."""
        chunks = chunk_text("", chunk_size=300)
        assert len(chunks) == 1
        assert chunks[0] == ""

    def test_chunk_text_with_overlap(self) -> None:
        """Test chunk_text with overlap parameter."""
        text = "Word " * 200
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        assert len(chunks) > 1


class TestChunkDocuments:
    """Tests for chunk_documents() function."""

    def test_chunk_documents_single_doc(
        self, sample_documents: List[Document]
    ) -> None:
        """Test chunk_documents with single document."""
        docs = sample_documents[:1]
        chunks = chunk_documents(docs, chunk_size=300)
        assert len(chunks) >= 1
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_documents_multiple_docs(
        self, sample_documents: List[Document]
    ) -> None:
        """Test chunk_documents with multiple documents."""
        chunks = chunk_documents(sample_documents, chunk_size=100)
        assert len(chunks) >= len(sample_documents)

    def test_chunk_documents_preserves_metadata(
        self, sample_documents: List[Document]
    ) -> None:
        """Test that chunk_documents preserves document metadata."""
        chunks = chunk_documents(sample_documents, chunk_size=500)
        # Each chunk should have metadata with doc_idx
        for chunk in chunks:
            assert "doc_idx" in chunk.metadata


class TestBuildIndex:
    """Tests for build_index() function."""

    def test_build_index_basic(
        self, fresh_store: MemoryVectorStore, sample_documents: List[Document]
    ) -> None:
        """Test build_index creates index successfully."""
        corpus_id = "test_build"
        count = build_index(corpus_id, sample_documents, fresh_store, chunk_size=300)
        assert count > 0
        assert fresh_store.count(corpus_id) == count

    def test_build_index_deterministic(
        self, sample_documents: List[Document]
    ) -> None:
        """Test that build_index produces same count for same inputs."""
        store1 = MemoryVectorStore()
        store2 = MemoryVectorStore()

        count1 = build_index("corpus1", sample_documents, store1, chunk_size=200)
        count2 = build_index("corpus2", sample_documents, store2, chunk_size=200)

        assert count1 == count2

    def test_build_index_empty_docs(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test build_index with empty document list."""
        count = build_index("empty_corpus", [], fresh_store)
        assert count == 0


# =============================================================================
# Vector Store Tests
# =============================================================================


class TestMemoryVectorStore:
    """Tests for MemoryVectorStore class."""

    def test_store_instantiation(self) -> None:
        """Test MemoryVectorStore can be instantiated."""
        store = MemoryVectorStore()
        assert store is not None
        assert isinstance(store, MemoryVectorStore)

    def test_store_add_and_count(self, fresh_store: MemoryVectorStore) -> None:
        """Test adding embeddings and counting."""
        corpus_id = "test_corpus"
        embeddings = [embed("test 1"), embed("test 2"), embed("test 3")]
        metadata_list = [
            {"text": "test 1"},
            {"text": "test 2"},
            {"text": "test 3"}
        ]

        fresh_store.add(corpus_id, embeddings, metadata_list)
        assert fresh_store.count(corpus_id) == 3

    def test_store_add_validates_lengths(self, fresh_store: MemoryVectorStore) -> None:
        """Test that add() validates embedding/metadata length match."""
        embeddings = [embed("test")]
        metadata_list = [{"text": "test 1"}, {"text": "test 2"}]  # Mismatched

        with pytest.raises(ValueError):
            fresh_store.add("corpus", embeddings, metadata_list)

    def test_store_search_basic(self, fresh_store: MemoryVectorStore) -> None:
        """Test basic search functionality."""
        corpus_id = "search_test"
        docs = ["machine learning AI", "cooking recipes food", "sports basketball"]
        embeddings = [embed(d) for d in docs]
        metadata_list = [{"text": d} for d in docs]

        fresh_store.add(corpus_id, embeddings, metadata_list)

        query_emb = embed("artificial intelligence machine learning")
        results = fresh_store.search(corpus_id, query_emb, top_k=2)

        assert len(results) == 2
        assert all(isinstance(r, ScoredChunk) for r in results)
        # Results should be sorted by score descending
        assert results[0].score >= results[1].score

    def test_store_search_returns_best_match(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that search returns most relevant result first."""
        corpus_id = "relevance_test"
        docs = [
            "Deep learning neural networks artificial intelligence",
            "Cooking recipes baking bread",
            "Football soccer sports athletics"
        ]
        embeddings = [embed(d) for d in docs]
        metadata_list = [{"text": d} for d in docs]

        fresh_store.add(corpus_id, embeddings, metadata_list)

        # Query about AI
        query_emb = embed("neural networks deep learning AI")
        results = fresh_store.search(corpus_id, query_emb, top_k=3)

        # First result should be about AI
        assert "neural" in results[0].text.lower() or "learning" in results[0].text.lower()

    def test_store_search_empty_corpus(self, fresh_store: MemoryVectorStore) -> None:
        """Test search on empty or non-existent corpus."""
        query_emb = embed("test query")
        results = fresh_store.search("nonexistent", query_emb, top_k=5)
        assert results == []

    def test_store_search_deterministic(
        self, fresh_store: MemoryVectorStore
    ) -> None:
        """Test that search results are deterministic."""
        corpus_id = "deterministic_test"
        docs = ["doc one", "doc two", "doc three"]
        embeddings = [embed(d) for d in docs]
        metadata_list = [{"text": d} for d in docs]

        fresh_store.add(corpus_id, embeddings, metadata_list)

        query_emb = embed("doc one")
        results1 = fresh_store.search(corpus_id, query_emb, top_k=3)
        results2 = fresh_store.search(corpus_id, query_emb, top_k=3)

        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.text == r2.text
            assert r1.score == r2.score

    def test_store_delete_corpus(self, fresh_store: MemoryVectorStore) -> None:
        """Test corpus deletion."""
        corpus_id = "delete_test"
        embeddings = [embed("test")]
        metadata_list = [{"text": "test"}]

        fresh_store.add(corpus_id, embeddings, metadata_list)
        assert fresh_store.count(corpus_id) == 1

        result = fresh_store.delete_corpus(corpus_id)
        assert result is True
        assert fresh_store.count(corpus_id) == 0

    def test_store_list_corpora(self, fresh_store: MemoryVectorStore) -> None:
        """Test listing all corpora."""
        fresh_store.add("corpus1", [embed("a")], [{"text": "a"}])
        fresh_store.add("corpus2", [embed("b")], [{"text": "b"}])

        corpora = fresh_store.list_corpora()
        assert "corpus1" in corpora
        assert "corpus2" in corpora

    def test_store_clear(self, fresh_store: MemoryVectorStore) -> None:
        """Test clearing all data."""
        fresh_store.add("corpus1", [embed("a")], [{"text": "a"}])
        fresh_store.add("corpus2", [embed("b")], [{"text": "b"}])

        fresh_store.clear()

        assert fresh_store.list_corpora() == []


class TestGlobalStore:
    """Tests for global store functions."""

    def test_get_global_store_returns_singleton(self) -> None:
        """Test that get_global_store returns the same instance."""
        reset_global_store()
        store1 = get_global_store()
        store2 = get_global_store()
        assert store1 is store2

    def test_reset_global_store(self) -> None:
        """Test that reset_global_store clears data."""
        store = get_global_store()
        store.add("test", [embed("a")], [{"text": "a"}])

        reset_global_store()

        new_store = get_global_store()
        assert new_store.list_corpora() == []


class TestCosineSimilarity:
    """Tests for _cosine_similarity function."""

    def test_cosine_similarity_identical_vectors(self) -> None:
        """Test cosine similarity of identical vectors is 1.0."""
        vec = [0.5, 0.5, 0.5, 0.5]
        sim = _cosine_similarity(vec, vec)
        assert abs(sim - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self) -> None:
        """Test cosine similarity of orthogonal vectors is 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        sim = _cosine_similarity(vec1, vec2)
        assert abs(sim) < 1e-6

    def test_cosine_similarity_opposite_vectors(self) -> None:
        """Test cosine similarity of opposite vectors is -1.0."""
        vec1 = [1.0, 0.0]
        vec2 = [-1.0, 0.0]
        sim = _cosine_similarity(vec1, vec2)
        assert abs(sim - (-1.0)) < 1e-6

    def test_cosine_similarity_range(self) -> None:
        """Test cosine similarity is in range [-1, 1]."""
        vec1 = embed("hello world")
        vec2 = embed("goodbye moon")
        sim = _cosine_similarity(vec1, vec2)
        assert -1.0 <= sim <= 1.0


# =============================================================================
# Retrieval Tests
# =============================================================================


class TestRetrieve:
    """Tests for retrieve() function."""

    def test_retrieve_basic(
        self, fresh_store: MemoryVectorStore, sample_documents: List[Document]
    ) -> None:
        """Test basic retrieval."""
        corpus_id = "retrieve_test"
        build_index(corpus_id, sample_documents, fresh_store, chunk_size=300)

        results = retrieve("machine learning", corpus_id, fresh_store, top_k=2)

        assert len(results) <= 2
        assert all(isinstance(r, ScoredChunk) for r in results)

    def test_retrieve_returns_sorted_results(
        self, fresh_store: MemoryVectorStore, sample_documents: List[Document]
    ) -> None:
        """Test that retrieve returns results sorted by score."""
        corpus_id = "sorted_test"
        build_index(corpus_id, sample_documents, fresh_store, chunk_size=300)

        results = retrieve("artificial intelligence", corpus_id, fresh_store, top_k=5)

        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_retrieve_deterministic(
        self, fresh_store: MemoryVectorStore, sample_documents: List[Document]
    ) -> None:
        """Test that retrieve is deterministic."""
        corpus_id = "deterministic_retrieve"
        build_index(corpus_id, sample_documents, fresh_store, chunk_size=300)

        query = "natural language processing"
        results1 = retrieve(query, corpus_id, fresh_store, top_k=3)
        results2 = retrieve(query, corpus_id, fresh_store, top_k=3)

        assert len(results1) == len(results2)
        for r1, r2 in zip(results1, results2):
            assert r1.text == r2.text
            assert r1.score == r2.score

    def test_retrieve_empty_corpus(self, fresh_store: MemoryVectorStore) -> None:
        """Test retrieve on empty corpus."""
        results = retrieve("query", "nonexistent", fresh_store, top_k=5)
        assert results == []


class TestRetrieveWithThreshold:
    """Tests for retrieve_with_threshold() function."""

    def test_retrieve_with_threshold_filters_low_scores(
        self, fresh_store: MemoryVectorStore, sample_documents: List[Document]
    ) -> None:
        """Test that retrieve_with_threshold filters low-score results."""
        corpus_id = "threshold_test"
        build_index(corpus_id, sample_documents, fresh_store, chunk_size=300)

        # Get all results first
        all_results = retrieve("machine", corpus_id, fresh_store, top_k=10)

        # Apply threshold
        threshold = 0.1
        filtered_results = retrieve_with_threshold(
            "machine", corpus_id, fresh_store, top_k=10, min_score=threshold
        )

        # All filtered results should have score >= threshold
        for r in filtered_results:
            assert r.score >= threshold

    def test_retrieve_with_threshold_zero(
        self, fresh_store: MemoryVectorStore, sample_documents: List[Document]
    ) -> None:
        """Test retrieve_with_threshold with zero threshold."""
        corpus_id = "zero_threshold"
        build_index(corpus_id, sample_documents, fresh_store, chunk_size=300)

        # Zero threshold should behave like regular retrieve
        results = retrieve_with_threshold(
            "test", corpus_id, fresh_store, top_k=5, min_score=0.0
        )
        assert isinstance(results, list)


# =============================================================================
# Document Loading Tests
# =============================================================================


class TestLoadDocuments:
    """Tests for load_documents() function."""

    def test_load_documents_from_directory(
        self, temp_directory_with_files: str
    ) -> None:
        """Test loading documents from directory."""
        docs = load_documents(temp_directory_with_files)

        assert len(docs) == 3
        assert all(isinstance(d, Document) for d in docs)

    def test_load_documents_from_single_file(
        self, temp_directory_with_files: str
    ) -> None:
        """Test loading a single file."""
        file_path = os.path.join(temp_directory_with_files, "ml_doc.txt")
        docs = load_documents(file_path)

        assert len(docs) == 1
        assert "machine" in docs[0].text.lower()

    def test_load_documents_nonexistent_path(self) -> None:
        """Test load_documents with non-existent path."""
        with pytest.raises(FileNotFoundError):
            load_documents("/nonexistent/path/to/files")

    def test_load_documents_preserves_content(
        self, temp_directory_with_files: str
    ) -> None:
        """Test that document content is preserved."""
        docs = load_documents(temp_directory_with_files)

        # Find the ML document
        ml_docs = [d for d in docs if "machine" in d.text.lower()]
        assert len(ml_docs) == 1
        assert "artificial intelligence" in ml_docs[0].text.lower()


class TestLoadText:
    """Tests for load_text() function."""

    def test_load_text_basic(self) -> None:
        """Test load_text with basic string."""
        text = "This is inline text content."
        doc = load_text(text)

        assert isinstance(doc, Document)
        assert doc.text == text

    def test_load_text_with_source(self) -> None:
        """Test load_text with custom source."""
        text = "Content"
        source = "custom_source"
        doc = load_text(text, source=source)

        assert doc.metadata.get("source") == source

    def test_load_text_default_source(self) -> None:
        """Test load_text default source is 'inline'."""
        doc = load_text("text")
        assert doc.metadata.get("source") == "inline"


# =============================================================================
# Data Type Tests
# =============================================================================


class TestCandidateEntry:
    """Tests for CandidateEntry dataclass."""

    def test_candidate_entry_creation(self) -> None:
        """Test CandidateEntry creation."""
        entry = CandidateEntry(
            text="Test text",
            score=0.85,
            source="test_corpus",
            metadata={"key": "value"}
        )
        assert entry.text == "Test text"
        assert entry.score == 0.85
        assert entry.source == "test_corpus"
        assert entry.metadata["key"] == "value"

    def test_candidate_entry_to_dict(self) -> None:
        """Test CandidateEntry.to_dict() method."""
        entry = CandidateEntry(
            text="Test",
            score=0.5,
            source="src",
            metadata={"a": 1}
        )
        d = entry.to_dict()

        assert d["text"] == "Test"
        assert d["score"] == 0.5
        assert d["source"] == "src"
        assert d["metadata"]["a"] == 1

    def test_candidate_entry_from_scored_chunk(self) -> None:
        """Test CandidateEntry.from_scored_chunk() class method."""
        chunk = ScoredChunk(
            text="Chunk text",
            score=0.75,
            metadata={"chunk_idx": 0}
        )
        entry = CandidateEntry.from_scored_chunk(chunk, source="test_source")

        assert entry.text == "Chunk text"
        assert entry.score == 0.75
        assert entry.source == "test_source"


class TestScoredChunk:
    """Tests for ScoredChunk dataclass."""

    def test_scored_chunk_creation(self) -> None:
        """Test ScoredChunk creation."""
        chunk = ScoredChunk(
            text="Chunk text",
            score=0.9,
            metadata={"doc_idx": 0, "chunk_idx": 1}
        )
        assert chunk.text == "Chunk text"
        assert chunk.score == 0.9
        assert chunk.metadata["doc_idx"] == 0

    def test_scored_chunk_equality(self) -> None:
        """Test ScoredChunk equality."""
        chunk1 = ScoredChunk(text="text", score=0.5, metadata={})
        chunk2 = ScoredChunk(text="text", score=0.5, metadata={})
        assert chunk1 == chunk2


class TestDocument:
    """Tests for Document dataclass."""

    def test_document_creation_minimal(self) -> None:
        """Test Document creation with minimal fields."""
        doc = Document(text="Document text")
        assert doc.text == "Document text"
        assert doc.metadata == {}

    def test_document_creation_with_metadata(self) -> None:
        """Test Document creation with metadata."""
        doc = Document(
            text="Document text",
            metadata={"source": "file.txt", "page": 1}
        )
        assert doc.metadata["source"] == "file.txt"
        assert doc.metadata["page"] == 1


class TestChunk:
    """Tests for Chunk dataclass."""

    def test_chunk_creation(self) -> None:
        """Test Chunk creation."""
        chunk = Chunk(
            text="Chunk text",
            metadata={"doc_idx": 0, "chunk_idx": 0}
        )
        assert chunk.text == "Chunk text"
        assert chunk.metadata["doc_idx"] == 0
