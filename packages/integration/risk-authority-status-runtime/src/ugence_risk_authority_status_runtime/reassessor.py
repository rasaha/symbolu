"""Signal intake + reassessment (RA-6 §6, §12.3, §13, §14).

A neutral :class:`AuthorityReassessmentSignal` is the ONLY thing an observer may
emit toward Risk Authority. The reassessor:

  1. validates the signal (malformed ⇒ ``IGNORE_EVENT`` + no mutation);
  2. deduplicates by ``event_id`` (duplicate ⇒ ``IGNORE_EVENT``);
  3. **reassesses against current authoritative state** and lets Risk Authority
     decide the lifecycle consequence (default path §6) — never a direct grant;
  4. executes any consequence through the authenticated writer using the RA
     automated-reassessor system principal (§5.2(a)).

Because reassessment reads current truth and the writer is monotonic/idempotent,
duplicate / stale / out-of-order signals are safe (they converge to the same
state; §14). A malformed or untrusted signal can only ever be ignored — it can
never mint, widen, or silently revoke authority (invariants I2/I7).

``TENANT_EMERGENCY_STOP`` is deliberately **refused** on this ordinary observer
intake: emergency stop is a privileged administrative direct write
(``AuthorityLifecycleService.emergency_stop``), not something an ordinary
telemetry producer can trigger by emitting a signal (RA-6 §12).

The mapping from a validated signal to a lifecycle action lives behind a
:class:`ReassessmentDecider` seam. This package ships a **reference** decider
(a deterministic category→action map); a production deployment injects the real
evidence/policy-driven reassessment (RA-5 machinery), which is out of scope here.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Set, runtime_checkable

from risk_authority.domain.authority_signal import (
    AuthorityReassessmentSignal,
    SignalChangeType,
    SignalTargetType,
)
from risk_authority.integrations.authority_lifecycle import (
    LifecycleWriteResult,
    SignalAck,
    SignalDisposition,
    WriterPrincipal,
)

from .writer import AuthorityLifecycleService

__all__ = [
    "ReassessmentActionKind",
    "ReassessmentAction",
    "ReassessmentDecider",
    "ReferenceReassessmentDecider",
    "AuthorityReassessor",
]


class ReassessmentActionKind(str, Enum):
    """The lifecycle consequence a reassessment resolves to."""

    NONE = "NONE"
    REVOKE_ENVELOPE = "REVOKE_ENVELOPE"
    REVOKE_SUBJECT = "REVOKE_SUBJECT"
    REVOKE_MODEL = "REVOKE_MODEL"
    ADVANCE_EPOCH = "ADVANCE_EPOCH"


@dataclass(frozen=True)
class ReassessmentAction:
    """A neutral lifecycle consequence — carries no authority, only a directive."""

    kind: ReassessmentActionKind
    target_id: str = ""
    reason: str = ""


@runtime_checkable
class ReassessmentDecider(Protocol):
    """Decides the lifecycle consequence of a validated signal against current state."""

    is_reference_decider: bool

    def decide(
        self, signal: AuthorityReassessmentSignal
    ) -> ReassessmentAction:
        ...


class ReferenceReassessmentDecider:
    """Deterministic reference category→action map (RA-6 §13 categories).

    This is NOT the production reassessment: it does not re-read evidence,
    control-assurance, or policy artifacts. It maps a signal's bounded category
    and target to the smallest fail-closed lifecycle consequence, so the
    signal→reassess→consequence flow is exercisable deterministically. Production
    injects the real evidence/policy-driven decider.
    """

    is_reference_decider = True

    def decide(self, signal: AuthorityReassessmentSignal) -> ReassessmentAction:
        ct = signal.change_type
        tgt = signal.target
        reason = f"{ct.value}: {signal.reason}"

        if ct in (
            SignalChangeType.EVIDENCE_INVALIDATED,
            SignalChangeType.CONTROL_CHANGED,
            SignalChangeType.RUNTIME_RISK_ESCALATED,
        ):
            if tgt.target_type is SignalTargetType.ENVELOPE:
                return ReassessmentAction(
                    ReassessmentActionKind.REVOKE_ENVELOPE, tgt.target_id, reason
                )
            if tgt.target_type is SignalTargetType.SUBJECT:
                return ReassessmentAction(
                    ReassessmentActionKind.REVOKE_SUBJECT, tgt.target_id, reason
                )
            if tgt.target_type is SignalTargetType.MODEL:
                return ReassessmentAction(
                    ReassessmentActionKind.REVOKE_MODEL, tgt.target_id, reason
                )
            # Workflow/policy/tenant target with an evidence/control/runtime cause
            # ⇒ broad invalidation via epoch advance (RA-6 §9).
            return ReassessmentAction(ReassessmentActionKind.ADVANCE_EPOCH, "", reason)

        if ct is SignalChangeType.MODEL_INVALIDATED:
            target_id = tgt.target_id
            return ReassessmentAction(
                ReassessmentActionKind.REVOKE_MODEL, target_id, reason
            )

        if ct in (
            SignalChangeType.POLICY_SUPERSEDED,
            SignalChangeType.WORKFLOW_SUPERSEDED,
        ):
            # Supersession: broad invalidation (tenant epoch) unless a narrower
            # target is named, in which case revoke just that envelope (RA-6 §9).
            if tgt.target_type is SignalTargetType.ENVELOPE and tgt.target_id:
                return ReassessmentAction(
                    ReassessmentActionKind.REVOKE_ENVELOPE, tgt.target_id, reason
                )
            return ReassessmentAction(ReassessmentActionKind.ADVANCE_EPOCH, "", reason)

        # TENANT_EMERGENCY_STOP and anything else ⇒ no ordinary consequence here.
        return ReassessmentAction(ReassessmentActionKind.NONE, "", reason)


class AuthorityReassessor:
    """Durable-intake reassessment port (``AuthorityReassessmentSignalPort``)."""

    def __init__(
        self,
        writer: AuthorityLifecycleService,
        *,
        system_principal: WriterPrincipal,
        decider: Optional[ReassessmentDecider] = None,
    ) -> None:
        self._writer = writer
        self._system_principal = system_principal
        self._decider = decider or ReferenceReassessmentDecider()
        self._seen: Set[str] = set()
        self._lock = threading.Lock()

    def submit(self, signal: AuthorityReassessmentSignal) -> SignalAck:
        # 1. Validate provenance/context (malformed ⇒ never a state change).
        errors = signal.validation_errors()
        if errors:
            return SignalAck(
                disposition=SignalDisposition.IGNORED,
                reasons=("malformed signal",) + errors,
                correlation_id=signal.correlation_id,
            )

        # 2. Emergency stop is not an observer-intake capability (RA-6 §12).
        if signal.change_type is SignalChangeType.TENANT_EMERGENCY_STOP:
            return SignalAck(
                disposition=SignalDisposition.IGNORED,
                reasons=(
                    "TENANT_EMERGENCY_STOP requires the privileged administrative "
                    "emergency-stop path, not observer signal intake",
                ),
                correlation_id=signal.correlation_id,
            )

        # 3. Deduplicate by event_id (§14).
        with self._lock:
            if signal.event_id in self._seen:
                return SignalAck(
                    disposition=SignalDisposition.IGNORED,
                    reasons=(f"duplicate event_id {signal.event_id!r}",),
                    correlation_id=signal.correlation_id,
                )
            self._seen.add(signal.event_id)

        # 4. Reassess against current state → lifecycle consequence.
        action = self._decider.decide(signal)
        result = self._execute(signal, action)
        reasons = (f"action={action.kind.value}",) + result_reasons(result)
        return SignalAck(
            disposition=SignalDisposition.ACCEPTED_FOR_REASSESSMENT,
            reasons=reasons,
            correlation_id=signal.correlation_id,
        )

    def _execute(
        self, signal: AuthorityReassessmentSignal, action: ReassessmentAction
    ) -> Optional[LifecycleWriteResult]:
        p = self._system_principal
        t = signal.tenant_id
        cid = signal.correlation_id
        if action.kind is ReassessmentActionKind.NONE:
            return None
        if action.kind is ReassessmentActionKind.REVOKE_ENVELOPE:
            return self._writer.revoke_envelope(
                principal=p, tenant_id=t, envelope_id=action.target_id,
                reason=action.reason, correlation_id=cid,
            )
        if action.kind is ReassessmentActionKind.REVOKE_SUBJECT:
            return self._writer.revoke_subject(
                principal=p, tenant_id=t, subject_id=action.target_id,
                reason=action.reason, correlation_id=cid,
            )
        if action.kind is ReassessmentActionKind.REVOKE_MODEL:
            return self._writer.revoke_model(
                principal=p, tenant_id=t, model_id=action.target_id,
                reason=action.reason, correlation_id=cid,
            )
        if action.kind is ReassessmentActionKind.ADVANCE_EPOCH:
            # change_id derived from the signal event so a replayed signal is an
            # idempotent no-op at the writer (monotonic epoch; §14).
            return self._writer.advance_epoch(
                principal=p, tenant_id=t, change_id=f"signal:{signal.event_id}",
                reason=action.reason, correlation_id=cid,
            )
        return None


def result_reasons(result: Optional[LifecycleWriteResult]) -> tuple[str, ...]:
    if result is None:
        return ("no-op",)
    return (f"outcome={result.outcome.value}",) + tuple(result.reasons)
