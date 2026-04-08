"""
Phase 54: Audit & Compliance Trace Engine - Core Collection Logic

This module contains the core collection logic for P54.
It collects authoritative phase outputs and computes determinism hashes
without interpretation or enforcement.

P54 is a recorder, not a judge.

What P54 Actually Does:
    1. Collects authoritative phase outputs (PO1-P9, P6, P7, P21)
    2. Collects governance binding info (P53)
    3. Computes a determinism hash
    4. Emits a single immutable audit record

That is all.

CRITICAL: The determinism hash must be stable across runs:
    - Use explicit ordered serialization
    - No random values
    - No timestamps in hash
"""

import hashlib
import json
from typing import Any, Optional, Tuple

from .p54_schema import ComplianceAuditRecord


# Authoritative phases that contribute to determinism hash
# These are the cognitive decision phases (not observer phases)
AUTHORITATIVE_PHASES = (
    "po1_phrase_boundary",
    "po4_semantic_frame",
    "p6_regime",
    "p7_discourse_envelope",
    "p9_lexical",
    "p21_delivery_mode",
)


def _serialize_for_hash(value: Any) -> str:
    """
    Serialize a value for deterministic hashing.

    Uses JSON with sorted keys for dictionaries to ensure
    deterministic ordering. Handles None, primitives, dicts, and lists.

    INV-P54-2: Reproducible for identical inputs.

    Args:
        value: Value to serialize

    Returns:
        Deterministic string representation
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, (list, tuple)):
        items = [_serialize_for_hash(item) for item in value]
        return "[" + ",".join(items) + "]"
    if isinstance(value, dict):
        # Sort keys for deterministic ordering
        items = []
        for key in sorted(value.keys()):
            k_ser = json.dumps(str(key), ensure_ascii=True)
            v_ser = _serialize_for_hash(value[key])
            items.append(f"{k_ser}:{v_ser}")
        return "{" + ",".join(items) + "}"
    # For objects with to_dict method
    if hasattr(value, "to_dict"):
        return _serialize_for_hash(value.to_dict())
    # For dataclasses or objects with __dict__
    if hasattr(value, "__dict__"):
        return _serialize_for_hash(vars(value))
    # Fallback to string representation
    return json.dumps(str(value), ensure_ascii=True)


def extract_phase_value(ctx: Any, phase_name: str) -> Any:
    """
    Extract a phase value from context for hashing.

    This extracts only structural data needed for determinism hash.
    No interpretation or modification.

    Args:
        ctx: Pipeline context
        phase_name: Name of the phase attribute

    Returns:
        Phase value or None if not present
    """
    value = getattr(ctx, phase_name, None)
    if value is None:
        return None
    # Return the value as-is for serialization
    return value


def collect_authoritative_outputs(ctx: Any) -> dict:
    """
    Collect authoritative phase outputs for hashing.

    This collects outputs from cognitive decision phases only.
    Observer phases are not included as they don't affect decisions.

    INV-P54-1: Read-only collection, no modification.

    Args:
        ctx: Pipeline context

    Returns:
        Dict mapping phase names to their outputs
    """
    outputs = {}
    for phase_name in AUTHORITATIVE_PHASES:
        value = extract_phase_value(ctx, phase_name)
        if value is not None:
            outputs[phase_name] = value
    return outputs


def compute_determinism_hash(
    authoritative_outputs: dict,
    governance_binding: Optional[Any] = None,
) -> str:
    """
    Compute determinism hash from authoritative outputs.

    This hash is reproducible for identical inputs.
    It does NOT include timestamps (for determinism).
    It does NOT include random values.

    INV-P54-2: Reproducible for identical inputs.

    Args:
        authoritative_outputs: Dict of authoritative phase outputs
        governance_binding: Optional governance binding envelope

    Returns:
        SHA-256 hex digest
    """
    # Build ordered hash input
    hash_parts = []

    # Add authoritative outputs in sorted order
    for phase_name in sorted(authoritative_outputs.keys()):
        value = authoritative_outputs[phase_name]
        serialized = _serialize_for_hash(value)
        hash_parts.append(f"{phase_name}={serialized}")

    # Add governance binding if present
    if governance_binding is not None:
        binding_ser = _serialize_for_hash(governance_binding)
        hash_parts.append(f"governance_binding={binding_ser}")

    # Join with separator and hash
    hash_input = "|".join(hash_parts)
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def extract_governance_info(ctx: Any) -> Tuple[
    bool,
    Optional[str],
    Optional[str],
    Tuple[str, ...],
]:
    """
    Extract governance information from context (P53 binding).

    This extracts governance info verbatim from P53.
    No interpretation or modification.

    INV-P54-3: Authority provenance exposed explicitly.
    INV-P54-4: No inferred explanations.

    Args:
        ctx: Pipeline context

    Returns:
        Tuple of (governance_present, authority_id, decision, rationale_codes)
    """
    # Get P53 binding envelope
    binding = getattr(ctx, "p53_policy_binding", None)

    if binding is None:
        return False, None, None, ()

    # Extract verbatim - no interpretation
    governance_present = getattr(binding, "bound", False)
    authority_id = getattr(binding, "authority_id", None)
    decision = getattr(binding, "decision", None)
    rationale_codes = getattr(binding, "rationale_codes", ())

    # Ensure rationale_codes is tuple
    if not isinstance(rationale_codes, tuple):
        rationale_codes = tuple(rationale_codes)

    return governance_present, authority_id, decision, rationale_codes


def extract_affected_phases(ctx: Any) -> Tuple[str, ...]:
    """
    Extract list of phases affected by governance.

    Currently returns empty tuple - affected phases tracking
    will be added when enforcement layer (P55) is implemented.

    INV-P54-4: No inferred explanations - we only record what
    the governance binding explicitly states.

    Args:
        ctx: Pipeline context

    Returns:
        Tuple of affected phase names
    """
    # Currently no enforcement exists, so no phases are "affected"
    # This field exists for future P55 enforcement layer
    return ()


def extract_blocked_actions(ctx: Any) -> Tuple[str, ...]:
    """
    Extract list of actions blocked by governance.

    Currently returns empty tuple - blocked actions tracking
    will be added when enforcement layer (P55) is implemented.

    INV-P54-4: No inferred explanations - we only record what
    the governance binding explicitly states.

    Args:
        ctx: Pipeline context

    Returns:
        Tuple of blocked action names
    """
    # Currently no enforcement exists, so no actions are blocked
    # This field exists for future P55 enforcement layer
    return ()


def create_audit_record(
    execution_id: str,
    timestamp_utc: str,
    ctx: Any,
) -> ComplianceAuditRecord:
    """
    Create a compliance audit record from pipeline context.

    This is the core function that assembles the audit record.
    It collects all required information and computes the hash.

    INV-P54-1: No influence on execution.
    INV-P54-2: Reproducible for identical inputs.
    INV-P54-3: Authority provenance explicit.
    INV-P54-4: No inferred explanations.

    Args:
        execution_id: Pipeline execution identifier
        timestamp_utc: UTC timestamp in ISO 8601 format
        ctx: Pipeline context

    Returns:
        ComplianceAuditRecord
    """
    # Collect authoritative outputs
    authoritative_outputs = collect_authoritative_outputs(ctx)

    # Extract governance info
    governance_present, authority_id, decision, rationale_codes = (
        extract_governance_info(ctx)
    )

    # Get governance binding for hash
    governance_binding = getattr(ctx, "p53_policy_binding", None)

    # Compute determinism hash (excludes timestamp for reproducibility)
    determinism_hash = compute_determinism_hash(
        authoritative_outputs,
        governance_binding,
    )

    # Extract affected scope
    affected_phases = extract_affected_phases(ctx)
    blocked_actions = extract_blocked_actions(ctx)

    return ComplianceAuditRecord(
        execution_id=execution_id,
        timestamp_utc=timestamp_utc,
        governance_present=governance_present,
        authority_id=authority_id,
        governance_decision=decision,
        rationale_codes=rationale_codes,
        affected_phases=affected_phases,
        blocked_actions=blocked_actions,
        determinism_hash=determinism_hash,
    )


def run_p54_directly(
    execution_id: str,
    timestamp_utc: str,
    ctx: Any,
) -> ComplianceAuditRecord:
    """
    Direct entry point for P54 audit record creation.

    This function allows direct invocation of P54 logic without
    going through the pipeline context.

    Args:
        execution_id: Pipeline execution identifier
        timestamp_utc: UTC timestamp in ISO 8601 format
        ctx: Pipeline context

    Returns:
        ComplianceAuditRecord
    """
    return create_audit_record(execution_id, timestamp_utc, ctx)


# Public exports
__all__ = [
    # Constants
    "AUTHORITATIVE_PHASES",
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
]
