"""
P15 — Interaction Mode Resolver Schema Definitions

P15 is a post-surface, pre-delivery phase.
It determines HOW INTERACTIVE the system may be when delivering the
already-realized expression. It does NOT alter wording, acoustics, or meaning.

P15's responsibility is to:
- Determine interaction posture only
- Produce a read-only InteractionDirective that constrains delivery mode

P15 does NOT:
- Alter wording, syntax, or meaning
- Modify acoustic parameters
- Introduce reasoning or explanation
- Override HOLD/BLOCKED states
- Execute actions
- Call LLMs
- Introduce probabilistic behavior

Design Principles:
- Deterministic: No LLM calls, no probabilistic sampling
- Posture-Only: Determines interaction level, not content
- Authority-Respecting: Cannot override PO1–P14 constraints
- Conservative: READ_ONLY is always safe

Authority Model:
- Authority flows: PO1 → ... → P13 → P14 → P15 → (Delivery layers)
- P15 receives signals from P6 (regime), P7 (discourse), PO1 (grounding)
- P15 cannot override or expand upstream decisions
- P15 cannot modify P13 or P14 outputs
- P15 produces InteractionDirective (read-only)

CRITICAL ARCHITECTURAL INVARIANT:
    P15 determines interaction posture only.
    P15 cannot alter wording, acoustics, or meaning.
    P15 cannot override HOLD/BLOCKED states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P15_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Interaction mode classification
# ============================================================================


class InteractionMode(str, Enum):
    """
    Classification of allowed interaction posture for delivery.

    READ_ONLY: Most conservative - system presents information with no
               expectation of interaction. Used for HOLD regime.
    ACK_ONLY: Simple acknowledgment only - system acknowledges receipt
              but does not expand or elaborate. Used for BLOCKED/DEFERRAL.
    SUPPORTIVE: Gentle, non-directive support - system may offer emotional
                acknowledgment. Used for REFLEXIVE + DE_ESCALATE/STABILIZE.
    CLARIFYING: System may ask clarifying questions. Used for QUESTION discourse.
    INFORMATIVE: System may provide informational content. Used for
                 DETACHED + EXPLANATION.

    READ_ONLY is always safe.
    Interaction mode may only restrict, never expand capability.
    """
    READ_ONLY = "READ_ONLY"
    ACK_ONLY = "ACK_ONLY"
    SUPPORTIVE = "SUPPORTIVE"
    CLARIFYING = "CLARIFYING"
    INFORMATIVE = "INFORMATIVE"


# ============================================================================
# DATACLASSES - Core envelope object
# ============================================================================


@dataclass(frozen=True)
class InteractionDirective:
    """
    P15 output envelope: Interaction mode directive.

    This envelope is read-only and captures the interaction posture
    that constrains downstream delivery. It does NOT affect wording,
    acoustics, or meaning.

    Invariants:
    - If blocked=True, mode must be ACK_ONLY (takes precedence over HOLD)
    - If source_regime is HOLD and NOT blocked, mode must be READ_ONLY
    - source_reason must be a non-empty string
    - mode must be a valid InteractionMode enum value

    Attributes:
        mode: The resolved interaction mode
        source_reason: Human-readable explanation of the mode selection
        blocked: Whether the interaction is blocked (upstream BLOCKED state)
        source_regime: The operational regime from P6 (for tracing)
        source_discourse_act: The discourse act from P7 (for tracing)
        source_grounding_mode: The grounding mode from PO1 (for tracing)
        architectural_phase: Identifier for this phase ("P15")
        version: P15 version string for provenance
        timestamp_utc: ISO-8601 timestamp for audit purposes
        debug: Additional debug/trace information
    """

    mode: InteractionMode
    source_reason: str
    blocked: bool

    # === Provenance ===
    source_regime: str = ""
    source_discourse_act: str = ""
    source_grounding_mode: str = ""

    # === Metadata ===
    architectural_phase: str = "P15"
    version: str = P15_VERSION
    timestamp_utc: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate InteractionDirective invariants."""
        # Mode must be set
        if self.mode is None:
            raise ValueError("InteractionDirective.mode cannot be None")

        # Validate mode is a valid enum value
        if not isinstance(self.mode, InteractionMode):
            raise ValueError(
                f"InteractionDirective.mode must be InteractionMode, "
                f"got {type(self.mode).__name__}"
            )

        # source_reason must be a non-empty string
        if not isinstance(self.source_reason, str) or not self.source_reason.strip():
            raise ValueError(
                "InteractionDirective.source_reason must be a non-empty string"
            )

        # blocked must be bool
        if not isinstance(self.blocked, bool):
            raise ValueError(
                f"InteractionDirective.blocked must be bool, "
                f"got {type(self.blocked).__name__}"
            )

        # INVARIANT: If blocked=True, mode must be ACK_ONLY
        if self.blocked and self.mode != InteractionMode.ACK_ONLY:
            raise ValueError(
                f"InteractionDirective: blocked=True requires mode=ACK_ONLY, "
                f"got {self.mode.value}"
            )

        # INVARIANT: If source_regime is HOLD and NOT blocked, mode must be READ_ONLY
        # (blocked takes precedence over HOLD regime constraint)
        if (self.source_regime == "HOLD" and
                not self.blocked and
                self.mode != InteractionMode.READ_ONLY):
            raise ValueError(
                f"InteractionDirective: HOLD regime requires mode=READ_ONLY, "
                f"got {self.mode.value}"
            )

    def is_read_only(self) -> bool:
        """Check if mode is READ_ONLY (most conservative)."""
        return self.mode == InteractionMode.READ_ONLY

    def is_ack_only(self) -> bool:
        """Check if mode is ACK_ONLY."""
        return self.mode == InteractionMode.ACK_ONLY

    def is_supportive(self) -> bool:
        """Check if mode is SUPPORTIVE."""
        return self.mode == InteractionMode.SUPPORTIVE

    def is_clarifying(self) -> bool:
        """Check if mode is CLARIFYING."""
        return self.mode == InteractionMode.CLARIFYING

    def is_informative(self) -> bool:
        """Check if mode is INFORMATIVE."""
        return self.mode == InteractionMode.INFORMATIVE

    def allows_questions(self) -> bool:
        """Check if questions are allowed in this mode."""
        return self.mode == InteractionMode.CLARIFYING

    def allows_information(self) -> bool:
        """Check if informational content is allowed in this mode."""
        return self.mode == InteractionMode.INFORMATIVE

    def allows_support(self) -> bool:
        """Check if supportive content is allowed in this mode."""
        return self.mode in (
            InteractionMode.SUPPORTIVE,
            InteractionMode.INFORMATIVE,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "mode": self.mode.value,
            "source_reason": self.source_reason,
            "blocked": self.blocked,
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "source_grounding_mode": self.source_grounding_mode,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
            "timestamp_utc": self.timestamp_utc,
            "debug": self.debug,
            # Computed
            "is_read_only": self.is_read_only(),
            "is_ack_only": self.is_ack_only(),
            "is_supportive": self.is_supportive(),
            "is_clarifying": self.is_clarifying(),
            "is_informative": self.is_informative(),
            "allows_questions": self.allows_questions(),
            "allows_information": self.allows_information(),
            "allows_support": self.allows_support(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_read_only_directive(
    source_reason: str = "Defaulting to READ_ONLY",
    source_regime: str = "UNKNOWN",
    source_discourse_act: str = "UNKNOWN",
    source_grounding_mode: str = "UNKNOWN",
    timestamp_utc: str = "",
) -> InteractionDirective:
    """
    Create a READ_ONLY interaction directive (most conservative).

    This is the safest possible directive and is used when:
    - HOLD regime is active
    - Upstream phases are missing
    - No specific interaction mode applies
    """
    return InteractionDirective(
        mode=InteractionMode.READ_ONLY,
        source_reason=source_reason,
        blocked=False,
        source_regime=source_regime,
        source_discourse_act=source_discourse_act,
        source_grounding_mode=source_grounding_mode,
        timestamp_utc=timestamp_utc,
    )


def get_ack_only_directive(
    source_reason: str = "Blocked state requires ACK_ONLY",
    source_regime: str = "UNKNOWN",
    source_discourse_act: str = "UNKNOWN",
    source_grounding_mode: str = "UNKNOWN",
    blocked: bool = True,
    timestamp_utc: str = "",
) -> InteractionDirective:
    """
    Create an ACK_ONLY interaction directive for blocked states.

    This directive is used when:
    - Upstream phases report BLOCKED state
    - DEFERRAL discourse act is active
    """
    return InteractionDirective(
        mode=InteractionMode.ACK_ONLY,
        source_reason=source_reason,
        blocked=blocked,
        source_regime=source_regime,
        source_discourse_act=source_discourse_act,
        source_grounding_mode=source_grounding_mode,
        timestamp_utc=timestamp_utc,
    )


# Public exports
__all__ = [
    # Enums
    "InteractionMode",
    # Dataclasses
    "InteractionDirective",
    # Constants - version
    "P15_VERSION",
    # Helper functions
    "get_read_only_directive",
    "get_ack_only_directive",
]
