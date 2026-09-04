"""The strict codec: every stored record round-trips, and nothing is guessed."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from risk_authority.crypto.canonical import to_canonical_obj
from risk_authority.domain import (
    AuthorityGrant,
    ControlEvidenceRecord,
    ControlResult,
    GovernanceEvent,
    RiskCaseSnapshot,
    RiskDecision,
    RiskDecisionCase,
    SnapshotIntegrityError,
)
from risk_authority.domain.enums import ControlStatus, EvidenceState, GovernanceEventType, RiskCaseState
from risk_authority.domain.events import make_event
from risk_authority.domain.evidence import EvidenceAdmission
from risk_authority.persistence import PersistenceStorageError, decode_dataclass, decode_envelope, encode_envelope
from risk_authority.persistence.codec import decode_case, decode_record, encode_case, encode_record

from tests import scenario as S

NOW = S.FIXED_NOW


def _world():
    app = S.build_application()
    evaluation, decision, envelope = S.approved_envelope(app)
    case = app.cases.get(S.TENANT, "rdc_1")
    return app, case, decision, envelope


def test_decision_round_trips_and_keeps_its_digest():
    _, _, decision, _ = _world()
    back = decode_record(RiskDecision, encode_record(decision))
    assert back == decision
    assert to_canonical_obj(back) == to_canonical_obj(decision)


def test_envelope_round_trips_with_its_signature_stored_beside_the_body():
    _, _, _, envelope = _world()
    stored = encode_envelope(envelope)
    assert set(stored) == {"envelope", "signature"} and "signature" not in stored["envelope"]
    back = decode_envelope(stored)
    assert back == envelope and back.signature == envelope.signature
    assert back.signing_payload() == envelope.signing_payload()


def test_case_round_trips_through_its_snapshot_with_events_and_state():
    _, case, _, _ = _world()
    back = decode_case(encode_case(case))
    assert back.state is case.state and back.events == case.events
    assert back.required_controls == case.required_controls
    assert back.snapshot() == case.snapshot()
    # The rebuilt aggregate keeps transitioning with an unbroken chain.
    back.transition(target=RiskCaseState.REVOKED, actor="t", reason="r", now=NOW)
    assert back.events[-1].prev_digest == case.events[-1].payload_digest


@pytest.mark.parametrize("break_it", [
    lambda ev: replace(ev[1], prev_digest="sha256:" + "f" * 64),
    lambda ev: replace(ev[1], event_id="evt_rdc_1_0009"),
    lambda ev: replace(ev[1], aggregate_id="other"),
])
def test_a_broken_event_chain_refuses_the_snapshot(break_it):
    _, case, _, _ = _world()
    snap = case.snapshot()
    events = list(snap.events)
    events[1] = break_it(events)
    with pytest.raises(SnapshotIntegrityError):
        RiskDecisionCase.from_snapshot(replace(snap, events=tuple(events)))
    with pytest.raises(SnapshotIntegrityError):
        RiskDecisionCase.from_snapshot(replace(snap, seq=snap.seq + 1))
    with pytest.raises(PersistenceStorageError):
        decode_case(to_canonical_obj(replace(snap, events=tuple(events))))


def test_grant_control_results_evidence_and_events_round_trip():
    grant = S.build_grant()
    assert decode_record(AuthorityGrant, encode_record(grant)) == grant
    result = ControlResult(control_id="C1", status=ControlStatus.PASS, evidence_ids=("e1",),
                           evaluated_at=NOW, valid_until=None, reason="ok", tenant_id=S.TENANT)
    assert decode_record(ControlResult, encode_record(result)) == result
    evidence = ControlEvidenceRecord(
        evidence_id="e1", tenant_id=S.TENANT, type="attestation", subject_id=S.ACTOR, issuer="iss",
        created_at=NOW, valid_until=None, digest="sha256:" + "a" * 64,
        admission=EvidenceAdmission(status=EvidenceState.ADMITTED), provenance={"k": "v"})
    assert decode_record(ControlEvidenceRecord, encode_record(evidence)) == evidence
    event = make_event(event_id="evt_x_0001", tenant_id=S.TENANT, event_type=GovernanceEventType.CASE_STATE_CHANGED,
                       aggregate_id="x", actor="a", timestamp=NOW, payload={"p": 1}, attributes={"a": "b"})
    back = decode_record(GovernanceEvent, encode_record(event))
    assert back == event and back.attributes == {"a": "b"}


@pytest.mark.parametrize("mutate", [
    lambda d: {**d, "extra": 1},
    lambda d: {k: v for k, v in d.items() if k != "decision_id"},
    lambda d: {**d, "outcome": "NOT_AN_OUTCOME"},
    lambda d: {**d, "issued_at": "2026-08-10T12:00:00Z"},
    lambda d: {**d, "conditions": "not-a-list"},
    lambda d: {**d, "scope": {**d["scope"], "max_autonomy_level": True}},
])
def test_malformed_stored_values_are_refused_not_guessed(mutate):
    _, _, decision, _ = _world()
    with pytest.raises(PersistenceStorageError):
        decode_record(RiskDecision, mutate(encode_record(decision)))


def test_decode_dataclass_rejects_non_dataclasses_and_non_objects():
    with pytest.raises(PersistenceStorageError):
        decode_dataclass(int, {})
    with pytest.raises(PersistenceStorageError):
        decode_dataclass(RiskCaseSnapshot, [])


def test_naive_datetimes_never_come_back():
    _, _, decision, _ = _world()
    back = decode_record(RiskDecision, encode_record(decision))
    assert back.issued_at.tzinfo is timezone.utc and isinstance(back.issued_at, datetime)
