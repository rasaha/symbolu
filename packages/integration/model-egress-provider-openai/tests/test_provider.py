"""The adapter: pre-flight refusals, reserve-before-dispatch, proof-gated retry,
ambiguous dispatch to OUTCOME_UNKNOWN, and never a genuine record."""

from __future__ import annotations

import dataclasses
import json
import uuid
from datetime import timedelta

import pytest

from ugence_model_egress_unit import (
    COMMISSIONING_LIMITS,
    COMMISSIONING_STATUS,
    CallBudget,
    CommissioningLimits,
    DispatchAttempt,
    EgressUnit,
    MinimizedUnit,
    ProvenanceKind,
    ProviderRefusedInProduction,
    RefusalReason,
    ResultOutcome,
    OPENAI_RESPONSES,
)
from ugence_model_egress_provider_openai import (
    ADAPTER_ID,
    DESIGNATED_MODEL,
    ESTIMATED_CENTS_PER_CALL,
    FAKE_RESPONSE_MARKER,
    FakeTransport,
    GenuineResponseNotRecordable,
    OpenAIResponsesProvider,
    OutcomeKind,
    PreparedRequest,
    TransportOutcome,
    prepare,
)
from conftest import NOW, PROFILE, SECRET, MarkerCustody, make_request


def _dump(result) -> str:
    return json.dumps(dataclasses.asdict(result), default=str)


# --- posture ---------------------------------------------------------------------

def test_this_release_refuses_a_production_posture_outright(provider):
    from ugence_model_egress_unit import status_admits_genuine_call
    assert COMMISSIONING_STATUS == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS" and status_admits_genuine_call() is False
    with pytest.raises(ProviderRefusedInProduction, match="no live transport"):
        provider.execute(make_request(), now=NOW, production=True)


def test_the_adapter_has_no_default_transport_and_no_way_to_change_the_limits(custody, budget):
    with pytest.raises(TypeError):
        OpenAIResponsesProvider(transport=None, custody=custody, budget=budget, credential_profile=PROFILE)
    with pytest.raises(TypeError):
        OpenAIResponsesProvider(transport=object(), custody=custody, budget=budget, credential_profile=PROFILE)
    with pytest.raises(ValueError, match="COMMISSIONING_LIMITS"):
        OpenAIResponsesProvider(transport=FakeTransport(), custody=custody, credential_profile=PROFILE,
                                budget=CallBudget(limits=CommissioningLimits(max_genuine_calls=1000)))
    p = OpenAIResponsesProvider(transport=FakeTransport(), custody=custody, budget=budget, credential_profile=PROFILE)
    assert p.limits is COMMISSIONING_LIMITS
    with pytest.raises(AttributeError):
        p.limits = CommissioningLimits(max_genuine_calls=1000)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.limits.max_genuine_calls = 1000
    assert ESTIMATED_CENTS_PER_CALL * COMMISSIONING_LIMITS.max_genuine_calls == COMMISSIONING_LIMITS.budget_usd_cents


# --- pre-flight ------------------------------------------------------------------

@pytest.mark.parametrize("kwargs, reason", [
    (dict(vendor="anthropic"), RefusalReason.TARGET_NOT_AUTHORIZED),
    (dict(model="gpt-5.4-mini"), RefusalReason.MODEL_NOT_PINNED),
    (dict(model="gpt-5.4-2026-03-17"), RefusalReason.MODEL_NOT_AVAILABLE),
    (dict(parameters={"max_output_tokens": 2048}), RefusalReason.REQUEST_LIMIT_EXCEEDED),
    (dict(parameters={"max_output_tokens": 8, "stream": True}), RefusalReason.REQUEST_LIMIT_EXCEEDED),
    (dict(parameters={"max_output_tokens": 8, "tools": [{"type": "web_search"}]}), RefusalReason.REQUEST_LIMIT_EXCEEDED),
    (dict(parameters={"max_output_tokens": 8, "store": True}), RefusalReason.REQUEST_LIMIT_EXCEEDED),
    (dict(tokens=8_193), RefusalReason.REQUEST_LIMIT_EXCEEDED),
    (dict(not_valid_after=NOW), RefusalReason.REQUEST_NOT_VALID),
], ids=lambda v: v.value if isinstance(v, RefusalReason) else "")
def test_a_request_outside_the_rulings_is_refused_before_anything_is_dispatched(
        provider, transport, custody, budget, kwargs, reason):
    request = make_request(**kwargs)
    assert provider._refusal(request, NOW) is reason
    result = provider.execute(request, now=NOW)
    assert result.outcome is ResultOutcome.REFUSED and result.refusal_reason is reason
    assert result.provenance["genuine_call"] is False
    assert transport.dispatches == [] and custody.requests == []
    assert budget.calls_reserved == 0 and budget.cents_reserved == 0


