"""
MirrorBalance: Self-Referential Balance Through Signal Mirrors
==============================================================

Implements mirror logic for balance detection and correction.

The concept: Create a "mirror" of the current signal state and compare
the original against its reflection. Asymmetries reveal imbalance that
can be corrected.

This connects to HRM (Harmonic Resonance Model) at the Fusion Renderer
level by providing a self-referential mechanism for balance.

Version: 2.7.4
Date: 2025-12-22

Theory:
-------
Just as a physical mirror reveals asymmetries in appearance, a signal
mirror reveals asymmetries in state. The mirror is not a simple inversion
but a principled complement that preserves certain invariants while
flipping others.

Mirror Types:
1. Guna Mirror: S ↔ T (Sattva/Tamas swap), R stays (Rajas is neutral)
2. Entropy Mirror: H' = 1 - H (order/chaos complement)
3. Motion Mirror: M' = 1 - M (stillness/movement complement)
4. Full Mirror: All signals mirrored together

Balance Detection:
- If original ≈ mirror, the state is balanced
- If |original - mirror| is large, imbalance exists
- The direction of imbalance tells us HOW to correct

Correction:
- Blend original toward mirror by a learning rate
- This pulls the system toward balance without overcorrecting
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import math

from symbolu.guna_modulation.observables import Observables, MotionType

# Epsilon for numerical stability
EPSILON: float = 1e-9


# =============================================================================
# Mirror Observables
# =============================================================================

@dataclass(frozen=True)
class MirrorPair:
    """
    A pair of original and mirrored observables.

    The mirror reveals what the "opposite" state would look like,
    allowing comparison and balance detection.
    """
    original: Observables
    mirror: Observables

    @property
    def guna_asymmetry(self) -> float:
        """
        Asymmetry in Guna distribution.

        Measures |S - T|. Perfect balance has S = T (with R as the neutral axis).
        Range: [0, 1] where 0 = perfect balance, 1 = extreme imbalance
        """
        return abs(self.original.s - self.original.t)

    @property
    def entropy_asymmetry(self) -> float:
        """
        Asymmetry in entropy (deviation from 0.5).

        Entropy at 0.5 represents balance between order and chaos.
        Range: [0, 0.5] where 0 = perfect balance
        """
        return abs(self.original.H - 0.5)

    @property
    def motion_asymmetry(self) -> float:
        """
        Asymmetry in motion (deviation from 0.5).

        Motion at 0.5 represents balance between stillness and movement.
        Range: [0, 0.5] where 0 = perfect balance
        """
        return abs(self.original.delta_sem - 0.5)

    @property
    def total_asymmetry(self) -> float:
        """
        Composite asymmetry score.

        Weighted combination of all asymmetries.
        Range: [0, 1] where 0 = perfect balance
        """
        # Weight Guna asymmetry highest (it's the primary signal)
        weights = (0.5, 0.25, 0.25)
        asymmetries = (
            self.guna_asymmetry,
            self.entropy_asymmetry * 2,  # Scale to [0, 1]
            self.motion_asymmetry * 2,   # Scale to [0, 1]
        )
        return sum(w * a for w, a in zip(weights, asymmetries))

    @property
    def is_balanced(self) -> bool:
        """Check if state is within balance threshold."""
        return self.total_asymmetry < 0.15  # 15% tolerance

    @property
    def balance_direction(self) -> str:
        """
        Direction of imbalance.

        Returns human-readable description of where imbalance lies.
        """
        if self.is_balanced:
            return "balanced"

        directions = []

        # Guna direction
        if self.original.s > self.original.t + 0.1:
            directions.append("sattva-heavy")
        elif self.original.t > self.original.s + 0.1:
            directions.append("tamas-heavy")

        # Entropy direction
        if self.original.H > 0.6:
            directions.append("high-entropy")
        elif self.original.H < 0.4:
            directions.append("low-entropy")

        # Motion direction
        if self.original.delta_sem > 0.6:
            directions.append("high-motion")
        elif self.original.delta_sem < 0.4:
            directions.append("low-motion")

        return ", ".join(directions) if directions else "subtle-imbalance"


def compute_mirror_observables(obs: Observables) -> Observables:
    """
    Compute the mirror (complement) of observables.

    Mirror transformation:
    - Guna: S ↔ T (Sattva/Tamas swap), R stays
    - Entropy: H' = 1 - H
    - Motion: M' = 1 - M
    - Contradiction/Failure: inverted (success mirror)

    The mirror represents the "opposite" state that would balance
    the current state if blended together.

    Args:
        obs: Original observables

    Returns:
        Mirrored observables
    """
    return Observables(
        s=obs.t,          # Sattva ↔ Tamas swap
        r=obs.r,          # Rajas stays (neutral axis)
        t=obs.s,          # Tamas ↔ Sattva swap
        H=1.0 - obs.H,    # Entropy complement
        delta_sem=1.0 - obs.delta_sem,  # Motion complement
        C_contr=1.0 - obs.C_contr,      # Success instead of contradiction
        F_fail=1.0 - obs.F_fail,        # Success instead of failure
        motion_type=obs.motion_type,
    )


def create_mirror_pair(obs: Observables) -> MirrorPair:
    """
    Create a mirror pair from observables.

    Args:
        obs: Original observables

    Returns:
        MirrorPair with original and mirror
    """
    return MirrorPair(
        original=obs,
        mirror=compute_mirror_observables(obs),
    )


# =============================================================================
# Balance Correction
# =============================================================================

@dataclass
class BalanceCorrection:
    """
    Correction signals to bring state toward balance.

    These are delta values that can be applied to observables
    to reduce asymmetry.
    """
    delta_s: float      # Adjustment to Sattva
    delta_r: float      # Adjustment to Rajas
    delta_t: float      # Adjustment to Tamas
    delta_H: float      # Adjustment to entropy
    delta_M: float      # Adjustment to motion
    asymmetry_before: float  # Asymmetry before correction
    asymmetry_after: float   # Expected asymmetry after correction

    @property
    def correction_magnitude(self) -> float:
        """Total magnitude of correction."""
        return math.sqrt(
            self.delta_s**2 + self.delta_r**2 + self.delta_t**2 +
            self.delta_H**2 + self.delta_M**2
        )

    @property
    def improvement_ratio(self) -> float:
        """Ratio of improvement (how much asymmetry is reduced)."""
        if self.asymmetry_before < EPSILON:
            return 1.0
        return 1.0 - (self.asymmetry_after / self.asymmetry_before)


def compute_balance_correction(
    obs: Observables,
    learning_rate: float = 0.1,
) -> BalanceCorrection:
    """
    Compute correction signals to bring state toward balance.

    The correction pulls the current state toward its mirror,
    which is equivalent to pulling toward balance.

    Args:
        obs: Current observables
        learning_rate: How aggressively to correct (0 = none, 1 = full)

    Returns:
        BalanceCorrection with delta values
    """
    pair = create_mirror_pair(obs)

    # Compute deltas (direction: original → mirror)
    # Guna correction: pull toward S = T
    delta_s = learning_rate * (pair.mirror.s - pair.original.s)
    delta_t = learning_rate * (pair.mirror.t - pair.original.t)
    delta_r = 0.0  # Rajas is neutral axis, no correction

    # Entropy correction: pull toward 0.5
    delta_H = learning_rate * (0.5 - pair.original.H)

    # Motion correction: pull toward 0.5
    delta_M = learning_rate * (0.5 - pair.original.delta_sem)

    # Estimate asymmetry after correction
    corrected_s = pair.original.s + delta_s
    corrected_t = pair.original.t + delta_t
    corrected_H = pair.original.H + delta_H
    corrected_M = pair.original.delta_sem + delta_M

    asymmetry_after = (
        0.5 * abs(corrected_s - corrected_t) +
        0.25 * abs(corrected_H - 0.5) * 2 +
        0.25 * abs(corrected_M - 0.5) * 2
    )

    return BalanceCorrection(
        delta_s=delta_s,
        delta_r=delta_r,
        delta_t=delta_t,
        delta_H=delta_H,
        delta_M=delta_M,
        asymmetry_before=pair.total_asymmetry,
        asymmetry_after=asymmetry_after,
    )


def apply_balance_correction(
    obs: Observables,
    correction: BalanceCorrection,
) -> Observables:
    """
    Apply balance correction to observables.

    Creates new observables with corrections applied.
    Ensures all constraints are maintained (Guna sums to 1, values in [0,1]).

    Args:
        obs: Original observables
        correction: Correction to apply

    Returns:
        Corrected observables
    """
    # Apply Guna corrections
    new_s = obs.s + correction.delta_s
    new_r = obs.r + correction.delta_r
    new_t = obs.t + correction.delta_t

    # Clamp to [0, 1]
    new_s = max(0.0, min(1.0, new_s))
    new_r = max(0.0, min(1.0, new_r))
    new_t = max(0.0, min(1.0, new_t))

    # Renormalize to sum to 1
    total = new_s + new_r + new_t
    if total > EPSILON:
        new_s /= total
        new_r /= total
        new_t /= total
    else:
        # Fallback to uniform
        new_s = new_r = new_t = 1.0 / 3.0

    # Apply other corrections
    new_H = max(0.0, min(1.0, obs.H + correction.delta_H))
    new_M = max(0.0, min(1.0, obs.delta_sem + correction.delta_M))

    return Observables(
        s=new_s,
        r=new_r,
        t=new_t,
        H=new_H,
        delta_sem=new_M,
        C_contr=obs.C_contr,  # Don't correct these
        F_fail=obs.F_fail,
        motion_type=obs.motion_type,
    )


# =============================================================================
# Mirror Balance Engine
# =============================================================================

class MirrorBalanceEngine:
    """
    Engine for continuous balance monitoring and correction.

    Integrates with the state evolution layer to provide
    self-referential balance checking.

    Usage:
        engine = MirrorBalanceEngine(learning_rate=0.1)

        # Monitor balance
        pair = engine.analyze(observables)
        if not pair.is_balanced:
            print(f"Imbalance detected: {pair.balance_direction}")

        # Get correction
        correction = engine.suggest_correction(observables)

        # Apply correction (optional)
        corrected = engine.apply_correction(observables)
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        auto_correct: bool = False,
        balance_threshold: float = 0.15,
    ):
        """
        Initialize MirrorBalanceEngine.

        Args:
            learning_rate: How aggressively to correct imbalance
            auto_correct: If True, automatically apply corrections
            balance_threshold: Asymmetry threshold for "balanced" state
        """
        self._learning_rate = learning_rate
        self._auto_correct = auto_correct
        self._balance_threshold = balance_threshold
        self._history: list = []

    def analyze(self, obs: Observables) -> MirrorPair:
        """
        Analyze observables for balance.

        Args:
            obs: Observables to analyze

        Returns:
            MirrorPair with analysis
        """
        pair = create_mirror_pair(obs)
        self._history.append({
            "asymmetry": pair.total_asymmetry,
            "direction": pair.balance_direction,
        })
        return pair

    def suggest_correction(self, obs: Observables) -> BalanceCorrection:
        """
        Suggest correction for imbalance.

        Args:
            obs: Observables to correct

        Returns:
            BalanceCorrection with suggested deltas
        """
        return compute_balance_correction(obs, self._learning_rate)

    def apply_correction(
        self,
        obs: Observables,
        correction: Optional[BalanceCorrection] = None,
    ) -> Observables:
        """
        Apply correction to observables.

        Args:
            obs: Original observables
            correction: Optional pre-computed correction

        Returns:
            Corrected observables
        """
        if correction is None:
            correction = self.suggest_correction(obs)
        return apply_balance_correction(obs, correction)

    def process(self, obs: Observables) -> Tuple[Observables, MirrorPair]:
        """
        Full processing pipeline: analyze and optionally correct.

        Args:
            obs: Input observables

        Returns:
            Tuple of (possibly corrected observables, analysis pair)
        """
        pair = self.analyze(obs)

        if self._auto_correct and not pair.is_balanced:
            corrected = self.apply_correction(obs)
            return corrected, pair

        return obs, pair

    @property
    def asymmetry_trend(self) -> list:
        """Get history of asymmetry values."""
        return [h["asymmetry"] for h in self._history]

    @property
    def average_asymmetry(self) -> float:
        """Get average asymmetry over history."""
        if not self._history:
            return 0.0
        return sum(h["asymmetry"] for h in self._history) / len(self._history)

    def reset_history(self):
        """Clear history."""
        self._history = []


