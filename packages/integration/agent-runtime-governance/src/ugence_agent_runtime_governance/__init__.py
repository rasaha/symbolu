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
Risk Authority ``production_mode`` still raises ``ProductionContainmentError``. An
ESCALATE now has a sink: since GAS-7 a human sees the parked instance and their approval
releases it. A HOLD still has none, and that is the ruling rather than a missing part —
a HOLD carrying no required approval is released upstream, never by an approval (HR-5).
DEFER and MANUAL_REVIEW are not this package's to sink: the projection never emits them.
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
            "HOLD has no sink: an ESCALATE is released by a human approval since "
            "GAS-7, but a HOLD carrying no required approval is released only "
            "upstream, never by an approval (HR-5); "
            "no credential broker (cloud-scaling Phase 5X is unbuilt)"
        ),
    }
