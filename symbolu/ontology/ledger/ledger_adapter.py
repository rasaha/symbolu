"""
Ontological Ledger Adapter (Read-Only)
======================================

Generates ledger span IDs for ontological projections.

Hard Constraints:
    - Read-only (no side effects)
    - Deterministic (hash-only)
    - NO timestamps
    - NO randomness
    - NO counters
    - NO UUID generation
    - NO external I/O

Ledger spans are identity attestations, not logs.
They provide structural proof of projection without mutation.

The adapter accepts Phase artifacts that already have hashes and
generates ledger_span_id based solely on those hashes.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from symbolu.ontology.layers.ontology_layer import OntologicalLayer


# =============================================================================
# Input Contract
# =============================================================================

@dataclass(frozen=True)
class LedgerSpanInput:
    """
    Input for generating a ledger span.

    Attributes:
        phase_id: The phase identifier.
        layer: The ontological layer.
        artifact_refs: Tuple of opaque artifact references.
        parent_span_refs: Optional tuple of parent span IDs.

    Note:
        artifact_refs are opaque - the adapter uses repr() for hashing.
    """
    phase_id: str
    layer: OntologicalLayer
    artifact_refs: Tuple[Any, ...] = ()
    parent_span_refs: Tuple[str, ...] = ()


# =============================================================================
# Output Contract
# =============================================================================

@dataclass(frozen=True)
class LedgerSpan:
    """
    A ledger span representing an identity attestation.

    Attributes:
        span_id: The unique span ID (hex hash).
        phase_id: The phase identifier.
        layer: The ontological layer.
        parent_span_refs: Tuple of parent span IDs.

    Note:
        span_id is deterministically computed from inputs.
        No timestamps, no randomness, no counters.
    """
    span_id: str
    phase_id: str
    layer: OntologicalLayer
    parent_span_refs: Tuple[str, ...]


# =============================================================================
# Hash Computation (Deterministic)
# =============================================================================

def _stable_repr(obj: Any) -> str:
    """
    Generate a stable string representation of an object.

    Args:
        obj: Any object to represent.

    Returns:
        A stable string representation.

    Note:
        Uses JSON for dicts/lists, repr() for other types.
        Sorting is applied for determinism.
    """
    if obj is None:
        return "None"
    if isinstance(obj, (bool, int, float, str)):
        return repr(obj)
    if isinstance(obj, (list, tuple)):
        items = [_stable_repr(item) for item in obj]
        return f"[{','.join(items)}]"
    if isinstance(obj, dict):
        try:
            return json.dumps(obj, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError):
            # Fallback for non-JSON-serializable dicts
            items = sorted((repr(k), _stable_repr(v)) for k, v in obj.items())
            return "{" + ",".join(f"{k}:{v}" for k, v in items) + "}"
    if isinstance(obj, OntologicalLayer):
        return f"OntologicalLayer.{obj.name}"
    # Fallback to repr for other types
    return repr(obj)


def _compute_span_hash(
    phase_id: str,
    layer: OntologicalLayer,
    artifact_refs: Tuple[Any, ...],
    parent_span_refs: Tuple[str, ...],
) -> str:
    """
    Compute a deterministic hash for a ledger span.

    Args:
        phase_id: The phase identifier.
        layer: The ontological layer.
        artifact_refs: Tuple of artifact references.
        parent_span_refs: Tuple of parent span IDs.

    Returns:
        A 64-character hex hash string.

    Note:
        - Uses SHA256 for cryptographic stability
        - Ordering is deterministic
        - No timestamps or randomness
    """
    # Build canonical representation
    parts = [
        f"phase:{phase_id}",
        f"layer:{layer.name}:{layer.value}",
        f"artifacts:{_stable_repr(artifact_refs)}",
        f"parents:{_stable_repr(parent_span_refs)}",
    ]
    canonical = "|".join(parts)

    # Compute SHA256 hash
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Public API
# =============================================================================

def generate_ledger_span(span_input: LedgerSpanInput) -> str:
    """
    Generate a ledger span ID from input.

    Args:
        span_input: The LedgerSpanInput containing phase, layer, and artifacts.

    Returns:
        A 64-character hex hash string representing the span ID.

    Note:
        - Deterministic: same input always produces same output
        - No side effects
        - No timestamps or randomness
    """
    return _compute_span_hash(
        phase_id=span_input.phase_id,
        layer=span_input.layer,
        artifact_refs=span_input.artifact_refs,
        parent_span_refs=span_input.parent_span_refs,
    )


def generate_ledger_span_full(span_input: LedgerSpanInput) -> LedgerSpan:
    """
    Generate a full LedgerSpan object from input.

    Args:
        span_input: The LedgerSpanInput containing phase, layer, and artifacts.

    Returns:
        A LedgerSpan object with computed span_id.

    Note:
        This is a convenience function that returns the full object
        rather than just the span ID.
    """
    span_id = generate_ledger_span(span_input)
    return LedgerSpan(
        span_id=span_id,
        phase_id=span_input.phase_id,
        layer=span_input.layer,
        parent_span_refs=span_input.parent_span_refs,
    )


def verify_span_hash(span: LedgerSpan, artifact_refs: Tuple[Any, ...]) -> bool:
    """
    Verify that a span's hash matches the expected computation.

    Args:
        span: The LedgerSpan to verify.
        artifact_refs: The original artifact references.

    Returns:
        True if the span_id matches the computed hash, False otherwise.

    Note:
        This allows replay verification without mutation.
    """
    expected_hash = _compute_span_hash(
        phase_id=span.phase_id,
        layer=span.layer,
        artifact_refs=artifact_refs,
        parent_span_refs=span.parent_span_refs,
    )
    return span.span_id == expected_hash