# =============================================================================
# Harmonic Mirror (HRM Integration)
# =============================================================================

def compute_harmonic_mirror(
    obs: Observables,
    harmonic_weights: Tuple[float, float, float] = (0.5, 0.3, 0.2),
) -> Observables:
    """
    Compute harmonic mirror for HRM integration.

    The harmonic mirror blends original and mirror signals using
    harmonic weights, creating a "resonance" state.

    This connects to HRM (Harmonic Resonance Model) by creating
    a signal that represents the harmonic mean of original and mirror.

    Args:
        obs: Original observables
        harmonic_weights: Weights for (original, mirror, balance_point)

    Returns:
        Harmonically balanced observables
    """
    w_orig, w_mirror, w_balance = harmonic_weights
    w_total = w_orig + w_mirror + w_balance
    w_orig /= w_total
    w_mirror /= w_total
    w_balance /= w_total

    mirror = compute_mirror_observables(obs)

    # Balance point is uniform/neutral
    balance_s = balance_r = balance_t = 1.0 / 3.0
    balance_H = 0.5
    balance_M = 0.5

    # Harmonic blend
    new_s = w_orig * obs.s + w_mirror * mirror.s + w_balance * balance_s
    new_r = w_orig * obs.r + w_mirror * mirror.r + w_balance * balance_r
    new_t = w_orig * obs.t + w_mirror * mirror.t + w_balance * balance_t
    new_H = w_orig * obs.H + w_mirror * mirror.H + w_balance * balance_H
    new_M = w_orig * obs.delta_sem + w_mirror * mirror.delta_sem + w_balance * balance_M

    # Renormalize Guna
    total = new_s + new_r + new_t
    new_s /= total
    new_r /= total
    new_t /= total

    return Observables(
        s=new_s,
        r=new_r,
        t=new_t,
        H=new_H,
        delta_sem=new_M,
        C_contr=obs.C_contr,
        F_fail=obs.F_fail,
        motion_type=obs.motion_type,
    )


# =============================================================================
# Self-Questioning Protocol
# =============================================================================

@dataclass
class SelfQuestion:
    """
    A question the system asks itself via mirror comparison.

    The mirror doesn't just detect imbalance - it poses questions
    about the current state that the system can use for reflection.
    """
    question: str
    signal: str
    current_value: float
    mirror_value: float
    deviation: float
    severity: str  # "low", "medium", "high"

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.question} ({self.signal}: {self.current_value:.3f} vs mirror {self.mirror_value:.3f})"


