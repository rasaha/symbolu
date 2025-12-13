"""
P17 - Semantic Integrity Monitor Schema Definitions

P17 is a post-lexical, observation-only governance phase.
It detects contradictions, drift, and integrity issues between upstream
semantic/lexical decisions WITHOUT modifying any upstream state.

P17's responsibility is to:
- Detect contradictions between discourse intent and lexical choices
- Flag uncertainty collapse (UNCERTAINTY slot but certainty lexemes)
- Identify mode/authority drift (RELATIONAL treated as REFLEXIVE)
- Detect causal inference leakage when forbidden by regime
- Identify tone escalation signals even from valid lexical pools

P17 does NOT:
- Modify upstream decisions
- Block pipeline execution
- Perform semantic interpretation
- Call LLMs
- Introduce probabilistic behavior

Design Principles:
- Observation-Only: Reads upstream state, produces report, changes nothing
- Deterministic: No LLM calls, no probabilistic sampling
- Conservative: False positives acceptable, severity levels for triage
- Authority-Respecting: Cannot override PO1-P9 constraints

Authority Model:
- Authority flows: PO1 -> PO2 -> ... -> P9 -> (P17 observes)
- P17 receives read-only signals from PO1, P6, P7, P8, P9
- P17 produces P17IntegrityReport for downstream gating decisions
- P17 report is advisory; later phases may gate on it but P17 never blocks
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# VERSION
# ============================================================================

P17_VERSION = "1.0.0"


# ============================================================================
# ENUMS - Issue type and severity classification
# ============================================================================


class IntegrityIssueType(str, Enum):
    """
    Classification of semantic integrity issues detected by P17.

    CONTRADICTION: Lexical choices contradict semantic intent (P8 vs P9)
    UNCERTAINTY_COLLAPSE: UNCERTAINTY slot present but certainty markers in P9
    CAUSE_LEAK: Causal inference implied when regime/discourse blocks CAUSE
    AUTHORITY_DRIFT: RELATIONAL content treated as REFLEXIVE assertions
    TONE_ESCALATION: Authority/certainty intensifiers detected in lexemes
    INSUFFICIENT_EVIDENCE: Required upstream artifacts missing for analysis
    """
    CONTRADICTION = "CONTRADICTION"
    UNCERTAINTY_COLLAPSE = "UNCERTAINTY_COLLAPSE"
    CAUSE_LEAK = "CAUSE_LEAK"
    AUTHORITY_DRIFT = "AUTHORITY_DRIFT"
    TONE_ESCALATION = "TONE_ESCALATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Severity(str, Enum):
    """
    Severity level for integrity issues.

    INFO: Informational, likely false positive or edge case
    WARN: Warning, possible drift that warrants attention
    HIGH: High severity, clear violation that should gate insight depth
    """
    INFO = "INFO"
    WARN = "WARN"
    HIGH = "HIGH"


# ============================================================================
# DATACLASSES - Core envelope objects
# ============================================================================


@dataclass(frozen=True)
class IntegrityIssue:
    """
    A single integrity issue detected by P17.

    Represents one detected contradiction, drift, or integrity violation
    between upstream semantic/lexical decisions.

    Attributes:
        issue_type: The type of integrity issue detected
        severity: Severity level (INFO/WARN/HIGH)
        message: Human-readable description of the issue
        evidence_paths: List of upstream paths involved (e.g., "p8.slots.UNCERTAINTY", "p9.selections.STATE")
        clause_index: Optional clause index if issue is clause-specific
    """
    issue_type: IntegrityIssueType
    severity: Severity
    message: str
    evidence_paths: Tuple[str, ...]
    clause_index: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate IntegrityIssue invariants."""
        # issue_type must be set and valid
        if self.issue_type is None:
            raise ValueError("IntegrityIssue.issue_type cannot be None")
        if not isinstance(self.issue_type, IntegrityIssueType):
            raise ValueError(
                f"IntegrityIssue.issue_type must be IntegrityIssueType, "
                f"got {type(self.issue_type).__name__}"
            )

        # severity must be set and valid
        if self.severity is None:
            raise ValueError("IntegrityIssue.severity cannot be None")
        if not isinstance(self.severity, Severity):
            raise ValueError(
                f"IntegrityIssue.severity must be Severity, "
                f"got {type(self.severity).__name__}"
            )

        # message must be non-empty string
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError(
                "IntegrityIssue.message must be a non-empty string"
            )

        # evidence_paths must be a tuple
        if not isinstance(self.evidence_paths, tuple):
            raise ValueError(
                "IntegrityIssue.evidence_paths must be a tuple"
            )

        # clause_index must be non-negative if provided
        if self.clause_index is not None and self.clause_index < 0:
            raise ValueError(
                f"IntegrityIssue.clause_index must be non-negative, "
                f"got {self.clause_index}"
            )

    def is_high_severity(self) -> bool:
        """Check if this is a HIGH severity issue."""
        return self.severity == Severity.HIGH

    def is_warn(self) -> bool:
        """Check if this is a WARN severity issue."""
        return self.severity == Severity.WARN

    def is_info(self) -> bool:
        """Check if this is an INFO severity issue."""
        return self.severity == Severity.INFO

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "evidence_paths": list(self.evidence_paths),
            "clause_index": self.clause_index,
        }