def test_a_tampered_or_purged_request_is_refused_before_dispatch(provider, transport):
    request = make_request()
    tampered = dataclasses.replace(request, minimized_context=(MinimizedUnit("u-1", "other", 4),))
    assert provider._refusal(tampered, NOW) is RefusalReason.CONTENT_DIGEST_MISMATCH
    purged = dataclasses.replace(request, minimized_context=None)
    assert provider._refusal(purged, NOW) is RefusalReason.CONTENT_DIGEST_MISMATCH
    assert transport.dispatches == []


def test_the_unit_asks_the_adapters_pre_flight_so_a_refusable_request_is_never_marked_dispatched(provider):
    unit = EgressUnit(exchange=None, provider=provider, holder="unit-test")
    assert unit._provider_will_dispatch(make_request(vendor="anthropic"), NOW) is False
    assert unit._provider_will_dispatch(make_request(), NOW) is True


def test_a_transport_that_does_not_declare_itself_non_production_is_refused_pre_flight(custody, budget):
    class UndeclaredTransport:
        def send(self, prepared, *, bearer, now):
            raise AssertionError("must never be reached")
    p = OpenAIResponsesProvider(transport=UndeclaredTransport(), custody=custody, budget=budget,
                                credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.refusal_reason is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE
    assert custody.requests == [] and budget.calls_reserved == 0


# --- the happy path, through the fake --------------------------------------------

def test_prepare_produces_exactly_the_designated_request(provider):
    request = make_request(units=[MinimizedUnit("u-1", "first", 1), MinimizedUnit("u-2", "second", 1)])
    prepared = prepare(request)
    assert isinstance(prepared, PreparedRequest)
    assert prepared.url == OPENAI_RESPONSES.url == "https://api.openai.com/v1/responses"
    assert prepared.body == {
        "model": DESIGNATED_MODEL,
        "input": [{"role": "user", "content": "first"}, {"role": "user", "content": "second"}],
        "max_output_tokens": 256, "store": False, "stream": False}
    with pytest.raises(ValueError):
        prepare(make_request(model="gpt-5.4-mini"))


def test_a_fake_dispatch_answers_with_the_marker_and_never_a_genuine_call(provider, transport, custody, budget):
    request = make_request()
    result = provider.execute(request, now=NOW)
    assert result.outcome is ResultOutcome.ANSWERED
    assert result.adapter_id == ADAPTER_ID
    assert result.provenance == {"kind": ProvenanceKind.RESPONSE.value, "adapter_id": ADAPTER_ID,
                                 "genuine_call": False, "model_ref": DESIGNATED_MODEL,
                                 "observed_at": NOW.isoformat(), "token_count": 0}
    assert result.payload.startswith(FAKE_RESPONSE_MARKER)
    assert result.custody_lease_id is None and result.custody_authority_id is None
    assert len(transport.dispatches) == 1
    dispatch = transport.dispatches[0]
    assert dispatch["url"] == OPENAI_RESPONSES.url and dispatch["bearer_present"] is True
    assert dispatch["body_digest"] == prepare(request).body_digest
    assert [r.vendor for r in custody.requests] == ["openai"]
    assert budget.as_record() == {"calls_reserved": 1, "cents_reserved": ESTIMATED_CENTS_PER_CALL,
                                  "in_flight": 0, "max_genuine_calls": 10, "budget_usd_cents": 2500}


def test_the_secret_appears_in_no_record_no_transport_state_and_no_repr(provider, transport):
    result = provider.execute(make_request(), now=NOW)
    everywhere = _dump(result) + repr(transport) + json.dumps(transport.dispatches) + repr(vars(provider))
    assert SECRET not in everywhere and SECRET[:16] not in everywhere


def test_a_custody_refusal_is_terminal_dispatches_nothing_and_consumes_no_budget(transport, budget):
    custody = MarkerCustody(refuse=True)
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.refusal_reason is RefusalReason.CREDENTIAL_NOT_COMMISSIONED
    assert transport.dispatches == [] and budget.calls_reserved == 0


def _admission_for(request, *, now=NOW):
    """A verified admission through the real gate, against the fixture ledger: the
    typed authorization pins this request, and a fixture commissioning record pins the
    authorization. Nothing canonical is touched."""

    from ugence_model_egress_unit import (
        CommissioningRecordView, InMemoryAuthorizationLedger, LiveSyntheticValidationAuthorization,
        ScopeExpectation, admit_genuine_call, designation_record_digest)
    designation = {"schema": "model-egress-unit.live-provider-designation.v1", "fixture": "adapter-test"}
    scope = ScopeExpectation(openai_organization_id="org-a1b2c3d4e5", openai_project_id="proj_f6g7h8i9j0",
                             openai_service_account_id="svc-acct-meu-validation-01", model=DESIGNATED_MODEL)
    auth = LiveSyntheticValidationAuthorization(
        authorization_id="lsva-adapter-test", nonce="nonce-" + uuid.uuid4().hex, authorizing_owner="Owner",
        authority_reference="acceptance://fixture", issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(hours=1),
        environment="NON_PRODUCTION", openai_organization_id=scope.openai_organization_id,
        openai_project_id=scope.openai_project_id, openai_service_account_id=scope.openai_service_account_id,
        provider="openai", model=DESIGNATED_MODEL, endpoint=OPENAI_RESPONSES.url,
        designation_record_digest=designation_record_digest(designation), validation_plan_digest="a" * 64,
        authorized_request_digests=(request.digest(),), synthetic_non_sensitive_only=True, max_calls=1,
        max_input_tokens=8_192, max_output_tokens=1_024, budget_usd_cents=2_500, concurrency=1, max_retries=1)
    record = CommissioningRecordView(status="PENDING_VALIDATION", authorization_digest=auth.digest(), revoked_digests=(),
                                     authorizing_owner="Owner", designation_digest=designation_record_digest(designation))
    return admit_genuine_call(auth, record=record, request=request, expected=scope, plan_digest="a" * 64, now=now,
                              ledger=InMemoryAuthorizationLedger(), estimated_cents=250)


def test_a_production_authoritative_lease_is_refused_without_a_verified_admission_for_this_request(transport, budget, monkeypatch):
    custody = MarkerCustody(production_authoritative=True)
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    request = make_request()
    result = p.execute(request, now=NOW)
    assert result.refusal_reason is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE
    assert transport.dispatches == [] and budget.calls_reserved == 0
    # a string, a flag, an owner's name, an admission for another request: all refused
    for bad in ("yes", True, "Owner", _admission_for(make_request())):
        assert p.execute(request, now=NOW, admission=bad).refusal_reason is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE
    assert transport.dispatches == []
    # a verified admission for this request, but the status mirror is still BLOCKED: refused (fails closed on drift)
    admission = _admission_for(request)
    assert p.execute(request, now=NOW, admission=admission).refusal_reason is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE
    # with G1's mirror admitting, the same lease is usable: that is the non-production validation call;
    # "production-authoritative" is the lease's custody authority, not a production deployment
    import ugence_model_egress_unit.version as version
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "PENDING_VALIDATION")
    result = p.execute(request, now=NOW, admission=admission)
    assert result.outcome is ResultOutcome.ANSWERED and result.provenance["genuine_call"] is False  # fake transport: never genuine
    assert len(transport.dispatches) == 1
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "MET")
    assert p.execute(make_request(), now=NOW).refusal_reason is RefusalReason.LIVE_EGRESS_NOT_AVAILABLE  # MET without an admission admits nothing


