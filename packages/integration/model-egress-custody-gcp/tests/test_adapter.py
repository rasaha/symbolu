"""The adapter: one pinned call, a lease that hides its payload, and a provider whose
words never reach a record."""

from __future__ import annotations

import json
import pickle

import pytest

from ugence_model_egress_custody_gcp import (
    AccessedSecretVersion, DesignationRefused, IdentityRefused,
    ProductionFormSecretManagerCustodyAdapter, SANITIZED_UNKNOWN, sanitize_exception_type)
from ugence_model_egress_unit import (
    CredentialLease, CustodyRefusal, CustodyRefused, ModelCredentialCustodyPort,
    PRODUCTION_FORM_CUSTODY_ADAPTER, looks_like_a_credential, materialize_with_audit)

from _fixtures import (
    ATTESTED_BY, DIGEST, FAKE_PAYLOAD, NOW, PROJECT, RESOURCE, SA, FakeClient, config,
    designation, identity, request)
from synthetic_shapes import KINDS, synthetic_credential_shape


def build(*, client=None, cfg=None, record=None) -> ProductionFormSecretManagerCustodyAdapter:
    return ProductionFormSecretManagerCustodyAdapter(
        config=cfg or config(), client=client or FakeClient(), designation=record or designation())


# --- the happy path, and what it is allowed to say -------------------------------------

def test_the_adapter_is_the_port_and_is_the_adapter_lp8_names():
    adapter = build()
    assert isinstance(adapter, ModelCredentialCustodyPort)
    assert adapter.adapter_name == PRODUCTION_FORM_CUSTODY_ADAPTER
    assert adapter.is_production_authoritative is True
    assert adapter.permitted_method == "AccessSecretVersion"


def test_it_accesses_exactly_the_pinned_version_once_and_leases_it():
    client = FakeClient()
    adapter = build(client=client)
    lease = adapter.materialize(request(), now=NOW)
    assert client.calls == [RESOURCE], "exactly one access, for exactly the pinned resource"
    assert isinstance(lease, CredentialLease)
    assert lease.secret_version_ref == RESOURCE and lease.is_production_authoritative is True
    assert lease.use(lambda s: s, now=NOW) == FAKE_PAYLOAD


def test_the_payload_is_absent_from_every_representation_record_and_serialization():
    adapter = build()
    lease = adapter.materialize(request(), now=NOW)
    surfaces = [repr(lease), str(lease), json.dumps(lease.as_record()), repr(adapter), str(adapter),
                json.dumps(adapter.as_record())]
    _, event = materialize_with_audit(build(), request(), now=NOW)
    surfaces += [repr(event), json.dumps(event.as_record()), event.digest()]
    for surface in surfaces:
        assert FAKE_PAYLOAD not in surface, surface[:120]
    with pytest.raises(TypeError):
        pickle.dumps(lease)
    with pytest.raises(TypeError):
        pickle.dumps(adapter)


def test_the_audit_event_is_the_units_existing_identifier_only_event():
    _, event = materialize_with_audit(build(), request(), now=NOW)
    record = event.as_record()
    assert record["kind"] == "meu.credential_leased" and record["outcome"] == "LEASED"
    assert record["secret_version_ref"] == RESOURCE and record["is_production_authoritative"] is True
    assert set(record) == {"kind", "request_digest", "tenant_id", "vendor", "credential_profile",
                           "custody_authority_id", "observed_at", "outcome", "lease_id",
                           "secret_version_ref", "expires_at", "is_production_authoritative", "refusal"}


def test_a_profile_or_vendor_mismatch_is_refused_before_the_client_is_touched():
    client = FakeClient()
    adapter = build(client=client)
    with pytest.raises(CustodyRefused) as info:
        adapter.materialize(request(vendor="anthropic"), now=NOW)
    assert info.value.reason is CustodyRefusal.PROFILE_MISMATCH
    assert client.calls == [], "the client was reached for a request the adapter does not serve"


# --- construction refuses, so a misconfigured adapter cannot call ----------------------

def test_construction_touches_nothing():
    client = FakeClient()
    build(client=client)
    assert client.calls == [], "constructing the adapter called Secret Manager"


