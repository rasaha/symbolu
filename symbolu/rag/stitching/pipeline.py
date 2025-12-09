"""
Symbol-U RAG v3.0 - Stitching Pipeline
======================================
Main public API for Symbol-U RAG integration.

This module provides two simple functions:
- index_corpus(): Index documents from a path
- run_rag(): Run retrieval and return candidates

These integrate with the Fusion Engine's CandidateEntry structure.
"""

from typing import List

from ..utils.types import CandidateEntry, ScoredChunk
from ..ingestion.loader import load_documents
from ..indexing.indexer import build_index
from ..retrieval.retriever import retrieve
from ..vectorstore.memory_store import MemoryVectorStore, get_global_store


def index_corpus(
    corpus_id: str,
    source_path: str,
    store: MemoryVectorStore | None = None,
    chunk_size: int = 300
) -> int:
    """
    Index a corpus from a file or directory path.
    
    This is the main indexing entry point for Symbol-U.
    
    Args:
        corpus_id: Unique identifier for this corpus
        source_path: Path to a file or directory containing .txt/.md files
        store: Optional vector store instance (uses global if not provided)
        chunk_size: Target chunk size in characters (default: 300)
    
    Returns:
        Number of chunks indexed
    
    Raises:
        FileNotFoundError: If source_path doesn't exist
        ValueError: If no valid documents found
    
    Examples:
        >>> n = index_corpus("my_docs", "data/documents/")
        >>> n >= 1
        True
    """
    # Use global store if not provided
    if store is None:
        store = get_global_store()
    
    # Step 1: Load documents
    documents = load_documents(source_path)
    
    # Step 2: Build index
    num_chunks = build_index(
        corpus_id=corpus_id,
        docs=documents,
        store=store,
        chunk_size=chunk_size
    )
    
    return num_chunks


def run_rag(
    query: str,
    corpus_id: str,
    store: MemoryVectorStore | None = None,
    top_k: int = 5
) -> List[CandidateEntry]:
    """
    Run RAG retrieval and return candidates for Fusion Engine.
    
    This is the main retrieval entry point for Symbol-U.
    
    Args:
        query: Query text string
        corpus_id: Corpus to search in
        store: Optional vector store instance (uses global if not provided)
        top_k: Number of candidates to return
    
    Returns:
        List of CandidateEntry objects sorted by relevance
    
    Examples:
        >>> candidates = run_rag("machine learning", "my_docs", top_k=3)
        >>> len(candidates) <= 3
        True
    """
    # Use global store if not provided
    if store is None:
        store = get_global_store()
    
    # Retrieve scored chunks
    scored_chunks: List[ScoredChunk] = retrieve(
        query=query,
        corpus_id=corpus_id,
        store=store,
        top_k=top_k
    )
    
    # Convert to CandidateEntry for Fusion Engine
    candidates: List[CandidateEntry] = []
    for chunk in scored_chunks:
        candidate = CandidateEntry.from_scored_chunk(chunk, source=corpus_id)
        candidates.append(candidate)
    
    return candidates


def run_rag_multi(
    query: str,
    corpus_ids: List[str],
    store: MemoryVectorStore | None = None,
    top_k: int = 5
) -> List[CandidateEntry]:
    """
    Run RAG retrieval across multiple corpora.
    
    Args:
        query: Query text string
        corpus_ids: List of corpus IDs to search
        store: Optional vector store instance
        top_k: Total number of candidates to return (combined)
    
    Returns:
        List of CandidateEntry objects from all corpora, sorted by score
    """
    if store is None:
        store = get_global_store()
    
    all_candidates: List[CandidateEntry] = []
    
    # Retrieve from each corpus
    for corpus_id in corpus_ids:
        candidates = run_rag(query, corpus_id, store, top_k=top_k)
        all_candidates.extend(candidates)
    
    # Sort by score and take top_k
    all_candidates.sort(key=lambda c: c.score, reverse=True)
    return all_candidates[:top_k]


def list_indexed_corpora(store: MemoryVectorStore | None = None) -> List[str]:
    """
    List all indexed corpus IDs.
    
    Args:
        store: Optional vector store instance
    
    Returns:
        List of corpus_id strings
    """
    if store is None:
        store = get_global_store()
    return store.list_corpora()


def corpus_stats(
    corpus_id: str,
    store: MemoryVectorStore | None = None
) -> dict:
    """
    Get statistics for an indexed corpus.
    
    Args:
        corpus_id: Corpus to query
        store: Optional vector store instance
    
    Returns:
        Dict with corpus statistics
    """
    if store is None:
        store = get_global_store()
    
    count = store.count(corpus_id)
    
    return {
        "corpus_id": corpus_id,
        "chunk_count": count,
        "indexed": count > 0
    }
