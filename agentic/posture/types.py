"""
Configurable Decision Posture - Type Definitions
=================================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                    BEHAVIORAL SOVEREIGNTY LAYER                                ║
║                                                                                ║
║  Gives operators control over HOW the system behaves,                          ║
║  while the system itself remains incapable of choosing WHAT is true.           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

This module provides operator-defined behavioral modulation within immutable
truth constraints.

HARD CONSTRAINTS (Non-Negotiable):
    ❌ Must NEVER override STL truth evaluation
    ❌ Must NEVER modify ontology or symbolic grounding
    ❌ Must NEVER perform moral judgments
    ❌ Must NEVER classify users ethically or psychologically
    ❌ Must NEVER introduce stochastic behavior
    ❌ Must NEVER affect Tier-1 invariant outputs

ALLOWED SCOPE:
    ✅ Threshold modulation (escalation, ambiguity tolerance)
    ✅ Routing sensitivity (confidence cutoffs, cascade timing)
    ✅ Response shaping (explanation depth, conservatism)
    ✅ Feedback gating (learning activation, decay rates)

This is Augmented General Intelligence:
    - No autonomy
    - No moral judgment
    - No value choice
    - Only operator-controlled behavioral tuning

Version: 1.0
Date: 2025-12-22
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional, FrozenSet
from enum import Enum


# =============================================================================
# Hard Safety Constraints
# =============================================================================

class PostureConstraint(Enum):
    """
    Hard constraints that posture must NEVER violate.

    These are documented explicitly for regulatory scrutiny and audit.
    """
    NO_TRUTH_OVERRIDE = "posture_must_not_override_stl_truth"
    NO_ONTOLOGY_MODIFICATION = "posture_must_not_modify_ontology"
    NO_MORAL_JUDGMENT = "posture_must_not_perform_moral_judgment"
    NO_USER_CLASSIFICATION = "posture_must_not_classify_users_ethically"
    NO_STOCHASTIC_BEHAVIOR = "posture_must_remain_deterministic"
    NO_TIER1_MODIFICATION = "posture_must_not_affect_tier1_invariants"


# All constraints that must always be respected
HARD_CONSTRAINTS: FrozenSet[PostureConstraint] = frozenset(PostureConstraint)


# =============================================================================
# Influence Scope
# =============================================================================

class PostureInfluenceScope(Enum):
    """
    Defines what a posture is allowed to influence.

    Each scope is explicitly non-authoritative over truth.
    """
    ROUTING_THRESHOLD = "routing_threshold"
    ESCALATION_THRESHOLD = "escalation_threshold"
    AMBIGUITY_TOLERANCE = "ambiguity_tolerance"
    RESPONSE_DEPTH = "response_depth"
    EXPLANATION_VERBOSITY = "explanation_verbosity"
    CONSERVATISM_LEVEL = "conservatism_level"
    FEEDBACK_ACTIVATION = "feedback_activation"
    LEARNING_DECAY_RATE = "learning_decay_rate"
    CASCADE_AGGRESSIVENESS = "cascade_aggressiveness"
    REFUSAL_STRICTNESS = "refusal_strictness"


# =============================================================================
# Tier Application Rules
# =============================================================================

class PostureTier(Enum):
    """Engine tiers with different posture application rules."""
    TIER_1 = "tier_1"  # Enterprise Search (STL only)
    TIER_2 = "tier_2"  # Enterprise Chat (STL + 7B)
    TIER_3 = "tier_3"  # Consumer (STL + 768D + Cascade)


# What each tier is allowed to have influenced by posture
TIER_ALLOWED_INFLUENCES: Dict[PostureTier, Tuple[PostureInfluenceScope, ...]] = {
    PostureTier.TIER_1: (),  # ❌ None - read-only reference only
    PostureTier.TIER_2: (
        PostureInfluenceScope.ROUTING_THRESHOLD,
        PostureInfluenceScope.EXPLANATION_VERBOSITY,
        PostureInfluenceScope.RESPONSE_DEPTH,
        PostureInfluenceScope.CONSERVATISM_LEVEL,
    ),
    PostureTier.TIER_3: (
        PostureInfluenceScope.ROUTING_THRESHOLD,
        PostureInfluenceScope.ESCALATION_THRESHOLD,
        PostureInfluenceScope.AMBIGUITY_TOLERANCE,
        PostureInfluenceScope.RESPONSE_DEPTH,
        PostureInfluenceScope.EXPLANATION_VERBOSITY,
        PostureInfluenceScope.CONSERVATISM_LEVEL,
        PostureInfluenceScope.FEEDBACK_ACTIVATION,
        PostureInfluenceScope.LEARNING_DECAY_RATE,
        PostureInfluenceScope.CASCADE_AGGRESSIVENESS,
        PostureInfluenceScope.REFUSAL_STRICTNESS,
    ),
}


# =============================================================================
# Decision Posture Profile (Public API)
# =============================================================================

@dataclass(frozen=True)
class DecisionPostureProfile:
    """
    Operator-defined behavioral modulation within immutable truth constraints.

    This is the PUBLIC API for enterprise configuration. Internal mappings
    are not exposed.

    Attributes:
        coherence_bias: [0.0-1.0] Preference for explanation, balance, auditability.
                        Higher values favor structured, well-explained responses.

        exploration_bias: [0.0-1.0] Preference for novelty, adaptation, learning.
                          Higher values allow more exploratory behavior.

        constraint_bias: [0.0-1.0] Preference for refusal, conservatism, brakes.
                         Higher values favor cautious, constrained behavior.

    Normalization:
        Values should sum to 1.0 for balanced posture interpretation.
        Use normalize() to ensure this property.

    Important:
        - This does NOT influence truth evaluation
        - This does NOT modify ontology
        - This does NOT perform moral judgments
        - This ONLY adjusts behavioral thresholds and response shaping
    """
    coherence_bias: float    # [0.0–1.0] explanation, balance, auditability
    exploration_bias: float  # [0.0–1.0] novelty, adaptation, learning
    constraint_bias: float   # [0.0–1.0] refusal, conservatism, brakes

    # Hard caps to prevent extreme behavior
    MIN_BIAS: float = 0.05
    MAX_BIAS: float = 0.80

    def __post_init__(self):
        """Validate and clamp all bias values."""
        for attr in ("coherence_bias", "exploration_bias", "constraint_bias"):
            val = getattr(self, attr)
            # Clamp to valid range
            clamped = max(0.0, min(1.0, val))
            if clamped != val:
                object.__setattr__(self, attr, clamped)

    def normalize(self) -> "DecisionPostureProfile":
        """
        Return a normalized profile where biases sum to 1.0.

        Also applies hard caps to prevent extreme single-axis dominance.
        """
        total = self.coherence_bias + self.exploration_bias + self.constraint_bias
        if total == 0.0:
            # Default to balanced
            return DecisionPostureProfile(
                coherence_bias=1/3,
                exploration_bias=1/3,
                constraint_bias=1/3,
            )

        # Normalize
        coherence = self.coherence_bias / total
        exploration = self.exploration_bias / total
        constraint = self.constraint_bias / total

        # Apply hard caps
        coherence = max(self.MIN_BIAS, min(self.MAX_BIAS, coherence))
        exploration = max(self.MIN_BIAS, min(self.MAX_BIAS, exploration))
        constraint = max(self.MIN_BIAS, min(self.MAX_BIAS, constraint))

        # Re-normalize after capping
        total = coherence + exploration + constraint
        return DecisionPostureProfile(
            coherence_bias=coherence / total,
            exploration_bias=exploration / total,
            constraint_bias=constraint / total,
        )

    @property
    def is_balanced(self) -> bool:
        """Check if this profile is approximately balanced."""
        variance = (
            (self.coherence_bias - 1/3) ** 2 +
            (self.exploration_bias - 1/3) ** 2 +
            (self.constraint_bias - 1/3) ** 2
        )
        return variance < 0.01  # Close to equal thirds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "coherence_bias": round(self.coherence_bias, 4),
            "exploration_bias": round(self.exploration_bias, 4),
            "constraint_bias": round(self.constraint_bias, 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> "DecisionPostureProfile":
        """Create profile from dictionary."""
        return cls(
            coherence_bias=data.get("coherence_bias", 1/3),
            exploration_bias=data.get("exploration_bias", 1/3),
            constraint_bias=data.get("constraint_bias", 1/3),
        )


# =============================================================================
# Posture Application Result
# =============================================================================

@dataclass(frozen=True)
class PostureApplicationResult:
    """
    Result of applying posture to a decision point.

    Contains full audit trail for regulatory compliance.
    """
    original_value: float
    adjusted_value: float
    adjustment_delta: float
    influence_scope: PostureInfluenceScope
    tier: PostureTier
    posture_applied: DecisionPostureProfile
    was_influenced: bool  # True if posture actually changed the value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for audit logging."""
        return {
            "original_value": round(self.original_value, 4),
            "adjusted_value": round(self.adjusted_value, 4),
            "adjustment_delta": round(self.adjustment_delta, 4),
            "influence_scope": self.influence_scope.value,
            "tier": self.tier.value,
            "posture_applied": self.posture_applied.to_dict(),
            "was_influenced": self.was_influenced,
        }