def test_a_configured_version_that_is_not_the_designated_one_is_refused():
    other = f"projects/{PROJECT}/secrets/meu-openai-validation/versions/4"
    with pytest.raises(DesignationRefused, match="not the designated one"):
        build(cfg=config(secret_version_resource=other))


def test_a_secret_name_mismatch_between_configuration_and_designation_is_refused():
    other = f"projects/{PROJECT}/secrets/some-other-secret/versions/3"
    with pytest.raises(DesignationRefused, match="not the designated one"):
        build(cfg=config(secret_version_resource=other))


def test_a_project_mismatch_between_configuration_and_designation_is_refused():
    other = f"projects/another-project/secrets/meu-openai-validation/versions/3"
    with pytest.raises(DesignationRefused, match="not the designated one"):
        build(cfg=config(secret_version_resource=other))


def test_a_runtime_account_that_is_not_the_designated_meu_account_is_refused():
    other_sa = f"projects/{PROJECT}/serviceAccounts/other@{PROJECT}.iam.gserviceaccount.com"
    with pytest.raises(IdentityRefused):
        build(cfg=config(identity=identity(service_account_resource=other_sa,
                                           designated_service_account=other_sa)))


def test_an_identity_that_disagrees_with_the_designation_record_is_refused():
    other_sa = f"projects/{PROJECT}/serviceAccounts/other@{PROJECT}.iam.gserviceaccount.com"
    with pytest.raises(IdentityRefused, match="not the designated MEU service account"):
        build(record=designation(obligations={"meu_gcp_service_account_resource_name": other_sa}))


def test_a_mechanism_other_than_the_designated_one_is_refused():
    with pytest.raises(IdentityRefused, match="asserts a different mechanism|pool-constrained"):
        build(cfg=config(identity=identity(source="workload_identity_federation")))


@pytest.mark.parametrize("source", ["application_default_credentials", "developer_credentials",
                                    "service_account_key_file", "emulator"])
def test_no_unverified_or_fake_identity_can_construct_a_production_authoritative_adapter(source):
    with pytest.raises(IdentityRefused):
        build(cfg=config(identity=identity(source=source)))


def test_an_unattested_or_incomplete_designation_cannot_construct_the_adapter():
    with pytest.raises(DesignationRefused, match="no independent verification"):
        build(record=designation(attestation={"independently_checked_by": None}))
    with pytest.raises(DesignationRefused, match="not supplied"):
        build(record=designation(obligations={"gcp_project_id": "UNDESIGNATED"}))


def test_an_unvalidated_mapping_is_not_configuration_and_a_clientless_adapter_cannot_exist():
    with pytest.raises(ValueError, match="CustodyConfig"):
        ProductionFormSecretManagerCustodyAdapter(
            config={"vendor": "openai"}, client=FakeClient(), designation=designation())  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="access_secret_version"):
        ProductionFormSecretManagerCustodyAdapter(config=config(), client=None, designation=designation())
    with pytest.raises(ValueError, match="access_secret_version"):
        ProductionFormSecretManagerCustodyAdapter(config=config(), client=object(), designation=designation())


# --- what the client may return -------------------------------------------------------

@pytest.mark.parametrize("payload, why", [
    (b"", "empty payload"),
    (b"   \n\t ", "only whitespace"),
    (b"\xff\xfe\x00bad", "not valid UTF-8"),
    ("not-bytes", "not bytes"),
    (b"line-one\nline-two", "control characters"),
    (b"key\x00with-nul", "control characters"),
    (b"x" * (8 * 1024 + 1), "too large"),
])
def test_an_empty_non_utf8_or_malformed_payload_never_becomes_a_lease(payload, why):
    adapter = build(client=FakeClient(payload=payload))
    with pytest.raises(CustodyRefused, match=why) as info:
        adapter.materialize(request(), now=NOW)
    assert info.value.reason is CustodyRefusal.CUSTODY_UNAVAILABLE


