"""
Mirror Pair Architecture
========================

The 10D ontological backbone is structured as 5 mirror pairs,
where lower (concrete) dimensions balance with higher (abstract) dimensions.

Mirror Pairs:
    1D Acting      ↔  10D Absolving    (Event ↔ Meaning)
    2D Tagging     ↔  9D Unifying      (Naming ↔ Connecting)
    3D Forming     ↔  8D Meta_Observing (Structure ↔ Perspective)
    4D Thinking    ↔  7D Purposing     (Process ↔ Why)
    5D Directing   ↔  6D Reasoning     (Choice ↔ Justification)

Key Principles:
    1. Tag EVENTS, not entities (solves dense clustering)
    2. Balance score determines insight quality
    3. Imbalance triggers propagation (concrete → abstract)
    4. User personas reveal patterns through query tracking

This is pattern matching, not philosophy.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import hashlib
from datetime import datetime

from .encoder import DimensionalVector, Dimension, encode_10d


# =============================================================================
# Mirror Pair Definitions
# =============================================================================

class MirrorPair(Enum):
    """The 5 mirror pairs that structure the 10D space."""

    # Event ↔ Meaning: What happened and what it ultimately means
    ACTION_ABSOLUTE = ("ACTION", "ABSOLUTE")

    # Naming ↔ Connecting: How we tag things and how they unify
    IDENTIFICATION_SINGULARITY = ("IDENTIFICATION", "SINGULARITY")

    # Structure ↔ Perspective: Form and how we observe it
    BODY_WITNESS = ("BODY", "WITNESS")

    # Process ↔ Purpose: How things flow and why they matter
    MIND_SOUL = ("MIND", "SOUL")

    # Choice ↔ Justification: Decisions and their reasoning
    EGO_INTELLECT = ("EGO", "INTELLECT")


# Direct mapping for fast lookup
MIRROR_MAP: Dict[Dimension, Dimension] = {
    Dimension.ACTION: Dimension.ABSOLUTE,
    Dimension.ABSOLUTE: Dimension.ACTION,
    Dimension.IDENTIFICATION: Dimension.SINGULARITY,
    Dimension.SINGULARITY: Dimension.IDENTIFICATION,
    Dimension.BODY: Dimension.WITNESS,
    Dimension.WITNESS: Dimension.BODY,
    Dimension.MIND: Dimension.SOUL,
    Dimension.SOUL: Dimension.MIND,
    Dimension.EGO: Dimension.INTELLECT,
    Dimension.INTELLECT: Dimension.EGO,
}

# Lower dimensions (concrete, dense)
LOWER_DIMENSIONS = {
    Dimension.ACTION,
    Dimension.IDENTIFICATION,
    Dimension.BODY,
    Dimension.MIND,
    Dimension.EGO,
}

# Higher dimensions (abstract, sparse)
HIGHER_DIMENSIONS = {
    Dimension.INTELLECT,
    Dimension.SOUL,
    Dimension.WITNESS,
    Dimension.SINGULARITY,
    Dimension.ABSOLUTE,
}


def get_mirror(dim: Dimension) -> Dimension:
    """Get the mirror dimension for any dimension."""
    return MIRROR_MAP[dim]


def is_lower(dim: Dimension) -> bool:
    """Check if dimension is in the lower (concrete) set."""
    return dim in LOWER_DIMENSIONS


def is_higher(dim: Dimension) -> bool:
    """Check if dimension is in the higher (abstract) set."""
    return dim in HIGHER_DIMENSIONS


# =============================================================================
# Balance Computation
# =============================================================================

@dataclass
class MirrorBalance:
    """
    Balance state for a single mirror pair.

    Attributes:
        pair: The mirror pair
        lower_value: Value of lower dimension
        higher_value: Value of higher dimension
        imbalance: Absolute difference (0 = perfect balance)
        state: Interpretation of the balance
    """
    pair: MirrorPair
    lower_value: float
    higher_value: float
    imbalance: float
    state: str  # "balanced", "grounded_only", "abstract_only", "both_low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair.name,
            "lower": self.lower_value,
            "higher": self.higher_value,
            "imbalance": self.imbalance,
            "state": self.state,
        }


@dataclass
class BalanceReport:
    """
    Complete balance analysis for a 10D vector.

    Attributes:
        pairs: Balance state for each mirror pair
        total_imbalance: Sum of all pair imbalances
        balance_score: 0.0 (unbalanced) to 1.0 (perfect)
        dominant_state: Overall characterization
        propagation_needed: Which pairs need propagation
    """
    pairs: List[MirrorBalance]
    total_imbalance: float
    balance_score: float
    dominant_state: str
    propagation_needed: List[MirrorPair]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pairs": [p.to_dict() for p in self.pairs],
            "total_imbalance": self.total_imbalance,
            "balance_score": self.balance_score,
            "dominant_state": self.dominant_state,
            "propagation_needed": [p.name for p in self.propagation_needed],
        }


def _classify_pair_state(lower: float, higher: float, threshold: float = 0.4) -> str:
    """Classify the state of a mirror pair."""
    if lower >= threshold and higher >= threshold:
        return "balanced"
    elif lower >= threshold and higher < threshold:
        return "grounded_only"  # Has concrete, missing abstract
    elif lower < threshold and higher >= threshold:
        return "abstract_only"  # Has abstract, missing grounding
    else:
        return "both_low"  # Neither activated


def compute_balance(vector: DimensionalVector, threshold: float = 0.4) -> BalanceReport:
    """
    Compute mirror balance for a 10D vector.

    Args:
        vector: The dimensional vector to analyze
        threshold: Minimum activation to consider "high"

    Returns:
        BalanceReport with detailed analysis
    """
    pairs = []
    total_imbalance = 0.0
    propagation_needed = []

    pair_definitions = [
        (MirrorPair.ACTION_ABSOLUTE, Dimension.ACTION, Dimension.ABSOLUTE),
        (MirrorPair.IDENTIFICATION_SINGULARITY, Dimension.IDENTIFICATION, Dimension.SINGULARITY),
        (MirrorPair.BODY_WITNESS, Dimension.BODY, Dimension.WITNESS),
        (MirrorPair.MIND_SOUL, Dimension.MIND, Dimension.SOUL),
        (MirrorPair.EGO_INTELLECT, Dimension.EGO, Dimension.INTELLECT),
    ]

    for pair, lower_dim, higher_dim in pair_definitions:
        lower_val = vector.get(lower_dim)
        higher_val = vector.get(higher_dim)
        imbalance = abs(lower_val - higher_val)
        state = _classify_pair_state(lower_val, higher_val, threshold)

        pairs.append(MirrorBalance(
            pair=pair,
            lower_value=lower_val,
            higher_value=higher_val,
            imbalance=imbalance,
            state=state,
        ))

        total_imbalance += imbalance

        # Need propagation if grounded but not abstract
        if state == "grounded_only":
            propagation_needed.append(pair)

    # Compute balance score (0 to 1, where 1 is perfect balance)
    # Max possible imbalance is 5.0 (5 pairs × 1.0 max diff each)
    balance_score = 1.0 - (total_imbalance / 5.0)

    # Determine dominant state
    state_counts = {}
    for p in pairs:
        state_counts[p.state] = state_counts.get(p.state, 0) + 1
    dominant_state = max(state_counts, key=state_counts.get)

    return BalanceReport(
        pairs=pairs,
        total_imbalance=total_imbalance,
        balance_score=balance_score,
        dominant_state=dominant_state,
        propagation_needed=propagation_needed,
    )


def is_transferable_insight(vector: DimensionalVector, min_balance: float = 0.6) -> bool:
    """
    Check if a vector represents a transferable insight.

    Transferable insights have good balance between concrete and abstract.

    Args:
        vector: The dimensional vector
        min_balance: Minimum balance score required

    Returns:
        True if insight is likely transferable across domains
    """
    report = compute_balance(vector)
    return report.balance_score >= min_balance


# =============================================================================
# Propagation Mechanism
# =============================================================================

def propagate_to_mirror(
    vector: DimensionalVector,
    propagation_strength: float = 0.7
) -> DimensionalVector:
    """
    Propagate values from grounded dimensions to their abstract mirrors.

    When a lower dimension is high but its mirror is low,
    this elevates the abstract dimension to create balance.

    Args:
        vector: Original vector
        propagation_strength: How much to propagate (0.0 to 1.0)

    Returns:
        New vector with propagated values
    """
    report = compute_balance(vector)

    if not report.propagation_needed:
        return vector  # Already balanced

    new_values = list(vector.values)

    for pair in report.propagation_needed:
        # Find the pair's dimensions
        for balance in report.pairs:
            if balance.pair == pair:
                # Get dimension indices
                lower_dim = None
                higher_dim = None

                if pair == MirrorPair.ACTION_ABSOLUTE:
                    lower_dim, higher_dim = Dimension.ACTION, Dimension.ABSOLUTE
                elif pair == MirrorPair.IDENTIFICATION_SINGULARITY:
                    lower_dim, higher_dim = Dimension.IDENTIFICATION, Dimension.SINGULARITY
                elif pair == MirrorPair.BODY_WITNESS:
                    lower_dim, higher_dim = Dimension.BODY, Dimension.WITNESS
                elif pair == MirrorPair.MIND_SOUL:
                    lower_dim, higher_dim = Dimension.MIND, Dimension.SOUL
                elif pair == MirrorPair.EGO_INTELLECT:
                    lower_dim, higher_dim = Dimension.EGO, Dimension.INTELLECT

                if lower_dim and higher_dim:
                    # Propagate: higher = lower * strength
                    propagated = balance.lower_value * propagation_strength
                    current_higher = new_values[higher_dim.value - 1]
                    # Take the max of current and propagated
                    new_values[higher_dim.value - 1] = max(current_higher, propagated)
                break

    return DimensionalVector(
        values=tuple(new_values),
        content_hash=vector.content_hash,
        metadata={**vector.metadata, "propagated": True},
    )


def propagate_iteratively(
    vector: DimensionalVector,
    max_iterations: int = 3,
    target_balance: float = 0.7
) -> Tuple[DimensionalVector, int]:
    """
    Iteratively propagate until balance target is reached.

    Args:
        vector: Original vector
        max_iterations: Maximum propagation rounds
        target_balance: Stop when this balance is achieved

    Returns:
        Tuple of (final_vector, iterations_used)
    """
    current = vector

    for i in range(max_iterations):
        report = compute_balance(current)
        if report.balance_score >= target_balance:
            return current, i

        current = propagate_to_mirror(current)

    return current, max_iterations


# =============================================================================
# Event Tagging (Not Entity Identification)
# =============================================================================

class EventType(Enum):
    """
    Core event types for tagging.

    Tag WHAT HAPPENED, not WHAT IT'S CALLED.
    """
    # Action events (1D)
    CONFLICT = "conflict"
    CREATION = "creation"
    DESTRUCTION = "destruction"
    MOVEMENT = "movement"
    TRANSFORMATION = "transformation"

    # Relationship events (2D)
    DIVISION = "division"
    UNION = "union"
    COMPARISON = "comparison"
    EXCHANGE = "exchange"

    # Structural events (3D)
    FORMATION = "formation"
    COLLAPSE = "collapse"
    GROWTH = "growth"
    DECAY = "decay"

    # Process events (4D)
    SEQUENCE = "sequence"
    CYCLE = "cycle"
    RECURSION = "recursion"
    EMERGENCE = "emergence"

    # Agency events (5D)
    DECISION = "decision"
    CHOICE = "choice"
    LEADERSHIP = "leadership"
    REBELLION = "rebellion"


@dataclass
class TaggedEvent:
    """
    An event tagged from content.

    Attributes:
        event_type: The type of event
        trigger_text: The text that triggered this tag
        dimension: Primary dimension this event activates
        confidence: Confidence in the tagging
    """
    event_type: EventType
    trigger_text: str
    dimension: Dimension
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "trigger": self.trigger_text,
            "dimension": self.dimension.name,
            "confidence": self.confidence,
        }


# Event detection patterns (simple, not regex-heavy)
EVENT_KEYWORDS: Dict[EventType, Tuple[List[str], Dimension]] = {
    # Action events → ACTION dimension
    EventType.CONFLICT: (["war", "battle", "fight", "conflict", "clash", "struggle"], Dimension.ACTION),
    EventType.CREATION: (["create", "build", "found", "establish", "invent", "develop"], Dimension.ACTION),
    EventType.DESTRUCTION: (["destroy", "demolish", "collapse", "fall", "end", "die"], Dimension.ACTION),
    EventType.MOVEMENT: (["move", "migrate", "travel", "spread", "expand", "retreat"], Dimension.ACTION),
    EventType.TRANSFORMATION: (["transform", "change", "evolve", "become", "shift"], Dimension.ACTION),

    # Relationship events → IDENTIFICATION dimension
    EventType.DIVISION: (["divide", "split", "separate", "divorce", "secede", "break"], Dimension.IDENTIFICATION),
    EventType.UNION: (["unite", "merge", "join", "marry", "combine", "ally"], Dimension.IDENTIFICATION),
    EventType.COMPARISON: (["compare", "versus", "against", "like", "unlike"], Dimension.IDENTIFICATION),
    EventType.EXCHANGE: (["trade", "exchange", "give", "take", "buy", "sell"], Dimension.IDENTIFICATION),

    # Structural events → BODY dimension
    EventType.FORMATION: (["form", "structure", "organize", "build", "construct"], Dimension.BODY),
    EventType.COLLAPSE: (["collapse", "crumble", "fall apart", "disintegrate"], Dimension.BODY),
    EventType.GROWTH: (["grow", "expand", "increase", "rise", "scale"], Dimension.BODY),
    EventType.DECAY: (["decay", "decline", "shrink", "diminish", "wither"], Dimension.BODY),

    # Process events → MIND dimension
    EventType.SEQUENCE: (["then", "next", "after", "before", "sequence", "step"], Dimension.MIND),
    EventType.CYCLE: (["cycle", "repeat", "recur", "again", "periodic"], Dimension.MIND),
    EventType.RECURSION: (["recursive", "self-reference", "loop", "iterate"], Dimension.MIND),
    EventType.EMERGENCE: (["emerge", "arise", "appear", "manifest", "surface"], Dimension.MIND),

    # Agency events → EGO dimension
    EventType.DECISION: (["decide", "determine", "resolve", "conclude"], Dimension.EGO),
    EventType.CHOICE: (["choose", "select", "pick", "opt", "prefer"], Dimension.EGO),
    EventType.LEADERSHIP: (["lead", "command", "direct", "govern", "rule"], Dimension.EGO),
    EventType.REBELLION: (["rebel", "revolt", "resist", "defy", "protest"], Dimension.EGO),
}


def tag_events(text: str) -> List[TaggedEvent]:
    """
    Tag events in text (not entities).

    Args:
        text: Content to analyze

    Returns:
        List of tagged events
    """
    text_lower = text.lower()
    events = []

    for event_type, (keywords, dimension) in EVENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                # Find the context around the keyword
                idx = text_lower.find(keyword)
                start = max(0, idx - 20)
                end = min(len(text), idx + len(keyword) + 20)
                context = text[start:end]

                events.append(TaggedEvent(
                    event_type=event_type,
                    trigger_text=context.strip(),
                    dimension=dimension,
                    confidence=0.8,  # Simple confidence
                ))
                break  # One tag per event type

    return events


def events_to_vector_boost(events: List[TaggedEvent]) -> Dict[Dimension, float]:
    """
    Convert tagged events to dimension boosts.

    Args:
        events: List of tagged events

    Returns:
        Dict of dimension → boost amount
    """
    boosts: Dict[Dimension, float] = {}

    for event in events:
        current = boosts.get(event.dimension, 0.0)
        boosts[event.dimension] = min(1.0, current + event.confidence * 0.3)

    return boosts


# =============================================================================
# Balanced Encoding (Event-Based)
# =============================================================================

def encode_with_events(content: str) -> Tuple[DimensionalVector, List[TaggedEvent], BalanceReport]:
    """
    Encode content with event tagging and balance analysis.

    This is the recommended encoding function that:
    1. Tags events (not entities)
    2. Encodes to 10D
    3. Boosts based on events
    4. Computes balance
    5. Propagates if needed

    Args:
        content: Text content

    Returns:
        Tuple of (vector, events, balance_report)
    """
    # Base encoding
    base_vector = encode_10d(content)

    # Tag events
    events = tag_events(content)

    # Apply event boosts
    boosts = events_to_vector_boost(events)
    boosted_values = list(base_vector.values)

    for dim, boost in boosts.items():
        idx = dim.value - 1
        boosted_values[idx] = min(1.0, boosted_values[idx] + boost)

    boosted_vector = DimensionalVector(
        values=tuple(boosted_values),
        content_hash=base_vector.content_hash,
        metadata={"events": [e.event_type.value for e in events]},
    )

    # Propagate to balance
    balanced_vector, iterations = propagate_iteratively(boosted_vector)

    # Compute final balance
    balance = compute_balance(balanced_vector)

    return balanced_vector, events, balance


# =============================================================================
# Utility Functions
# =============================================================================

def explain_balance(report: BalanceReport) -> str:
    """Generate human-readable balance explanation."""
    lines = [f"Balance Score: {report.balance_score:.2f}"]
    lines.append(f"Dominant State: {report.dominant_state}")
    lines.append("")
    lines.append("Mirror Pairs:")

    for pair in report.pairs:
        lower_name = pair.pair.value[0]
        higher_name = pair.pair.value[1]
        arrow = "↔" if pair.state == "balanced" else "→" if pair.state == "grounded_only" else "←"
        lines.append(f"  {lower_name} ({pair.lower_value:.2f}) {arrow} {higher_name} ({pair.higher_value:.2f}) [{pair.state}]")

    if report.propagation_needed:
        lines.append("")
        lines.append(f"Propagation needed: {[p.name for p in report.propagation_needed]}")

    return "\n".join(lines)
