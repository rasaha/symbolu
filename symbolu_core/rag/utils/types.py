"""
Symbol-U RAG v3.0 - Shared Data Types
=====================================
Core dataclasses used across all RAG components.
Pure Python, no external dependencies.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional


@dataclass
class Document:
    """
    Represents a loaded document before chunking.
    
    Attributes:
        text: Full document text content
        metadata: Optional metadata (source path, file type, etc.)
    """
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Chunk:
    """
    Represents a text chunk after splitting a document.
    
    Attributes:
        text: Chunk text content
        metadata: Inherited + chunk-specific metadata (index, source, etc.)
    """
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ScoredChunk:
    """
    Represents a chunk with similarity score after retrieval.
    
    Attributes:
        text: Chunk text content
        score: Similarity score (0.0 to 1.0, higher = more similar)
        metadata: Full metadata from the chunk
    """
    text: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CandidateEntry:
    """
    Final candidate entry for Fusion Engine integration.
    
    This is the output format consumed by Symbol-U's stitching
    and rendering pipelines.
    
    Attributes:
        text: Candidate text content
        score: Relevance score (0.0 to 1.0)
        source: Source identifier (corpus_id or document path)
        metadata: Full metadata for traceability
    """
    text: str
    score: float
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON/API output."""
        return {
            "text": self.text,
            "score": self.score,
            "source": self.source,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_scored_chunk(cls, chunk: ScoredChunk, source: str) -> "CandidateEntry":
        """Create CandidateEntry from a ScoredChunk."""
        return cls(
            text=chunk.text,
            score=chunk.score,
            source=source,
            metadata=chunk.metadata
        )
