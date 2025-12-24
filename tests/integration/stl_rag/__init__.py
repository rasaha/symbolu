"""
STL-RAG Integration Tests
=========================

Tests for the integration between the Symbolic Transformer Engine (STL)
and the RAG (Retrieval-Augmented Generation) system.

Key integration points tested:
1. SemanticRouter routes queries to appropriate corpora based on phoneme signatures
2. CandidatePreFilter filters RAG results using phoneme resonance
3. PhonemeAttentionHead applies attention to RAG candidates
4. HybridRAGEngine combines all components

STL Components:
- symbolu.resonance: Word/phrase vector computation
- symbolu.hybrid.router: Semantic query routing
- symbolu.hybrid.prefilter: Candidate filtering
- symbolu.hybrid.attention: Phoneme-based attention

RAG Components:
- symbolu.rag.retrieval: Query embedding and retrieval
- symbolu.rag.embeddings: Hash-based embedding encoder
- symbolu.rag.vectorstore: In-memory vector store
- symbolu.rag.fixtures.builders: Mock corpus generators
"""
