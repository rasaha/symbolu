"""Action Control adapter — ActionGate ("may THIS exact action execute?").

Wraps the real ActionGate engine (``build_actiongate_provider``) through the
frozen ``actiongate_provider.api`` / ``governance_providers.api`` surfaces.

Every action is reduced to a canonical envelope and hashed into a stable
identity — the Canonical Execution Request (CER) id — which is the join key that
threads a single decision across Truth & Evidence, Action Control, operational
clearance, and the audit trail. Kernel-bound CER authorization via
``ActionGovernanceControlPlaneAdapter.authorize(action_request, cer)`` is the
productization path; here we compute the CER identity directly so the loop is
self-contained.
"""

from __future__ import annotations

import hashlib
import json

from ..models import ActionRequest, ActionVerdict

_available = True
_reason = ""
try:  # fail-safe import
    from actiongate_provider.configuration import build_actiongate_provider
    from governance_providers.api import ActionGovernanceRequest
    _provider = build_actiongate_provider()
except Exception as exc:  # noqa: BLE001
    _available = False
    _reason = f"{type(exc).__name__}: {exc}"
    _provider = None


def available() -> tuple[bool, str]:
    return _available, _reason


def _canonical_envelope(req: ActionRequest) -> dict:
    """The stable, hashable action envelope (order-independent)."""
    return {
        "action_type": req.action_type,
        "requested_parameters": dict(sorted(req.requested_parameters.items())),
        "actor": req.actor,
        "authority_context": req.authority_context,
        "target_resource": req.target_resource,
        "policy_refs": sorted(req.policy_refs),
    }


def cer_identity(req: ActionRequest) -> tuple[str, str]:
    """Return (cer_id, action_fingerprint) for the canonical action envelope."""
    envelope = _canonical_envelope(req)
    blob = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode()
    fingerprint = hashlib.sha256(blob).hexdigest()
    return f"cer-{fingerprint[:16]}", fingerprint


def authorize(req: ActionRequest) -> ActionVerdict:
    if not _available or _provider is None:
        raise RuntimeError(f"actiongate unavailable: {_reason}")

    cer_id, fingerprint = cer_identity(req)
    native = ActionGovernanceRequest(
        action_type=req.action_type,
        requested_parameters=dict(req.requested_parameters),
        actor=req.actor,
        authority_context=req.authority_context,
        target_resource=req.target_resource,
        policy_refs=tuple(req.policy_refs),
        risk_context=dict(req.risk_context),
        evidence_refs=tuple(req.evidence_refs),
        idempotency_key=cer_id,
        correlation_id=req.correlation_id,
        authorization_expired=req.authorization_expired,
    )
    res = _provider.authorize(native)
    return ActionVerdict(
        outcome=res.outcome.value,
        constraints=list(res.constraints),
        obligations=list(res.obligations),
        reason_codes=list(res.reason_codes),
        authority_basis=res.authority_basis,
        provider_trace_id=res.provider_trace_id,
        cer_id=cer_id,
        action_fingerprint=fingerprint,
    )
