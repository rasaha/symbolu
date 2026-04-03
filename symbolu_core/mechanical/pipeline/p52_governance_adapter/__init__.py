"""
Phase 52: Governance Adapter Interface

Phase 52 defines the structural interface between Symbol-U cognition and
external governance systems. It contains no governance logic.

P52 exists to answer exactly one question:
    "If an external governance engine existed, what data would it receive,
    and what shape must its response have?"

P52 does NOT:
    - Enforce policy
    - Evaluate rules
    - Block execution
    - Modify outputs
    - Interpret meaning
    - Contain logic

P52 is a pure contract definition — nothing more.
Think of P52 as an electrical socket — not the appliance.

Usage:
    from symbolu_core.mechanical.pipeline.p52_governance_adapter import (
        maybe_run_p52,
        GovernanceRequest,
        GovernanceResponse,
        get_p52_request,
    )

    # Run P52 in pipeline
    request = maybe_run_p52(ctx)

    # Access results
    if request is not None:
        print(f"Snapshot ID: {request.snapshot_id}")
        print(f"Readiness: {request.readiness_level}")
        print(f"Trace Hash: {request.trace_hash}")

INVARIANTS:
    INV-P52-1: P52 MUST NOT execute or simulate governance
    INV-P52-2: P52 MUST NOT modify or reinterpret upstream data
    INV-P52-3: P52 MUST NOT introduce branching or gating
    INV-P52-4: P52 MUST NOT require GovernanceResponse to exist
    INV-P52-5: When P52 is removed, system behavior is bitwise identical
"""

from .p52_schema import (
    # Version
    P52_VERSION,
    # Type Aliases
    GovernanceDecision,
    ReadinessLevel,
    # Constants
    VALID_GOVERNANCE_DECISIONS,
    VALID_READINESS_LEVELS,
    GOVERNANCE_REQUEST_FIELDS,
    GOVERNANCE_RESPONSE_FIELDS,
    # Dataclasses
    GovernanceRequest,
    GovernanceResponse,
)

from .p52_assembler import (
    assemble_governance_request,
    run_p52_directly,
)

from .p52_integration import (
    # Integration
    maybe_run_p52,
    # Helpers
    is_p52_disabled,
    has_p52_request,
    get_p52_request,
    get_p52_version,
)


__all__ = [
    # Version
    "P52_VERSION",
    # Type Aliases
    "GovernanceDecision",
    "ReadinessLevel",
    # Constants
    "VALID_GOVERNANCE_DECISIONS",
    "VALID_READINESS_LEVELS",
    "GOVERNANCE_REQUEST_FIELDS",
    "GOVERNANCE_RESPONSE_FIELDS",
    # Dataclasses
    "GovernanceRequest",
    "GovernanceResponse",
    # Core assembly
    "assemble_governance_request",
    "run_p52_directly",
    # Integration
    "maybe_run_p52",
    # Helpers
    "is_p52_disabled",
    "has_p52_request",
    "get_p52_request",
    "get_p52_version",
]
