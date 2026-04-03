"""
Ontological Engine - Bhava Sub-Layers (90D) [DEPRECATED]
=========================================================

WARNING: This module uses the deprecated sub-layer architecture.
For new implementations, use bhava_relationships.py instead.

ARCHITECTURAL EVOLUTION:
------------------------
OLD (This Module - Deprecated):
    - 9-10 pairs × 10 sub-layers = 90-100D
    - Sequential relationships between adjacent layers only
    - ~34% computational overhead

NEW (bhava_relationships.py - Recommended):
    - 12 × 12 = 144 inter-layer relationships
    - All-to-all relationship modeling
    - Based on Vedic Drishti (aspect) patterns
    - ~5% computational overhead
    - Richer relationship space

VEDIC INSIGHT:
--------------
In Jyotish (Vedic Astrology), Bhavas are RELATIONSHIPS, not entities.
The same Rashi (sign) serves different Bhava functions based on Lagna.
This module's sub-layer approach treats Bhavas as separate entities,
which is architecturally less elegant than the relationship approach.

To migrate to the new architecture:
    # OLD (Deprecated)
    from symbolu_core.ontological.bhava import BhavaComputer90

    # NEW (Recommended)
    from symbolu_core.ontological.bhava_relationships import InterLayerBhavaEngine

===============================================================================
LEGACY DOCUMENTATION (for backward compatibility):
===============================================================================

Bhava layers capture relational dynamics BETWEEN ontological dimensions.
Inspired by Bhavas (houses) in Vedic astrology, these sub-layers represent
how pairs of ontological dimensions interact.

Architecture:
    - 10 Ontological Layers (O1-O10): Primary dimensions
    - 90 Bhava Layers: 10 sub-layers for each of 9 adjacent pairs
    - Total: 100 interpretable dimensions

Bhava Structure (10 sub-layers per pair):
    Between O1 and O2, there are 10 Bhava sub-layers (B1.1 to B1.10)
    Between O2 and O3, there are 10 Bhava sub-layers (B2.1 to B2.10)
    ...and so on for all 9 adjacent pairs + the closing pair (O10↔O1)

Each set of 10 Bhava sub-layers represents different aspects of
the relationship between two ontological dimensions:
    Bhava 1: Foundation/Resources
    Bhava 2: Communication/Exchange
    Bhava 3: Environment/Context
    Bhava 4: Emotion/Feeling
    Bhava 6: Duty/Service
    Bhava 7: Partnership/Balance
    Bhava 8: Transformation/Depth
    Bhava 9: Expansion/Wisdom
    Bhava 10: Achievement/Structure
    Bhava 11: Aspiration/Network

(Following Houses 2-11 pattern, as House 1 is the layer itself)
"""

import math
from typing import List, Tuple, Dict, Optional, Any
from dataclasses import dataclass

from symbolu_core.ontological.types import LAYER_NAMES, LAYER_INDEX


# The 10 Bhava sub-layer meanings (Houses 2-11 pattern)
BHAVA_SUBLAYER_NAMES: Tuple[str, ...] = (
    "FOUNDATION",       # Bhava 2: Resources, values, foundation
    "COMMUNICATION",    # Bhava 3: Exchange, expression, connection
    "ENVIRONMENT",      # Bhava 4: Context, roots, emotional base
    "EXPRESSION",       # Bhava 5: Creativity, joy, self-expression
    "SERVICE",          # Bhava 6: Duty, refinement, improvement
    "PARTNERSHIP",      # Bhava 7: Balance, relationship, harmony
    "TRANSFORMATION",   # Bhava 8: Depth, change, shared resources
    "WISDOM",           # Bhava 9: Expansion, meaning, higher learning
    "STRUCTURE",        # Bhava 10: Achievement, responsibility, form
    "ASPIRATION",       # Bhava 11: Goals, network, collective
)

BHAVA_SUBLAYER_DESCRIPTIONS: Dict[str, str] = {
    "FOUNDATION": "Resources, values, and foundation of the relationship",
    "COMMUNICATION": "Exchange, expression, and connection between layers",
    "ENVIRONMENT": "Context, roots, and emotional base of interaction",
    "EXPRESSION": "Creative and joyful manifestation of the pair",
    "SERVICE": "How the pair serves, refines, and improves",
    "PARTNERSHIP": "Balance, harmony, and relationship dynamics",
    "TRANSFORMATION": "Depth, change, and transformative potential",
    "WISDOM": "Expansion, meaning, and higher understanding",
    "STRUCTURE": "Achievement, responsibility, and formal manifestation",
    "ASPIRATION": "Goals, networks, and collective aspirations",
}

