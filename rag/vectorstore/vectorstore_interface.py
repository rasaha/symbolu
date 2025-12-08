"""
Vectorstore Interface
======================

Abstract interface for vector stores.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class VectorstoreInterface(ABC):
    """Abstract base for vector stores."""
    
    @abstractmethod
    def add(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents to store."""
        pass
    
    @abstractmethod
    def search(self, query_embedding: List[float], k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents."""
        pass
    
    @abstractmethod
    def delete(self, ids: List[str]) -> None:
        """Delete documents by ID."""
        pass
