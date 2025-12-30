"""
COHERA Metrics and Coherence Monitoring
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Optional, Callable


class VrittiState(IntEnum):
    """
    Five Vritti states from Yoga Sutras.
    Detected by the Kosha Entropy Engine (KEE).
    """
    PRAMANA = 0     # Valid cognition (high coherence, low entropy)
    VIPARYAYA = 1   # Misperception (phase misalignment)
    VIKALPA = 2     # Imagination (high entropy)
    SMRTI = 3       # Memory (TCU activation spike)
    NIDRA = 4       # Dormancy (low overall activation)


class Kosha(IntEnum):
    """
    Five Kosha (consciousness sheaths) from Pancha Kosha model.
    Maps to ontological layers.
    """
    PRE_ANNAMAYA = 0   # O1 (dormant)
    ANNAMAYA = 1       # O2, O3 (physical)
    PRANAMAYA = 2      # O4 (energy)
    MANOMAYA = 3       # O5, O6 (mental)
    VIJNANAMAYA = 4    # O7, O8 (wisdom)
    ANANDAMAYA = 5     # O9, O10, O11 (bliss)


@dataclass
class Metrics:
    """
    Runtime metrics from the COHERA device.

    Attributes:
        coherence: Phase alignment score [0, 1]
        entropy: Uncertainty level [0, 1]
        confidence: Belief strength [0, 1]
        momentum: Rate of meaning change
        dominant_layer: Most active ontology layer (0-11)
        vritti_state: Current Vritti state
        kosha_level: Current Kosha level
        frame_count: Total frames processed
        tcu_updates: Total TCU accumulations
    """
    coherence: float = 0.0
    entropy: float = 0.0
    confidence: float = 0.0
    momentum: float = 0.0
    dominant_layer: int = 0
    vritti_state: VrittiState = VrittiState.NIDRA
    kosha_level: Kosha = Kosha.PRE_ANNAMAYA
    frame_count: int = 0
    tcu_updates: int = 0

    @property
    def vritti_name(self) -> str:
        """Get human-readable Vritti name."""
        names = {
            VrittiState.PRAMANA: "Valid Cognition",
            VrittiState.VIPARYAYA: "Misperception",
            VrittiState.VIKALPA: "Imagination",
            VrittiState.SMRTI: "Memory",
            VrittiState.NIDRA: "Dormancy",
        }
        return names.get(self.vritti_state, "Unknown")

    @property
    def kosha_name(self) -> str:
        """Get human-readable Kosha name."""
        names = {
            Kosha.PRE_ANNAMAYA: "Pre-Physical",
            Kosha.ANNAMAYA: "Physical",
            Kosha.PRANAMAYA: "Energy",
            Kosha.MANOMAYA: "Mental",
            Kosha.VIJNANAMAYA: "Wisdom",
            Kosha.ANANDAMAYA: "Bliss",
        }
        return names.get(self.kosha_level, "Unknown")

    @property
    def ontology_layer_name(self) -> str:
        """Get ontology layer name."""
        names = [
            "O1_POTENTIAL", "O2_IDENTITY", "O3_EXECUTION", "O4_STRUCTURE",
            "O5_COGNITION", "O6_AGENCY", "O7_REASONING", "O8_PURPOSE",
            "O9_WITNESSES", "O10_UNIFYING", "O11_INTEGRATION", "O12_ABSOLVING"
        ]
        if 0 <= self.dominant_layer < 12:
            return names[self.dominant_layer]
        return "Unknown"


def get_metrics() -> Metrics:
    """
    Get current runtime metrics from the COHERA device.

    Returns:
        Metrics object with current coherence, entropy, etc.

    Example:
        >>> metrics = get_metrics()
        >>> print(f"Coherence: {metrics.coherence:.3f}")
        >>> print(f"Vritti: {metrics.vritti_name}")
    """
    # TODO: Call cohera_get_metrics()
    return Metrics(
        coherence=0.85,
        entropy=0.30,
        confidence=0.75,
        momentum=0.1,
        dominant_layer=5,  # O5_COGNITION
        vritti_state=VrittiState.PRAMANA,
        kosha_level=Kosha.MANOMAYA,
        frame_count=1000,
        tcu_updates=1000,
    )


# Global callback storage
_coherence_callback: Optional[Callable[[float], None]] = None
_coherence_threshold: float = 0.5


def register_coherence_callback(
    callback: Callable[[float], None],
    threshold: float = 0.5,
) -> None:
    """
    Register a callback for when coherence drops below threshold.

    Args:
        callback: Function to call with current coherence value
        threshold: Trigger threshold (default 0.5)

    Example:
        >>> def on_low_coherence(coherence):
        ...     print(f"Warning: coherence dropped to {coherence}")
        >>> register_coherence_callback(on_low_coherence, threshold=0.6)
    """
    global _coherence_callback, _coherence_threshold
    _coherence_callback = callback
    _coherence_threshold = threshold
    # TODO: Call cohera_register_coherence_callback()


def unregister_coherence_callback() -> None:
    """Unregister the coherence callback."""
    global _coherence_callback
    _coherence_callback = None
    # TODO: Call cohera_unregister_coherence_callback()
