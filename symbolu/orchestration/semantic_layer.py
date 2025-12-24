"""
Semantic Layer for Pipeline B

Provides semantic-to-mechanical translation capabilities:
- Intent parsing: Extract meaning from natural language requests
- Constraint mapping: Translate semantic concepts to Phase-7 constraints
- Response projection: Add semantic annotations to mechanical outputs

This layer bridges the gap between human intent and mechanical generation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable
import re


class SemanticDimension(Enum):
    """Semantic dimensions that can be mapped to mechanical constraints."""
    ENERGY = "energy"           # calm ↔ energetic
    DURATION = "duration"       # short ↔ long
    COMPLEXITY = "complexity"   # simple ↔ complex
    DIRECTION = "direction"     # rising ↔ falling
    STABILITY = "stability"     # stable ↔ volatile
    RHYTHM = "rhythm"           # even ↔ varied


@dataclass
class SemanticVector:
    """
    Multi-dimensional semantic representation.

    Each dimension is a float from -1.0 to 1.0:
    - Negative values: one pole (calm, short, simple, falling, stable, even)
    - Positive values: opposite pole (energetic, long, complex, rising, volatile, varied)
    - Zero: neutral / unspecified
    """
    energy: float = 0.0
    duration: float = 0.0
    complexity: float = 0.0
    direction: float = 0.0
    stability: float = 0.0
    rhythm: float = 0.0

    def __post_init__(self):
        # Clamp all values to [-1, 1]
        self.energy = max(-1.0, min(1.0, self.energy))
        self.duration = max(-1.0, min(1.0, self.duration))
        self.complexity = max(-1.0, min(1.0, self.complexity))
        self.direction = max(-1.0, min(1.0, self.direction))
        self.stability = max(-1.0, min(1.0, self.stability))
        self.rhythm = max(-1.0, min(1.0, self.rhythm))

    def to_dict(self) -> Dict[str, float]:
        return {
            "energy": self.energy,
            "duration": self.duration,
            "complexity": self.complexity,
            "direction": self.direction,
            "stability": self.stability,
            "rhythm": self.rhythm,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, float]) -> "SemanticVector":
        return cls(
            energy=d.get("energy", 0.0),
            duration=d.get("duration", 0.0),
            complexity=d.get("complexity", 0.0),
            direction=d.get("direction", 0.0),
            stability=d.get("stability", 0.0),
            rhythm=d.get("rhythm", 0.0),
        )


@dataclass
class ParsedIntent:
    """Result of parsing a semantic intent string."""
    original_text: str
    semantic_vector: SemanticVector
    keywords_matched: List[str]
    confidence: float
    mechanical_constraints: Dict[str, Any]


# Keyword mappings for intent parsing
SEMANTIC_KEYWORDS = {
    # Energy dimension
    "calm": (SemanticDimension.ENERGY, -0.8),
    "gentle": (SemanticDimension.ENERGY, -0.6),
    "soft": (SemanticDimension.ENERGY, -0.5),
    "peaceful": (SemanticDimension.ENERGY, -0.7),
    "relaxing": (SemanticDimension.ENERGY, -0.8),
    "soothing": (SemanticDimension.ENERGY, -0.7),
    "quiet": (SemanticDimension.ENERGY, -0.6),
    "subtle": (SemanticDimension.ENERGY, -0.4),
    "energetic": (SemanticDimension.ENERGY, 0.8),
    "active": (SemanticDimension.ENERGY, 0.6),
    "dynamic": (SemanticDimension.ENERGY, 0.7),
    "vibrant": (SemanticDimension.ENERGY, 0.8),
    "intense": (SemanticDimension.ENERGY, 0.9),
    "powerful": (SemanticDimension.ENERGY, 0.8),
    "strong": (SemanticDimension.ENERGY, 0.7),
    "bold": (SemanticDimension.ENERGY, 0.6),

    # Duration dimension
    "short": (SemanticDimension.DURATION, -0.8),
    "brief": (SemanticDimension.DURATION, -0.7),
    "quick": (SemanticDimension.DURATION, -0.6),
    "concise": (SemanticDimension.DURATION, -0.5),
    "long": (SemanticDimension.DURATION, 0.8),
    "extended": (SemanticDimension.DURATION, 0.7),
    "sustained": (SemanticDimension.DURATION, 0.6),
    "lengthy": (SemanticDimension.DURATION, 0.7),

    # Complexity dimension
    "simple": (SemanticDimension.COMPLEXITY, -0.8),
    "basic": (SemanticDimension.COMPLEXITY, -0.6),
    "minimal": (SemanticDimension.COMPLEXITY, -0.7),
    "plain": (SemanticDimension.COMPLEXITY, -0.5),
    "complex": (SemanticDimension.COMPLEXITY, 0.8),
    "intricate": (SemanticDimension.COMPLEXITY, 0.9),
    "elaborate": (SemanticDimension.COMPLEXITY, 0.7),
    "rich": (SemanticDimension.COMPLEXITY, 0.6),

    # Direction dimension
    "rising": (SemanticDimension.DIRECTION, 0.8),
    "ascending": (SemanticDimension.DIRECTION, 0.8),
    "growing": (SemanticDimension.DIRECTION, 0.6),
    "building": (SemanticDimension.DIRECTION, 0.7),
    "falling": (SemanticDimension.DIRECTION, -0.8),
    "descending": (SemanticDimension.DIRECTION, -0.8),
    "settling": (SemanticDimension.DIRECTION, -0.6),
    "declining": (SemanticDimension.DIRECTION, -0.7),

    # Stability dimension
    "stable": (SemanticDimension.STABILITY, -0.8),
    "steady": (SemanticDimension.STABILITY, -0.7),
    "constant": (SemanticDimension.STABILITY, -0.8),
    "consistent": (SemanticDimension.STABILITY, -0.6),
    "volatile": (SemanticDimension.STABILITY, 0.8),
    "changing": (SemanticDimension.STABILITY, 0.6),
    "varied": (SemanticDimension.STABILITY, 0.7),
    "fluctuating": (SemanticDimension.STABILITY, 0.8),

    # Rhythm dimension
    "even": (SemanticDimension.RHYTHM, -0.7),
    "regular": (SemanticDimension.RHYTHM, -0.6),
    "uniform": (SemanticDimension.RHYTHM, -0.8),
    "smooth": (SemanticDimension.RHYTHM, -0.5),
    "uneven": (SemanticDimension.RHYTHM, 0.7),
    "irregular": (SemanticDimension.RHYTHM, 0.6),
    "syncopated": (SemanticDimension.RHYTHM, 0.8),
    "broken": (SemanticDimension.RHYTHM, 0.7),
}


class IntentParser:
    """
    Parses natural language intent into semantic vectors and mechanical constraints.
    """

    def __init__(self, custom_keywords: Optional[Dict[str, Tuple[SemanticDimension, float]]] = None):
        self.keywords = dict(SEMANTIC_KEYWORDS)
        if custom_keywords:
            self.keywords.update(custom_keywords)

    def parse(self, intent_text: str) -> ParsedIntent:
        """
        Parse an intent string into semantic representation.

        Args:
            intent_text: Natural language description of desired output

        Returns:
            ParsedIntent with semantic vector and mechanical constraints
        """
        text_lower = intent_text.lower()

        # Extract keywords and accumulate semantic values
        matched_keywords = []
        dimension_values: Dict[SemanticDimension, List[float]] = {
            dim: [] for dim in SemanticDimension
        }

        for keyword, (dimension, value) in self.keywords.items():
            if keyword in text_lower:
                matched_keywords.append(keyword)
                dimension_values[dimension].append(value)

        # Average values for each dimension
        vector_values = {}
        for dim in SemanticDimension:
            values = dimension_values[dim]
            if values:
                vector_values[dim.value] = sum(values) / len(values)
            else:
                vector_values[dim.value] = 0.0

        semantic_vector = SemanticVector.from_dict(vector_values)

        # Calculate confidence based on keyword coverage
        confidence = min(1.0, len(matched_keywords) * 0.2) if matched_keywords else 0.1

        # Translate to mechanical constraints
        mechanical_constraints = self._vector_to_constraints(semantic_vector)

        return ParsedIntent(
            original_text=intent_text,
            semantic_vector=semantic_vector,
            keywords_matched=matched_keywords,
            confidence=confidence,
            mechanical_constraints=mechanical_constraints,
        )

    def _vector_to_constraints(self, vector: SemanticVector) -> Dict[str, Any]:
        """
        Translate semantic vector to Phase-7 mechanical constraints.

        This is the core mapping from semantic space to validity space.
        """
        constraints = {}

        # Energy → final_magnitude
        if vector.energy < -0.3:
            # Low energy: magnitude close to 1.0
            constraints["final_magnitude"] = f"in [1.0, {1.0 + 0.2 * (1 + vector.energy):.1f}]"
        elif vector.energy > 0.3:
            # High energy: higher magnitude
            constraints["final_magnitude"] = f">= {1.0 + 0.3 * vector.energy:.1f}"

        # Duration → len(steps)
        if vector.duration < -0.3:
            # Short: fewer steps
            max_len = max(1, int(3 + 2 * (1 + vector.duration)))
            constraints["len(steps)"] = f"<= {max_len}"
        elif vector.duration > 0.3:
            # Long: more steps
            min_len = max(2, int(2 + 3 * vector.duration))
            constraints["len(steps)"] = f">= {min_len}"

        # Complexity → template pattern or event counts
        if vector.complexity < -0.3:
            # Simple: consonant-vowel alternation only
            constraints["template starts_with"] = "CV"
        elif vector.complexity > 0.3:
            # Complex: require multiple consonant clusters
            constraints["count(steps where event == 'reset')"] = f">= {max(2, int(2 + 2 * vector.complexity))}"

        # Direction → monotonic constraints
        if vector.direction < -0.3:
            # Falling: monotonically decreasing
            constraints["monotonic_decreasing(steps[].magnitude)"] = "== true"
        elif vector.direction > 0.3:
            # Rising: monotonically increasing
            constraints["monotonic_increasing(steps[].magnitude)"] = "== true"

        # Stability → magnitude range
        if vector.stability < -0.3:
            # Stable: small magnitude range
            constraints["max(steps[].magnitude) - min(steps[].magnitude)"] = f"<= {0.3 * (1 + vector.stability):.1f}"
        elif vector.stability > 0.3:
            # Volatile: larger magnitude swings
            constraints["max(steps[].magnitude) - min(steps[].magnitude)"] = f">= {0.2 * vector.stability:.1f}"

        return constraints


class ResponseProjector:
    """
    Projects mechanical outputs back into semantic space.

    Adds semantic annotations to Phase-7 results without modifying them.
    """

    def __init__(self):
        pass

    def project(
        self,
        sequences: Tuple[Tuple[str, ...], ...],
        trajectories: Optional[List[Any]] = None,
        original_intent: Optional[ParsedIntent] = None,
    ) -> Dict[str, Any]:
        """
        Project sequences into semantic space.

        Args:
            sequences: Generated sequences from Phase-7
            trajectories: Optional trajectory data
            original_intent: Optional parsed intent for comparison

        Returns:
            Semantic projection with annotations
        """
        projections = []

        for i, seq in enumerate(sequences):
            projection = self._project_sequence(seq, trajectories[i] if trajectories else None)
            projections.append(projection)

        # Calculate aggregate semantic properties
        aggregate = self._aggregate_projections(projections)

        # Calculate intent match if original intent provided
        intent_match = None
        if original_intent:
            intent_match = self._calculate_intent_match(aggregate, original_intent)

        return {
            "sequence_projections": projections,
            "aggregate": aggregate,
            "intent_match": intent_match,
        }

    def _project_sequence(
        self,
        sequence: Tuple[str, ...],
        trajectory: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Project a single sequence to semantic space."""

        # Derive semantic properties from sequence structure
        length = len(sequence)

        # Count token types (assuming we can identify them)
        # This is a simplified projection
        projection = {
            "sequence": sequence,
            "length": length,
            "estimated_energy": 0.0,
            "estimated_complexity": 0.0,
        }

        # If we have trajectory data, use it
        if trajectory and hasattr(trajectory, 'final_magnitude'):
            mag = trajectory.final_magnitude
            # Higher magnitude → higher energy
            projection["estimated_energy"] = min(1.0, (mag - 1.0) / 0.5)

            # Count resets for complexity
            if hasattr(trajectory, 'steps'):
                reset_count = sum(1 for s in trajectory.steps if s.event == "reset")
                projection["estimated_complexity"] = min(1.0, reset_count / 3.0)

        return projection

    def _aggregate_projections(self, projections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate multiple sequence projections."""
        if not projections:
            return {"count": 0}

        return {
            "count": len(projections),
            "avg_length": sum(p["length"] for p in projections) / len(projections),
            "avg_energy": sum(p.get("estimated_energy", 0) for p in projections) / len(projections),
            "avg_complexity": sum(p.get("estimated_complexity", 0) for p in projections) / len(projections),
        }

    def _calculate_intent_match(
        self,
        aggregate: Dict[str, Any],
        intent: ParsedIntent,
    ) -> Dict[str, Any]:
        """Calculate how well results match original intent."""

        vector = intent.semantic_vector

        # Compare each dimension
        matches = {}

        # Energy match
        if vector.energy != 0:
            actual_energy = aggregate.get("avg_energy", 0)
            # Normalize to same scale
            normalized_actual = actual_energy * 2 - 1  # Convert [0,1] to [-1,1]
            matches["energy"] = 1.0 - abs(vector.energy - normalized_actual) / 2.0

        # Complexity match
        if vector.complexity != 0:
            actual_complexity = aggregate.get("avg_complexity", 0)
            normalized_actual = actual_complexity * 2 - 1
            matches["complexity"] = 1.0 - abs(vector.complexity - normalized_actual) / 2.0

        # Overall match score
        if matches:
            overall = sum(matches.values()) / len(matches)
        else:
            overall = 0.5  # Neutral if no dimensions specified

        return {
            "dimension_matches": matches,
            "overall_match": overall,
            "confidence": intent.confidence,
        }


# Convenience functions
def parse_intent(text: str) -> ParsedIntent:
    """Parse an intent string using default parser."""
    parser = IntentParser()
    return parser.parse(text)


def intent_to_constraints(text: str) -> Dict[str, Any]:
    """Convert intent text directly to mechanical constraints."""
    return parse_intent(text).mechanical_constraints
