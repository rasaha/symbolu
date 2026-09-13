"""The custody seam holds no credential, leaks no secret, and refuses honestly.

No database, no clock, no environment: every instant is a literal and every adapter
is the inert reference.
"""

from __future__ import annotations

import copy
import json
import pickle
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from ugence_model_egress_unit import (
    REFERENCE_CUSTODY_MARKER,
    CredentialLease,
    CredentialRequest,
    CustodyAuditEvent,
    CustodyRefusal,
    CustodyRefused,
    CustodyRefusedInProduction,
    ModelCredentialCustodyPort,
    ReferenceCustodyAdapter,
    canonical_bytes,
    ledger_payload,
    materialize_with_audit,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=timezone.utc)
TENANT = uuid.UUID("00000000-0000-4000-8000-000000000001")


def request(**over) -> CredentialRequest:
    fields = dict(request_id=uuid.UUID("00000000-0000-4000-8000-000000000009"), tenant_id=TENANT,
                  vendor="reference-vendor", credential_profile="reference-profile", requested_at=NOW)
    fields.update(over)
    return CredentialRequest(**fields)


def test_the_reference_adapter_is_the_port_and_is_never_production_authoritative():
    adapter = ReferenceCustodyAdapter()
    assert isinstance(adapter, ModelCredentialCustodyPort)
    assert adapter.is_production_authoritative is False and adapter.maturity == "FIXTURE_ONLY"
    assert adapter.NON_PRODUCTION is True
    with pytest.raises(CustodyRefusedInProduction) as excinfo:
        adapter.materialize(request(), now=NOW, production=True)
    assert excinfo.value.reason is CustodyRefusal.REFERENCE_IN_PRODUCTION


def test_a_lease_exposes_its_secret_only_to_one_consumer_and_nowhere_else():
    lease = ReferenceCustodyAdapter().materialize(request(), now=NOW)
    assert lease.is_production_authoritative is False and lease.secret_version_ref == "reference/0"
    assert lease.expires_at == NOW + timedelta(minutes=5)
    seen = lease.use(lambda secret: secret, now=NOW)
    assert seen == REFERENCE_CUSTODY_MARKER
    for surface in (repr(lease), str(lease), json.dumps(lease.as_record()), canonical_bytes(
            "d", "t", lease.as_record()).decode()):
        assert REFERENCE_CUSTODY_MARKER not in surface and "_secret" not in surface
    assert "secret" not in {k for k in lease.as_record()}
    with pytest.raises(TypeError):
        pickle.dumps(lease)
    with pytest.raises(TypeError):
        copy.deepcopy(lease)
    # expired at use: refused, and the consumer never runs
    with pytest.raises(CustodyRefused) as excinfo:
        lease.use(lambda secret: pytest.fail("the consumer ran on an expired lease"),
                  now=NOW + timedelta(minutes=6))
    assert excinfo.value.reason is CustodyRefusal.CUSTODY_UNAVAILABLE
    assert REFERENCE_CUSTODY_MARKER not in str(excinfo.value)


def test_leases_never_compare_by_content_and_refuse_to_be_built_empty():
    a = ReferenceCustodyAdapter().materialize(request(), now=NOW)
    b = ReferenceCustodyAdapter().materialize(request(), now=NOW)
    assert a != b and a.lease_id == b.lease_id, "same deterministic id, never equal objects"
    with pytest.raises(ValueError, match="carries a credential"):
        CredentialLease(lease_id="x", custody_authority_id="c", credential_profile="p", vendor="v",
                        tenant_id=TENANT, secret_version_ref="r", issued_at=NOW,
                        expires_at=NOW + timedelta(minutes=1), is_production_authoritative=False)
    with pytest.raises(ValueError, match="expire after"):
        CredentialLease(lease_id="x", custody_authority_id="c", credential_profile="p", vendor="v",
                        tenant_id=TENANT, secret_version_ref="r", issued_at=NOW, expires_at=NOW,
                        is_production_authoritative=False, _secret="s")


def test_a_profile_or_vendor_mismatch_is_a_typed_refusal():
    adapter = ReferenceCustodyAdapter()
    with pytest.raises(CustodyRefused) as excinfo:
        adapter.materialize(request(vendor="openai"), now=NOW)
    assert excinfo.value.reason is CustodyRefusal.PROFILE_MISMATCH
    with pytest.raises(CustodyRefused) as excinfo:
        adapter.materialize(request(credential_profile="prod"), now=NOW)
    assert excinfo.value.reason is CustodyRefusal.PROFILE_MISMATCH


