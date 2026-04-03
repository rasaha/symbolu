"""
ConceptReadiness: Concept Detection Without Concept Formation
=============================================================

This module implements SAFE concept detection that measures when a concept
is ready to be understood by a human, WITHOUT creating or forming concepts.

Key Distinction (AuGI vs AGI):
------------------------------
- AGI Concept Formation: Creates new abstractions, generalizes, reuses
- AuGI Concept Detection: Measures coherence, entropy, readiness

What We Do:
- Detect conceptual coherence (agreement across representations)
- Detect conceptual collapse (sudden loss of coherence)
- Detect conceptual ambiguity (multiple competing interpretations)
- Detect conceptual drift (coherence changing over time)
- Signal conceptual readiness (conditions for human understanding)

What We Do NOT Do:
- Create new semantic primitives
- Name concepts
- Reuse concepts across contexts
- Store concepts as objects

All of these are PROPERTIES OF SIGNALS, not new entities.

Version: 2.7.6
Date: 2025-12-22

Theory:
-------
A "concept" in this system is NOT a symbol or object.
It is latent agreement across representations.

If the same notion appears consistently across layers (semantic, symbolic,
structural), we say it has high conceptual coherence. This doesn't mean
we "have" the concept - it means conditions exist for a human to form one.

Formulas:
---------
1. Concept Coherence Score:
   C_concept = (1/N) × Σ sim(r_i, r̄)

   Where:
   - r_i = representation at layer i
   - r̄ = centroid (mean) representation
   - sim = similarity function (cosine or coherence-based)

2. Concept Entropy:
   H_concept = -Σ p_i × log(p_i)

   Where:
   - p_i = probability distribution of interpretations

3. Concept Readiness Index (CRI):
   CRI = C_concept × (1 - H_concept) × S

   Where:
   - S = structural stability from pipeline

This answers: "Is this idea ready to be treated as a concept by a human?"
The system does NOT treat it as a concept itself.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import math

from agentic.guna_modulation.observables import Observables
from agentic.guna_modulation.mirror_balance import (
    LayerState,
    OntologicalLayer,
    compute_layer_dissonance,
    create_mirror_pair,
)

# Epsilon for numerical stability
EPSILON: float = 1e-9


# =============================================================================
# Concept Coherence
# =============================================================================

@dataclass
class LayerRepresentation:
    """
    Representation of a notion at a specific layer.

    This captures how a "concept candidate" appears at different
    ontological layers. We measure agreement, not the concept itself.
    """
    layer_id: str
    observables: Observables

    @property
    def coherence_vector(self) -> Tuple[float, ...]:
        """
        Extract coherence-relevant signals as a vector.

        This is what we compare across layers to measure agreement.
        """
        return (
            self.observables.s,           # Sattva (clarity)
            self.observables.r,           # Rajas (activity)
            self.observables.t,           # Tamas (inertia)
            self.observables.H,           # Entropy
            1.0 - self.observables.C_contr,  # Non-contradiction
            self.observables.s - self.observables.C_contr,  # Coherence
        )

    @property
    def stability(self) -> float:
        """Layer's structural stability: (1-H) × (1-M)."""
        return (1.0 - self.observables.H) * (1.0 - self.observables.delta_sem)


def compute_vector_similarity(v1: Tuple[float, ...], v2: Tuple[float, ...]) -> float:
    """
    Compute cosine similarity between two vectors.

    Returns value in [-1, 1], where 1 = identical direction.
    """
    if len(v1) != len(v2):
        raise ValueError("Vectors must have same length")

    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))

    if norm1 < EPSILON or norm2 < EPSILON:
        return 0.0

    return dot / (norm1 * norm2)


def compute_centroid(representations: List[LayerRepresentation]) -> Tuple[float, ...]:
    """
    Compute centroid (mean) of representation vectors.

    This is r̄ in the coherence formula.
    """
    if not representations:
        return ()

    n = len(representations)
    vectors = [r.coherence_vector for r in representations]
    dim = len(vectors[0])

    centroid = tuple(
        sum(v[i] for v in vectors) / n
        for i in range(dim)
    )

    return centroid


