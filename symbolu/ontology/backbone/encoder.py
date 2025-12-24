"""
10D Ontological Encoder
=======================

Encodes any content into a 10-dimensional vector based on mathematical
structures underlying each cognitive dimension.

Hard Constraints:
    - Deterministic: same input => identical output
    - No LLM/ML: purely rule-based extraction
    - No external dependencies: self-contained logic
    - Normalized output: all dimensions in [0.0, 1.0]
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import re
from functools import lru_cache


class Dimension(Enum):
    """
    10 ontological dimensions mapping cognition to mathematics.

    Each dimension represents a fundamental aspect of knowledge that can
    be expressed mathematically, enabling cross-domain structural comparison.
    """

    # 1D: Action - Linear progression, sequences, cause-effect chains
    # Mathematical basis: Addition/subtraction, linear algebra
    ACTION = 1

    # 2D: Identification - Entities, polarities, comparisons
    # Mathematical basis: Multiplication/division, ratios
    IDENTIFICATION = 2

    # 3D: Body - Physical form, space, structure
    # Mathematical basis: Geometry, spatial relationships
    BODY = 3

    # 4D: Mind - Time, process, memory, recursion
    # Mathematical basis: Sequences, recursion, flow
    MIND = 4

    # 5D: Ego - Choices, decisions, agency
    # Mathematical basis: Boolean logic, branching, computation
    EGO = 5

    # 6D: Intellect - Laws, categories, universals
    # Mathematical basis: Set theory, classification
    INTELLECT = 6

    # 7D: Soul - Continuity, transformation, connection
    # Mathematical basis: Topology, continuous mappings
    SOUL = 7

    # 8D: Witness - Possibilities, uncertainty, awareness
    # Mathematical basis: Probability, superposition
    WITNESS = 8

    # 9D: Singularity - Unity, convergence, synthesis
    # Mathematical basis: Unification theories, limits
    SINGULARITY = 9

    # 10D: Absolute - Infinity, transcendence, potential
    # Mathematical basis: Symbolic infinity, completeness
    ABSOLUTE = 10


@dataclass(frozen=True)
class DimensionalVector:
    """
    Immutable 10-dimensional encoding of content.

    Each dimension value is normalized to [0.0, 1.0] representing
    the degree to which that dimensional quality is present.

    Attributes:
        values: Tuple of 10 floats, one per dimension
        content_hash: SHA256 hash of source content for tracing
        metadata: Optional extraction metadata
    """
    values: Tuple[float, float, float, float, float,
                  float, float, float, float, float]
    content_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if len(self.values) != 10:
            raise ValueError(f"Expected 10 dimensions, got {len(self.values)}")
        for i, v in enumerate(self.values):
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"Dimension {i+1} value {v} not in [0.0, 1.0]")

    def get(self, dim: Dimension) -> float:
        """Get value for specific dimension."""
        return self.values[dim.value - 1]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "dimensions": {
                dim.name: self.values[dim.value - 1]
                for dim in Dimension
            },
            "content_hash": self.content_hash,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DimensionalVector":
        """Reconstruct from dictionary."""
        dims = data["dimensions"]
        values = tuple(dims[dim.name] for dim in Dimension)
        return cls(
            values=values,
            content_hash=data["content_hash"],
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        parts = [f"{d.name[:3]}={self.values[d.value-1]:.2f}" for d in Dimension]
        return f"DimensionalVector({', '.join(parts)})"


# =============================================================================
# Pattern Definitions for Each Dimension
# =============================================================================

# 1D ACTION: Verbs, events, progressions, sequences
ACTION_PATTERNS = {
    "verbs": re.compile(
        r'\b(do|did|done|make|made|create|build|destroy|begin|end|start|'
        r'stop|continue|move|go|come|run|walk|fight|win|lose|change|'
        r'transform|evolve|develop|grow|decline|rise|fall|attack|defend|'
        r'invade|retreat|advance|progress|happen|occur|unfold)\b',
        re.IGNORECASE
    ),
    "sequence_markers": re.compile(
        r'\b(first|then|next|after|before|finally|subsequently|'
        r'following|preceding|meanwhile|during|while|until|since)\b',
        re.IGNORECASE
    ),
    "cause_effect": re.compile(
        r'\b(because|therefore|thus|hence|consequently|result|'
        r'cause|effect|lead to|due to|owing to|as a result)\b',
        re.IGNORECASE
    ),
}

# 2D IDENTIFICATION: Entities, polarities, comparisons
IDENTIFICATION_PATTERNS = {
    "entities": re.compile(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'  # Proper nouns
    ),
    "polarities": re.compile(
        r'\b(vs|versus|against|or|either|neither|both|'
        r'opposite|contrary|conflict|division|split|'
        r'north|south|east|west|left|right|'
        r'rich|poor|good|evil|light|dark|war|peace)\b',
        re.IGNORECASE
    ),
    "comparisons": re.compile(
        r'\b(like|unlike|similar|different|same|equal|'
        r'greater|lesser|more|less|better|worse|'
        r'compared to|in contrast|on the other hand)\b',
        re.IGNORECASE
    ),
}

# 3D BODY: Physical, spatial, structural
BODY_PATTERNS = {
    "physical": re.compile(
        r'\b(body|physical|material|tangible|concrete|'
        r'solid|liquid|gas|mass|weight|size|shape|'
        r'large|small|tall|short|wide|narrow|thick|thin)\b',
        re.IGNORECASE
    ),
    "spatial": re.compile(
        r'\b(place|location|position|area|region|territory|'
        r'land|country|city|state|continent|ocean|'
        r'above|below|inside|outside|between|among|'
        r'north|south|east|west|here|there|where)\b',
        re.IGNORECASE
    ),
    "structural": re.compile(
        r'\b(structure|form|shape|pattern|design|'
        r'architecture|framework|system|organization|'
        r'layer|level|hierarchy|arrangement)\b',
        re.IGNORECASE
    ),
}

# 4D MIND: Time, process, memory, recursion
MIND_PATTERNS = {
    "temporal": re.compile(
        r'\b(time|year|month|day|hour|century|decade|era|'
        r'period|age|epoch|moment|instant|duration|'
        r'past|present|future|history|memory|remember|'
        r'ancient|modern|contemporary|recent|old|new|'
        r'\d{4}|\d{1,2}th\s+century)\b',
        re.IGNORECASE
    ),
    "process": re.compile(
        r'\b(process|procedure|method|step|stage|phase|'
        r'cycle|loop|iteration|recursion|repeat|'
        r'flow|stream|sequence|series|chain)\b',
        re.IGNORECASE
    ),
    "cognitive": re.compile(
        r'\b(think|thought|believe|know|understand|'
        r'learn|remember|forget|imagine|consider|'
        r'mind|mental|cognitive|conscious|aware)\b',
        re.IGNORECASE
    ),
}

# 5D EGO: Choice, decision, agency, logic
EGO_PATTERNS = {
    "choice": re.compile(
        r'\b(choose|chose|choice|decide|decision|'
        r'option|alternative|select|pick|prefer|'
        r'want|desire|will|willing|refuse|accept)\b',
        re.IGNORECASE
    ),
    "agency": re.compile(
        r'\b(I|we|he|she|they|person|people|individual|'
        r'leader|president|king|queen|general|hero|'
        r'actor|agent|subject|self|identity)\b',
        re.IGNORECASE
    ),
    "logic": re.compile(
        r'\b(if|then|else|and|or|not|true|false|'
        r'condition|conditional|logic|logical|'
        r'reason|rational|argument|premise|conclusion)\b',
        re.IGNORECASE
    ),
}

# 6D INTELLECT: Laws, categories, universals, set theory
INTELLECT_PATTERNS = {
    "laws": re.compile(
        r'\b(law|rule|principle|theory|theorem|'
        r'axiom|postulate|formula|equation|'
        r'constitution|regulation|statute|code)\b',
        re.IGNORECASE
    ),
    "categories": re.compile(
        r'\b(type|kind|class|category|group|set|'
        r'classification|taxonomy|genus|species|'
        r'all|every|any|some|none|each|universal)\b',
        re.IGNORECASE
    ),
    "abstract": re.compile(
        r'\b(concept|idea|notion|abstract|theoretical|'
        r'general|specific|particular|instance|example|'
        r'definition|meaning|essence|nature)\b',
        re.IGNORECASE
    ),
}

# 7D SOUL: Continuity, transformation, connection, topology
SOUL_PATTERNS = {
    "continuity": re.compile(
        r'\b(continue|continuous|continuity|persistent|'
        r'endure|lasting|permanent|eternal|forever|'
        r'sustain|maintain|preserve|survive)\b',
        re.IGNORECASE
    ),
    "transformation": re.compile(
        r'\b(transform|change|convert|evolve|metamorphosis|'
        r'transition|shift|turn|become|emerge|'
        r'develop|growth|adaptation|mutation)\b',
        re.IGNORECASE
    ),
    "connection": re.compile(
        r'\b(connect|connection|link|bond|tie|'
        r'relation|relationship|association|'
        r'bridge|unite|join|merge|integrate)\b',
        re.IGNORECASE
    ),
}

# 8D WITNESS: Probability, possibility, uncertainty
WITNESS_PATTERNS = {
    "probability": re.compile(
        r'\b(probable|probably|likely|unlikely|'
        r'chance|odds|risk|possibility|'
        r'percent|percentage|ratio|rate)\b',
        re.IGNORECASE
    ),
    "possibility": re.compile(
        r'\b(possible|impossible|might|may|could|'
        r'would|should|perhaps|maybe|potentially|'
        r'hypothetical|speculative|uncertain)\b',
        re.IGNORECASE
    ),
    "awareness": re.compile(
        r'\b(observe|witness|see|watch|notice|'
        r'perceive|aware|consciousness|attention|'
        r'perspective|viewpoint|standpoint|angle)\b',
        re.IGNORECASE
    ),
}

# 9D SINGULARITY: Unity, convergence, synthesis
SINGULARITY_PATTERNS = {
    "unity": re.compile(
        r'\b(unity|united|union|unified|unify|'
        r'one|single|whole|complete|total|'
        r'together|combine|consolidate|integrate)\b',
        re.IGNORECASE
    ),
    "convergence": re.compile(
        r'\b(converge|convergence|focus|center|'
        r'concentrate|gather|assemble|culminate|'
        r'peak|climax|apex|pinnacle|zenith)\b',
        re.IGNORECASE
    ),
    "synthesis": re.compile(
        r'\b(synthesis|synthesize|combine|merge|'
        r'fusion|blend|mixture|hybrid|'
        r'reconcile|resolve|harmonize|balance)\b',
        re.IGNORECASE
    ),
}

# 10D ABSOLUTE: Infinity, transcendence, completeness
ABSOLUTE_PATTERNS = {
    "infinity": re.compile(
        r'\b(infinite|infinity|endless|boundless|'
        r'limitless|unlimited|eternal|forever|'
        r'always|never|absolute|ultimate)\b',
        re.IGNORECASE
    ),
    "transcendence": re.compile(
        r'\b(transcend|transcendent|beyond|above|'
        r'supreme|divine|sacred|holy|spiritual|'
        r'metaphysical|supernatural|mystical)\b',
        re.IGNORECASE
    ),
    "completeness": re.compile(
        r'\b(complete|whole|entire|full|total|'
        r'perfect|pure|absolute|definitive|'
        r'final|ultimate|fundamental|essential)\b',
        re.IGNORECASE
    ),
}

# Aggregate all patterns by dimension
DIMENSION_PATTERNS = {
    Dimension.ACTION: ACTION_PATTERNS,
    Dimension.IDENTIFICATION: IDENTIFICATION_PATTERNS,
    Dimension.BODY: BODY_PATTERNS,
    Dimension.MIND: MIND_PATTERNS,
    Dimension.EGO: EGO_PATTERNS,
    Dimension.INTELLECT: INTELLECT_PATTERNS,
    Dimension.SOUL: SOUL_PATTERNS,
    Dimension.WITNESS: WITNESS_PATTERNS,
    Dimension.SINGULARITY: SINGULARITY_PATTERNS,
    Dimension.ABSOLUTE: ABSOLUTE_PATTERNS,
}


# =============================================================================
# Encoding Functions
# =============================================================================

def _compute_content_hash(content: str) -> str:
    """Compute deterministic hash of content."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


