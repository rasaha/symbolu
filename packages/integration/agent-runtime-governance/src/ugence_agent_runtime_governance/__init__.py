"""Ugence Agent Runtime Governance — the production ``GovernanceHook`` adapter.

    COMPOSE, THEN PROJECT. MINT NOTHING.

Agent Runtime ships three hooks: ``UnconfiguredGovernanceHook`` (BLOCK, the default),
``AllowAllGovernanceHook`` (an explicitly unsafe test helper) and a deprecated alias.
This package adds the fourth — the one a deployment actually uses. It obtains a
``GovernedExecutionDecision`` from the ratified ``RiskAuthorityCompositionEngine`` and
projects it onto the runtime's ``GovernanceEvaluation``, bound to the exact proposal.

It contains no composition logic, no authority, and no credentials: the envelope, key
ring and revocation state live in the deployment's ``GovernanceInputSource``, and the
last-mile recheck is Risk Authority's own ``make_pre_effect_recheck``, wired rather than
rebuilt.

Scoped by ``docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md`` and sequenced
as GAS-3 in the Ugence productization roadmap §11.

**Maturity.** Core implemented; **not** pilot-validated and **not** production-certified.
Risk Authority ``production_mode`` still raises ``ProductionContainmentError``, and HOLD,
DEFER, ESCALATE and MANUAL_REVIEW still have no sink — a parked instance has nowhere to
be seen by a human until one is built.
"""
from __future__ import annotations

from .dispositions import (
    REASON_NOT_A_FINAL_DISPOSITION,
    REASON_NOT_EXECUTABLE,
    REASON_UNKNOWN_DISPOSITION,
    project_disposition,
)
from .errors import CompositionUnavailable, GovernanceHookError, MalformedDecision
from .hook import (
    REASON_COMPOSITION_FAILED,
    REASON_MALFORMED_INPUTS,
    REASON_NO_AUTHORIZATION_REFERENCE,
    REASON_NOT_AUTHORITY_BOUND,
    REASON_RECORD_CAPACITY,
    REASON_SOURCE_UNAVAILABLE,
    GovernedExecutionHook,
)
from .interfaces import CompositionInputs, GovernanceInputSource
from .recheck import build_authority_recheck, hook_envelope_resolver
from .version import __version__

__all__ = [
    "__version__",
    "GovernedExecutionHook",
    "CompositionInputs",
    "GovernanceInputSource",
    "project_disposition",
    "build_authority_recheck",
    "hook_envelope_resolver",
    "GovernanceHookError",
    "CompositionUnavailable",
    "MalformedDecision",
    "REASON_SOURCE_UNAVAILABLE",
    "REASON_RECORD_CAPACITY",
    "REASON_COMPOSITION_FAILED",
    "REASON_NOT_AUTHORITY_BOUND",
    "REASON_NO_AUTHORIZATION_REFERENCE",
    "REASON_MALFORMED_INPUTS",
    "REASON_NOT_A_FINAL_DISPOSITION",
    "REASON_NOT_EXECUTABLE",
    "REASON_UNKNOWN_DISPOSITION",
    "maturity",
]


def maturity() -> dict:
    """The package's own maturity claim, in a form a caller can assert on."""
    return {
        "stage": "Core implemented",
        "pilot_validated": False,
        "production_certified": False,
        "known_gaps": (
            "Risk Authority production_mode raises ProductionContainmentError; "
            "HOLD, DEFER, ESCALATE and MANUAL_REVIEW have no sink; "
            "no credential broker (cloud-scaling Phase 5X is unbuilt)"
        ),
    }
