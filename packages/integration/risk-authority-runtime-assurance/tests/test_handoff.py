"""RA-6 signal handoff tests (spec §15, §18, §20; matrix 3–5, 24).

Material ESCALATED → AuthorityReassessmentSignal(RUNTIME_RISK_ESCALATED, ENVELOPE)
→ intake. Non-material → no signal. Sink fault → deferred, never widened. RA-7
holds only the neutral intake port — never the writer.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from risk_authority.domain.authority_signal import (
    SignalChangeType,
    SignalTargetType,
)
from risk_authority.integrations.authority_lifecycle import (
    AuthorityReassessmentSignalPort,
    SignalAck,
    SignalDisposition,
)

from ugence_risk_authority_runtime_assurance import (
    AssessmentOutcome,
    AuthorityReassessmentSignalEmitter,
    HandoffOutcome,
    ReasonCode,
    RuntimeRiskLevel,
    TrajectoryAssessment,
    assessment_to_signal,
)

NOW = datetime(2026, 8, 11, 12, 0, 0)


def _escalated(assessment_id="a1", envelope_id="env_abc", tenant_id="t1"):
    return TrajectoryAssessment(
        assessment_id=assessment_id,
        tenant_id=tenant_id,
        workflow_instance_id="w1",
        envelope_id=envelope_id,
        risk_level=RuntimeRiskLevel.ESCALATED,
        outcome=AssessmentOutcome.SIGNAL_REASSESS,
        produced_at=NOW,
        evaluator_identity="id",
        evaluator_version="0",
        reason_codes=(ReasonCode.CUMULATIVE_EXPOSURE,),
        reasons=("cumulative model_cost exposure 90000 exceeds ceiling 50000",),
        supporting_event_refs=("w1:1", "w1:2"),
    )


def _normal():
    return TrajectoryAssessment(
        assessment_id="a2",
        tenant_id="t1",
        workflow_instance_id="w1",
        envelope_id="env_abc",
        risk_level=RuntimeRiskLevel.NORMAL,
        outcome=AssessmentOutcome.NO_SIGNAL,
        produced_at=NOW,
        evaluator_identity="id",
        evaluator_version="0",
    )


class _RecordingIntake:
    def __init__(self, disposition=SignalDisposition.ACCEPTED_FOR_REASSESSMENT):
        self.received = []
        self._disposition = disposition

    def submit(self, signal) -> SignalAck:
        self.received.append(signal)
        return SignalAck(disposition=self._disposition, correlation_id=signal.correlation_id)


def test_material_assessment_maps_to_neutral_signal():
    sig = assessment_to_signal(_escalated(), correlation_id="corr-1")
    assert sig.change_type is SignalChangeType.RUNTIME_RISK_ESCALATED
    assert sig.target.target_type is SignalTargetType.ENVELOPE
    assert sig.target.target_id == "env_abc"
    assert sig.event_id == "a1"  # assessment_id ⇒ dedupe/idempotency
    assert sig.tenant_id == "t1"
    assert sig.evidence_refs == ("w1:1", "w1:2")
    assert sig.validation_errors() == ()  # a well-formed leaf signal


def test_signal_carries_no_authority_fields():
    sig = assessment_to_signal(_escalated(), correlation_id="c")
    # The leaf signal is structurally authority-free; assert no ALLOW/scope smuggled.
    for attr in ("allow", "scope", "grant", "token", "authorization"):
        assert not hasattr(sig, attr)


def test_emit_material_submits_to_intake():
    intake = _RecordingIntake()
    res = AuthorityReassessmentSignalEmitter(intake).emit(_escalated(), correlation_id="c")
    assert res.outcome is HandoffOutcome.SUBMITTED
    assert res.submitted
    assert len(intake.received) == 1


def test_emit_non_material_emits_no_signal():
    intake = _RecordingIntake()
    res = AuthorityReassessmentSignalEmitter(intake).emit(_normal())
    assert res.outcome is HandoffOutcome.NO_SIGNAL
    assert intake.received == []


def test_sink_unavailable_defers_without_widening():
    class Broken:
        def submit(self, signal):
            raise RuntimeError("sink down")

    res = AuthorityReassessmentSignalEmitter(Broken()).emit(_escalated())
    assert res.outcome is HandoffOutcome.SINK_UNAVAILABLE
    assert not res.submitted
    assert res.signal is not None  # retained for retry; assessment stands as evidence


def test_emitter_holds_only_intake_port_not_writer():
    intake = _RecordingIntake()
    emitter = AuthorityReassessmentSignalEmitter(intake)
    # There is no path from the emitter to any writer/revoke/epoch method.
    for attr in ("revoke_envelope", "revoke_subject", "revoke_model", "advance_epoch", "emergency_stop"):
        assert not hasattr(emitter, attr)


def test_emitter_requires_intake():
    with pytest.raises(ValueError):
        AuthorityReassessmentSignalEmitter(None)


def test_intake_port_protocol_satisfied_by_recording_intake():
    assert isinstance(_RecordingIntake(), AuthorityReassessmentSignalPort)
