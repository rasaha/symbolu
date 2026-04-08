"""Presentation Layer Signal Structures.

Implements: PRESENTATION_LAYER_v1.0.md Part 6

Defines the input signal structures consumed by the Presentation Engine:
- VrittiDistribution: The 5-mode cognitive distribution
- SessionContext: Session-level tracking signals
- V27ExperimentalSignals: Optional v2.7 experimental signals
- SignalBundle: Complete input bundle for rule evaluation
"""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from agentic.chitta_vritti.types import ChittaVrittiInputs, ChittaVrittiResult


# =============================================================================
# V2.7 Experimental Signals (Optional)
# =============================================================================

@dataclass
class V27ExperimentalSignals:
    """Optional signals from v2.7 experimental features.

    These signals are only available when v2.7 experimental features are enabled.
    The Presentation Layer gracefully handles their absence.

    v2.7 has two modes (from V27Config.update_mode):
    - EMA mode: Standard exponential moving average updates
    - Bayesian mode (Alpha 2.7): Full uncertainty quantification

    Signals by mode:
    - EMA v2.7: cognitive_state, mirror_balance, concept_readiness, primary_cause
    - Bayesian v2.7: All above PLUS bayesian_confidence, credible_interval_width

    Signals from SPEC_V27_EXPERIMENTAL.md:
    - Bayesian 2.7: bayesian_confidence (ONLY in Bayesian mode)
    - Cognitive Ability Model: cognitive_state, mirror_balance
    - Concept Readiness Index: concept_readiness
    - Causal Layer: primary_cause
    - Self-Improvement: low_utility_streak
    """

    # === Mode Flags ===
    v27_enabled: bool = False  # Master switch: V27Config.v2_7_enabled
    bayesian_mode: bool = False  # Bayesian mode: V27Config.is_bayesian

    # === Bayesian 2.7 (Alpha 2.7) - ONLY available when bayesian_mode=True ===
    bayesian_confidence: Optional[float] = None  # Reliability of estimates [0, 1]
    credible_interval_width: Optional[float] = None  # Uncertainty width

    # === Cognitive Ability Model (EMA or Bayesian) ===
    cognitive_state: str = "neutral"  # thriving/striving/stable/regressing/unstable/neutral
    mirror_balance: float = 1.0  # Self-referential coherence [0, 1]
    cognitive_ambition: float = 0.0  # Improvement vs regression [-1, 1]

    # === Concept Readiness Index (EMA or Bayesian) ===
    concept_readiness: float = 1.0  # CRI [0, 1]
    concept_readiness_level: str = "ready"  # ready/nearly_ready/forming/emerging/not_ready

    # === Causal Layer (EMA or Bayesian) ===
    primary_cause: Optional[str] = None  # Which layer caused issues
    causal_attribution: Optional[dict] = None  # Layer -> contribution %

    # === Self-Improvement (EMA or Bayesian) ===
    low_utility_streak: int = 0  # Consecutive low utility observations

    def __post_init__(self) -> None:
        """Validate signal values."""
        # Bayesian signals only valid in Bayesian mode
        if self.bayesian_confidence is not None:
            if not 0.0 <= self.bayesian_confidence <= 1.0:
                raise ValueError(f"bayesian_confidence must be in [0, 1], got {self.bayesian_confidence}")

        if not 0.0 <= self.mirror_balance <= 1.0:
            raise ValueError(f"mirror_balance must be in [0, 1], got {self.mirror_balance}")
        if not 0.0 <= self.concept_readiness <= 1.0:
            raise ValueError(f"concept_readiness must be in [0, 1], got {self.concept_readiness}")

        valid_cognitive_states = {"thriving", "striving", "stable", "regressing", "unstable", "neutral"}
        if self.cognitive_state not in valid_cognitive_states:
            raise ValueError(f"cognitive_state must be one of {valid_cognitive_states}, got {self.cognitive_state}")

        valid_cri_levels = {"ready", "nearly_ready", "forming", "emerging", "not_ready"}
        if self.concept_readiness_level not in valid_cri_levels:
            raise ValueError(f"concept_readiness_level must be one of {valid_cri_levels}, got {self.concept_readiness_level}")

    @property
    def is_available(self) -> bool:
        """Check if v2.7 signals are available (v2.7 enabled)."""
        return self.v27_enabled

    @property
    def has_bayesian_signals(self) -> bool:
        """Check if Bayesian-specific signals are available."""
        return self.v27_enabled and self.bayesian_mode and self.bayesian_confidence is not None

    @property
    def is_estimate_reliable(self) -> bool:
        """Check if Bayesian estimate is reliable (confidence >= 0.7).

        Returns True if Bayesian mode is off (assume reliable by default).
        """
        if not self.has_bayesian_signals:
            return True  # No Bayesian data = assume reliable
        return self.bayesian_confidence >= 0.7

    @property
    def is_regressing(self) -> bool:
        """Check if cognitive state indicates regression."""
        return self.cognitive_state in {"regressing", "unstable"}

    @property
    def is_concept_stable(self) -> bool:
        """Check if concepts are stable enough to present confidently."""
        return self.concept_readiness >= 0.6

    @property
    def has_causal_attribution(self) -> bool:
        """Check if causal attribution is available."""
        return self.primary_cause is not None

    @classmethod
    def disabled(cls) -> "V27ExperimentalSignals":
        """Create signals for when v2.7 is disabled."""
        return cls(v27_enabled=False, bayesian_mode=False)

    @classmethod
    def ema_mode(cls, **kwargs) -> "V27ExperimentalSignals":
        """Create signals for EMA v2.7 mode."""
        return cls(v27_enabled=True, bayesian_mode=False, **kwargs)

    @classmethod
    def bayesian_mode_signals(
        cls,
        bayesian_confidence: float,
        credible_interval_width: float = 0.0,
        **kwargs,
    ) -> "V27ExperimentalSignals":
        """Create signals for Bayesian v2.7 mode."""
        return cls(
            v27_enabled=True,
            bayesian_mode=True,
            bayesian_confidence=bayesian_confidence,
            credible_interval_width=credible_interval_width,
            **kwargs,
        )


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

    # === V2.7 Experimental Signals (Optional) ===
    v27: Optional[V27ExperimentalSignals] = None

    @property
    def has_v27_signals(self) -> bool:
        """Check if v2.7 experimental signals are available."""
        return self.v27 is not None and self.v27.is_available

    @property
    def has_bayesian_signals(self) -> bool:
        """Check if Bayesian v2.7 signals are available."""
        return self.v27 is not None and self.v27.has_bayesian_signals

    @classmethod
    def from_cv_result(
        cls,
        result: "ChittaVrittiResult",
        inputs: "ChittaVrittiInputs",
        session: SessionContext,
        v27: Optional[V27ExperimentalSignals] = None,
    ) -> "SignalBundle":
        """Construct bundle from CV result and context.

        Part 6.1: Factory method for standard construction flow.

        Args:
            result: Output from ChittaVrittiEngine.compute()
            inputs: Original inputs to CV engine
            session: Current session context
            v27: Optional v2.7 experimental signals (None if v2.7 disabled)

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
            # V2.7 experimental (optional)
            v27=v27,
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
            "v27": None,  # v2.7 disabled by default in tests
        }
        defaults.update(kwargs)
        return cls(**defaults)

    @classmethod
    def create_with_v27(
        cls,
        v27: V27ExperimentalSignals,
        **kwargs,
    ) -> "SignalBundle":
        """Create bundle with v2.7 experimental signals for testing.

        Args:
            v27: V2.7 experimental signals (EMA or Bayesian mode)
            **kwargs: Override any SignalBundle fields

        Returns:
            SignalBundle with v2.7 signals attached
        """
        return cls.create_minimal(v27=v27, **kwargs)