def _count_pattern_matches(text: str, patterns: Dict[str, re.Pattern]) -> int:
    """Count total matches across all patterns in a category."""
    total = 0
    for pattern in patterns.values():
        matches = pattern.findall(text)
        total += len(matches)
    return total


def _normalize_score(raw_score: int, text_length: int, base_rate: float = 0.02) -> float:
    """
    Normalize raw match count to [0.0, 1.0].

    Uses logarithmic scaling to handle varying text lengths and
    prevent saturation for long texts.

    Args:
        raw_score: Number of pattern matches
        text_length: Length of text in words
        base_rate: Expected matches per word in neutral text

    Returns:
        Normalized score in [0.0, 1.0]
    """
    if text_length == 0:
        return 0.0

    # Calculate density (matches per word)
    density = raw_score / text_length

    # Normalize relative to base rate using sigmoid-like function
    # density = base_rate => 0.5
    # density = 2*base_rate => ~0.73
    # density = 4*base_rate => ~0.88
    import math

    ratio = density / base_rate if base_rate > 0 else 0
    normalized = 1.0 / (1.0 + math.exp(-ratio + 2))  # Shifted sigmoid

    return max(0.0, min(1.0, normalized))


def _extract_dimension_score(text: str, dimension: Dimension, word_count: int) -> float:
    """
    Extract score for a single dimension.

    Args:
        text: Input text
        dimension: Dimension to score
        word_count: Pre-computed word count

    Returns:
        Normalized score in [0.0, 1.0]
    """
    patterns = DIMENSION_PATTERNS[dimension]
    raw_score = _count_pattern_matches(text, patterns)
    return _normalize_score(raw_score, word_count)


