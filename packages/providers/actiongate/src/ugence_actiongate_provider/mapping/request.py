"""Request mapping: neutral ActionGovernanceRequest → native ActionGateRequest.

Deterministic and total. Every field the neutral contract carries is preserved.

``authorization_expired`` was previously the one exception — the only neutral
field this mapping dropped, while the control-plane adapter computed it and the
framework's own reference provider honoured it. ActionGate consequently
authorized actions under an expired authorization. It is now mapped, and a
regression test asserts the mapping is total against the neutral dataclass's
fields rather than against a hand-maintained list, so a future neutral field
cannot be added and silently ignored the same way.

Intentionally lossy / not-populated (documented):

* ``tenant`` — the neutral ``ActionGovernanceRequest`` has no tenant field (the
  kernel adapter does not propagate it), so ActionGate's ``tenant`` is left empty;
* the neutral contract's ``risk_context`` / ``evidence_refs`` are preserved when
  present, but the current kernel adapter does not populate them.
"""

from __future__ import annotations

from ugence_governance_provider_framework.api import ActionGovernanceRequest

from ..core import ActionGateRequest


def map_request(request: ActionGovernanceRequest) -> ActionGateRequest:
    return ActionGateRequest(
        action_type=request.action_type,
        parameters=dict(request.requested_parameters),
        principal=request.actor,
        authority=request.authority_context,
        resource=request.target_resource,
        policy_context=tuple(request.policy_refs),
        risk_context=dict(request.risk_context),
        evidence_refs=tuple(request.evidence_refs),
        decision_refs=tuple(request.decision_refs),
        tenant="",  # not carried by the neutral contract (documented)
        correlation_id=request.correlation_id,
        idempotency_key=request.idempotency_key,
        authorization_expired=request.authorization_expired,
    )
