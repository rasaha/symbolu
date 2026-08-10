"""Ugence Risk Authority Runtime — RA-4.5 fail-closed governance composition.

This integration package composes three independently packaged components into a
single, fail-closed execution-eligibility decision:

* ``ugence-risk-authority``          — machine capability authority (the owner;
                                       issues the signed ``RiskAuthorizationEnvelope``
                                       and enforces exact-action scope).
* ``ugence-decision-authority``      — human / organizational governance veto.
* ``ugence-actiongate-provider``     — supplementary action-policy veto / restriction.

**The corrected authority model** (see
``docs/architecture/RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION_PLAN.md``): Risk
Authority is the sole issuer of machine execution authority. Decision Authority
and ActionGate are *additive governance inputs* that may only **subtract**
authority (veto / hold / restrict) — never add it. The non-negotiable
invariants, true by construction:

    FinalAuthority ≤ RiskAuthority
    FinalScope    ⊆ RiskAuthorityScope

No permissive governance result can upgrade a Risk Authority ``DENY``, widen
scope, or manufacture authority. The signed ``RiskAuthorizationEnvelope`` remains
the sole machine-execution authority artifact; the ``GovernedExecutionDecision``
produced here *wraps* it with governance evidence — it never re-mints it.

Dependency direction (one-way; no cycle; RA stays a stdlib-only leaf):

    risk_authority  ◄──  risk_authority_runtime  ──►  decision-authority
                                              └────►  actiongate-provider

F-D (jurisdiction / autonomy / resource enforcement) remains a **separate** work
item, issue #1397 — RA-4.5 composition preserves current enforcement coverage
and explicitly does not close F-D.
"""

from __future__ import annotations

from .version import __version__
from .contracts import (
    EffectiveConstraints,
    FinalDisposition,
    GovernanceRestrictions,
    GovernanceVetoResult,
    GovernedExecutionDecision,
    ReasonCode,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
    VetoDisposition,
)
from .actiongate_adapter import ActionGatePolicyAdapter
from .decision_authority_adapter import (
    DecisionAuthorityGovernanceAdapter,
    DecisionAuthorityUnavailable,
)
from .composition import RiskAuthorityCompositionEngine
from .restrictions import apply_restrictions
from .effective_scope import (
    effective_scope_authorizes,
    effective_scope_violations,
)
from .risk_authority_enforcer import RiskAuthorityEnforcer

__all__ = [
    "__version__",
    # Contracts
    "RiskAuthorityDisposition",
    "VetoDisposition",
    "FinalDisposition",
    "ReasonCode",
    "GovernanceRestrictions",
    "GovernanceVetoResult",
    "RiskAuthorityMachineResult",
    "EffectiveConstraints",
    "GovernedExecutionDecision",
    # Adapters
    "DecisionAuthorityGovernanceAdapter",
    "DecisionAuthorityUnavailable",
    "ActionGatePolicyAdapter",
    # Enforcement + composition
    "RiskAuthorityEnforcer",
    "RiskAuthorityCompositionEngine",
    "apply_restrictions",
    "effective_scope_violations",
    "effective_scope_authorizes",
]