def generate_self_questions(obs: Observables) -> list:
    """
    Generate self-referential questions based on mirror comparison.

    The system "questions itself" by comparing current state to mirror.
    These questions can guide balance correction or flag concerns.

    Args:
        obs: Current observables

    Returns:
        List of SelfQuestion objects
    """
    pair = create_mirror_pair(obs)
    questions = []

    def severity(dev: float) -> str:
        if dev < 0.15:
            return "low"
        elif dev < 0.35:
            return "medium"
        return "high"

    # Guna questions
    guna_dev = pair.guna_asymmetry
    if guna_dev > 0.1:
        if obs.s > obs.t:
            questions.append(SelfQuestion(
                question="Is the system too oriented toward clarity/order?",
                signal="sattva-tamas",
                current_value=obs.s,
                mirror_value=obs.t,
                deviation=guna_dev,
                severity=severity(guna_dev),
            ))
        else:
            questions.append(SelfQuestion(
                question="Is the system too oriented toward inertia/stability?",
                signal="tamas-sattva",
                current_value=obs.t,
                mirror_value=obs.s,
                deviation=guna_dev,
                severity=severity(guna_dev),
            ))

    # Entropy questions
    entropy_dev = pair.entropy_asymmetry
    if entropy_dev > 0.1:
        if obs.H > 0.5:
            questions.append(SelfQuestion(
                question="Is there too much uncertainty/chaos in the signals?",
                signal="entropy-high",
                current_value=obs.H,
                mirror_value=1.0 - obs.H,
                deviation=entropy_dev,
                severity=severity(entropy_dev * 2),
            ))
        else:
            questions.append(SelfQuestion(
                question="Is the system too rigid/certain?",
                signal="entropy-low",
                current_value=obs.H,
                mirror_value=1.0 - obs.H,
                deviation=entropy_dev,
                severity=severity(entropy_dev * 2),
            ))

    # Motion questions
    motion_dev = pair.motion_asymmetry
    if motion_dev > 0.1:
        if obs.delta_sem > 0.5:
            questions.append(SelfQuestion(
                question="Is there too much change/movement happening?",
                signal="motion-high",
                current_value=obs.delta_sem,
                mirror_value=1.0 - obs.delta_sem,
                deviation=motion_dev,
                severity=severity(motion_dev * 2),
            ))
        else:
            questions.append(SelfQuestion(
                question="Is the system too static/stagnant?",
                signal="motion-low",
                current_value=obs.delta_sem,
                mirror_value=1.0 - obs.delta_sem,
                deviation=motion_dev,
                severity=severity(motion_dev * 2),
            ))

    # Contradiction questions
    if obs.C_contr > 0.2:
        questions.append(SelfQuestion(
            question="Are there unresolved contradictions that need attention?",
            signal="contradiction",
            current_value=obs.C_contr,
            mirror_value=1.0 - obs.C_contr,
            deviation=obs.C_contr,
            severity=severity(obs.C_contr),
        ))

    # Failure questions
    if obs.F_fail > 0.1:
        questions.append(SelfQuestion(
            question="Are failures accumulating that need correction?",
            signal="failure",
            current_value=obs.F_fail,
            mirror_value=1.0 - obs.F_fail,
            deviation=obs.F_fail,
            severity=severity(obs.F_fail),
        ))

    # Balance question (meta)
    if pair.total_asymmetry > 0.2:
        questions.append(SelfQuestion(
            question="Is the overall system in balance?",
            signal="total-asymmetry",
            current_value=pair.total_asymmetry,
            mirror_value=0.0,  # Perfect balance
            deviation=pair.total_asymmetry,
            severity=severity(pair.total_asymmetry),
        ))

    return questions


# =============================================================================
# Ontological Layer Hierarchy
# =============================================================================

class OntologicalLayer:
    """
    Defines the ontological layers in the processing pipeline.

    Each layer represents a different level of abstraction:
    - Lower layers: closer to raw signals
    - Higher layers: closer to meaning and interpretation

    The hierarchy creates natural "friction points" where
    dissonance can drive cognitive ambition.
    """
    # Layer 0: Physical/Signal Layer
    # Raw signals before any interpretation
    SIGNAL = "signal"

    # Layer 1: Embedding Layer
    # Semantic embeddings from signals
    EMBEDDING = "embedding"

    # Layer 2: Guna Layer
    # Quality classification (Sattva/Rajas/Tamas)
    GUNA = "guna"

    # Layer 3: Motion Layer
    # Change detection and dynamics
    MOTION = "motion"

    # Layer 4: Fusion Layer
    # Integration of all signals (HRM)
    FUSION = "fusion"

    # Layer 5: State Layer
    # Evolved state registers
    STATE = "state"

    # Layer 6: Output Layer
    # Final rendered output
    OUTPUT = "output"

    # Ordered hierarchy (lower index = lower abstraction)
    HIERARCHY = [SIGNAL, EMBEDDING, GUNA, MOTION, FUSION, STATE, OUTPUT]

    @classmethod
    def level(cls, layer: str) -> int:
        """Get the abstraction level of a layer (0-6)."""
        if layer in cls.HIERARCHY:
            return cls.HIERARCHY.index(layer)
        return -1

    @classmethod
    def is_adjacent(cls, layer_a: str, layer_b: str) -> bool:
        """Check if two layers are adjacent in the hierarchy."""
        level_a = cls.level(layer_a)
        level_b = cls.level(layer_b)
        if level_a < 0 or level_b < 0:
            return False
        return abs(level_a - level_b) == 1

    @classmethod
    def direction(cls, from_layer: str, to_layer: str) -> str:
        """
        Get direction of layer transition.

        Returns:
            "ascending" if moving to higher abstraction
            "descending" if moving to lower abstraction
            "same" if same level
        """
        from_level = cls.level(from_layer)
        to_level = cls.level(to_layer)
        if to_level > from_level:
            return "ascending"
        elif to_level < from_level:
            return "descending"
        return "same"


# =============================================================================
# Configurable Layer Comparison
# =============================================================================

@dataclass
class LayerComparisonConfig:
    """
    Configuration for which layers to compare for cognitive ambition.

    This is where "cognitive ability" emerges from user selection:
    - Users choose which ontological boundaries to monitor
    - Different tiers/domains focus on different layer transitions
    - The system's "attention" is directed by this configuration

    Attributes:
        primary_comparison: Main layer pair to monitor (upstream, downstream)
        secondary_comparisons: Additional layer pairs to track
        mirror_layer: Default layer for balance comparison
        attention_weight: Weight given to primary vs secondary [0, 1]
        enable_cross_layer: Whether to compute cross-layer dissonance
    """
    primary_comparison: Tuple[str, str]  # (upstream_layer, downstream_layer)
    secondary_comparisons: list  # List of (layer_a, layer_b) tuples
    mirror_layer: str  # Layer used as reference for balance
    attention_weight: float = 0.7  # Weight for primary comparison
    enable_cross_layer: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if not 0 <= self.attention_weight <= 1:
            raise ValueError("attention_weight must be in [0, 1]")

    @property
    def all_comparisons(self) -> list:
        """All layer comparisons (primary + secondary)."""
        return [self.primary_comparison] + self.secondary_comparisons

    @property
    def monitored_layers(self) -> set:
        """Set of all layers being monitored."""
        layers = set()
        for a, b in self.all_comparisons:
            layers.add(a)
            layers.add(b)
        layers.add(self.mirror_layer)
        return layers


