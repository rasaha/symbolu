"""RA-6 signal handoff (spec §15, §18 — reuse the existing seam as-is).

A *material* (``ESCALATED``) :class:`~.contracts.TrajectoryAssessment` is mapped to
the leaf's neutral :class:`AuthorityReassessmentSignal` and submitted to the
existing RA-6 :class:`AuthorityReassessmentSignalPort`. RA-7 never calls
``revoke_envelope`` / ``revoke_subject`` / ``revoke_model`` / ``advance_epoch``
directly — **every** authority consequence routes through RA-6's reassessor and
sole authenticated writer (invariants I3/I4).

Ratified mapping (spec §18):

    change_type = RUNTIME_RISK_ESCALATED         (spec §9/D6)
    target_type = ENVELOPE  (default; SUBJECT/MODEL only on RA-6's own reassessment)
    reason      = structured reason codes + human summary
    event_id    = assessment_id                  (dedupe / idempotency at intake)

A non-material assessment (``NORMAL`` / ``UNKNOWN``) emits **no** signal. The
signal carries no ALLOW, no scope, no authority token — it can only *trigger*
reassessment; RA-6 decides and enacts the consequence (default: targeted envelope
revocation, spec §8).
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

from .contracts import TrajectoryAssessment

__all__ = [
    "HandoffOutcome",
    "HandoffResult",
    "SIGNAL_SOURCE",
    "AuthorityReassessmentSignalEmitter",
    "assessment_to_signal",
]

#: Producer identity stamped on emitted signals (spec §10 ``source``).
SIGNAL_SOURCE = "ra7-runtime-assurance"
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
    is deferred (spec §20: retry/queue; authority unchanged; never widened). The
    assessment is retained on the result so a caller can re-submit it later.
    """

    outcome: HandoffOutcome
    assessment: TrajectoryAssessment
    signal: Optional[AuthorityReassessmentSignal] = None
    ack: Optional[SignalAck] = None
    reasons: Tuple[str, ...] = ()

    @property
    def submitted(self) -> bool:
        return self.outcome is HandoffOutcome.SUBMITTED


def assessment_to_signal(
    assessment: TrajectoryAssessment,
    *,
    correlation_id: str,
    observed_at: Optional[datetime] = None,
) -> AuthorityReassessmentSignal:
    """Map a material assessment to a neutral RA-6 signal (spec §18).

    Uses ``target_type = ENVELOPE`` (the default targeted consequence, spec §8/D5)
    and ``change_type = RUNTIME_RISK_ESCALATED`` (the single reused category, spec
    §9/D6). The structured reason codes ride in ``reason`` for audit; RA-6 decides
    breadth.
    """

    codes = ",".join(rc.value for rc in assessment.reason_codes)
    summary = "; ".join(assessment.reasons) if assessment.reasons else ""
    reason = f"[{codes}] {summary}".strip() if codes else (summary or "runtime risk escalated")
    return AuthorityReassessmentSignal(
        schema_version=AUTHORITY_SIGNAL_SCHEMA_VERSION,
        event_id=assessment.assessment_id,
        tenant_id=assessment.tenant_id,
        target=SignalTarget(SignalTargetType.ENVELOPE, assessment.envelope_id),
        change_type=SignalChangeType.RUNTIME_RISK_ESCALATED,
        source=SIGNAL_SOURCE,
        source_version=SIGNAL_SOURCE_VERSION,
        observed_at=observed_at if isinstance(observed_at, datetime) else assessment.produced_at,
        reason=reason,
        correlation_id=correlation_id or assessment.assessment_id,
        evidence_refs=tuple(assessment.supporting_event_refs),
    )


class AuthorityReassessmentSignalEmitter:
    """Emit material assessments into the RA-6 intake port (spec §15/§18).

    Holds only the neutral intake ``Protocol`` — never the writer, never emergency
    stop. A sink fault is caught and reported as ``SINK_UNAVAILABLE`` so a transport
    failure never widens authority (spec §20).
    """

    def __init__(self, intake: AuthorityReassessmentSignalPort) -> None:
        if intake is None:
            raise ValueError("AuthorityReassessmentSignalEmitter requires an intake port")
        self._intake = intake

    def emit(
        self,
        assessment: TrajectoryAssessment,
        *,
        correlation_id: str = "",
        observed_at: Optional[datetime] = None,
    ) -> HandoffResult:
        if not assessment.is_material:
            return HandoffResult(
                outcome=HandoffOutcome.NO_SIGNAL,
                assessment=assessment,
                reasons=(f"non-material assessment ({assessment.risk_level.value})",),
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
