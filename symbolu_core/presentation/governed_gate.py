"""GOVERNED Mode Gate - Output Control Based on P12 Audit.

This module implements the GOVERNED mode decision gate that controls
whether output is released or blocked based on P12 audit results.

Architecture:
------------
    AcousticChainResult → GovernedGate → GateDecision
                              ↓
                    [ALLOW | BLOCK | WARN]

Design Principles:
-----------------
1. Fail-closed: Ambiguous cases → BLOCK
2. CRITICAL violations → Always BLOCK in GOVERNED mode
3. MAJOR violations → WARN in GOVERNED, ALLOW in OPEN
4. Full traceability of all decisions
5. No semantic interpretation (pure rule application)

Authority Model:
---------------
- GovernedGate reads AcousticChainResult (immutable)
- GovernedGate produces GateDecision (audit trail)
- GovernedGate NEVER modifies upstream data
- Blocking is advisory (caller decides final action)

Usage:
    from symbolu_core.presentation.governed_gate import GovernedGate, GateMode

    gate = GovernedGate(mode=GateMode.GOVERNED)
    decision = gate.evaluate(chain_result)

    if decision.should_block:
        # Handle blocked output
        return decision.fallback_response
    else:
        # Proceed with output
        render(chain_result.acoustic_frame)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, unique
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from symbolu_core.presentation.acoustic_chain import AcousticChainResult
from symbolu_core.mechanical.pipeline.p12_consistency.p12_consistency_schema import (
    P12Violation,
    ViolationSeverity,
    ViolationType,
)


# =============================================================================
# GATE MODE ENUM
# =============================================================================


@unique
class GateMode(str, Enum):
    """Gate operation mode.

    GOVERNED: Production mode - strict enforcement, blocks on CRITICAL
    OPEN: Development mode - permissive, allows with warnings
    AUDIT_ONLY: Logging mode - never blocks, always logs
    """
    GOVERNED = "governed"    # Strict: CRITICAL → BLOCK
    OPEN = "open"            # Permissive: All → ALLOW (with warnings)
    AUDIT_ONLY = "audit"     # Passive: Log only, never block


# =============================================================================
# GATE DECISION ENUM
# =============================================================================


@unique
class GateAction(str, Enum):
    """Gate decision action."""
    ALLOW = "allow"      # Output is released
    BLOCK = "block"      # Output is blocked
    WARN = "warn"        # Output is released with warnings


# =============================================================================
# GATE DECISION DATACLASS
# =============================================================================


@dataclass(frozen=True)
class GateDecision:
    """Result of gate evaluation.

    Attributes:
        action: The gate decision (ALLOW, BLOCK, WARN)
        mode: The gate mode used for evaluation
        reason: Human-readable reason for decision
        violations: List of violations that influenced decision
        critical_count: Number of CRITICAL violations
        major_count: Number of MAJOR violations
        minor_count: Number of MINOR violations
        fallback_response: Suggested fallback if blocked
        timestamp: UTC timestamp of decision
        debug: Additional debug information
    """
    action: GateAction
    mode: GateMode
    reason: str
    violations: List[P12Violation]
    critical_count: int
    major_count: int
    minor_count: int
    fallback_response: Optional[str]
    timestamp: str
    debug: Dict[str, Any] = field(default_factory=dict)

    @property
    def should_block(self) -> bool:
        """Check if output should be blocked."""
        return self.action == GateAction.BLOCK

    @property
    def should_warn(self) -> bool:
        """Check if warnings should be logged."""
        return self.action in (GateAction.WARN, GateAction.BLOCK)

    @property
    def total_violations(self) -> int:
        """Total number of violations."""
        return self.critical_count + self.major_count + self.minor_count

    @property
    def is_clean(self) -> bool:
        """Check if no violations were found."""
        return self.total_violations == 0


# =============================================================================
# FALLBACK RESPONSES
# =============================================================================

# Default fallback responses by violation type
FALLBACK_RESPONSES: Dict[ViolationType, str] = {
    ViolationType.REGIME_ACOUSTIC_MISMATCH: (
        "I need to pause and reconsider my response."
    ),
    ViolationType.DISCOURSE_PROSODY_MISMATCH: (
        "Let me rephrase that more carefully."
    ),
    ViolationType.UNCERTAINTY_VIOLATION: (
        "I'm not certain about that."
    ),
    ViolationType.AUTHORITY_ESCALATION: (
        "I should defer to a human on this."
    ),
    ViolationType.SUPPRESSION_VIOLATION: (
        "I need to be more measured in my response."
    ),
    ViolationType.LEXICAL_PROSODIC_INCOMPATIBILITY: (
        "Let me express that differently."
    ),
    ViolationType.GROUNDING_VIOLATION: (
        "I should reconsider my approach here."
    ),
}

# Default fallback when no specific type matches
DEFAULT_FALLBACK = "I need a moment to reconsider."


# =============================================================================
# GOVERNED GATE
# =============================================================================


class GovernedGate:
    """GOVERNED mode decision gate for output control.

    This gate evaluates AcousticChainResult and decides whether output
    should be released, blocked, or released with warnings.

    Decision Rules:
    ---------------
    GOVERNED mode:
        - CRITICAL violations → BLOCK
        - MAJOR violations (>= 2) → BLOCK
        - MAJOR violations (1) → WARN
        - MINOR violations → ALLOW

    OPEN mode:
        - CRITICAL violations → WARN
        - MAJOR violations → WARN
        - MINOR violations → ALLOW

    AUDIT_ONLY mode:
        - All violations → ALLOW (logged only)

    Example:
        gate = GovernedGate(mode=GateMode.GOVERNED)
        decision = gate.evaluate(chain_result)

        if decision.should_block:
            return decision.fallback_response
        else:
            return render(chain_result)
    """

    def __init__(self, mode: GateMode = GateMode.GOVERNED) -> None:
        """Initialize the governed gate.

        Args:
            mode: The gate operation mode (default: GOVERNED)
        """
        self._mode = mode

    @property
    def mode(self) -> GateMode:
        """Get the current gate mode."""
        return self._mode

    def evaluate(self, result: AcousticChainResult) -> GateDecision:
        """Evaluate chain result and produce gate decision.

        Args:
            result: The AcousticChainResult from the acoustic chain

        Returns:
            GateDecision with action and metadata

        Raises:
            ValueError: If result is None
        """
        if result is None:
            raise ValueError("result cannot be None")

        # Count violations by severity
        violations = result.audit_report.violations
        critical_count = sum(
            1 for v in violations if v.severity == ViolationSeverity.CRITICAL
        )
        major_count = sum(
            1 for v in violations if v.severity == ViolationSeverity.MAJOR
        )
        minor_count = sum(
            1 for v in violations if v.severity == ViolationSeverity.MINOR
        )

        # Determine action based on mode and violations
        action, reason = self._determine_action(
            critical_count, major_count, minor_count
        )

        # Generate fallback response if blocking
        fallback = None
        if action == GateAction.BLOCK:
            fallback = self._generate_fallback(violations)

        # Build debug info
        debug = {
            "mode": self._mode.value,
            "source_regime": result.regime_envelope.regime.value,
            "source_discourse_act": result.discourse_envelope.act.value,
            "acoustic_regime": result.acoustic_frame.regime.value,
            "is_consistent": result.is_consistent,
        }

        return GateDecision(
            action=action,
            mode=self._mode,
            reason=reason,
            violations=list(violations),
            critical_count=critical_count,
            major_count=major_count,
            minor_count=minor_count,
            fallback_response=fallback,
            timestamp=datetime.now(timezone.utc).isoformat(),
            debug=debug,
        )

    def _determine_action(
        self,
        critical_count: int,
        major_count: int,
        minor_count: int,
    ) -> tuple:
        """Determine gate action based on violation counts.

        Returns:
            Tuple of (GateAction, reason_string)
        """
        if self._mode == GateMode.AUDIT_ONLY:
            # Audit mode never blocks
            if critical_count > 0 or major_count > 0:
                return (
                    GateAction.ALLOW,
                    f"AUDIT_ONLY mode: {critical_count} critical, {major_count} major (logged)"
                )
            return (GateAction.ALLOW, "No violations (audit mode)")

        if self._mode == GateMode.OPEN:
            # Open mode warns but doesn't block
            if critical_count > 0:
                return (
                    GateAction.WARN,
                    f"OPEN mode: {critical_count} critical violations (warning only)"
                )
            if major_count > 0:
                return (
                    GateAction.WARN,
                    f"OPEN mode: {major_count} major violations (warning only)"
                )
            return (GateAction.ALLOW, "No significant violations")

        # GOVERNED mode - strict enforcement
        if critical_count > 0:
            return (
                GateAction.BLOCK,
                f"GOVERNED mode: {critical_count} CRITICAL violations → BLOCKED"
            )

        if major_count >= 2:
            return (
                GateAction.BLOCK,
                f"GOVERNED mode: {major_count} MAJOR violations → BLOCKED"
            )

        if major_count == 1:
            return (
                GateAction.WARN,
                f"GOVERNED mode: 1 MAJOR violation → ALLOWED with WARNING"
            )

        if minor_count > 0:
            return (
                GateAction.ALLOW,
                f"GOVERNED mode: {minor_count} minor violations → ALLOWED"
            )

        return (GateAction.ALLOW, "No violations detected")

    def _generate_fallback(self, violations: List[P12Violation]) -> str:
        """Generate appropriate fallback response for blocked output.

        Selects fallback based on the most severe violation type.
        """
        if not violations:
            return DEFAULT_FALLBACK

        # Find most severe violation
        critical = [v for v in violations if v.severity == ViolationSeverity.CRITICAL]
        if critical:
            violation_type = critical[0].violation_type
        else:
            major = [v for v in violations if v.severity == ViolationSeverity.MAJOR]
            if major:
                violation_type = major[0].violation_type
            else:
                violation_type = violations[0].violation_type

        return FALLBACK_RESPONSES.get(violation_type, DEFAULT_FALLBACK)


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def evaluate_governed(result: AcousticChainResult) -> GateDecision:
    """Evaluate result in GOVERNED mode (strict).

    Args:
        result: The AcousticChainResult to evaluate

    Returns:
        GateDecision with strict enforcement
    """
    gate = GovernedGate(mode=GateMode.GOVERNED)
    return gate.evaluate(result)


def evaluate_open(result: AcousticChainResult) -> GateDecision:
    """Evaluate result in OPEN mode (permissive).

    Args:
        result: The AcousticChainResult to evaluate

    Returns:
        GateDecision with permissive enforcement
    """
    gate = GovernedGate(mode=GateMode.OPEN)
    return gate.evaluate(result)


def should_block_output(result: AcousticChainResult) -> bool:
    """Quick check if output should be blocked in GOVERNED mode.

    Args:
        result: The AcousticChainResult to check

    Returns:
        True if output should be blocked
    """
    decision = evaluate_governed(result)
    return decision.should_block


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Main classes
    "GovernedGate",
    "GateDecision",
    # Enums
    "GateMode",
    "GateAction",
    # Convenience functions
    "evaluate_governed",
    "evaluate_open",
    "should_block_output",
    # Fallback responses
    "FALLBACK_RESPONSES",
    "DEFAULT_FALLBACK",
]
