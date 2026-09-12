"""ADR §0.6: the typed, immutable, consumable authorization and the six-condition gate.

Every negative case the owner listed, against the in-memory fixture ledger; the
durable ledger's own behaviour is proven in ``test_migration_3_authorization_ledger.py``.
"""

from __future__ import annotations

import dataclasses
import json
import pathlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest

import ugence_model_egress_unit as meu
import ugence_model_egress_unit.version as version
from ugence_model_egress_unit import (
    AUTHORIZATION_SCHEMA,
    COMMISSIONING_LIMITS,
    NOT_GIVEN,
    AuthorizationRefusal as R,
    AuthorizationRefused,
    CommissioningRecordView,
    EgressRequest,
    EgressResult,
    GenuineCallAdmission,
    InMemoryAuthorizationLedger,
    LiveSyntheticValidationAuthorization,
    MinimizedUnit,
    ScopeExpectation,
    admit_genuine_call,
    check_live_authorization,
    designation_record_digest,
    reference_clearance,
)

NOW = datetime(2026, 9, 12, 1, 0, tzinfo=timezone.utc)
MODEL = "gpt-5.4-mini-2026-03-17"
OWNER = "Rakesh Mohan — Founder, Ugence Labs"
PKG = pathlib.Path(meu.__file__).resolve().parents[2]
PLAN = "a" * 64


def _request(text="synthetic probe", tokens=8, out=64, model=MODEL, vendor="openai") -> EgressRequest:
    tenant = uuid.uuid4()
    return EgressRequest.create(
        request_id=uuid.uuid4(), tenant_id=tenant, correlation_id=uuid.uuid4(), submitted_at=NOW,
        not_valid_after=NOW + timedelta(hours=1),
        authorization=reference_clearance(tenant_id=tenant, vendor=vendor, model=model),
        minimized_context=[MinimizedUnit("u-1", text, tokens)], parameters={"max_output_tokens": out})


#: A SHAPE for the tests. Nothing here is an authorization: the record it would have to
#: be pinned into stays NOT_GIVEN, and the tests prove that alone refuses it.
DESIGNATION = {"schema": "model-egress-unit.live-provider-designation.v1", "fixture": "test-designation"}
SCOPE = ScopeExpectation(openai_organization_id="org-a1b2c3d4e5", openai_project_id="proj_f6g7h8i9j0",
                         openai_service_account_id="svc-acct-meu-validation-01", model=MODEL)


def _auth(requests, **overrides) -> LiveSyntheticValidationAuthorization:
    base = dict(
        authorization_id="lsva-2026-09-12-001", nonce="nonce-" + "0" * 26, authorizing_owner=OWNER,
        authority_reference="acceptance://owner/live-synthetic-validation/2026-09-12",
        issued_at=NOW - timedelta(minutes=5), expires_at=NOW + timedelta(hours=2), environment="NON_PRODUCTION",
        openai_organization_id=SCOPE.openai_organization_id, openai_project_id=SCOPE.openai_project_id,
        openai_service_account_id=SCOPE.openai_service_account_id, provider="openai", model=MODEL,
        endpoint="https://api.openai.com/v1/responses", designation_record_digest=designation_record_digest(DESIGNATION),
        validation_plan_digest=PLAN, authorized_request_digests=tuple(r.digest() for r in requests),
        synthetic_non_sensitive_only=True, max_calls=len(requests), max_input_tokens=8_192, max_output_tokens=1_024,
        budget_usd_cents=2_500, concurrency=1, max_retries=1)
    base.update(overrides)
    return LiveSyntheticValidationAuthorization(**base)


def _record(auth=None, status="PENDING_VALIDATION", revoked=(), owner=OWNER, designation=DESIGNATION) -> CommissioningRecordView:
    return CommissioningRecordView(status=status, authorization_digest=auth.digest() if auth else NOT_GIVEN,
                                   revoked_digests=tuple(revoked), authorizing_owner=owner,
                                   designation_digest=designation_record_digest(designation))


def _admit(auth, request, record=None, ledger=None, now=NOW, expected=SCOPE, plan=PLAN, cents=250):
    return admit_genuine_call(auth, record=record if record is not None else _record(auth), request=request,
                              expected=expected, plan_digest=plan, now=now,
                              ledger=ledger if ledger is not None else InMemoryAuthorizationLedger(), estimated_cents=cents)


def _refused(reason, **kw):
    with pytest.raises(AuthorizationRefused) as info:
        _admit(**kw)
    assert info.value.reason is reason, info.value


# --- the happy path exists, and only through the gate -----------------------------

