"""Authenticated Authority Lifecycle Service (RA-6 §5, §10, §12.2).

The **single authorized mutator** of revocation/epoch state. Every write:

* requires an authenticated :class:`WriterPrincipal` (fail closed if absent);
* is authorized by an injected :class:`WriterAuthorizer` seam that verifies the
  principal holds the lifecycle-write capability for the **target tenant/scope**
  (least privilege; ActionGate/hot-path is never handed this service);
* is **tenant-isolated** — a principal bound to tenant A can never mutate tenant
  B (invariant, RA-6 §5.3);
* is **idempotent** — revoke = set union; ``advance_epoch`` idempotent under a
  caller-supplied ``change_id`` (R-2, I13/I14);
* emits an **append-only, attributed** ``GovernanceEvent``
  (``AUTHORITY_EPOCH_ADVANCED`` / ``ENVELOPE_REVOKED``) carrying actor, reason,
  correlation id, target, and idempotency key (RA-6 §11).

Authentication itself is delegated to the deployment (mTLS / workload identity /
signed token), exactly like RA-5's trusted-ingress seam. This package ships the
neutral seam and a **reference** authorizer for conformance; production mode
**refuses** the reference authorizer (the RA-5 F-1 pattern) so a permissive
stand-in can never silently authorize real writes.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable, Optional, Protocol, Tuple, runtime_checkable

from risk_authority.domain.enums import GovernanceEventType
from risk_authority.domain.events import GovernanceEvent, make_event
from risk_authority.integrations.authority_lifecycle import (
    LifecycleOutcome,
    LifecycleWriteResult,
    WriterPrincipal,
)

from .store import ReferenceAuthorityStore

__all__ = [
    "LIFECYCLE_WRITE_CAPABILITY",
    "EMERGENCY_STOP_CAPABILITY",
    "WriterAuthorizer",
    "ReferenceWriterAuthorizer",
    "AuthorityLifecycleService",
    "ReferenceWriterRejectedError",
]

#: Capability a principal must hold to advance an epoch or revoke a target.
LIFECYCLE_WRITE_CAPABILITY = "authority.lifecycle.write"
#: Stronger capability required for the privileged emergency-stop path (RA-6 §12).
EMERGENCY_STOP_CAPABILITY = "authority.lifecycle.emergency_stop"


class ReferenceWriterRejectedError(RuntimeError):
    """Raised when a reference authorizer is wired into production (F-1)."""


@runtime_checkable
class WriterAuthorizer(Protocol):
    """The deployment's authorization seam for lifecycle writes (RA-6 §5.3).

    Returns ``(authorized, reasons)``. A production implementation checks the
    authenticated principal against the deployment's IAM / ``AuthorityRegistry``
    grants for the target tenant/scope. This package invents no IAM.
    """

    #: Production composition refuses any authorizer that marks itself reference.
    is_reference_authorizer: bool

    def authorize(
        self,
        *,
        principal: WriterPrincipal,
        tenant_id: str,
        operation: str,
        capability: str,
    ) -> Tuple[bool, Tuple[str, ...]]:
        ...


class ReferenceWriterAuthorizer:
    """A conformance authorizer: trusts the principal's declared capabilities.

    It authenticates NOTHING — it treats ``principal.capabilities`` as ground
    truth, which is only valid when the capabilities were established by a real
    authenticated channel out of band. It exists so the lifecycle-write *flow*
    can be exercised deterministically. Because it is a stand-in, it is flagged
    ``is_reference_authorizer = True`` and **production mode refuses it**; wiring
    it into production would reopen the write-authorization gap.
    """

    is_reference_authorizer = True

    def authorize(
        self,
        *,
        principal: WriterPrincipal,
        tenant_id: str,
        operation: str,
        capability: str,
    ) -> Tuple[bool, Tuple[str, ...]]:
        if principal.tenant_id != tenant_id:
            return False, (
                f"principal tenant {principal.tenant_id!r} != target {tenant_id!r}",
            )
        if capability not in principal.capabilities:
            return False, (f"principal lacks capability {capability!r}",)
        return True, ()


class AuthorityLifecycleService:
    """The sole authorized writer of revocation/epoch state."""

    def __init__(
        self,
        store: ReferenceAuthorityStore,
        authorizer: WriterAuthorizer,
        *,
        event_sink: Optional[Callable[[GovernanceEvent], None]] = None,
        clock: Callable[[], datetime],
        production_mode: bool = False,
    ) -> None:
        if authorizer is None:  # fail closed: no authorization seam ⇒ no writes
            raise ReferenceWriterRejectedError(
                "AuthorityLifecycleService requires a WriterAuthorizer (fail closed)"
            )
        if production_mode and getattr(authorizer, "is_reference_authorizer", False):
            # RA-5 F-1 symmetry: a reference stand-in is rejected in production.
            raise ReferenceWriterRejectedError(
                "reference WriterAuthorizer refused in production mode (RA-6 §5.3): "
                "inject the deployment's authenticated authorizer"
            )
        self._store = store
        self._authorizer = authorizer
        self._event_sink = event_sink
        self._clock = clock
        self._production_mode = production_mode
        self._seq = 0
        self._seq_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Internal helpers.                                                   #
    # ------------------------------------------------------------------ #
    def _reject(self, reasons: Tuple[str, ...], correlation_id: str) -> LifecycleWriteResult:
        return LifecycleWriteResult(
            outcome=LifecycleOutcome.ERROR_NON_EXECUTABLE,
            reasons=reasons,
            correlation_id=correlation_id,
        )

    def _guard(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        operation: str,
        capability: str,
        correlation_id: str,
    ) -> Optional[LifecycleWriteResult]:
        """Fail-closed authentication+authorization gate. None ⇒ authorized."""

        if principal is None:
            return self._reject(("no authenticated principal",), correlation_id)
        if getattr(principal, "is_reference", False) and self._production_mode:
            return self._reject(
                ("reference principal refused in production mode",), correlation_id
            )
        if principal.tenant_id != tenant_id:
            # Tenant isolation: a writer for tenant A can never mutate tenant B.
            return self._reject(
                (f"cross-tenant write refused: {principal.tenant_id!r} -> {tenant_id!r}",),
                correlation_id,
            )
        ok, reasons = self._authorizer.authorize(
            principal=principal,
            tenant_id=tenant_id,
            operation=operation,
            capability=capability,
        )
        if not ok:
            return self._reject(reasons, correlation_id)
        return None

    def _emit(
        self,
        *,
        event_type: GovernanceEventType,
        tenant_id: str,
        principal: WriterPrincipal,
        aggregate_id: str,
        reason: str,
        correlation_id: str,
        idempotency_key: str,
        target_kind: str,
        target_id: str,
        epoch: int,
    ) -> str:
        with self._seq_lock:
            self._seq += 1
            seq = self._seq
        event = make_event(
            event_id=f"ra6_{event_type.value}_{tenant_id}_{seq:06d}",
            tenant_id=tenant_id,
            event_type=event_type,
            aggregate_id=aggregate_id,
            actor=principal.principal_id,
            timestamp=self._clock(),
            correlation_id=correlation_id,
            payload={
                "reason": reason,
                "target_kind": target_kind,
                "target_id": target_id,
                "epoch": epoch,
                "idempotency_key": idempotency_key,
            },
            attributes={
                "reason": reason,
                "target_kind": target_kind,
                "target_id": target_id,
                "epoch": str(epoch),
                "idempotency_key": idempotency_key,
                "principal": principal.principal_id,
            },
        )
        if self._event_sink is not None:
            self._event_sink(event)
        return event.event_id

    # ------------------------------------------------------------------ #
    # AuthorityLifecycleWriter.                                           #
    # ------------------------------------------------------------------ #
    def advance_epoch(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        change_id: str,
        reason: str,
        correlation_id: str,
        capability: str = LIFECYCLE_WRITE_CAPABILITY,
    ) -> LifecycleWriteResult:
        rejected = self._guard(
            principal=principal,
            tenant_id=tenant_id,
            operation="advance_epoch",
            capability=capability,
            correlation_id=correlation_id,
        )
        if rejected is not None:
            return rejected
        assert principal is not None
        epoch, changed = self._store.advance_epoch(tenant_id, change_id)
        if not changed:
            # Idempotent no-op (duplicate change_id): a successful non-change.
            return LifecycleWriteResult(
                outcome=LifecycleOutcome.NO_STATE_CHANGE,
                reasons=(f"duplicate change_id {change_id!r}",),
                epoch=epoch,
                correlation_id=correlation_id,
            )
        event_id = self._emit(
            event_type=GovernanceEventType.AUTHORITY_EPOCH_ADVANCED,
            tenant_id=tenant_id,
            principal=principal,
            aggregate_id=tenant_id,
            reason=reason,
            correlation_id=correlation_id,
            idempotency_key=change_id,
            target_kind="TENANT",
            target_id=tenant_id,
            epoch=epoch,
        )
        return LifecycleWriteResult(
            outcome=LifecycleOutcome.APPLIED,
            epoch=epoch,
            event_id=event_id,
            correlation_id=correlation_id,
        )

    def _revoke(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        target_kind: str,
        target_id: str,
        do_revoke: Callable[[], bool],
        reason: str,
        correlation_id: str,
        capability: str,
    ) -> LifecycleWriteResult:
        rejected = self._guard(
            principal=principal,
            tenant_id=tenant_id,
            operation=f"revoke_{target_kind.lower()}",
            capability=capability,
            correlation_id=correlation_id,
        )
        if rejected is not None:
            return rejected
        assert principal is not None
        changed = do_revoke()
        epoch = self._store.current_epoch(tenant_id)
        if not changed:
            return LifecycleWriteResult(
                outcome=LifecycleOutcome.NO_STATE_CHANGE,
                reasons=(f"{target_kind.lower()} {target_id!r} already revoked",),
                epoch=epoch,
                correlation_id=correlation_id,
            )
        event_id = self._emit(
            event_type=GovernanceEventType.ENVELOPE_REVOKED,
            tenant_id=tenant_id,
            principal=principal,
            aggregate_id=target_id or tenant_id,
            reason=reason,
            correlation_id=correlation_id,
            idempotency_key=f"{target_kind}:{target_id}",
            target_kind=target_kind,
            target_id=target_id,
            epoch=epoch,
        )
        return LifecycleWriteResult(
            outcome=LifecycleOutcome.APPLIED,
            epoch=epoch,
            event_id=event_id,
            correlation_id=correlation_id,
        )

    def revoke_envelope(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        envelope_id: str,
        reason: str,
        correlation_id: str,
        capability: str = LIFECYCLE_WRITE_CAPABILITY,
    ) -> LifecycleWriteResult:
        return self._revoke(
            principal=principal,
            tenant_id=tenant_id,
            target_kind="ENVELOPE",
            target_id=envelope_id,
            do_revoke=lambda: self._store.revoke_envelope(tenant_id, envelope_id),
            reason=reason,
            correlation_id=correlation_id,
            capability=capability,
        )

    def revoke_subject(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        subject_id: str,
        reason: str,
        correlation_id: str,
        capability: str = LIFECYCLE_WRITE_CAPABILITY,
    ) -> LifecycleWriteResult:
        return self._revoke(
            principal=principal,
            tenant_id=tenant_id,
            target_kind="SUBJECT",
            target_id=subject_id,
            do_revoke=lambda: self._store.revoke_subject(tenant_id, subject_id),
            reason=reason,
            correlation_id=correlation_id,
            capability=capability,
        )

    def revoke_model(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        model_id: str,
        reason: str,
        correlation_id: str,
        capability: str = LIFECYCLE_WRITE_CAPABILITY,
    ) -> LifecycleWriteResult:
        return self._revoke(
            principal=principal,
            tenant_id=tenant_id,
            target_kind="MODEL",
            target_id=model_id,
            do_revoke=lambda: self._store.revoke_model(tenant_id, model_id),
            reason=reason,
            correlation_id=correlation_id,
            capability=capability,
        )

    # ------------------------------------------------------------------ #
    # Privileged emergency stop (RA-6 §12) — separate, stronger capability. #
    # ------------------------------------------------------------------ #
    def emergency_stop(
        self,
        *,
        principal: Optional[WriterPrincipal],
        tenant_id: str,
        change_id: str,
        reason: str,
        correlation_id: str,
    ) -> LifecycleWriteResult:
        """Immediate tenant-epoch advance under the privileged emergency capability.

        This is NOT an observer path: it requires ``EMERGENCY_STOP_CAPABILITY``
        (stronger than ordinary lifecycle write) so an ordinary telemetry
        producer can never invoke emergency-stop semantics (RA-6 §12).
        """

        return self.advance_epoch(
            principal=principal,
            tenant_id=tenant_id,
            change_id=change_id,
            reason=f"EMERGENCY_STOP: {reason}",
            correlation_id=correlation_id,
            capability=EMERGENCY_STOP_CAPABILITY,
        )
