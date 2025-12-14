"""
Phase 54: Audit & Compliance Trace Engine Schema

Phase 54 generates immutable compliance audit records without interpretation
or enforcement.

P54 answers exactly one question:
    "Can an external auditor reconstruct exactly what happened, without
    inference or explanation?"

P54:
    - Observes governance binding
    - Observes cognitive decisions
    - Records provenance
    - Makes no judgments
    - Enables legal, regulatory, and enterprise auditability

P54 DOES:
    - Collect authoritative phase outputs
    - Collect governance binding info
    - Compute determinism hash
    - Emit immutable audit record

P54 does NOT:
    - Explain decisions
    - Interpret policy
    - Recommend actions
    - Modify outputs
    - Enforce compliance
    - Compress audit data

INPUTS (Read-Only):
    Phase 54 MAY read:
        - GovernanceBindingEnvelope (from P53)
        - GovernanceRequest metadata (from P52)
        - Phase execution trail (P1-P53 outputs)
        - Pipeline execution ID
        - Timestamps

    Phase 54 MUST NOT read:
        - Raw user input
        - Acoustic features
        - Semantic meaning
        - Intent rationale
        - Any external systems

OUTPUTS:
    - ComplianceAuditRecord: Immutable audit record

INVARIANTS:
    INV-P54-1: P54 MUST NOT influence execution, governance, or cognition
    INV-P54-2: Audit records MUST be reproducible for identical inputs
    INV-P54-3: Audit records MUST expose authority provenance explicitly
    INV-P54-4: Audit records MUST NOT contain inferred explanations
    INV-P54-5: Removing P54 MUST NOT change system behavior
"""

from dataclasses import dataclass
from typing import Optional, Tuple


# Version identifier for this phase
P54_VERSION = "1.0.0"

# Allowed fields in ComplianceAuditRecord (for structural validation)
COMPLIANCE_AUDIT_RECORD_FIELDS = frozenset({
    "execution_id",
    "timestamp_utc",
    "governance_present",
    "authority_id",
    "governance_decision",
    "rationale_codes",
    "affected_phases",
    "blocked_actions",
    "determinism_hash",
    "version",
    "architectural_phase",
})


@dataclass(frozen=True)
class ComplianceAuditRecord:
    """
    Immutable compliance audit record.

    This is the output of Phase 54. It provides an externally verifiable
    record of governance interaction without interpretation or explanation.

    P54 records authority. P54 does NOT interpret authority.
    P54 is the legal memory of the system.

    Invariants:
        - execution_id must be non-empty string
        - timestamp_utc must be non-empty string (ISO 8601 format)
        - governance_present indicates if governance was bound
        - authority_id is verbatim from P53 (None if no governance)
        - governance_decision is verbatim from P53 (None if no governance)
        - rationale_codes are verbatim from P53 (empty if no governance)
        - affected_phases lists phases touched by governance
        - blocked_actions lists actions blocked by governance
        - determinism_hash is reproducible for identical inputs
    """

    # Core identity fields
    execution_id: str
    timestamp_utc: str

    # Governance presence
    governance_present: bool
    authority_id: Optional[str]

    # Governance decision (verbatim from P53)
    governance_decision: Optional[str]
    rationale_codes: Tuple[str, ...]

    # Affected scope
    affected_phases: Tuple[str, ...]
    blocked_actions: Tuple[str, ...]

    # Determinism hash
    determinism_hash: str

    # Metadata
    version: str = P54_VERSION
    architectural_phase: str = "P54"

    def __post_init__(self) -> None:
        """Validate invariants on construction."""
        # Validate execution_id is non-empty
        if not self.execution_id or not isinstance(self.execution_id, str):
            raise ValueError("execution_id must be a non-empty string")

        # Validate timestamp_utc is non-empty
        if not self.timestamp_utc or not isinstance(self.timestamp_utc, str):
            raise ValueError("timestamp_utc must be a non-empty string")

        # Validate determinism_hash is non-empty
        if not self.determinism_hash or not isinstance(self.determinism_hash, str):
            raise ValueError("determinism_hash must be a non-empty string")

        # Ensure rationale_codes is tuple
        if not isinstance(self.rationale_codes, tuple):
            object.__setattr__(
                self, "rationale_codes",
                tuple(self.rationale_codes)
            )

        # Ensure affected_phases is tuple
        if not isinstance(self.affected_phases, tuple):
            object.__setattr__(
                self, "affected_phases",
                tuple(self.affected_phases)
            )

        # Ensure blocked_actions is tuple
        if not isinstance(self.blocked_actions, tuple):
            object.__setattr__(
                self, "blocked_actions",
                tuple(self.blocked_actions)
            )

        # If governance is present, decision should not be None
        # Note: We do NOT enforce this - we record verbatim what P53 provides
        # This is intentional for INV-P54-4 (no inferred explanations)

    def to_dict(self) -> dict:
        """Serialize to dictionary for observability and export."""
        return {
            "execution_id": self.execution_id,
            "timestamp_utc": self.timestamp_utc,
            "governance_present": self.governance_present,
            "authority_id": self.authority_id,
            "governance_decision": self.governance_decision,
            "rationale_codes": list(self.rationale_codes),
            "affected_phases": list(self.affected_phases),
            "blocked_actions": list(self.blocked_actions),
            "determinism_hash": self.determinism_hash,
            "version": self.version,
            "architectural_phase": self.architectural_phase,
        }


# Public exports
__all__ = [
    # Version
    "P54_VERSION",
    # Constants
    "COMPLIANCE_AUDIT_RECORD_FIELDS",
    # Dataclasses
    "ComplianceAuditRecord",
]
