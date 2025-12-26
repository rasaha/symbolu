"""
12D Mirror Pair Architecture for Robotics
==========================================

The 12D ontological backbone is structured as 6 mirror pairs,
following the astrological mirror pattern (1<->7, 2<->8, etc.).

Robotics Interpretation of Mirror Pairs:
    O1_POTENTIAL   <->  O7_REASONING      Sensor readiness <-> Planning
    O2_IDENTITY    <->  O8_PURPOSE        Where am I? <-> Where to go?
    O3_EXECUTION   <->  O9_WITNESSES      Action <-> Observation
    O4_STRUCTURE   <->  O10_UNIFYING      Body <-> World
    O5_COGNITION   <->  O11_INTEGRATION   Perception <-> Fusion
    O6_AGENCY      <->  O12_ABSOLVING     Autonomy <-> Safety
"""

from dataclasses import dataclass
from typing import Dict, Tuple, List
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D
from symbolu_robotics.core.ontology_12d import LAYER_NAMES, LAYER_INDICES


class MirrorPair12D(Enum):
    """The 6 mirror pairs that structure the 12D space."""

    # 1<->7: Readiness <-> Planning
    POTENTIAL_REASONING = ("O1_POTENTIAL", "O7_REASONING")

    # 2<->8: Localization <-> Goals
    IDENTITY_PURPOSE = ("O2_IDENTITY", "O8_PURPOSE")

    # 3<->9: Action <-> Observation
    EXECUTION_WITNESSES = ("O3_EXECUTION", "O9_WITNESSES")

    # 4<->10: Body <-> World
    STRUCTURE_UNIFYING = ("O4_STRUCTURE", "O10_UNIFYING")

    # 5<->11: Perception <-> Fusion
    COGNITION_INTEGRATION = ("O5_COGNITION", "O11_INTEGRATION")

    # 6<->12: Autonomy <-> Safety
    AGENCY_ABSOLVING = ("O6_AGENCY", "O12_ABSOLVING")


# Direct mapping for fast lookup
MIRROR_MAP_12D: Dict[str, str] = {
    "O1_POTENTIAL": "O7_REASONING",
    "O7_REASONING": "O1_POTENTIAL",
    "O2_IDENTITY": "O8_PURPOSE",
    "O8_PURPOSE": "O2_IDENTITY",
    "O3_EXECUTION": "O9_WITNESSES",
    "O9_WITNESSES": "O3_EXECUTION",
    "O4_STRUCTURE": "O10_UNIFYING",
    "O10_UNIFYING": "O4_STRUCTURE",
    "O5_COGNITION": "O11_INTEGRATION",
    "O11_INTEGRATION": "O5_COGNITION",
    "O6_AGENCY": "O12_ABSOLVING",
    "O12_ABSOLVING": "O6_AGENCY",
}

# Index-based mirror mapping (i <-> i+6)
MIRROR_INDEX_MAP: Dict[int, int] = {
    0: 6, 6: 0,   # O1 <-> O7
    1: 7, 7: 1,   # O2 <-> O8
    2: 8, 8: 2,   # O3 <-> O9
    3: 9, 9: 3,   # O4 <-> O10
    4: 10, 10: 4, # O5 <-> O11
    5: 11, 11: 5, # O6 <-> O12
}


def get_mirror_layer(layer: str) -> str:
    """Get the mirror layer for any layer."""
    return MIRROR_MAP_12D[layer]


def get_mirror_index(index: int) -> int:
    """Get the mirror index for any layer index (0-11)."""
    return MIRROR_INDEX_MAP[index]


@dataclass
class MirrorBalance12D:
    """
    Balance state for a single 12D mirror pair.

    In robotics context:
    - "balanced": Both concrete and abstract aspects are active
    - "grounded_only": Sensors active but no planning
    - "abstract_only": Planning without sensor grounding
    - "both_low": Pair is inactive
    """
    pair: MirrorPair12D
    lower_layer: str
    higher_layer: str
    lower_value: float
    higher_value: float
    imbalance: float
    state: str

    def to_dict(self) -> Dict:
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
    """Complete balance analysis for a 12D vector."""
    pairs: List[MirrorBalance12D]
    total_imbalance: float
    balance_score: float
    dominant_state: str
    propagation_needed: List[MirrorPair12D]

    def to_dict(self) -> Dict:
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
        return "grounded_only"
    elif lower < threshold and higher >= threshold:
        return "abstract_only"
    else:
        return "both_low"


