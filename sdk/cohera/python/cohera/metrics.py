"""
COHERA Metrics and Coherence Monitoring
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


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


# ---------------------------------------------------------------------------
# Distillation + FSCS gate telemetry (P4)
# ---------------------------------------------------------------------------

@dataclass
class DistillationMetrics:
    """
    Teacher-student distillation telemetry for mistral_teacher / mistral_cg.

    Matches the loss decomposition in
    ``symbolu_training/training/unified/mistral_teacher.py`` so the runtime
    can surface the same numbers end-to-end.
    """
    teacher_ce: float = 0.0              # teacher's cross-entropy on labels
    student_ce: float = 0.0              # student's cross-entropy on labels
    kl_div: float = 0.0                  # KL(student || teacher) on soft logits
    temperature: float = 1.0             # softmax temperature used for KL
    alpha_kl: float = 0.5                # KL weight in total loss
    alpha_ce: float = 0.5                # student CE weight in total loss
    total_loss: float = 0.0              # alpha_kl * kl + alpha_ce * student_ce
    tokens: int = 0                      # tokens participating in the loss

    @property
    def student_teacher_gap(self) -> float:
        """student_ce - teacher_ce. Positive = student worse than teacher."""
        return self.student_ce - self.teacher_ce


@dataclass
class FSCSGateMetrics:
    """
    Per-layer telemetry for the FSCS routing gate
    (``symbolu/fscs/mistral_gated_layer.py``). Mirrors the fields
    ``FSCSGatedDecoderLayer.last_gate_fraction`` and friends expose after
    a forward pass.
    """
    layer_idx: int = 0
    gate_fraction: float = 0.0           # fraction of tokens routed to coarse
    mean_coherence: float = 0.0          # mean pi (gate probability)
    tau: float = 0.0                     # effective threshold at this layer
    alpha: float = 0.0                   # routing softness param
    alignment_loss: float = 0.0          # §12.2 alignment regularizer
    prev_layer_gate_fraction: float = 0.0  # for cross-layer caution (§8)
    boundary_hits: int = 0
    tokens: int = 0


@dataclass
class RuntimeHooks:
    """
    Container for hook-delivered metrics. The runtime populates these by
    callback during training / eval so the trainer can log them without
    reaching into the accelerator internals.
    """
    distillation: Optional[DistillationMetrics] = None
    fscs_gate_per_layer: List[FSCSGateMetrics] = field(default_factory=list)
    coherence_per_layer: List[float] = field(default_factory=list)
    state_delta_per_layer: List[float] = field(default_factory=list)

    def reset(self) -> None:
        self.distillation = None
        self.fscs_gate_per_layer.clear()
        self.coherence_per_layer.clear()
        self.state_delta_per_layer.clear()

    def to_dict(self) -> Dict[str, object]:
        return {
            "distillation": (
                self.distillation.__dict__ if self.distillation else None
            ),
            "fscs_gate_per_layer": [m.__dict__ for m in self.fscs_gate_per_layer],
            "coherence_per_layer": list(self.coherence_per_layer),
            "state_delta_per_layer": list(self.state_delta_per_layer),
        }


_runtime_hooks = RuntimeHooks()


def get_runtime_hooks() -> RuntimeHooks:
    """Return the process-wide RuntimeHooks container."""
    return _runtime_hooks


def record_distillation(metrics: DistillationMetrics) -> None:
    """
    Publish a distillation telemetry frame. Called by
    ``mistral_teacher.compute_distillation_loss`` per training step.
    """
    if not isinstance(metrics, DistillationMetrics):
        raise TypeError("record_distillation requires a DistillationMetrics")
    _runtime_hooks.distillation = metrics
    # Runtime: cohera_metrics_record_distillation(&metrics)


def record_fscs_gate(metrics: FSCSGateMetrics) -> None:
    """
    Publish an FSCS gate telemetry frame. Called by
    ``FSCSGatedDecoderLayer`` after each forward pass.
    """
    if not isinstance(metrics, FSCSGateMetrics):
        raise TypeError("record_fscs_gate requires an FSCSGateMetrics")
    _runtime_hooks.fscs_gate_per_layer.append(metrics)
    # Runtime: cohera_metrics_record_fscs_gate(&metrics)


def record_per_layer_coherence(
    coherence_per_layer: List[float],
    state_delta_per_layer: Optional[List[float]] = None,
) -> None:
    """
    Publish per-layer coherence / state-delta traces emitted by the
    HybridOntologicalAccelerator. Replaces the previous list contents so
    each forward pass starts fresh.
    """
    _runtime_hooks.coherence_per_layer = list(coherence_per_layer)
    if state_delta_per_layer is not None:
        _runtime_hooks.state_delta_per_layer = list(state_delta_per_layer)
