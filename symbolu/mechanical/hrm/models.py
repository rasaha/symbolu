"""
HRM v1.0 Models Module

Defines data models for the High-Resolution Mapper:
- HRMInput: Input context for HRM processing
- HighResolutionMap: Output high-resolution cognitive map

All models are immutable dataclasses for deterministic processing.
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class HRMInput:
    """
    Input context for HRM (High-Resolution Mapper) processing.

    Contains all signals needed for building a high-resolution cognitive map:
    - Aspect probabilities from symbolic engine
    - Experiential anchor scores
    - Entropy measures (dimensional, guna, kosha)
    - Domain and tier context
    - Flow mode specification

    Attributes:
        aspect_probs: Dictionary mapping aspect names to probabilities [0, 1].
                     Keys: Execution, Identity, Form, Cognition (lower)
                           Agency, Reasoning, Purpose, Observation, Core, Universal (upper)
        anchor_scores: Dictionary mapping anchor names to scores [0, 1].
                      Keys: Needs, Exchange, Challenge (lower)
                            Belonging, Relation, Change, Meaning, Role, Collective (upper)
        H_D: Dimensional entropy [0, ln(10) ≈ 2.303]
        H_G: Guna entropy [0, ln(3) ≈ 1.099]
        H_K: Kosha entropy [0, ln(5) ≈ 1.609]
        domain: Domain classification (task, code, math, therapy, philosophy, etc.)
        tier: Routing tier from TTOR ("lower", "upper", "hybrid")
        flow_mode: Cognitive flow mode ("outer_only", "outer_plus_inner", "inner_priority")
    """

    aspect_probs: Dict[str, float]
    anchor_scores: Dict[str, float]
    H_D: float
    H_G: float
    H_K: float
    domain: str
    tier: str
    flow_mode: str


@dataclass
class HighResolutionMap:
    """
    Output high-resolution cognitive map from HRM.

    Contains structured, symbolic data for Fusion/DHA engines:
    - Aspect and anchor analysis
    - Entropy profiling
    - Conflict zone detection
    - Resolution hints

    No text generation - only deterministic structured data.

    Attributes:
        dominant_aspects: Aspects sorted by influence (highest first).
                         Aspects with probability >= threshold.
        suppressed_aspects: Aspects with very low probability (< threshold).
                           These receive minimal processing attention.
        anchor_profile: Normalized anchor vector (sums to 1.0).
                       Shows relative strength of each experiential anchor.
        entropy_profile: Entropy analysis dictionary containing:
                        - H_D_norm: Normalized dimensional entropy [0, 1]
                        - H_G_norm: Normalized guna entropy [0, 1]
                        - H_K_norm: Normalized kosha entropy [0, 1]
                        - entropy_mix: Combined weighted entropy signal [0, 1]
                        - regime: Classification ("low", "medium", "high")
        conflict_zones: List of detected aspect/anchor conflict labels.
                       Examples: "practical_support_gap", "identity_integration_gap"
        resolution_hints: Deterministic hint labels for Fusion/DHA.
                         Examples: "anchor_tension_needs_vs_meaning",
                                  "high_entropy_upper_tilt"
        tier: Routing tier from input ("lower", "upper", "hybrid")
        domain: Domain classification from input
    """

    dominant_aspects: List[str] = field(default_factory=list)
    suppressed_aspects: List[str] = field(default_factory=list)
    anchor_profile: Dict[str, float] = field(default_factory=dict)
    entropy_profile: Dict[str, float] = field(default_factory=dict)
    conflict_zones: List[str] = field(default_factory=list)
    resolution_hints: List[str] = field(default_factory=list)
    tier: str = ""
    domain: str = ""

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "dominant_aspects": self.dominant_aspects,
            "suppressed_aspects": self.suppressed_aspects,
            "anchor_profile": self.anchor_profile,
            "entropy_profile": self.entropy_profile,
            "conflict_zones": self.conflict_zones,
            "resolution_hints": self.resolution_hints,
            "tier": self.tier,
            "domain": self.domain,
        }

    def __repr__(self) -> str:
        """Concise representation for logging."""
        dominant = ", ".join(self.dominant_aspects[:3]) if self.dominant_aspects else "none"
        conflicts = len(self.conflict_zones)
        regime = self.entropy_profile.get("regime", "unknown")
        return (
            f"HighResolutionMap(tier={self.tier}, domain={self.domain}, "
            f"dominant=[{dominant}], conflicts={conflicts}, regime={regime})"
        )
