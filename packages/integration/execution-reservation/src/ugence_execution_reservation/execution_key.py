"""The canonical execution key — *which authorized action is being executed once?*

Exactly the key the prerequisites design ratified (``EXECUTION_KEY.md``):

    (tenant_id, authorization_ref, authorized_action_fingerprint, target_ref, operation)

Stable across retries, unique across distinct authorized actions, and
deliberately **excluding the clearance receipt reference**: a re-issued receipt
for the same action (fresher signals) must not mint a new key, or one-time-use
would be defeated. The receipt is validated at reservation time, not folded in.

Serialization is ``exec_key.v1:<sha256hex>`` over a domain-separated canonical
JSON preimage. That string is what Decision Authority's
``execution_idempotency_key`` carries. The neutral projection for the
governance-contracts idempotency family is ``IdempotencyKey(key=<that string>,
scope=GLOBAL, partition=tenant_id)``; its ``canonical_digest()`` is what a
producer places in ``ExecutionDispatchRequest.idempotency_key``.
"""

from __future__ import annotations

from dataclasses import dataclass

from ugence_governance_contracts.api import IdempotencyKey, IdempotencyScope

from ._canon import domain_digest, require_nonempty

__all__ = ["ExecutionKey", "EXECUTION_KEY_PREFIX"]

EXECUTION_KEY_PREFIX = "exec_key.v1:"


@dataclass(frozen=True)
class ExecutionKey:
    tenant_id: str
    authorization_ref: str
    authorized_action_fingerprint: str
    target_ref: str
    operation: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "authorization_ref", "authorized_action_fingerprint",
                     "target_ref", "operation"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), f"ExecutionKey.{name}"))

    @property
    def identity(self) -> tuple[str, str, str, str, str]:
        return (self.tenant_id, self.authorization_ref, self.authorized_action_fingerprint,
                self.target_ref, self.operation)

    def canonical_digest(self) -> str:
        return domain_digest("exec_key", {
            "tenant_id": self.tenant_id,
            "authorization_ref": self.authorization_ref,
            "authorized_action_fingerprint": self.authorized_action_fingerprint,
            "target_ref": self.target_ref,
            "operation": self.operation,
        })

    @property
    def serialized(self) -> str:
        """``exec_key.v1:<sha256hex>`` — the ledger's ``execution_idempotency_key``."""

        return EXECUTION_KEY_PREFIX + self.canonical_digest()

    def to_idempotency_key(self) -> IdempotencyKey:
        """Neutral projection: GLOBAL scope, the tenant as the opaque partition."""

        return IdempotencyKey(key=self.serialized, scope=IdempotencyScope.GLOBAL,
                              partition=self.tenant_id)

    def neutral_idempotency_digest(self) -> str:
        """What a producer places in ``ExecutionDispatchRequest.idempotency_key``."""

        return self.to_idempotency_key().canonical_digest()
