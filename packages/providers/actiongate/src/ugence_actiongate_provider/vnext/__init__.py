"""ActionGate vNext — the deterministic policy evaluator (staged, not yet public).

This subpackage is deliberately **not** re-exported from
``ugence_actiongate_provider.api``. Everything the ActionGate ``.api`` surface
exports is covered by a literal snapshot hash that CI asserts byte-for-byte
(``actiongate-provider-package-ci.yml``, base
``9eeb66e31430d9e65982826e9910fc571fbae0331b797c5bb1b735bc53887300``) and by
``public_api_manifests`` in ``platform/PLATFORM_FREEZE_V1.json``. Adding a symbol
there is a versioned decision, not a side effect of landing an evaluator.

So this stages the semantics without moving a frozen surface: the evaluator is
complete and tested, the public path is untouched, and wiring it in becomes a
separate, explicitly classified change.

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
]