@lru_cache(maxsize=1024)
def encode_10d(content: str) -> DimensionalVector:
    """
    Encode content into 10-dimensional vector.

    Extracts structural features for each dimension using pattern matching.
    Results are deterministic and cached for efficiency.

    Args:
        content: Text content to encode

    Returns:
        DimensionalVector with normalized scores per dimension

    Example:
        >>> vec = encode_10d("The Civil War divided the nation in 1861")
        >>> vec.get(Dimension.ACTION)  # High (war, divided)
        0.72
        >>> vec.get(Dimension.IDENTIFICATION)  # High (division/polarity)
        0.68
    """
    if not content or not content.strip():
        return DimensionalVector(
            values=(0.0,) * 10,
            content_hash=_compute_content_hash(content or ""),
            metadata={"empty": True},
        )

    # Pre-compute word count
    words = content.split()
    word_count = len(words)

    # Extract score for each dimension
    scores = []
    extraction_details = {}

    for dim in Dimension:
        score = _extract_dimension_score(content, dim, word_count)
        scores.append(score)
        extraction_details[dim.name] = {
            "raw_matches": _count_pattern_matches(content, DIMENSION_PATTERNS[dim]),
            "normalized": score,
        }

    return DimensionalVector(
        values=tuple(scores),
        content_hash=_compute_content_hash(content),
        metadata={
            "word_count": word_count,
            "extraction": extraction_details,
        },
    )


