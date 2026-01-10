"""
Symbol-U RAG v3.1
=================

RAG (Retrieval-Augmented Generation) module for Symbol-U.

Features:
- Document ingestion (.txt, .md)
- Deterministic hash-based embeddings (no external models)
- In-memory vector store with cosine similarity
- Simple indexing and retrieval API
- CandidateEntry integration for Fusion Engine
- Episodic Memory Store (ChromaDB + sentence-transformers)

Public API:
-----------
from symbolu.rag import index_corpus, run_rag

# Index documents
n = index_corpus("my_corpus", "path/to/documents/")

# Run retrieval
candidates = run_rag("search query", "my_corpus", top_k=5)

# Episodic Memory (requires chromadb, sentence-transformers)
from symbolu.rag import EpisodicMemoryStore
memory = EpisodicMemoryStore("./data/episodic_memory")
memory.add_memories(["fact 1", "fact 2"], sources=["wiki"])
results = memory.query_memory("query")

Dependencies:
-------------
Core: Pure Python - no external dependencies required.
Episodic: chromadb, sentence-transformers (optional)

Version: 3.1.0
"""

__version__ = "3.1.0"

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

# Episodic Memory (optional - requires chromadb, sentence-transformers)
# Lazy import to avoid dependency issues
def _get_episodic_store():
    from .episodic_store import EpisodicMemoryStore, create_episodic_memory
    return EpisodicMemoryStore, create_episodic_memory

try:
    EpisodicMemoryStore, create_episodic_memory = _get_episodic_store()
    _HAS_EPISODIC = True
except ImportError:
    EpisodicMemoryStore = None
    create_episodic_memory = None
    _HAS_EPISODIC = False

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

    # Episodic Memory (optional)
    "EpisodicMemoryStore",
    "create_episodic_memory",

    # Metadata
    "__version__",
]
