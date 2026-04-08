"""
Name Resonance System - Type Definitions
========================================

All types are frozen (immutable) dataclasses.
All collections are immutable (tuple, frozenset).

Tier: Core/Substrate (Tier 1)
Authority: NONE (signal processing only)
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any
from enum import Enum


# =============================================================================
# Enumerations
# =============================================================================

class ScriptFamily(Enum):
    """Script family detection for input normalization."""
    LATIN = "latin"
    DEVANAGARI = "devanagari"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class CompatibilityLevel(Enum):
    """Domain compatibility classification."""
    STRONG = "strong"      # >= threshold + 0.15
    MODERATE = "moderate"  # >= threshold
    PARTIAL = "partial"    # >= threshold - 0.15
    WEAK = "weak"          # < threshold - 0.15


# =============================================================================
# Layer 1: Input Normalization
# =============================================================================

@dataclass(frozen=True)
class NormalizedInput:
    """
    Immutable canonical form of input.

    Attributes:
        original: Raw input string
        canonical: Normalized lowercase form
        segments: Word/syllable segments
        script_family: Detected script family
    """
    original: str
    canonical: str
    segments: Tuple[str, ...]
    script_family: ScriptFamily


# =============================================================================
# Layer 2: Signal Extraction
# =============================================================================

@dataclass(frozen=True)
class ExtractedSignals:
    """
    All signals extracted from input.

    These are mechanical, rule-based features with no interpretation.
    """
    # Phonemic signals
    phoneme_sequence: Tuple[str, ...]
    phoneme_categories: Tuple[str, ...]

    # Rhythmic signals
    syllable_count: int
    stress_pattern: Tuple[int, ...]  # 0=unstressed, 1=stressed
    vowel_consonant_ratio: float

    # Structural signals
    onset_cluster_size: int
    coda_cluster_size: int

    # Positional signals
    initial_phoneme: str
    final_phoneme: str
    initial_category: str
    final_category: str

    # Energy signals (counts)
    plosive_count: int
    fricative_count: int
    nasal_count: int
    liquid_count: int
    glide_count: int
    vowel_count: int

    def __post_init__(self):
        if self.syllable_count < 1:
            object.__setattr__(self, "syllable_count", 1)


# =============================================================================
# Layer 3: Abstract Structural Space
# =============================================================================

# Dimension names for the 12D structural profile
DIMENSION_NAMES: Tuple[str, ...] = (
    "force",
    "stability",
    "duration",
    "initiation",
    "flow",
    "termination",
    "complexity",
    "density",
    "balance",
    "openness",
    "depth",
    "connectivity",
)


@dataclass(frozen=True)
class StructuralProfile:
    """
    12D domain-agnostic structural representation.

    All values are in range [0.0, 1.0].
    """
    # Energy Dimensions (3)
    force: float          # Low (flowing) to High (forceful)
    stability: float      # Variable to Constant
    duration: float       # Brief to Sustained

    # Movement Dimensions (3)
    initiation: float     # Gradual to Explosive
    flow: float           # Interrupted to Continuous
    termination: float    # Fading to Abrupt

    # Structural Dimensions (3)
    complexity: float     # Simple to Complex
    density: float        # Sparse to Dense
    balance: float        # Asymmetric to Symmetric

    # Resonance Dimensions (3)
    openness: float       # Closed to Open
    depth: float          # Surface to Deep
    connectivity: float   # Isolated to Connected

    # Trace for explainability
    signal_contributions: Tuple[Tuple[str, str, float], ...] = field(default=())

    def __post_init__(self):
        # Clamp all values to [0.0, 1.0]
        for dim in DIMENSION_NAMES:
            val = getattr(self, dim)
            if val < 0.0 or val > 1.0:
                object.__setattr__(self, dim, max(0.0, min(1.0, val)))

    def get_high_dimensions(self, threshold: float = 0.65) -> Tuple[Tuple[str, float], ...]:
        """Get dimensions above threshold."""
        return tuple(
            (dim, getattr(self, dim))
            for dim in DIMENSION_NAMES
            if getattr(self, dim) >= threshold
        )

    def get_low_dimensions(self, threshold: float = 0.35) -> Tuple[Tuple[str, float], ...]:
        """Get dimensions below threshold."""
        return tuple(
            (dim, getattr(self, dim))
            for dim in DIMENSION_NAMES
            if getattr(self, dim) <= threshold
        )

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization."""
        return {dim: getattr(self, dim) for dim in DIMENSION_NAMES}


# =============================================================================
# Layer 4: Domain Projection
# =============================================================================

@dataclass(frozen=True)
class DomainPattern:
    """
    Structural pattern defining a domain's requirements.

    Domains are structural patterns, not labels.
    """
    name: str
    category: str  # "career", "sport", "role"
    ideal_profile: Tuple[Tuple[str, float], ...]  # (dimension, ideal_value)
    dimension_weights: Tuple[Tuple[str, float], ...]  # (dimension, weight)
    compatibility_threshold: float
    rationale: str

    def get_ideal(self, dimension: str) -> float:
        """Get ideal value for a dimension."""
        for dim, val in self.ideal_profile:
            if dim == dimension:
                return val
        return 0.5  # Default to middle

    def get_weight(self, dimension: str) -> float:
        """Get weight for a dimension."""
        for dim, weight in self.dimension_weights:
            if dim == dimension:
                return weight
        return 0.0


@dataclass(frozen=True)
class DimensionScore:
    """Score breakdown for a single dimension."""
    dimension: str
    actual: float
    ideal: float
    weight: float
    match_score: float  # 1.0 - |actual - ideal|
    weighted_contribution: float


@dataclass(frozen=True)
class DomainCompatibilityResult:
    """
    Result of matching a profile against a domain pattern.
    """
    domain_name: str
    domain_category: str
    compatibility_score: float
    classification: CompatibilityLevel
    dimension_breakdown: Tuple[DimensionScore, ...]
    rationale: str
    top_matches: Tuple[str, ...]  # Best matching dimensions
    weak_matches: Tuple[str, ...]  # Worst matching dimensions


# =============================================================================
# Layer 5: Full Result
# =============================================================================

@dataclass(frozen=True)
class NameResonanceResult:
    """
    Complete result of name resonance analysis.

    Includes full trace from input to output.
    """
    # Input
    original_input: str
    normalized_input: NormalizedInput

    # Signals
    signals: ExtractedSignals

    # Structure
    profile: StructuralProfile

    # Domain results
    domain_results: Tuple[DomainCompatibilityResult, ...]

    # Summary
    summary: str
    high_compatibility: Tuple[str, ...]  # Domain names with strong match
    low_compatibility: Tuple[str, ...]   # Domain names with weak match

    # Mandatory caveats
    caveats: Tuple[str, ...] = field(default=(
        "This analysis is based solely on phonetic/structural features.",
        "Domain compatibility reflects pattern matching, not individual capability.",
        "Cultural, personal, and contextual factors are not considered.",
        "This is a deterministic projection, not a prediction.",
    ))

    def get_domain_result(self, domain_name: str) -> DomainCompatibilityResult | None:
        """Get result for a specific domain."""
        for result in self.domain_results:
            if result.domain_name == domain_name:
                return result
        return None
