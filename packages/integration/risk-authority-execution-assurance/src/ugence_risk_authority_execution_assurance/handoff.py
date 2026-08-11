"""RA-6 signal handoff (spec §7/D-D, §22 — reuse the existing seam as-is).

A *material* :class:`~.contracts.EffectAssuranceAssessment` is mapped to the leaf's
neutral :class:`AuthorityReassessmentSignal` (``change_type =
EXECUTION_EFFECT_MISMATCH``) and submitted to the existing RA-6
:class:`AuthorityReassessmentSignalPort`. RA-8 never calls ``revoke_envelope`` /
``revoke_subject`` / ``revoke_model`` / ``advance_epoch`` / ``emergency_stop``
directly — **every** authority consequence routes through RA-6's reassessor and
sole authenticated writer (spec §22, §28 I3/I4).

Ratified mapping (spec §7):

    MATCHED                         → no signal
    PARTIAL (within policy)         → no signal yet
    UNKNOWN / UNVERIFIABLE          → no signal (policy-dependent; default no change)
    MISMATCH                        → EXECUTION_EFFECT_MISMATCH (material)
    CONFLICTED                      → EXECUTION_EFFECT_MISMATCH (material)
    MANUAL_REVIEW (duplicate real effect) → EXECUTION_EFFECT_MISMATCH (material)

Only a *material* assessment emits (spec §7 "only material mismatch emits"). The
signal carries no ALLOW, no scope, no authority token — it can only *trigger*
reassessment; RA-6 decides and enacts the consequence (default: targeted envelope
revocation). A false RA-8 mismatch can therefore cost availability but can never
widen authority (spec §18).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from risk_authority.domain.authority_signal import (
    AUTHORITY_SIGNAL_SCHEMA_VERSION,
    AuthorityReassessmentSignal,
    SignalChangeType,
    SignalTarget,
    SignalTargetType,
)
from risk_authority.integrations.authority_lifecycle import (
    AuthorityReassessmentSignalPort,
    SignalAck,
    SignalDisposition,
)

from .contracts import EffectAssuranceAssessment

__all__ = [
    "HandoffOutcome",
    "HandoffResult",
    "SIGNAL_SOURCE",
    "EffectAssuranceSignalEmitter",
    "assessment_to_signal",
]

#: Producer identity stamped on emitted signals (spec §12 ``source``).
SIGNAL_SOURCE = "ra8-execution-assurance"
SIGNAL_SOURCE_VERSION = "0.1.0"


class HandoffOutcome(str, Enum):
    """Outcome of a handoff attempt (never carries authority)."""

    NO_SIGNAL = "NO_SIGNAL"
    SUBMITTED = "SUBMITTED"
    SINK_UNAVAILABLE = "SINK_UNAVAILABLE"


@dataclass(frozen=True)
class HandoffResult:
    """The audited result of a handoff — evidence only, no authority.

    ``SINK_UNAVAILABLE`` means the assessment stands as evidence but the consequence
    is deferred (spec §27: retry/queue; authority unchanged; never widened). The
    assessment is retained so a caller can re-submit it later.
    """

    outcome: HandoffOutcome
    assessment: EffectAssuranceAssessment
    signal: Optional[AuthorityReassessmentSignal] = None
    ack: Optional[SignalAck] = None
    reasons: Tuple[str, ...] = ()

    @property
    def submitted(self) -> bool:
        return self.outcome is HandoffOutcome.SUBMITTED


def assessment_to_signal(
    assessment: EffectAssuranceAssessment,
    *,
    correlation_id: str = "",
    observed_at: Optional[datetime] = None,
) -> AuthorityReassessmentSignal:
    """Map a material assessment to a neutral RA-6 signal (spec §7/§22).

    Uses ``target_type = ENVELOPE`` (the default targeted consequence) and
    ``change_type = EXECUTION_EFFECT_MISMATCH`` (the additive RA-8 category). The
    structured reason codes ride in ``reason`` for audit; RA-6 decides breadth.
    Evidence refs reconstruct the audit chain (spec §26): reconciliation → intent →
    envelope.
    """

    codes = ",".join(rc.value for rc in assessment.reason_codes)
    summary = "; ".join(assessment.reasons) if assessment.reasons else ""
    reason = (
        f"[{assessment.outcome.value}][{codes}] {summary}".strip()
        if codes
        else f"[{assessment.outcome.value}] {summary}".strip()
    )
    evidence_refs = tuple(
        r
        for r in (
            assessment.reconciliation_id,
            assessment.execution_intent_id,
            assessment.envelope_id,
            assessment.authorized_action_digest,
            *assessment.evidence_refs,
        )
        if r
    )
    return AuthorityReassessmentSignal(
        schema_version=AUTHORITY_SIGNAL_SCHEMA_VERSION,
        event_id=assessment.assessment_id,
        tenant_id=assessment.tenant_id,
        target=SignalTarget(SignalTargetType.ENVELOPE, assessment.envelope_id),
        change_type=SignalChangeType.EXECUTION_EFFECT_MISMATCH,
        source=SIGNAL_SOURCE,
        source_version=SIGNAL_SOURCE_VERSION,
        observed_at=observed_at if isinstance(observed_at, datetime) else assessment.produced_at,
        reason=reason or "execution effect mismatch",
        correlation_id=correlation_id or assessment.correlation_digest or assessment.assessment_id,
        evidence_refs=evidence_refs,
    )


class EffectAssuranceSignalEmitter:
    """Emit material assessments into the RA-6 intake port (spec §22).

    Holds only the neutral intake ``Protocol`` — never the writer, never emergency
    stop. A sink fault is caught and reported as ``SINK_UNAVAILABLE`` so a transport
    failure never widens authority (spec §27).
    """

    def __init__(self, intake: AuthorityReassessmentSignalPort) -> None:
        if intake is None:
            raise ValueError("EffectAssuranceSignalEmitter requires an intake port")
        self._intake = intake

    def emit(
        self,
        assessment: EffectAssuranceAssessment,
        *,
        correlation_id: str = "",
        observed_at: Optional[datetime] = None,
    ) -> HandoffResult:
        if not assessment.is_material:
            return HandoffResult(
                outcome=HandoffOutcome.NO_SIGNAL,
                assessment=assessment,
                reasons=(f"non-material assessment ({assessment.outcome.value})",),
            )
        signal = assessment_to_signal(
            assessment, correlation_id=correlation_id, observed_at=observed_at
        )
        try:
            ack = self._intake.submit(signal)
        except Exception as exc:  # noqa: BLE001 - sink fault ⇒ defer, never widen
            return HandoffResult(
                outcome=HandoffOutcome.SINK_UNAVAILABLE,
                assessment=assessment,
                signal=signal,
                reasons=("RA-6 signal sink unavailable", repr(exc)),
            )
        return HandoffResult(
            outcome=HandoffOutcome.SUBMITTED,
            assessment=assessment,
            signal=signal,
            ack=ack,
            reasons=(f"disposition={_disposition_value(ack)}",),
        )


def _disposition_value(ack: Optional[SignalAck]) -> str:
    if ack is None or not isinstance(ack.disposition, SignalDisposition):
        return "UNKNOWN"
    return ack.disposition.value
