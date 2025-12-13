"""
P21 - Delivery Mode Resolver Schema Definitions

P21 is a governance-only phase that determines HOW output may be delivered.
It does NOT determine WHAT is said or HOW it sounds.

P21's responsibility is to:
- Determine delivery channel permissions (text, voice, suppressed)
- Enforce delivery constraints based on upstream governance signals
- Produce a read-only DeliveryModeDecision for downstream renderers

P21 does NOT:
- Read acoustic units
- Read vrtti mappings
- Read Sanskrit data
- Inspect lexical or semantic content
- Modify text
- Infer emotion or intent
- Override any upstream decision

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Read-only: Does not modify context or upstream state
- Non-cognitive: No inference, no interpretation
- Restrictive-only: Can only restrict, never enable delivery channels
- Binding: Renderers must respect delivery decision

Authority Model:
- P21 sits after cognition/governance and before any renderer
- P21 reads from: regime, blocked status, acoustic_permission_flag, safety envelope
- P21 cannot amplify or override upstream restrictions
- P21 produces DeliveryModeDecision (read-only, binding)

CRITICAL ARCHITECTURAL INVARIANT:
    P21 answers only one question: "Is output allowed, and through which delivery channel?"
    It does not know what the user said, what the system thinks, or how the output will sound.
    Renderers violating P21 are considered unsafe by design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, Optional, Set


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P21_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Delivery mode classification
# ============================================================================


class DeliveryMode(str, Enum):
    """
    Delivery channel permission classification.

    SUPPRESSED: Output must be completely blocked (no delivery)
    TEXT_ONLY: Only text delivery is permitted (voice prohibited)
    TEXT_AND_VOICE: Both text and voice delivery are permitted
    VOICE_PROHIBITED: Explicit voice prohibition (equivalent to TEXT_ONLY but semantically distinct)

    SUPPRESSED is always safe.
    Delivery mode may only restrict, never expand capability.
    """
    SUPPRESSED = "SUPPRESSED"
    TEXT_ONLY = "TEXT_ONLY"
    TEXT_AND_VOICE = "TEXT_AND_VOICE"
    VOICE_PROHIBITED = "VOICE_PROHIBITED"


# ============================================================================
# ENFORCEMENT TAG CONSTANTS
# ============================================================================


# Standard enforcement tags
TAG_BLOCKED_BY_UPSTREAM = "BLOCKED_BY_UPSTREAM"
TAG_HOLD_REGIME = "HOLD_REGIME"
TAG_ACOUSTIC_SAFETY_RESTRICTION = "ACOUSTIC_SAFETY_RESTRICTION"
TAG_HIGH_DRIFT_RISK = "HIGH_DRIFT_RISK"
TAG_CONSERVATIVE_DEFAULT = "CONSERVATIVE_DEFAULT"
TAG_NORMAL_OPERATION = "NORMAL_OPERATION"


# ============================================================================
# DATACLASSES - Core decision object
# ============================================================================


@dataclass(frozen=True)
class DeliveryModeDecision:
    """
    P21 output: Delivery mode decision.

    This decision is read-only and captures the delivery channel permissions
    that constrain all downstream renderers. It is BINDING on renderers.

    Invariants:
    - If delivery_mode == SUPPRESSED, then delivery_allowed must be False
    - If delivery_allowed == False, enforcement_tags must be non-empty
    - blocked_reason must be set if delivery_allowed == False

    Attributes (Decision):
        delivery_mode: The permitted delivery channel (SUPPRESSED/TEXT_ONLY/TEXT_AND_VOICE/VOICE_PROHIBITED)
        delivery_allowed: Whether any delivery is permitted at all
        blocked_reason: Human-readable reason if delivery is blocked/restricted (None if fully allowed)
        enforcement_tags: Tags explaining why this decision was made (for audit/tracing)

    Attributes (Provenance):
        source_regime: The operational regime from P6 (for tracing)
        source_intent_type: The intent type from P0 (for tracing)
        source_blocked: Whether upstream flagged as blocked (for tracing)
        source_acoustic_permission: The acoustic permission flag from P13 (for tracing)
        source_drift_risk_band: The drift risk band from P19 (for tracing)

    Attributes (Metadata):
        architectural_phase: Identifier for this phase ("P21")
        version: P21 version string for provenance
        timestamp_utc: ISO-8601 timestamp for audit purposes
        debug: Additional debug/trace information
    """

    # === Decision ===
    delivery_mode: DeliveryMode
    delivery_allowed: bool
    blocked_reason: Optional[str]
    enforcement_tags: FrozenSet[str]

    # === Provenance ===
    source_regime: Optional[str] = None
    source_intent_type: Optional[str] = None
    source_blocked: Optional[bool] = None
    source_acoustic_permission: Optional[bool] = None
    source_drift_risk_band: Optional[str] = None

    # === Metadata ===
    architectural_phase: str = "P21"
    version: str = P21_VERSION
    timestamp_utc: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate DeliveryModeDecision invariants."""
        # Validate delivery_mode is valid enum
        if not isinstance(self.delivery_mode, DeliveryMode):
            raise ValueError(
                f"DeliveryModeDecision.delivery_mode must be DeliveryMode, "
                f"got {type(self.delivery_mode).__name__}"
            )

        # Validate delivery_allowed is bool
        if not isinstance(self.delivery_allowed, bool):
            raise ValueError(
                f"DeliveryModeDecision.delivery_allowed must be bool, "
                f"got {type(self.delivery_allowed).__name__}"
            )

        # INVARIANT: SUPPRESSED → delivery_allowed must be False
        if self.delivery_mode == DeliveryMode.SUPPRESSED and self.delivery_allowed:
            raise ValueError(
                "DeliveryModeDecision: SUPPRESSED mode requires delivery_allowed=False"
            )

        # Validate enforcement_tags is frozenset
        if not isinstance(self.enforcement_tags, frozenset):
            raise ValueError(
                f"DeliveryModeDecision.enforcement_tags must be frozenset, "
                f"got {type(self.enforcement_tags).__name__}"
            )

        # INVARIANT: If delivery is restricted, enforcement_tags must be non-empty
        is_restricted = (
            not self.delivery_allowed or
            self.delivery_mode in (DeliveryMode.SUPPRESSED, DeliveryMode.TEXT_ONLY, DeliveryMode.VOICE_PROHIBITED)
        )
        if is_restricted and len(self.enforcement_tags) == 0:
            raise ValueError(
                "DeliveryModeDecision: enforcement_tags must be non-empty when delivery is restricted"
            )

        # Validate blocked_reason when delivery not allowed
        if not self.delivery_allowed and not self.blocked_reason:
            raise ValueError(
                "DeliveryModeDecision: blocked_reason must be set when delivery_allowed=False"
            )

    def is_suppressed(self) -> bool:
        """Check if delivery is completely suppressed."""
        return self.delivery_mode == DeliveryMode.SUPPRESSED

    def is_text_only(self) -> bool:
        """Check if only text delivery is permitted."""
        return self.delivery_mode in (DeliveryMode.TEXT_ONLY, DeliveryMode.VOICE_PROHIBITED)

    def allows_voice(self) -> bool:
        """Check if voice delivery is permitted."""
        return self.delivery_mode == DeliveryMode.TEXT_AND_VOICE

    def allows_text(self) -> bool:
        """Check if text delivery is permitted."""
        return self.delivery_mode in (DeliveryMode.TEXT_ONLY, DeliveryMode.TEXT_AND_VOICE, DeliveryMode.VOICE_PROHIBITED)

    def is_fully_blocked(self) -> bool:
        """Check if all delivery is blocked."""
        return not self.delivery_allowed

    def has_enforcement_tag(self, tag: str) -> bool:
        """Check if a specific enforcement tag is present."""
        return tag in self.enforcement_tags

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            # Decision
            "delivery_mode": self.delivery_mode.value,
            "delivery_allowed": self.delivery_allowed,
            "blocked_reason": self.blocked_reason,
            "enforcement_tags": sorted(self.enforcement_tags),
            # Provenance
            "source_regime": self.source_regime,
            "source_intent_type": self.source_intent_type,
            "source_blocked": self.source_blocked,
            "source_acoustic_permission": self.source_acoustic_permission,
            "source_drift_risk_band": self.source_drift_risk_band,
            # Metadata
            "architectural_phase": self.architectural_phase,
            "version": self.version,
            "timestamp_utc": self.timestamp_utc,
            "debug": self.debug,
            # Computed
            "is_suppressed": self.is_suppressed(),
            "is_text_only": self.is_text_only(),
            "allows_voice": self.allows_voice(),
            "allows_text": self.allows_text(),
            "is_fully_blocked": self.is_fully_blocked(),
        }


