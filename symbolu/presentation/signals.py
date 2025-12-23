"""Presentation Layer Signal Structures.

Implements: PRESENTATION_LAYER_v1.0.md Part 6

Defines the input signal structures consumed by the Presentation Engine:
- VrittiDistribution: The 5-mode cognitive distribution
- SessionContext: Session-level tracking signals
- SignalBundle: Complete input bundle for rule evaluation
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from symbolu.chitta_vritti.types import ChittaVrittiInputs, ChittaVrittiResult


@dataclass
class VrittiDistribution:
    """Distribution across the 5 vṛtti modes.

    Part 6.1: Extracted from ChittaVrittiResult.vritti dict.
    """

    pramana: float = 0.0  # Valid cognition
    viparyaya: float = 0.0  # Misperception
    vikalpa: float = 0.0  # Conceptual branching
    smrti: float = 0.0  # Memory/staleness
    nidra: float = 0.0  # Dormancy/absence

    def __post_init__(self) -> None:
        """Validate distribution values."""
        for name, value in [
            ("pramana", self.pramana),
            ("viparyaya", self.viparyaya),
            ("vikalpa", self.vikalpa),
            ("smrti", self.smrti),
            ("nidra", self.nidra),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")

    @classmethod
    def from_dict(cls, vritti_dict: dict[str, float]) -> "VrittiDistribution":
        """Construct from CV result vritti dict."""
        return cls(
            pramana=vritti_dict.get("pramana", 0.0),
            viparyaya=vritti_dict.get("viparyaya", 0.0),
            vikalpa=vritti_dict.get("vikalpa", 0.0),
            smrti=vritti_dict.get("smrti", 0.0),
            nidra=vritti_dict.get("nidra", 0.0),
        )


@dataclass
class SessionContext:
    """Session-level context signals.

    Part 6.1: Tracked by SessionStateManager across turns.
    """

    turn_count: int = 0
    consecutive_low_scores: int = 0  # Streak of score < 0.5
    consecutive_high_scores: int = 0  # Streak of score > 0.8
    consecutive_low_motion: int = 0  # Streak of motion < 0.1
    previous_dominant_vritti: Optional[str] = None  # Last turn's dominant mode
    accumulated_smrti: float = 0.0  # Staleness accumulation


@dataclass(frozen=True)
class SignalBundle:
    """All signals consumed by Presentation Layer.

    Part 6.1: Complete input bundle constructed from CV result and context.

    This is the unified input to the PresentationEngine. It aggregates:
    - Chitta-Vṛtti outputs (coherence, score, vritti distribution)
    - Raw observables (entropy, motion, confidence)
    - Layer presence information
    - Session context
    """

    # === Chitta-Vṛtti Outputs ===
    coherence: float  # Cross-layer agreement [0, 1]
    score: float  # Overall readiness [0, 1]
    dominant_vritti: str  # Primary cognitive mode
    vritti: VrittiDistribution  # Full distribution
    fractures: dict  # Pairwise disagreements
    primary_fracture: Optional[tuple[str, str]]  # Highest disagreement pair
    fast_path_used: bool  # Optimization flag

    # === Raw Observables ===
    entropy: float  # Normalized uncertainty [0, 1]
    motion: float  # Semantic delta [0, 1]
    confidence: float  # Fusion audit confidence [0, 1]
    temporal_continuity: float  # State consistency [0, 1]

    # === Layer Presence ===
    layers_present_count: int  # Total layers available [0-4]
    missing_layers: tuple  # Tuple of missing layer names (frozen)

    # === Session Context ===
    session: SessionContext

    @classmethod
    def from_cv_result(
        cls,
        result: "ChittaVrittiResult",
        inputs: "ChittaVrittiInputs",
        session: SessionContext,
    ) -> "SignalBundle":
        """Construct bundle from CV result and context.

        Part 6.1: Factory method for standard construction flow.

        Args:
            result: Output from ChittaVrittiEngine.compute()
            inputs: Original inputs to CV engine
            session: Current session context

        Returns:
            Complete SignalBundle ready for rule evaluation
        """
        # Build vritti distribution from result dict
        vritti = VrittiDistribution.from_dict(result.vritti)

        # Determine missing layers
        missing = []
        if inputs.phonemic_rep is None:
            missing.append("phonemic")
        if inputs.semantic_rep is None:
            missing.append("semantic")
        if inputs.structural_rep is None:
            missing.append("structural")
        if inputs.temporal_rep is None:
            missing.append("temporal")

        # Count present layers
        layers_present = 4 - len(missing)

        return cls(
            # CV outputs
            coherence=result.coherence,
            score=result.score,
            dominant_vritti=result.dominant_vritti,
            vritti=vritti,
            fractures=dict(result.fractures) if result.fractures else {},
            primary_fracture=result.primary_fracture,
            fast_path_used=result.fast_path_used,
            # Raw observables
            entropy=inputs.entropy,
            motion=inputs.motion,
            confidence=inputs.confidence,
            temporal_continuity=inputs.temporal_continuity,
            # Layer presence
            layers_present_count=layers_present,
            missing_layers=tuple(missing),
            # Session
            session=session,
        )

    @classmethod
    def create_minimal(
        cls,
        score: float = 0.5,
        coherence: float = 0.5,
        vritti: Optional[VrittiDistribution] = None,
        **kwargs,
    ) -> "SignalBundle":
        """Create minimal bundle for testing.

        Provides sensible defaults for all required fields.
        """
        if vritti is None:
            vritti = VrittiDistribution(
                pramana=0.2,
                viparyaya=0.2,
                vikalpa=0.2,
                smrti=0.2,
                nidra=0.2,
            )

        defaults = {
            "coherence": coherence,
            "score": score,
            "dominant_vritti": "pramana",
            "vritti": vritti,
            "fractures": {},
            "primary_fracture": None,
            "fast_path_used": False,
            "entropy": 0.3,
            "motion": 0.2,
            "confidence": 0.7,
            "temporal_continuity": 0.8,
            "layers_present_count": 4,
            "missing_layers": (),
            "session": SessionContext(),
        }
        defaults.update(kwargs)
        return cls(**defaults)
