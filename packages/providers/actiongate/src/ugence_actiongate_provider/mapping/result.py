"""Result mapping: native ActionGateDecision → neutral ActionGovernanceResult.

Outcome map (unknown never authorizes):

    ALLOW                  → AUTHORIZED
    ALLOW_WITH_CONSTRAINTS → AUTHORIZED_WITH_CONSTRAINTS
    DENY                   → DENIED
    UNKNOWN                → INDETERMINATE
    EXPIRED                → EXPIRED

``EXPIRED`` completes the map. The neutral contract has carried that outcome
since it was written and the kernel has an ``EXPIRED`` authorization state, but
ActionGate had no native counterpart, so an expired authorization could only be
reported as something else. Composing this map with ``core.TIER_TO_NATIVE``
reproduces ``vnext.NEUTRAL_OUTCOME_V2`` exactly.

Preserves constraints, obligations, expiry, authority basis, reason codes, trace
id, and publishes a deterministic result fingerprint.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional

from ugence_governance_provider_framework.api import ActionGovernanceOutcome, ActionGovernanceResult

from ..core import ActionGateDecision, ActionGateOutcome
from .constraints import encode_constraints, encode_obligations

_OUTCOME_MAP = {
    ActionGateOutcome.ALLOW: ActionGovernanceOutcome.AUTHORIZED,
    ActionGateOutcome.ALLOW_WITH_CONSTRAINTS: ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS,
    ActionGateOutcome.DENY: ActionGovernanceOutcome.DENIED,
    ActionGateOutcome.UNKNOWN: ActionGovernanceOutcome.INDETERMINATE,
    ActionGateOutcome.EXPIRED: ActionGovernanceOutcome.EXPIRED,
}

#: The framework mapping-contract version (published in observability).
#:
#: Bumped to -2 by the MAJOR change that made ``authorization_expired`` a mapped
#: field and ``EXPIRED`` a native outcome. The mapping contract itself changed —
#: an observability record stamped -1 and one stamped -2 describe different
#: request/result translations, and the version is how a consumer tells them
#: apart after the fact.
MAPPING_VERSION = "actiongate-map-2"


def _fingerprint(decision: ActionGateDecision, outcome: ActionGovernanceOutcome,
                 constraints: tuple[str, ...], obligations: tuple[str, ...]) -> str:
    payload = json.dumps({
        "outcome": outcome.value, "constraints": sorted(constraints),
        "obligations": sorted(obligations), "trace": decision.trace_id,
        "reasons": sorted(decision.reason_codes),
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def map_result(decision: ActionGateDecision, *, now: Optional[datetime] = None
               ) -> ActionGovernanceResult:
    # Unknown / unmapped native outcome must never authorize.
    outcome = _OUTCOME_MAP.get(decision.outcome, ActionGovernanceOutcome.INDETERMINATE)
    constraints = encode_constraints(decision.constraints)
    obligations = encode_obligations(decision.obligations)
    expiry = None
    if decision.expiry_seconds is not None and now is not None:
        expiry = now + timedelta(seconds=decision.expiry_seconds)
    fp = _fingerprint(decision, outcome, constraints, obligations)
    return ActionGovernanceResult(
        outcome=outcome, constraints=constraints, obligations=obligations,
        expiry=expiry, authority_basis=decision.authority_basis,
        reason_codes=decision.reason_codes, provider_trace_id=decision.trace_id,
        fingerprint=fp)