def test_every_materialization_is_audited_as_identifiers_and_digests_only():
    events = []
    lease, event = materialize_with_audit(ReferenceCustodyAdapter(), request(), now=NOW, sink=events.append)
    assert lease is not None and events == [event]
    assert event.outcome == "LEASED" and event.lease_id == lease.lease_id
    assert event.request_digest == request().digest() and event.is_production_authoritative is False
    record = event.as_record()
    assert record["kind"] == "meu.credential_leased"
    assert REFERENCE_CUSTODY_MARKER not in json.dumps(record)
    assert ledger_payload("meu.credential_leased", record) == record, "the audit event fits the ledger kind"
    assert len(event.digest()) == 64
    # refused, the same shape
    lease, event = materialize_with_audit(ReferenceCustodyAdapter(), request(vendor="openai"), now=NOW)
    assert lease is None and event.outcome == "REFUSED" and event.refusal is CustodyRefusal.PROFILE_MISMATCH
    assert ledger_payload("meu.credential_refused", event.as_record())["refusal"] == "custody_profile_mismatch"
    lease, event = materialize_with_audit(ReferenceCustodyAdapter(), request(), now=NOW, production=True)
    assert lease is None and event.refusal is CustodyRefusal.REFERENCE_IN_PRODUCTION


def test_a_port_that_raises_or_overreaches_is_recorded_as_unavailable_without_its_words():
    class Talkative:
        custody_authority_id = "talkative"
        credential_profile = "p"
        is_production_authoritative = True
        max_credential_age = timedelta(days=1)

        def materialize(self, request, *, now, production=False):
            raise RuntimeError("secret manager said: the key is MARKER-THIS-MUST-NOT-LEAK")

    lease, event = materialize_with_audit(Talkative(), request(), now=NOW)
    assert lease is None and event.refusal is CustodyRefusal.CUSTODY_UNAVAILABLE
    assert "MARKER-THIS" not in json.dumps(event.as_record())

    # a lease longer than the adapter's own rotation policy allows is refused, not trusted
    overlong = ReferenceCustodyAdapter(max_credential_age=timedelta(seconds=1))
    lease, event = materialize_with_audit(overlong, request(), now=NOW)
    assert lease is None and event.refusal is CustodyRefusal.CUSTODY_UNAVAILABLE


def test_the_request_is_identifiers_only_and_complete():
    with pytest.raises(ValueError):
        request(vendor="")
    with pytest.raises(ValueError):
        request(requested_at=datetime(2026, 9, 11, 12, 0))
    assert set(request().digest_body()) == {"request_id", "tenant_id", "vendor", "credential_profile",
                                            "requested_at", "purpose"}


def test_no_audit_event_can_claim_a_lease_without_naming_it():
    with pytest.raises(ValueError):
        CustodyAuditEvent(request_digest="d" * 64, tenant_id=TENANT, vendor="v", credential_profile="p",
                          custody_authority_id="c", observed_at=NOW, outcome="LEASED")
    with pytest.raises(ValueError):
        CustodyAuditEvent(request_digest="d" * 64, tenant_id=TENANT, vendor="v", credential_profile="p",
                          custody_authority_id="c", observed_at=NOW, outcome="REFUSED")


# --- the pinned-version adapter, fake path only (LP-2, LP-6 step 5) -------------------
from ugence_model_egress_unit import CustodyIdentity, PinnedSecretVersionCustodyAdapter, is_pinned_secret_version  # noqa: E402

RESOURCE = "projects/ugence-meu-validation/secrets/openai-meu-validation/versions/3"


def _pinned(reader=lambda resource: "MARKER-FAKE-PAYLOAD-NOT-A-KEY", **over):
    kwargs = dict(custody_authority_id="gsm-fake", credential_profile="openai-validation", vendor="openai",
                  secret_version_resource=RESOURCE, identity=CustodyIdentity("fake_emulator", "emulator"),
                  reader=reader)
    kwargs.update(over)
    return PinnedSecretVersionCustodyAdapter(**kwargs)