def test_a_genuine_transport_response_is_recorded_only_under_an_admission_and_a_production_authoritative_lease(budget, monkeypatch):
    class GenuineOnceTransport(FakeTransport):
        def send(self, prepared, *, bearer, now):
            super().send(prepared, bearer=bearer, now=now)
            return TransportOutcome.responded(200, {"output_text": "vendor text", "usage": {"total_tokens": 3}}, genuine=True)
    request = make_request()
    admission = _admission_for(request)
    import ugence_model_egress_unit.version as version
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "PENDING_VALIDATION")
    # admission but a non-authoritative (fixture) lease: the response cannot be recorded
    p = OpenAIResponsesProvider(transport=GenuineOnceTransport(), custody=MarkerCustody(), budget=budget, credential_profile=PROFILE)
    with pytest.raises(GenuineResponseNotRecordable):
        p.execute(request, now=NOW, admission=admission)
    # admission and a production-authoritative lease: a genuine result carrying both
    p = OpenAIResponsesProvider(transport=GenuineOnceTransport(), custody=MarkerCustody(production_authoritative=True),
                                budget=CallBudget(), credential_profile=PROFILE)
    result = p.execute(request, now=NOW, admission=admission)
    assert result.provenance["genuine_call"] is True and result.admission is admission
    assert result.custody_lease_id and result.custody_authority_id == "test-marker-custody"
    assert result.trust == "UNTRUSTED_EVIDENCE" and result.payload == "vendor text"


