"""
Index Builder
==============

Builds indices for RAG.
"""

from typing import List, Dict, Any
from symbolu.rag.ingestion.ingestion_pipeline import IngestionPipeline
from symbolu.rag.vectorstore.chroma_manager import ChromaManager


class IndexBuilder:
    """Builds and populates indices."""
    
    def __init__(self, vectorstore: ChromaManager = None):
        self.pipeline = IngestionPipeline()
        self.vectorstore = vectorstore or ChromaManager()
    
    def build_from_files(self, file_paths: List[str]) -> int:
        """
        Build index from list of files.
        
        Returns number of chunks indexed.
        """
        total_chunks = 0
        
        for path in file_paths:
            chunks = self.pipeline.ingest(path)
            self.vectorstore.add(chunks)
            total_chunks += len(chunks)
        
        return total_chunks
