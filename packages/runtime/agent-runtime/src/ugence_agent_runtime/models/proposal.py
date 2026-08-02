"""Immutable transition proposal — the exact intended provider invocation.

Before a consequential transition, the runtime constructs a ``TransitionProposal``
that identifies *exactly* what it is about to do (workflow/instance/task, provider,
operation, deeply-frozen canonical arguments, idempotency key, correlation). The
proposal carries a deterministic ``fingerprint`` over **all** of those identifying
fields, including the correlation id.

Identity is deeply immutable: arguments are recursively frozen at construction, so
neither the caller (after construction) nor a governance hook can mutate what was
evaluated. Provider invocation arguments are re-materialized as fresh mutable
structures only after clearance validation, and the invocation is re-fingerprinted
immediately before the provider call so the permission consumed provably applies to
the exact call made. Nothing here creates authority — the proposal is a description.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Optional

from ..runtime.errors import ProposalError

PROPOSAL_VERSION = "1"

# Scalar argument types that are inherently immutable and JSON-canonicalizable.
_SCALARS = (str, int, float, bool, type(None))


def _freeze(value: Any) -> Any:
    """Recursively convert a supported value into a deeply immutable representation.

    Mappings become read-only ``MappingProxyType`` over frozen values, sequences
    become tuples of frozen values, sets become ``frozenset`` of frozen values, and
    scalars pass through. Any unsupported type fails closed with ``ProposalError``
    rather than relying on unstable ``repr()`` output for identity.
    """
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, Mapping):
        frozen = {}
        for k in value:
            if not isinstance(k, str):
                raise ProposalError(
                    f"proposal argument mapping keys must be strings, got {type(k).__name__}"
                )
            frozen[k] = _freeze(value[k])
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(v) for v in value)
    raise ProposalError(
        f"unsupported proposal argument type: {type(value).__name__} "
        "(supported: str, int, float, bool, None, mapping, list, tuple, set)"
    )


def _thaw(value: Any) -> Any:
    """Reverse of :func:`_freeze` — materialize fresh mutable structures for the
    provider invocation. Semantically equal to the frozen value; never aliases it."""
    if isinstance(value, Mapping):
        return {k: _thaw(value[k]) for k in value}
    if isinstance(value, (tuple, list)):
        return [_thaw(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_thaw(v) for v in _sorted_set(value)]
    return value


def _sorted_set(values):
    try:
        return sorted(values, key=lambda v: json.dumps(_canonical(v), sort_keys=True))
    except TypeError:
        return list(values)


def _canonical(value: Any) -> Any:
    """Deterministic JSON-ready canonical form. Frozen and plain structures alike map
    to the same canonical shape (a list and a tuple both become a JSON array; a dict
    and a MappingProxyType both become a sorted object), so a re-materialized
    invocation re-fingerprints to the exact value governance evaluated."""
    if isinstance(value, bool) or value is None or isinstance(value, (str, int, float)):
        return value
    if isinstance(value, Mapping):
        return {k: _canonical(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_canonical(v) for v in _sorted_set(value)]
    raise ProposalError(f"unsupported argument type for canonicalization: {type(value).__name__}")


def compute_fingerprint(
    workflow_id: str,
    instance_id: str,
    task_id: str,
    provider_id: str,
    operation: str,
    arguments: Any,
    idempotency_key: str,
    correlation_id: Optional[str],
    proposal_version: str = PROPOSAL_VERSION,
) -> str:
    payload = {
        "proposal_version": proposal_version,
        "workflow_id": workflow_id,
        "instance_id": instance_id,
        "task_id": task_id,
        "provider_id": provider_id,
        "operation": operation,
        "arguments": _canonical(arguments if arguments is not None else {}),
        "idempotency_key": idempotency_key,
        "correlation_id": correlation_id,
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
    arguments: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
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
        arguments: Optional[Mapping[str, Any]] = None,
        idempotency_key: str = "",
        correlation_id: Optional[str] = None,
    ) -> "TransitionProposal":
        # Deep-freeze the caller's arguments — we never retain a mutable structure by
        # reference, so later mutation of the caller's object cannot change identity.
        frozen_args = _freeze(dict(arguments) if arguments is not None else {})
        fp = compute_fingerprint(
            workflow_id, instance_id, task_id, provider_id, operation, frozen_args,
            idempotency_key, correlation_id, PROPOSAL_VERSION,
        )
        return cls(
            workflow_id=workflow_id,
            instance_id=instance_id,
            task_id=task_id,
            provider_id=provider_id,
            operation=operation,
            arguments=frozen_args,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            proposal_version=PROPOSAL_VERSION,
            fingerprint=fp,
        )

    def materialize_arguments(self) -> dict:
        """Return a FRESH, deeply mutable copy of the arguments for provider invocation.

        Semantically equal to what governance evaluated, but a new object graph, so the
        provider can mutate its arguments without affecting proposal identity."""
        return _thaw(self.arguments)

    def recompute_fingerprint(self) -> str:
        return compute_fingerprint(
            self.workflow_id, self.instance_id, self.task_id, self.provider_id,
            self.operation, self.arguments, self.idempotency_key, self.correlation_id,
            self.proposal_version,
        )

    def is_intact(self) -> bool:
        """True when the stored fingerprint still matches the identifying fields."""
        return bool(self.fingerprint) and self.fingerprint == self.recompute_fingerprint()

    def to_dict(self) -> dict:
        return {
            "proposal_version": self.proposal_version,
            "workflow_id": self.workflow_id,
            "instance_id": self.instance_id,
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "operation": self.operation,
            "arguments": _thaw(self.arguments),
            "idempotency_key": self.idempotency_key,
            "correlation_id": self.correlation_id,
            "fingerprint": self.fingerprint,
        }
