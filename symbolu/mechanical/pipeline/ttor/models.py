"""
TTOR v1.4 Models Module

Defines validated data models for the Two-Tier Ontology Router:
- RouterContext: Input context for routing decisions
- RoutingPlan: Output routing plan with full audit trail
- Tier: Enumeration of routing tiers
- FlowMode: Enumeration of flow modes

Uses Pydantic for strict validation and type safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from .constants import (
    ALL_ANCHORS,
    ALL_ASPECTS,
    H_D_MAX,
    H_G_MAX,
    VALID_RISK_LEVELS,
)


class Tier(str, Enum):
    """Routing tier classification."""

    LOWER = "lower"
    UPPER = "upper"
    HYBRID = "hybrid"


class FlowMode(str, Enum):
    """Flow mode for cognitive processing."""

    OUTER_ONLY = "outer_only"
    OUTER_PLUS_INNER = "outer_plus_inner"
    INNER_PRIORITY = "inner_priority"


class RouterContextValidationError(Exception):
    """Raised when RouterContext validation fails."""

    def __init__(self, message: str, field: str, value: Any = None) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Validation error in '{field}': {message}")


class RouterContext(BaseModel):
    """
    Input context for TTOR routing decisions.

    Contains all signals needed for tier and flow mode determination:
    - Aspect probabilities from symbolic engine
    - Entropy measures (dimensional, guna, kosha)
    - Experiential anchor scores
    - Domain and risk context
    - Long-arc tension for LAM integration

    All fields are validated for type correctness and value ranges.
    """

    model_config = ConfigDict(
        frozen=False,
        validate_assignment=True,
        extra="forbid",
    )

    # Required: Aspect probabilities from symbolic engine
    aspect_probs: Dict[str, float]

    # Required: Dimensional entropy [0, ln(10)]
    H_D: float

    # Required: Guna entropy [0, ln(3)]
    H_G: float

    # Optional: Kosha entropy [0, ln(5)]
    H_K: float = 0.0

    # Optional: Vritti probabilities (for future use)
    vritti_probs: Optional[Dict[str, float]] = None

    # Required: Experiential anchor scores
    anchor_scores: Dict[str, float]

    # Domain context
    domain: str = "generic"

    # Risk level classification
    risk_level: str = "low"

    # Long-arc tension for LAM integration
    long_arc_tension: float = 0.0

    # Temporal patterns signal from TemporalBhavaTracker
    # When True, activates LAM regardless of other conditions
    temporal_patterns_detected: bool = False

    @field_validator("aspect_probs")
    @classmethod
    def validate_aspect_probs(cls, v: Dict[str, float]) -> Dict[str, float]:
        """Validate aspect probability keys and values."""
        if not v:
            raise ValueError("aspect_probs cannot be empty")

        # Check for unrecognized aspect keys
        unrecognized = set(v.keys()) - ALL_ASPECTS
        if unrecognized:
            raise ValueError(
                f"Unrecognized aspect keys: {unrecognized}. "
                f"Valid keys are: {ALL_ASPECTS}"
            )

        # Validate probability values
        for key, prob in v.items():
            if not isinstance(prob, (int, float)):
                raise ValueError(f"Aspect '{key}' probability must be numeric, got {type(prob)}")
            if prob < 0.0 or prob > 1.0:
                raise ValueError(
                    f"Aspect '{key}' probability must be in [0, 1], got {prob}"
                )

        return v

    @field_validator("anchor_scores", mode="before")
    @classmethod
    def normalize_anchor_scores(cls, v: Optional[Dict[str, float]]) -> Dict[str, float]:
        """Normalize anchor scores, filling missing keys with 0.0."""
        if v is None:
            # Initialize all anchors to 0.0
            return {anchor: 0.0 for anchor in ALL_ANCHORS}

        # Start with all anchors at 0.0
        normalized: Dict[str, float] = {anchor: 0.0 for anchor in ALL_ANCHORS}

        # Override with provided values (only for recognized anchors)
        for key, score in v.items():
            if key in ALL_ANCHORS:
                if not isinstance(score, (int, float)):
                    raise ValueError(f"Anchor '{key}' score must be numeric")
                # Clamp to [0, 1] range
                normalized[key] = max(0.0, min(1.0, float(score)))

        return normalized

    @field_validator("H_D")
    @classmethod
    def validate_h_d(cls, v: float) -> float:
        """Validate dimensional entropy range."""
        if v < 0.0:
            raise ValueError(f"H_D must be >= 0, got {v}")
        if v > H_D_MAX:
            raise ValueError(f"H_D must be <= {H_D_MAX} (ln(10)), got {v}")
        return v

    @field_validator("H_G")
    @classmethod
    def validate_h_g(cls, v: float) -> float:
        """Validate guna entropy range."""
        if v < 0.0:
            raise ValueError(f"H_G must be >= 0, got {v}")
        if v > H_G_MAX:
            raise ValueError(f"H_G must be <= {H_G_MAX} (ln(3)), got {v}")
        return v

    @field_validator("H_K")
    @classmethod
    def validate_h_k(cls, v: float) -> float:
        """Validate kosha entropy range."""
        if v < 0.0:
            raise ValueError(f"H_K must be >= 0, got {v}")
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, v: str) -> str:
        """Validate risk level is recognized."""
        if v not in VALID_RISK_LEVELS:
            raise ValueError(
                f"Invalid risk_level '{v}'. Must be one of: {VALID_RISK_LEVELS}"
            )
        return v

    @field_validator("long_arc_tension")
    @classmethod
    def validate_long_arc_tension(cls, v: float) -> float:
        """Validate long-arc tension range."""
        if v < 0.0 or v > 1.0:
            raise ValueError(f"long_arc_tension must be in [0, 1], got {v}")
        return v

    def get_aspect_prob(self, aspect: str) -> float:
        """Get aspect probability, returning 0.0 for missing aspects."""
        return self.aspect_probs.get(aspect, 0.0)

    def get_anchor_score(self, anchor: str) -> float:
        """Get anchor score, returning 0.0 for missing anchors."""
        return self.anchor_scores.get(anchor, 0.0)


@dataclass
class RoutingPlan:
    """
    Output routing plan from TTOR.

    Contains the complete routing decision with full audit trail:
    - Tier and flow mode selection
    - Engine family recommendation
    - Module activation flags (HRM, LCM, LAM)
    - Safety flags (regulated mode, metaphor allowance)
    - Key routing signals (normalized_entropy, long_arc_tension, domain)
    - Human-readable explanation
    - Complete debug dictionary for auditability
    """

    # Primary routing decisions
    tier: Tier
    flow_mode: FlowMode
    preferred_engine_family: str

    # Module activation flags
    use_hrm: bool
    use_lcm: bool
    use_lam: bool

    # Safety flags
    regulated_mode: bool
    allow_metaphor: bool

    # Key routing signals (for introspection and debugging)
    normalized_entropy: float
    long_arc_tension: float
    domain: str

    # Audit trail
    explanation: str
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert routing plan to dictionary for serialization."""
        return {
            "tier": self.tier.value,
            "flow_mode": self.flow_mode.value,
            "preferred_engine_family": self.preferred_engine_family,
            "use_hrm": self.use_hrm,
            "use_lcm": self.use_lcm,
            "use_lam": self.use_lam,
            "regulated_mode": self.regulated_mode,
            "allow_metaphor": self.allow_metaphor,
            "normalized_entropy": self.normalized_entropy,
            "long_arc_tension": self.long_arc_tension,
            "domain": self.domain,
            "explanation": self.explanation,
            "debug": self.debug,
        }

    def __repr__(self) -> str:
        """Concise representation for logging."""
        return (
            f"RoutingPlan(tier={self.tier.value}, "
            f"flow_mode={self.flow_mode.value}, "
            f"engine={self.preferred_engine_family}, "
            f"hrm={self.use_hrm}, lcm={self.use_lcm}, lam={self.use_lam})"
        )
