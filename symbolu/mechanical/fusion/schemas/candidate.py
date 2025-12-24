"""
Candidate Schema - Input to FusionEngine
Represents a single candidate response from RAG/retrieval
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum


class CandidateSource(str, Enum):
    """Source of candidate generation"""
    HRM = "HRM"      # High-Reasoning Module (symbolic/abstract)
    LCM = "LCM"      # Linguistic Coherence Module (semantic)
    MOE = "MoE"      # Mixture of Experts (domain-specific)
    RAG = "RAG"      # Retrieved from knowledge base
    TEMPLATE = "TEMPLATE"  # Pre-defined template
    

@dataclass
class Candidate:
    """
    A candidate response for fusion
    
    Attributes:
        id: Unique identifier
        text: The actual response text
        source: Where this candidate came from
        channel_scores: Scores from each reasoning channel
        metadata: Additional context
    """
    id: str
    text: str
    source: CandidateSource
    channel_scores: Dict[str, float] = field(default_factory=dict)
    
    # Optional attributes
    domain: Optional[str] = None
    relevance_score: float = 0.0
    confidence: float = 1.0
    
    # Consciousness-aware attributes
    kosha_signature: Optional[List[float]] = None
    ontology_signature: Optional[List[float]] = None
    smi: Optional[float] = None  # Semantic Mismatch Index

    # Cross-domain reasoning attributes
    aspect_vector: Dict[str, float] = field(default_factory=dict)  # Domain-agnostic aspects
    entropy: float = 0.0  # Entropy for stability assessment
    embedding: Optional[List[float]] = None  # For semantic similarity
    template_id: Optional[str] = None  # For redundancy detection

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate candidate"""
        if not self.id:
            raise ValueError("Candidate must have an id")
        if not self.text:
            raise ValueError("Candidate must have text")
        
        # Ensure channel_scores has all three channels
        if not self.channel_scores:
            self.channel_scores = {
                "hrm": 0.0,
                "lcm": 0.0,
                "moe": 0.0
            }
    
    def get_total_channel_score(self) -> float:
        """Sum of all channel scores"""
        return sum(self.channel_scores.values())
    
    def get_weighted_channel_score(self, weights: Dict[str, float]) -> float:
        """Weighted sum of channel scores"""
        return sum(
            self.channel_scores.get(channel, 0.0) * weight
            for channel, weight in weights.items()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "text": self.text,
            "source": self.source.value,
            "channel_scores": self.channel_scores,
            "domain": self.domain,
            "relevance_score": self.relevance_score,
            "confidence": self.confidence,
            "kosha_signature": self.kosha_signature,
            "ontology_signature": self.ontology_signature,
            "smi": self.smi,
            "aspect_vector": self.aspect_vector,
            "entropy": self.entropy,
            "embedding": self.embedding,
            "template_id": self.template_id,
            "metadata": self.metadata,
        }
