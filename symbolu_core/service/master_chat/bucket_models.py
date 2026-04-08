"""
Bucket Models for Master Chat Context Retrieval
================================================

Data models for the bucket-based context management system.

Buckets are semantic containers that organize harvested knowledge
from the continuous master chat session. Each bucket is associated
with ontological signals (12D layers, Kosha, Vritti, Guna) that
determine activation during context retrieval.

Architecture:
    User Message → Signal Analysis → Bucket Router → Context Assembly
                          ↓
                    Knowledge Harvester → Bucket Store

Version: 1.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4


# =============================================================================
# Bucket Category Taxonomy
# =============================================================================

class BucketCategory(str, Enum):
    """
    Primary bucket categories derived from ontological signals.

    Mapping to 12D Ontological Layers:
        POTENTIAL (1)     → ASPIRATIONS (goals, dreams, possibilities)
        IDENTITY (2)      → SELF (personal facts, preferences, identity)
        EXECUTION (3)     → ACTIONS (tasks, todos, commitments)
        STRUCTURE (4)     → SYSTEMS (processes, workflows, organizations)
        COGNITION (5)     → LEARNING (knowledge, insights, understanding)
        AGENCY (6)        → DECISIONS (choices, rationale, trade-offs)
        REASONING (7)     → ANALYSIS (logic, arguments, evaluations)
        PURPOSE (8)       → VALUES (beliefs, principles, motivations)
        WITNESSES (9)     → RELATIONSHIPS (people, entities, connections)
        UNIFYING (10)     → SYNTHESIS (integrations, patterns, themes)
        INTEGRATION (11)  → PROJECTS (multi-domain work, initiatives)
        ABSOLVING (12)    → CLOSURE (completions, resolutions, endings)
    """
    # Core buckets (mapped from 12D layers)
    ASPIRATIONS = "aspirations"       # Layer 1: POTENTIAL
    SELF = "self"                     # Layer 2: IDENTITY
    ACTIONS = "actions"               # Layer 3: EXECUTION
    SYSTEMS = "systems"               # Layer 4: STRUCTURE
    LEARNING = "learning"             # Layer 5: COGNITION
    DECISIONS = "decisions"           # Layer 6: AGENCY
    ANALYSIS = "analysis"             # Layer 7: REASONING
    VALUES = "values"                 # Layer 8: PURPOSE
    RELATIONSHIPS = "relationships"   # Layer 9: WITNESSES
    SYNTHESIS = "synthesis"           # Layer 10: UNIFYING
    PROJECTS = "projects"             # Layer 11: INTEGRATION
    CLOSURE = "closure"               # Layer 12: ABSOLVING

    # Meta buckets (cross-cutting)
    PREFERENCES = "preferences"       # User preferences extracted from any context
    EMOTIONS = "emotions"             # Emotional states and expressions
    TEMPORAL = "temporal"             # Time-sensitive information


# 12D Layer to Bucket mapping
LAYER_TO_BUCKET: Dict[int, BucketCategory] = {
    1: BucketCategory.ASPIRATIONS,
    2: BucketCategory.SELF,
    3: BucketCategory.ACTIONS,
    4: BucketCategory.SYSTEMS,
    5: BucketCategory.LEARNING,
    6: BucketCategory.DECISIONS,
    7: BucketCategory.ANALYSIS,
    8: BucketCategory.VALUES,
    9: BucketCategory.RELATIONSHIPS,
    10: BucketCategory.SYNTHESIS,
    11: BucketCategory.PROJECTS,
    12: BucketCategory.CLOSURE,
}


# =============================================================================
# Signal Profiles for Bucket Activation
# =============================================================================

@dataclass(frozen=True)
class SignalProfile:
    """
    Ontological signal profile for bucket activation.

    Each bucket has an ideal signal profile. During routing,
    the incoming message's signals are compared against bucket
    profiles to determine activation strength.

    Attributes:
        ontology_layers: List of preferred 12D layer indices [1-12]
        kosha_range: Preferred kosha activation range (low, high) [0-1]
        vritti_types: Preferred vritti motion types
        guna_bias: Preferred guna distribution {"sattva", "rajas", "tamas"}
        entropy_range: Preferred entropy range (low, high) [0-1]
    """
    ontology_layers: tuple[int, ...]
    kosha_range: tuple[float, float] = (0.0, 1.0)
    vritti_types: tuple[str, ...] = ()
    guna_bias: Optional[str] = None
    entropy_range: tuple[float, float] = (0.0, 1.0)


# Default signal profiles for each bucket category
BUCKET_SIGNAL_PROFILES: Dict[BucketCategory, SignalProfile] = {
    # ASPIRATIONS: High layers, upward kosha, sattva-dominant
    BucketCategory.ASPIRATIONS: SignalProfile(
        ontology_layers=(1, 8, 10),
        kosha_range=(0.5, 1.0),  # Higher koshas (vijnanamaya, anandamaya)
        vritti_types=("release", "oscillation"),
        guna_bias="sattva",
        entropy_range=(0.3, 0.7),
    ),

    # SELF: Identity layer, balanced kosha
    BucketCategory.SELF: SignalProfile(
        ontology_layers=(2,),
        kosha_range=(0.2, 0.8),
        vritti_types=("inertia", "release"),
        guna_bias=None,  # Balanced
        entropy_range=(0.2, 0.6),
    ),

    # ACTIONS: Execution layer, lower kosha, rajas-dominant
    BucketCategory.ACTIONS: SignalProfile(
        ontology_layers=(3,),
        kosha_range=(0.0, 0.4),  # Lower koshas (annamaya, pranamaya)
        vritti_types=("activation", "tension"),
        guna_bias="rajas",
        entropy_range=(0.4, 0.8),
    ),

    # SYSTEMS: Structure layer, mid kosha
    BucketCategory.SYSTEMS: SignalProfile(
        ontology_layers=(4,),
        kosha_range=(0.2, 0.6),
        vritti_types=("inertia", "oscillation"),
        guna_bias=None,
        entropy_range=(0.2, 0.5),
    ),

    # LEARNING: Cognition layer, higher kosha, sattva-leaning
    BucketCategory.LEARNING: SignalProfile(
        ontology_layers=(5,),
        kosha_range=(0.4, 0.8),  # manomaya, vijnanamaya
        vritti_types=("oscillation", "release"),
        guna_bias="sattva",
        entropy_range=(0.3, 0.7),
    ),

    # DECISIONS: Agency layer, mid kosha, rajas-leaning
    BucketCategory.DECISIONS: SignalProfile(
        ontology_layers=(6,),
        kosha_range=(0.3, 0.7),
        vritti_types=("activation", "tension"),
        guna_bias="rajas",
        entropy_range=(0.4, 0.7),
    ),

    # ANALYSIS: Reasoning layer, higher kosha
    BucketCategory.ANALYSIS: SignalProfile(
        ontology_layers=(7,),
        kosha_range=(0.5, 0.9),  # vijnanamaya dominant
        vritti_types=("oscillation", "inertia"),
        guna_bias="sattva",
        entropy_range=(0.2, 0.6),
    ),

    # VALUES: Purpose layer, highest kosha, sattva-dominant
    BucketCategory.VALUES: SignalProfile(
        ontology_layers=(8,),
        kosha_range=(0.6, 1.0),  # anandamaya
        vritti_types=("inertia", "release"),
        guna_bias="sattva",
        entropy_range=(0.1, 0.5),
    ),

    # RELATIONSHIPS: Witnesses layer, balanced
    BucketCategory.RELATIONSHIPS: SignalProfile(
        ontology_layers=(9,),
        kosha_range=(0.3, 0.7),
        vritti_types=("oscillation", "release"),
        guna_bias=None,
        entropy_range=(0.3, 0.7),
    ),

    # SYNTHESIS: Unifying layer, high kosha
    BucketCategory.SYNTHESIS: SignalProfile(
        ontology_layers=(10,),
        kosha_range=(0.5, 1.0),
        vritti_types=("oscillation", "inertia"),
        guna_bias="sattva",
        entropy_range=(0.2, 0.6),
    ),

    # PROJECTS: Integration layer, balanced
    BucketCategory.PROJECTS: SignalProfile(
        ontology_layers=(11,),
        kosha_range=(0.3, 0.8),
        vritti_types=("activation", "oscillation"),
        guna_bias="rajas",
        entropy_range=(0.4, 0.8),
    ),

    # CLOSURE: Absolving layer, any kosha, tamas-accepting
    BucketCategory.CLOSURE: SignalProfile(
        ontology_layers=(12,),
        kosha_range=(0.0, 1.0),
        vritti_types=("release", "inertia"),
        guna_bias="tamas",
        entropy_range=(0.1, 0.4),
    ),

    # PREFERENCES: Cross-cutting, identity-adjacent
    BucketCategory.PREFERENCES: SignalProfile(
        ontology_layers=(2, 6, 8),
        kosha_range=(0.2, 0.8),
        vritti_types=("inertia",),
        guna_bias=None,
        entropy_range=(0.2, 0.6),
    ),

    # EMOTIONS: Cross-cutting, kosha-sensitive
    BucketCategory.EMOTIONS: SignalProfile(
        ontology_layers=(2, 8, 9),
        kosha_range=(0.1, 0.6),  # pranamaya, manomaya
        vritti_types=("tension", "release", "activation"),
        guna_bias=None,
        entropy_range=(0.5, 0.9),  # High entropy = emotional content
    ),

    # TEMPORAL: Cross-cutting, time-sensitive
    BucketCategory.TEMPORAL: SignalProfile(
        ontology_layers=(3, 11),
        kosha_range=(0.0, 0.5),
        vritti_types=("activation",),
        guna_bias="rajas",
        entropy_range=(0.4, 0.8),
    ),
}


# =============================================================================
# Bucket Entry Models
# =============================================================================

@dataclass
class BucketEntry:
    """
    A single knowledge entry within a bucket.

    Entries are harvested from conversation turns and contain
    extracted facts, preferences, or other knowledge nuggets.

    Attributes:
        entry_id: Unique identifier for this entry
        content: The harvested text content
        summary: Optional condensed summary
        source_turn_id: ID of the turn this was extracted from
        source_message: Original user/assistant message snippet
        timestamp: When this entry was created
        importance_score: Salience ranking [0.0, 1.0]
        confidence_score: Extraction confidence [0.0, 1.0]
        signal_snapshot: Ontological signals at extraction time
        entities: Extracted named entities
        metadata: Additional metadata
    """
    entry_id: str
    content: str
    source_turn_id: str
    timestamp: datetime
    importance_score: float = 0.5
    confidence_score: float = 0.8
    summary: Optional[str] = None
    source_message: Optional[str] = None
    signal_snapshot: Optional[Dict[str, Any]] = None
    entities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Embedding for semantic search (populated by harvester)
    embedding: Optional[List[float]] = None

    def __post_init__(self):
        if not self.entry_id:
            self.entry_id = str(uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "summary": self.summary,
            "source_turn_id": self.source_turn_id,
            "source_message": self.source_message,
            "timestamp": self.timestamp.isoformat(),
            "importance_score": self.importance_score,
            "confidence_score": self.confidence_score,
            "entities": self.entities,
            "metadata": self.metadata,
        }


@dataclass
class Bucket:
    """
    A semantic bucket containing related knowledge entries.

    Buckets are activated based on signal matching during routing.
    Each bucket maintains statistics for activation tuning.

    Attributes:
        bucket_id: Unique identifier (usually category name)
        category: The bucket category enum
        display_name: Human-readable name
        description: What this bucket contains
        signal_profile: Ideal signal profile for activation
        entries: List of knowledge entries
        created_at: Bucket creation timestamp
        last_accessed: Last activation timestamp
        access_count: Number of times activated
        total_entries: Running count of entries
    """
    bucket_id: str
    category: BucketCategory
    display_name: str
    description: str
    signal_profile: SignalProfile
    entries: List[BucketEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    total_entries: int = 0

    # Computed centroid embedding (average of entry embeddings)
    centroid_embedding: Optional[List[float]] = None

    def add_entry(
        self,
        entry: BucketEntry,
        deduplicate: bool = True,
        similarity_threshold: float = 0.85,
    ) -> bool:
        """
        Add an entry to this bucket with optional deduplication.

        If deduplication is enabled and a similar entry exists:
        - If new entry has higher importance: update existing entry
        - Otherwise: reinforce existing entry (increment access count)

        Args:
            entry: The entry to add
            deduplicate: Whether to check for duplicates
            similarity_threshold: Cosine similarity threshold for duplicates

        Returns:
            True if entry was added/merged, False if discarded as duplicate
        """
        if deduplicate and entry.embedding is not None:
            # Check for semantic duplicates
            merged = self._try_merge_duplicate(entry, similarity_threshold)
            if merged:
                return True

        # No duplicate found or deduplication disabled - add new entry
        self.entries.append(entry)
        self.total_entries += 1
        self._update_centroid(entry)
        return True

    def _try_merge_duplicate(
        self,
        new_entry: BucketEntry,
        threshold: float,
    ) -> bool:
        """
        Try to merge with an existing duplicate entry.

        Returns True if merged (and caller should not add new entry).
        """
        if new_entry.embedding is None:
            return False

        for existing in self.entries:
            if existing.embedding is None:
                continue

            # Compute cosine similarity
            similarity = self._cosine_similarity(
                new_entry.embedding,
                existing.embedding,
            )

            if similarity > threshold:
                # Found a duplicate - decide what to do
                if new_entry.importance_score > existing.importance_score:
                    # New entry is better - update existing
                    existing.content = new_entry.content
                    existing.importance_score = new_entry.importance_score
                    existing.summary = new_entry.summary
                    existing.embedding = new_entry.embedding
                    existing.metadata["updated_at"] = datetime.utcnow().isoformat()
                    existing.metadata["update_count"] = (
                        existing.metadata.get("update_count", 0) + 1
                    )
                else:
                    # Existing is better - just reinforce
                    existing.metadata["access_count"] = (
                        existing.metadata.get("access_count", 0) + 1
                    )
                    existing.metadata["last_reinforced"] = (
                        datetime.utcnow().isoformat()
                    )
                return True

        return False

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b) or len(a) == 0:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def record_access(self) -> None:
        """Record an access/activation of this bucket."""
        self.last_accessed = datetime.utcnow()
        self.access_count += 1

    def get_recent_entries(self, limit: int = 10) -> List[BucketEntry]:
        """Get most recent entries."""
        sorted_entries = sorted(
            self.entries,
            key=lambda e: e.timestamp,
            reverse=True
        )
        return sorted_entries[:limit]

    def get_important_entries(self, limit: int = 10) -> List[BucketEntry]:
        """Get highest importance entries."""
        sorted_entries = sorted(
            self.entries,
            key=lambda e: e.importance_score,
            reverse=True
        )
        return sorted_entries[:limit]

    def _update_centroid(self, new_entry: BucketEntry) -> None:
        """Update centroid embedding with new entry (running average)."""
        if new_entry.embedding is None:
            return

        if self.centroid_embedding is None:
            self.centroid_embedding = new_entry.embedding.copy()
        else:
            # Running average: new_avg = old_avg + (new_val - old_avg) / n
            n = len(self.entries)
            for i in range(len(self.centroid_embedding)):
                self.centroid_embedding[i] += (
                    new_entry.embedding[i] - self.centroid_embedding[i]
                ) / n

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary (without entries for summary)."""
        return {
            "bucket_id": self.bucket_id,
            "category": self.category.value,
            "display_name": self.display_name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "total_entries": self.total_entries,
        }