# --- retry, ambiguity, failure ---------------------------------------------------

def test_one_retry_and_only_with_proof_that_no_bytes_were_dispatched(custody, budget):
    proven = TransportOutcome.transient_before_dispatch("ECONNREFUSED", no_bytes_dispatched=True)
    transport = FakeTransport([proven])
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    assert p.execute(make_request(), now=NOW).outcome is ResultOutcome.ANSWERED
    assert len(transport.dispatches) == 2
    assert budget.calls_reserved == 1  # a retry is the same reserved call

    transport = FakeTransport([proven, proven, proven])
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=CallBudget(), credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.outcome is ResultOutcome.FAILED and result.provenance["genuine_call"] is False
    assert len(transport.dispatches) == 2  # never a third attempt


def test_an_unproven_transient_failure_gets_no_retry_and_records_outcome_unknown(custody, budget):
    unproven = TransportOutcome.transient_before_dispatch("timeout", no_bytes_dispatched=False)
    transport = FakeTransport([unproven])
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.outcome is ResultOutcome.OUTCOME_UNKNOWN
    assert len(transport.dispatches) == 1
    assert result.provenance["kind"] == ProvenanceKind.DISPATCH_ATTEMPT.value
    assert result.provenance["genuine_call"] is False
    for key in ("model_ref", "token_count", "cost"):
        if key in result.provenance:
            assert result.provenance[key] == DispatchAttempt.UNKNOWN


def test_an_ambiguous_dispatch_or_a_raising_transport_is_outcome_unknown_and_keeps_the_reservation(custody):
    budget = CallBudget()
    transport = FakeTransport([TransportOutcome.dispatched_no_response("connection reset mid-body")])
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.outcome is ResultOutcome.OUTCOME_UNKNOWN and "reset" in result.provenance["reason"]
    assert budget.calls_reserved == 1 and budget.cents_reserved == ESTIMATED_CENTS_PER_CALL and budget.in_flight == 0

    class RaisingTransport(FakeTransport):
        def send(self, prepared, *, bearer, now):
            super().send(prepared, bearer=bearer, now=now)
            raise OSError("socket vanished")
    transport = RaisingTransport()
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.outcome is ResultOutcome.OUTCOME_UNKNOWN and len(transport.dispatches) == 1
    assert budget.calls_reserved == 2 and budget.in_flight == 0


def test_a_non_200_or_textless_response_is_a_failure_not_an_answer(custody, budget):
    transport = FakeTransport([TransportOutcome.responded(429, {"error": {"type": "rate_limit"}}),
                               TransportOutcome.responded(200, {"output": []})])
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    assert p.execute(make_request(), now=NOW).outcome is ResultOutcome.FAILED
    assert p.execute(make_request(), now=NOW).outcome is ResultOutcome.FAILED
    assert budget.calls_reserved == 2  # a failed call was still a call


def test_a_responses_shaped_body_is_read_and_its_usage_is_metered(custody, budget):
    body = {"output": [{"type": "message", "content": [{"type": "output_text", "text": FAKE_RESPONSE_MARKER + " a"},
                                                        {"type": "output_text", "text": "b"}]}],
            "usage": {"total_tokens": 7}}
    transport = FakeTransport([TransportOutcome.responded(200, body)])
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.payload == FAKE_RESPONSE_MARKER + " ab" and result.provenance["token_count"] == 7


def test_a_transport_claiming_a_genuine_response_cannot_be_recorded(custody, budget):
    class LyingTransport(FakeTransport):
        def send(self, prepared, *, bearer, now):
            super().send(prepared, bearer=bearer, now=now)
            return TransportOutcome.responded(200, {"output_text": "real"}, genuine=True)
    p = OpenAIResponsesProvider(transport=LyingTransport(), custody=custody, budget=budget, credential_profile=PROFILE)
    with pytest.raises(GenuineResponseNotRecordable, match="genuine_call: true"):
        p.execute(make_request(), now=NOW)
    assert budget.calls_reserved == 1 and budget.in_flight == 0  # consumed, not refunded