# =============================================================================
# Posture Audit Record
# =============================================================================

@dataclass(frozen=True)
class PostureAuditRecord:
    """
    Complete audit record for posture application.

    Designed for regulatory scrutiny and external auditors.

    NEVER claims:
        - "system chose"
        - "system judged"
        - "system decided morally"

    ALWAYS indicates:
        - operator-configured
        - non-authoritative over truth
        - deterministic application
    """
    posture_profile: DecisionPostureProfile
    applied_to: Tuple[PostureInfluenceScope, ...]
    influence_scope_label: str  # Always "non-authoritative"
    tier: PostureTier
    applications: Tuple[PostureApplicationResult, ...]
    constraints_respected: Tuple[PostureConstraint, ...]
    posture_source: str  # "deployment_default", "request_override", etc.

    def __post_init__(self):
        """Ensure influence scope is always non-authoritative."""
        if self.influence_scope_label != "non-authoritative":
            object.__setattr__(self, "influence_scope_label", "non-authoritative")

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization.

        This is the format exposed in API responses for audit.
        """
        return {
            "decision_posture": {
                "coherence_bias": round(self.posture_profile.coherence_bias, 4),
                "exploration_bias": round(self.posture_profile.exploration_bias, 4),
                "constraint_bias": round(self.posture_profile.constraint_bias, 4),
                "applied_to": [scope.value for scope in self.applied_to],
                "influence_scope": self.influence_scope_label,
                "tier": self.tier.value,
                "source": self.posture_source,
            },
            "applications": [app.to_dict() for app in self.applications],
            "constraints_respected": [c.value for c in self.constraints_respected],
        }


# =============================================================================
# Posture Configuration
# =============================================================================

@dataclass(frozen=True)
class PostureConfig:
    """
    Configuration for posture behavior in a deployment.

    Attributes:
        default_profile: The default posture when none is specified
        allow_request_override: Whether per-request overrides are allowed
        max_adjustment_magnitude: Maximum posture influence on any value
        enable_audit_logging: Whether to log all posture applications
    """
    default_profile: DecisionPostureProfile
    allow_request_override: bool = True
    max_adjustment_magnitude: float = 0.10  # Maximum ±10% adjustment
    enable_audit_logging: bool = True

    def __post_init__(self):
        """Validate configuration."""
        if self.max_adjustment_magnitude < 0.0 or self.max_adjustment_magnitude > 0.20:
            raise ValueError(
                f"max_adjustment_magnitude must be in [0.0, 0.20], got {self.max_adjustment_magnitude}"
            )
