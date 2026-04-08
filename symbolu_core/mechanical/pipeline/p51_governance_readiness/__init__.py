"""
Phase 51: Governance Readiness Envelope

Phase 51 summarizes structural readiness for governance without exercising
governance authority.

P51 exists to answer one question only:
    "Is this pipeline output structurally ready to be handed to a future
    governance layer?"

P51 does NOT:
    - Enforce policy
    - Modify behavior
    - Block actions
    - Override any prior phase
    - Predict outcomes

P51 ONLY summarizes whether upstream phases are:
    - Complete
    - Coherent
    - Explainable
    - Non-contradictory

P51 is diagnostic only.

Usage:
    from symbolu_core.mechanical.pipeline.p51_governance_readiness import (
        maybe_run_p51,
        GovernanceReadinessEnvelope,
        get_readiness_level,
        is_governance_ready,
    )

    # Run P51 in pipeline
    envelope = maybe_run_p51(ctx)

    # Access results
    if envelope is not None:
        print(f"Ready: {envelope.ready}")
        print(f"Level: {envelope.readiness_level}")
        print(f"Blocking factors: {envelope.blocking_factors}")

INVARIANTS:
    INV-P51-1: P51 MUST NOT modify any upstream data
    INV-P51-2: P51 MUST NOT introduce new classifications or decisions
    INV-P51-3: P51 MUST NOT block or gate output
    INV-P51-4: P51 MUST NOT depend on future governance logic
    INV-P51-5: When P51 is removed, system behavior is bitwise identical
"""

from .p51_schema import (
    # Version
    P51_VERSION,
    # Type Aliases
    ReadinessLevel,
    # Constants
    VALID_READINESS_LEVELS,
    DRIFT_SAFETY_THRESHOLD,
    MANDATORY_PHASES,
    # Dataclasses
    GovernanceReadinessEnvelope,
    # Factory
    create_governance_readiness_envelope,
)

from .p51_analyzer import (
    compute_governance_readiness,
    run_p51_directly,
)

from .p51_integration import (
    # Integration
    maybe_run_p51,
    # Helpers
    is_p51_disabled,
    has_p51_envelope,
    get_p51_envelope,
    get_readiness_level,
    is_governance_ready,
    get_blocking_factors,
    get_advisory_notes,
    get_p51_version,
)


__all__ = [
    # Version
    "P51_VERSION",
    # Type Aliases
    "ReadinessLevel",
    # Constants
    "VALID_READINESS_LEVELS",
    "DRIFT_SAFETY_THRESHOLD",
    "MANDATORY_PHASES",
    # Dataclasses
    "GovernanceReadinessEnvelope",
    # Factory
    "create_governance_readiness_envelope",
    # Core computation
    "compute_governance_readiness",
    "run_p51_directly",
    # Integration
    "maybe_run_p51",
    # Helpers
    "is_p51_disabled",
    "has_p51_envelope",
    "get_p51_envelope",
    "get_readiness_level",
    "is_governance_ready",
    "get_blocking_factors",
    "get_advisory_notes",
    "get_p51_version",
]
