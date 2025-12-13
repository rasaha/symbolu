"""
P12 - Acoustic-Prosodic Consistency Validator Schema Definitions

P12 is an AUDIT-ONLY phase. It validates consistency between:
- Governance layers (PO1-P7)
- Acoustic intent (P10)
- Prosodic evidence (P11)

P12's responsibility is to:
- Validate that acoustic parameters do not contradict regime constraints
- Validate that prosodic evidence does not contradict discourse act constraints
- Ensure uncertainty preservation rules are respected
- Detect safety invariant violations (no escalation, no certainty inflation)
- Produce a read-only P12ConsistencyReport

P12 does NOT:
- Modify or correct any data
- Override, mutate, or reinterpret upstream decisions
- Generate speech or acoustic output
- Execute actions
- Call LLMs
- Introduce probabilistic behavior

Design Principles:
- Audit-Only: P12 observes and validates, never modifies
- Deterministic: No LLM calls, no probabilistic sampling
- Subordinate: Cannot override PO1-P11 constraints
- Fail-Closed: Assumes violation on any error
- Truth-Preserving: Reports what IS, not what SHOULD BE

Authority Model:
- Authority flows: PO1 -> ... -> P10 -> P11 -> P12 (read-only)
- P12 receives signals from all upstream phases (read-only)
- P12 cannot override, mutate, or reinterpret any upstream decision
- P12 produces P12ConsistencyReport (read-only, non-actuating)
- Violations are reported upward, never corrected

CRITICAL ARCHITECTURAL INVARIANT:
    P12 is not an intelligence layer.
    It is a truth-preserving audit layer that ensures Symbol-U
    never sounds more certain, forceful, or authoritative
    than it is allowed to be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ============================================================================
# VERSION CONSTANT
# ============================================================================


P12_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Violation severity classification
# ============================================================================


class ViolationSeverity(str, Enum):
    """
    Severity levels for consistency violations.

    CRITICAL: Safety or authority breach - must be addressed immediately
    MAJOR: Regime or discourse contradiction - significant issue
    MINOR: Stylistic inconsistency - lower priority
    INFO: Logged observation only - informational
    """
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"


class ViolationType(str, Enum):
    """
    Classification of violation types for categorization.

    REGIME_ACOUSTIC_MISMATCH: Acoustic parameters contradict regime
    DISCOURSE_PROSODY_MISMATCH: Prosodic evidence contradicts discourse act
    UNCERTAINTY_VIOLATION: Uncertainty preservation rules violated
    LEXICAL_PROSODIC_INCOMPATIBILITY: Lexical-prosodic pairing incompatible
    AUTHORITY_ESCALATION: Prosody implies unauthorized authority
    SAFETY_VIOLATION: Safety invariant breached
    GROUNDING_VIOLATION: Grounding constraints violated
    SUPPRESSION_VIOLATION: Required suppression not applied
    """
    REGIME_ACOUSTIC_MISMATCH = "REGIME_ACOUSTIC_MISMATCH"
    DISCOURSE_PROSODY_MISMATCH = "DISCOURSE_PROSODY_MISMATCH"
    UNCERTAINTY_VIOLATION = "UNCERTAINTY_VIOLATION"
    LEXICAL_PROSODIC_INCOMPATIBILITY = "LEXICAL_PROSODIC_INCOMPATIBILITY"
    AUTHORITY_ESCALATION = "AUTHORITY_ESCALATION"
    SAFETY_VIOLATION = "SAFETY_VIOLATION"
    GROUNDING_VIOLATION = "GROUNDING_VIOLATION"
    SUPPRESSION_VIOLATION = "SUPPRESSION_VIOLATION"


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class P12Violation:
    """
    A single consistency violation detected by P12.

    Represents one specific inconsistency between layers that
    violates architectural invariants.

    Attributes:
        severity: The severity level (CRITICAL/MAJOR/MINOR/INFO)
        violation_type: The type of violation detected
        invariant_name: Name of the invariant that was violated
        source_phase: The upstream phase where the issue originates
        target_phase: The phase against which validation failed
        description: Human-readable description of the violation
        evidence: Supporting evidence for the violation detection
    """
    severity: ViolationSeverity
    violation_type: ViolationType
    invariant_name: str
    source_phase: str
    target_phase: str
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate P12Violation invariants."""
        # Validate severity is a valid enum
        if not isinstance(self.severity, ViolationSeverity):
            raise ValueError(
                f"P12Violation.severity must be ViolationSeverity, "
                f"got {type(self.severity).__name__}"
            )

        # Validate violation_type is a valid enum
        if not isinstance(self.violation_type, ViolationType):
            raise ValueError(
                f"P12Violation.violation_type must be ViolationType, "
                f"got {type(self.violation_type).__name__}"
            )

        # Validate invariant_name is non-empty string
        if not isinstance(self.invariant_name, str) or not self.invariant_name.strip():
            raise ValueError(
                "P12Violation.invariant_name must be a non-empty string"
            )

        # Validate source_phase is non-empty string
        if not isinstance(self.source_phase, str) or not self.source_phase.strip():
            raise ValueError(
                "P12Violation.source_phase must be a non-empty string"
            )

        # Validate target_phase is non-empty string
        if not isinstance(self.target_phase, str) or not self.target_phase.strip():
            raise ValueError(
                "P12Violation.target_phase must be a non-empty string"
            )

        # Validate description is non-empty string
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(
                "P12Violation.description must be a non-empty string"
            )

    def is_critical(self) -> bool:
        """Check if this is a CRITICAL violation."""
        return self.severity == ViolationSeverity.CRITICAL

    def is_major(self) -> bool:
        """Check if this is a MAJOR violation."""
        return self.severity == ViolationSeverity.MAJOR

    def is_minor(self) -> bool:
        """Check if this is a MINOR violation."""
        return self.severity == ViolationSeverity.MINOR

    def is_info(self) -> bool:
        """Check if this is an INFO observation."""
        return self.severity == ViolationSeverity.INFO

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "severity": self.severity.value,
            "violation_type": self.violation_type.value,
            "invariant_name": self.invariant_name,
            "source_phase": self.source_phase,
            "target_phase": self.target_phase,
            "description": self.description,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class P12Warning:
    """
    A non-critical warning detected by P12.

    Represents a potential issue that does not rise to violation level
    but should be logged for observability.

    Attributes:
        warning_code: Unique code identifying the warning type
        description: Human-readable description of the warning
        source_phase: The phase where the potential issue was detected
        evidence: Supporting evidence for the warning
    """
    warning_code: str
    description: str
    source_phase: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate P12Warning invariants."""
        # Validate warning_code is non-empty string
        if not isinstance(self.warning_code, str) or not self.warning_code.strip():
            raise ValueError(
                "P12Warning.warning_code must be a non-empty string"
            )

        # Validate description is non-empty string
        if not isinstance(self.description, str) or not self.description.strip():
            raise ValueError(
                "P12Warning.description must be a non-empty string"
            )

        # Validate source_phase is non-empty string
        if not isinstance(self.source_phase, str) or not self.source_phase.strip():
            raise ValueError(
                "P12Warning.source_phase must be a non-empty string"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "warning_code": self.warning_code,
            "description": self.description,
            "source_phase": self.source_phase,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class P12ConsistencyReport:
    """
    P12 output envelope: Consistency validation report.

    This envelope is read-only and captures the results of consistency
    validation across all governance, acoustic, and prosodic layers.
    It does NOT modify, correct, or override any upstream data.

    Invariants:
    - is_consistent is False if any violations exist
    - violations list contains all detected violations
    - warnings list contains non-critical observations
    - checked_invariants lists all invariants that were validated
    - audit_notes provides additional context for debugging

    Attributes:
        is_consistent: True if no violations detected, False otherwise
        violations: List of all detected violations
        warnings: List of non-critical warnings
        checked_invariants: List of invariant names that were checked
        audit_notes: Additional context and metadata for debugging
        source_regime: The operational regime from P6 (for tracing)
        source_discourse_act: The discourse act from P7 (for tracing)
        source_intent: The intent type from PO2 (for tracing)
        architectural_phase: Identifier for this phase ("P12")
        version: P12 version string for provenance
        timestamp_utc: ISO-8601 timestamp for audit purposes
        debug: Additional debug/trace information
    """
    is_consistent: bool
    violations: List[P12Violation]
    warnings: List[P12Warning]
    checked_invariants: List[str]
    audit_notes: Dict[str, Any]
    source_regime: str
    source_discourse_act: str
    source_intent: Optional[str]
    architectural_phase: str = "P12"
    version: str = P12_VERSION
    timestamp_utc: str = ""
    debug: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate P12ConsistencyReport invariants."""
        # Validate is_consistent is bool
        if not isinstance(self.is_consistent, bool):
            raise ValueError(
                f"P12ConsistencyReport.is_consistent must be bool, "
                f"got {type(self.is_consistent).__name__}"
            )

        # Validate violations is a list
        if not isinstance(self.violations, list):
            raise ValueError(
                f"P12ConsistencyReport.violations must be list, "
                f"got {type(self.violations).__name__}"
            )

        # Validate each violation is a P12Violation
        for i, violation in enumerate(self.violations):
            if not isinstance(violation, P12Violation):
                raise ValueError(
                    f"P12ConsistencyReport.violations[{i}] must be P12Violation, "
                    f"got {type(violation).__name__}"
                )

        # Validate warnings is a list
        if not isinstance(self.warnings, list):
            raise ValueError(
                f"P12ConsistencyReport.warnings must be list, "
                f"got {type(self.warnings).__name__}"
            )

        # Validate each warning is a P12Warning
        for i, warning in enumerate(self.warnings):
            if not isinstance(warning, P12Warning):
                raise ValueError(
                    f"P12ConsistencyReport.warnings[{i}] must be P12Warning, "
                    f"got {type(warning).__name__}"
                )

        # Validate checked_invariants is a list of strings
        if not isinstance(self.checked_invariants, list):
            raise ValueError(
                f"P12ConsistencyReport.checked_invariants must be list, "
                f"got {type(self.checked_invariants).__name__}"
            )
        for i, inv in enumerate(self.checked_invariants):
            if not isinstance(inv, str):
                raise ValueError(
                    f"P12ConsistencyReport.checked_invariants[{i}] must be str, "
                    f"got {type(inv).__name__}"
                )

        # Validate audit_notes is a dict
        if not isinstance(self.audit_notes, dict):
            raise ValueError(
                f"P12ConsistencyReport.audit_notes must be dict, "
                f"got {type(self.audit_notes).__name__}"
            )

        # Validate source_regime is non-empty string
        if not isinstance(self.source_regime, str) or not self.source_regime.strip():
            raise ValueError(
                "P12ConsistencyReport.source_regime must be a non-empty string"
            )

        # Validate source_discourse_act is non-empty string
        if not isinstance(self.source_discourse_act, str) or not self.source_discourse_act.strip():
            raise ValueError(
                "P12ConsistencyReport.source_discourse_act must be a non-empty string"
            )

        # source_intent can be None or string
        if self.source_intent is not None and not isinstance(self.source_intent, str):
            raise ValueError(
                f"P12ConsistencyReport.source_intent must be str or None, "
                f"got {type(self.source_intent).__name__}"
            )

        # Validate consistency: is_consistent should be False if violations exist
        if self.violations and self.is_consistent:
            raise ValueError(
                "P12ConsistencyReport.is_consistent must be False when violations exist"
            )

    def has_violations(self) -> bool:
        """Check if any violations were detected."""
        return len(self.violations) > 0

    def has_warnings(self) -> bool:
        """Check if any warnings were detected."""
        return len(self.warnings) > 0

    def has_critical_violations(self) -> bool:
        """Check if any CRITICAL violations were detected."""
        return any(v.is_critical() for v in self.violations)

    def has_major_violations(self) -> bool:
        """Check if any MAJOR violations were detected."""
        return any(v.is_major() for v in self.violations)

    def get_violations_by_severity(self, severity: ViolationSeverity) -> List[P12Violation]:
        """Get all violations of a specific severity level."""
        return [v for v in self.violations if v.severity == severity]

    def get_violations_by_type(self, violation_type: ViolationType) -> List[P12Violation]:
        """Get all violations of a specific type."""
        return [v for v in self.violations if v.violation_type == violation_type]

    def get_critical_violations(self) -> List[P12Violation]:
        """Get all CRITICAL violations."""
        return self.get_violations_by_severity(ViolationSeverity.CRITICAL)

    def get_major_violations(self) -> List[P12Violation]:
        """Get all MAJOR violations."""
        return self.get_violations_by_severity(ViolationSeverity.MAJOR)

    def get_minor_violations(self) -> List[P12Violation]:
        """Get all MINOR violations."""
        return self.get_violations_by_severity(ViolationSeverity.MINOR)

    def get_info_violations(self) -> List[P12Violation]:
        """Get all INFO observations."""
        return self.get_violations_by_severity(ViolationSeverity.INFO)

    def violation_count(self) -> int:
        """Get total number of violations."""
        return len(self.violations)

    def warning_count(self) -> int:
        """Get total number of warnings."""
        return len(self.warnings)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "is_consistent": self.is_consistent,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "checked_invariants": self.checked_invariants,
            "audit_notes": self.audit_notes,
            "source_regime": self.source_regime,
            "source_discourse_act": self.source_discourse_act,
            "source_intent": self.source_intent,
            "architectural_phase": self.architectural_phase,
            "version": self.version,
            "timestamp_utc": self.timestamp_utc,
            "debug": self.debug,
            "violation_count": self.violation_count(),
            "warning_count": self.warning_count(),
            "has_critical": self.has_critical_violations(),
            "has_major": self.has_major_violations(),
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_violation(
    severity: ViolationSeverity,
    violation_type: ViolationType,
    invariant_name: str,
    source_phase: str,
    target_phase: str,
    description: str,
    evidence: Optional[Dict[str, Any]] = None,
) -> P12Violation:
    """
    Helper function to create a P12Violation.

    Args:
        severity: Severity level of the violation.
        violation_type: Type of violation.
        invariant_name: Name of the violated invariant.
        source_phase: Upstream phase where issue originates.
        target_phase: Phase against which validation failed.
        description: Human-readable description.
        evidence: Optional supporting evidence.

    Returns:
        A new P12Violation instance.
    """
    return P12Violation(
        severity=severity,
        violation_type=violation_type,
        invariant_name=invariant_name,
        source_phase=source_phase,
        target_phase=target_phase,
        description=description,
        evidence=evidence or {},
    )


def create_warning(
    warning_code: str,
    description: str,
    source_phase: str,
    evidence: Optional[Dict[str, Any]] = None,
) -> P12Warning:
    """
    Helper function to create a P12Warning.

    Args:
        warning_code: Unique code for the warning type.
        description: Human-readable description.
        source_phase: Phase where issue was detected.
        evidence: Optional supporting evidence.

    Returns:
        A new P12Warning instance.
    """
    return P12Warning(
        warning_code=warning_code,
        description=description,
        source_phase=source_phase,
        evidence=evidence or {},
    )


# Public exports
__all__ = [
    # Enums
    "ViolationSeverity",
    "ViolationType",
    # Dataclasses
    "P12Violation",
    "P12Warning",
    "P12ConsistencyReport",
    # Constants
    "P12_VERSION",
    # Helper functions
    "create_violation",
    "create_warning",
]
