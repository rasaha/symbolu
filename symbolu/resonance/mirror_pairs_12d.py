"""
12D Mirror Pair Architecture
=============================

The 12D ontological backbone is structured as 6 mirror pairs,
where lower (concrete) dimensions balance with higher (abstract) dimensions.

Mirror Pairs (12D patent-exact sequence):
    O1_POTENTIAL    ↔  O12_ABSOLVING    (Dormant ↔ Dissolution)
    O2_IDENTITY     ↔  O11_INTEGRATION  (Classification ↔ Consolidation)
    O3_EXECUTION    ↔  O10_UNIFYING     (Action ↔ Connection)
    O4_STRUCTURE    ↔  O9_WITNESSES     (Form ↔ Meta-observation)
    O5_COGNITION    ↔  O8_PURPOSE       (Perception ↔ Teleology)
    O6_AGENCY       ↔  O7_REASONING     (Control ↔ Logic)

This extends the 10D mirror architecture (5 pairs) to 12D (6 pairs),
adding the POTENTIAL ↔ ABSOLVING pair for the new layers.

Key Principles:
    1. Lower layers (1-6) are concrete/grounded
    2. Higher layers (7-12) are abstract/transcendent
    3. Balance score determines insight quality
    4. Imbalance triggers propagation (concrete → abstract)
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional
from enum import Enum

from .types import OntologicalLayer, LAYER_NAMES


# =============================================================================
# 12D Mirror Pair Definitions
# =============================================================================

class MirrorPair12D(Enum):
    """The 6 mirror pairs that structure the 12D space."""

    # Dormant ↔ Dissolution: Latent capacity and terminal release
    POTENTIAL_ABSOLVING = ("O1_POTENTIAL", "O12_ABSOLVING")

    # Classification ↔ Consolidation: How we tag and how we unify
    IDENTITY_INTEGRATION = ("O2_IDENTITY", "O11_INTEGRATION")

    # Action ↔ Connection: What happens and how things connect
    EXECUTION_UNIFYING = ("O3_EXECUTION", "O10_UNIFYING")

    # Form ↔ Meta-observation: Structure and how we observe it
    STRUCTURE_WITNESSES = ("O4_STRUCTURE", "O9_WITNESSES")

    # Perception ↔ Purpose: What we notice and why it matters
    COGNITION_PURPOSE = ("O5_COGNITION", "O8_PURPOSE")

    # Control ↔ Logic: Decisions and their justification
    AGENCY_REASONING = ("O6_AGENCY", "O7_REASONING")


# Direct mapping for fast lookup (layer name → mirror layer name)
MIRROR_MAP_12D: Dict[str, str] = {
    "O1_POTENTIAL": "O12_ABSOLVING",
    "O12_ABSOLVING": "O1_POTENTIAL",
    "O2_IDENTITY": "O11_INTEGRATION",
    "O11_INTEGRATION": "O2_IDENTITY",
    "O3_EXECUTION": "O10_UNIFYING",
    "O10_UNIFYING": "O3_EXECUTION",
    "O4_STRUCTURE": "O9_WITNESSES",
    "O9_WITNESSES": "O4_STRUCTURE",
    "O5_COGNITION": "O8_PURPOSE",
    "O8_PURPOSE": "O5_COGNITION",
    "O6_AGENCY": "O7_REASONING",
    "O7_REASONING": "O6_AGENCY",
}

# Layer index mapping (0-indexed)
MIRROR_INDEX_MAP: Dict[int, int] = {
    0: 11,   # O1_POTENTIAL ↔ O12_ABSOLVING
    11: 0,
    1: 10,   # O2_IDENTITY ↔ O11_INTEGRATION
    10: 1,
    2: 9,    # O3_EXECUTION ↔ O10_UNIFYING
    9: 2,
    3: 8,    # O4_STRUCTURE ↔ O9_WITNESSES
    8: 3,
    4: 7,    # O5_COGNITION ↔ O8_PURPOSE
    7: 4,
    5: 6,    # O6_AGENCY ↔ O7_REASONING
    6: 5,
}

# Lower layers (concrete, grounded) - layers 1-6
LOWER_LAYERS = frozenset({
    "O1_POTENTIAL",
    "O2_IDENTITY",
    "O3_EXECUTION",
    "O4_STRUCTURE",
    "O5_COGNITION",
    "O6_AGENCY",
})

# Higher layers (abstract, transcendent) - layers 7-12
HIGHER_LAYERS = frozenset({
    "O7_REASONING",
    "O8_PURPOSE",
    "O9_WITNESSES",
    "O10_UNIFYING",
    "O11_INTEGRATION",
    "O12_ABSOLVING",
})


def get_mirror_layer(layer: str) -> str:
    """Get the mirror layer for any layer."""
    return MIRROR_MAP_12D[layer]


def get_mirror_index(index: int) -> int:
    """Get the mirror index for any layer index (0-11)."""
    return MIRROR_INDEX_MAP[index]


def is_lower_layer(layer: str) -> bool:
    """Check if layer is in the lower (concrete) set."""
    return layer in LOWER_LAYERS


def is_higher_layer(layer: str) -> bool:
    """Check if layer is in the higher (abstract) set."""
    return layer in HIGHER_LAYERS


# =============================================================================
# Balance Computation
# =============================================================================

@dataclass
class MirrorBalance12D:
    """
    Balance state for a single 12D mirror pair.

    Attributes:
        pair: The mirror pair
        lower_layer: Name of lower layer
        higher_layer: Name of higher layer
        lower_value: Value of lower layer
        higher_value: Value of higher layer
        imbalance: Absolute difference (0 = perfect balance)
        state: Interpretation of the balance
    """
    pair: MirrorPair12D
    lower_layer: str
    higher_layer: str
    lower_value: float
    higher_value: float
    imbalance: float
    state: str  # "balanced", "grounded_only", "abstract_only", "both_low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair.name,
            "lower_layer": self.lower_layer,
            "higher_layer": self.higher_layer,
            "lower": self.lower_value,
            "higher": self.higher_value,
            "imbalance": self.imbalance,
            "state": self.state,
        }


@dataclass
class BalanceReport12D:
    """
    Complete balance analysis for a 12D vector.

    Attributes:
        pairs: Balance state for each mirror pair
        total_imbalance: Sum of all pair imbalances
        balance_score: 0.0 (unbalanced) to 1.0 (perfect)
        dominant_state: Overall characterization
        propagation_needed: Which pairs need propagation
    """
    pairs: List[MirrorBalance12D]
    total_imbalance: float
    balance_score: float
    dominant_state: str
    propagation_needed: List[MirrorPair12D]

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


def compute_balance_12d(
    layer_values: Tuple[float, ...],
    threshold: float = 0.4
) -> BalanceReport12D:
    """
    Compute mirror balance for a 12D layer vector.

    Args:
        layer_values: 12-element tuple of layer values (0.0 to 1.0)
        threshold: Minimum activation to consider "high"

    Returns:
        BalanceReport12D with detailed analysis
    """
    if len(layer_values) != 12:
        raise ValueError(f"Expected 12 layer values, got {len(layer_values)}")

    pairs = []
    total_imbalance = 0.0
    propagation_needed = []

    # 6 mirror pairs for 12D
    pair_definitions = [
        (MirrorPair12D.POTENTIAL_ABSOLVING, 0, 11),    # O1 ↔ O12
        (MirrorPair12D.IDENTITY_INTEGRATION, 1, 10),   # O2 ↔ O11
        (MirrorPair12D.EXECUTION_UNIFYING, 2, 9),      # O3 ↔ O10
        (MirrorPair12D.STRUCTURE_WITNESSES, 3, 8),     # O4 ↔ O9
        (MirrorPair12D.COGNITION_PURPOSE, 4, 7),       # O5 ↔ O8
        (MirrorPair12D.AGENCY_REASONING, 5, 6),        # O6 ↔ O7
    ]

    for pair, lower_idx, higher_idx in pair_definitions:
        lower_val = layer_values[lower_idx]
        higher_val = layer_values[higher_idx]
        imbalance = abs(lower_val - higher_val)
        state = _classify_pair_state(lower_val, higher_val, threshold)

        pairs.append(MirrorBalance12D(
            pair=pair,
            lower_layer=LAYER_NAMES[lower_idx],
            higher_layer=LAYER_NAMES[higher_idx],
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
    # Max possible imbalance is 6.0 (6 pairs × 1.0 max diff each)
    balance_score = 1.0 - (total_imbalance / 6.0)

    # Determine dominant state
    state_counts: Dict[str, int] = {}
    for p in pairs:
        state_counts[p.state] = state_counts.get(p.state, 0) + 1
    dominant_state = max(state_counts, key=lambda k: state_counts[k])

    return BalanceReport12D(
        pairs=pairs,
        total_imbalance=total_imbalance,
        balance_score=balance_score,
        dominant_state=dominant_state,
        propagation_needed=propagation_needed,
    )


def is_transferable_insight_12d(
    layer_values: Tuple[float, ...],
    min_balance: float = 0.3
) -> bool:
    """
    Check if a 12D vector represents a transferable insight.

    Transferable insights have good balance between concrete and abstract.

    Args:
        layer_values: 12-element tuple of layer values
        min_balance: Minimum balance score required

    Returns:
        True if insight is likely transferable across domains
    """
    report = compute_balance_12d(layer_values)
    return report.balance_score >= min_balance


# =============================================================================
# Propagation Mechanism
# =============================================================================

def propagate_to_mirror_12d(
    layer_values: Tuple[float, ...],
    propagation_strength: float = 0.7
) -> Tuple[float, ...]:
    """
    Propagate values from grounded layers to their abstract mirrors.

    When a lower layer is high but its mirror is low,
    this elevates the abstract layer to create balance.

    Args:
        layer_values: Original 12D layer values
        propagation_strength: How much to propagate (0.0 to 1.0)

    Returns:
        New tuple with propagated values
    """
    report = compute_balance_12d(layer_values)

    if not report.propagation_needed:
        return layer_values  # Already balanced

    new_values = list(layer_values)

    for pair in report.propagation_needed:
        # Find the pair's indices
        for balance in report.pairs:
            if balance.pair == pair:
                lower_idx = LAYER_NAMES.index(balance.lower_layer)
                higher_idx = LAYER_NAMES.index(balance.higher_layer)

                # Propagate: higher = lower * strength
                propagated = balance.lower_value * propagation_strength
                current_higher = new_values[higher_idx]
                # Take the max of current and propagated
                new_values[higher_idx] = max(current_higher, propagated)
                break

    return tuple(new_values)


def propagate_iteratively_12d(
    layer_values: Tuple[float, ...],
    max_iterations: int = 3,
    target_balance: float = 0.7
) -> Tuple[Tuple[float, ...], int]:
    """
    Iteratively propagate until balance target is reached.

    Args:
        layer_values: Original 12D values
        max_iterations: Maximum propagation rounds
        target_balance: Stop when this balance is achieved

    Returns:
        Tuple of (final_values, iterations_used)
    """
    current = layer_values

    for i in range(max_iterations):
        report = compute_balance_12d(current)
        if report.balance_score >= target_balance:
            return current, i

        current = propagate_to_mirror_12d(current)

    return current, max_iterations


# =============================================================================
# Utility Functions
# =============================================================================

def explain_balance_12d(report: BalanceReport12D) -> str:
    """Generate human-readable balance explanation for 12D."""
    lines = [f"Balance Score: {report.balance_score:.2f}"]
    lines.append(f"Dominant State: {report.dominant_state}")
    lines.append("")
    lines.append("Mirror Pairs (12D):")

    for pair in report.pairs:
        arrow = "↔" if pair.state == "balanced" else "→" if pair.state == "grounded_only" else "←"
        lines.append(
            f"  {pair.lower_layer} ({pair.lower_value:.2f}) "
            f"{arrow} {pair.higher_layer} ({pair.higher_value:.2f}) [{pair.state}]"
        )

    if report.propagation_needed:
        lines.append("")
        lines.append(f"Propagation needed: {[p.name for p in report.propagation_needed]}")

    return "\n".join(lines)


# =============================================================================
# Bridge to 10D (Backward Compatibility)
# =============================================================================

# Mapping from 10D dimensions to 12D layers
DIMENSION_10D_TO_12D: Dict[str, str] = {
    "ACTION": "O3_EXECUTION",
    "IDENTIFICATION": "O2_IDENTITY",
    "BODY": "O4_STRUCTURE",
    "MIND": "O5_COGNITION",
    "EGO": "O6_AGENCY",
    "INTELLECT": "O7_REASONING",
    "SOUL": "O8_PURPOSE",
    "WITNESS": "O9_WITNESSES",
    "SINGULARITY": "O10_UNIFYING",
    "ABSOLUTE": "O12_ABSOLVING",
}

# Mapping from 12D layers to 10D dimensions
LAYER_12D_TO_DIMENSION_10D: Dict[str, Optional[str]] = {
    "O1_POTENTIAL": None,        # New in 12D
    "O2_IDENTITY": "IDENTIFICATION",
    "O3_EXECUTION": "ACTION",
    "O4_STRUCTURE": "BODY",
    "O5_COGNITION": "MIND",
    "O6_AGENCY": "EGO",
    "O7_REASONING": "INTELLECT",
    "O8_PURPOSE": "SOUL",
    "O9_WITNESSES": "WITNESS",
    "O10_UNIFYING": "SINGULARITY",
    "O11_INTEGRATION": None,     # New in 12D
    "O12_ABSOLVING": "ABSOLUTE",
}


def convert_10d_to_12d(values_10d: Tuple[float, ...]) -> Tuple[float, ...]:
    """
    Convert 10D vector to 12D by inserting new layers.

    O1_POTENTIAL and O11_INTEGRATION are set to 0.0 as they're new.

    Args:
        values_10d: 10-element tuple

    Returns:
        12-element tuple with new layers at 0.0
    """
    if len(values_10d) != 10:
        raise ValueError(f"Expected 10 values, got {len(values_10d)}")

    # 10D order: ACTION, IDENTIFICATION, BODY, MIND, EGO, INTELLECT, SOUL, WITNESS, SINGULARITY, ABSOLUTE
    # 12D order: POTENTIAL, IDENTITY, EXECUTION, STRUCTURE, COGNITION, AGENCY, REASONING, PURPOSE, WITNESSES, UNIFYING, INTEGRATION, ABSOLVING

    return (
        0.0,              # O1_POTENTIAL (new)
        values_10d[1],    # O2_IDENTITY (was IDENTIFICATION)
        values_10d[0],    # O3_EXECUTION (was ACTION)
        values_10d[2],    # O4_STRUCTURE (was BODY)
        values_10d[3],    # O5_COGNITION (was MIND)
        values_10d[4],    # O6_AGENCY (was EGO)
        values_10d[5],    # O7_REASONING (was INTELLECT)
        values_10d[6],    # O8_PURPOSE (was SOUL)
        values_10d[7],    # O9_WITNESSES (was WITNESS)
        values_10d[8],    # O10_UNIFYING (was SINGULARITY)
        0.0,              # O11_INTEGRATION (new)
        values_10d[9],    # O12_ABSOLVING (was ABSOLUTE)
    )


__all__ = [
    # Enums
    "MirrorPair12D",
    # Data
    "MIRROR_MAP_12D",
    "MIRROR_INDEX_MAP",
    "LOWER_LAYERS",
    "HIGHER_LAYERS",
    "DIMENSION_10D_TO_12D",
    "LAYER_12D_TO_DIMENSION_10D",
    # Functions
    "get_mirror_layer",
    "get_mirror_index",
    "is_lower_layer",
    "is_higher_layer",
    "compute_balance_12d",
    "is_transferable_insight_12d",
    "propagate_to_mirror_12d",
    "propagate_iteratively_12d",
    "explain_balance_12d",
    "convert_10d_to_12d",
    # Classes
    "MirrorBalance12D",
    "BalanceReport12D",
]
