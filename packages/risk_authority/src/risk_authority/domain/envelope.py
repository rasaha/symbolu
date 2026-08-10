"""RiskAuthorizationEnvelope — the central runtime artifact (spec §12).

The envelope is a compact, signed, scoped, time-bound capability derived from a
:class:`~risk_authority.domain.decision.RiskDecision`. It is immutable and
verifiable offline on the hot path. Its scope can never exceed the decision's
scope (spec §29 envelope monotonicity, AC-04) — that invariant is enforced by
the issuer, not trusted here.

The ``signature`` field is excluded from the canonical signing payload (see the
``canonical=False`` metadata) so ``signing_payload`` is stable and a tampered
body is detectable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..crypto.canonical import canonical_bytes
from .scope import Scope

__all__ = ["EnvelopeConditions", "EnvelopeBindings", "RiskAuthorizationEnvelope"]


@dataclass(frozen=True)
class EnvelopeConditions:
    """Runtime conditions attached to an envelope (spec §12 ``conditions``)."""

    context_minimization: bool = False
    human_approval_required_above_minor_units: Optional[int] = None
    trajectory_policy_id: Optional[str] = None
    # Opaque condition tokens the runtime must see satisfied before authorizing.
    required_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class EnvelopeBindings:
    """Cryptographic bindings carried by the envelope (spec §12 ``bindings``)."""

    workflow_ir_digest: str
    evidence_snapshot_digest: str
    model_digest: str
    authority_epoch: int


@dataclass(frozen=True)
class RiskAuthorizationEnvelope:
    """A signed runtime authority scope consumed by ActionGate."""

    envelope_id: str
    issuer: str
    audience: str
    subject: str  # actor_id
    tenant_id: str
    session_id: str
    nonce: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    decision_id: str
    model_id: str
    scope: Scope
    conditions: EnvelopeConditions
    bindings: EnvelopeBindings
    key_id: str
    signature_alg: str = ""
    # Excluded from the canonical signing payload.
    signature: bytes = field(default=b"", metadata={"canonical": False})

    def signing_payload(self) -> bytes:
        """Canonical bytes over the whole envelope minus the signature."""

        return canonical_bytes(self)

    def is_temporally_valid(self, now: datetime) -> bool:
        return self.not_before <= now <= self.expires_at