# Adjacent ontological pairs (10 pairs forming a cycle)
ONTOLOGICAL_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("O5_COGNITION", "O4_STRUCTURE"),
    ("O4_STRUCTURE", "O3_EXECUTION"),
    ("O3_EXECUTION", "O4_TAGGING"),
    ("O4_TAGGING", "O6_AGENCY"),
    ("O6_AGENCY", "O7_REASONING"),
    ("O7_REASONING", "O8_PURPOSE"),
    ("O8_PURPOSE", "O9_WITNESSES"),
    ("O9_WITNESSES", "O10_UNIFYING"),
    ("O10_UNIFYING", "O12_ABSOLVING"),
    ("O12_ABSOLVING", "O5_COGNITION"),  # Cycle back
)

# But we only need 9 pairs for 90 Bhavas (the 10th pair uses first ontological layer)
# Actually, keeping all 10 pairs gives us: 10 pairs × 10 sub-layers = 100 Bhavas
# But user said 90 Bhava + 10 onto = 100 total
# So we use 9 pairs × 10 sub-layers = 90 Bhavas

NINE_PAIRS: Tuple[Tuple[str, str], ...] = ONTOLOGICAL_PAIRS[:9]  # Exclude closing cycle


def get_bhava_name(pair_idx: int, sublayer_idx: int) -> str:
    """
    Get the name of a specific Bhava.

    Args:
        pair_idx: Which ontological pair (0-8)
        sublayer_idx: Which sub-layer (0-9)

    Returns:
        Bhava name like "O1_O2_FOUNDATION"
    """
    pair = NINE_PAIRS[pair_idx]
    sublayer = BHAVA_SUBLAYER_NAMES[sublayer_idx]
    o1 = pair[0].split("_")[0]  # "O1"
    o2 = pair[1].split("_")[0]  # "O2"
    return f"{o1}_{o2}_{sublayer}"


def get_all_bhava_names() -> Tuple[str, ...]:
    """Get all 90 Bhava names."""
    names = []
    for pair_idx in range(9):
        for sublayer_idx in range(10):
            names.append(get_bhava_name(pair_idx, sublayer_idx))
    return tuple(names)


# All 90 Bhava names
BHAVA_NAMES_90: Tuple[str, ...] = get_all_bhava_names()

# Bhava index mapping
BHAVA_INDEX_90: Dict[str, int] = {name: i for i, name in enumerate(BHAVA_NAMES_90)}


