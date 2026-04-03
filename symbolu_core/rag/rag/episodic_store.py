"""
Symbol-U RAG v3.0 - Episodic Memory Store
==========================================

ChromaDB-backed persistent vector store for episodic memory retrieval.
Uses sentence-transformers (all-MiniLM-L6-v2, 384D) for semantic embeddings.

This module is the "Storage" layer of the Sovereign RAG architecture,
completely separate from the model's 32D reasoning weights.

Usage:
------
    from symbolu_core.rag.episodic_store import EpisodicMemoryStore

    # Initialize (loads or creates DB)
    memory = EpisodicMemoryStore("./data/episodic_memory")

    # Add memories
    memory.add_memories(
        texts=["The Eiffel Tower is in Paris.", "Python was created by Guido."],
        sources=["geography", "programming"]
    )

    # Query
    results = memory.query_memory("Where is the Eiffel Tower?", n_results=3)

Dependencies:
-------------
- chromadb
- sentence-transformers

Version: 1.0.0
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import logging

from .utils.types import ScoredChunk, CandidateEntry

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
_chromadb = None
_SentenceTransformer = None


def _ensure_chromadb():
    """Lazy import chromadb."""
    global _chromadb
    if _chromadb is None:
        try:
            import chromadb
            _chromadb = chromadb
        except ImportError:
            raise ImportError(
                "chromadb is required for EpisodicMemoryStore. "
                "Install with: pip install chromadb"
            )
    return _chromadb


def _ensure_sentence_transformers():
    """Lazy import sentence-transformers."""
    global _SentenceTransformer
    if _SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer
            _SentenceTransformer = SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is required for EpisodicMemoryStore. "
                "Install with: pip install sentence-transformers"
            )
    return _SentenceTransformer


class EpisodicMemoryStore:
    """
    Persistent Vector Database for Episodic Memory.

    This is the "High-Res Storage" (384D) layer that is separate from
    the Sovereign Model's 32D reasoning weights. The embeddings come from
    a frozen, standard sentence-transformers model.

    Architecture:
    - Backend: ChromaDB (persistent, local)
    - Embeddings: all-MiniLM-L6-v2 (384D, fast, sufficient for facts)
    - Storage: Text + metadata only (no 32D state - that's query-side)

    Attributes:
        persistence_path: Path to ChromaDB storage directory
        collection_name: Name of the ChromaDB collection
        embedding_model_name: Sentence-transformers model to use
    """

    DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    DEFAULT_COLLECTION_NAME = "episodic_memory"

    def __init__(
        self,
        persistence_path: str = "./data/episodic_memory",
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
    ):
        """
        Initialize the Episodic Memory Store.

        Args:
            persistence_path: Directory for ChromaDB persistence
            collection_name: Name of the collection to use/create
            embedding_model_name: Sentence-transformers model name
        """
        self.persistence_path = Path(persistence_path)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name

        # Ensure persistence directory exists
        self.persistence_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client
        chromadb = _ensure_chromadb()
        self._client = chromadb.PersistentClient(
            path=str(self.persistence_path)
        )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}  # Use cosine similarity
        )

        # Initialize embedding model (lazy - loaded on first use)
        self._encoder = None

        logger.info(
            f"EpisodicMemoryStore initialized: "
            f"path={self.persistence_path}, "
            f"collection={self.collection_name}, "
            f"count={self._collection.count()}"
        )

    @property
    def encoder(self):
        """Lazy-load the sentence-transformers encoder."""
        if self._encoder is None:
            SentenceTransformer = _ensure_sentence_transformers()
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self._encoder = SentenceTransformer(self.embedding_model_name)
        return self._encoder

    def add_memories(
        self,
        texts: List[str],
        sources: Optional[List[str]] = None,
        metadata: Optional[List[Dict[str, Any]]] = None,
        batch_size: int = 100,
    ) -> int:
        """
        Add text chunks to the episodic memory.

        Args:
            texts: List of text chunks to embed and store
            sources: Optional list of source identifiers (e.g., "WikiText-103")
            metadata: Optional list of metadata dicts per chunk
            batch_size: Batch size for embedding (for memory efficiency)

        Returns:
            Number of chunks added
        """
        if not texts:
            return 0

        n_texts = len(texts)

        # Prepare sources
        if sources is None:
            sources = ["unknown"] * n_texts
        elif len(sources) == 1:
            sources = sources * n_texts
        elif len(sources) != n_texts:
            raise ValueError(f"sources length ({len(sources)}) != texts length ({n_texts})")

        # Prepare metadata
        if metadata is None:
            metadata = [{}] * n_texts
        elif len(metadata) != n_texts:
            raise ValueError(f"metadata length ({len(metadata)}) != texts length ({n_texts})")

        # Merge source into metadata
        full_metadata = [
            {**m, "source": s}
            for m, s in zip(metadata, sources)
        ]

        # Generate unique IDs
        existing_count = self._collection.count()
        ids = [f"chunk_{existing_count + i}" for i in range(n_texts)]

        # Embed and add in batches
        added = 0
        for i in range(0, n_texts, batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            batch_meta = full_metadata[i:i + batch_size]

            # Embed batch
            embeddings = self.encoder.encode(
                batch_texts,
                show_progress_bar=False,
                convert_to_numpy=True,
            ).tolist()

            # Add to ChromaDB
            self._collection.add(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_texts,
                metadatas=batch_meta,
            )

            added += len(batch_texts)

        logger.info(f"Added {added} chunks to episodic memory (total: {self._collection.count()})")
        return added

    def query_memory(
        self,
        query_text: str,
        n_results: int = 3,
        min_score: float = 0.0,
    ) -> List[ScoredChunk]:
        """
        Query the episodic memory for relevant chunks.

        Args:
            query_text: The query to search for
            n_results: Maximum number of results to return
            min_score: Minimum similarity score (0-1, cosine similarity)

        Returns:
            List of ScoredChunk objects with text, score, and metadata
        """
        if self._collection.count() == 0:
            logger.warning("Episodic memory is empty - no results to return")
            return []

        # Embed query
        query_embedding = self.encoder.encode(
            query_text,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).tolist()

        # Query ChromaDB
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        # Convert to ScoredChunk objects
        # ChromaDB returns distances, convert to similarity scores
        # For cosine: distance = 1 - similarity, so similarity = 1 - distance
        chunks = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                score = 1.0 - dist  # Convert distance to similarity
                if score >= min_score:
                    chunks.append(ScoredChunk(
                        text=doc,
                        score=score,
                        metadata=meta,
                    ))

        return chunks

    def query_memory_as_candidates(
        self,
        query_text: str,
        n_results: int = 3,
        min_score: float = 0.0,
    ) -> List[CandidateEntry]:
        """
        Query and return results as CandidateEntry objects.

        This integrates with Symbol-U's Fusion Engine pipeline.

        Args:
            query_text: The query to search for
            n_results: Maximum number of results
            min_score: Minimum similarity score

        Returns:
            List of CandidateEntry objects
        """
        chunks = self.query_memory(query_text, n_results, min_score)
        return [
            CandidateEntry.from_scored_chunk(chunk, chunk.metadata.get("source", "episodic"))
            for chunk in chunks
        ]

    def count(self) -> int:
        """Return the number of chunks in the memory store."""
        return self._collection.count()

    def clear(self) -> None:
        """Clear all entries from the memory store."""
        # Delete and recreate collection
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info("Episodic memory cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the memory store."""
        return {
            "persistence_path": str(self.persistence_path),
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_model_name,
            "chunk_count": self._collection.count(),
        }

    def __repr__(self) -> str:
        return (
            f"EpisodicMemoryStore("
            f"path='{self.persistence_path}', "
            f"count={self._collection.count()})"
        )


# Convenience function for quick initialization
def create_episodic_memory(
    persistence_path: str = "./data/episodic_memory",
) -> EpisodicMemoryStore:
    """
    Create an EpisodicMemoryStore with default settings.

    Args:
        persistence_path: Directory for ChromaDB persistence

    Returns:
        Initialized EpisodicMemoryStore
    """
    return EpisodicMemoryStore(persistence_path=persistence_path)
