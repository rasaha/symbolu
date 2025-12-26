"""
Chitta-Vritti (Cognitive Mode) Analysis for Robotics
=====================================================

Computes the 5-element vritti distribution p_v[v] adapted for robotics.

The five modes (citta-vritti from Patanjali's Yoga Sutras):
- Pramana: Valid cognition -> Robot has accurate perception
- Viparyaya: Misperception -> Sensor conflicts or errors
- Vikalpa: Conceptual branching -> Multiple valid interpretations
- Smrti: Memory persistence -> Using cached/predicted state
- Nidra: Dormancy -> Sensors offline or system idle

Robotics Applications:
- Pramana high: Safe to act on sensor data
- Viparyaya high: Need to resolve sensor conflicts
- Vikalpa high: Multiple action possibilities, need to plan
- Smrti high: Using stale data, refresh needed
- Nidra high: System in standby, activate sensors
"""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional
from enum import Enum
import numpy as np

from symbolu_robotics.core.types import Layer12D


class VrittiMode(Enum):
    """The five cognitive modes."""
    PRAMANA = "pramana"       # Valid cognition
    VIPARYAYA = "viparyaya"   # Misperception
    VIKALPA = "vikalpa"       # Conceptual branching
    SMRTI = "smrti"           # Memory persistence
    NIDRA = "nidra"           # Dormancy


@dataclass
class VrittiConfig:
    """Configuration for vritti computation."""
    pramana_coherence_threshold: float = 0.6
    pramana_entropy_ceiling: float = 0.8
    viparyaya_conflict_threshold: float = 0.7
    vikalpa_variance_floor: float = 0.1
    smrti_staleness_threshold: float = 0.3
    smrti_decay_rate: float = 0.95


@dataclass
class VrittiResult:
    """Result of vritti analysis."""
    distribution: Dict[str, float]
    dominant: str
    confidence: float
    robotics_action: str

    def to_dict(self) -> Dict:
        return {
            "distribution": self.distribution,
            "dominant": self.dominant,
            "confidence": self.confidence,
            "robotics_action": self.robotics_action,
        }


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def compute_pramana(
    layer_12d: Layer12D,
    sensor_coherence: float,
    entropy: float,
    config: VrittiConfig
) -> float:
    """
    Compute Pramana (valid cognition) score for robotics.

    High when:
    - Sensors agree (high coherence)
    - Low entropy (clear situation)
    - O5_COGNITION and O11_INTEGRATION are active

    Args:
        layer_12d: 12D layer vector
        sensor_coherence: Aggregate sensor agreement [0,1]
        entropy: Situation entropy [0,1]
        config: Threshold configuration

    Returns:
        Pramana score [0,1]
    """
    # Cognition and Integration layers
    cognition = layer_12d[4]  # O5_COGNITION
    integration = layer_12d[10]  # O11_INTEGRATION

    # Layer factor: perception is working
    layer_factor = (cognition + integration) / 2.0

    # Coherence factor: sensors agree
    coherence_factor = sensor_coherence

    # Entropy factor: low entropy is good
    entropy_factor = max(0.0, 1.0 - entropy / config.pramana_entropy_ceiling)

    # Combine multiplicatively
    raw = layer_factor * coherence_factor * entropy_factor

    return clamp(raw)


def compute_viparyaya(
    layer_12d: Layer12D,
    sensor_conflicts: float,
    config: VrittiConfig
) -> float:
    """
    Compute Viparyaya (misperception) score for robotics.

    High when:
    - Sensors disagree (conflicts detected)
    - But system is confident (acting on wrong data)

    Args:
        layer_12d: 12D layer vector
        sensor_conflicts: Sensor disagreement level [0,1]
        config: Threshold configuration

    Returns:
        Viparyaya score [0,1]
    """
    if sensor_conflicts < config.viparyaya_conflict_threshold:
        return 0.0

    # How much above the conflict threshold
    conflict_excess = (sensor_conflicts - config.viparyaya_conflict_threshold) / \
                      (1.0 - config.viparyaya_conflict_threshold)

    # If cognition is still high, we're acting on conflicting data
    cognition = layer_12d[4]

    return clamp(conflict_excess * cognition)


def compute_vikalpa(
    layer_12d: Layer12D,
    action_options: int,
    entropy: float,
    config: VrittiConfig
) -> float:
    """
    Compute Vikalpa (conceptual branching) score for robotics.

    High when:
    - Multiple valid action options exist
    - High planning activity (O7_REASONING)
    - High entropy (uncertain situation)

    Args:
        layer_12d: 12D layer vector
        action_options: Number of valid action alternatives
        entropy: Situation entropy [0,1]
        config: Threshold configuration

    Returns:
        Vikalpa score [0,1]
    """
    if action_options <= 1:
        return 0.0

    # Reasoning layer activity
    reasoning = layer_12d[6]  # O7_REASONING

    # More options = more branching
    options_factor = min(1.0, (action_options - 1) / 5.0)

    # High entropy amplifies branching
    if entropy > config.vikalpa_variance_floor:
        return clamp(reasoning * options_factor * entropy)

    return 0.0


