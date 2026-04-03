"""
P30 Output Verification Phase Schema
======================================

Schema definitions for the P30 Output Verification phase within the
Delivery Adaptation Band (P27-P31).

Phase Authority: MEDIUM
Band: Delivery Adaptation (P27-P31)

This phase verifies output quality and constraint compliance:
- P13 safety envelope compliance via RendererComplianceChecker
- P12 acoustic-prosodic consistency validation
- Coherence verification via CoherenceEngine
- Phase authority chain validation

Inputs:
    - P29 final text
    - Pipeline context with phase outputs

Outputs:
    - Verified text (or blocked if violations)
    - Compliance report
    - Coherence metrics
    - Verification pass/fail status

Version: 1.0.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

# =============================================================================
# VERSION
# =============================================================================

VERSION = "1.0.0"


# =============================================================================
# ENUMS
# =============================================================================


class P30Authority(Enum):
    """Authority level for P30 phase decisions."""
    HIGH = "high"       # Verification decision is binding (blocks output)
    MEDIUM = "medium"   # Verification flags issues (default)
    LOW = "low"         # Verification is advisory


class VerificationStatus(Enum):
    """Overall verification status."""
    PASSED = "passed"           # All checks passed
    PASSED_WITH_WARNINGS = "passed_with_warnings"  # Passed but with warnings
    FAILED = "failed"           # Critical violations, output blocked
    SKIPPED = "skipped"         # Verification skipped


class ViolationSeverity(Enum):
    """Severity of verification violations."""
    CRITICAL = "critical"   # Blocks output
    WARNING = "warning"     # Logged but doesn't block
    INFO = "info"           # Informational only


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass(frozen=True)
class P30Violation:
    """
    A verification violation.
    """
    code: str
    message: str
    severity: ViolationSeverity
    source: str  # Which checker found it
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "source": self.source,
            "details": self.details,
        }


@dataclass(frozen=True)
class P30ComplianceResult:
    """
    Result from compliance checking.
    """
    # Pass/fail status
    passed: bool = True

    # Violations found
    violations: List[P30Violation] = field(default_factory=list)

    # P13 compliance
    p13_compliant: bool = True

    # P12 consistency
    p12_consistent: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
            "p13_compliant": self.p13_compliant,
            "p12_consistent": self.p12_consistent,
        }


@dataclass(frozen=True)
class P30CoherenceResult:
    """
    Result from coherence verification.
    """
    # Coherence score (0-1)
    coherence_score: float = 1.0

    # Semantic stability
    semantic_stability: float = 1.0

    # Persona consistency
    persona_consistent: bool = True

    # Temporal arc score
    temporal_arc_score: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "coherence_score": self.coherence_score,
            "semantic_stability": self.semantic_stability,
            "persona_consistent": self.persona_consistent,
            "temporal_arc_score": self.temporal_arc_score,
        }


@dataclass(frozen=True)
class P30Output:
    """
    Output from P30 Output Verification phase.
    """
    # Verified text (same as input if passed, empty if blocked)
    verified_text: str

    # Verification status
    verification_status: VerificationStatus = VerificationStatus.PASSED

    # Authority level
    authority: P30Authority = P30Authority.MEDIUM

    # Compliance result
    compliance_result: Optional[P30ComplianceResult] = None

    # Coherence result
    coherence_result: Optional[P30CoherenceResult] = None

    # Checks performed
    checks_performed: List[str] = field(default_factory=list)

    # Processing trace
    processing_trace: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "phase": "P30",
            "version": VERSION,
            "verified_text": self.verified_text,
            "verification_status": self.verification_status.value,
            "authority": self.authority.value,
            "compliance_result": self.compliance_result.to_dict() if self.compliance_result else None,
            "coherence_result": self.coherence_result.to_dict() if self.coherence_result else None,
            "checks_performed": self.checks_performed,
            "processing_trace": self.processing_trace,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "VERSION",
    "P30Authority",
    "VerificationStatus",
    "ViolationSeverity",
    "P30Violation",
    "P30ComplianceResult",
    "P30CoherenceResult",
    "P30Output",
]
