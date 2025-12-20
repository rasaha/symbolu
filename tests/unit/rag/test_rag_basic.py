"""
Symbol-U RAG v3.0 - Unit Tests
==============================
Basic tests using only standard library (tempfile, os).
No external testing libraries required.
"""

import os
import sys
import tempfile

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from symbolu.rag import index_corpus, run_rag, reset_global_store
from symbolu.rag.utils.types import CandidateEntry


def test_index_and_retrieve():
    """
    Test basic indexing and retrieval workflow.
    
    1. Create temp folder with 2 text files
    2. Index the corpus
    3. Run query
    4. Assert best candidate contains expected keyword
    """
    print("=" * 60)
    print("TEST: test_index_and_retrieve")
    print("=" * 60)
    
    # Reset global store before test
    reset_global_store()
    
    # Create temp directory with test files
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create file 1 - about machine learning
        file1_path = os.path.join(tmpdir, "ml_doc.txt")
        with open(file1_path, "w", encoding="utf-8") as f:
            f.write(
                "Machine learning is a subset of artificial intelligence. "
                "It involves training models on data to make predictions. "
                "Deep learning uses neural networks with many layers."
            )
        
        # Create file 2 - about cooking
        file2_path = os.path.join(tmpdir, "cooking_doc.txt")
        with open(file2_path, "w", encoding="utf-8") as f:
            f.write(
                "Cooking is the art of preparing food. "
                "Recipes provide instructions for making dishes. "
                "Baking involves using an oven to cook food."
            )
        
        print(f"Created temp files in: {tmpdir}")
        
        # Step 1: Index the corpus
        corpus_id = "test_corpus"
        num_chunks = index_corpus(corpus_id, tmpdir)
        print(f"Indexed {num_chunks} chunks")
        
        assert num_chunks >= 2, f"Expected at least 2 chunks, got {num_chunks}"
        
        # Step 2: Query for machine learning
        query = "machine learning artificial intelligence"
        candidates = run_rag(query, corpus_id, top_k=5)
        
        print(f"Query: '{query}'")
        print(f"Retrieved {len(candidates)} candidates")
        
        assert len(candidates) > 0, "Expected at least 1 candidate"
        
        # Step 3: Check best candidate contains relevant keyword
        best_candidate = candidates[0]
        print(f"Best candidate (score={best_candidate.score:.3f}):")
        print(f"  {best_candidate.text[:100]}...")
        
        # The best match should contain ML-related keywords
        best_text_lower = best_candidate.text.lower()
        has_ml_keyword = any(
            kw in best_text_lower 
            for kw in ["machine", "learning", "intelligence", "neural"]
        )
        
        assert has_ml_keyword, (
            f"Expected best candidate to contain ML keywords. "
            f"Got: {best_candidate.text[:100]}"
        )
        
        # Verify it's a CandidateEntry
        assert isinstance(best_candidate, CandidateEntry), (
            f"Expected CandidateEntry, got {type(best_candidate)}"
        )
        
        print("✓ TEST PASSED: Best candidate contains expected keywords")
    
    print()
    return True


def test_candidate_entry_structure():
    """Test CandidateEntry dataclass structure."""
    print("=" * 60)
    print("TEST: test_candidate_entry_structure")
    print("=" * 60)
    
    # Create a CandidateEntry
    candidate = CandidateEntry(
        text="Test text content",
        score=0.85,
        source="test_corpus",
        metadata={"key": "value"}
    )
    
    # Check fields
    assert candidate.text == "Test text content"
    assert candidate.score == 0.85
    assert candidate.source == "test_corpus"
    assert candidate.metadata["key"] == "value"
    
    # Check to_dict method
    as_dict = candidate.to_dict()
    assert as_dict["text"] == "Test text content"
    assert as_dict["score"] == 0.85
    
    print("✓ TEST PASSED: CandidateEntry structure is correct")
    print()
    return True


def test_empty_query():
    """Test handling of empty query."""
    print("=" * 60)
    print("TEST: test_empty_query")
    print("=" * 60)
    
    reset_global_store()
    
    # Run with empty query
    candidates = run_rag("", "nonexistent_corpus")
    
    assert candidates == [], f"Expected empty list for empty query, got {candidates}"
    
    print("✓ TEST PASSED: Empty query handled correctly")
    print()
    return True


def test_nonexistent_corpus():
    """Test retrieval from non-existent corpus."""
    print("=" * 60)
    print("TEST: test_nonexistent_corpus")
    print("=" * 60)
    
    reset_global_store()
    
    # Run on corpus that doesn't exist
    candidates = run_rag("some query", "corpus_that_does_not_exist")
    
    assert candidates == [], f"Expected empty list for non-existent corpus"
    
    print("✓ TEST PASSED: Non-existent corpus handled correctly")
    print()
    return True


def test_embedding_determinism():
    """Test that embeddings are deterministic."""
    print("=" * 60)
    print("TEST: test_embedding_determinism")
    print("=" * 60)

    from symbolu.rag.embeddings.encoder import embed
    
    text = "Hello world this is a test"
    
    # Generate embedding twice
    emb1 = embed(text)
    emb2 = embed(text)
    
    # Should be identical
    assert emb1 == emb2, "Embeddings should be deterministic"
    
    # Check dimension
    assert len(emb1) == 256, f"Expected 256 dimensions, got {len(emb1)}"
    
    print(f"✓ TEST PASSED: Embeddings are deterministic (dim={len(emb1)})")
    print()
    return True


def test_chunking():
    """Test text chunking."""
    print("=" * 60)
    print("TEST: test_chunking")
    print("=" * 60)

    from symbolu.rag.indexing.indexer import chunk_text
    
    # Long text
    text = "This is sentence one. " * 50  # ~1100 chars
    
    chunks = chunk_text(text, chunk_size=300)
    
    assert len(chunks) > 1, f"Expected multiple chunks, got {len(chunks)}"
    
    # Check no chunk is too long (with some tolerance)
    for i, chunk in enumerate(chunks):
        assert len(chunk) < 500, f"Chunk {i} too long: {len(chunk)}"
    
    print(f"✓ TEST PASSED: Chunking produced {len(chunks)} chunks")
    print()
    return True


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("SYMBOL-U RAG v3.0 - TEST SUITE")
    print("=" * 60 + "\n")
    
    tests = [
        test_candidate_entry_structure,
        test_empty_query,
        test_nonexistent_corpus,
        test_embedding_determinism,
        test_chunking,
        test_index_and_retrieve,  # Run this last (most complex)
    ]
    
    passed = 0
    failed = 0
    
    for test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ TEST FAILED: {test_func.__name__}")
            print(f"  Error: {e}")
            failed += 1
            print()
    
    print("=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
