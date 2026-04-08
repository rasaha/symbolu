"""
Symbol-U RAG v3.0 - Embedding Encoder
=====================================
Deterministic hash-based embedding encoder.
NO external ML models - pure Python implementation.

This uses a simple but effective approach:
1. Tokenize text into words
2. Hash each word to get consistent indices
3. Create a sparse vector representation
4. Normalize for cosine similarity compatibility
"""

import math
import hashlib
from typing import List


# Embedding dimension (powers of 2 work well with hashing)
EMBEDDING_DIM = 256


def embed(text: str) -> List[float]:
    """
    Convert text to a fixed-dimension embedding vector.
    
    Uses deterministic hashing for reproducibility.
    No external models required.
    
    Args:
        text: Input text string
    
    Returns:
        List of floats (normalized embedding vector)
    
    Examples:
        >>> vec = embed("hello world")
        >>> len(vec)
        256
    """
    # Tokenize (simple whitespace + punctuation split)
    tokens = _tokenize(text)
    
    if not tokens:
        # Return zero vector for empty text
        return [0.0] * EMBEDDING_DIM
    
    # Initialize embedding vector
    embedding = [0.0] * EMBEDDING_DIM
    
    # Hash each token to indices and accumulate
    for token in tokens:
        # Get deterministic hash
        token_hash = _hash_token(token)
        
        # Map to index in embedding space
        idx = token_hash % EMBEDDING_DIM
        
        # Use secondary hash for value (positive or negative contribution)
        value_hash = _hash_token(token + "_val")
        value = 1.0 if (value_hash % 2) == 0 else -1.0
        
        # Add token frequency weighting
        embedding[idx] += value
    
    # L2 normalize for cosine similarity
    embedding = _normalize(embedding)
    
    return embedding


def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """
    Embed multiple text chunks.
    
    Args:
        chunks: List of text strings
    
    Returns:
        List of embedding vectors (one per chunk)
    
    Examples:
        >>> vecs = embed_chunks(["hello", "world"])
        >>> len(vecs)
        2
    """
    return [embed(chunk) for chunk in chunks]


def _tokenize(text: str) -> List[str]:
    """
    Simple tokenization: lowercase, split on non-alphanumeric.
    
    Args:
        text: Input text
    
    Returns:
        List of lowercase tokens
    """
    # Lowercase
    text = text.lower()
    
    # Replace non-alphanumeric with spaces
    cleaned = []
    for char in text:
        if char.isalnum():
            cleaned.append(char)
        else:
            cleaned.append(" ")
    
    # Split and filter empty
    tokens = "".join(cleaned).split()
    
    # Filter very short tokens
    tokens = [t for t in tokens if len(t) >= 2]
    
    return tokens


def _hash_token(token: str) -> int:
    """
    Get deterministic hash for a token.
    
    Uses MD5 for reproducibility across Python versions.
    
    Args:
        token: Input token string
    
    Returns:
        Integer hash value
    """
    # MD5 is deterministic and fast (not used for security here)
    hash_bytes = hashlib.md5(token.encode("utf-8")).digest()
    # Convert first 8 bytes to integer
    return int.from_bytes(hash_bytes[:8], byteorder="big")


def _normalize(vector: List[float]) -> List[float]:
    """
    L2 normalize a vector.
    
    Args:
        vector: Input vector
    
    Returns:
        Normalized vector (unit length)
    """
    # Calculate L2 norm
    norm = math.sqrt(sum(x * x for x in vector))
    
    if norm == 0:
        return vector
    
    return [x / norm for x in vector]


def get_embedding_dim() -> int:
    """Return the embedding dimension."""
    return EMBEDDING_DIM
