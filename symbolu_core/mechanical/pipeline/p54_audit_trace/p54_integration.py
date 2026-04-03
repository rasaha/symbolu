"""
Phase 54: Audit & Compliance Trace Pipeline Integration

Integration functions for running P54 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p54_audit_trace import (
        maybe_run_p54,
    )

    # In pipeline after P53:
    maybe_run_p54(ctx)

    # Access audit record:
    if ctx.p54_audit_record is not None:
        print(f"Execution ID: {ctx.p54_audit_record.execution_id}")
        print(f"Governance: {ctx.p54_audit_record.governance_present}")
        print(f"Hash: {ctx.p54_audit_record.determinism_hash}")

INPUTS (Read-Only):
    Phase 54 MAY read:
        - ctx.p53_policy_binding (P53 GovernanceBindingEnvelope)
        - ctx.p52_governance_request (P52 GovernanceRequest)
        - Authoritative phase outputs (P6, P7, P9, P21, etc.)
        - ctx.execution_id or ctx.run_id
        - ctx.timestamp_utc

    Phase 54 MUST NOT read:
        - ctx.request (raw user text)
        - ctx.semantic_frame (semantic content)
        - ctx.lexical_frame (lexical content)
        - ctx.p10_acoustic, p11_prosodic_evidence (acoustic content)

CRITICAL CONSTRAINTS:
    - P54 records audit trail, nothing more
    - P54 stores record in ctx.p54_audit_record
    - P54 does NOT interpret governance decisions
    - P54 does NOT influence execution
    - P54 is an observer only

INVARIANTS:
    INV-P54-1: P54 MUST NOT influence execution, governance, or cognition
    INV-P54-2: Audit records MUST be reproducible for identical inputs
    INV-P54-3: Audit records MUST expose authority provenance explicitly
    INV-P54-4: Audit records MUST NOT contain inferred explanations
    INV-P54-5: Removing P54 MUST NOT change system behavior
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .p54_schema import (
    P54_VERSION,
    ComplianceAuditRecord,
)
from .p54_collector import (
    create_audit_record,
)


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_execution_id(ctx: Any) -> str:
    """
    Extract execution ID from context.

    Tries multiple possible attribute names for flexibility.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Execution ID string
    """
    # Try different attribute names
    for attr_name in ("execution_id", "run_id", "pipeline_id", "id"):
        value = getattr(ctx, attr_name, None)
        if value is not None and isinstance(value, str) and value:
            return value

    # Try nested snapshot
    snapshot = getattr(ctx, "phase_20_snapshot", None)
    if snapshot is not None:
        run_id = getattr(snapshot, "run_id", None)
        if run_id is not None and isinstance(run_id, str) and run_id:
            return run_id

    # Generate a placeholder if nothing found
    return "unknown_execution"


def _extract_timestamp_utc(ctx: Any) -> str:
    """
    Extract or generate UTC timestamp.

    If context has a timestamp, use it. Otherwise generate current time.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ISO 8601 UTC timestamp string
    """
    # Try to get existing timestamp
    for attr_name in ("timestamp_utc", "timestamp", "created_at"):
        value = getattr(ctx, attr_name, None)
        if value is not None:
            if isinstance(value, str) and value:
                return value
            if isinstance(value, datetime):
                return value.isoformat()

    # Generate current UTC timestamp
    return datetime.now(timezone.utc).isoformat()


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p54(ctx: Any) -> Optional[ComplianceAuditRecord]:
    """
    Run P54 audit trace if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P54 should run
    2. Extracts execution ID and timestamp
    3. Creates the audit record
    4. Attaches the result to ctx.p54_audit_record

    P54 is designed to run after P53.
    Returns None only if disabled.

    INV-P54-1: We record audit, never influence execution.
    INV-P54-2: Same inputs produce same hash.
    INV-P54-3: Authority provenance exposed explicitly.
    INV-P54-4: No inferred explanations.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ComplianceAuditRecord if created, None if skipped
    """
    # Check if P54 is disabled on this context
    if is_p54_disabled(ctx):
        return None

    # Extract execution ID and timestamp
    execution_id = _extract_execution_id(ctx)
    timestamp_utc = _extract_timestamp_utc(ctx)

    # Create the audit record
    record = create_audit_record(execution_id, timestamp_utc, ctx)

    # Attach to context (observer-only append)
    _attach_audit_record_to_context(ctx, record)

    return record


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p54_disabled(ctx: Any) -> bool:
    """
    Check if P54 is disabled on this context.

    P54 can be disabled by setting ctx._p54_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P54 is disabled, False otherwise
    """
    return getattr(ctx, "_p54_disabled", False)


def has_p54_audit_record(ctx: Any) -> bool:
    """
    Check if context has a P54 audit record attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p54_audit_record is set and not None
    """
    return getattr(ctx, "p54_audit_record", None) is not None


def get_p54_audit_record(ctx: Any) -> Optional[ComplianceAuditRecord]:
    """
    Get the P54 audit record from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ComplianceAuditRecord if present, None otherwise
    """
    return getattr(ctx, "p54_audit_record", None)


def get_determinism_hash(ctx: Any) -> Optional[str]:
    """
    Get the determinism hash from P54 audit record.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Determinism hash string or None if no record
    """
    record = get_p54_audit_record(ctx)
    if record is None:
        return None
    return record.determinism_hash


def get_p54_version() -> str:
    """
    Get the current P54 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P54_VERSION


def _attach_audit_record_to_context(
    ctx: Any,
    record: ComplianceAuditRecord,
) -> None:
    """
    Attach the P54 audit record to context.

    This is observer-only: we only append to ctx.p54_audit_record,
    we do NOT modify any other context fields or influence behavior.

    INV-P54-1: Only writes to ctx.p54_audit_record, nothing else.
    INV-P54-5: This is the only effect P54 has on context.

    Args:
        ctx: PipelineContext
        record: The P54 audit record to attach
    """
    # Attach to p54_audit_record attribute
    if hasattr(ctx, "p54_audit_record"):
        ctx.p54_audit_record = record
    else:
        try:
            setattr(ctx, "p54_audit_record", record)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p54",
    # Helpers
    "is_p54_disabled",
    "has_p54_audit_record",
    "get_p54_audit_record",
    "get_determinism_hash",
    "get_p54_version",
]