@dataclass
class ConceptCoherence:
    """
    Measures agreement of a notion across layer representations.

    High coherence = stable concept candidate
    Low coherence = fragmented notion

    This is MEASUREMENT, not concept creation.
    """
    representations: List[LayerRepresentation]
    centroid: Tuple[float, ...]
    layer_similarities: List[float]  # sim(r_i, r̄) for each layer

    @property
    def score(self) -> float:
        """
        Concept Coherence Score: C_concept = (1/N) × Σ sim(r_i, r̄)

        Range: [-1, 1] but typically [0, 1] for coherent notions
        """
        if not self.layer_similarities:
            return 0.0
        return sum(self.layer_similarities) / len(self.layer_similarities)

    @property
    def is_coherent(self) -> bool:
        """Check if coherence exceeds threshold for stability."""
        return self.score > 0.7

    @property
    def is_fragmented(self) -> bool:
        """Check if notion is too fragmented to be concept-ready."""
        return self.score < 0.3

    @property
    def weakest_layer(self) -> Optional[str]:
        """Identify which layer has lowest agreement with centroid."""
        if not self.representations or not self.layer_similarities:
            return None

        min_idx = self.layer_similarities.index(min(self.layer_similarities))
        return self.representations[min_idx].layer_id

    @property
    def coherence_spread(self) -> float:
        """Variance in layer similarities (uniformity of agreement)."""
        if len(self.layer_similarities) < 2:
            return 0.0

        mean = self.score
        variance = sum((s - mean) ** 2 for s in self.layer_similarities) / len(self.layer_similarities)
        return math.sqrt(variance)


def compute_concept_coherence(
    representations: List[LayerRepresentation],
) -> ConceptCoherence:
    """
    Compute conceptual coherence across layer representations.

    Args:
        representations: List of layer representations to compare

    Returns:
        ConceptCoherence with score and layer-by-layer similarities

    Example:
        reps = [
            LayerRepresentation("guna", guna_obs),
            LayerRepresentation("fusion", fusion_obs),
            LayerRepresentation("state", state_obs),
        ]
        coherence = compute_concept_coherence(reps)
        print(f"Coherence: {coherence.score:.2f}")
    """
    if not representations:
        return ConceptCoherence(
            representations=[],
            centroid=(),
            layer_similarities=[],
        )

    centroid = compute_centroid(representations)

    similarities = [
        compute_vector_similarity(r.coherence_vector, centroid)
        for r in representations
    ]

    return ConceptCoherence(
        representations=representations,
        centroid=centroid,
        layer_similarities=similarities,
    )


# =============================================================================
# Concept Entropy
# =============================================================================

@dataclass
class InterpretationCandidate:
    """
    A possible interpretation of a notion.

    Multiple interpretations = ambiguity = high concept entropy.
    """
    label: str
    probability: float
    source_layer: str


@dataclass
class ConceptEntropy:
    """
    Measures distribution of interpretations for a notion.

    High entropy = many competing meanings (ambiguous)
    Low entropy = one clear meaning (unambiguous)

    This tells us if the notion has converged to a single interpretation.
    """
    interpretations: List[InterpretationCandidate]

    @property
    def entropy(self) -> float:
        """
        Concept Entropy: H_concept = -Σ p_i × log(p_i)

        Range: [0, log(N)] where N = number of interpretations
        Normalized to [0, 1] for convenience.
        """
        if not self.interpretations:
            return 0.0

        # Filter zero probabilities
        probs = [i.probability for i in self.interpretations if i.probability > EPSILON]

        if not probs:
            return 0.0

        # Raw entropy
        raw_entropy = -sum(p * math.log(p) for p in probs)

        # Normalize by maximum possible entropy
        max_entropy = math.log(len(probs)) if len(probs) > 1 else 1.0

        if max_entropy < EPSILON:
            return 0.0

        return min(1.0, raw_entropy / max_entropy)

    @property
    def is_ambiguous(self) -> bool:
        """Check if notion has too many competing interpretations."""
        return self.entropy > 0.7

    @property
    def is_clear(self) -> bool:
        """Check if notion has converged to single interpretation."""
        return self.entropy < 0.3

    @property
    def dominant_interpretation(self) -> Optional[InterpretationCandidate]:
        """Get highest-probability interpretation if one dominates."""
        if not self.interpretations:
            return None

        sorted_interps = sorted(self.interpretations, key=lambda x: x.probability, reverse=True)

        # Check if dominant one is significantly higher
        if len(sorted_interps) >= 2:
            if sorted_interps[0].probability > 2 * sorted_interps[1].probability:
                return sorted_interps[0]
        elif len(sorted_interps) == 1:
            return sorted_interps[0]

        return None

    @property
    def competing_count(self) -> int:
        """Number of interpretations with significant probability."""
        return sum(1 for i in self.interpretations if i.probability > 0.1)