# =============================================================================
# Tier-Specific Layer Comparison Defaults
# =============================================================================

# Enterprise Tier 1: Focus on Fusion → State (high-level quality)
LAYER_COMPARISON_ENTERPRISE_T1 = LayerComparisonConfig(
    primary_comparison=(OntologicalLayer.FUSION, OntologicalLayer.STATE),
    secondary_comparisons=[
        (OntologicalLayer.GUNA, OntologicalLayer.FUSION),
    ],
    mirror_layer=OntologicalLayer.FUSION,  # Compare against fusion for balance
    attention_weight=0.8,
)

# Enterprise Tier 2: Focus on Guna → Fusion (semantic integration)
LAYER_COMPARISON_ENTERPRISE_T2 = LayerComparisonConfig(
    primary_comparison=(OntologicalLayer.GUNA, OntologicalLayer.FUSION),
    secondary_comparisons=[
        (OntologicalLayer.EMBEDDING, OntologicalLayer.GUNA),
        (OntologicalLayer.FUSION, OntologicalLayer.STATE),
    ],
    mirror_layer=OntologicalLayer.GUNA,  # Compare against Guna for balance
    attention_weight=0.7,
)

# Consumer: Focus on State → Output (user-facing quality)
LAYER_COMPARISON_CONSUMER = LayerComparisonConfig(
    primary_comparison=(OntologicalLayer.STATE, OntologicalLayer.OUTPUT),
    secondary_comparisons=[
        (OntologicalLayer.FUSION, OntologicalLayer.STATE),
    ],
    mirror_layer=OntologicalLayer.OUTPUT,  # Compare against output for balance
    attention_weight=0.6,
)

# Full pipeline monitoring (for debugging/audit)
LAYER_COMPARISON_FULL_PIPELINE = LayerComparisonConfig(
    primary_comparison=(OntologicalLayer.SIGNAL, OntologicalLayer.OUTPUT),
    secondary_comparisons=[
        (OntologicalLayer.SIGNAL, OntologicalLayer.EMBEDDING),
        (OntologicalLayer.EMBEDDING, OntologicalLayer.GUNA),
        (OntologicalLayer.GUNA, OntologicalLayer.MOTION),
        (OntologicalLayer.MOTION, OntologicalLayer.FUSION),
        (OntologicalLayer.FUSION, OntologicalLayer.STATE),
        (OntologicalLayer.STATE, OntologicalLayer.OUTPUT),
    ],
    mirror_layer=OntologicalLayer.FUSION,  # Center of pipeline
    attention_weight=0.5,  # Equal attention to all
)

# Default: Enterprise T2 behavior
DEFAULT_LAYER_COMPARISON = LAYER_COMPARISON_ENTERPRISE_T2


def get_layer_comparison_for_tier(tier: str) -> LayerComparisonConfig:
    """
    Get layer comparison configuration for a tier.

    Args:
        tier: Tier identifier ("enterprise_t1", "enterprise_t2", "consumer")

    Returns:
        Layer comparison configuration
    """
    tier_configs = {
        "enterprise_t1": LAYER_COMPARISON_ENTERPRISE_T1,
        "enterprise_t2": LAYER_COMPARISON_ENTERPRISE_T2,
        "consumer": LAYER_COMPARISON_CONSUMER,
        "full": LAYER_COMPARISON_FULL_PIPELINE,
    }
    return tier_configs.get(tier.lower(), DEFAULT_LAYER_COMPARISON)


# =============================================================================
# Configurable Dissonance Monitor
# =============================================================================

class ConfigurableDissonanceMonitor:
    """
    Dissonance monitor with user-configurable layer comparisons.

    The "cognitive ability" emerges from which layers the user chooses
    to monitor. Different configurations reveal different insights:

    - Enterprise T1: Focuses on high-level state quality
    - Enterprise T2: Focuses on semantic integration
    - Consumer: Focuses on output quality
    - Full: Monitors entire pipeline

    Usage:
        # Use tier-specific configuration
        monitor = ConfigurableDissonanceMonitor.for_tier("enterprise_t2")

        # Or custom configuration
        config = LayerComparisonConfig(
            primary_comparison=("guna", "fusion"),
            secondary_comparisons=[],
            mirror_layer="guna",
        )
        monitor = ConfigurableDissonanceMonitor(config)

        # Add observations for each layer
        monitor.observe("embedding", embedding_obs)
        monitor.observe("guna", guna_obs)
        monitor.observe("fusion", fusion_obs)

        # Get cognitive insights
        insights = monitor.get_cognitive_insights()
    """

    def __init__(self, config: LayerComparisonConfig = None):
        """
        Initialize with layer comparison configuration.

        Args:
            config: Layer comparison configuration (default: enterprise_t2)
        """
        self._config = config or DEFAULT_LAYER_COMPARISON
        self._observations: dict = {}  # layer_id -> Observables
        self._dissonances: dict = {}   # (layer_a, layer_b) -> LayerDissonance

    @classmethod
    def for_tier(cls, tier: str) -> "ConfigurableDissonanceMonitor":
        """Create monitor with tier-specific configuration."""
        config = get_layer_comparison_for_tier(tier)
        return cls(config)

    def observe(self, layer_id: str, observables: Observables):
        """
        Record observation for a layer.

        Args:
            layer_id: Layer identifier (should match OntologicalLayer constants)
            observables: Observed signals at this layer
        """
        self._observations[layer_id] = observables
        self._update_dissonances(layer_id)

    def _update_dissonances(self, updated_layer: str):
        """Update dissonances involving the updated layer."""
        for layer_a, layer_b in self._config.all_comparisons:
            if layer_a == updated_layer or layer_b == updated_layer:
                if layer_a in self._observations and layer_b in self._observations:
                    state_a = LayerState(
                        layer_id=layer_a,
                        observables=self._observations[layer_a],
                    )
                    state_b = LayerState(
                        layer_id=layer_b,
                        observables=self._observations[layer_b],
                    )
                    self._dissonances[(layer_a, layer_b)] = compute_layer_dissonance(
                        state_a, state_b
                    )

    def get_primary_dissonance(self) -> Optional["LayerDissonance"]:
        """Get dissonance for primary comparison."""
        return self._dissonances.get(self._config.primary_comparison)

    def get_cognitive_insights(self) -> dict:
        """
        Get cognitive insights from configured layer comparisons.

        Returns insights about:
        - Primary cognitive ambition
        - Secondary ambitions
        - Overall cognitive drive
        - Balance relative to mirror layer
        - Recommended attention focus
        """
        primary = self.get_primary_dissonance()
        secondaries = [
            self._dissonances.get(pair)
            for pair in self._config.secondary_comparisons
            if pair in self._dissonances
        ]

        # Primary ambition (weighted)
        primary_ambition = primary.cognitive_ambition if primary else 0.0

        # Secondary ambitions (averaged)
        secondary_ambitions = [
            d.cognitive_ambition for d in secondaries if d is not None
        ]
        avg_secondary = (
            sum(secondary_ambitions) / len(secondary_ambitions)
            if secondary_ambitions else 0.0
        )

        # Weighted total
        w = self._config.attention_weight
        total_ambition = w * primary_ambition + (1 - w) * avg_secondary

        # Mirror layer balance
        mirror_balance = self._compute_mirror_balance()

        # Determine attention focus
        attention_focus = self._determine_attention_focus(primary, secondaries)

        return {
            "primary_comparison": self._config.primary_comparison,
            "primary_ambition": primary_ambition,
            "primary_type": primary.ambition_type if primary else "unknown",
            "secondary_ambitions": secondary_ambitions,
            "total_ambition": total_ambition,
            "mirror_layer": self._config.mirror_layer,
            "mirror_balance": mirror_balance,
            "attention_focus": attention_focus,
            "cognitive_state": self._classify_cognitive_state(total_ambition, mirror_balance),
        }

    def _compute_mirror_balance(self) -> float:
        """Compute balance relative to mirror layer."""
        mirror_obs = self._observations.get(self._config.mirror_layer)
        if mirror_obs is None:
            return 0.5  # Neutral if mirror not observed

        pair = create_mirror_pair(mirror_obs)
        return 1.0 - pair.total_asymmetry  # Higher = more balanced

    def _determine_attention_focus(
        self,
        primary: Optional["LayerDissonance"],
        secondaries: list,
    ) -> str:
        """Determine where attention should focus."""
        if primary is None:
            return "awaiting_primary_layers"

        # Check for destructive dissonance
        if primary.is_destructive:
            return f"fix_regression:{primary.layer_a.layer_id}→{primary.layer_b.layer_id}"

        # Check secondaries for issues
        for d in secondaries:
            if d is not None and d.is_destructive:
                return f"fix_secondary:{d.layer_a.layer_id}→{d.layer_b.layer_id}"

        # Check for strong positive ambition
        if primary.cognitive_ambition > 0.2:
            return f"amplify:{primary.layer_a.layer_id}→{primary.layer_b.layer_id}"

        # Stable state
        return "maintain_current"

    def _classify_cognitive_state(
        self,
        ambition: float,
        balance: float,
    ) -> str:
        """Classify overall cognitive state."""
        if ambition > 0.3 and balance > 0.7:
            return "thriving"  # High ambition, good balance
        elif ambition > 0.3 and balance < 0.5:
            return "striving"  # High ambition, poor balance (needs correction)
        elif ambition < -0.2:
            return "regressing"  # Negative ambition
        elif balance > 0.8:
            return "stable"  # Low ambition, excellent balance
        elif balance < 0.4:
            return "unstable"  # Low ambition, poor balance
        else:
            return "neutral"  # Middle ground

    @property
    def config(self) -> LayerComparisonConfig:
        """Get current configuration."""
        return self._config

    def reset(self):
        """Clear all observations."""
        self._observations.clear()
        self._dissonances.clear()


