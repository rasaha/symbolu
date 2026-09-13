"""The reference provider: deterministic, and unable to pass for production."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from _fixtures import CONTEXT, MODEL, NOW, VENDOR, binding, request as _make_request
from ugence_model_egress_unit import (
    REFERENCE_RESPONSE_MARKER,
    DeterministicFakeProvider,
    LiveEgressUnavailableProvider,
    MinimizedUnit,
    ProviderRefusedInProduction,
    RefusalReason,
    ResultOutcome,
)


def _request(**over):
    """A request for a fresh tenant, so each case is independent."""

    tenant = over.pop("tenant", None) or uuid.uuid4()
    return _make_request(tenant, **over)


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
        _request(context=(MinimizedUnit("unit-1", "something else", 3),)))


def test_the_answer_body_depends_on_no_clock():
    """The body is a pure function of the request; only the timestamp differs.

    Asserted on ``answer_for`` rather than through ``execute``, because ``execute``
    also enforces the request's own expiry — see the test below. Conflating the
    two would let a validity change silently pass as a determinism change.
    """

    provider = DeterministicFakeProvider()
    request = _request()
    assert provider.answer_for(request) == provider.answer_for(request)

    early = provider.execute(request, now=NOW)
    slightly_later = provider.execute(request, now=NOW + timedelta(minutes=1))
    assert early.payload == slightly_later.payload
    assert early.recorded_at != slightly_later.recorded_at


def test_a_request_past_its_own_expiry_is_refused():
    """§4.1: ``not_valid_after`` is the request's own expiry, independent of any
    lease. A request that outlived its authorization is not served late."""

    provider = DeterministicFakeProvider()
    request = _request()
    late = provider.execute(
        request, now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    assert late.refusal_reason is RefusalReason.REQUEST_NOT_VALID


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
    answer = provider.execute(_request(), now=NOW).payload
    assert answer.startswith(REFERENCE_RESPONSE_MARKER)
    assert "NOT A MODEL RESPONSE" in answer
    assert provider.adapter_id in answer


def test_the_marker_is_not_configurable():
    """A marker a deployment can switch off is a marker that will be off in the
    deployment that most needed it."""

    provider = DeterministicFakeProvider(adapter_id="renamed")
    assert provider.execute(_request(), now=NOW).payload.startswith(
        REFERENCE_RESPONSE_MARKER)


def test_both_shipped_providers_declare_the_repository_maturity_convention():
    for provider in (DeterministicFakeProvider(), LiveEgressUnavailableProvider()):
        assert provider.NON_PRODUCTION is True
        assert provider.maturity == "FIXTURE_ONLY"


# --- terminal refusals -------------------------------------------------------

def test_an_unavailable_model_is_refused_terminally():
    tenant = uuid.uuid4()
    provider = DeterministicFakeProvider(available_models=frozenset({MODEL}))
    result = provider.execute(
        _request(tenant=tenant, authorization=binding(tenant, model="another")),
        now=NOW)
    assert result.outcome is ResultOutcome.REFUSED
    assert result.refusal_reason is RefusalReason.MODEL_NOT_AVAILABLE
    assert result.payload is None


def test_an_unauthorized_vendor_is_refused_terminally():
    """Replaces the old ``purpose`` check. The ratified binding is what the unit
    verifies, and a vendor the clearance did not name is the sharpest case of a
    target the unit may not broaden to."""

    tenant = uuid.uuid4()
    provider = DeterministicFakeProvider(vendor=VENDOR)
    result = provider.execute(
        _request(tenant=tenant, authorization=binding(tenant, vendor="other-vendor")),
        now=NOW)
    assert result.refusal_reason is RefusalReason.TARGET_NOT_AUTHORIZED


def test_content_over_the_ceiling_is_refused_terminally():
    """Terminal because re-running the same content cannot help — the caller has
    to send different content, which is a different request."""

    provider = DeterministicFakeProvider(content_ceiling=10)
    result = provider.execute(
        _request(context=(MinimizedUnit("unit-1", "x" * 11, 1),)), now=NOW)
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
    assert result.refusal_reason is RefusalReason.CREDENTIAL_NOT_COMMISSIONED


def test_there_is_no_catch_all_refusal_reason():
    """An escape-hatch member would become the one everybody uses, and a refusal
    a caller cannot name is a refusal a caller cannot act on."""

    names = {r.name for r in RefusalReason}
    assert not (names & {"UNKNOWN", "OTHER", "UNSPECIFIED", "GENERIC"}), names
