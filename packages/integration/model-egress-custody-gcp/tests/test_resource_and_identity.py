"""The resource is pinned before anything is called, and only a bound native identity
(or WIF) may be production-authoritative."""

from __future__ import annotations

import pytest

from ugence_model_egress_custody_gcp import (
    IdentityRefused, ResourceRefused, RuntimeIdentityAssertion, check_production_identity,
    parse_secret_version)
from ugence_model_egress_unit import CustodyIdentity

from _fixtures import DIGEST, PROJECT, RESOURCE, SA, ATTESTED_BY, identity
from synthetic_shapes import KINDS, synthetic_credential_shape


def test_a_pinned_numeric_version_parses_into_its_parts():
    parsed = parse_secret_version(RESOURCE)
    assert (parsed.project, parsed.secret, parsed.version) == (PROJECT, "meu-openai-validation", 3)
    assert parsed.resource == RESOURCE
    assert parsed.secret_resource == f"projects/{PROJECT}/secrets/meu-openai-validation"


@pytest.mark.parametrize("resource, why", [
    (f"projects/{PROJECT}/secrets/s/versions/latest", "alias"),
    (f"projects/{PROJECT}/secrets/s/versions/LATEST", "alias"),
    (f"projects/{PROJECT}/secrets/s/versions/3a", "alias"),
    (f"projects/{PROJECT}/secrets/s/versions/", "empty segment"),
    (f"projects/{PROJECT}/secrets/s/versions/003", "zero-padded"),
    (f"projects/{PROJECT}/secrets/s/versions/0", "numbered from 1"),
    (f"projects/{PROJECT}/secrets/s/versions/-1", "exact number"),
    (f"projects/{PROJECT}/secrets/s", "exactly projects/"),
    (f"projects//secrets/s/versions/1", "exactly projects/"),
    (f"projects/{PROJECT}/secrets//versions/1", "exactly projects/"),
    (f"projects/{PROJECT}/secrets/s/versions/1/", "exactly projects/"),
    (f" projects/{PROJECT}/secrets/s/versions/1", "whitespace"),
    ("", "required"), (None, "required"), (17, "required"),
])
def test_every_unpinned_or_malformed_resource_is_refused(resource, why):
    with pytest.raises(ResourceRefused, match=why):
        parse_secret_version(resource)


@pytest.mark.parametrize("kind", KINDS)
def test_a_credential_pasted_into_the_resource_field_is_refused_without_being_echoed(kind):
    value = synthetic_credential_shape(kind)
    with pytest.raises(ResourceRefused) as info:
        parse_secret_version(value)
    assert "credential shape" in str(info.value)
    assert value not in str(info.value)


def test_the_attached_service_account_bound_to_the_designation_is_production_authoritative():
    resolved = check_production_identity(identity())
    assert isinstance(resolved, CustodyIdentity)
    assert resolved.kind == "native_gcp_workload_identity" and resolved.principal == SA
    assert resolved.production_authority_refusal() is None


def test_generic_adc_presented_as_a_native_identity_is_refused_by_name():
    """ADC may be how Cloud Run's own credential is found, but succeeding proves nothing
    about which identity was found, so it is never production-authoritative."""

    with pytest.raises(IdentityRefused, match="discovery order, not an identity"):
        check_production_identity(identity(source="application_default_credentials"))
    # …and the kind itself refuses, however it is reached
    assert "never production-authoritative" in CustodyIdentity(
        "application_default_credentials", SA).production_authority_refusal()


@pytest.mark.parametrize("source, why", [
    ("developer_credentials", "human identity"),
    ("service_account_key_file", "downloaded service-account key"),
    ("emulator", "test double"),
    ("something_else", "unknown runtime identity source"),
])
def test_every_other_source_is_refused_with_its_own_reason(source, why):
    with pytest.raises(IdentityRefused, match=why):
        check_production_identity(identity(source=source))


@pytest.mark.parametrize("account", [
    f"projects/{PROJECT}/serviceAccounts/000000000000-compute@developer.gserviceaccount.com",
    "user:someone@ugence.invalid",
    "meu-runtime@gmail.com",
])
def test_a_human_or_default_compute_account_is_not_the_meu_identity(account):
    with pytest.raises(IdentityRefused):
        check_production_identity(identity(service_account_resource=account,
                                           designated_service_account=account))


def test_a_runtime_account_that_is_not_the_designated_one_is_refused():
    other = f"projects/{PROJECT}/serviceAccounts/other@{PROJECT}.iam.gserviceaccount.com"
    with pytest.raises(IdentityRefused, match="not the designated service-account resource"):
        check_production_identity(identity(service_account_resource=other))


@pytest.mark.parametrize("over, why", [
    ({"designated_service_account": ""}, "exact designated service-account resource"),
    ({"designated_service_account": "meu-runtime@p.iam.gserviceaccount.com"}, "exact designated"),
    ({"designation_attested_by": "  "}, "no independent verification"),
    ({"designation_record_digest": ""}, "digest is absent or malformed"),
    ({"designation_record_digest": "not-a-digest"}, "digest is absent or malformed"),
    ({"service_account_resource": "meu-runtime@p.iam.gserviceaccount.com"}, "projects/<project>/serviceAccounts"),
])
def test_an_unbound_or_unattested_native_identity_is_refused(over, why):
    with pytest.raises(IdentityRefused, match=why):
        check_production_identity(identity(**over))


def test_a_credential_in_an_identity_field_is_refused_without_being_echoed():
    value = synthetic_credential_shape("openai_project_key")
    with pytest.raises(IdentityRefused) as info:
        check_production_identity(identity(designation_attested_by=value))
    assert "credential shape" in str(info.value) and value not in str(info.value)


def test_a_bare_string_asserts_no_identity():
    with pytest.raises(IdentityRefused, match="RuntimeIdentityAssertion is required"):
        check_production_identity("attached_service_account")  # type: ignore[arg-type]


def test_federated_identity_remains_production_authoritative_and_still_needs_a_non_human_principal():
    wif = CustodyIdentity("workload_identity_federation", "principal://pool/meu-runtime")
    assert wif.production_authority_refusal() is None
    human = CustodyIdentity("workload_identity_federation", "user:someone@ugence.invalid")
    assert "human identity" in human.production_authority_refusal()
    loose = CustodyIdentity("workload_identity_federation", "meu-runtime")
    assert "pool-constrained" in loose.production_authority_refusal()
