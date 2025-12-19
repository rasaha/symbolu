"""
Dimension Extractors
====================

Specialized extractors for each dimension with directional classification.

The projection direction indicates how knowledge flows:
    - TOP_DOWN: Universal → Specific (deductive, from principles)
    - BOTTOM_UP: Specific → Universal (inductive, from examples)
    - BIDIRECTIONAL: Both directions present

This captures whether content reasons from general laws to instances
or from concrete examples to abstract principles.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import re
from abc import ABC, abstractmethod


class ProjectionDirection(Enum):
    """
    Direction of cognitive projection in the ontological space.

    TOP_DOWN: Deductive - from universal principles to specific cases
        Example: "According to Newton's laws, the apple must fall"

    BOTTOM_UP: Inductive - from specific cases to universal principles
        Example: "Observing many falling objects, we derive gravity"

    BIDIRECTIONAL: Both directions present
        Example: "The law of supply and demand explains why prices rose"
    """
    TOP_DOWN = "top_down"      # Universal → Specific (10D → 1D flow)
    BOTTOM_UP = "bottom_up"    # Specific → Universal (1D → 10D flow)
    BIDIRECTIONAL = "bidirectional"  # Both directions


@dataclass
class DirectionalScore:
    """
    Dimensional score with projection direction.

    Attributes:
        dimension_value: Base score [0.0, 1.0]
        direction: Projection direction
        direction_strength: Confidence in direction [0.0, 1.0]
        evidence: Patterns that contributed to classification
    """
    dimension_value: float
    direction: ProjectionDirection
    direction_strength: float
    evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.dimension_value,
            "direction": self.direction.value,
            "direction_strength": self.direction_strength,
            "evidence": self.evidence,
        }


# =============================================================================
# Direction Detection Patterns
# =============================================================================

# TOP_DOWN indicators: deductive reasoning, from principles
TOP_DOWN_PATTERNS = re.compile(
    r'\b(therefore|thus|hence|consequently|it follows|'
    r'according to|by definition|in principle|'
    r'the law states|the rule is|from this we see|'
    r'this means that|we can conclude|'
    r'logically|necessarily|must be|'
    r'applying|given that|since .+ then)\b',
    re.IGNORECASE
)

# BOTTOM_UP indicators: inductive reasoning, from examples
BOTTOM_UP_PATTERNS = re.compile(
    r'\b(for example|for instance|such as|like|'
    r'evidence shows|data suggests|observations indicate|'
    r'we observe|we see that|we find|'
    r'this suggests|this implies|this shows|'
    r'based on|from .+ we learn|'
    r'empirically|inductively|tends to|'
    r'pattern|trend|correlation)\b',
    re.IGNORECASE
)

# Structural markers for direction
HIERARCHY_TOP_DOWN = re.compile(
    r'\b(all|every|universal|always|never|'
    r'in general|generally|typically|'
    r'law|principle|theorem|axiom|'
    r'definition|category|class)\b',
    re.IGNORECASE
)

HIERARCHY_BOTTOM_UP = re.compile(
    r'\b(specific|particular|individual|'
    r'case|instance|example|sample|'
    r'story|event|incident|occurrence|'
    r'detail|fact|datum|observation)\b',
    re.IGNORECASE
)


def detect_projection_direction(text: str) -> Tuple[ProjectionDirection, float, List[str]]:
    """
    Detect the projection direction of content.

    Analyzes linguistic patterns to determine if reasoning flows
    from universal to specific (top-down) or vice versa (bottom-up).

    Args:
        text: Input text

    Returns:
        Tuple of (direction, confidence, evidence_list)
    """
    evidence = []

    # Count pattern matches
    top_down_matches = TOP_DOWN_PATTERNS.findall(text)
    bottom_up_matches = BOTTOM_UP_PATTERNS.findall(text)
    hierarchy_td = HIERARCHY_TOP_DOWN.findall(text)
    hierarchy_bu = HIERARCHY_BOTTOM_UP.findall(text)

    # Calculate scores
    td_score = len(top_down_matches) * 2 + len(hierarchy_td)
    bu_score = len(bottom_up_matches) * 2 + len(hierarchy_bu)

    # Collect evidence
    if top_down_matches:
        evidence.extend([f"TD:{m}" for m in top_down_matches[:3]])
    if bottom_up_matches:
        evidence.extend([f"BU:{m}" for m in bottom_up_matches[:3]])

    total = td_score + bu_score
    if total == 0:
        return ProjectionDirection.BIDIRECTIONAL, 0.5, ["no_clear_direction"]

    # Determine direction
    td_ratio = td_score / total
    bu_ratio = bu_score / total

    if td_ratio > 0.65:
        direction = ProjectionDirection.TOP_DOWN
        strength = min(1.0, td_ratio)
    elif bu_ratio > 0.65:
        direction = ProjectionDirection.BOTTOM_UP
        strength = min(1.0, bu_ratio)
    else:
        direction = ProjectionDirection.BIDIRECTIONAL
        strength = 1.0 - abs(td_ratio - bu_ratio)

    return direction, strength, evidence


# =============================================================================
# Abstract Extractor Base
# =============================================================================

class DimensionExtractor(ABC):
    """
    Base class for dimension-specific extractors.

    Each dimension can have specialized extraction logic beyond
    the basic pattern matching in encoder.py.
    """

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the dimension number (1-10)."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return dimension name."""
        pass

    @property
    @abstractmethod
    def mathematical_basis(self) -> str:
        """Return the mathematical structure this dimension maps to."""
        pass

    @abstractmethod
    def extract(self, text: str) -> DirectionalScore:
        """
        Extract dimensional score with direction.

        Args:
            text: Input text

        Returns:
            DirectionalScore with value, direction, and evidence
        """
        pass

    def _base_extract(self, text: str, patterns: Dict[str, re.Pattern]) -> Tuple[float, List[str]]:
        """
        Base extraction using pattern matching.

        Args:
            text: Input text
            patterns: Dict of pattern names to compiled patterns

        Returns:
            Tuple of (normalized_score, evidence_list)
        """
        words = text.split()
        word_count = len(words) if words else 1

        total_matches = 0
        evidence = []

        for name, pattern in patterns.items():
            matches = pattern.findall(text)
            total_matches += len(matches)
            if matches:
                evidence.extend(matches[:2])

        # Normalize
        import math
        density = total_matches / word_count
        base_rate = 0.02
        ratio = density / base_rate if base_rate > 0 else 0
        normalized = 1.0 / (1.0 + math.exp(-ratio + 2))

        return max(0.0, min(1.0, normalized)), evidence