def test_a_canonical_authorization_admits_exactly_its_requests_once_each_and_consumes_before_anything_else():
    r1, r2 = _request(), _request(text="second synthetic probe")
    auth = _auth([r1, r2])
    ledger = InMemoryAuthorizationLedger()
    a1 = _admit(auth, r1, ledger=ledger)
    assert isinstance(a1, GenuineCallAdmission) and a1.verify() and a1.call_number == 1
    assert a1.request_id == r1.request_id and a1.authorization_digest == auth.digest()
    assert ledger.capacity(tenant_id=r1.tenant_id) == (9, 2250)
    a2 = _admit(auth, r2, ledger=ledger)
    assert a2.call_number == 2
    _refused(R.ALREADY_CONSUMED, auth=auth, request=r1, ledger=ledger)          # reuse of a consumed request
    r3 = _request(text="third, not in the set")
    _refused(R.REQUEST_NOT_AUTHORIZED, auth=auth, request=r3, ledger=ledger)   # after the sequence, still refused
    # an edited token verifies false
    assert not dataclasses.replace(a1, call_number=2).verify()


def test_the_admission_is_what_a_genuine_result_needs_and_a_token_alone_is_not_enough(monkeypatch):
    r = _request()
    auth = _auth([r])
    admission = _admit(auth, r)
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "PENDING_VALIDATION")
    result = EgressResult.answered_genuine(
        request_id=r.request_id, tenant_id=r.tenant_id, correlation_id=r.correlation_id, recorded_at=NOW,
        adapter_id="a", payload="x", model_ref=MODEL, custody_lease_id="lease", custody_authority_id="authority",
        admission=admission)
    assert result.provenance["genuine_call"] is True and result.trust == "UNTRUSTED_EVIDENCE"
    for bad in (None, "yes", True, OWNER, dataclasses.replace(admission, request_id=uuid.uuid4())):
        with pytest.raises(ValueError):
            EgressResult.answered_genuine(
                request_id=r.request_id, tenant_id=r.tenant_id, correlation_id=r.correlation_id, recorded_at=NOW,
                adapter_id="a", payload="x", model_ref=MODEL, custody_lease_id="lease", custody_authority_id="authority",
                admission=bad)
    monkeypatch.setattr(version, "COMMISSIONING_STATUS", "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS")
    with pytest.raises(ValueError, match="while commissioning is BLOCKED"):  # the mirror fails closed on drift
        EgressResult.answered_genuine(
            request_id=r.request_id, tenant_id=r.tenant_id, correlation_id=r.correlation_id, recorded_at=NOW,
            adapter_id="a", payload="x", model_ref=MODEL, custody_lease_id="lease", custody_authority_id="authority",
            admission=admission)


# --- the negative matrix -----------------------------------------------------------

@pytest.mark.parametrize("value", ["yes", "GIVEN", "owner-authorization-2026-09-12", True, OWNER, "sk-not-a-key", 1])
def test_arbitrary_non_not_given_values_never_satisfy_g2(value, monkeypatch):
    r = _request()
    # even with the mirror constant altered to a non-NOT_GIVEN value
    monkeypatch.setattr(version, "LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST", str(value))
    _refused(R.NOT_GIVEN, auth=value, request=r, record=_record(None))
    pinned = _record(_auth([r]))
    with pytest.raises(AuthorizationRefused) as info:
        _admit(value, r, record=pinned)
    assert info.value.reason is R.MALFORMED


def test_the_canonical_record_pinning_not_given_refuses_even_a_well_formed_authorization():
    r = _request()
    auth = _auth([r])
    _refused(R.NOT_GIVEN, auth=auth, request=r, record=_record(None))
    assert version.LIVE_SYNTHETIC_VALIDATION_AUTHORIZATION_DIGEST == NOT_GIVEN


def test_a_different_pinned_digest_or_an_edited_copy_is_not_canonical():
    r = _request()
    auth = _auth([r])
    other = _auth([r], authorization_id="lsva-2026-09-12-002")
    _refused(R.NOT_CANONICAL, auth=auth, request=r, record=_record(other))
    edited = dataclasses.replace(auth, max_calls=1, budget_usd_cents=100)
    _refused(R.NOT_CANONICAL, auth=edited, request=r, record=_record(auth))


@pytest.mark.parametrize("missing", ["authorization_id", "nonce", "authorizing_owner", "authority_reference", "issued_at",
                                     "expires_at", "environment", "openai_organization_id", "openai_project_id",
                                     "openai_service_account_id", "provider", "model", "endpoint",
                                     "designation_record_digest", "validation_plan_digest", "authorized_request_digests",
                                     "synthetic_non_sensitive_only", "max_calls", "max_input_tokens", "max_output_tokens",
                                     "budget_usd_cents", "concurrency", "max_retries"])
