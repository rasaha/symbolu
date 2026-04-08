"""
SOULPI Core Data Models
=======================

Pure-Python dataclass models used across the Symbol-U stack.

SHARED CONTRACT STATUS
======================
These types are the canonical shared contract layer between the Symbol-U
pipeline (``symbolu_core/``) and the agentic governance framework
(``agentic/agentic_framework/``).

All types in this module are:
- Pure Python dataclasses (no PyTorch, no ML dependencies)
- Importable without side effects
- Safe for use in governance signal adapters, policy replay, and audit

Governance-safe types (intended for cross-layer consumption):
- ``EntropyState``   — entropy measurements (maps to entropy_adapter)
- ``BhavaState``     — consciousness state snapshot (maps to vritti/session signals)
- ``SMIResult``      — semantic mismatch index (maps to vritti_adapter)
- ``AnalysisResult`` — complete pipeline analysis output
- ``DeliveryMode``   — DHA delivery mode enum (maps to output_modulation)

Pipeline-internal types (used by pipeline, not typically needed in governance):
- ``SyllableAnalysis`` — phonemic decomposition detail
- ``WordAnalysis``     — word-level SMI detail
- ``RecursionState``   — iteration tracking for pipeline recursion
- ``CandidateResponse`` — stitching/fusion candidate scoring
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


@dataclass
class SyllableAnalysis:
    """Result of syllable decomposition and analysis."""
    syllable: str
    consonant: Optional[str] = None
    vowel: Optional[str] = None
    kosha_id: Optional[int] = None
    vritti_distribution: List[float] = field(default_factory=list)


@dataclass
class WordAnalysis:
    """Result of word-level analysis."""
    word: str
    syllables: List[SyllableAnalysis] = field(default_factory=list)
    ontology_layer: Optional[int] = None
    inner_kosha: Optional[int] = None
    outer_ontology: Optional[int] = None
    smi: Optional[float] = None


@dataclass
class EntropyState:
    """Entropy measurements across dimensions."""
    H_dim: float = 0.0
    H_guna: float = 0.0
    H_kosha: float = 0.0
    H_combined: float = 0.0


@dataclass
class BhavaState:
    """Consciousness state at a point in time."""
    timestamp: float = 0.0
    vritti_distribution: List[float] = field(default_factory=lambda: [0.2] * 5)
    aspect_weights: List[float] = field(default_factory=lambda: [0.1] * 10)
    entropy: EntropyState = field(default_factory=EntropyState)
    stability_score: float = 0.0


@dataclass
class RecursionState:
    """State maintained across recursion iterations."""
    iteration: int = 0
    max_iterations: int = 10
    converged: bool = False
    states: List[BhavaState] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateResponse:
    """A candidate response with scoring metadata."""
    text: str
    score: float = 0.0
    aspect_alignment: float = 0.0
    vritti_alignment: float = 0.0
    entropy_penalty: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SMIResult:
    """Semantic Mismatch Index computation result."""
    smi: float = 0.0
    inner_kosha: int = 0
    outer_ontology: int = 0
    components: Dict[str, float] = field(default_factory=dict)
    interpretation: str = ""


class DeliveryMode(Enum):
    """DHA delivery mode selection."""
    SWEET_RESONANCE = "sweet_resonance"
    INVERSE_JOLT = "inverse_jolt"
    SYMBOLIC_METAPHOR = "symbolic_metaphor"
    DEFER = "defer"
    MIRROR_PREVIEW = "mirror_preview"
    MIRROR_CAUTION = "mirror_caution"
    FULL_DELIVERY = "full_delivery"


@dataclass
class AnalysisResult:
    """Complete analysis result from the pipeline."""
    text: str
    words: List[WordAnalysis] = field(default_factory=list)
    average_smi: float = 0.0
    bhava_state: Optional[BhavaState] = None
    entropy: Optional[EntropyState] = None
    delivery_mode: Optional[DeliveryMode] = None
    recommendations: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


# =============================================================================
# EXPORT SURFACE
# =============================================================================

# Types safe for governance adapter / cross-layer consumption.
# These can be imported by agentic_framework signal adapters without
# pulling in pipeline internals.
GOVERNANCE_SAFE_TYPES = (
    "EntropyState",
    "BhavaState",
    "SMIResult",
    "AnalysisResult",
    "DeliveryMode",
)

# All types (includes pipeline-internal types).
__all__ = [
    "SyllableAnalysis",
    "WordAnalysis",
    "EntropyState",
    "BhavaState",
    "RecursionState",
    "CandidateResponse",
    "SMIResult",
    "DeliveryMode",
    "AnalysisResult",
    "GOVERNANCE_SAFE_TYPES",
]