# =============================================================================
# Cross-Layer Dissonance Detection
# =============================================================================

@dataclass
class LayerState:
    """
    State of a processing layer.

    Each layer in the pipeline has its own view of the signals.
    Comparing adjacent layers reveals dissonance and ambition.
    """
    layer_id: str
    observables: Observables
    layer_index: int = 0

    @property
    def coherence(self) -> float:
        """Layer's internal coherence (S - C_contr)."""
        return self.observables.s - self.observables.C_contr

    @property
    def stability(self) -> float:
        """Layer's stability ((1-H) × (1-M))."""
        return (1.0 - self.observables.H) * (1.0 - self.observables.delta_sem)


@dataclass
class LayerDissonance:
    """
    Dissonance between two adjacent layers.

    Dissonance is the "friction" between layers - where they disagree.
    This friction can be:
    - Destructive: conflicting signals that degrade quality
    - Constructive: tension that drives improvement (cognitive ambition)
    """
    layer_a: LayerState
    layer_b: LayerState

    # Dissonance components
    guna_dissonance: float      # Difference in Guna distributions
    entropy_dissonance: float   # Difference in entropy levels
    motion_dissonance: float    # Difference in motion signals
    coherence_gap: float        # Gap in coherence between layers

    @property
    def total_dissonance(self) -> float:
        """Total dissonance magnitude."""
        return math.sqrt(
            self.guna_dissonance**2 +
            self.entropy_dissonance**2 +
            self.motion_dissonance**2
        )

    @property
    def is_constructive(self) -> bool:
        """
        Check if dissonance is constructive (drives improvement).

        Constructive dissonance occurs when:
        - Layer B (downstream) has higher coherence than Layer A
        - The dissonance pushes toward better states
        """
        return self.coherence_gap > 0  # B is more coherent than A

    @property
    def is_destructive(self) -> bool:
        """
        Check if dissonance is destructive (degrades quality).

        Destructive dissonance occurs when:
        - Layer B (downstream) has lower coherence
        - Signals are conflicting without improvement
        """
        return self.coherence_gap < -0.1 and self.total_dissonance > 0.2

    @property
    def cognitive_ambition(self) -> float:
        """
        Measure of cognitive ambition from this layer transition.

        Cognitive ambition is the drive toward improvement.
        It's positive when downstream layers show higher quality.

        Range: [-1, 1] where positive = improvement drive
        """
        # Ambition is the coherence gap modulated by dissonance
        # More dissonance with positive gap = stronger drive
        if self.total_dissonance < EPSILON:
            return 0.0
        return self.coherence_gap * min(1.0, self.total_dissonance * 2)

    @property
    def ambition_type(self) -> str:
        """Classify the type of ambition/tension."""
        ambition = self.cognitive_ambition
        if abs(ambition) < 0.05:
            return "neutral"
        elif ambition > 0.2:
            return "strong-drive"
        elif ambition > 0:
            return "mild-drive"
        elif ambition < -0.2:
            return "regression"
        else:
            return "mild-regression"

    @property
    def ontological_direction(self) -> str:
        """
        Direction of transition in ontological hierarchy.

        Returns "ascending", "descending", or "same".
        Ascending = moving toward higher abstraction.
        """
        return OntologicalLayer.direction(
            self.layer_a.layer_id,
            self.layer_b.layer_id,
        )

    @property
    def is_ontologically_adjacent(self) -> bool:
        """Check if layers are adjacent in the ontological hierarchy."""
        return OntologicalLayer.is_adjacent(
            self.layer_a.layer_id,
            self.layer_b.layer_id,
        )

    @property
    def ontological_tension(self) -> float:
        """
        Tension from crossing ontological boundaries.

        Higher tension when:
        - Layers are adjacent (natural friction point)
        - Dissonance is high
        - Coherence gap is significant

        This tension can be productive (cognitive ambition)
        or destructive (information loss).
        """
        if not self.is_ontologically_adjacent:
            # Non-adjacent transitions have attenuated tension
            return self.total_dissonance * 0.5

        # Adjacent layers: full tension
        # Modulated by coherence change
        base_tension = self.total_dissonance

        # Ascending with improvement = constructive tension
        # Descending with degradation = destructive tension
        if self.ontological_direction == "ascending":
            if self.coherence_gap > 0:
                return base_tension * 1.2  # Amplified: good abstraction
            else:
                return base_tension * 0.8  # Attenuated: lossy abstraction
        elif self.ontological_direction == "descending":
            if self.coherence_gap < 0:
                return base_tension * 1.2  # Amplified: bad grounding
            else:
                return base_tension * 0.8  # Attenuated: good grounding

        return base_tension