def test_every_field_is_required_in_a_record(missing):
    r = _request()
    record = _auth([r]).as_record()
    del record[missing]
    with pytest.raises(AuthorizationRefused) as info:
        LiveSyntheticValidationAuthorization.from_record(record)
    assert info.value.reason is R.MALFORMED and missing in str(info.value)
    record = _auth([r]).as_record()
    record["extra"] = 1
    with pytest.raises(AuthorizationRefused, match="unknown"):
        LiveSyntheticValidationAuthorization.from_record(record)


def test_a_record_round_trips_and_a_tampered_digest_field_is_refused():
    r = _request()
    auth = _auth([r])
    record = json.loads(json.dumps(auth.as_record()))
    assert LiveSyntheticValidationAuthorization.from_record(record) == auth
    record["digest"] = "0" * 64
    with pytest.raises(AuthorizationRefused, match="digest does not match"):
        LiveSyntheticValidationAuthorization.from_record(record)
    assert auth.schema == AUTHORIZATION_SCHEMA


@pytest.mark.parametrize("field, value, reason", [
    ("authorizing_owner", "Someone Else", R.OWNER_MISMATCH),
    ("environment", "PRODUCTION", R.ENVIRONMENT_MISMATCH),
    ("environment", "NON-PRODUCTION", R.ENVIRONMENT_MISMATCH),
    ("openai_organization_id", "org-other00000", R.SCOPE_MISMATCH),
    ("openai_project_id", "proj_other0000", R.SCOPE_MISMATCH),
    ("openai_service_account_id", "svc-acct-other", R.SCOPE_MISMATCH),
    ("provider", "anthropic", R.SCOPE_MISMATCH),
    ("model", "gpt-5.4-2026-03-17", R.SCOPE_MISMATCH),
    ("model", "gpt-5.4-mini", R.SCOPE_MISMATCH),
    ("endpoint", "https://api.openai.com/v1/chat/completions", R.SCOPE_MISMATCH),
    ("endpoint", "https://proxy.example/v1/responses", R.SCOPE_MISMATCH),
])
def test_wrong_owner_environment_organization_project_service_account_provider_model_or_endpoint(field, value, reason):
    r = _request()
    try:
        auth = _auth([r], **{field: value})
    except AuthorizationRefused as exc:      # refused at construction already
        assert exc.reason is reason
        return
    _refused(reason, auth=auth, request=r)


def test_the_requests_own_binding_must_name_the_authorized_vendor_and_model():
    r = _request(vendor="anthropic")
    auth = _auth([r])
    _refused(R.SCOPE_MISMATCH, auth=auth, request=r)


def test_designation_digest_drift_is_refused():
    r = _request()
    auth = _auth([r])
    drifted = dict(DESIGNATION, changed="a value was supplied after the authorization was issued")
    _refused(R.DESIGNATION_DRIFT, auth=auth, request=r, record=_record(auth, designation=drifted))


def test_wrong_request_or_validation_plan_digest_is_refused():
    r = _request()
    auth = _auth([r])
    _refused(R.PLAN_MISMATCH, auth=auth, request=r, plan="b" * 64)
    other = _request(text="a request the owner never authorized")
    _refused(R.REQUEST_NOT_AUTHORIZED, auth=auth, request=other)
    tampered = dataclasses.replace(r, minimized_context=(MinimizedUnit("u-1", "substituted", 8),))
    _refused(R.REQUEST_NOT_AUTHORIZED, auth=auth, request=tampered)


def test_a_request_beyond_the_authorized_limits_is_refused_even_if_within_the_ruling():
    r = _request(tokens=100, out=256)
    auth = _auth([r], max_input_tokens=50)
    _refused(R.REQUEST_EXCEEDS_AUTHORIZATION, auth=auth, request=r)
    auth = _auth([r], max_output_tokens=128)
    _refused(R.REQUEST_EXCEEDS_AUTHORIZATION, auth=auth, request=r)


@pytest.mark.parametrize("field, value", [
    ("max_calls", 11), ("max_calls", 0), ("max_input_tokens", 8_193), ("max_output_tokens", 1_025),
    ("budget_usd_cents", 2_501), ("concurrency", 2), ("max_retries", 2),
])
def test_limits_beyond_the_ruling_are_refused_at_construction(field, value):
    r = _request()
    with pytest.raises(AuthorizationRefused) as info:
        _auth([r], **{field: value})
    assert info.value.reason is R.LIMITS_EXCEED_RULING
    assert COMMISSIONING_LIMITS.max_genuine_calls == 10 and COMMISSIONING_LIMITS.budget_usd_cents == 2_500


