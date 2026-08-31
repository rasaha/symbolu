"""RA-6 signal handoff — EXECUTION_EFFECT_MISMATCH, material-only (spec §7, §22, §27)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from risk_authority.domain.authority_signal import SignalChangeType, SignalTargetType

from ugence_risk_authority_execution_assurance import (
    EffectAssuranceAssessment,
    EffectAssuranceSignalEmitter,
    EffectFinality,
    EffectReconciliationOutcome,
    HandoffOutcome,
    assessment_to_signal,
)

NOW = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)


def _assessment(outcome: EffectReconciliationOutcome) -> EffectAssuranceAssessment:
    return EffectAssuranceAssessment(
        assessment_id="a1", tenant_id="t1", workflow_instance_id="wf1", envelope_id="env_abc",
        authorized_action_digest="pf1", attempt_id="at1", outcome=outcome,
        finality=EffectFinality.FINAL, produced_at=NOW, reconciliation_id="rec1",
        execution_intent_id="exi1",
    )


class _Intake:
    def __init__(self):
        self.submitted = []

    def submit(self, signal):
        self.submitted.append(signal)
        from risk_authority.integrations.authority_lifecycle import SignalAck, SignalDisposition

        return SignalAck(disposition=SignalDisposition.ACCEPTED_FOR_REASSESSMENT)


def test_mismatch_maps_to_execution_effect_mismatch_envelope_signal():
    sig = assessment_to_signal(_assessment(EffectReconciliationOutcome.MISMATCH))
    assert sig.change_type is SignalChangeType.EXECUTION_EFFECT_MISMATCH
    assert sig.target.target_type is SignalTargetType.ENVELOPE
    assert sig.target.target_id == "env_abc"
    # evidence chain reconstructs reconciliation → intent → envelope (spec §26).
    assert "rec1" in sig.evidence_refs and "exi1" in sig.evidence_refs
    assert sig.validation_errors() == ()


@pytest.mark.parametrize(
    "outcome",
    [
        EffectReconciliationOutcome.MISMATCH,
        EffectReconciliationOutcome.CONFLICTED,
        EffectReconciliationOutcome.MANUAL_REVIEW,
    ],
)
def test_material_outcomes_submit(outcome):
    intake = _Intake()
    res = EffectAssuranceSignalEmitter(intake).emit(_assessment(outcome))
    assert res.outcome is HandoffOutcome.SUBMITTED
    assert len(intake.submitted) == 1


@pytest.mark.parametrize(
    "outcome",
    [
        EffectReconciliationOutcome.MATCHED,
        EffectReconciliationOutcome.PARTIAL,
        EffectReconciliationOutcome.UNKNOWN,
        EffectReconciliationOutcome.UNVERIFIABLE,
    ],
)
def test_non_material_outcomes_emit_no_signal(outcome):
    intake = _Intake()
    res = EffectAssuranceSignalEmitter(intake).emit(_assessment(outcome))
    assert res.outcome is HandoffOutcome.NO_SIGNAL
    assert intake.submitted == []


def test_sink_unavailable_defers_never_widens():
    class Broken:
        def submit(self, signal):
            raise RuntimeError("intake down")

    res = EffectAssuranceSignalEmitter(Broken()).emit(_assessment(EffectReconciliationOutcome.MISMATCH))
    assert res.outcome is HandoffOutcome.SINK_UNAVAILABLE
    assert not res.submitted
    assert res.signal is not None  # retained for re-submission


def test_emitter_requires_intake():
    with pytest.raises(ValueError):
        EffectAssuranceSignalEmitter(None)  # type: ignore[arg-type]
