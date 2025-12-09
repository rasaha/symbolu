"""
Symbol-U RAG v3.0 - Memory Vector Store
=======================================
In-memory vector store with cosine similarity search.
Pure Python - no external vector DB dependencies.
"""

import math
from typing import List, Dict, Any, Tuple


from ..utils.types import ScoredChunk


class MemoryVectorStore:
    """
    Simple in-memory vector store.
    
    Stores embeddings by corpus_id and performs brute-force
    cosine similarity search. Suitable for small to medium
    corpora (< 100K chunks).
    
    Attributes:
        _data: Dict mapping corpus_id -> list of (embedding, metadata)
    """
    
    def __init__(self):
        """Initialize empty store."""
        self._data: Dict[str, List[Tuple[List[float], Dict[str, Any]]]] = {}
    
    def add(
        self,
        corpus_id: str,
        embeddings: List[List[float]],
        metadata_list: List[Dict[str, Any]]
    ) -> None:
        """
        Add embeddings to the store.
        
        Args:
            corpus_id: Unique identifier for this corpus
            embeddings: List of embedding vectors
            metadata_list: List of metadata dicts (must match embeddings length)
        
        Raises:
            ValueError: If embeddings and metadata_list lengths don't match
        
        Examples:
            >>> store = MemoryVectorStore()
            >>> store.add("demo", [[0.1, 0.2]], [{"text": "hello"}])
        """
        if len(embeddings) != len(metadata_list):
            raise ValueError(
                f"Embeddings ({len(embeddings)}) and metadata ({len(metadata_list)}) "
                "must have same length"
            )
        
        # Initialize corpus if needed
        if corpus_id not in self._data:
            self._data[corpus_id] = []
        
        # Add each embedding with its metadata
        for emb, meta in zip(embeddings, metadata_list):
            self._data[corpus_id].append((emb, meta))
    
    def search(
        self,
        corpus_id: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[ScoredChunk]:
        """
        Search for most similar chunks using cosine similarity.
        
        Args:
            corpus_id: Corpus to search in
            query_embedding: Query vector
            top_k: Number of results to return
        
        Returns:
            List of ScoredChunk objects, sorted by score (descending)
        
        Examples:
            >>> store = MemoryVectorStore()
            >>> store.add("demo", [[0.1, 0.2]], [{"text": "hello"}])
            >>> results = store.search("demo", [0.1, 0.2], top_k=1)
            >>> len(results)
            1
        """
        if corpus_id not in self._data:
            return []
        
        corpus_data = self._data[corpus_id]
        
        if not corpus_data:
            return []
        
        # Calculate cosine similarity for each stored embedding
        scored_items: List[Tuple[float, Dict[str, Any]]] = []
        
        for stored_emb, metadata in corpus_data:
            score = _cosine_similarity(query_embedding, stored_emb)
            scored_items.append((score, metadata))
        
        # Sort by score descending
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        # Take top_k
        top_results = scored_items[:top_k]
        
        # Convert to ScoredChunk objects
        results: List[ScoredChunk] = []
        for score, metadata in top_results:
            text = metadata.get("text", "")
            # Create clean metadata without the text field
            clean_metadata = {k: v for k, v in metadata.items() if k != "text"}
            results.append(ScoredChunk(
                text=text,
                score=score,
                metadata=clean_metadata
            ))
        
        return results
    
    def delete_corpus(self, corpus_id: str) -> bool:
        """
        Delete all data for a corpus.
        
        Args:
            corpus_id: Corpus to delete
        
        Returns:
            True if corpus existed and was deleted, False otherwise
        """
        if corpus_id in self._data:
            del self._data[corpus_id]
            return True
        return False
    
    def list_corpora(self) -> List[str]:
        """
        List all corpus IDs in the store.
        
        Returns:
            List of corpus_id strings
        """
        return list(self._data.keys())
    
    def count(self, corpus_id: str) -> int:
        """
        Count chunks in a corpus.
        
        Args:
            corpus_id: Corpus to count
        
        Returns:
            Number of chunks, or 0 if corpus doesn't exist
        """
        if corpus_id not in self._data:
            return 0
        return len(self._data[corpus_id])
    
    def clear(self) -> None:
        """Clear all data from the store."""
        self._data.clear()


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Cosine similarity = (A · B) / (||A|| * ||B||)
    
    Args:
        vec_a: First vector
        vec_b: Second vector
    
    Returns:
        Similarity score in range [-1, 1]
        (usually [0, 1] for normalized positive vectors)
    """
    if len(vec_a) != len(vec_b):
        raise ValueError(
            f"Vector dimensions must match: {len(vec_a)} vs {len(vec_b)}"
        )
    
    # Dot product
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    
    # Magnitudes
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    
    # Avoid division by zero
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


# Global singleton store instance (optional convenience)
_global_store: MemoryVectorStore | None = None


def get_global_store() -> MemoryVectorStore:
    """
    Get or create the global store instance.
    
    Returns:
        Global MemoryVectorStore instance
    """
    global _global_store
    if _global_store is None:
        _global_store = MemoryVectorStore()
    return _global_store


def reset_global_store() -> None:
    """Reset the global store instance."""
    global _global_store
    _global_store = None
