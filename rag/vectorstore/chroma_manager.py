"""
ChromaDB Manager
=================

ChromaDB vector store implementation.
"""

from typing import List, Dict, Any, Optional
from symbolu.rag.vectorstore.vectorstore_interface import VectorstoreInterface


class ChromaManager(VectorstoreInterface):
    """ChromaDB implementation of vectorstore."""
    
    def __init__(self, collection_name: str = "symbolu_rag"):
        self.collection_name = collection_name
        self._client = None
        self._collection = None
    
    @property
    def collection(self):
        """Lazy load ChromaDB collection."""
        if self._collection is None:
            try:
                import chromadb
                self._client = chromadb.Client()
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name
                )
            except ImportError:
                raise ImportError("chromadb required: pip install chromadb")
        return self._collection
    
    def add(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to ChromaDB."""
        ids = [f"doc_{i}" for i in range(len(documents))]
        embeddings = [d["embedding"] for d in documents]
        texts = [d["text"] for d in documents]
        metadatas = [d.get("metadata", {}) for d in documents]
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
    
    def search(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Search ChromaDB for similar documents."""
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k
        )
        
        return [
            {
                "id": results["ids"][0][i],
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0
            }
            for i in range(len(results["ids"][0]))
        ]
    
    def delete(self, ids: List[str]) -> None:
        """Delete documents from ChromaDB."""
        self.collection.delete(ids=ids)
