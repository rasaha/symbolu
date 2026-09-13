"""Configuration carries references, never material; a designation is complete and
attested before anything is materialized."""

from __future__ import annotations

import json

import pytest

from ugence_model_egress_custody_gcp import (
    ConfigRefused, CustodyConfig, DesignationRefused, check_designation_accepted,
    refuse_credential_material)

from _fixtures import ATTESTED_BY, PROJECT, RESOURCE, SA, config, designation, identity
from synthetic_shapes import KINDS, service_account_key_document, synthetic_credential_shape


def test_a_complete_configuration_of_references_is_accepted():
    cfg = config()
    assert cfg.secret_version_resource == RESOURCE and cfg.environment == "non-production"
    record = cfg.as_reference_record()
    assert record["identity"]["service_account_resource"] == SA
    assert json.dumps(record)  # references only: it serializes


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("field", ["custody_authority_id", "credential_profile", "vendor"])
def test_a_credential_in_any_configuration_field_is_refused_without_being_echoed(kind, field):
    value = synthetic_credential_shape(kind)
    with pytest.raises(ConfigRefused) as info:
        config(**{field: value})
    assert field in str(info.value) and value not in str(info.value)


def test_a_downloaded_service_account_key_document_is_refused_in_any_field():
    """The realistic document carries a private-key block, so the credential-shape
    detector catches it first; a stripped one with no material still has to be caught by
    the key-document check, and both refusals name the field and repeat nothing."""

    document = service_account_key_document()
    with pytest.raises(ConfigRefused) as info:
        config(custody_authority_id=document)
    assert "credential shape" in str(info.value) and document not in str(info.value)

    stripped = json.dumps({"type": "service_account", "project_id": PROJECT,
                           "client_email": SA.split("/")[-1]})
    with pytest.raises(ConfigRefused) as info:
        config(credential_profile=stripped)
    assert "downloaded service-account key document" in str(info.value)
    assert stripped not in str(info.value)


@pytest.mark.parametrize("key", ["private_key", "privateKey", "PRIVATE-KEY", "api_key",
                                 "credentials_json", "service_account_key", "password",
                                 "GOOGLE_APPLICATION_CREDENTIALS", "secret_payload", "bearer_token"])
def test_a_field_that_names_material_rather_than_a_reference_is_refused(key):
    with pytest.raises(ConfigRefused, match="names credential material"):
        refuse_credential_material({"custody": {key: "anything-at-all"}})


def test_pointer_shaped_fields_are_never_confused_for_material():
    refuse_credential_material({
        "secret_version_resource": RESOURCE,
        "iam_policy_evidence_ref": "evidence://iam/2026-09-13",
        "designation_record_digest": "a" * 64,
        "authorization_record_path": "/etc/meu/authorization.json",
        "openai_project_id": "proj_f6g7h8i9j0",
    })


@pytest.mark.parametrize("over, why", [
    ({"environment": "production"}, "non-production only"),
    ({"environment": "PRODUCTION"}, "non-production only"),
    ({"environment": ""}, "non-production only"),
    ({"max_credential_age_days": 91}, "90 days"),
    ({"max_credential_age_days": 0}, "90 days"),
    ({"lease_ttl_seconds": 0}, "one second and one hour"),
    ({"lease_ttl_seconds": 7200}, "one second and one hour"),
    ({"custody_authority_id": "  "}, "required"),
    ({"secret_version_resource": f"projects/{PROJECT}/secrets/s/versions/latest"}, "exact number"),
    ({"identity": "attached_service_account"}, "RuntimeIdentityAssertion is required"),
])
def test_configuration_refusals(over, why):
    with pytest.raises((ConfigRefused, ValueError), match=why):
        config(**over)