# =============================================================================
# Activated Bucket Result
# =============================================================================

@dataclass
class ActivatedBucket:
    """
    Result of bucket activation during routing.

    Contains the bucket, activation score, and retrieved entries
    for context injection into the LLM.

    Attributes:
        bucket: The activated bucket
        activation_score: How strongly this bucket was activated [0.0, 1.0]
        retrieved_entries: Entries selected for context injection
        activation_reason: Explanation of why this bucket activated
    """
    bucket: Bucket
    activation_score: float
    retrieved_entries: List[BucketEntry]
    activation_reason: str

    def get_context_text(self, max_entries: int = 5) -> str:
        """Generate context text for LLM injection."""
        entries = self.retrieved_entries[:max_entries]
        if not entries:
            return ""

        lines = [f"[{self.bucket.display_name}]"]
        for entry in entries:
            text = entry.summary or entry.content
            lines.append(f"- {text}")

        return "\n".join(lines)


# =============================================================================
# Signal Snapshot for Routing
# =============================================================================

@dataclass
class MessageSignals:
    """
    Ontological signals extracted from a message for routing.

    This is the input to the bucket router - contains all signal
    values from the 12D/Kosha/Vritti/Guna analysis.

    Attributes:
        ontology_layers: Activated 12D layer indices with weights
        lower_mass: Lower tier mass from MLCR
        upper_mass: Upper tier mass from MLCR
        kosha_activations: Kosha layer activations [0-1] per layer
        kosha_resonance: Overall kosha resonance index
        vritti_distribution: Distribution of vritti types
        dominant_vritti: Most active vritti type
        guna_distribution: Guna probability distribution
        guna_resonance: Guna balance index
        entropy_H_D: Domain entropy
        entropy_H_G: Guna entropy
        entropy_H_K: Kosha entropy
        normalized_entropy: Combined entropy measure
    """
    # 12D Ontology signals
    ontology_layers: Dict[int, float] = field(default_factory=dict)
    lower_mass: float = 0.5
    upper_mass: float = 0.5

    # Kosha signals
    kosha_activations: Dict[str, float] = field(default_factory=dict)
    kosha_resonance: float = 0.5

    # Vritti signals
    vritti_distribution: Dict[str, float] = field(default_factory=dict)
    dominant_vritti: str = "inertia"

    # Guna signals
    guna_distribution: Dict[str, float] = field(default_factory=dict)
    guna_resonance: float = 0.5

    # Entropy signals
    entropy_H_D: float = 0.5
    entropy_H_G: float = 0.5
    entropy_H_K: float = 0.5
    normalized_entropy: float = 0.5

    def get_dominant_layer(self) -> int:
        """Get the most activated ontology layer."""
        if not self.ontology_layers:
            return 5  # Default to COGNITION
        return max(self.ontology_layers, key=lambda k: self.ontology_layers[k])

    def get_kosha_level(self) -> float:
        """Get normalized kosha level (0=physical, 1=bliss)."""
        if not self.kosha_activations:
            return 0.5

        # Weighted average based on layer position
        kosha_order = ["annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya"]
        total_weight = 0.0
        weighted_sum = 0.0

        for i, kosha in enumerate(kosha_order):
            activation = self.kosha_activations.get(kosha, 0.0)
            level = i / (len(kosha_order) - 1)  # 0 to 1
            weighted_sum += activation * level
            total_weight += activation

        return weighted_sum / total_weight if total_weight > 0 else 0.5

    def get_dominant_guna(self) -> Optional[str]:
        """Get the dominant guna if one is clearly dominant."""
        if not self.guna_distribution:
            return None

        dominant = max(self.guna_distribution, key=lambda k: self.guna_distribution[k])
        # Only return if clearly dominant (>40%)
        if self.guna_distribution[dominant] > 0.4:
            return dominant
        return None