# ============================================================================
# EXCEPTIONS
# ============================================================================


class DeliveryInvariantViolation(Exception):
    """
    Exception raised when P21 invariants are violated.

    This is raised when:
    - Forbidden data is accessed (acoustic, lexical, semantic, ontology)
    - Renderer attempts to override decision
    - Non-deterministic behavior is detected
    - Context is mutated
    """

    def __init__(self, message: str, violation_type: str = "UNKNOWN") -> None:
        """
        Initialize the violation exception.

        Args:
            message: Human-readable description of the violation
            violation_type: Category of violation (FORBIDDEN_ACCESS, OVERRIDE_ATTEMPT, etc.)
        """
        super().__init__(message)
        self.violation_type = violation_type
        self.message = message

    def __str__(self) -> str:
        return f"[{self.violation_type}] {self.message}"


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_decision(
    delivery_mode: DeliveryMode,
    delivery_allowed: bool,
    blocked_reason: Optional[str] = None,
    enforcement_tags: Optional[Set[str]] = None,
    source_regime: Optional[str] = None,
    source_intent_type: Optional[str] = None,
    source_blocked: Optional[bool] = None,
    source_acoustic_permission: Optional[bool] = None,
    source_drift_risk_band: Optional[str] = None,
    timestamp_utc: str = "",
    debug: Optional[Dict[str, Any]] = None,
) -> DeliveryModeDecision:
    """
    Factory function to create a DeliveryModeDecision.

    Args:
        delivery_mode: The delivery mode (SUPPRESSED/TEXT_ONLY/TEXT_AND_VOICE/VOICE_PROHIBITED)
        delivery_allowed: Whether delivery is permitted
        blocked_reason: Reason for blocking (if applicable)
        enforcement_tags: Set of enforcement tags
        source_regime: Source regime from P6
        source_intent_type: Source intent type from P0
        source_blocked: Whether upstream blocked
        source_acoustic_permission: Acoustic permission from P13
        source_drift_risk_band: Drift risk band from P19
        timestamp_utc: Timestamp string
        debug: Debug information

    Returns:
        DeliveryModeDecision instance
    """
    tags = frozenset(enforcement_tags) if enforcement_tags else frozenset()

    return DeliveryModeDecision(
        delivery_mode=delivery_mode,
        delivery_allowed=delivery_allowed,
        blocked_reason=blocked_reason,
        enforcement_tags=tags,
        source_regime=source_regime,
        source_intent_type=source_intent_type,
        source_blocked=source_blocked,
        source_acoustic_permission=source_acoustic_permission,
        source_drift_risk_band=source_drift_risk_band,
        timestamp_utc=timestamp_utc,
        debug=debug or {},
    )


