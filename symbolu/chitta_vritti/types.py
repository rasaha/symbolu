"""Type definitions for Chitta-Vṛtti module.

This module defines the core data structures used throughout the Chitta-Vṛtti
computation pipeline, following the v2.8 design specification.
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass(frozen=True)
class OptimizedConfig:
    """Production-ready threshold configuration for Chitta-Vṛtti computation.

    All thresholds have been validated by external review. The configuration
    uses threshold-driven penalties (step functions) rather than proportional
    penalties for interpretability and drift resistance.
    """

    # Projection dimension (smaller = faster)
    projection_dim: int = 32

    # Fast-path gates
    fast_path_entropy_threshold: float = 0.1
    fast_path_coherence_threshold: float = 0.9
    fast_path_viparyaya_ceiling: float = 0.1  # SAFETY: block fast-path if opposition

    # Vṛtti computation thresholds
    pramana_entropy_ceiling: float = 0.3  # Above this → pramāṇa decreases
    viparyaya_opposition_floor: float = -0.5  # Similarity below this → opposition
    vikalpa_variance_floor: float = 0.2  # Fracture variance above this → branching
    smrti_staleness_threshold: float = 0.05  # State Δ below this → unchanged
    nidra_presence_floor: float = 0.1  # Confidence below this → absent

    # Smṛti temporal parameters
    smrti_window_turns: int = 3
    smrti_decay_rate: float = 0.4  # Per-turn decay

    # Score penalties (applied as step functions, not proportionally)
    penalty_viparyaya: float = 0.25
    penalty_vikalpa: float = 0.15
    penalty_smrti: float = 0.15
    penalty_nidra: float = 0.20

    # Activation thresholds (penalty applies only above these)
    viparyaya_activation_threshold: float = 0.1
    vikalpa_activation_threshold: float = 0.15
    smrti_activation_threshold: float = 0.2
    nidra_activation_threshold: float = 0.25


# Consumer: More tolerant, faster decay, wider thresholds
CONSUMER_CONFIG = OptimizedConfig(
    projection_dim=32,
    fast_path_entropy_threshold=0.15,
    fast_path_viparyaya_ceiling=0.15,
    penalty_viparyaya=0.20,
    penalty_vikalpa=0.10,
    penalty_smrti=0.10,
    penalty_nidra=0.15,
    viparyaya_activation_threshold=0.15,
    vikalpa_activation_threshold=0.20,
    smrti_activation_threshold=0.25,
    nidra_activation_threshold=0.30,
    smrti_decay_rate=0.5,
)

# Enterprise: Stricter, slower decay, tighter thresholds
ENTERPRISE_CONFIG = OptimizedConfig(
    projection_dim=32,
    fast_path_entropy_threshold=0.08,
    fast_path_viparyaya_ceiling=0.05,
    penalty_viparyaya=0.35,
    penalty_vikalpa=0.20,
    penalty_smrti=0.15,
    penalty_nidra=0.30,
    viparyaya_activation_threshold=0.05,
    vikalpa_activation_threshold=0.10,
    smrti_activation_threshold=0.15,
    nidra_activation_threshold=0.20,
    smrti_decay_rate=0.2,
)


@dataclass(frozen=True)
class ChittaVrittiInputs:
    """Inputs required for Chitta-Vṛtti computation.

    All representations should be numpy arrays that will be projected
    to a common space for coherence computation.
    """

    # Representations (project to common space)
    phonemic_rep: Optional[np.ndarray] = None  # From acoustic pipeline
    semantic_rep: Optional[np.ndarray] = None  # From embedding layer
    structural_rep: Optional[np.ndarray] = None  # From ontology encoder
    temporal_rep: Optional[np.ndarray] = None  # From state differencing

    # Signals
    entropy: float = 0.0  # Combined normalized H [0,1]
    motion: float = 0.0  # M from Observables [0,1]
    confidence: float = 1.0  # From fusion audit [0,1]
    temporal_continuity: float = 1.0  # From temporal tracker [0,1]

    def __post_init__(self) -> None:
        """Validate input ranges."""
        if not 0.0 <= self.entropy <= 1.0:
            raise ValueError(f"entropy must be in [0,1], got {self.entropy}")
        if not 0.0 <= self.motion <= 1.0:
            raise ValueError(f"motion must be in [0,1], got {self.motion}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0,1], got {self.confidence}")
        if not 0.0 <= self.temporal_continuity <= 1.0:
            raise ValueError(
                f"temporal_continuity must be in [0,1], got {self.temporal_continuity}"
            )

    def count_present_layers(self) -> int:
        """Count how many representation layers are present."""
        count = 0
        if self.phonemic_rep is not None:
            count += 1
        if self.semantic_rep is not None:
            count += 1
        if self.structural_rep is not None:
            count += 1
        if self.temporal_rep is not None:
            count += 1
        return count

    def count_missing_layers(self) -> int:
        """Count how many representation layers are missing."""
        return 4 - self.count_present_layers()

    def all_layers_present(self) -> bool:
        """Check if all 4 representation layers are present."""
        return self.count_present_layers() == 4


@dataclass(frozen=True)
class ChittaVrittiResult:
    """Complete output from Chitta-Vṛtti computation.

    This result provides:
    - Cross-layer coherence measurement
    - 5-mode vṛtti distribution (THE CONTROL VECTOR for core formula)
    - Diagnostic score for system readiness
    - Explainability fields for debugging and monitoring
    """

    # Cross-Representation Coherence
    coherence: float  # Aggregate coherence [0,1]
    fractures: dict[tuple[str, str], float]  # Per-pair fracture (1 - similarity)

    # Vṛtti Distribution (THE CONTROL VECTOR for core formula)
    # Keys: "pramana", "viparyaya", "vikalpa", "smrti", "nidra"
    # Values sum to 1.0 (probability distribution)
    vritti: dict[str, float]

    # Diagnostic Score
    score: float  # Overall readiness [0,1]

    # Explainability Fields
    dominant_vritti: str  # Mode with highest activation
    primary_fracture: Optional[tuple[str, str]]  # Layer pair with largest disagreement
    explanation: str  # Human-readable summary

    # Metadata
    fast_path_used: bool = False  # Whether fast-path optimization was used

    def __post_init__(self) -> None:
        """Validate output constraints."""
        # Validate coherence bounds
        if not 0.0 <= self.coherence <= 1.0:
            raise ValueError(f"coherence must be in [0,1], got {self.coherence}")

        # Validate score bounds
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0,1], got {self.score}")

        # Validate fracture bounds
        for pair, fracture in self.fractures.items():
            if not 0.0 <= fracture <= 1.0:
                raise ValueError(
                    f"fracture for {pair} must be in [0,1], got {fracture}"
                )

        # Validate vritti distribution
        expected_keys = {"pramana", "viparyaya", "vikalpa", "smrti", "nidra"}
        if set(self.vritti.keys()) != expected_keys:
            raise ValueError(
                f"vritti must have keys {expected_keys}, got {set(self.vritti.keys())}"
            )

        for mode, value in self.vritti.items():
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"vritti[{mode}] must be in [0,1], got {value}")

        # Validate sum constraint (with tolerance for floating point)
        vritti_sum = sum(self.vritti.values())
        if not 0.99 <= vritti_sum <= 1.01:
            raise ValueError(
                f"vritti values must sum to 1.0, got {vritti_sum}"
            )

        # Validate dominant_vritti
        if self.dominant_vritti not in expected_keys:
            raise ValueError(
                f"dominant_vritti must be one of {expected_keys}, got {self.dominant_vritti}"
            )


@dataclass
class SessionState:
    """Per-session state for smṛti computation.

    Maintains temporal context needed to detect staleness (smṛti escalation).
    """

    previous_inputs: Optional[ChittaVrittiInputs] = None
    accumulated_smrti: float = 0.0

    def update(self, current_inputs: ChittaVrittiInputs, new_smrti: float) -> None:
        """Update session state after computation."""
        self.previous_inputs = current_inputs
        self.accumulated_smrti = new_smrti