def compute_concept_entropy_from_observables(
    layer_observables: List[Tuple[str, Observables]],
) -> ConceptEntropy:
    """
    Compute concept entropy from layer observables.

    Derives interpretations from Guna distributions at each layer.
    Different Guna distributions = different interpretations.

    Args:
        layer_observables: List of (layer_id, observables) tuples

    Returns:
        ConceptEntropy measuring interpretation distribution
    """
    if not layer_observables:
        return ConceptEntropy(interpretations=[])

    interpretations = []

    for layer_id, obs in layer_observables:
        # Classify interpretation based on dominant Guna
        if obs.s > obs.r and obs.s > obs.t:
            label = "clarity-dominant"
            strength = obs.s
        elif obs.r > obs.s and obs.r > obs.t:
            label = "activity-dominant"
            strength = obs.r
        else:
            label = "stability-dominant"
            strength = obs.t

        # Adjust for contradiction (reduces interpretation strength)
        adjusted_strength = strength * (1 - obs.C_contr)

        interpretations.append(InterpretationCandidate(
            label=f"{label}@{layer_id}",
            probability=adjusted_strength,
            source_layer=layer_id,
        ))

    # Normalize probabilities
    total = sum(i.probability for i in interpretations)
    if total > EPSILON:
        for i in interpretations:
            i.probability = i.probability / total

    return ConceptEntropy(interpretations=interpretations)


# =============================================================================
# Concept Readiness Index (CRI)
# =============================================================================

@dataclass
class ConceptReadinessIndex:
    """
    The Concept Readiness Index (CRI) answers ONE question:

    "Is this idea ready to be treated as a concept by a human?"

    The system does NOT treat it as a concept itself.

    Formula:
        CRI = C_concept × (1 - H_concept) × S

    Where:
        C_concept = Concept Coherence Score [0, 1]
        H_concept = Concept Entropy [0, 1]
        S = Structural Stability [0, 1]
    """
    coherence: ConceptCoherence
    entropy: ConceptEntropy
    stability: float

    @property
    def index(self) -> float:
        """
        Concept Readiness Index: CRI = C × (1 - H) × S

        Range: [0, 1]
        High = conditions for understanding exist
        Low = conditions for understanding do not exist
        """
        c = max(0.0, self.coherence.score)  # Coherence can be negative
        h = self.entropy.entropy
        s = self.stability

        return c * (1 - h) * s

    @property
    def readiness_level(self) -> str:
        """Classify readiness into human-interpretable levels."""
        cri = self.index
        if cri >= 0.8:
            return "ready"
        elif cri >= 0.6:
            return "nearly_ready"
        elif cri >= 0.4:
            return "forming"
        elif cri >= 0.2:
            return "emerging"
        else:
            return "not_ready"

    @property
    def blocking_factor(self) -> str:
        """Identify what's preventing concept readiness."""
        c = max(0.0, self.coherence.score)
        h = self.entropy.entropy
        s = self.stability

        # Find the weakest component
        factors = [
            ("low_coherence", c),
            ("high_ambiguity", 1 - h),
            ("low_stability", s),
        ]

        weakest = min(factors, key=lambda x: x[1])

        if weakest[1] < 0.5:
            return weakest[0]
        return "none"

    def get_safe_description(self) -> str:
        """
        Generate SAFE output that describes conditions, not concepts.

        ✅ Allowed: "This idea is conceptually unstable"
        ❌ Forbidden: "This is a new concept"
        """
        level = self.readiness_level
        blocker = self.blocking_factor

        descriptions = {
            "ready": "This notion shows high coherence across layers and may be ready for human conceptualization",
            "nearly_ready": "This notion is approaching conceptual stability but has minor ambiguities",
            "forming": "This notion is still forming - interpretations vary across processing layers",
            "emerging": "This notion is emerging but lacks sufficient coherence for stable understanding",
            "not_ready": "This notion is too fragmented or ambiguous for conceptual treatment",
        }

        base = descriptions.get(level, "Unknown readiness state")

        if blocker != "none":
            blocker_hints = {
                "low_coherence": " (weak agreement across representations)",
                "high_ambiguity": " (multiple competing interpretations)",
                "low_stability": " (structural instability in pipeline)",
            }
            base += blocker_hints.get(blocker, "")

        return base