def test_from_mapping_refuses_unknown_fields_so_a_typo_is_never_silently_ignored():
    base = {"custody_authority_id": "a", "credential_profile": "b", "vendor": "openai",
            "secret_version_resource": RESOURCE,
            "identity": {"source": "attached_service_account", "service_account_resource": SA,
                         "designated_service_account": SA, "designation_attested_by": ATTESTED_BY,
                         "designation_record_digest": "a" * 64}}
    assert CustodyConfig.from_mapping(base).vendor == "openai"
    with pytest.raises(ConfigRefused, match="unknown field"):
        CustodyConfig.from_mapping({**base, "enviroment": "non-production"})
    with pytest.raises(ConfigRefused, match="unknown field"):
        CustodyConfig.from_mapping({**base, "identity": {**base["identity"], "principal_hint": "x"}})


# --- the designation ------------------------------------------------------------------

def test_a_complete_attested_designation_is_accepted_and_reduced_to_what_custody_needs():
    accepted = check_designation_accepted(designation()["obligations"] and designation())
    assert accepted.gcp_project_id == PROJECT and accepted.service_account_resource == SA
    assert accepted.secret_version_resource == RESOURCE and accepted.attested_by == ATTESTED_BY
    assert accepted.identity_mechanism == "native_gcp_workload_identity"


def test_an_incomplete_designation_refuses_and_counts_what_is_missing():
    record = designation(obligations={"gcp_project_id": "UNDESIGNATED (LP-7 ruling 1)",
                                      "openai_project_id": "   "})
    with pytest.raises(DesignationRefused, match="2 of 17 designation obligations are not supplied"):
        check_designation_accepted(record)


def test_the_canonical_record_beside_the_unit_is_refused_because_nothing_is_designated_yet():
    """The real record ships with all seventeen UNDESIGNATED. No credential can be
    materialized against it, which is the state this slice leaves the repository in."""

    import json
    import pathlib
    # Anchored on this file, which lives in the checkout whether or not the distribution
    # under test was installed into site-packages.
    repo = pathlib.Path(__file__).resolve().parents[4]
    record = json.loads((repo / "packages/integration/model-egress-unit"
                         / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8"))
    with pytest.raises(DesignationRefused, match="17 of 17 designation obligations are not supplied"):
        check_designation_accepted(record["step8_required_values"])


@pytest.mark.parametrize("over, why", [
    ({"attestation": {"independently_checked_by": None}}, "no independent verification"),
    ({"attestation": {"independently_checked_by": "  "}}, "no independent verification"),
    ({"attestation": "checked"}, "no independent verification"),
    ({"obligation_count": 16}, "exactly 17 obligations"),
])
def test_an_unattested_or_miscounted_designation_is_refused(over, why):
    with pytest.raises(DesignationRefused, match=why):
        check_designation_accepted(designation(**over))


def test_a_designation_missing_an_obligation_entirely_is_refused():
    record = designation()
    del record["obligations"]["approved_processing_or_data_residency_region"]
    with pytest.raises(DesignationRefused, match="exactly 17 obligations"):
        check_designation_accepted(record)


def test_a_credential_shape_in_an_obligation_is_refused_without_being_echoed():
    value = synthetic_credential_shape("openai_project_key")
    with pytest.raises(DesignationRefused) as info:
        check_designation_accepted(designation(obligations={"openai_role_and_api_key_scope_evidence": value}))
    assert "credential shape" in str(info.value) and value not in str(info.value)


def test_a_secret_version_in_another_project_than_the_designated_one_is_refused():
    other = "projects/some-other-project/secrets/meu-openai-validation/versions/3"
    with pytest.raises(DesignationRefused, match="different project"):
        check_designation_accepted(designation(
            obligations={"full_numeric_secret_manager_version_resource": other}))


def test_an_unpinned_secret_version_in_the_designation_is_refused():
    with pytest.raises(DesignationRefused, match="exact number"):
        check_designation_accepted(designation(obligations={
            "full_numeric_secret_manager_version_resource":
                f"projects/{PROJECT}/secrets/meu-openai-validation/versions/latest"}))


@pytest.mark.parametrize("value", [None, "step8", 17, []])
def test_a_designation_that_is_not_a_mapping_is_refused(value):
    with pytest.raises(DesignationRefused):
        check_designation_accepted(value)