def test_an_answer_for_a_different_version_is_refused_even_if_the_bytes_look_fine():
    """A client that resolved an alias would answer for another version. The lease must
    name the version the bytes came from, so a mismatch is a refusal, not a relabel."""

    other = f"projects/{PROJECT}/secrets/meu-openai-validation/versions/9"
    adapter = build(client=FakeClient(name=other))
    with pytest.raises(CustodyRefused, match="different version"):
        adapter.materialize(request(), now=NOW)


def test_an_answer_that_is_not_an_accessed_secret_version_is_refused():
    class Impostor:
        name = RESOURCE
        payload = b"anything"
    adapter = build(client=FakeClient(answer=Impostor()))
    with pytest.raises(CustodyRefused, match="not an AccessedSecretVersion"):
        adapter.materialize(request(), now=NOW)


def test_an_accessed_secret_version_hides_its_payload_and_refuses_pickling():
    accessed = AccessedSecretVersion(name=RESOURCE, payload=FAKE_PAYLOAD.encode("utf-8"))
    assert FAKE_PAYLOAD not in repr(accessed) and FAKE_PAYLOAD not in str(accessed)
    assert "withheld" in repr(accessed)
    with pytest.raises(TypeError):
        pickle.dumps(accessed)


# --- what a provider exception may say ------------------------------------------------

@pytest.mark.parametrize("kind", KINDS)
def test_a_google_exception_carrying_credential_shaped_text_never_reaches_the_refusal(kind):
    leaked = synthetic_credential_shape(kind)

    class PermissionDenied(RuntimeError):
        pass

    adapter = build(client=FakeClient(raises=PermissionDenied(
        f"PERMISSION_DENIED on {RESOURCE}: token {leaked} is not authorized")))
    with pytest.raises(CustodyRefused) as info:
        adapter.materialize(request(), now=NOW)
    message = str(info.value)
    assert leaked not in message and "PERMISSION_DENIED" not in message
    assert "PermissionDenied" in message, "the exception TYPE is named; its message is not"
    assert info.value.reason is CustodyRefusal.CUSTODY_UNAVAILABLE
    assert not looks_like_a_credential(message)


def test_a_refused_materialization_is_audited_without_the_providers_words():
    class Boom(RuntimeError):
        pass
    adapter = build(client=FakeClient(raises=Boom("MARKER-SECRET-TEXT")))
    lease, event = materialize_with_audit(adapter, request(), now=NOW)
    assert lease is None and event.outcome == "REFUSED"
    assert "MARKER-SECRET-TEXT" not in json.dumps(event.as_record())


def test_an_exception_whose_type_name_is_itself_absurd_is_replaced_outright():
    weird = type("x" * 100, (RuntimeError,), {})
    assert sanitize_exception_type(weird("m")) == SANITIZED_UNKNOWN
    assert sanitize_exception_type(RuntimeError("anything")) == "RuntimeError"


# --- listing is not reachable ---------------------------------------------------------

@pytest.mark.parametrize("method", ["list_secrets", "list_secret_versions", "get_secret",
                                    "add_secret_version", "destroy_secret_version"])
def test_the_adapter_never_reaches_for_a_listing_or_mutating_method(method):
    client = FakeClient()
    adapter = build(client=client)
    adapter.materialize(request(), now=NOW)
    with pytest.raises(AssertionError, match=method):
        getattr(client, method)
    assert client.calls == [RESOURCE]


# --- regressions from the adversarial pass of 2026-09-13 ------------------------------

def test_a_sanitized_refusal_leaves_no_provider_exception_on_the_context_chain():
    """``raise ... from None`` suppresses the PRINTING of the original exception but
    leaves it on ``__context__``, where an error reporter walking the chain would find
    the provider's message. The refusal is raised outside the except block instead."""

    leaked = synthetic_credential_shape("openai_project_key")

    class PermissionDenied(RuntimeError):
        pass

    adapter = build(client=FakeClient(raises=PermissionDenied(f"denied: {leaked}")))
    with pytest.raises(CustodyRefused) as info:
        adapter.materialize(request(), now=NOW)
    assert info.value.__context__ is None and info.value.__cause__ is None
    chain = []
    exc = info.value
    while exc is not None and exc not in chain:
        chain.append(exc)
        exc = exc.__context__ or exc.__cause__
    assert all(leaked not in str(link) for link in chain)
