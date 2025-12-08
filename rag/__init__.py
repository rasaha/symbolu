"""
Symbol-U RAG v3.0
=================

Pure Python RAG (Retrieval-Augmented Generation) module for Symbol-U.

Features:
- Document ingestion (.txt, .md)
- Deterministic hash-based embeddings (no external models)
- In-memory vector store with cosine similarity
- Simple indexing and retrieval API
- CandidateEntry integration for Fusion Engine

Public API:
-----------
from rag import index_corpus, run_rag

# Index documents
n = index_corpus("my_corpus", "path/to/documents/")

# Run retrieval
candidates = run_rag("search query", "my_corpus", top_k=5)

Dependencies:
-------------
Pure Python - no external dependencies required.

Version: 3.0.0
"""

__version__ = "3.0.0"

# Public API exports
from .stitching.pipeline import index_corpus, run_rag

# Additional exports for advanced usage
from .stitching.pipeline import (
    run_rag_multi,
    list_indexed_corpora,
    corpus_stats
)

from .utils.types import (
    Document,
    Chunk,
    ScoredChunk,
    CandidateEntry
)

from .vectorstore.memory_store import (
    MemoryVectorStore,
    get_global_store,
    reset_global_store
)

__all__ = [
    # Primary API
    "index_corpus",
    "run_rag",
    
    # Extended API
    "run_rag_multi",
    "list_indexed_corpora",
    "corpus_stats",
    
    # Data types
    "Document",
    "Chunk",
    "ScoredChunk",
    "CandidateEntry",
    
    # Vector store
    "MemoryVectorStore",
    "get_global_store",
    "reset_global_store",
    
    # Metadata
    "__version__",
]
