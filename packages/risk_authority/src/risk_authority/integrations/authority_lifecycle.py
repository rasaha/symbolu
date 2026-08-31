"""Neutral RA-6 authority-lifecycle ports (RA-6 §12).

Three **segregated** Protocols, owned by the stdlib-only leaf, implemented by the
``ugence-risk-authority-status-runtime`` control-plane package. Read/write
segregation is deliberate (RA-6 §12): it materially enforces least privilege —
ActionGate / the hot path holds only :class:`AuthorityStatusReader` and can never
be handed the writer.

    AuthorityStatusReader          READ  — current epoch, revocation lookup,
                                           init/freshness metadata (offline)
    AuthorityLifecycleWriter       WRITE — advance_epoch / revoke_* (authenticated)
    AuthorityReassessmentSignalPort INTAKE — receive neutral material-change
                                           signals; never returns authority

The leaf defines the contracts and the neutral value types; it imports no
persistence, messaging, or service client (invariant I8; RA-6 §7.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from ..domain.authority_signal import AuthorityReassessmentSignal
from ..services.authority_status import AuthorityStatusSnapshot

__all__ = [
    "WriterPrincipal",
    "LifecycleOutcome",
    "LifecycleWriteResult",
    "SignalDisposition",
    "SignalAck",
    "AuthorityStatusReader",
    "AuthorityLifecycleWriter",
    "AuthorityReassessmentSignalPort",
]


# ---------------------------------------------------------------------------
# Value types (neutral; carry no authority).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WriterPrincipal:
    """An authenticated principal presenting a lifecycle write (RA-6 §5.3).

    Identity is established **out of band by the deployment** (mTLS / workload
    identity / signed token) — the leaf carries the identity, never authenticates
    it. ``is_reference`` marks a conformance/test stand-in that production
    composition must refuse (the RA-5 F-1 pattern), so a permissive stand-in can
    never silently authorize production writes.
    """

    principal_id: str
    tenant_id: str
    capabilities: frozenset[str] = frozenset()
    is_reference: bool = False


class LifecycleOutcome(str, Enum):
    """Outcome of a lifecycle write command (RA-6 §14 vocabulary)."""

    APPLIED = "APPLIED"
    NO_STATE_CHANGE = "NO_STATE_CHANGE"
    ERROR_NON_EXECUTABLE = "ERROR_NON_EXECUTABLE"


@dataclass(frozen=True)
class LifecycleWriteResult:
    """The audited result of a lifecycle write (RA-6 §12.2).

    ``APPLIED`` — the state changed (epoch advanced / target revoked).
    ``NO_STATE_CHANGE`` — idempotent no-op (duplicate ``change_id``, already
    revoked, or a rejected rollback) — a *successful* non-change, not an error.
    ``ERROR_NON_EXECUTABLE`` — the write was rejected (unauthorized / tenant
    mismatch); no state changed (invariant I12).
    """

    outcome: LifecycleOutcome
    reasons: tuple[str, ...] = ()
    epoch: Optional[int] = None
    event_id: Optional[str] = None
    correlation_id: str = ""

    @property
    def state_changed(self) -> bool:
        return self.outcome is LifecycleOutcome.APPLIED


class SignalDisposition(str, Enum):
    """How a reassessment-signal intake resolved (RA-6 §12.3)."""

    ACCEPTED_FOR_REASSESSMENT = "ACCEPTED_FOR_REASSESSMENT"
    IGNORED = "IGNORED"


@dataclass(frozen=True)
class SignalAck:
    """The acknowledgement returned by the signal intake — never an authority.

    A signal is an intake event, not a decision: the ack says only whether the
    signal was accepted for reassessment or ignored (dedupe / malformed). It
    carries no ``ALLOW``, no scope, no authority token (invariant I2/I7).
    """

    disposition: SignalDisposition
    reasons: tuple[str, ...] = ()
    correlation_id: str = ""


# ---------------------------------------------------------------------------
# Ports (Protocols).
# ---------------------------------------------------------------------------
@runtime_checkable
class AuthorityStatusReader(Protocol):
    """READ-ONLY authority status for the hot path (RA-6 §12.1).

    Every method reads a **local bounded-stale snapshot** (RA-6 §4) — never a
    synchronous central call. No authority is required to read; least privilege
    is enforced by there being no write method here at all.
    """

    def snapshot(self, *, tenant_id: str) -> AuthorityStatusSnapshot:
        """Return the local snapshot (revocation predicate + freshness) for a tenant."""
        ...

    def current_epoch(self, tenant_id: str) -> int:
        """The tenant's current authority epoch as this cache last observed it."""
        ...

    def is_initialized(self, *, tenant_id: str) -> bool:
        """False until the first successful sync for ``tenant_id`` (R-1)."""
        ...

    def as_of(self, *, tenant_id: str) -> Optional[datetime]:
        """The instant of the last successful sync, or ``None`` if never synced."""
        ...


@runtime_checkable
class AuthorityLifecycleWriter(Protocol):
    """WRITE-ONLY authority lifecycle mutation (RA-6 §12.2).

    The sole mutator of revocation/epoch state. Every write requires an
    authenticated :class:`WriterPrincipal` holding the lifecycle-write capability
    for the target tenant/scope, emits an append-only audit event, is
    tenant-isolated, and is idempotent (revoke = set union; ``advance_epoch``
    idempotent under a caller-supplied ``change_id``). Fails closed without an
    authenticated principal (RA-6 §5.3).
    """

    def advance_epoch(
        self,
        *,
        principal: WriterPrincipal,
        tenant_id: str,
        change_id: str,
        reason: str,
        correlation_id: str,
    ) -> LifecycleWriteResult:
        ...

    def revoke_envelope(
        self,
        *,
        principal: WriterPrincipal,
        tenant_id: str,
        envelope_id: str,
        reason: str,
        correlation_id: str,
    ) -> LifecycleWriteResult:
        ...

    def revoke_subject(
        self,
        *,
        principal: WriterPrincipal,
        tenant_id: str,
        subject_id: str,
        reason: str,
        correlation_id: str,
    ) -> LifecycleWriteResult:
        ...

    def revoke_model(
        self,
        *,
        principal: WriterPrincipal,
        tenant_id: str,
        model_id: str,
        reason: str,
        correlation_id: str,
    ) -> LifecycleWriteResult:
        ...


@runtime_checkable
class AuthorityReassessmentSignalPort(Protocol):
    """INTAKE for neutral material-change signals (RA-6 §12.3).

    Receives an :class:`AuthorityReassessmentSignal`, deduplicates it, and
    triggers reassessment. It NEVER returns authority and NEVER carries an
    ALLOW / scope escalation — only a :class:`SignalAck`.
    """

    def submit(self, signal: AuthorityReassessmentSignal) -> SignalAck:
        ...
