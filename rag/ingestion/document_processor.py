"""
Document Processor
===================

Processes documents for RAG ingestion.
"""

from typing import Dict, Any, List
from symbolu.rag.utils.chunking import chunk_text
from symbolu.rag.utils.text_cleaning import clean_text


class DocumentProcessor:
    """Processes documents into chunks for indexing."""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
    
    def process(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Process text into chunks with metadata."""
        cleaned = clean_text(text)
        chunks = chunk_text(cleaned, self.chunk_size, self.overlap)
        
        return [
            {
                "text": chunk,
                "metadata": {**(metadata or {}), "chunk_index": i}
            }
            for i, chunk in enumerate(chunks)
        ]
