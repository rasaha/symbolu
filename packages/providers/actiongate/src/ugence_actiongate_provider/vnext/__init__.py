"""ActionGate vNext — the deterministic policy evaluator.

``ActionGateEngine.evaluate`` delegates here, so this is where every governance
dimension the neutral contract carries is actually read. The policy types are
re-exported from ``ugence_actiongate_provider.api``; that export, and the native
``EXPIRED`` outcome it accompanies, are the MAJOR change that moved the frozen
``.api`` snapshot hash and ``public_api_manifests``.

Provenance: reduced from the ActionGate reference evaluator at
``cyber_security/action_gate_reference/action_gate_ref/`` (195 tests, gated by
``action-gate-reference-ci.yml``). The severity lattice and non-compensatory
aggregation are that evaluator's; the closed-catalogue-plus-default-tier shape
follows ``ugence_action_clearance.reason_codes``, which is a downstream
narrowing capability that consumes an already-authorized action — it is not
imported here and cannot create authorization.
"""

from __future__ import annotations

from .evaluator import (
    NEUTRAL_OUTCOME_STAGED,
    NEUTRAL_OUTCOME_V2,
    VNextDecision,
    evaluate,
)
from .expiry import is_expired
from .policy import ActionGatePolicy, ParameterBound
from .reason_codes import (
    DEFAULT_TIER,
    NON_SOFTENABLE,
    TIER_PRECEDENCE,
    ActionGateReasonCode,
    ActionGateTier,
    canonical_reason_order,
    combine_tiers,
    default_tier,
)
from .request import VNextAuthorizationRequest

__all__ = [
    "ActionGatePolicy",
    "ParameterBound",
    "VNextAuthorizationRequest",
    "VNextDecision",
    "evaluate",
    "ActionGateReasonCode",
    "ActionGateTier",
    "TIER_PRECEDENCE",
    "DEFAULT_TIER",
    "NON_SOFTENABLE",
    "combine_tiers",
    "default_tier",
    "canonical_reason_order",
    "NEUTRAL_OUTCOME_STAGED",
    "NEUTRAL_OUTCOME_V2",
    "is_expired",
]
