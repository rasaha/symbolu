"""
Ingestion Pipeline
===================

Full ingestion pipeline for RAG.
"""

from typing import List, Dict, Any
from symbolu.rag.ingestion.file_loader import FileLoader
from symbolu.rag.ingestion.document_processor import DocumentProcessor
from symbolu.rag.embeddings.embeddings_generator import EmbeddingsGenerator


class IngestionPipeline:
    """Complete ingestion pipeline."""
    
    def __init__(self):
        self.loader = FileLoader()
        self.processor = DocumentProcessor()
        self.embeddings = EmbeddingsGenerator()
    
    def ingest(self, file_path: str) -> List[Dict[str, Any]]:
        """Ingest a file and return chunks with embeddings."""
        # Load file
        content, metadata = self.loader.load(file_path)
        
        # Process into chunks
        chunks = self.processor.process(content, metadata)
        
        # Generate embeddings
        texts = [c["text"] for c in chunks]
        vectors = self.embeddings.generate(texts)
        
        # Combine
        for i, chunk in enumerate(chunks):
            chunk["embedding"] = vectors[i].tolist()
        
        return chunks
