"""Five vṛtti (cognitive mode) computations.

Computes the 5-element vṛtti distribution p_v[v] based on:
- Cross-layer coherence
- Entropy signals
- Motion stability
- Temporal state changes
- Layer presence

The five modes (citta-vṛtti from Patañjali's Yoga Sutras):
- Pramāṇa: Valid cognition
- Viparyaya: Misperception
- Vikalpa: Conceptual branching
- Smṛti: Memory persistence
- Nidrā: Dormancy

Invariants:
- INV-CV-4: Missing rep → only nidrā increases
- INV-CV-5: Bounded output (all values ∈ [0,1])
- INV-CV-7: Sum constraint (Σ p_v[v] = 1.0)
"""

from typing import Optional
import numpy as np

from symbolu.chitta_vritti.types import ChittaVrittiInputs, OptimizedConfig


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def variance(values: list[float]) -> float:
    """Compute variance of a list of values."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def compute_pramana(
    coherence: float,
    entropy: float,
    motion: float,
    config: OptimizedConfig
) -> float:
    """Compute Pramāṇa (valid cognition) score.

    High when:
    - Coherence is strong (layers agree)
    - Entropy is low (certainty)
    - Motion is stable (not changing rapidly)

    Args:
        coherence: Aggregate coherence [0,1]
        entropy: Normalized entropy [0,1]
        motion: Motion signal [0,1]
        config: Threshold configuration

    Returns:
        Pramāṇa score [0,1]
    """
    # Entropy factor: high when entropy is low
    entropy_factor = max(0.0, 1.0 - entropy / config.pramana_entropy_ceiling)

    # Motion stability: high when motion is low
    motion_stability = 1.0 - min(1.0, motion)

    # Combine multiplicatively
    raw = coherence * entropy_factor * motion_stability

    return clamp(raw)


def compute_viparyaya(
    fractures: dict[tuple[str, str], float],
    confidence: float,
    config: OptimizedConfig
) -> float:
    """Compute Viparyaya (misperception) score.

    High when:
    - Layers confidently oppose each other
    - High fracture with high confidence = dangerous inversion

    Args:
        fractures: Pairwise fracture dict
        confidence: Confidence signal [0,1]
        config: Threshold configuration

    Returns:
        Viparyaya score [0,1]
    """
    if not fractures:
        return 0.0

    # Find maximum fracture (strongest disagreement)
    max_fracture = max(fractures.values())

    # Viparyaya activates when fracture is high (>0.7 after normalization)
    # Remember: fracture is in [0,1] where 0.5 = orthogonal, 1.0 = opposite
    if max_fracture > 0.7:
        # Scale 0.7-1.0 → 0-1
        opposition_strength = (max_fracture - 0.7) / 0.3
        return clamp(opposition_strength * confidence)

    return 0.0


def compute_vikalpa(
    fractures: dict[tuple[str, str], float],
    entropy: float,
    config: OptimizedConfig
) -> float:
    """Compute Vikalpa (conceptual branching) score.

    High when:
    - Agreement is uneven across layers (some agree, some don't)
    - Entropy is high (multiple interpretations possible)

    Args:
        fractures: Pairwise fracture dict
        entropy: Normalized entropy [0,1]
        config: Threshold configuration

    Returns:
        Vikalpa score [0,1]
    """
    if not fractures or len(fractures) < 2:
        return 0.0

    # Compute variance of fractures (uneven agreement)
    fracture_values = list(fractures.values())
    fracture_variance = variance(fracture_values)

    # Vikalpa requires both high variance AND high entropy
    if fracture_variance > config.vikalpa_variance_floor and entropy > 0.3:
        return clamp(entropy * (fracture_variance / 0.5))

    return 0.0


def compute_representation_delta(
    current: ChittaVrittiInputs,
    previous: ChittaVrittiInputs
) -> float:
    """Compute delta between current and previous representations.

    Args:
        current: Current input state
        previous: Previous input state

    Returns:
        Aggregate delta [0,1], higher = more change
    """
    deltas = []

    # Compare each layer that exists in both
    if current.phonemic_rep is not None and previous.phonemic_rep is not None:
        if current.phonemic_rep.shape == previous.phonemic_rep.shape:
            delta = np.linalg.norm(current.phonemic_rep - previous.phonemic_rep)
            deltas.append(min(1.0, delta))

    if current.semantic_rep is not None and previous.semantic_rep is not None:
        if current.semantic_rep.shape == previous.semantic_rep.shape:
            delta = np.linalg.norm(current.semantic_rep - previous.semantic_rep)
            deltas.append(min(1.0, delta))

    if current.structural_rep is not None and previous.structural_rep is not None:
        if current.structural_rep.shape == previous.structural_rep.shape:
            delta = np.linalg.norm(current.structural_rep - previous.structural_rep)
            deltas.append(min(1.0, delta))

    if current.temporal_rep is not None and previous.temporal_rep is not None:
        if current.temporal_rep.shape == previous.temporal_rep.shape:
            delta = np.linalg.norm(current.temporal_rep - previous.temporal_rep)
            deltas.append(min(1.0, delta))

    if not deltas:
        return 0.5  # Unknown, assume moderate change

    return sum(deltas) / len(deltas)


def compute_smrti(
    current: ChittaVrittiInputs,
    previous: Optional[ChittaVrittiInputs],
    accumulated_smrti: float,
    config: OptimizedConfig
) -> float:
    """Compute Smṛti (memory persistence) score.

    High when:
    - State remains unchanged despite new input
    - Accumulates over time if representations don't update

    Args:
        current: Current input state
        previous: Previous input state (None if first turn)
        accumulated_smrti: Previously accumulated smṛti
        config: Threshold configuration

    Returns:
        New smṛti score [0,1]
    """
    if previous is None:
        return 0.0  # No history = no smṛti

    # Compute state delta
    delta = compute_representation_delta(current, previous)

    if delta < config.smrti_staleness_threshold:
        # State unchanged → accumulate smṛti
        new_smrti = min(1.0, accumulated_smrti + 0.2)
    else:
        # State changed → decay smṛti
        new_smrti = accumulated_smrti * config.smrti_decay_rate

    return clamp(new_smrti)


def compute_nidra(inputs: ChittaVrittiInputs) -> float:
    """Compute Nidrā (dormancy) score.

    High when:
    - Representations are missing or weak
    - This is the ONLY vṛtti that increases when signals are missing (INV-CV-4)

    Args:
        inputs: Input representations

    Returns:
        Nidrā score [0,1]
    """
    missing_count = inputs.count_missing_layers()
    return missing_count / 4.0


def normalize_vritti(raw_scores: dict[str, float]) -> dict[str, float]:
    """Normalize raw vṛtti scores to probability distribution.

    Uses L1 normalization (simple sum) as specified in design doc.

    Args:
        raw_scores: Dict of mode → raw score

    Returns:
        Dict of mode → normalized probability (sums to 1.0)
    """
    total = sum(raw_scores.values())

    # Handle edge case: all zeros → uniform distribution
    if total < 1e-8:
        n = len(raw_scores)
        return {k: 1.0 / n for k in raw_scores.keys()}

    return {k: v / total for k, v in raw_scores.items()}


class VrittiComputer:
    """Stateless vṛtti distribution computation engine."""

    def __init__(self, config: OptimizedConfig) -> None:
        """Initialize vṛtti computer.

        Args:
            config: Threshold configuration
        """
        self._config = config

    def compute(
        self,
        inputs: ChittaVrittiInputs,
        coherence: float,
        fractures: dict[tuple[str, str], float],
        previous_inputs: Optional[ChittaVrittiInputs] = None,
        accumulated_smrti: float = 0.0
    ) -> tuple[dict[str, float], float]:
        """Compute normalized vṛtti distribution.

        Args:
            inputs: Current input representations
            coherence: Aggregate coherence
            fractures: Pairwise fracture dict
            previous_inputs: Previous input state for smṛti
            accumulated_smrti: Previously accumulated smṛti

        Returns:
            Tuple of (normalized vritti dict, new accumulated smṛti)
        """
        # Compute each vṛtti
        pramana = compute_pramana(
            coherence, inputs.entropy, inputs.motion, self._config
        )

        viparyaya = compute_viparyaya(
            fractures, inputs.confidence, self._config
        )

        vikalpa = compute_vikalpa(
            fractures, inputs.entropy, self._config
        )

        smrti = compute_smrti(
            inputs, previous_inputs, accumulated_smrti, self._config
        )

        nidra = compute_nidra(inputs)

        # Collect raw scores
        raw_scores = {
            "pramana": pramana,
            "viparyaya": viparyaya,
            "vikalpa": vikalpa,
            "smrti": smrti,
            "nidra": nidra,
        }

        # Normalize to probability distribution
        normalized = normalize_vritti(raw_scores)

        return normalized, smrti


def get_dominant_vritti(vritti: dict[str, float]) -> str:
    """Get the mode with highest activation.

    Args:
        vritti: Normalized vṛtti distribution

    Returns:
        Name of dominant mode
    """
    return max(vritti.keys(), key=lambda k: vritti[k])