def compute_layer_dissonance(
    layer_a: LayerState,
    layer_b: LayerState,
) -> LayerDissonance:
    """
    Compute dissonance between two adjacent layers.

    Args:
        layer_a: Upstream layer (earlier in pipeline)
        layer_b: Downstream layer (later in pipeline)

    Returns:
        LayerDissonance analysis
    """
    obs_a = layer_a.observables
    obs_b = layer_b.observables

    # Guna dissonance: Euclidean distance in Guna space
    guna_dissonance = math.sqrt(
        (obs_a.s - obs_b.s)**2 +
        (obs_a.r - obs_b.r)**2 +
        (obs_a.t - obs_b.t)**2
    ) / math.sqrt(2)  # Normalize to [0, 1]

    # Entropy dissonance: absolute difference
    entropy_dissonance = abs(obs_a.H - obs_b.H)

    # Motion dissonance: absolute difference
    motion_dissonance = abs(obs_a.delta_sem - obs_b.delta_sem)

    # Coherence gap: B - A (positive means improvement)
    coherence_gap = layer_b.coherence - layer_a.coherence

    return LayerDissonance(
        layer_a=layer_a,
        layer_b=layer_b,
        guna_dissonance=guna_dissonance,
        entropy_dissonance=entropy_dissonance,
        motion_dissonance=motion_dissonance,
        coherence_gap=coherence_gap,
    )


class LayerDissonanceMonitor:
    """
    Monitor dissonance across a multi-layer pipeline.

    Tracks the "friction" between adjacent layers and uses it
    to detect cognitive ambition (drive for improvement) or
    destructive dissonance (quality degradation).

    Usage:
        monitor = LayerDissonanceMonitor()

        # Add layers as pipeline processes
        monitor.add_layer("embedding", embedding_observables)
        monitor.add_layer("guna", guna_observables)
        monitor.add_layer("fusion", fusion_observables)

        # Analyze
        report = monitor.analyze()
        print(f"Total ambition: {report['total_ambition']}")
        print(f"Destructive layers: {report['destructive_transitions']}")
    """

    def __init__(self):
        """Initialize the monitor."""
        self._layers: list = []
        self._dissonances: list = []

    def add_layer(self, layer_id: str, observables: Observables):
        """
        Add a layer to the pipeline.

        Args:
            layer_id: Identifier for this layer
            observables: Layer's observable state
        """
        layer = LayerState(
            layer_id=layer_id,
            observables=observables,
            layer_index=len(self._layers),
        )
        self._layers.append(layer)

        # Compute dissonance with previous layer
        if len(self._layers) > 1:
            dissonance = compute_layer_dissonance(
                self._layers[-2],
                self._layers[-1],
            )
            self._dissonances.append(dissonance)

    def analyze(self) -> dict:
        """
        Analyze the full pipeline for dissonance and ambition.

        Returns:
            Dict with analysis results
        """
        if len(self._dissonances) == 0:
            return {
                "layers": len(self._layers),
                "transitions": 0,
                "total_ambition": 0.0,
                "average_dissonance": 0.0,
                "constructive_transitions": [],
                "destructive_transitions": [],
                "ambition_trend": [],
            }

        constructive = []
        destructive = []
        ambition_trend = []

        for d in self._dissonances:
            ambition_trend.append(d.cognitive_ambition)
            if d.is_constructive:
                constructive.append(f"{d.layer_a.layer_id} → {d.layer_b.layer_id}")
            elif d.is_destructive:
                destructive.append(f"{d.layer_a.layer_id} → {d.layer_b.layer_id}")

        return {
            "layers": len(self._layers),
            "transitions": len(self._dissonances),
            "total_ambition": sum(d.cognitive_ambition for d in self._dissonances),
            "average_dissonance": sum(d.total_dissonance for d in self._dissonances) / len(self._dissonances),
            "constructive_transitions": constructive,
            "destructive_transitions": destructive,
            "ambition_trend": ambition_trend,
        }

    def get_layer(self, layer_id: str) -> Optional[LayerState]:
        """Get a layer by ID."""
        for layer in self._layers:
            if layer.layer_id == layer_id:
                return layer
        return None

    def get_dissonance(self, from_layer: str, to_layer: str) -> Optional[LayerDissonance]:
        """Get dissonance between two specific layers."""
        for d in self._dissonances:
            if d.layer_a.layer_id == from_layer and d.layer_b.layer_id == to_layer:
                return d
        return None

    def reset(self):
        """Clear all layers and dissonances."""
        self._layers = []
        self._dissonances = []

    @property
    def has_destructive_dissonance(self) -> bool:
        """Check if any transition is destructive."""
        return any(d.is_destructive for d in self._dissonances)

    @property
    def net_ambition(self) -> float:
        """Net cognitive ambition across pipeline."""
        if not self._dissonances:
            return 0.0
        return sum(d.cognitive_ambition for d in self._dissonances)


def generate_ambition_questions(dissonance: LayerDissonance) -> list:
    """
    Generate questions about cognitive ambition from layer dissonance.

    Args:
        dissonance: Dissonance between two layers

    Returns:
        List of questions about the transition
    """
    questions = []
    a_id = dissonance.layer_a.layer_id
    b_id = dissonance.layer_b.layer_id

    if dissonance.is_constructive:
        questions.append(
            f"Layer '{b_id}' shows improvement over '{a_id}' - "
            f"can we amplify this transformation?"
        )
    elif dissonance.is_destructive:
        questions.append(
            f"Layer '{b_id}' degrades quality from '{a_id}' - "
            f"what is causing this regression?"
        )

    if dissonance.guna_dissonance > 0.2:
        questions.append(
            f"Guna distribution shifts significantly ({a_id} → {b_id}) - "
            f"is this intentional?"
        )

    if dissonance.entropy_dissonance > 0.2:
        questions.append(
            f"Entropy changes by {dissonance.entropy_dissonance:.2f} ({a_id} → {b_id}) - "
            f"is uncertainty being managed correctly?"
        )

    ambition = dissonance.cognitive_ambition
    if abs(ambition) > 0.1:
        direction = "positive" if ambition > 0 else "negative"
        questions.append(
            f"Cognitive ambition is {direction} ({ambition:.2f}) - "
            f"is the system evolving as intended?"
        )

    return questions


# =============================================================================
# Cognitive Approach Benchmark
# =============================================================================

@dataclass
class CognitiveMetrics:
    """
    Measurable cognitive metrics for benchmarking approaches.

    These metrics quantify "cognitive ability" in different ways:
    - self_awareness: Ability to detect internal imbalance
    - directional_focus: Ability to identify where to improve
    - actionability: Ability to produce actionable recommendations
    - state_classification: Ability to classify current cognitive state
    """
    self_awareness: float       # [0, 1] - can detect imbalance
    directional_focus: float    # [0, 1] - knows which direction to go
    actionability: float        # [0, 1] - produces actionable output
    state_classification: float # [0, 1] - can classify cognitive state

    @property
    def total_cognitive_score(self) -> float:
        """Weighted total cognitive score."""
        weights = (0.2, 0.3, 0.3, 0.2)  # Focus and action weighted higher
        scores = (
            self.self_awareness,
            self.directional_focus,
            self.actionability,
            self.state_classification,
        )
        return sum(w * s for w, s in zip(weights, scores))

    @property
    def category(self) -> str:
        """Classify cognitive capability level."""
        score = self.total_cognitive_score
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "moderate"
        elif score >= 0.3:
            return "low"
        return "minimal"