# --- the LP-5 ceiling, non-compensatory ------------------------------------------

def test_ten_calls_then_the_eleventh_is_refused_without_dispatch_and_nothing_is_refunded(provider, transport, budget):
    for n in range(1, 11):
        assert provider.execute(make_request(), now=NOW + timedelta(seconds=n)).outcome is ResultOutcome.ANSWERED
        assert budget.calls_reserved == n and budget.cents_reserved == n * ESTIMATED_CENTS_PER_CALL
    assert budget.cents_reserved == COMMISSIONING_LIMITS.budget_usd_cents
    eleventh = make_request()
    assert provider._refusal(eleventh, NOW) is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED
    result = provider.execute(eleventh, now=NOW)
    assert result.refusal_reason is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED
    assert len(transport.dispatches) == 10
    assert budget.calls_reserved == 10 and budget.in_flight == 0
    assert [h["call_number"] for h in budget.history] == list(range(1, 11))


def test_concurrency_one_is_enforced_by_the_reservation_not_by_the_transport(custody):
    budget = CallBudget()
    budget.in_flight = 1  # another call of this tenant is in flight
    p = OpenAIResponsesProvider(transport=FakeTransport(), custody=custody, budget=budget, credential_profile=PROFILE)
    assert p._refusal(make_request(), NOW) is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED


def test_a_budget_shared_across_adapters_is_still_one_budget(custody):
    budget = CallBudget()
    a = OpenAIResponsesProvider(transport=FakeTransport(), custody=custody, budget=budget, credential_profile=PROFILE)
    b = OpenAIResponsesProvider(transport=FakeTransport(), custody=custody, budget=budget, credential_profile=PROFILE)
    for _ in range(5):
        a.execute(make_request(), now=NOW)
        b.execute(make_request(), now=NOW)
    assert b.execute(make_request(), now=NOW).refusal_reason is RefusalReason.COMMISSIONING_BUDGET_EXHAUSTED
    assert uuid.UUID(budget.history[0]["request_id"])


# --- validation row 11: a lease expired at use --------------------------------------

def test_a_lease_expired_at_use_is_a_custody_refusal_before_any_dispatch(transport, budget):
    from datetime import timedelta as _td
    from ugence_model_egress_unit import CredentialLease, CustodyRefused

    class ExpiredLeaseCustody(MarkerCustody):
        def materialize(self, request, *, now, production=False):
            self.requests.append(request)
            return CredentialLease(
                lease_id="lease-expired", custody_authority_id=self.custody_authority_id,
                credential_profile=self.credential_profile, vendor="openai", tenant_id=request.tenant_id,
                secret_version_ref="projects/p/secrets/s/versions/3", issued_at=now - _td(minutes=10),
                expires_at=now - _td(minutes=5), is_production_authoritative=False, _secret=SECRET)

    custody = ExpiredLeaseCustody()
    p = OpenAIResponsesProvider(transport=transport, custody=custody, budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.outcome is ResultOutcome.REFUSED and result.refusal_reason is RefusalReason.CREDENTIAL_NOT_COMMISSIONED
    assert transport.dispatches == [] and budget.calls_reserved == 0

    # and a lease whose use() itself refuses (expiry between the check and the use) is
    # refused before the transport sees the secret: still no dispatch, reservation kept
    from ugence_model_egress_unit import CustodyRefusal

    class LeaseRefusingAtUse(CredentialLease):
        def use(self, consumer, *, now):
            raise CustodyRefused(CustodyRefusal.CUSTODY_UNAVAILABLE, "expired between check and use")

    class RefusingAtUse(MarkerCustody):
        def materialize(self, request, *, now, production=False):
            self.requests.append(request)
            return LeaseRefusingAtUse(
                lease_id="lease-refusing", custody_authority_id=self.custody_authority_id,
                credential_profile=self.credential_profile, vendor="openai", tenant_id=request.tenant_id,
                secret_version_ref="projects/p/secrets/s/versions/3", issued_at=now,
                expires_at=now + _td(minutes=5), is_production_authoritative=False, _secret=SECRET)

    p = OpenAIResponsesProvider(transport=transport, custody=RefusingAtUse(), budget=budget, credential_profile=PROFILE)
    result = p.execute(make_request(), now=NOW)
    assert result.refusal_reason is RefusalReason.CREDENTIAL_NOT_COMMISSIONED
    assert transport.dispatches == [] and budget.calls_reserved == 1