def test_expired_not_yet_valid_and_revoked_authorizations_are_refused_and_met_extends_nothing():
    r = _request()
    auth = _auth([r])
    _refused(R.EXPIRED, auth=auth, request=r, now=auth.expires_at)
    _refused(R.EXPIRED, auth=auth, request=r, now=auth.expires_at, record=_record(auth, status="MET"))
    _refused(R.NOT_YET_VALID, auth=auth, request=r, now=auth.issued_at - timedelta(seconds=1))
    _refused(R.REVOKED, auth=auth, request=r, record=_record(auth, revoked=[auth.digest()]))
    _refused(R.REVOKED, auth=auth, request=r, record=_record(auth, status="MET", revoked=[auth.digest()]))


def test_nonce_replay_is_refused():
    r1, r2 = _request(), _request(text="another")
    first = _auth([r1])
    second = _auth([r2], authorization_id="lsva-2026-09-12-002")   # same nonce, different authorization
    ledger = InMemoryAuthorizationLedger()
    _admit(first, r1, ledger=ledger)
    _refused(R.NONCE_REPLAYED, auth=second, request=r2, record=_record(second), ledger=ledger)


def test_exhausted_calls_or_budget_in_the_durable_ledger_refuse_before_consumption():
    requests = [_request(text=f"probe {i}") for i in range(3)]
    with pytest.raises(AuthorizationRefused, match="more request digests than max_calls"):
        _auth(requests, max_calls=2)
    # calls exhausted: two authorizations against one tenant's ledger? no — one tenant, one
    # authorization of three calls, but the durable budget already holds nine reservations
    auth = _auth(requests, max_calls=3)
    ledger = InMemoryAuthorizationLedger()
    ledger._budget[str(requests[0].tenant_id)] = (9, 2000)
    r = requests[0]
    _admit(auth, r, ledger=ledger)                                        # the tenth call fits (500 cents left)
    ledger._budget[str(requests[1].tenant_id)] = (10, 0)
    _refused(R.CAPACITY_EXHAUSTED, auth=auth, request=requests[1], ledger=ledger)
    ledger._budget[str(requests[2].tenant_id)] = (5, 2400)
    _refused(R.CAPACITY_EXHAUSTED, auth=auth, request=requests[2], ledger=ledger, cents=250)
    # authorized calls exhausted: max_calls 1 but two distinct requests would need two calls
    r1, r2 = _request(), _request(text="second")
    auth = _auth([r1, r2], max_calls=2)
    ledger = InMemoryAuthorizationLedger()
    _admit(auth, r1, ledger=ledger)
    _admit(auth, r2, ledger=ledger)
    r3 = _request(text="third")
    auth3 = _auth([r1, r2, r3], max_calls=3, authorization_id="lsva-003", nonce="nonce-" + "1" * 26)
    ledger2 = InMemoryAuthorizationLedger()
    ledger2._calls[auth3.digest()] = 3                                   # the sequence already consumed
    _refused(R.CALLS_EXHAUSTED, auth=auth3, request=r3, record=_record(auth3), ledger=ledger2)


def test_met_without_a_current_authorization_admits_nothing_and_blocked_admits_nothing_with_one():
    r = _request()
    auth = _auth([r])
    _refused(R.NOT_GIVEN, auth=None, request=r, record=_record(None, status="MET"))
    _refused(R.NOT_GIVEN, auth=auth, request=r, record=_record(None, status="MET"))
    _refused(R.STATUS_NOT_ADMITTING, auth=auth, request=r, record=_record(auth, status="BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"))
    _refused(R.STATUS_NOT_ADMITTING, auth=auth, request=r, record=_record(auth, status="NOT_MET"))


def test_the_canonical_records_pin_no_authorization_and_the_designation_scope_matches_nothing_yet():
    """The real records beside the unit: NOT_GIVEN, so no authorization — however well
    formed — can be admitted, and every OpenAI identifier is UNDESIGNATED."""

    validation = json.loads((PKG / "MEU_LIVE_VALIDATION.json").read_text(encoding="utf-8"))
    designation = json.loads((PKG / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8"))
    view = CommissioningRecordView.from_records(validation, designation)
    assert view.authorization_digest == NOT_GIVEN and view.status == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"
    assert view.authorizing_owner == OWNER and view.revoked_digests == ()
    r = _request()
    _refused(R.STATUS_NOT_ADMITTING, auth=_auth([r]), request=r, record=view)
    obligations = designation["step8_required_values"]["obligations"]
    assert all(obligations[k] == "UNDESIGNATED" for k in ("openai_organization_id", "openai_project_id", "openai_project_service_account_id"))
