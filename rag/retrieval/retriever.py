"""
Base Retriever
===============

Basic retrieval functionality.
"""

from typing import List, Dict, Any
from symbolu.rag.embeddings.embeddings_generator import EmbeddingsGenerator
from symbolu.rag.vectorstore.chroma_manager import ChromaManager


class Retriever:
    """Basic semantic retriever."""
    
    def __init__(self, vectorstore: ChromaManager = None):
        self.vectorstore = vectorstore or ChromaManager()
        self.embeddings = EmbeddingsGenerator()
    
    def retrieve(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for query."""
        query_embedding = self.embeddings.generate_single(query).tolist()
        return self.vectorstore.search(query_embedding, k)
