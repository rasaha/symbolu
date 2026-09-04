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

__all__ = ["ArtifactBinding", "EnvelopeConditions", "EnvelopeBindings", "RiskAuthorizationEnvelope"]


@dataclass(frozen=True)
class EnvelopeConditions:
    """Runtime conditions attached to an envelope (spec §12 ``conditions``)."""

    context_minimization: bool = False
    human_approval_required_above_minor_units: Optional[int] = None
    trajectory_policy_id: Optional[str] = None
    # Opaque condition tokens the runtime must see satisfied before authorizing.
    required_conditions: tuple[str, ...] = ()


_HEX = frozenset("0123456789abcdef")


@dataclass(frozen=True)
class ArtifactBinding:
    """One verified upstream artifact the envelope commits to, by kind and digest.

    Phase 5 (ADR ``ADR_RISK_AUTHORITY_PHASE5_ENVELOPE_ISSUANCE_RATIFICATION`` D-2).
    ``kind`` is an opaque, composition-root-declared token — Risk Authority names
    no domain's artifacts — and ``digest`` is a bare lowercase sha-256 hex string.
    """

    kind: str
    digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind.strip() or self.kind != self.kind.strip():
            raise ValueError("ArtifactBinding.kind must be a non-blank token with no surrounding whitespace")
        if (not isinstance(self.digest, str) or len(self.digest) != 64
                or any(c not in _HEX for c in self.digest)):
            raise ValueError("ArtifactBinding.digest must be a lowercase 64-char sha-256 hex digest")


@dataclass(frozen=True)
class EnvelopeBindings:
    """Cryptographic bindings carried by the envelope (spec §12 ``bindings``).

    ``artifact_bindings`` (Phase 5, additive) commits the envelope to the verified
    upstream artifacts issuance was conditioned on; kinds are unique.
    """

    workflow_ir_digest: str
    evidence_snapshot_digest: str
    model_digest: str
    authority_epoch: int
    artifact_bindings: tuple[ArtifactBinding, ...] = ()

    def __post_init__(self) -> None:
        bindings = tuple(self.artifact_bindings)
        for b in bindings:
            if not isinstance(b, ArtifactBinding):
                raise ValueError("EnvelopeBindings.artifact_bindings must contain ArtifactBinding values")
        kinds = [b.kind for b in bindings]
        if len(set(kinds)) != len(kinds):
            raise ValueError("EnvelopeBindings.artifact_bindings kinds must be unique")
        object.__setattr__(self, "artifact_bindings", bindings)

    def binding_for(self, kind: str) -> Optional[ArtifactBinding]:
        for b in self.artifact_bindings:
            if b.kind == kind:
                return b
        return None


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
