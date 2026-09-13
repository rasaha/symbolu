"""D-4's ledger rule, enforced: the MEU's kinds refuse content-bearing keys."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from ugence_model_egress_unit import (
    CONTENT_BEARING_KEYS,
    MAX_LEDGER_STRING,
    MEU_LEDGER_KINDS,
    DeterministicFakeProvider,
    EgressRequest,
    LedgerKindViolation,
    MinimizedUnit,
    ledger_payload,
    reference_clearance,
    result_ledger_payload,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
TENANT = uuid.UUID("00000000-0000-4000-8000-000000000001")


def _request() -> EgressRequest:
    return EgressRequest.create(
        request_id=uuid.UUID("00000000-0000-4000-8000-000000000002"), tenant_id=TENANT,
        correlation_id=uuid.UUID("00000000-0000-4000-8000-000000000003"),
        submitted_at=NOW, not_valid_after=datetime(2026, 9, 11, 13, 0, tzinfo=timezone.utc),
        authorization=reference_clearance(tenant_id=TENANT, vendor="reference-vendor", model="reference-model"),
        minimized_context=(MinimizedUnit("unit-1", "the first admitted unit", 5),),
        parameters={"max_output_tokens": 64})


def test_every_kind_has_an_allowlist_free_of_content_keys():
    assert set(MEU_LEDGER_KINDS) == {"meu.request_submitted", "meu.result_recorded", "meu.content_purged",
                                     "meu.credential_leased", "meu.credential_refused"}
    for kind, allowed in MEU_LEDGER_KINDS.items():
        assert not ({k.lower() for k in allowed} & CONTENT_BEARING_KEYS), kind


def test_an_answered_result_reaches_the_ledger_without_its_payload():
    result = DeterministicFakeProvider().execute(_request(), now=NOW)
    assert result.payload and "[UGENCE-REFERENCE-FAKE" in result.payload
    payload = result_ledger_payload(result)
    assert "payload" not in payload and payload["content_digest"] == result.content_digest
    assert payload["result_digest"] == result.digest() and payload["outcome"] == "ANSWERED"
    assert result.payload not in str(payload)
    assert payload["provenance"]["genuine_call"] is False


@pytest.mark.parametrize("bad", [
    {"payload": "a prompt"}, {"Prompt": "x"}, {"provenance": {"response": "x"}},
    {"provenance": {"nested": [{"api_key": "sk"}]}}, {"provenance": {"TOKEN": "t"}},
])
def test_a_content_or_credential_key_is_refused_at_any_depth_in_any_case(bad):
    base = {"request_id": "r", "tenant_id": "t", "outcome": "ANSWERED"}
    with pytest.raises(LedgerKindViolation):
        ledger_payload("meu.result_recorded", {**base, **bad})


def test_unknown_kinds_unknown_keys_long_strings_and_odd_values_are_refused():
    with pytest.raises(LedgerKindViolation, match="not a Model Egress Unit ledger kind"):
        ledger_payload("meu.something_else", {})
    with pytest.raises(LedgerKindViolation, match="outside the kind's schema"):
        ledger_payload("meu.result_recorded", {"request_id": "r", "extra": 1})
    with pytest.raises(LedgerKindViolation, match="is content, not a reference"):
        ledger_payload("meu.result_recorded", {"adapter_id": "x" * (MAX_LEDGER_STRING + 1)})
    with pytest.raises(LedgerKindViolation, match="not a ledger value"):
        ledger_payload("meu.result_recorded", {"provenance": {"observed_at": NOW}})
    assert ledger_payload("meu.result_recorded", {"adapter_id": "x" * MAX_LEDGER_STRING})
