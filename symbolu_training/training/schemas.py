"""
Training Data Schemas
=====================

Data structures for training consumer providers.

Query-Intent Pairs (for Router):
    Used to train the intent classifier that routes queries
    to appropriate model types.

Paraphrase Pairs (for Embeddings):
    Used to train the embedding encoder via contrastive learning.
    Similar queries should have similar embeddings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
import json


class IntentLabel(Enum):
    """
    Intent labels for router training.
    Maps to ModelType in the provider interfaces.
    """
    REASONING = "reasoning"      # Logic, analysis, problem-solving
    RELATIONSHIP = "relationship"  # Emotions, connections, support
    ACTION = "action"            # Commands, procedures, tasks
    CREATIVE = "creative"        # Art, writing, imagination
    REFLECTIVE = "reflective"    # Philosophy, contemplation
    GENERAL = "general"          # Mixed or unclear intent


@dataclass
class QueryIntentPair:
    """
    A labeled query-intent pair for router training.

    Attributes:
        query: The input query text
        intent: The intent label (maps to ModelType)
        domain: Optional domain hint (physics, emotional, travel, etc.)
        confidence: Labeler confidence (1.0 = certain)
        source: Where this data came from (synthetic, manual, augmented)
        metadata: Additional metadata
    """
    query: str
    intent: IntentLabel
    domain: str = "general"
    confidence: float = 1.0
    source: str = "synthetic"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query": self.query,
            "intent": self.intent.value,
            "domain": self.domain,
            "confidence": self.confidence,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QueryIntentPair":
        """Create from dictionary."""
        return cls(
            query=data["query"],
            intent=IntentLabel(data["intent"]),
            domain=data.get("domain", "general"),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", "synthetic"),
            metadata=data.get("metadata", {}),
        )

    def to_jsonl(self) -> str:
        """Convert to JSONL format."""
        return json.dumps(self.to_dict())


@dataclass
class ParaphrasePair:
    """
    A pair of queries for contrastive embedding training.

    Attributes:
        query_a: First query
        query_b: Second query
        similar: True if semantically similar, False if dissimilar
        similarity_score: Optional continuous similarity (0.0-1.0)
        source: Where this data came from
        metadata: Additional metadata
    """
    query_a: str
    query_b: str
    similar: bool
    similarity_score: Optional[float] = None
    source: str = "synthetic"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "query_a": self.query_a,
            "query_b": self.query_b,
            "similar": self.similar,
            "similarity_score": self.similarity_score,
            "source": self.source,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParaphrasePair":
        """Create from dictionary."""
        return cls(
            query_a=data["query_a"],
            query_b=data["query_b"],
            similar=data["similar"],
            similarity_score=data.get("similarity_score"),
            source=data.get("source", "synthetic"),
            metadata=data.get("metadata", {}),
        )

    def to_jsonl(self) -> str:
        """Convert to JSONL format."""
        return json.dumps(self.to_dict())


@dataclass
class TrainingDataset:
    """
    A complete training dataset with metadata.

    Attributes:
        name: Dataset name
        version: Dataset version
        intent_pairs: List of query-intent pairs
        paraphrase_pairs: List of paraphrase pairs
        metadata: Dataset metadata
    """
    name: str
    version: str
    intent_pairs: List[QueryIntentPair] = field(default_factory=list)
    paraphrase_pairs: List[ParaphrasePair] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_intent_pair(self, pair: QueryIntentPair) -> None:
        """Add an intent pair to the dataset."""
        self.intent_pairs.append(pair)

    def add_paraphrase_pair(self, pair: ParaphrasePair) -> None:
        """Add a paraphrase pair to the dataset."""
        self.paraphrase_pairs.append(pair)

    def get_intent_distribution(self) -> Dict[str, int]:
        """Get distribution of intent labels."""
        dist: Dict[str, int] = {}
        for pair in self.intent_pairs:
            label = pair.intent.value
            dist[label] = dist.get(label, 0) + 1
        return dist

    def get_stats(self) -> Dict[str, Any]:
        """Get dataset statistics."""
        return {
            "name": self.name,
            "version": self.version,
            "intent_pairs_count": len(self.intent_pairs),
            "paraphrase_pairs_count": len(self.paraphrase_pairs),
            "intent_distribution": self.get_intent_distribution(),
            "similar_pairs": sum(1 for p in self.paraphrase_pairs if p.similar),
            "dissimilar_pairs": sum(1 for p in self.paraphrase_pairs if not p.similar),
        }

    def save_intent_pairs(self, path: str) -> int:
        """Save intent pairs to JSONL file. Returns count."""
        with open(path, "w") as f:
            for pair in self.intent_pairs:
                f.write(pair.to_jsonl() + "\n")
        return len(self.intent_pairs)

    def save_paraphrase_pairs(self, path: str) -> int:
        """Save paraphrase pairs to JSONL file. Returns count."""
        with open(path, "w") as f:
            for pair in self.paraphrase_pairs:
                f.write(pair.to_jsonl() + "\n")
        return len(self.paraphrase_pairs)

    @classmethod
    def load_intent_pairs(cls, path: str) -> List[QueryIntentPair]:
        """Load intent pairs from JSONL file."""
        pairs = []
        with open(path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    pairs.append(QueryIntentPair.from_dict(data))
        return pairs

    @classmethod
    def load_paraphrase_pairs(cls, path: str) -> List[ParaphrasePair]:
        """Load paraphrase pairs from JSONL file."""
        pairs = []
        with open(path, "r") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    pairs.append(ParaphrasePair.from_dict(data))
        return pairs
