"""
Phase 52: Governance Adapter Request Assembler

Assembles GovernanceRequest from upstream phase outputs.

P52 reads ONLY from:
    - GovernanceReadinessEnvelope (P51)
    - UnifiedCognitiveSnapshot (P20)
    - Phase trace metadata (IDs, timestamps)
    - Delivery metadata (P21 result)

P52 MUST NOT read:
    - Raw user input
    - Lexical or semantic content
    - Acoustic data
    - Any policy configuration
    - Any runtime execution state

P52 assembles a GovernanceRequest and does nothing else.
It does NOT invoke any external system.
It does NOT expect a response.

INVARIANTS:
    INV-P52-1: P52 MUST NOT execute or simulate governance
    INV-P52-2: P52 MUST NOT modify or reinterpret upstream data
    INV-P52-3: P52 MUST NOT introduce branching or gating
    INV-P52-4: P52 MUST NOT require GovernanceResponse to exist
    INV-P52-5: When P52 is removed, system behavior is bitwise identical
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Optional, Tuple

from .p52_schema import (
    P52_VERSION,
    GovernanceRequest,
    ReadinessLevel,
)


# ============================================================================
# TRACE HASH COMPUTATION
# ============================================================================


def _compute_trace_hash(
    snapshot_id: str,
    readiness_level: str,
    blocking_factors: Tuple[str, ...],
) -> str:
    """
    Compute a deterministic trace hash for audit purposes.

    This is structural metadata only — no semantic content.

    INV-P52-2: We use only structural data, no reinterpretation.

    Args:
        snapshot_id: The P20 snapshot run_id
        readiness_level: The P51 readiness level
        blocking_factors: The P51 blocking factors

    Returns:
        SHA-256 hash string (first 16 hex chars)
    """
    # Combine structural elements deterministically
    elements = [
        f"snapshot:{snapshot_id}",
        f"readiness:{readiness_level}",
        f"blockers:{len(blocking_factors)}",
    ]
    combined = "|".join(elements)

    # Compute hash
    hash_bytes = hashlib.sha256(combined.encode("utf-8")).hexdigest()

    # Return first 16 characters
    return hash_bytes[:16]


# ============================================================================
# COGNITIVE SUMMARY EXTRACTION
# ============================================================================


def _extract_cognitive_summary(
    phase_20_snapshot: Any,
    p21_delivery_mode: Any,
) -> Mapping[str, Any]:
    """
    Extract structural cognitive summary from upstream phases.

    This extracts ONLY structural metadata — no free text, no semantics,
    no probabilities, no raw content.

    INV-P52-2: We copy values verbatim, no reinterpretation.

    Args:
        phase_20_snapshot: P20 UnifiedCognitiveSnapshot (may be None)
        p21_delivery_mode: P21 DeliveryModeDecision (may be None)

    Returns:
        Mapping of structural metadata
    """
    summary: dict = {}

    # Extract P20 snapshot structural data (if present)
    if phase_20_snapshot is not None:
        summary["snapshot_present"] = True
        summary["has_coherence"] = getattr(
            phase_20_snapshot, "coherence_v3", None
        ) is not None
        summary["has_drift"] = getattr(
            phase_20_snapshot, "drift_fusion_index", None
        ) is not None
        summary["has_entropy"] = getattr(
            phase_20_snapshot, "temporal_entropy_diff", None
        ) is not None
        summary["phase_count"] = (
            phase_20_snapshot.phase_count()
            if hasattr(phase_20_snapshot, "phase_count")
            else 0
        )
    else:
        summary["snapshot_present"] = False

    # Extract P21 delivery structural data (if present)
    if p21_delivery_mode is not None:
        summary["delivery_present"] = True
        summary["delivery_allowed"] = getattr(
            p21_delivery_mode, "delivery_allowed", None
        )
    else:
        summary["delivery_present"] = False

    return summary


# ============================================================================
# REQUEST ASSEMBLY
# ============================================================================


def assemble_governance_request(
    p51_envelope: Any,
    phase_20_snapshot: Any,
    p21_delivery_mode: Any,
) -> Optional[GovernanceRequest]:
    """
    Assemble a GovernanceRequest from upstream phase outputs.

    This is the core assembly function of P52. It:
    1. Reads structural data from P51, P20, P21
    2. Computes trace hash from structural elements
    3. Creates GovernanceRequest

    It does NOT:
    - Execute governance
    - Simulate policies
    - Invoke external systems
    - Expect or require a response

    INV-P52-1: No governance execution — just assembly.
    INV-P52-2: No reinterpretation — values copied verbatim.
    INV-P52-3: No branching — always returns request if P51 present.
    INV-P52-4: GovernanceResponse never created or required.

    Args:
        p51_envelope: GovernanceReadinessEnvelope from P51
        phase_20_snapshot: UnifiedCognitiveSnapshot from P20
        p21_delivery_mode: DeliveryModeDecision from P21

    Returns:
        GovernanceRequest if P51 envelope present, None otherwise
    """
    # If no P51 envelope, cannot assemble request
    if p51_envelope is None:
        return None

    # Extract readiness data from P51 (verbatim copy, INV-P52-2)
    readiness_level: ReadinessLevel = getattr(
        p51_envelope, "readiness_level", "NOT_READY"
    )
    blocking_factors: Tuple[str, ...] = tuple(
        getattr(p51_envelope, "blocking_factors", ())
    )
    advisory_notes: Tuple[str, ...] = tuple(
        getattr(p51_envelope, "advisory_notes", ())
    )

    # Extract snapshot ID from P20 (or generate placeholder)
    snapshot_id = (
        getattr(phase_20_snapshot, "run_id", "no_snapshot")
        if phase_20_snapshot is not None
        else "no_snapshot"
    )

    # Compute trace hash (structural metadata only)
    trace_hash = _compute_trace_hash(
        snapshot_id=snapshot_id,
        readiness_level=readiness_level,
        blocking_factors=blocking_factors,
    )

    # Extract cognitive summary (structural metadata only)
    cognitive_summary = _extract_cognitive_summary(
        phase_20_snapshot=phase_20_snapshot,
        p21_delivery_mode=p21_delivery_mode,
    )

    # Assemble and return request
    return GovernanceRequest(
        snapshot_id=snapshot_id,
        readiness_level=readiness_level,
        blocking_factors=blocking_factors,
        advisory_notes=advisory_notes,
        cognitive_summary=cognitive_summary,
        trace_hash=trace_hash,
    )


def run_p52_directly(
    p51_envelope: Any,
    phase_20_snapshot: Any = None,
    p21_delivery_mode: Any = None,
) -> Optional[GovernanceRequest]:
    """
    Run P52 directly with explicit inputs.

    This is the lower-level entry point for P52.
    It assembles a GovernanceRequest from the provided inputs.

    INV-P52-1: No governance execution.
    INV-P52-2: No data modification.
    INV-P52-3: No branching/gating.

    Args:
        p51_envelope: GovernanceReadinessEnvelope from P51 (required)
        phase_20_snapshot: UnifiedCognitiveSnapshot from P20 (optional)
        p21_delivery_mode: DeliveryModeDecision from P21 (optional)

    Returns:
        GovernanceRequest if P51 envelope present, None otherwise
    """
    return assemble_governance_request(
        p51_envelope=p51_envelope,
        phase_20_snapshot=phase_20_snapshot,
        p21_delivery_mode=p21_delivery_mode,
    )


# Public exports
__all__ = [
    "assemble_governance_request",
    "run_p52_directly",
]
