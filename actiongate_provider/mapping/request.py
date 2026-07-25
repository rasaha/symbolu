"""Request mapping: neutral ActionGovernanceRequest → native ActionGateRequest.

Deterministic and total. Every field the neutral contract carries is preserved.

Intentionally lossy / not-populated (documented):

* ``tenant`` — the neutral ``ActionGovernanceRequest`` has no tenant field (the
  kernel adapter does not propagate it), so ActionGate's ``tenant`` is left empty;
* the neutral contract's ``risk_context`` / ``evidence_refs`` are preserved when
  present, but the current kernel adapter does not populate them.
"""

from __future__ import annotations

from governance_providers.api import ActionGovernanceRequest

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
    )