@dataclass(frozen=True)
class P17IntegrityReport:
    """
    P17 output envelope: Semantic integrity analysis report.

    This envelope is read-only and captures all detected integrity issues
    between upstream semantic/lexical decisions. It does NOT modify any
    upstream state or block pipeline execution directly.

    Invariants:
    - integrity_score must be in [0.0, 1.0]
    - is_clean == True only if no HIGH severity issues present
    - issues tuple is immutable

    Attributes:
        issues: Tuple of detected integrity issues
        integrity_score: Overall integrity score in [0.0, 1.0] (1.0 = clean)
        is_clean: True if no HIGH severity issues detected
        debug: Additional debug/trace information
        version: Schema version for compatibility checking
        architectural_phase: Identifier for this phase ("P17")
    """
    issues: Tuple[IntegrityIssue, ...]
    integrity_score: float
    is_clean: bool
    debug: Dict[str, Any] = field(default_factory=dict)
    version: str = P17_VERSION
    architectural_phase: str = "P17"

    def __post_init__(self) -> None:
        """Validate P17IntegrityReport invariants."""
        # issues must be a tuple
        if not isinstance(self.issues, tuple):
            raise ValueError(
                "P17IntegrityReport.issues must be a tuple"
            )

        # All issues must be IntegrityIssue instances
        for i, issue in enumerate(self.issues):
            if not isinstance(issue, IntegrityIssue):
                raise ValueError(
                    f"P17IntegrityReport.issues[{i}] must be IntegrityIssue, "
                    f"got {type(issue).__name__}"
                )

        # integrity_score must be in [0.0, 1.0]
        if not isinstance(self.integrity_score, (int, float)):
            raise ValueError(
                f"P17IntegrityReport.integrity_score must be numeric, "
                f"got {type(self.integrity_score).__name__}"
            )
        if not 0.0 <= self.integrity_score <= 1.0:
            raise ValueError(
                f"P17IntegrityReport.integrity_score must be in [0.0, 1.0], "
                f"got {self.integrity_score}"
            )

        # is_clean must be consistent with issues
        # is_clean == True requires no HIGH severity issues
        has_high = any(
            issue.severity == Severity.HIGH for issue in self.issues
        )
        if self.is_clean and has_high:
            raise ValueError(
                "P17IntegrityReport.is_clean cannot be True when HIGH "
                "severity issues are present"
            )

    def issue_count(self) -> int:
        """Get the total number of issues detected."""
        return len(self.issues)

    def high_count(self) -> int:
        """Get the number of HIGH severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.HIGH)

    def warn_count(self) -> int:
        """Get the number of WARN severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.WARN)

    def info_count(self) -> int:
        """Get the number of INFO severity issues."""
        return sum(1 for i in self.issues if i.severity == Severity.INFO)

    def get_issues_by_type(
        self, issue_type: IntegrityIssueType
    ) -> List[IntegrityIssue]:
        """Get all issues of a specific type."""
        return [i for i in self.issues if i.issue_type == issue_type]

    def get_issues_by_severity(self, severity: Severity) -> List[IntegrityIssue]:
        """Get all issues of a specific severity."""
        return [i for i in self.issues if i.severity == severity]

    def has_issue_type(self, issue_type: IntegrityIssueType) -> bool:
        """Check if any issues of the given type were detected."""
        return any(i.issue_type == issue_type for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/tracing."""
        return {
            "issues": [i.to_dict() for i in self.issues],
            "issue_count": self.issue_count(),
            "high_count": self.high_count(),
            "warn_count": self.warn_count(),
            "info_count": self.info_count(),
            "integrity_score": self.integrity_score,
            "is_clean": self.is_clean,
            "debug": self.debug,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def create_issue(
    issue_type: IntegrityIssueType,
    severity: Severity,
    message: str,
    evidence_paths: List[str],
    clause_index: Optional[int] = None,
) -> IntegrityIssue:
    """
    Helper to create an IntegrityIssue with list-to-tuple conversion.

    Args:
        issue_type: The type of integrity issue
        severity: Severity level
        message: Human-readable description
        evidence_paths: List of upstream paths involved
        clause_index: Optional clause index

    Returns:
        A validated IntegrityIssue instance
    """
    return IntegrityIssue(
        issue_type=issue_type,
        severity=severity,
        message=message,
        evidence_paths=tuple(evidence_paths),
        clause_index=clause_index,
    )


def create_report(
    issues: List[IntegrityIssue],
    integrity_score: float,
    debug: Optional[Dict[str, Any]] = None,
) -> P17IntegrityReport:
    """
    Helper to create a P17IntegrityReport with automatic is_clean computation.

    Args:
        issues: List of detected integrity issues
        integrity_score: Overall integrity score in [0.0, 1.0]
        debug: Optional debug/trace information

    Returns:
        A validated P17IntegrityReport instance
    """
    has_high = any(issue.severity == Severity.HIGH for issue in issues)
    is_clean = not has_high

    return P17IntegrityReport(
        issues=tuple(issues),
        integrity_score=integrity_score,
        is_clean=is_clean,
        debug=debug or {},
    )


# Public exports
__all__ = [
    # Version
    "P17_VERSION",
    # Enums
    "IntegrityIssueType",
    "Severity",
    # Dataclasses
    "IntegrityIssue",
    "P17IntegrityReport",
    # Helpers
    "create_issue",
    "create_report",
]
