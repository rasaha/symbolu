"""
Symbol-U RAG v3.0 - Retriever
=============================
Handles query embedding and retrieval from vector store.
"""

from typing import List

from ..utils.types import ScoredChunk
from ..embeddings.encoder import embed
from ..vectorstore.memory_store import MemoryVectorStore


def retrieve(
    query: str,
    corpus_id: str,
    store: MemoryVectorStore,
    top_k: int = 5
) -> List[ScoredChunk]:
    """
    Retrieve most relevant chunks for a query.
    
    Steps:
    1. Embed the query
    2. Search the vector store
    3. Return scored chunks
    
    Args:
        query: Query text string
        corpus_id: Corpus to search in
        store: Vector store instance
        top_k: Number of results to return
    
    Returns:
        List of ScoredChunk objects sorted by relevance (descending)
    
    Examples:
        >>> from rag.vectorstore.memory_store import MemoryVectorStore
        >>> store = MemoryVectorStore()
        >>> results = retrieve("hello", "demo", store, top_k=5)
        >>> isinstance(results, list)
        True
    """
    if not query or not query.strip():
        return []
    
    # Step 1: Embed query
    query_embedding = embed(query)
    
    # Step 2: Search store
    results = store.search(corpus_id, query_embedding, top_k=top_k)
    
    return results


def retrieve_with_threshold(
    query: str,
    corpus_id: str,
    store: MemoryVectorStore,
    top_k: int = 5,
    min_score: float = 0.0
) -> List[ScoredChunk]:
    """
    Retrieve chunks above a minimum similarity threshold.
    
    Args:
        query: Query text string
        corpus_id: Corpus to search in
        store: Vector store instance
        top_k: Maximum number of results
        min_score: Minimum similarity score (0.0 to 1.0)
    
    Returns:
        List of ScoredChunk objects with score >= min_score
    """
    results = retrieve(query, corpus_id, store, top_k=top_k)
    
    # Filter by threshold
    return [r for r in results if r.score >= min_score]