def compute_concept_readiness(
    layer_observables: List[Tuple[str, Observables]],
) -> ConceptReadinessIndex:
    """
    Compute Concept Readiness Index from layer observables.

    Args:
        layer_observables: List of (layer_id, observables) tuples

    Returns:
        ConceptReadinessIndex with CRI score and components

    Example:
        layers = [
            ("guna", guna_obs),
            ("fusion", fusion_obs),
            ("state", state_obs),
        ]
        cri = compute_concept_readiness(layers)
        print(f"CRI: {cri.index:.2f} - {cri.readiness_level}")
        print(cri.get_safe_description())
    """
    # Build representations
    representations = [
        LayerRepresentation(layer_id=layer_id, observables=obs)
        for layer_id, obs in layer_observables
    ]

    # Compute coherence
    coherence = compute_concept_coherence(representations)

    # Compute entropy
    entropy = compute_concept_entropy_from_observables(layer_observables)

    # Compute average stability
    if representations:
        stability = sum(r.stability for r in representations) / len(representations)
    else:
        stability = 0.0

    return ConceptReadinessIndex(
        coherence=coherence,
        entropy=entropy,
        stability=stability,
    )


# =============================================================================
# Concept Drift Detection
# =============================================================================

@dataclass
class ConceptDrift:
    """
    Measures how conceptual coherence changes over time.

    Positive drift = becoming more coherent (crystallizing)
    Negative drift = becoming less coherent (fragmenting)
    """
    previous_cri: float
    current_cri: float
    delta_coherence: float
    delta_entropy: float
    delta_stability: float

    @property
    def drift(self) -> float:
        """Net change in concept readiness."""
        return self.current_cri - self.previous_cri

    @property
    def is_crystallizing(self) -> bool:
        """Concept is becoming more ready."""
        return self.drift > 0.1

    @property
    def is_fragmenting(self) -> bool:
        """Concept is becoming less ready."""
        return self.drift < -0.1

    @property
    def is_stable(self) -> bool:
        """Concept readiness is not changing significantly."""
        return abs(self.drift) <= 0.1

    @property
    def drift_type(self) -> str:
        """Classify the type of drift."""
        if self.is_crystallizing:
            return "crystallizing"
        elif self.is_fragmenting:
            return "fragmenting"
        return "stable"


