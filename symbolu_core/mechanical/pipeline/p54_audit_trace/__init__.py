"""
Phase 54: Audit & Compliance Trace Engine

Phase 54 generates immutable compliance audit records without interpretation
or enforcement.

P54 is the legal memory of the system.

P54 answers exactly one question:
    "Can an external auditor reconstruct exactly what happened, without
    inference or explanation?"

Architectural Positioning:
    - P52 defines how governance may speak (contract)
    - P53 defines where governance attaches (binding)
    - P54 defines how it is audited (this phase)
    - P55 will define how execution is blocked or allowed

Usage:
    from symbolu_core.mechanical.pipeline.p54_audit_trace import (
        maybe_run_p54,
        ComplianceAuditRecord,
    )

    # In pipeline after P53:
    record = maybe_run_p54(ctx)

    # Access audit record:
    if record is not None:
        print(f"Execution ID: {record.execution_id}")
        print(f"Governance Present: {record.governance_present}")
        print(f"Authority ID: {record.authority_id}")
        print(f"Decision: {record.governance_decision}")
        print(f"Hash: {record.determinism_hash}")

INVARIANTS:
    INV-P54-1: P54 MUST NOT influence execution, governance, or cognition
    INV-P54-2: Audit records MUST be reproducible for identical inputs
    INV-P54-3: Audit records MUST expose authority provenance explicitly
    INV-P54-4: Audit records MUST NOT contain inferred explanations
    INV-P54-5: Removing P54 MUST NOT change system behavior
"""

from .p54_schema import (
    # Version
    P54_VERSION,
    # Constants
    COMPLIANCE_AUDIT_RECORD_FIELDS,
    # Dataclasses
    ComplianceAuditRecord,
)

from .p54_collector import (
    # Constants
    AUTHORITATIVE_PHASES,
    # Hash computation
    compute_determinism_hash,
    # Collection functions
    collect_authoritative_outputs,
    extract_governance_info,
    extract_affected_phases,
    extract_blocked_actions,
    # Core creation
    create_audit_record,
    # Direct entry point
    run_p54_directly,
)

from .p54_integration import (
    # Integration
    maybe_run_p54,
    # Helpers
    is_p54_disabled,
    has_p54_audit_record,
    get_p54_audit_record,
    get_determinism_hash,
    get_p54_version,
)


__all__ = [
    # Version
    "P54_VERSION",
    # Constants
    "COMPLIANCE_AUDIT_RECORD_FIELDS",
    "AUTHORITATIVE_PHASES",
    # Dataclasses
    "ComplianceAuditRecord",
    # Hash computation
    "compute_determinism_hash",
    # Collection functions
    "collect_authoritative_outputs",
    "extract_governance_info",
    "extract_affected_phases",
    "extract_blocked_actions",
    # Core creation
    "create_audit_record",
    # Direct entry point
    "run_p54_directly",
    # Integration
    "maybe_run_p54",
    # Helpers
    "is_p54_disabled",
    "has_p54_audit_record",
    "get_p54_audit_record",
    "get_determinism_hash",
    "get_p54_version",
]
