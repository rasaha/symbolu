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
]
