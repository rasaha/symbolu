"""
P16 Regression Guard — Contract Schema Definitions

This module defines the immutable contract types for P16:
- P16InputContract: What P16 is permitted to READ (read-only)
- ContractViolation: Record of a contract violation
- HashSnapshot: Stable hash snapshot of upstream authority objects
- AuthorityScope: Enum tagging authority objects by phase

DESIGN PRINCIPLES:
- All dataclasses are FROZEN (immutable)
- Deterministic: No random/time-dependent core fields
- Complete: Captures all authority-bearing decisions
- Serializable: Supports logging/audit
- Explicit: Clear allow-lists and deny-lists
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


# ============================================================================
# VERSION
# ============================================================================

P16_VERSION = "1.0.0"


# ============================================================================
# AUTHORITY SCOPE ENUM
# ============================================================================


class AuthorityScope(str, Enum):
    """
    Tags authority objects by their originating phase.

    Used to track which phase produced each authority decision
    and to ensure hashes are associated with the correct scope.

    Phases PO1-PO3 are "observer" phases (Phase -1, 0, 1).
    Phases P6-P15 are governance/expression phases.
    """
    # Observer phases
    PO1 = "PO1"  # Phase -1: Observer-Observed Grounding
    PO2 = "PO2"  # Phase 0: Intent & Response Posture
    PO3 = "PO3"  # Phase 1: Allowed Actions Contract
    PO4 = "PO4"  # Phase O4: Planner Proposal
    PO5 = "PO5"  # Phase O5: Execution Eligibility

    # Governance phases
    P6 = "P6"    # Regime Selection
    P7 = "P7"    # Discourse Act Resolver
    P8 = "P8"    # Semantic Slot Resolution
    P9 = "P9"    # Lexical Selection
    P10 = "P10"  # Acoustic Parameterization
    P11 = "P11"  # Prosodic Evidence Capture (witness)
    P12 = "P12"  # Consistency Validator (audit)
    P13 = "P13"  # Acoustic Safety Envelope (binding)
    P14 = "P14"  # Surface Realizer
    P15 = "P15"  # Interaction Mode Resolver

    # P16 namespace (allowed write target)
    P16 = "P16"  # Regression Guard Output

    # Meta scopes
    DEBUG = "DEBUG"    # Debug/trace data (append-only)
    METRICS = "METRICS"  # Metrics data (append-only)


class ViolationType(str, Enum):
    """
    Classification of P16 contract violations.

    Each type represents a specific category of unauthorized
    modification or contract breach.
    """
    # Hash integrity violations
    HASH_MISMATCH = "HASH_MISMATCH"
    AUTHORITY_DRIFT = "AUTHORITY_DRIFT"

    # Slot/action violations
    SLOT_EXPANSION = "SLOT_EXPANSION"
    ACTION_EXPANSION = "ACTION_EXPANSION"

    # State violations
    BLOCKED_UNBLOCK = "BLOCKED_UNBLOCK"
    CERTAINTY_AMPLIFICATION = "CERTAINTY_AMPLIFICATION"

    # Write violations
    FORBIDDEN_WRITE = "FORBIDDEN_WRITE"
    APPEND_ONLY_REPLACEMENT = "APPEND_ONLY_REPLACEMENT"

    # Acoustic violations
    ACOUSTIC_ESCALATION = "ACOUSTIC_ESCALATION"
    SAFETY_BOUND_EXCEEDED = "SAFETY_BOUND_EXCEEDED"

    # Contract violations
    CONTRACT_BREACH = "CONTRACT_BREACH"
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"


# ============================================================================
# HASH SNAPSHOT
# ============================================================================


@dataclass(frozen=True)
class ScopeHash:
    """
    Hash of a single authority scope's state.

    Captures the stable hash and metadata for one phase's output.
    """
    scope: AuthorityScope
    hash_value: str
    field_count: int = 0
    is_present: bool = True

    def __post_init__(self) -> None:
        """Validate scope hash invariants."""
        if not isinstance(self.scope, AuthorityScope):
            raise ValueError(
                f"ScopeHash.scope must be AuthorityScope, got {type(self.scope).__name__}"
            )
        if not self.hash_value:
            raise ValueError("ScopeHash.hash_value cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scope": self.scope.value,
            "hash_value": self.hash_value,
            "field_count": self.field_count,
            "is_present": self.is_present,
        }


@dataclass(frozen=True)
class HashSnapshot:
    """
    Immutable snapshot of upstream authority object hashes.

    Captures stable hashes of all authority-bearing objects from PO1-P15.
    Used to detect any mutation or authority drift after P16.

    Fields:
        scope_hashes: Mapping of scope -> hash for each upstream phase
        aggregate_hash: Combined hash of all scopes
        slot_set_hash: Hash of P8 semantic slot set (for slot expansion check)
        safety_bounds_hash: Hash of P13 safety envelope bounds
        captured_at_phase: Phase number when snapshot was captured
        version: Schema version for compatibility

    Invariants:
        - All fields are immutable (frozen dataclass)
        - scope_hashes is a frozenset of ScopeHash tuples
        - aggregate_hash is derived deterministically from scope_hashes
    """
    scope_hashes: FrozenSet[ScopeHash]
    aggregate_hash: str
    slot_set_hash: str = ""
    safety_bounds_hash: str = ""
    blocked_state: bool = False
    uncertainty_present: bool = False
    captured_at_phase: int = 15
    version: str = P16_VERSION

    def __post_init__(self) -> None:
        """Validate snapshot invariants."""
        if not isinstance(self.scope_hashes, frozenset):
            raise ValueError(
                f"HashSnapshot.scope_hashes must be frozenset, "
                f"got {type(self.scope_hashes).__name__}"
            )
        if not self.aggregate_hash:
            raise ValueError("HashSnapshot.aggregate_hash cannot be empty")

    def get_scope_hash(self, scope: AuthorityScope) -> Optional[str]:
        """Get hash for a specific scope."""
        for sh in self.scope_hashes:
            if sh.scope == scope:
                return sh.hash_value
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scope_hashes": sorted(
                [sh.to_dict() for sh in self.scope_hashes],
                key=lambda x: x["scope"]
            ),
            "aggregate_hash": self.aggregate_hash,
            "slot_set_hash": self.slot_set_hash,
            "safety_bounds_hash": self.safety_bounds_hash,
            "blocked_state": self.blocked_state,
            "uncertainty_present": self.uncertainty_present,
            "captured_at_phase": self.captured_at_phase,
            "version": self.version,
        }


# ============================================================================
# CONTRACT VIOLATION
# ============================================================================


@dataclass(frozen=True)
class ContractViolation:
    """
    Immutable record of a single P16 contract violation.

    Each violation captures:
    - Which scope was violated
    - What type of violation occurred
    - The expected and observed values
    - The field path where violation occurred

    This is an audit record, not a correction mechanism.
    """
    scope: AuthorityScope
    violation_type: ViolationType
    field_path: str
    expected: Any
    observed: Any
    reason: str = ""
    severity: str = "ERROR"  # ERROR, WARNING

    def __post_init__(self) -> None:
        """Validate violation record invariants."""
        if not isinstance(self.scope, AuthorityScope):
            raise ValueError(
                f"ContractViolation.scope must be AuthorityScope, "
                f"got {type(self.scope).__name__}"
            )
        if not isinstance(self.violation_type, ViolationType):
            raise ValueError(
                f"ContractViolation.violation_type must be ViolationType, "
                f"got {type(self.violation_type).__name__}"
            )
        if not self.field_path:
            raise ValueError("ContractViolation.field_path cannot be empty")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "scope": self.scope.value,
            "violation_type": self.violation_type.value,
            "field_path": self.field_path,
            "expected": _serialize_value(self.expected),
            "observed": _serialize_value(self.observed),
            "reason": self.reason,
            "severity": self.severity,
        }


# ============================================================================
# INPUT CONTRACT
# ============================================================================


@dataclass(frozen=True)
class P16InputContract:
    """
    Explicit contract defining what P16 may read (read-only) from upstream.

    This contract is IMMUTABLE and defines:
    - Which scopes P16 is permitted to read
    - Which fields within each scope are accessible
    - Which scopes are marked as authority (must not drift)

    P16 operates in READ-ONLY mode for all upstream phases.
    It may only WRITE to ctx.p16, ctx.debug (append), ctx.metrics (append).
    """
    # Scopes P16 may read (all upstream phases)
    readable_scopes: FrozenSet[AuthorityScope] = field(
        default_factory=lambda: frozenset({
            AuthorityScope.PO1,
            AuthorityScope.PO2,
            AuthorityScope.PO3,
            AuthorityScope.PO4,
            AuthorityScope.PO5,
            AuthorityScope.P6,
            AuthorityScope.P7,
            AuthorityScope.P8,
            AuthorityScope.P9,
            AuthorityScope.P10,
            AuthorityScope.P11,
            AuthorityScope.P12,
            AuthorityScope.P13,
            AuthorityScope.P14,
            AuthorityScope.P15,
        })
    )

    # Scopes that are authority-bearing (hashes must not change)
    authority_scopes: FrozenSet[AuthorityScope] = field(
        default_factory=lambda: frozenset({
            AuthorityScope.PO1,
            AuthorityScope.PO2,
            AuthorityScope.PO3,
            AuthorityScope.P6,
            AuthorityScope.P7,
            AuthorityScope.P8,
            AuthorityScope.P13,
            AuthorityScope.P15,
        })
    )

    # Paths P16 is permitted to write to
    writable_paths: FrozenSet[str] = field(
        default_factory=lambda: frozenset({
            "p16",
            "p16_guard_result",
            "_p16_snapshot",
        })
    )

    # Paths that are append-only (can add but not replace)
    append_only_paths: FrozenSet[str] = field(
        default_factory=lambda: frozenset({
            "debug",
            "metrics",
        })
    )

    # Scopes that must not be modified (acoustic escalation prevention)
    acoustic_protected_scopes: FrozenSet[AuthorityScope] = field(
        default_factory=lambda: frozenset({
            AuthorityScope.P10,
            AuthorityScope.P13,
            AuthorityScope.P14,
        })
    )

    # Version for compatibility
    version: str = P16_VERSION

    def __post_init__(self) -> None:
        """Validate contract invariants."""
        # All authority scopes must be readable
        if not self.authority_scopes.issubset(self.readable_scopes):
            raise ValueError(
                "All authority_scopes must be in readable_scopes"
            )
        # Ensure frozensets
        if not isinstance(self.readable_scopes, frozenset):
            raise ValueError("readable_scopes must be frozenset")
        if not isinstance(self.authority_scopes, frozenset):
            raise ValueError("authority_scopes must be frozenset")
        if not isinstance(self.writable_paths, frozenset):
            raise ValueError("writable_paths must be frozenset")

    def is_readable(self, scope: AuthorityScope) -> bool:
        """Check if a scope is readable by P16."""
        return scope in self.readable_scopes

    def is_authority(self, scope: AuthorityScope) -> bool:
        """Check if a scope is authority-bearing."""
        return scope in self.authority_scopes

    def is_writable(self, path: str) -> bool:
        """Check if a path is writable by P16."""
        return path in self.writable_paths

    def is_append_only(self, path: str) -> bool:
        """Check if a path is append-only."""
        return path in self.append_only_paths

    def is_acoustic_protected(self, scope: AuthorityScope) -> bool:
        """Check if a scope is protected from acoustic escalation."""
        return scope in self.acoustic_protected_scopes

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "readable_scopes": sorted(s.value for s in self.readable_scopes),
            "authority_scopes": sorted(s.value for s in self.authority_scopes),
            "writable_paths": sorted(self.writable_paths),
            "append_only_paths": sorted(self.append_only_paths),
            "acoustic_protected_scopes": sorted(s.value for s in self.acoustic_protected_scopes),
            "version": self.version,
        }


# ============================================================================
# GUARD RESULT
# ============================================================================


@dataclass(frozen=True)
class P16GuardResult:
    """
    Result from P16 regression guard validation.

    Contains:
    - Whether validation passed
    - Any violations detected
    - The snapshot used for validation
    - Metadata for audit
    """
    passed: bool
    violations: Tuple[ContractViolation, ...]  # Tuple for immutability
    snapshot: Optional[HashSnapshot]
    contract: P16InputContract
    validated_at_phase: int = 16
    version: str = P16_VERSION

    def __post_init__(self) -> None:
        """Validate result invariants."""
        if not isinstance(self.violations, tuple):
            raise ValueError("violations must be a tuple")
        # If passed is True, there should be no violations
        if self.passed and len(self.violations) > 0:
            raise ValueError("passed=True but violations present")
        # If passed is False, there should be violations
        if not self.passed and len(self.violations) == 0:
            raise ValueError("passed=False but no violations")

    def violation_count(self) -> int:
        """Return count of violations."""
        return len(self.violations)

    def has_violations(self) -> bool:
        """Check if there are any violations."""
        return len(self.violations) > 0

    def get_violations_by_scope(self, scope: AuthorityScope) -> List[ContractViolation]:
        """Get all violations for a specific scope."""
        return [v for v in self.violations if v.scope == scope]

    def get_violations_by_type(self, vtype: ViolationType) -> List[ContractViolation]:
        """Get all violations of a specific type."""
        return [v for v in self.violations if v.violation_type == vtype]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "passed": self.passed,
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
            "snapshot": self.snapshot.to_dict() if self.snapshot else None,
            "contract_version": self.contract.version,
            "validated_at_phase": self.validated_at_phase,
            "version": self.version,
        }


# ============================================================================
# EXCEPTION CLASS
# ============================================================================


class P16ContractViolationError(Exception):
    """
    Exception raised when P16 contract violations are detected.

    This exception is DETERMINISTIC and NON-BYPASSABLE.
    It indicates a fundamental breach of the regression guard contract.
    """

    def __init__(
        self,
        violations: List[ContractViolation],
        message: str = "",
    ) -> None:
        """
        Initialize the violation error.

        Args:
            violations: List of all detected violations
            message: Optional additional message
        """
        self.violations = violations

        # Build comprehensive error message
        violation_summaries = []
        for v in violations:
            violation_summaries.append(
                f"  - [{v.scope.value}] {v.violation_type.value}: "
                f"field='{v.field_path}', "
                f"expected={_serialize_value(v.expected)}, "
                f"observed={_serialize_value(v.observed)}"
            )

        full_message = (
            f"P16 Contract Violation: {len(violations)} violation(s) detected.\n"
            f"P16 operates READ-ONLY on upstream phases PO1-P15.\n"
            f"Violations:\n" + "\n".join(violation_summaries)
        )

        if message:
            full_message = f"{message}\n{full_message}"

        super().__init__(full_message)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/audit."""
        return {
            "error_type": "P16ContractViolationError",
            "violation_count": len(self.violations),
            "violations": [v.to_dict() for v in self.violations],
        }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _serialize_value(value: Any) -> Any:
    """
    Serialize a value for logging/audit purposes.

    Handles frozensets, enums, tuples, and other special types.
    """
    if isinstance(value, frozenset):
        return sorted(str(v) for v in value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


# ============================================================================
# PUBLIC EXPORTS
# ============================================================================


__all__ = [
    # Version
    "P16_VERSION",
    # Enums
    "AuthorityScope",
    "ViolationType",
    # Dataclasses
    "ScopeHash",
    "HashSnapshot",
    "ContractViolation",
    "P16InputContract",
    "P16GuardResult",
    # Exception
    "P16ContractViolationError",
]
