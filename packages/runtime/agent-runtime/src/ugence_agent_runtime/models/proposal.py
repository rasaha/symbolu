"""Immutable transition proposal — the exact intended provider invocation.

Before a consequential transition, the runtime constructs a ``TransitionProposal``
that identifies *exactly* what it is about to do (workflow/instance/task, provider,
operation, canonicalized arguments, idempotency key, correlation). The proposal
carries a deterministic ``fingerprint`` over those identifying fields.

Governance evaluates the proposal, and a CLEAR result MUST be bound to the exact
fingerprint. The runtime then builds the provider invocation from the *same* proposal
and re-checks the fingerprint, so the permission it consumes provably applies to the
invocation it makes. Nothing here creates authority — the proposal is a description.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

PROPOSAL_VERSION = "1"


def _canonical(value: Any) -> Any:
    """Canonicalize arguments deterministically for fingerprinting."""
    if isinstance(value, dict):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    return value


def compute_fingerprint(
    workflow_id: str,
    instance_id: str,
    task_id: str,
    provider_id: str,
    operation: str,
    arguments: Dict[str, Any],
    idempotency_key: str,
    proposal_version: str = PROPOSAL_VERSION,
) -> str:
    payload = {
        "proposal_version": proposal_version,
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "task_id": task_id,
        "provider_id": provider_id,
        "operation": operation,
        "arguments": _canonical(arguments or {}),
        "idempotency_key": idempotency_key,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class TransitionProposal:
    workflow_id: str
    instance_id: str
    task_id: str
    provider_id: str
    operation: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: str = ""
    correlation_id: Optional[str] = None
    proposal_version: str = PROPOSAL_VERSION
    fingerprint: str = ""

    @classmethod
    def build(
        cls,
        *,
        workflow_id: str,
        instance_id: str,
        task_id: str,
        provider_id: str,
        operation: str,
        arguments: Optional[Dict[str, Any]] = None,
        idempotency_key: str = "",
        correlation_id: Optional[str] = None,
    ) -> "TransitionProposal":
        args = dict(arguments or {})
        fp = compute_fingerprint(
            workflow_id, instance_id, task_id, provider_id, operation, args,
            idempotency_key, PROPOSAL_VERSION,
        )
        return cls(
            workflow_id=workflow_id,
            instance_id=instance_id,
            task_id=task_id,
            provider_id=provider_id,
            operation=operation,
            arguments=args,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            proposal_version=PROPOSAL_VERSION,
            fingerprint=fp,
        )

    def recompute_fingerprint(self) -> str:
        return compute_fingerprint(
            self.workflow_id, self.instance_id, self.task_id, self.provider_id,
            self.operation, self.arguments, self.idempotency_key, self.proposal_version,
        )

    def is_intact(self) -> bool:
        """True when the stored fingerprint still matches the identifying fields."""
        return bool(self.fingerprint) and self.fingerprint == self.recompute_fingerprint()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_version": self.proposal_version,
            "workflow_id": self.workflow_id,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "operation": self.operation,
            "arguments": dict(self.arguments),
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "fingerprint": self.fingerprint,
        }
