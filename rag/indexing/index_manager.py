"""
Index Manager
==============

Manages RAG indices.
"""

from typing import Optional
from symbolu.rag.vectorstore.chroma_manager import ChromaManager


class IndexManager:
    """Manages index lifecycle."""
    
    def __init__(self, collection_name: str = "symbolu_rag"):
        self.collection_name = collection_name
        self._store: Optional[ChromaManager] = None
    
    def get_store(self) -> ChromaManager:
        """Get or create the vectorstore."""
        if self._store is None:
            self._store = ChromaManager(self.collection_name)
        return self._store
    
    def clear(self) -> None:
        """Clear the index."""
        # Would implement index clearing
        pass
    
    def stats(self) -> dict:
        """Get index statistics."""
        return {
            "collection": self.collection_name,
            "initialized": self._store is not None
        }
