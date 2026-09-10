"""The reference provider: deterministic, and unable to pass for production."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from ugence_model_egress_unit import (
    REFERENCE_RESPONSE_MARKER,
    DeterministicFakeProvider,
    EgressRequest,
    LiveEgressUnavailableProvider,
    ProviderRefusedInProduction,
    RefusalReason,
    ResultOutcome,
)

NOW = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)


def _request(**over):
    kwargs = dict(request_id=uuid.uuid4(), tenant_id=uuid.uuid4(), submitted_at=NOW,
                  model_id="reference-model-a", purpose="reference-exchange",
                  content="ask something")
    kwargs.update(over)
    return EgressRequest.create(**kwargs)


# --- determinism -------------------------------------------------------------

def test_the_same_request_always_gets_the_same_answer():
    """What lets the exchange tests assert an exact response digest rather than
    merely that something came back."""

    provider = DeterministicFakeProvider()
    request = _request()
    assert provider.answer_for(request) == provider.answer_for(request)


def test_a_different_request_gets_a_different_answer():
    provider = DeterministicFakeProvider()
    assert provider.answer_for(_request()) != provider.answer_for(
        _request(content="ask something else"))


def test_the_answer_depends_on_no_clock():
    provider = DeterministicFakeProvider()
    request = _request()
    early = provider.execute(request, now=NOW)
    late = provider.execute(request, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert early.content == late.content
    assert early.recorded_at != late.recorded_at


# --- it cannot pass for production -------------------------------------------

def test_it_refuses_a_production_posture_outright():
    """The binding mechanism. The labels below describe the provider; this is
    what makes the description enforceable."""

    with pytest.raises(ProviderRefusedInProduction, match="reference fixture"):
        DeterministicFakeProvider().execute(_request(), now=NOW, production=True)


def test_every_answer_carries_the_marker_and_names_its_provider():
    """A response that reached a log, a screen or an audit record still says what
    produced it. There is no rendering of it that reads as a model's answer."""

    provider = DeterministicFakeProvider()
    answer = provider.execute(_request(), now=NOW).content
    assert answer.startswith(REFERENCE_RESPONSE_MARKER)
    assert "NOT A MODEL RESPONSE" in answer
    assert provider.provider_id in answer


def test_the_marker_is_not_configurable():
    """A marker a deployment can switch off is a marker that will be off in the
    deployment that most needed it."""

    provider = DeterministicFakeProvider(provider_id="renamed")
    assert provider.execute(_request(), now=NOW).content.startswith(
        REFERENCE_RESPONSE_MARKER)


def test_both_shipped_providers_declare_the_repository_maturity_convention():
    for provider in (DeterministicFakeProvider(), LiveEgressUnavailableProvider()):
        assert provider.NON_PRODUCTION is True
        assert provider.maturity == "FIXTURE_ONLY"


# --- terminal refusals -------------------------------------------------------

def test_an_unavailable_model_is_refused_terminally():
    provider = DeterministicFakeProvider(
        available_models=frozenset({"reference-model-a"}))
    result = provider.execute(_request(model_id="another"), now=NOW)
    assert result.outcome is ResultOutcome.REFUSED
    assert result.refusal_reason is RefusalReason.MODEL_NOT_AVAILABLE
    assert result.content is None


def test_an_impermissible_purpose_is_refused_terminally():
    provider = DeterministicFakeProvider(
        permitted_purposes=frozenset({"reference-exchange"}))
    result = provider.execute(_request(purpose="exfiltration"), now=NOW)
    assert result.refusal_reason is RefusalReason.PURPOSE_NOT_PERMITTED


def test_content_over_the_ceiling_is_refused_terminally():
    """Terminal because re-running the same content cannot help — the caller has
    to send different content, which is a different request."""

    provider = DeterministicFakeProvider(content_ceiling=10)
    result = provider.execute(_request(content="x" * 11), now=NOW)
    assert result.refusal_reason is RefusalReason.CONTENT_EXCEEDS_CEILING


def test_an_unconstrained_provider_answers():
    """The positive control: without it a provider that refused everything would
    satisfy all three refusal tests above."""

    result = DeterministicFakeProvider().execute(_request(), now=NOW)
    assert result.outcome is ResultOutcome.ANSWERED
    assert result.refusal_reason is None


def test_the_no_egress_provider_refuses_everything_by_name():
    result = LiveEgressUnavailableProvider().execute(_request(), now=NOW)
    assert result.outcome is ResultOutcome.REFUSED
    assert result.refusal_reason is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE


def test_there_is_no_catch_all_refusal_reason():
    """An escape-hatch member would become the one everybody uses, and a refusal
    a caller cannot name is a refusal a caller cannot act on."""

    names = {r.name for r in RefusalReason}
    assert not (names & {"UNKNOWN", "OTHER", "UNSPECIFIED", "GENERIC"}), names