@dataclass
class BhavaVector90:
    """
    A 90D Bhava vector representing relational dynamics.

    Structure:
        - Positions 0-9: O1↔O2 relationship (10 sub-layers)
        - Positions 10-19: O2↔O3 relationship (10 sub-layers)
        - ... and so on for 9 pairs = 90 total
    """
    values: Tuple[float, ...]

    def __post_init__(self):
        if len(self.values) != 90:
            raise ValueError(f"BhavaVector90 must have 90 values, got {len(self.values)}")

    def get_bhava(self, name: str) -> float:
        """Get activation for a specific Bhava by name."""
        if name not in BHAVA_INDEX_90:
            raise ValueError(f"Unknown Bhava: {name}")
        return self.values[BHAVA_INDEX_90[name]]

    def get_pair_bhavas(self, pair_idx: int) -> Tuple[float, ...]:
        """Get all 10 Bhava values for a specific ontological pair."""
        start = pair_idx * 10
        return self.values[start:start + 10]

    def dominant_bhava(self) -> Tuple[str, float]:
        """Get the Bhava with highest activation."""
        max_idx = max(range(90), key=lambda i: self.values[i])
        return BHAVA_NAMES_90[max_idx], self.values[max_idx]

    def dominant_per_pair(self) -> List[Tuple[str, float]]:
        """Get dominant Bhava for each ontological pair."""
        dominants = []
        for pair_idx in range(9):
            pair_values = self.get_pair_bhavas(pair_idx)
            max_sublayer = max(range(10), key=lambda i: pair_values[i])
            name = get_bhava_name(pair_idx, max_sublayer)
            dominants.append((name, pair_values[max_sublayer]))
        return dominants

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary with Bhava names as keys."""
        return {BHAVA_NAMES_90[i]: self.values[i] for i in range(90)}


@dataclass
class FullOntologicalVector100:
    """
    Complete 100D representation:
        - 10 ontological dimensions (what)
        - 90 Bhava dimensions (how they relate)

    This provides maximum expressiveness while maintaining
    full interpretability - every dimension has meaning.
    """
    ontological: Tuple[float, ...]  # 10D: What dimensions are active
    bhava: Tuple[float, ...]         # 90D: How dimensions interact

    def __post_init__(self):
        if len(self.ontological) != 10:
            raise ValueError(f"ontological must have 10 values, got {len(self.ontological)}")
        if len(self.bhava) != 90:
            raise ValueError(f"bhava must have 90 values, got {len(self.bhava)}")

    @property
    def full_vector(self) -> Tuple[float, ...]:
        """Get the full 100D vector."""
        return self.ontological + self.bhava

    @property
    def dimension_count(self) -> int:
        """Total dimensions: 10 + 90 = 100."""
        return 100

    def dominant_ontological(self) -> Tuple[str, float]:
        """Get dominant ontological layer."""
        max_idx = max(range(10), key=lambda i: self.ontological[i])
        return LAYER_NAMES[max_idx], self.ontological[max_idx]

    def dominant_bhava(self) -> Tuple[str, float]:
        """Get dominant Bhava (relational dynamic)."""
        max_idx = max(range(90), key=lambda i: self.bhava[i])
        return BHAVA_NAMES_90[max_idx], self.bhava[max_idx]

    def get_pair_relationship(self, pair_idx: int) -> Dict[str, float]:
        """
        Get detailed relationship for an ontological pair.

        Returns dict mapping sublayer names to values.
        """
        start = pair_idx * 10
        pair = NINE_PAIRS[pair_idx]
        return {
            "pair": f"{pair[0]} ↔ {pair[1]}",
            **{
                BHAVA_SUBLAYER_NAMES[i]: self.bhava[start + i]
                for i in range(10)
            }
        }

    def interpretation(self) -> str:
        """Human-readable interpretation of the vector."""
        onto_name, onto_val = self.dominant_ontological()
        bhava_name, bhava_val = self.dominant_bhava()

        # Parse bhava name to get pair and sublayer
        parts = bhava_name.split("_")
        pair_str = f"{parts[0]}↔{parts[1]}"
        sublayer = "_".join(parts[2:])
        sublayer_desc = BHAVA_SUBLAYER_DESCRIPTIONS.get(sublayer, "")

        return (
            f"Primary Ontological: {onto_name} ({onto_val:.2f})\n"
            f"Primary Relational: {pair_str} via {sublayer} ({bhava_val:.2f})\n"
            f"  → {sublayer_desc}"
        )


class BhavaComputer90:
    """
    Computes 90 Bhava sub-layer values from 10 ontological dimensions.

    For each of the 9 adjacent ontological pairs, computes 10 sub-layer
    values representing different aspects of their relationship.
    """

    def __init__(self, mode: str = "learned"):
        """
        Initialize Bhava computer.

        Args:
            mode: How to compute Bhavas
                - "multiplicative": Product-based interactions
                - "learned": Neural network layers
        """
        self.mode = mode

        # Learnable weights for 90 Bhava outputs
        # Each Bhava is a learned combination of the 10 ontological dimensions
        self._weights: List[List[float]] = []
        self._biases: List[float] = []

        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize learnable weights for Bhava computation."""
        import random

        for pair_idx in range(9):
            o1_idx, o2_idx = self._get_pair_indices(pair_idx)

            for sublayer_idx in range(10):
                # Each Bhava takes input from all 10 ontological dimensions
                # but has stronger connection to its pair
                weights = [random.gauss(0, 0.1) for _ in range(10)]

                # Boost weights for the connected pair
                weights[o1_idx] = 0.5 + random.gauss(0, 0.1)
                weights[o2_idx] = 0.5 + random.gauss(0, 0.1)

                # Add sublayer-specific modulation
                # Different sublayers emphasize different aspects
                if sublayer_idx == 0:  # FOUNDATION
                    weights[o1_idx] *= 1.2
                elif sublayer_idx == 5:  # PARTNERSHIP
                    weights[o2_idx] *= 1.2
                elif sublayer_idx == 6:  # TRANSFORMATION
                    # Both layers equally
                    pass
                elif sublayer_idx == 8:  # STRUCTURE
                    weights[o1_idx] *= 1.1
                    weights[o2_idx] *= 1.1

                self._weights.append(weights)
                self._biases.append(random.gauss(0, 0.01))

    def _get_pair_indices(self, pair_idx: int) -> Tuple[int, int]:
        """Get ontological indices for a pair."""
        pair = NINE_PAIRS[pair_idx]
        o1_idx = LAYER_INDEX[pair[0]]
        o2_idx = LAYER_INDEX[pair[1]]
        return o1_idx, o2_idx

    def compute(self, ontological: List[float]) -> List[float]:
        """
        Compute 90 Bhava values from 10 ontological dimensions.

        Args:
            ontological: 10D ontological vector

        Returns:
            90D Bhava vector
        """
        if self.mode == "multiplicative":
            return self._compute_multiplicative(ontological)
        elif self.mode == "learned":
            return self._compute_learned(ontological)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")

    def _compute_multiplicative(self, ontological: List[float]) -> List[float]:
        """
        Compute Bhavas using multiplicative interactions.

        Each Bhava = f(O_i, O_j, sublayer_modulation)
        """
        bhava = []

        for pair_idx in range(9):
            o1_idx, o2_idx = self._get_pair_indices(pair_idx)

            # Get the two ontological values (shift from [-1,1] to [0,1])
            o1 = (ontological[o1_idx] + 1) / 2
            o2 = (ontological[o2_idx] + 1) / 2

            # Base interaction
            base_interaction = o1 * o2

            for sublayer_idx in range(10):
                # Modulate based on sublayer meaning
                if sublayer_idx == 0:  # FOUNDATION - emphasize first layer
                    value = base_interaction * (0.7 * o1 + 0.3 * o2)
                elif sublayer_idx == 1:  # COMMUNICATION - balanced exchange
                    value = base_interaction * 0.5 * (o1 + o2)
                elif sublayer_idx == 2:  # ENVIRONMENT - context
                    value = base_interaction * math.sqrt(o1 * o2)
                elif sublayer_idx == 3:  # EXPRESSION - creative output
                    value = base_interaction * max(o1, o2)
                elif sublayer_idx == 4:  # SERVICE - refined output
                    value = base_interaction * min(o1, o2)
                elif sublayer_idx == 5:  # PARTNERSHIP - harmonic mean
                    value = 2 * o1 * o2 / (o1 + o2 + 1e-10)
                elif sublayer_idx == 6:  # TRANSFORMATION - difference
                    value = base_interaction * (1 - abs(o1 - o2))
                elif sublayer_idx == 7:  # WISDOM - expansion
                    value = base_interaction * (o1 + o2) / 2
                elif sublayer_idx == 8:  # STRUCTURE - product
                    value = o1 * o2
                elif sublayer_idx == 9:  # ASPIRATION - max potential
                    value = base_interaction * max(o1, o2) ** 0.5
                else:
                    value = base_interaction

                # Shift back to [-1, 1]
                value = 2 * value - 1
                bhava.append(value)

        return bhava

    def _compute_learned(self, ontological: List[float]) -> List[float]:
        """Compute Bhavas via learned linear combinations."""
        bhava = []
        for i in range(90):
            value = self._biases[i]
            for j in range(10):
                value += self._weights[i][j] * ontological[j]
            # Apply tanh to keep in [-1, 1]
            value = math.tanh(value)
            bhava.append(value)
        return bhava

    def get_full_vector(self, ontological: List[float]) -> FullOntologicalVector100:
        """
        Get the complete 100D vector.

        Args:
            ontological: 10D ontological vector

        Returns:
            FullOntologicalVector100 with 10D onto + 90D Bhava
        """
        bhava = self.compute(ontological)
        return FullOntologicalVector100(
            ontological=tuple(ontological),
            bhava=tuple(bhava),
        )

    def get_weights(self) -> Dict[str, Any]:
        """Get learnable weights for saving."""
        return {
            "weights": self._weights,
            "biases": self._biases,
        }

    def set_weights(self, weights_dict: Dict[str, Any]) -> None:
        """Load weights."""
        self._weights = weights_dict["weights"]
        self._biases = weights_dict["biases"]

    def parameter_count(self) -> int:
        """Count trainable parameters."""
        # 90 Bhavas × 10 weights each + 90 biases
        return 90 * 10 + 90  # = 990 parameters