# =============================================================================
# Factory Functions
# =============================================================================

def create_default_buckets() -> Dict[str, Bucket]:
    """
    Create the default set of buckets with standard configurations.

    Returns:
        Dictionary mapping bucket_id to Bucket instances
    """
    buckets = {}

    descriptions = {
        BucketCategory.ASPIRATIONS: "Goals, dreams, future possibilities, and desired outcomes",
        BucketCategory.SELF: "Personal facts, identity, preferences, and self-descriptions",
        BucketCategory.ACTIONS: "Tasks, to-dos, commitments, and action items",
        BucketCategory.SYSTEMS: "Processes, workflows, organizations, and structures",
        BucketCategory.LEARNING: "Knowledge acquired, insights gained, things understood",
        BucketCategory.DECISIONS: "Choices made, rationale, trade-offs considered",
        BucketCategory.ANALYSIS: "Logical evaluations, arguments, assessments",
        BucketCategory.VALUES: "Beliefs, principles, motivations, and core values",
        BucketCategory.RELATIONSHIPS: "People, entities, connections, and relationships",
        BucketCategory.SYNTHESIS: "Integrated patterns, themes, and connections",
        BucketCategory.PROJECTS: "Multi-domain initiatives and ongoing work",
        BucketCategory.CLOSURE: "Completed items, resolutions, and endings",
        BucketCategory.PREFERENCES: "Expressed preferences and likes/dislikes",
        BucketCategory.EMOTIONS: "Emotional states and expressions",
        BucketCategory.TEMPORAL: "Time-sensitive and deadline-related information",
    }

    display_names = {
        BucketCategory.ASPIRATIONS: "Aspirations & Goals",
        BucketCategory.SELF: "Self & Identity",
        BucketCategory.ACTIONS: "Actions & Tasks",
        BucketCategory.SYSTEMS: "Systems & Processes",
        BucketCategory.LEARNING: "Learning & Knowledge",
        BucketCategory.DECISIONS: "Decisions & Choices",
        BucketCategory.ANALYSIS: "Analysis & Reasoning",
        BucketCategory.VALUES: "Values & Beliefs",
        BucketCategory.RELATIONSHIPS: "Relationships & People",
        BucketCategory.SYNTHESIS: "Synthesis & Patterns",
        BucketCategory.PROJECTS: "Projects & Initiatives",
        BucketCategory.CLOSURE: "Closure & Completions",
        BucketCategory.PREFERENCES: "Preferences",
        BucketCategory.EMOTIONS: "Emotions & Feelings",
        BucketCategory.TEMPORAL: "Time-Sensitive",
    }

    for category in BucketCategory:
        bucket_id = category.value
        buckets[bucket_id] = Bucket(
            bucket_id=bucket_id,
            category=category,
            display_name=display_names.get(category, category.value.title()),
            description=descriptions.get(category, f"Information related to {category.value}"),
            signal_profile=BUCKET_SIGNAL_PROFILES.get(
                category,
                SignalProfile(ontology_layers=(5,))  # Default to COGNITION
            ),
        )

    return buckets


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Enums
    "BucketCategory",
    # Data classes
    "SignalProfile",
    "BucketEntry",
    "Bucket",
    "ActivatedBucket",
    "MessageSignals",
    # Constants
    "LAYER_TO_BUCKET",
    "BUCKET_SIGNAL_PROFILES",
    # Factory functions
    "create_default_buckets",
]