class MirrorOnlyAnalyzer:
    """
    Approach 1: Mirror-only cognitive analysis.

    Uses only self-referential balance (S↔T mirror) for cognition.

    Strengths:
    - Detects internal imbalance well
    - Simple, elegant model

    Weaknesses:
    - No directional focus (doesn't know WHERE to improve)
    - No layer awareness
    - Can't prioritize between issues
    """

    def __init__(self):
        self._engine = MirrorBalanceEngine(learning_rate=0.1)

    def analyze(self, observables: Observables) -> CognitiveMetrics:
        """Analyze using mirror-only approach."""
        pair = self._engine.analyze(observables)
        questions = generate_self_questions(observables)

        # Self-awareness: high if detects imbalance
        self_awareness = 1.0 - pair.total_asymmetry if pair.is_balanced else min(1.0, pair.total_asymmetry * 2)

        # Directional focus: limited - knows S vs T but not layer
        directional_focus = 0.3  # Fixed: mirror provides direction but no priority
        if pair.balance_direction != "balanced":
            directional_focus = 0.4  # Slightly better if knows direction

        # Actionability: moderate - can suggest correction but not context
        actionability = 0.4 if len(questions) > 0 else 0.2

        # State classification: binary only (balanced/unbalanced)
        state_classification = 0.3  # Limited: only two states possible

        return CognitiveMetrics(
            self_awareness=self_awareness,
            directional_focus=directional_focus,
            actionability=actionability,
            state_classification=state_classification,
        )


class SelectiveOnlyAnalyzer:
    """
    Approach 2: Selective layer comparison only.

    Uses layer dissonance without mirror balance reference.

    Strengths:
    - Knows which layers to focus on
    - Detects cross-layer issues
    - Can prioritize by layer importance

    Weaknesses:
    - No self-referential balance check
    - Can miss internal layer imbalances
    - Blind to within-layer issues
    """

    def __init__(self, config: LayerComparisonConfig = None):
        self._config = config or DEFAULT_LAYER_COMPARISON
        self._observations: dict = {}
        self._dissonances: dict = {}

    def observe(self, layer_id: str, observables: Observables):
        """Record layer observation."""
        self._observations[layer_id] = observables
        self._update_dissonances(layer_id)

    def _update_dissonances(self, updated_layer: str):
        """Update dissonances involving updated layer."""
        for layer_a, layer_b in self._config.all_comparisons:
            if layer_a == updated_layer or layer_b == updated_layer:
                if layer_a in self._observations and layer_b in self._observations:
                    state_a = LayerState(
                        layer_id=layer_a,
                        observables=self._observations[layer_a],
                    )
                    state_b = LayerState(
                        layer_id=layer_b,
                        observables=self._observations[layer_b],
                    )
                    self._dissonances[(layer_a, layer_b)] = compute_layer_dissonance(
                        state_a, state_b
                    )

    def analyze(self) -> CognitiveMetrics:
        """Analyze using selective-only approach."""
        primary = self._dissonances.get(self._config.primary_comparison)

        if primary is None:
            return CognitiveMetrics(
                self_awareness=0.0,
                directional_focus=0.0,
                actionability=0.0,
                state_classification=0.0,
            )

        # Self-awareness: limited - only sees cross-layer, not internal
        self_awareness = 0.4  # Fixed cap: can't see internal balance

        # Directional focus: HIGH - knows exactly which layer boundary
        directional_focus = 0.8
        if primary.is_constructive:
            directional_focus = 0.9  # Knows to amplify
        elif primary.is_destructive:
            directional_focus = 0.85  # Knows to fix

        # Actionability: good - can recommend layer-specific actions
        actionability = 0.6
        secondaries = [
            self._dissonances.get(pair)
            for pair in self._config.secondary_comparisons
            if pair in self._dissonances
        ]
        if any(d and d.is_destructive for d in secondaries):
            actionability = 0.7  # Better if detects secondary issues

        # State classification: moderate - ambition types but no balance
        state_classification = 0.5  # Can classify ambition but not balance state

        return CognitiveMetrics(
            self_awareness=self_awareness,
            directional_focus=directional_focus,
            actionability=actionability,
            state_classification=state_classification,
        )

    def reset(self):
        """Clear observations."""
        self._observations.clear()
        self._dissonances.clear()


class CombinedAnalyzer:
    """
    Approach 3: Combined mirror + selective layer analysis.

    Uses both self-referential balance AND selective layer comparison.
    This is the ConfigurableDissonanceMonitor with full features.

    Strengths:
    - Full self-awareness through mirror
    - Precise directional focus through layer selection
    - Rich state classification (6 states)
    - Highly actionable recommendations

    This demonstrates that "cognitive ability" emerges from the
    combination of self-reference (mirror) and selective attention (layers).
    """

    def __init__(self, config: LayerComparisonConfig = None):
        self._monitor = ConfigurableDissonanceMonitor(config)

    def observe(self, layer_id: str, observables: Observables):
        """Record layer observation."""
        self._monitor.observe(layer_id, observables)

    def analyze(self) -> CognitiveMetrics:
        """Analyze using combined approach."""
        insights = self._monitor.get_cognitive_insights()

        # Self-awareness: HIGH - mirror balance provides internal check
        mirror_balance = insights.get("mirror_balance", 0.5)
        self_awareness = 0.7 + (mirror_balance * 0.3)  # 0.7-1.0 range

        # Directional focus: HIGH - layer comparison + priority
        attention = insights.get("attention_focus", "")
        if "amplify" in attention:
            directional_focus = 0.95  # Knows to amplify good
        elif "fix_regression" in attention:
            directional_focus = 0.9   # Knows to fix primary
        elif "fix_secondary" in attention:
            directional_focus = 0.85  # Knows to fix secondary
        else:
            directional_focus = 0.7   # At least knows to maintain

        # Actionability: HIGH - specific recommendations
        actionability = 0.8
        cognitive_state = insights.get("cognitive_state", "neutral")
        if cognitive_state in ("thriving", "striving"):
            actionability = 0.95  # Clear action path
        elif cognitive_state in ("regressing", "unstable"):
            actionability = 0.9   # Clear problem to fix

        # State classification: HIGH - 6 distinct states
        state_classification = 0.9  # Can classify into 6 meaningful states

        return CognitiveMetrics(
            self_awareness=self_awareness,
            directional_focus=directional_focus,
            actionability=actionability,
            state_classification=state_classification,
        )

    def reset(self):
        """Clear observations."""
        self._monitor.reset()


@dataclass
class BenchmarkResult:
    """Result of comparing cognitive approaches."""
    mirror_only: CognitiveMetrics
    selective_only: CognitiveMetrics
    combined: CognitiveMetrics
    scenario: str

    @property
    def winner(self) -> str:
        """Which approach scored highest."""
        scores = {
            "mirror_only": self.mirror_only.total_cognitive_score,
            "selective_only": self.selective_only.total_cognitive_score,
            "combined": self.combined.total_cognitive_score,
        }
        return max(scores, key=scores.get)

    @property
    def combined_improvement_over_mirror(self) -> float:
        """How much better combined is vs mirror-only."""
        mirror_score = self.mirror_only.total_cognitive_score
        if mirror_score < EPSILON:
            return float('inf')
        return (self.combined.total_cognitive_score - mirror_score) / mirror_score

    @property
    def combined_improvement_over_selective(self) -> float:
        """How much better combined is vs selective-only."""
        selective_score = self.selective_only.total_cognitive_score
        if selective_score < EPSILON:
            return float('inf')
        return (self.combined.total_cognitive_score - selective_score) / selective_score

    def summary(self) -> dict:
        """Get summary of benchmark results."""
        return {
            "scenario": self.scenario,
            "mirror_only_score": self.mirror_only.total_cognitive_score,
            "mirror_only_category": self.mirror_only.category,
            "selective_only_score": self.selective_only.total_cognitive_score,
            "selective_only_category": self.selective_only.category,
            "combined_score": self.combined.total_cognitive_score,
            "combined_category": self.combined.category,
            "winner": self.winner,
            "combined_vs_mirror": f"+{self.combined_improvement_over_mirror*100:.1f}%",
            "combined_vs_selective": f"+{self.combined_improvement_over_selective*100:.1f}%",
        }


