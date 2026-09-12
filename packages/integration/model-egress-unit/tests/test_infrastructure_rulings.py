"""LP-7 / step 8 (non-production): the seventeen values' shapes, the refusals, the rotation order."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from ugence_model_egress_unit import (
    COMMISSIONING_STATUS,
    MAX_ROTATION_INTERVAL,
    OPENAI_KEY_SCOPE,
    ROTATION_SEQUENCE,
    STEP8_REQUIRED_VALUES,
    DesignationRefused,
    NativeGcpWorkloadIdentity,
    RotationRefused,
    Step8Designation,
    WorkloadIdentityFederation,
    check_rotation_plan,
    check_step8_designation,
    looks_like_a_credential,
    rollback_permitted,
)
from ugence_model_egress_unit.infrastructure import DESTRUCTION_STEP
from synthetic_shapes import KINDS, expected_family, synthetic_credential_shape

NOW = datetime(2026, 9, 11, 18, 0, tzinfo=timezone.utc)

WIF = WorkloadIdentityFederation(
    oidc_issuer="https://token.actions.githubusercontent.invalid/issuer",
    audience="//iam.googleapis.com/projects/000000000000/locations/global/workloadIdentityPools/meu-pool/providers/meu-provider",
    subject_constraints="assertion.sub == 'system:serviceaccount:meu:meu-runtime'",
    pool="projects/000000000000/locations/global/workloadIdentityPools/meu-pool",
    provider="projects/000000000000/locations/global/workloadIdentityPools/meu-pool/providers/meu-provider",
    principal_binding="principal://iam.googleapis.com/projects/000000000000/locations/global/workloadIdentityPools/meu-pool/subject/system:serviceaccount:meu:meu-runtime",
)

#: Well-formed in every field. These are SHAPES for the tests, not designations: nothing
#: here designates a project, an account, a secret, an organization or a region.
SHAPE = dict(
    gcp_project_id="ugence-meu-nonprod-4821",
    gcp_project_number="000000000000",
    meu_service_account="projects/ugence-meu-nonprod-4821/serviceAccounts/meu-runtime@ugence-meu-nonprod-4821.iam.gserviceaccount.com",
    deployment_platform_identity_mechanism="workload_identity_federation",
    workload_identity_binding=WIF,
    secret_version="projects/ugence-meu-nonprod-4821/secrets/meu-openai-validation/versions/3",
    iam_policy_evidence_ref="evidence://iam/meu-openai-validation/policy/2026-09-11",
    iam_binding_scope="secret",
    audit_log_config_and_retention_ref="evidence://audit/secretmanager/config-and-retention/2026-09-11",
    rotation_runbook_ref="runbook://meu-openai-rotation/v1-approved",
    openai_organization_id="org-a1b2c3d4e5",
    openai_project_id="proj_f6g7h8i9j0",
    openai_service_account_id="svc-acct-meu-validation-01",
    openai_role_and_key_scope_evidence_ref="evidence://openai/role-and-key-scope/2026-09-11",
    openai_key_scope=OPENAI_KEY_SCOPE,
    vendor_spend_control_evidence_ref="evidence://openai/spend-control/2026-09-11",
    vendor_spend_control_classification="advisory",
    model_availability_evidence_ref="evidence://openai/models/availability-check/2026-09-11",
    data_processing_terms_ref="terms://openai/data-processing-addendum/ref-2026",
    processing_region="eu",
    environment="non-production",
    verified_by="Rakesh Mohan — Founder, Ugence Labs",
    verified_at=NOW,
)


def _record(**overrides) -> Step8Designation:
    return Step8Designation(**dict(SHAPE, **overrides))


def test_ruling_12_is_seventeen_obligations_represented_by_the_checked_fields_and_nothing_claims_an_eighteenth():
    from ugence_model_egress_unit import (
        STEP8_ATTESTATION_FIELDS, STEP8_DERIVED_SUBFIELDS, STEP8_OBLIGATION_COUNT, STEP8_OBLIGATIONS, step8_field_counts)
    assert STEP8_OBLIGATION_COUNT == len(STEP8_OBLIGATIONS) == 17
    assert [n for n, _, _ in STEP8_OBLIGATIONS] == list(range(1, 18))
    assert [t for _, t, _ in STEP8_OBLIGATIONS] == [
        "GCP project ID", "GCP project number", "MEU GCP service-account resource name",
        "deployment-platform identity mechanism",
        "WIF pool/provider and constrained principal binding, or the documented native GCP equivalent",
        "full numeric Secret Manager version resource", "secret-level IAM-policy evidence reference",
        "Data Access audit-log configuration and retention reference", "approved rotation-runbook reference",
        "OpenAI organization ID", "OpenAI project ID", "OpenAI project service-account ID",
        "OpenAI role and API-key scope evidence",
        "vendor spend-control evidence and hard-stop/advisory classification",
        "designated-model availability evidence", "applicable data-processing-terms reference",
        "approved processing/data-residency region"]
    # the one decomposition: obligation 14 is two typed fields; every other obligation is one
    assert [len(f) for _, _, f in STEP8_OBLIGATIONS] == [1] * 13 + [2] + [1] * 3
    assert dict((n, f) for n, _, f in STEP8_OBLIGATIONS)[14] == ("vendor_spend_control_evidence_ref", "vendor_spend_control_classification")
    assert tuple(f for _, _, fs in STEP8_OBLIGATIONS for f in fs) == STEP8_REQUIRED_VALUES
    assert len(STEP8_REQUIRED_VALUES) == 18
    counts = step8_field_counts()
    assert counts["obligations"] == 17 and counts["obligation_bearing_fields"] == 18
    assert counts["derived_subfields"] == 2 and STEP8_DERIVED_SUBFIELDS == ("iam_binding_scope", "openai_key_scope")
    assert counts["attestation_fields"] == 3 and STEP8_ATTESTATION_FIELDS == ("environment", "verified_by", "verified_at")
    assert counts["checked_fields"] == 23 == len(dataclasses.fields(Step8Designation))
    assert counts["statement"] == "17 mandatory designation obligations represented by 23 checked fields"
    assert counts["identity_binding_subfields"] == {"workload_identity_federation": 6, "native_gcp_workload_identity": 2}
    # the derived subfields and attestation fields are never listed as obligations
    listed = {f for _, _, fs in STEP8_OBLIGATIONS for f in fs}
    assert not listed & set(STEP8_DERIVED_SUBFIELDS) and not listed & set(STEP8_ATTESTATION_FIELDS)


def test_a_well_formed_verified_non_production_record_is_accepted_and_changes_no_status():
    record = check_step8_designation(_record())
    out = record.as_record()
    assert out["verified_at"] == NOW.isoformat() and out["workload_identity_binding"]["mechanism"] == "workload_identity_federation"
    native = _record(deployment_platform_identity_mechanism="native_gcp_workload_identity",
                     workload_identity_binding=NativeGcpWorkloadIdentity(
                         path="gke-workload-identity://meu/meu-runtime", no_static_key_evidence_ref="evidence://iam/keys/none/2026-09-11"))
    assert check_step8_designation(native).as_record()["workload_identity_binding"]["mechanism"] == "native_gcp_workload_identity"
    assert COMMISSIONING_STATUS == "BLOCKED_PENDING_INFRASTRUCTURE_DESIGNATIONS"


@pytest.mark.parametrize("name", [n for n in STEP8_REQUIRED_VALUES if n != "workload_identity_binding"]
                         + ["iam_binding_scope", "openai_key_scope", "environment", "verified_by"])
def test_every_value_is_required(name):
    with pytest.raises(DesignationRefused, match=f"{name}: required"):
        check_step8_designation(_record(**{name: ""}))
    with pytest.raises(DesignationRefused, match=name):
        check_step8_designation(_record(**{name: "   "}))


@pytest.mark.parametrize("value", [
    "UNDESIGNATED (LP-6 step 8)", "projects/<project>/secrets/<name>/versions/<n>", "TODO", "tbd",
    "my-project-placeholder", "example-project", "org-changeme", "proj_xxx", "{{ project }}",
    "projects/p/secrets/s/versions/latest", "fake-evidence", "dummy", "pending-review",
])
def test_a_placeholder_alias_or_synthesized_token_is_refused_in_any_field(value):
    for name in STEP8_REQUIRED_VALUES:
        if name == "workload_identity_binding":
            continue
        with pytest.raises(DesignationRefused, match="placeholder or alias"):
            check_step8_designation(_record(**{name: value}))
    with pytest.raises(DesignationRefused, match="workload_identity_binding.audience: placeholder"):
        check_step8_designation(_record(workload_identity_binding=dataclasses.replace(WIF, audience="<audience>")))


@pytest.mark.parametrize("kind", KINDS)
def test_a_secret_shaped_value_is_refused_in_any_field_without_being_echoed(kind):
    secret_like = synthetic_credential_shape(kind)   # assembled at runtime; no literal in this file
    assert looks_like_a_credential(secret_like)
    for name in ("iam_policy_evidence_ref", "openai_service_account_id", "rotation_runbook_ref", "processing_region"):
        with pytest.raises(DesignationRefused) as info:
            check_step8_designation(_record(**{name: secret_like}))
        assert "credential shape" in str(info.value) and secret_like[:12] not in str(info.value)
    assert not looks_like_a_credential("projects/p/secrets/meu-openai/versions/3")
    assert not looks_like_a_credential("evidence://iam/policy/2026-09-11")
    assert not looks_like_a_credential("task-123")  # 'sk-' inside a word is not a key


def test_the_runtime_assembled_shapes_take_the_same_production_detection_path_as_the_real_prefixes():
    """Requirement 8: each synthetic value is caught by the production detector through
    the prefix family a real credential of that kind would trigger, and each fragment
    alone is not a credential shape."""

    from ugence_model_egress_unit import CREDENTIAL_SHAPE_PREFIXES
    for kind in KINDS:
        value = synthetic_credential_shape(kind)
        family = expected_family(kind)
        assert family in CREDENTIAL_SHAPE_PREFIXES, (kind, family)
        assert looks_like_a_credential(value), kind
        assert family in value, kind
        # a well-formed record is refused on this value in an evidence field, naming the field only
        with pytest.raises(DesignationRefused) as info:
            check_step8_designation(_record(rotation_runbook_ref=value))
        assert "credential shape" in str(info.value) and value not in str(info.value)
    # the fragments themselves are not shapes (that is what keeps them out of the diff scan)
    for fragment in ("sk", "-", "proj", "svcacct", "ey", "JhbGciOiJIUzI1NiJ9", "AI", "za", "ya", "29", "-----", "BEGIN ", "PRIVATE", " KEY-----"):
        assert not looks_like_a_credential(fragment), fragment


def test_a_production_or_unverified_record_is_refused():
    with pytest.raises(DesignationRefused, match="environment: these rulings govern the first non-production"):
        check_step8_designation(_record(environment="production"))
    with pytest.raises(DesignationRefused, match="independently checked"):
        check_step8_designation(_record(verified_at=None))
    with pytest.raises(DesignationRefused, match="timezone-aware"):
        check_step8_designation(_record(verified_at=NOW.replace(tzinfo=None)))


@pytest.mark.parametrize("field, value, why", [
    ("gcp_project_id", "Ugence-Prod", "well-formed"), ("gcp_project_id", "p", "well-formed"),
    ("gcp_project_id", "ugence-meu-", "well-formed"), ("gcp_project_number", "12ab", "digits only"),
])
def test_a_malformed_project_id_or_number_is_refused_but_never_judged_by_name(field, value, why):
    with pytest.raises(DesignationRefused, match=why):
        check_step8_designation(_record(**{field: value}))
    # ruling 12: nothing is inferred from naming conventions — a name saying 'prod' is neither
    # accepted nor refused on that account; the environment field and the evidence decide
    prodlike = _record(gcp_project_id="ugence-meu-prod-4821",
                       meu_service_account="projects/ugence-meu-prod-4821/serviceAccounts/meu-runtime@ugence-meu-prod-4821.iam.gserviceaccount.com",
                       secret_version="projects/ugence-meu-prod-4821/secrets/meu-openai-validation/versions/3")
    assert check_step8_designation(prodlike) is prodlike


@pytest.mark.parametrize("account, why", [
    ("projects/ugence-meu-nonprod-4821/serviceAccounts/123456-compute@developer.gserviceaccount.com", "default compute"),
    ("projects/ugence-meu-nonprod-4821/serviceAccounts/rakesh@ugence.org", "human identity or a foreign project"),
    ("projects/other-nonprod-1/serviceAccounts/meu@other-nonprod-1.iam.gserviceaccount.com", "designated project"),
    ("meu-runtime@ugence-meu-nonprod-4821.iam.gserviceaccount.com", "serviceAccounts"),
    ("projects/ugence-meu-nonprod-4821/serviceAccounts/meu-runtime", "malformed"),
])
def test_a_human_default_compute_foreign_or_malformed_identity_is_refused(account, why):
    with pytest.raises(DesignationRefused, match=why):
        check_step8_designation(_record(meu_service_account=account))


def test_the_identity_mechanism_and_binding_must_agree_and_be_constrained():
    with pytest.raises(DesignationRefused, match="deployment_platform_identity_mechanism"):
        check_step8_designation(_record(deployment_platform_identity_mechanism="service_account_key"))
    with pytest.raises(DesignationRefused, match="does not match"):
        check_step8_designation(_record(deployment_platform_identity_mechanism="native_gcp_workload_identity"))
    with pytest.raises(DesignationRefused, match="oidc_issuer"):
        check_step8_designation(_record(workload_identity_binding=dataclasses.replace(WIF, oidc_issuer="http://issuer")))
    with pytest.raises(DesignationRefused, match="unconstrained principal"):
        check_step8_designation(_record(workload_identity_binding=dataclasses.replace(
            WIF, principal_binding="principalSet://iam.googleapis.com/projects/000000000000/locations/global/workloadIdentityPools/meu-pool/*")))
    with pytest.raises(DesignationRefused, match="workload_identity_binding"):
        check_step8_designation(_record(workload_identity_binding="a string"))


@pytest.mark.parametrize("secret, why", [
    ("projects/ugence-meu-nonprod-4821/secrets/meu-openai-validation/versions/latest", "placeholder or alias"),
    ("projects/ugence-meu-nonprod-4821/secrets/meu-openai-validation", "numeric"),
    ("projects/ugence-meu-nonprod-4821/secrets/meu-openai-validation/versions/v3", "numeric"),
    ("projects/other-nonprod-1/secrets/meu-openai-validation/versions/3", "designated project"),
])
def test_an_unpinned_aliased_or_foreign_secret_version_is_refused(secret, why):
    with pytest.raises(DesignationRefused, match=why):
        check_step8_designation(_record(secret_version=secret))
    by_number = _record(secret_version="projects/000000000000/secrets/meu-openai-validation/versions/3")
    assert check_step8_designation(by_number) is by_number


@pytest.mark.parametrize("scope", ["project", "folder", "organization", "Secret"])
def test_a_binding_anywhere_but_on_the_secret_is_refused(scope):
    with pytest.raises(DesignationRefused, match="never with a project-level grant"):
        check_step8_designation(_record(iam_binding_scope=scope))


@pytest.mark.parametrize("field, value, why", [
    ("openai_organization_id", "a1b2c3", "org-"), ("openai_organization_id", "org-", "org-"),
    ("openai_project_id", "org-a1b2c3", "proj_"), ("openai_project_id", "proj_", "proj_"),
    ("openai_key_scope", "api.responses.write api.models.read", "exactly api.responses.write"),
    ("openai_key_scope", "all", "exactly api.responses.write"),
    ("vendor_spend_control_classification", "limit", "recorded as what it is"),
    ("model_availability_evidence_ref", "gpt-5.4-mini-2026-03-17", "not availability evidence"),
])
def test_openai_identity_scope_spend_classification_and_availability_evidence_shapes(field, value, why):
    with pytest.raises(DesignationRefused, match=why):
        check_step8_designation(_record(**{field: value}))


def test_no_value_is_inferred_from_another_and_the_record_is_immutable():
    with pytest.raises(DesignationRefused, match="gcp_project_id: required"):
        check_step8_designation(_record(gcp_project_id=""))
    with pytest.raises(dataclasses.FrozenInstanceError):
        _record().gcp_project_id = "other"


# --- ruling 6 ------------------------------------------------------------------------

def test_the_rotation_sequence_is_the_owners_eight_steps_and_revocation_comes_last():
    assert ROTATION_SEQUENCE == (
        "create_new_openai_service_account_credential", "store_as_new_secret_manager_version",
        "designate_candidate_numeric_version", "offline_fake_transport_conformance",
        "authorize_controlled_validation_separately", "accept_and_activate_candidate_version",
        "verify_successful_operation", "revoke_superseded_credential_and_disable_version")
    assert check_rotation_plan(ROTATION_SEQUENCE) == ROTATION_SEQUENCE
    assert check_rotation_plan(ROTATION_SEQUENCE[:5]) == ROTATION_SEQUENCE[:5]
    assert MAX_ROTATION_INTERVAL == timedelta(days=90)


@pytest.mark.parametrize("plan", [
    (),
    ("revoke_superseded_credential_and_disable_version", "create_new_openai_service_account_credential"),
    ("create_new_openai_service_account_credential", "revoke_superseded_credential_and_disable_version"),
    ("create_new_openai_service_account_credential", "store_as_new_secret_manager_version", "accept_and_activate_candidate_version"),
    ROTATION_SEQUENCE[:3] + ("authorize_controlled_validation_separately", "offline_fake_transport_conformance"),
    ROTATION_SEQUENCE[:5] + ("verify_successful_operation", "accept_and_activate_candidate_version"),
])
def test_any_other_order_is_refused(plan):
    with pytest.raises(RotationRefused):
        check_rotation_plan(plan)


def test_destruction_never_happens_during_initial_commissioning_and_only_after_the_full_sequence_later():
    full = ROTATION_SEQUENCE + (DESTRUCTION_STEP,)
    with pytest.raises(RotationRefused, match="initial commissioning"):
        check_rotation_plan(full)
    with pytest.raises(RotationRefused, match="initial commissioning"):
        check_rotation_plan(("create_new_openai_service_account_credential", DESTRUCTION_STEP))
    assert check_rotation_plan(full, initial_commissioning=False) == full
    with pytest.raises(RotationRefused, match="complete sequence"):
        check_rotation_plan(("create_new_openai_service_account_credential", DESTRUCTION_STEP), initial_commissioning=False)


def test_rollback_needs_both_versions_valid_and_the_owner():
    assert rollback_permitted(previous_secret_version_valid=True, previous_openai_credential_valid=True, owner_authorized=True)
    for flags in [(False, True, True), (True, False, True), (True, True, False)]:
        assert not rollback_permitted(previous_secret_version_valid=flags[0], previous_openai_credential_valid=flags[1],
                                      owner_authorized=flags[2])