def compute_smrti(
    layer_12d: Layer12D,
    sensor_freshness: float,
    accumulated_smrti: float,
    config: VrittiConfig
) -> float:
    """
    Compute Smrti (memory persistence) score for robotics.

    High when:
    - Using stale/predicted sensor data
    - No new observations coming in
    - Relying on world model (O9_WITNESSES)

    Args:
        layer_12d: 12D layer vector
        sensor_freshness: How fresh sensor data is [0=stale, 1=fresh]
        accumulated_smrti: Previously accumulated smrti
        config: Threshold configuration

    Returns:
        Updated smrti score [0,1]
    """
    # If sensors are fresh, decay smrti
    if sensor_freshness > config.smrti_staleness_threshold:
        return accumulated_smrti * config.smrti_decay_rate

    # Stale sensors: accumulate smrti
    world_model = layer_12d[8]  # O9_WITNESSES
    staleness = 1.0 - sensor_freshness

    new_smrti = accumulated_smrti + 0.1 * staleness * world_model
    return clamp(new_smrti)


def compute_nidra(layer_12d: Layer12D) -> float:
    """
    Compute Nidra (dormancy) score for robotics.

    High when:
    - Sensors offline (low O1_POTENTIAL)
    - System idle (low O6_AGENCY)
    - No active goals (low O8_PURPOSE)

    Args:
        layer_12d: 12D layer vector

    Returns:
        Nidra score [0,1]
    """
    potential = layer_12d[0]   # O1_POTENTIAL
    agency = layer_12d[5]      # O6_AGENCY
    purpose = layer_12d[7]     # O8_PURPOSE

    # Average of "activity" layers, inverted
    activity = (potential + agency + purpose) / 3.0
    dormancy = 1.0 - activity

    return clamp(dormancy)


def normalize_vritti(raw_scores: Dict[str, float]) -> Dict[str, float]:
    """Normalize raw vritti scores to probability distribution."""
    total = sum(raw_scores.values())

    if total < 1e-8:
        # Uniform if all zeros
        n = len(raw_scores)
        return {k: 1.0 / n for k in raw_scores}

    return {k: v / total for k, v in raw_scores.items()}


def get_robotics_action(dominant: str, confidence: float) -> str:
    """
    Map dominant vritti to robotics action recommendation.

    Args:
        dominant: Dominant vritti mode
        confidence: Confidence in the dominant mode

    Returns:
        Action recommendation string
    """
    if confidence < 0.3:
        return "uncertain_state_check_sensors"

    actions = {
        "pramana": "proceed_with_action",
        "viparyaya": "halt_resolve_conflicts",
        "vikalpa": "evaluate_options",
        "smrti": "refresh_sensors",
        "nidra": "activate_system",
    }

    return actions.get(dominant, "unknown")


def compute_vritti(
    layer_12d: Layer12D,
    sensor_coherence: float = 0.8,
    sensor_conflicts: float = 0.0,
    sensor_freshness: float = 1.0,
    action_options: int = 1,
    entropy: float = 0.3,
    accumulated_smrti: float = 0.0,
    config: Optional[VrittiConfig] = None
) -> Tuple[VrittiResult, float]:
    """
    Compute full vritti distribution for robotics.

    Args:
        layer_12d: 12D ontological layer vector
        sensor_coherence: Agreement between sensors [0,1]
        sensor_conflicts: Detected sensor conflicts [0,1]
        sensor_freshness: How recent sensor data is [0,1]
        action_options: Number of valid action alternatives
        entropy: Situation uncertainty [0,1]
        accumulated_smrti: Previously accumulated memory score
        config: Optional vritti configuration

    Returns:
        Tuple of (VrittiResult, new_accumulated_smrti)
    """
    if config is None:
        config = VrittiConfig()

    # Compute each vritti
    pramana = compute_pramana(layer_12d, sensor_coherence, entropy, config)
    viparyaya = compute_viparyaya(layer_12d, sensor_conflicts, config)
    vikalpa = compute_vikalpa(layer_12d, action_options, entropy, config)
    smrti = compute_smrti(layer_12d, sensor_freshness, accumulated_smrti, config)
    nidra = compute_nidra(layer_12d)

    raw_scores = {
        "pramana": pramana,
        "viparyaya": viparyaya,
        "vikalpa": vikalpa,
        "smrti": smrti,
        "nidra": nidra,
    }

    # Normalize to probability distribution
    distribution = normalize_vritti(raw_scores)

    # Get dominant mode
    dominant = max(distribution.keys(), key=lambda k: distribution[k])
    confidence = distribution[dominant]

    # Get action recommendation
    action = get_robotics_action(dominant, confidence)

    result = VrittiResult(
        distribution=distribution,
        dominant=dominant,
        confidence=confidence,
        robotics_action=action,
    )

    return result, smrti


def get_dominant_vritti(distribution: Dict[str, float]) -> str:
    """Get the mode with highest activation."""
    return max(distribution.keys(), key=lambda k: distribution[k])
