"""ADR §0.5: the genuine-call gate is two predecessor gates, never MET."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

import ugence_model_egress_unit.version as version
from ugence_model_egress_unit import (
    GENUINE_CALL_ADMITTING_STATUSES,
    LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION,
    EgressResult,
    ProvenanceKind,
    ResultOutcome,
    genuine_call_admitted,
)

NOW = datetime(2026, 9, 12, tzinfo=timezone.utc)


def _genuine(**custody) -> EgressResult:
    return EgressResult(
        request_id=uuid.uuid4(), tenant_id=uuid.uuid4(), correlation_id=uuid.uuid4(), recorded_at=NOW,
        outcome=ResultOutcome.ANSWERED, adapter_id="a",
        provenance={"kind": ProvenanceKind.RESPONSE.value, "adapter_id": "a", "genuine_call": True,
                    "model_ref": "gpt-5.4-mini-2026-03-17", "observed_at": NOW.isoformat(), "token_count": 1},
        payload="x", content_digest=EgressResult.answered(
            request_id=uuid.uuid4(), tenant_id=uuid.uuid4(), correlation_id=uuid.uuid4(), recorded_at=NOW,
            adapter_id="a", payload="x", model_ref="m").content_digest,
        **custody)


def test_the_release_constants_hold_both_gates_shut_today():
    assert version.COMMISSIONING_STATUS == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"
    assert LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION == "NOT_GIVEN"
    assert GENUINE_CALL_ADMITTING_STATUSES == ("PENDING_VALIDATION", "MET")
    assert genuine_call_admitted() is False
    with pytest.raises(ValueError, match="while commissioning is BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS and the live synthetic validation authorization is NOT_GIVEN"):
        _genuine(custody_lease_id="lease", custody_authority_id="authority")


@pytest.mark.parametrize("status, authorization, admitted", [
    ("BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS", "NOT_GIVEN", False),
    ("BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS", "owner-authorization-2026-09-xx", False),
    ("PENDING_VALIDATION", "NOT_GIVEN", False),
    ("PENDING_VALIDATION", "owner-authorization-2026-09-xx", True),   # the validation call happens here
    ("NOT_MET", "owner-authorization-2026-09-xx", False),
    ("MET", "NOT_GIVEN", False),
    ("MET", "owner-authorization-2026-09-xx", True),
])
def test_each_gate_alone_is_insufficient_and_met_is_never_required(monkeypatch, status, authorization, admitted):
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", status)
    monkeypatch.setattr(version, "LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION", authorization)
    assert version.genuine_call_admitted() is admitted
    if admitted:
        result = _genuine(custody_lease_id="lease", custody_authority_id="authority")
        assert result.provenance["genuine_call"] is True and result.trust == "UNTRUSTED_EVIDENCE"
        with pytest.raises(ValueError, match="names the custody lease and authority"):
            _genuine()
    else:
        with pytest.raises(ValueError, match="no result may record a genuine call"):
            _genuine(custody_lease_id="lease", custody_authority_id="authority")


def test_row_12_can_be_satisfied_before_met(monkeypatch):
    """PENDING_VALIDATION plus the authorization admits the genuine result whose evidence
    later feeds the owner's MET decision; nothing here reads MET."""

    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "PENDING_VALIDATION")
    monkeypatch.setattr(version, "LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION", "owner-authorization-2026-09-xx")
    result = _genuine(custody_lease_id="lease", custody_authority_id="authority")
    assert result.outcome is ResultOutcome.ANSWERED and version.COMMISSIONING_STATUS != "MET"
