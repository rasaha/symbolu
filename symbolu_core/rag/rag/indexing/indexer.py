"""
Symbol-U RAG v3.0 - Indexer
===========================
Handles text chunking and index building.
Pure Python, no external dependencies.
"""

from typing import List, TYPE_CHECKING

from ..utils.types import Document, Chunk
from ..embeddings.encoder import embed_chunks

if TYPE_CHECKING:
    from ..vectorstore.memory_store import MemoryVectorStore


def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """
    Split text into overlapping chunks.
    
    Uses a simple character-based chunking with sentence-boundary
    awareness where possible.
    
    Args:
        text: Full text to chunk
        chunk_size: Target characters per chunk (default: 300)
        overlap: Characters of overlap between chunks (default: 50)
    
    Returns:
        List of text chunk strings
    
    Examples:
        >>> chunks = chunk_text("Hello world. This is a test.", chunk_size=15)
        >>> len(chunks) >= 1
        True
    """
    if not text or not text.strip():
        return []
    
    # Clean text
    text = text.strip()
    
    # If text is shorter than chunk_size, return as single chunk
    if len(text) <= chunk_size:
        return [text]
    
    chunks: List[str] = []
    start = 0
    
    while start < len(text):
        # Calculate end position
        end = start + chunk_size
        
        if end >= len(text):
            # Last chunk - take everything remaining
            chunk = text[start:].strip()
            if chunk:
                chunks.append(chunk)
            break
        
        # Try to find a sentence boundary (., !, ?) near the end
        boundary = _find_boundary(text, end, chunk_size // 4)
        
        if boundary > start:
            end = boundary
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        # Move start with overlap
        start = max(start + 1, end - overlap)
    
    return chunks


def _find_boundary(text: str, position: int, search_range: int) -> int:
    """
    Find nearest sentence boundary near position.
    
    Args:
        text: Full text
        position: Target position
        search_range: How far to search before/after position
    
    Returns:
        Boundary position, or original position if none found
    """
    # Sentence-ending punctuation
    boundaries = ".!?\n"
    
    # Search backward from position
    for i in range(position, max(0, position - search_range), -1):
        if i < len(text) and text[i] in boundaries:
            return i + 1
    
    # Search forward from position
    for i in range(position, min(len(text), position + search_range)):
        if text[i] in boundaries:
            return i + 1
    
    # No boundary found - return original
    return position


def chunk_documents(docs: List[Document], chunk_size: int = 300) -> List[Chunk]:
    """
    Chunk multiple documents into Chunk objects.
    
    Args:
        docs: List of Document objects
        chunk_size: Target characters per chunk
    
    Returns:
        List of Chunk objects with metadata
    """
    all_chunks: List[Chunk] = []
    
    for doc_idx, doc in enumerate(docs):
        text_chunks = chunk_text(doc.text, chunk_size=chunk_size)
        
        for chunk_idx, text in enumerate(text_chunks):
            chunk_metadata = {
                **doc.metadata,
                "doc_index": doc_idx,
                "chunk_index": chunk_idx,
                "total_chunks": len(text_chunks)
            }
            all_chunks.append(Chunk(text=text, metadata=chunk_metadata))
    
    return all_chunks


def build_index(
    corpus_id: str,
    docs: List[Document],
    store: "MemoryVectorStore",
    chunk_size: int = 300
) -> int:
    """
    Build a searchable index from documents.
    
    Steps:
    1. Chunk all documents
    2. Generate embeddings for chunks
    3. Store in vector store
    
    Args:
        corpus_id: Unique identifier for this corpus
        docs: List of Document objects to index
        store: Vector store instance to use
        chunk_size: Target chunk size in characters
    
    Returns:
        Number of chunks indexed
    
    Examples:
        >>> from rag.vectorstore.memory_store import MemoryVectorStore
        >>> store = MemoryVectorStore()
        >>> docs = [Document(text="Hello world", metadata={})]
        >>> n = build_index("demo", docs, store)
        >>> n >= 1
        True
    """
    if not docs:
        return 0
    
    # Step 1: Chunk documents
    chunks = chunk_documents(docs, chunk_size=chunk_size)
    
    if not chunks:
        return 0
    
    # Step 2: Generate embeddings
    chunk_texts = [c.text for c in chunks]
    embeddings = embed_chunks(chunk_texts)
    
    # Step 3: Prepare metadata list
    metadata_list = [
        {
            **c.metadata,
            "text": c.text  # Store text in metadata for retrieval
        }
        for c in chunks
    ]
    
    # Step 4: Add to store
    store.add(corpus_id, embeddings, metadata_list)
    
    return len(chunks)