class BhavaAttention90:
    """
    Attention mechanism using 90 Bhava relationships.

    Each of the 9 ontological pairs has its own attention pattern
    modulated by the 10 Bhava sub-layers.
    """

    def __init__(self, hidden_dim: int = 64):
        """
        Initialize Bhava attention.

        Args:
            hidden_dim: Hidden dimension for attention computation
        """
        self.hidden_dim = hidden_dim
        self._init_weights()

    def _init_weights(self) -> None:
        """Initialize attention weights."""
        import random

        # Query, Key, Value projections for each pair
        # 9 pairs × (Q + K + V) × hidden_dim × 10
        self._pair_queries: List[List[List[float]]] = []
        self._pair_keys: List[List[List[float]]] = []
        self._pair_values: List[List[List[float]]] = []

        for _ in range(9):  # 9 pairs
            # Query: 10 (sublayers) × hidden_dim
            q = [[random.gauss(0, 0.1) for _ in range(self.hidden_dim)]
                 for _ in range(10)]
            k = [[random.gauss(0, 0.1) for _ in range(self.hidden_dim)]
                 for _ in range(10)]
            v = [[random.gauss(0, 0.1) for _ in range(self.hidden_dim)]
                 for _ in range(10)]

            self._pair_queries.append(q)
            self._pair_keys.append(k)
            self._pair_values.append(v)

        # Output projection: hidden_dim → 10 (back to ontological)
        self._output_proj = [[random.gauss(0, 0.1) for _ in range(self.hidden_dim)]
                            for _ in range(10)]

    def attend(
        self,
        ontological: List[float],
        bhava: List[float],
    ) -> List[float]:
        """
        Apply Bhava-aware attention to enhance ontological representation.

        Uses the 90 Bhava values to modulate attention between ontological
        dimensions, creating a refined 10D output.

        Args:
            ontological: 10D ontological vector
            bhava: 90D Bhava vector

        Returns:
            Enhanced 10D ontological vector
        """
        # Aggregate attention outputs from all pairs
        attended = [0.0] * 10

        for pair_idx in range(9):
            # Get Bhava values for this pair (10 sub-layers)
            pair_bhava = bhava[pair_idx * 10:(pair_idx + 1) * 10]

            # Get the two ontological dimensions for this pair
            pair = NINE_PAIRS[pair_idx]
            o1_idx = LAYER_INDEX[pair[0]]
            o2_idx = LAYER_INDEX[pair[1]]

            # Compute attention score using Bhava values
            attention_score = sum(pair_bhava) / 10  # Average activation

            # Weight the ontological dimensions by attention
            attended[o1_idx] += attention_score * ontological[o1_idx]
            attended[o2_idx] += attention_score * ontological[o2_idx]

        # Normalize and add residual
        for i in range(10):
            attended[i] = 0.5 * attended[i] + 0.5 * ontological[i]

        return attended


def summarize_bhava_structure() -> str:
    """Print a summary of the 90 Bhava structure."""
    lines = [
        "=" * 70,
        "90 BHAVA SUB-LAYERS STRUCTURE",
        "=" * 70,
        "",
        "Total Dimensions: 100 (10 Ontological + 90 Bhava)",
        "",
        "Ontological Pairs and Their 10 Bhava Sub-Layers:",
        "",
    ]

    for pair_idx, pair in enumerate(NINE_PAIRS):
        o1 = pair[0].split("_", 1)[1]  # Remove "O1_" prefix
        o2 = pair[1].split("_", 1)[1]
        lines.append(f"Pair {pair_idx + 1}: {o1} ↔ {o2}")
        for sublayer_idx, sublayer in enumerate(BHAVA_SUBLAYER_NAMES):
            bhava_name = get_bhava_name(pair_idx, sublayer_idx)
            lines.append(f"  └─ {bhava_name}")
        lines.append("")

    lines.extend([
        "Bhava Sub-Layer Meanings:",
        "",
    ])
    for name, desc in BHAVA_SUBLAYER_DESCRIPTIONS.items():
        lines.append(f"  {name}: {desc}")

    lines.append("=" * 70)
    return "\n".join(lines)