def create_suppressed_decision(
    reason: str,
    enforcement_tags: Optional[Set[str]] = None,
    source_regime: Optional[str] = None,
    source_blocked: Optional[bool] = None,
    timestamp_utc: str = "",
) -> DeliveryModeDecision:
    """
    Create a SUPPRESSED delivery decision (no delivery permitted).

    This is the safest possible decision.

    Args:
        reason: Why delivery is suppressed
        enforcement_tags: Tags for audit trail
        source_regime: Source regime
        source_blocked: Whether upstream blocked
        timestamp_utc: Timestamp

    Returns:
        DeliveryModeDecision with SUPPRESSED mode
    """
    tags = enforcement_tags or {TAG_BLOCKED_BY_UPSTREAM}

    return create_decision(
        delivery_mode=DeliveryMode.SUPPRESSED,
        delivery_allowed=False,
        blocked_reason=reason,
        enforcement_tags=tags,
        source_regime=source_regime,
        source_blocked=source_blocked,
        timestamp_utc=timestamp_utc,
    )


def create_text_only_decision(
    reason: str,
    enforcement_tags: Optional[Set[str]] = None,
    source_regime: Optional[str] = None,
    source_acoustic_permission: Optional[bool] = None,
    source_drift_risk_band: Optional[str] = None,
    timestamp_utc: str = "",
) -> DeliveryModeDecision:
    """
    Create a TEXT_ONLY delivery decision (voice prohibited).

    Args:
        reason: Why voice is prohibited
        enforcement_tags: Tags for audit trail
        source_regime: Source regime
        source_acoustic_permission: Acoustic permission flag
        source_drift_risk_band: Drift risk band
        timestamp_utc: Timestamp

    Returns:
        DeliveryModeDecision with TEXT_ONLY mode
    """
    tags = enforcement_tags or {TAG_CONSERVATIVE_DEFAULT}

    return create_decision(
        delivery_mode=DeliveryMode.TEXT_ONLY,
        delivery_allowed=True,
        blocked_reason=reason,
        enforcement_tags=tags,
        source_regime=source_regime,
        source_acoustic_permission=source_acoustic_permission,
        source_drift_risk_band=source_drift_risk_band,
        timestamp_utc=timestamp_utc,
    )


# Public exports
__all__ = [
    # Enums
    "DeliveryMode",
    # Dataclasses
    "DeliveryModeDecision",
    # Exceptions
    "DeliveryInvariantViolation",
    # Constants - version
    "P21_VERSION",
    # Constants - enforcement tags
    "TAG_BLOCKED_BY_UPSTREAM",
    "TAG_HOLD_REGIME",
    "TAG_ACOUSTIC_SAFETY_RESTRICTION",
    "TAG_HIGH_DRIFT_RISK",
    "TAG_CONSERVATIVE_DEFAULT",
    "TAG_NORMAL_OPERATION",
    # Helper functions
    "create_decision",
    "create_suppressed_decision",
    "create_text_only_decision",
]
