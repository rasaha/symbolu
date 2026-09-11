"""The seam: exact destination, exact shape, proof-gated outcomes, a fake that keeps nothing."""

from __future__ import annotations

import json
import pickle

import pytest

from ugence_model_egress_unit import DestinationRefused, OPENAI_RESPONSES
from ugence_model_egress_provider_openai import (
    DESIGNATED_MODEL,
    FAKE_RESPONSE_MARKER,
    REQUEST_BODY_KEYS,
    FakeTransport,
    OutcomeKind,
    PreparedRequest,
    TransportOutcome,
)
from conftest import NOW

GOOD_BODY = {"model": DESIGNATED_MODEL, "input": [{"role": "user", "content": "x"}],
             "max_output_tokens": 16, "store": False, "stream": False}


def test_the_designated_destination_is_the_only_url_a_prepared_request_accepts():
    assert PreparedRequest(url=OPENAI_RESPONSES.url, body=GOOD_BODY).url == "https://api.openai.com/v1/responses"
    for url in ["http://api.openai.com/v1/responses", "https://api.openai.com/v1/chat/completions",
                "https://api.openai.com:8443/v1/responses", "https://evil.example/v1/responses",
                "https://api.openai.com/v1/responses?x=1", "https://u@api.openai.com/v1/responses",
                "https://api.openai.com.evil.example/v1/responses", "https://api.openai.com/v1/responses/"]:
        with pytest.raises(DestinationRefused):
            PreparedRequest(url=url, body=GOOD_BODY)
    with pytest.raises(DestinationRefused):
        PreparedRequest(url=OPENAI_RESPONSES.url, body=GOOD_BODY, method="GET")


@pytest.mark.parametrize("mutation", [
    {"tools": []}, {"stream": True}, {"store": True}, {"background": True},
    {"previous_response_id": "resp_1"}, {"temperature": 0.2}, {"model": "gpt-5.4-mini"},
    {"max_output_tokens": 1025}, {"max_output_tokens": 0}, {"max_output_tokens": True},
    {"input": []},
], ids=lambda m: next(iter(m)))
def test_the_request_shape_is_closed_and_the_ceiling_is_not_the_adapters_to_raise(mutation):
    body = dict(GOOD_BODY, **mutation)
    with pytest.raises(ValueError):
        PreparedRequest(url=OPENAI_RESPONSES.url, body=body)
    missing = {k: v for k, v in GOOD_BODY.items() if k != "store"}
    with pytest.raises(ValueError):
        PreparedRequest(url=OPENAI_RESPONSES.url, body=missing)
    assert REQUEST_BODY_KEYS == {"model", "input", "max_output_tokens", "store", "stream"}


def test_a_prepared_request_is_canonical_and_its_record_carries_no_content():
    a = PreparedRequest(url=OPENAI_RESPONSES.url, body=GOOD_BODY)
    b = PreparedRequest(url=OPENAI_RESPONSES.url, body=dict(reversed(list(GOOD_BODY.items()))))
    assert a.encoded() == b.encoded() and a.body_digest == b.body_digest
    assert json.loads(a.encoded())["stream"] is False
    record = a.as_record()
    assert set(record) == {"url", "method", "body_digest", "model", "max_output_tokens", "input_units"}
    assert "x" not in json.dumps(record).replace('"max_output_tokens"', "")  # the content is not in it


def test_an_unproven_transient_failure_collapses_to_an_ambiguous_dispatch():
    proven = TransportOutcome.transient_before_dispatch("ECONNREFUSED", no_bytes_dispatched=True)
    assert proven.kind is OutcomeKind.TRANSIENT_BEFORE_DISPATCH and proven.retryable
    unproven = TransportOutcome.transient_before_dispatch("timeout", no_bytes_dispatched=False)
    assert unproven.kind is OutcomeKind.DISPATCHED_NO_RESPONSE and not unproven.retryable
    assert "reclassified" in unproven.detail
    assert not TransportOutcome.dispatched_no_response("cut").retryable
    with pytest.raises(ValueError):
        TransportOutcome(OutcomeKind.DISPATCHED_NO_RESPONSE, status=200, body={})
    with pytest.raises(ValueError):
        TransportOutcome(OutcomeKind.RESPONDED, status=None, body={})
    with pytest.raises(ValueError):
        TransportOutcome(OutcomeKind.TRANSIENT_BEFORE_DISPATCH, genuine=True, no_bytes_dispatched=True)


def test_the_fake_transport_refuses_to_be_scripted_with_a_genuine_response():
    with pytest.raises(ValueError, match="genuine"):
        FakeTransport([TransportOutcome.responded(200, {"output_text": "hi"}, genuine=True)])
    with pytest.raises(TypeError):
        FakeTransport(["not an outcome"])


def test_the_fake_transport_keeps_a_digest_and_a_boolean_and_never_the_bearer():
    fake = FakeTransport()
    prepared = PreparedRequest(url=OPENAI_RESPONSES.url, body=GOOD_BODY)
    secret = "MARKER-THIS-MUST-NOT-LEAK-0123456789"
    outcome = fake.send(prepared, bearer=secret, now=NOW)
    assert outcome.kind is OutcomeKind.RESPONDED and outcome.genuine is False
    assert outcome.body["output_text"].startswith(FAKE_RESPONSE_MARKER)
    assert fake.dispatches == [dict(prepared.as_record(), bearer_present=True, at=NOW.isoformat())]
    state = repr(fake) + json.dumps(fake.dispatches) + repr(vars(fake)) + repr(pickle.dumps(fake.dispatches))
    assert secret not in state and secret[-10:] not in state
    assert set(fake.dispatches[0]) == {"url", "method", "body_digest", "model", "max_output_tokens", "input_units", "bearer_present", "at"}
    assert fake.NON_PRODUCTION is True and fake.maturity == "FIXTURE_ONLY"
    with pytest.raises(TypeError):
        fake.send({"url": OPENAI_RESPONSES.url}, bearer=secret, now=NOW)


def test_the_fake_transport_plays_its_script_in_order_then_answers_with_the_marker():
    scripted = [TransportOutcome.dispatched_no_response("cut"),
                TransportOutcome.transient_before_dispatch("refused", no_bytes_dispatched=True)]
    fake = FakeTransport(scripted)
    prepared = PreparedRequest(url=OPENAI_RESPONSES.url, body=GOOD_BODY)
    kinds = [fake.send(prepared, bearer="b", now=NOW).kind for _ in range(3)]
    assert kinds == [OutcomeKind.DISPATCHED_NO_RESPONSE, OutcomeKind.TRANSIENT_BEFORE_DISPATCH, OutcomeKind.RESPONDED]
    assert len(fake.dispatches) == 3