def compute_balance_12d(
    layer_values: Layer12D,
    threshold: float = 0.4
) -> BalanceReport12D:
    """
    Compute mirror balance for a 12D layer vector.

    For robotics, balanced pairs indicate:
    - Sensors are feeding into planning
    - Actions are informed by observations
    - Autonomy is constrained by safety

    Args:
        layer_values: 12-element array of layer values
        threshold: Minimum activation to consider "high"

    Returns:
        BalanceReport12D with detailed analysis
    """
    pairs = []
    total_imbalance = 0.0
    propagation_needed = []

    pair_definitions = [
        (MirrorPair12D.POTENTIAL_REASONING, 0, 6),
        (MirrorPair12D.IDENTITY_PURPOSE, 1, 7),
        (MirrorPair12D.EXECUTION_WITNESSES, 2, 8),
        (MirrorPair12D.STRUCTURE_UNIFYING, 3, 9),
        (MirrorPair12D.COGNITION_INTEGRATION, 4, 10),
        (MirrorPair12D.AGENCY_ABSOLVING, 5, 11),
    ]

    for pair, lower_idx, higher_idx in pair_definitions:
        lower_val = float(layer_values[lower_idx])
        higher_val = float(layer_values[higher_idx])
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

        # Robotics: Propagate from sensors to planning when needed
        if state == "grounded_only":
            propagation_needed.append(pair)

    # Balance score (0 to 1, where 1 is perfect balance)
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


def propagate_to_mirror_12d(
    layer_values: Layer12D,
    propagation_strength: float = 0.7
) -> Layer12D:
    """
    Propagate values from lower layers to their higher mirrors.

    In robotics, this helps ensure planning uses sensor data:
    - Sensor readiness feeds into path planning
    - Perception drives sensor fusion
    - Autonomy level affects safety constraints

    Args:
        layer_values: Original 12D layer values
        propagation_strength: How much to propagate (0.0 to 1.0)

    Returns:
        New array with propagated values
    """
    report = compute_balance_12d(layer_values)

    if not report.propagation_needed:
        return layer_values.copy()

    new_values = layer_values.copy()

    for pair in report.propagation_needed:
        for balance in report.pairs:
            if balance.pair == pair:
                lower_idx = LAYER_INDICES[balance.lower_layer]
                higher_idx = LAYER_INDICES[balance.higher_layer]

                # Propagate: higher = lower * strength
                propagated = balance.lower_value * propagation_strength
                new_values[higher_idx] = max(new_values[higher_idx], propagated)
                break

    return new_values


def check_safety_balance(layer_values: Layer12D) -> Tuple[bool, str]:
    """
    Check the Agency <-> Absolving balance for safety.

    In robotics, this is critical:
    - High Agency + Low Absolving = dangerous autonomous operation
    - High Agency + High Absolving = safe autonomous operation
    - Low Agency = teleoperation or idle

    Args:
        layer_values: 12D layer vector

    Returns:
        Tuple of (is_safe, message)
    """
    agency = layer_values[5]
    absolving = layer_values[11]

    if agency > 0.7 and absolving < 0.3:
        return (False, "High autonomy without safety constraints")

    if agency > 0.5 and absolving > 0.5:
        return (True, "Safe autonomous operation")

    if agency < 0.3:
        return (True, "Low autonomy mode (teleoperation or idle)")

    return (True, "Normal operation")


def propagate_safety_constraint(
    layer_values: Layer12D,
    safety_level: float
) -> Layer12D:
    """
    Propagate safety level to relevant layers.

    Safety (O12) should reduce:
    - O3_EXECUTION (motor commands)
    - O6_AGENCY (autonomy level)

    Args:
        layer_values: Original layer vector
        safety_level: Safety constraint level (0=nominal, 1=full stop)

    Returns:
        Modified layer vector
    """
    new_values = layer_values.copy()

    # Set absolving level
    new_values[11] = max(new_values[11], safety_level)

    # Reduce execution proportionally
    reduction = 1.0 - safety_level
    new_values[2] *= reduction  # O3_EXECUTION

    # Reduce agency if very high safety
    if safety_level > 0.8:
        new_values[5] *= 0.5  # O6_AGENCY

    return new_values