# =============================================================================
# Concrete Extractors
# =============================================================================

class ActionExtractor(DimensionExtractor):
    """1D Action: Linear progression, cause-effect chains."""

    @property
    def dimension(self) -> int:
        return 1

    @property
    def name(self) -> str:
        return "ACTION"

    @property
    def mathematical_basis(self) -> str:
        return "Addition/subtraction, linear algebra"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "verbs": re.compile(
                r'\b(do|make|create|build|destroy|begin|end|start|'
                r'fight|win|lose|change|happen|occur)\b', re.IGNORECASE
            ),
            "sequence": re.compile(
                r'\b(first|then|next|after|before|finally)\b', re.IGNORECASE
            ),
            "causation": re.compile(
                r'\b(because|therefore|result|cause|effect|lead to)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class IdentificationExtractor(DimensionExtractor):
    """2D Identification: Entities, polarities, ratios."""

    @property
    def dimension(self) -> int:
        return 2

    @property
    def name(self) -> str:
        return "IDENTIFICATION"

    @property
    def mathematical_basis(self) -> str:
        return "Multiplication/division, ratios, polarities"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "entities": re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'),
            "polarities": re.compile(
                r'\b(vs|versus|against|opposite|conflict|division)\b', re.IGNORECASE
            ),
            "ratios": re.compile(
                r'\b(ratio|proportion|percent|fraction|half|double)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class BodyExtractor(DimensionExtractor):
    """3D Body: Geometry, form, space."""

    @property
    def dimension(self) -> int:
        return 3

    @property
    def name(self) -> str:
        return "BODY"

    @property
    def mathematical_basis(self) -> str:
        return "Geometry, spatial relationships"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "physical": re.compile(
                r'\b(body|physical|material|solid|mass|shape)\b', re.IGNORECASE
            ),
            "spatial": re.compile(
                r'\b(place|location|area|region|land|country|city)\b', re.IGNORECASE
            ),
            "geometry": re.compile(
                r'\b(point|line|plane|circle|angle|distance|dimension)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class MindExtractor(DimensionExtractor):
    """4D Mind: Time, recursion, flow."""

    @property
    def dimension(self) -> int:
        return 4

    @property
    def name(self) -> str:
        return "MIND"

    @property
    def mathematical_basis(self) -> str:
        return "Recursion, sequences, flow"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "temporal": re.compile(
                r'\b(time|year|century|era|past|present|future|history)\b', re.IGNORECASE
            ),
            "process": re.compile(
                r'\b(process|step|stage|phase|cycle|sequence)\b', re.IGNORECASE
            ),
            "memory": re.compile(
                r'\b(remember|memory|recall|forget|learn)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class EgoExtractor(DimensionExtractor):
    """5D Ego: Logic, computation, choice."""

    @property
    def dimension(self) -> int:
        return 5

    @property
    def name(self) -> str:
        return "EGO"

    @property
    def mathematical_basis(self) -> str:
        return "Boolean logic, branching, computation"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "choice": re.compile(
                r'\b(choose|decide|decision|option|select|prefer)\b', re.IGNORECASE
            ),
            "logic": re.compile(
                r'\b(if|then|else|and|or|not|true|false|condition)\b', re.IGNORECASE
            ),
            "agency": re.compile(
                r'\b(I|we|person|leader|actor|self|identity)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class IntellectExtractor(DimensionExtractor):
    """6D Intellect: Set theory, laws, categories."""

    @property
    def dimension(self) -> int:
        return 6

    @property
    def name(self) -> str:
        return "INTELLECT"

    @property
    def mathematical_basis(self) -> str:
        return "Set theory, classification"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "laws": re.compile(
                r'\b(law|rule|principle|theory|theorem|formula)\b', re.IGNORECASE
            ),
            "categories": re.compile(
                r'\b(type|kind|class|category|set|all|every|universal)\b', re.IGNORECASE
            ),
            "abstract": re.compile(
                r'\b(concept|idea|abstract|definition|meaning)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class SoulExtractor(DimensionExtractor):
    """7D Soul: Topology, continuity, transformation."""

    @property
    def dimension(self) -> int:
        return 7

    @property
    def name(self) -> str:
        return "SOUL"

    @property
    def mathematical_basis(self) -> str:
        return "Topology, continuous mappings"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "continuity": re.compile(
                r'\b(continue|continuous|endure|lasting|eternal)\b', re.IGNORECASE
            ),
            "transformation": re.compile(
                r'\b(transform|evolve|transition|become|emerge)\b', re.IGNORECASE
            ),
            "connection": re.compile(
                r'\b(connect|link|bond|relation|bridge|unite)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class WitnessExtractor(DimensionExtractor):
    """8D Witness: Probability, superposition, awareness."""

    @property
    def dimension(self) -> int:
        return 8

    @property
    def name(self) -> str:
        return "WITNESS"

    @property
    def mathematical_basis(self) -> str:
        return "Probability, superposition"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "probability": re.compile(
                r'\b(probable|likely|chance|odds|risk|percent)\b', re.IGNORECASE
            ),
            "possibility": re.compile(
                r'\b(possible|might|may|could|perhaps|maybe)\b', re.IGNORECASE
            ),
            "awareness": re.compile(
                r'\b(observe|witness|see|perceive|aware|perspective)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class SingularityExtractor(DimensionExtractor):
    """9D Singularity: Unification, convergence."""

    @property
    def dimension(self) -> int:
        return 9

    @property
    def name(self) -> str:
        return "SINGULARITY"

    @property
    def mathematical_basis(self) -> str:
        return "Unification theories, limits"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "unity": re.compile(
                r'\b(unity|united|union|unified|one|whole)\b', re.IGNORECASE
            ),
            "convergence": re.compile(
                r'\b(converge|focus|center|culminate|peak|climax)\b', re.IGNORECASE
            ),
            "synthesis": re.compile(
                r'\b(synthesis|combine|merge|fusion|blend|reconcile)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


class AbsoluteExtractor(DimensionExtractor):
    """10D Absolute: Infinity, transcendence, completeness."""

    @property
    def dimension(self) -> int:
        return 10

    @property
    def name(self) -> str:
        return "ABSOLUTE"

    @property
    def mathematical_basis(self) -> str:
        return "Symbolic infinity, completeness"

    def extract(self, text: str) -> DirectionalScore:
        patterns = {
            "infinity": re.compile(
                r'\b(infinite|endless|boundless|limitless|eternal)\b', re.IGNORECASE
            ),
            "transcendence": re.compile(
                r'\b(transcend|beyond|supreme|divine|sacred|spiritual)\b', re.IGNORECASE
            ),
            "completeness": re.compile(
                r'\b(complete|whole|perfect|absolute|ultimate|fundamental)\b', re.IGNORECASE
            ),
        }
        value, evidence = self._base_extract(text, patterns)
        direction, strength, dir_evidence = detect_projection_direction(text)
        return DirectionalScore(value, direction, strength, evidence + dir_evidence)


# =============================================================================
# Registry and Factory
# =============================================================================

_EXTRACTORS: Dict[int, DimensionExtractor] = {
    1: ActionExtractor(),
    2: IdentificationExtractor(),
    3: BodyExtractor(),
    4: MindExtractor(),
    5: EgoExtractor(),
    6: IntellectExtractor(),
    7: SoulExtractor(),
    8: WitnessExtractor(),
    9: SingularityExtractor(),
    10: AbsoluteExtractor(),
}


def get_extractor(dimension: int) -> DimensionExtractor:
    """
    Get extractor for specific dimension.

    Args:
        dimension: Dimension number (1-10)

    Returns:
        DimensionExtractor instance

    Raises:
        ValueError: If dimension not in range 1-10
    """
    if dimension not in _EXTRACTORS:
        raise ValueError(f"Dimension must be 1-10, got {dimension}")
    return _EXTRACTORS[dimension]


def get_all_extractors() -> List[DimensionExtractor]:
    """Get all extractors in order."""
    return [_EXTRACTORS[i] for i in range(1, 11)]


def extract_all_with_direction(text: str) -> Dict[str, DirectionalScore]:
    """
    Extract all dimensions with directional information.

    Args:
        text: Input text

    Returns:
        Dict mapping dimension name to DirectionalScore
    """
    result = {}
    for extractor in get_all_extractors():
        score = extractor.extract(text)
        result[extractor.name] = score
    return result