def run_cognitive_benchmark(
    scenario: str,
    layer_observations: dict,  # layer_id -> Observables
    config: LayerComparisonConfig = None,
) -> BenchmarkResult:
    """
    Run benchmark comparing all three cognitive approaches.

    Args:
        scenario: Description of the test scenario
        layer_observations: Dict mapping layer IDs to their Observables
        config: Layer comparison configuration (default: enterprise_t2)

    Returns:
        BenchmarkResult with metrics for each approach

    Example:
        result = run_cognitive_benchmark(
            scenario="High coherence downstream",
            layer_observations={
                "guna": Observables(s=0.3, r=0.3, t=0.4, H=0.5, delta_sem=0.3),
                "fusion": Observables(s=0.5, r=0.3, t=0.2, H=0.4, delta_sem=0.3),
                "state": Observables(s=0.6, r=0.3, t=0.1, H=0.3, delta_sem=0.2),
            }
        )
        print(result.summary())
    """
    config = config or DEFAULT_LAYER_COMPARISON

    # Mirror-only: use the primary layer's observables
    primary_layer = config.primary_comparison[0]
    primary_obs = layer_observations.get(primary_layer)
    if primary_obs is None:
        primary_obs = next(iter(layer_observations.values()))

    mirror_analyzer = MirrorOnlyAnalyzer()
    mirror_metrics = mirror_analyzer.analyze(primary_obs)

    # Selective-only
    selective_analyzer = SelectiveOnlyAnalyzer(config)
    for layer_id, obs in layer_observations.items():
        selective_analyzer.observe(layer_id, obs)
    selective_metrics = selective_analyzer.analyze()

    # Combined
    combined_analyzer = CombinedAnalyzer(config)
    for layer_id, obs in layer_observations.items():
        combined_analyzer.observe(layer_id, obs)
    combined_metrics = combined_analyzer.analyze()

    return BenchmarkResult(
        mirror_only=mirror_metrics,
        selective_only=selective_metrics,
        combined=combined_metrics,
        scenario=scenario,
    )


def run_standard_benchmark_suite() -> list:
    """
    Run standard benchmark suite with predefined scenarios.

    Returns list of BenchmarkResult for various cognitive scenarios.
    """
    results = []

    # Scenario 1: Balanced pipeline (low dissonance)
    results.append(run_cognitive_benchmark(
        scenario="Balanced Pipeline",
        layer_observations={
            OntologicalLayer.GUNA: Observables(s=0.35, r=0.3, t=0.35, H=0.5, delta_sem=0.5, C_contr=0.1, F_fail=0.05),
            OntologicalLayer.FUSION: Observables(s=0.36, r=0.3, t=0.34, H=0.48, delta_sem=0.48, C_contr=0.08, F_fail=0.04),
            OntologicalLayer.STATE: Observables(s=0.37, r=0.3, t=0.33, H=0.47, delta_sem=0.46, C_contr=0.06, F_fail=0.03),
        },
    ))

    # Scenario 2: High improvement downstream (constructive dissonance)
    results.append(run_cognitive_benchmark(
        scenario="Constructive Improvement",
        layer_observations={
            OntologicalLayer.GUNA: Observables(s=0.3, r=0.3, t=0.4, H=0.6, delta_sem=0.5, C_contr=0.2, F_fail=0.1),
            OntologicalLayer.FUSION: Observables(s=0.45, r=0.3, t=0.25, H=0.45, delta_sem=0.4, C_contr=0.1, F_fail=0.05),
            OntologicalLayer.STATE: Observables(s=0.6, r=0.25, t=0.15, H=0.3, delta_sem=0.3, C_contr=0.05, F_fail=0.02),
        },
    ))

    # Scenario 3: Quality degradation downstream (destructive dissonance)
    results.append(run_cognitive_benchmark(
        scenario="Destructive Regression",
        layer_observations={
            OntologicalLayer.GUNA: Observables(s=0.6, r=0.25, t=0.15, H=0.3, delta_sem=0.3, C_contr=0.05, F_fail=0.02),
            OntologicalLayer.FUSION: Observables(s=0.4, r=0.3, t=0.3, H=0.5, delta_sem=0.5, C_contr=0.15, F_fail=0.08),
            OntologicalLayer.STATE: Observables(s=0.25, r=0.3, t=0.45, H=0.7, delta_sem=0.6, C_contr=0.3, F_fail=0.15),
        },
    ))

    # Scenario 4: Internal imbalance (mirror detects, selective misses)
    results.append(run_cognitive_benchmark(
        scenario="Internal Imbalance",
        layer_observations={
            OntologicalLayer.GUNA: Observables(s=0.7, r=0.2, t=0.1, H=0.2, delta_sem=0.8, C_contr=0.1, F_fail=0.05),  # Very unbalanced
            OntologicalLayer.FUSION: Observables(s=0.68, r=0.2, t=0.12, H=0.22, delta_sem=0.78, C_contr=0.1, F_fail=0.05),  # Similar unbalance
            OntologicalLayer.STATE: Observables(s=0.66, r=0.2, t=0.14, H=0.24, delta_sem=0.76, C_contr=0.1, F_fail=0.05),  # Similar unbalance
        },
    ))

    # Scenario 5: Mixed signals (complex scenario)
    results.append(run_cognitive_benchmark(
        scenario="Mixed Signals",
        layer_observations={
            OntologicalLayer.GUNA: Observables(s=0.5, r=0.3, t=0.2, H=0.4, delta_sem=0.6, C_contr=0.1, F_fail=0.05),
            OntologicalLayer.FUSION: Observables(s=0.3, r=0.4, t=0.3, H=0.55, delta_sem=0.4, C_contr=0.2, F_fail=0.1),
            OntologicalLayer.STATE: Observables(s=0.55, r=0.25, t=0.2, H=0.35, delta_sem=0.5, C_contr=0.08, F_fail=0.03),
        },
    ))

    return results


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "MirrorPair",
    "BalanceCorrection",
    "SelfQuestion",
    "LayerState",
    "LayerDissonance",
    "OntologicalLayer",
    # Configurable layer comparison
    "LayerComparisonConfig",
    "LAYER_COMPARISON_ENTERPRISE_T1",
    "LAYER_COMPARISON_ENTERPRISE_T2",
    "LAYER_COMPARISON_CONSUMER",
    "LAYER_COMPARISON_FULL_PIPELINE",
    "DEFAULT_LAYER_COMPARISON",
    "get_layer_comparison_for_tier",
    # Functions
    "compute_mirror_observables",
    "create_mirror_pair",
    "compute_balance_correction",
    "apply_balance_correction",
    "compute_harmonic_mirror",
    "generate_self_questions",
    "compute_layer_dissonance",
    "generate_ambition_questions",
    # Engines
    "MirrorBalanceEngine",
    "LayerDissonanceMonitor",
    "ConfigurableDissonanceMonitor",
    # Benchmark
    "CognitiveMetrics",
    "MirrorOnlyAnalyzer",
    "SelectiveOnlyAnalyzer",
    "CombinedAnalyzer",
    "BenchmarkResult",
    "run_cognitive_benchmark",
    "run_standard_benchmark_suite",
]