@pytest.mark.parametrize("resource, pinned", [
    (RESOURCE, True), ("projects/p/secrets/s/versions/latest", False), ("projects/p/secrets/s", False),
    ("projects//secrets/s/versions/1", False), ("p/secrets/s/versions/1", False), (None, False),
])
def test_only_an_exact_numeric_version_is_pinned(resource, pinned):
    assert is_pinned_secret_version(resource) is pinned


def test_the_pinned_adapter_refuses_latest_a_key_identity_and_a_loose_rotation():
    with pytest.raises(ValueError, match="never resolved"):
        _pinned(secret_version_resource="projects/p/secrets/s/versions/latest")
    with pytest.raises(ValueError, match="service-account key"):
        CustodyIdentity("service_account_key", "sa@p.iam")
    with pytest.raises(ValueError, match="unknown identity kind"):
        CustodyIdentity("password", "x")
    with pytest.raises(ValueError, match="90 days"):
        _pinned(max_credential_age=timedelta(days=91))
    with pytest.raises(ValueError, match="workload identity federation"):
        _pinned(production_authoritative=True)
    wif = _pinned(identity=CustodyIdentity("workload_identity_federation", "principal://pool/meu"),
                  production_authoritative=True)
    assert wif.is_production_authoritative is True and wif.maturity == "FIXTURE_ONLY"


def test_the_pinned_adapter_leases_the_exact_version_and_hides_the_payload():
    adapter = _pinned()
    assert adapter.is_production_authoritative is False
    req = request(vendor="openai", credential_profile="openai-validation")
    lease = adapter.materialize(req, now=NOW)
    assert lease.secret_version_ref == RESOURCE and lease.expires_at == NOW + timedelta(minutes=5)
    assert lease.use(lambda s: s, now=NOW) == "MARKER-FAKE-PAYLOAD-NOT-A-KEY"
    assert "MARKER-FAKE" not in repr(lease) and "MARKER-FAKE" not in json.dumps(lease.as_record())
    with pytest.raises(CustodyRefusedInProduction):
        adapter.materialize(req, now=NOW, production=True)
    _, event = materialize_with_audit(adapter, req, now=NOW)
    assert event.secret_version_ref == RESOURCE and event.is_production_authoritative is False


def test_a_reader_failure_or_empty_payload_is_unavailable_without_the_managers_words():
    def broken(resource):
        raise RuntimeError("PERMISSION_DENIED for principal x on MARKER-SECRET-TEXT")

    with pytest.raises(CustodyRefused) as excinfo:
        _pinned(reader=broken).materialize(request(vendor="openai", credential_profile="openai-validation"), now=NOW)
    assert excinfo.value.reason is CustodyRefusal.CUSTODY_UNAVAILABLE and "MARKER-SECRET" not in str(excinfo.value)
    with pytest.raises(CustodyRefused) as excinfo:
        _pinned(reader=lambda r: "  ").materialize(request(vendor="openai", credential_profile="openai-validation"), now=NOW)
    assert excinfo.value.reason is CustodyRefusal.CUSTODY_UNAVAILABLE


def test_a_leases_secret_is_not_a_dataclass_field_so_asdict_cannot_reach_it():
    """Regression, adversarial pass 2026-09-13: ``dataclasses.asdict`` walks ``fields()``
    and ignores ``repr=False``, so a secret kept as a field leaked through the one call a
    reasonable person makes when serializing a record. It is an InitVar now."""

    import dataclasses
    lease = CredentialLease(
        lease_id="l", custody_authority_id="c", credential_profile="p", vendor="v",
        tenant_id=TENANT, secret_version_ref="projects/p/secrets/s/versions/1",
        issued_at=NOW, expires_at=NOW + timedelta(minutes=5),
        is_production_authoritative=False, _secret="MARKER-SECRET-VALUE")
    assert "_secret" not in {f.name for f in dataclasses.fields(lease)}
    assert "MARKER-SECRET-VALUE" not in json.dumps(dataclasses.asdict(lease), default=str)
    assert "MARKER-SECRET-VALUE" not in repr(dataclasses.astuple(lease))
    assert "MARKER-SECRET-VALUE" not in repr(lease) and "MARKER-SECRET-VALUE" not in str(lease)
    assert "MARKER-SECRET-VALUE" not in json.dumps(lease.as_record())
    assert lease.use(lambda s: s, now=NOW) == "MARKER-SECRET-VALUE"