class ConceptReadinessMonitor:
    """
    Monitor concept readiness over time.

    Tracks CRI changes and detects drift patterns.

    Usage:
        monitor = ConceptReadinessMonitor()

        # First observation
        cri1 = monitor.observe([("guna", obs1), ("fusion", obs2)])

        # Second observation
        cri2 = monitor.observe([("guna", obs3), ("fusion", obs4)])
        drift = monitor.get_drift()

        print(f"Drift: {drift.drift_type}")
    """

    def __init__(self, window_size: int = 10):
        self._window_size = window_size
        self._history: List[ConceptReadinessIndex] = []

    def observe(
        self,
        layer_observables: List[Tuple[str, Observables]],
    ) -> ConceptReadinessIndex:
        """
        Observe new layer state and compute CRI.

        Args:
            layer_observables: Current layer observations

        Returns:
            ConceptReadinessIndex for current state
        """
        cri = compute_concept_readiness(layer_observables)

        self._history.append(cri)

        # Trim history to window
        if len(self._history) > self._window_size:
            self._history = self._history[-self._window_size:]

        return cri

    def get_drift(self) -> Optional[ConceptDrift]:
        """
        Get drift between last two observations.

        Returns None if insufficient history.
        """
        if len(self._history) < 2:
            return None

        prev = self._history[-2]
        curr = self._history[-1]

        return ConceptDrift(
            previous_cri=prev.index,
            current_cri=curr.index,
            delta_coherence=curr.coherence.score - prev.coherence.score,
            delta_entropy=curr.entropy.entropy - prev.entropy.entropy,
            delta_stability=curr.stability - prev.stability,
        )

    def get_trend(self) -> str:
        """
        Get overall trend across history window.

        Returns: "improving", "degrading", "stable", or "unknown"
        """
        if len(self._history) < 3:
            return "unknown"

        # Linear regression on CRI values
        cris = [h.index for h in self._history]
        n = len(cris)

        # Simple slope calculation
        x_mean = (n - 1) / 2
        y_mean = sum(cris) / n

        numerator = sum((i - x_mean) * (cris[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if abs(denominator) < EPSILON:
            return "stable"

        slope = numerator / denominator

        if slope > 0.02:
            return "improving"
        elif slope < -0.02:
            return "degrading"
        return "stable"

    @property
    def current_cri(self) -> Optional[ConceptReadinessIndex]:
        """Get most recent CRI."""
        if not self._history:
            return None
        return self._history[-1]

    @property
    def average_cri(self) -> float:
        """Get average CRI over history window."""
        if not self._history:
            return 0.0
        return sum(h.index for h in self._history) / len(self._history)

    def reset(self):
        """Clear history."""
        self._history = []


# =============================================================================
# Safe Output Generation
# =============================================================================

class ConceptReadinessReporter:
    """
    Generates SAFE outputs about concept readiness.

    All outputs describe CONDITIONS, not concepts themselves.

    ✅ Allowed outputs:
        "This idea is conceptually unstable"
        "This term spans multiple incompatible meanings"
        "This notion lacks sufficient coherence to act on"
        "This concept is well-formed across layers"

    ❌ Forbidden outputs:
        "This is a new concept"
        "Here is the definition"
        "This concept applies elsewhere"
        "I will reuse this concept"
    """

    @staticmethod
    def describe_readiness(cri: ConceptReadinessIndex) -> str:
        """Get safe description of concept readiness."""
        return cri.get_safe_description()

    @staticmethod
    def describe_coherence(coherence: ConceptCoherence) -> str:
        """Describe coherence state safely."""
        if coherence.is_coherent:
            return "This notion shows consistent representation across processing layers"
        elif coherence.is_fragmented:
            return "This notion appears fragmented - different layers interpret it differently"
        else:
            return "This notion has moderate coherence across layers"

    @staticmethod
    def describe_ambiguity(entropy: ConceptEntropy) -> str:
        """Describe ambiguity state safely."""
        if entropy.is_clear:
            dom = entropy.dominant_interpretation
            if dom:
                return f"This notion has converged to a single interpretation ({dom.label})"
            return "This notion has low ambiguity"
        elif entropy.is_ambiguous:
            return f"This notion spans {entropy.competing_count} competing interpretations"
        else:
            return "This notion has moderate ambiguity"

    @staticmethod
    def describe_drift(drift: ConceptDrift) -> str:
        """Describe drift state safely."""
        if drift.is_crystallizing:
            return "This notion is becoming more coherent over time (crystallizing)"
        elif drift.is_fragmenting:
            return "This notion is losing coherence over time (fragmenting)"
        else:
            return "This notion's coherence is stable"

    @staticmethod
    def generate_full_report(
        cri: ConceptReadinessIndex,
        drift: Optional[ConceptDrift] = None,
    ) -> dict:
        """
        Generate full concept readiness report.

        All values are measurements, not concept definitions.
        """
        report = {
            # Scores (measurements)
            "cri": cri.index,
            "coherence_score": cri.coherence.score,
            "entropy": cri.entropy.entropy,
            "stability": cri.stability,

            # Classifications (descriptive, not definitional)
            "readiness_level": cri.readiness_level,
            "blocking_factor": cri.blocking_factor,
            "is_coherent": cri.coherence.is_coherent,
            "is_ambiguous": cri.entropy.is_ambiguous,

            # Safe descriptions
            "description": cri.get_safe_description(),

            # Actionable signals (not actions)
            "human_can_conceptualize": cri.index >= 0.7,
            "needs_clarification": cri.entropy.is_ambiguous,
            "needs_stabilization": cri.stability < 0.5,
        }

        if drift:
            report["drift"] = drift.drift
            report["drift_type"] = drift.drift_type
            report["is_crystallizing"] = drift.is_crystallizing
            report["is_fragmenting"] = drift.is_fragmenting

        return report


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Types
    "LayerRepresentation",
    "ConceptCoherence",
    "InterpretationCandidate",
    "ConceptEntropy",
    "ConceptReadinessIndex",
    "ConceptDrift",
    # Functions
    "compute_vector_similarity",
    "compute_centroid",
    "compute_concept_coherence",
    "compute_concept_entropy_from_observables",
    "compute_concept_readiness",
    # Monitor
    "ConceptReadinessMonitor",
    # Reporter
    "ConceptReadinessReporter",
]