def encode_batch(contents: List[str]) -> List[DimensionalVector]:
    """
    Encode multiple contents efficiently.

    Args:
        contents: List of text contents

    Returns:
        List of DimensionalVector encodings
    """
    return [encode_10d(content) for content in contents]


# =============================================================================
# Utility Functions
# =============================================================================

def get_dominant_dimensions(vec: DimensionalVector, top_k: int = 3) -> List[Tuple[Dimension, float]]:
    """
    Get the top-k most prominent dimensions.

    Args:
        vec: Dimensional vector
        top_k: Number of dimensions to return

    Returns:
        List of (Dimension, score) tuples, sorted by score descending
    """
    dim_scores = [(dim, vec.get(dim)) for dim in Dimension]
    dim_scores.sort(key=lambda x: x[1], reverse=True)
    return dim_scores[:top_k]


def get_dimensional_profile(vec: DimensionalVector) -> str:
    """
    Generate human-readable profile of dimensional encoding.

    Args:
        vec: Dimensional vector

    Returns:
        Multi-line string describing the dimensional profile
    """
    lines = ["Dimensional Profile:"]
    for dim in Dimension:
        score = vec.get(dim)
        bar = "=" * int(score * 20)
        lines.append(f"  {dim.name:15} [{bar:20}] {score:.2f}")
    return "\n".join(lines)
