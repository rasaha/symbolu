"""
Audit Trace — Facade for P54 compliance audit records.

Re-exports P54 audit trace from symbolu_core.mechanical.pipeline.
P54 generates immutable compliance audit records with determinism
hashing for verifiable pipeline execution history.
"""

from symbolu_core.mechanical.pipeline.p54_audit_trace.p54_schema import (
    ComplianceAuditRecord,
)
from symbolu_core.mechanical.pipeline.p54_audit_trace.p54_collector import (
    create_audit_record,
    compute_determinism_hash,
    collect_authoritative_outputs,
    extract_governance_info,
    extract_blocked_actions,
)

__all__ = [
    "ComplianceAuditRecord",
    "create_audit_record",
    "compute_determinism_hash",
    "collect_authoritative_outputs",
    "extract_governance_info",
    "extract_blocked_actions",
]
