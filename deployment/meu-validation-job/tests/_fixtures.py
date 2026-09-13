"""Shapes for the job's tests. Nothing here designates anything and no value is a
credential: the designation shape is invented, and the canonical records beside the unit
are copied read-only into a temporary directory so a test can never edit them."""

from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

PROJECT = "ugence-meu-nonprod-4821"
SA = f"projects/{PROJECT}/serviceAccounts/meu-runtime@{PROJECT}.iam.gserviceaccount.com"
RESOURCE = f"projects/{PROJECT}/secrets/meu-openai-validation/versions/3"
INSTANCE = f"cloud-run-job-execution://{PROJECT}/jobs/meu-validation/executions/run-0001"
ATTESTED_BY = "Priya Raman, independent reviewer"
DIGEST = "a" * 64

#: The canonical records in the CHECKOUT. Anchored on this test file so an installed
#: distribution under test still reads the repository's records, not site-packages.
RECORDS = pathlib.Path(__file__).resolve().parents[3] / "packages/integration/model-egress-unit"


def canonical_records() -> tuple:
    designation = json.loads((RECORDS / "MEU_LIVE_PROVIDER_DESIGNATION.json").read_text(encoding="utf-8"))
    validation = json.loads((RECORDS / "MEU_LIVE_VALIDATION.json").read_text(encoding="utf-8"))
    return designation, validation


def complete_designation() -> dict:
    """The canonical record with every obligation filled by an INVENTED shape and an
    attestation added. It designates nothing: it exists so the tests can exercise the
    path that comes after acceptance without touching the real record."""

    designation, _ = canonical_records()
    step8 = designation["step8_required_values"]
    step8["obligations"] = {
        "gcp_project_id": PROJECT,
        "gcp_project_number": "000000000000",
        "meu_gcp_service_account_resource_name": SA,
        "deployment_platform_identity_mechanism": "native_gcp_workload_identity",
        "wif_pool_provider_and_constrained_principal_binding_or_native_gcp_equivalent":
            f"native: {SA} attached to the designated Cloud Run Job",
        "full_numeric_secret_manager_version_resource": RESOURCE,
        "secret_level_iam_policy_evidence_reference": "evidence://iam/2026-09-13",
        "data_access_audit_log_configuration_and_retention_reference": "evidence://audit/2026-09-13",
        "approved_rotation_runbook_reference": "runbook://meu-openai-rotation/v1-approved",
        "openai_organization_id": "org-a1b2c3d4e5",
        "openai_project_id": "proj_f6g7h8i9j0",
        "openai_project_service_account_id": "svc-acct-meu-validation-01",
        "openai_role_and_api_key_scope_evidence": "evidence://openai/role-and-scope/2026-09-13",
        "vendor_spend_control_evidence_and_hard_stop_or_advisory_classification":
            "evidence://openai/spend-control/2026-09-13 (advisory)",
        "designated_model_availability_evidence": "evidence://openai/availability/2026-09-13",
        "applicable_data_processing_terms_reference": "evidence://openai/dpa/2026-09-13",
        "approved_processing_or_data_residency_region": "us",
    }
    step8["attestation"] = {"independently_checked_by": ATTESTED_BY, "environment": "non-production"}
    return designation


def write_records(tmp_path: pathlib.Path, *, designation=None, validation=None) -> tuple:
    designation_doc, validation_doc = canonical_records()
    designation_doc = designation if designation is not None else designation_doc
    validation_doc = validation if validation is not None else validation_doc
    d = tmp_path / "MEU_LIVE_PROVIDER_DESIGNATION.json"
    v = tmp_path / "MEU_LIVE_VALIDATION.json"
    d.write_text(json.dumps(designation_doc), encoding="utf-8")
    v.write_text(json.dumps(validation_doc), encoding="utf-8")
    return d, v


def config_mapping(tmp_path: pathlib.Path, **over) -> dict:
    d, v = write_records(tmp_path, designation=over.pop("designation", None),
                         validation=over.pop("validation", None))
    mapping = {
        "schema": "meu-validation-job.config.v1",
        "mode": "offline",
        "environment": "non-production",
        "instance_reference": INSTANCE,
        "workload_identity_principal": SA,
        "designation_record_path": str(d),
        "validation_record_path": str(v),
        "authorization_record_path": "",
        "endpoint": "https://api.openai.com/v1/responses",
        "report_path": str(tmp_path / "report.json"),
        "custody": {
            "custody_authority_id": "gsm-meu-nonprod",
            "credential_profile": "openai-validation",
            "vendor": "openai",
            "secret_version_resource": RESOURCE,
            "environment": "non-production",
            "identity": {
                "source": "attached_service_account",
                "service_account_resource": SA,
                "designated_service_account": SA,
                "designation_attested_by": ATTESTED_BY,
                "designation_record_digest": DIGEST,
            },
        },
    }
    for key, value in over.items():
        if key == "custody" and isinstance(value, dict):
            mapping["custody"] = {**mapping["custody"], **value}
        else:
            mapping[key] = value
    return mapping


def write_config(tmp_path: pathlib.Path, **over) -> pathlib.Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config_mapping(tmp_path, **over)), encoding="utf-8")
    return path


class FakeClient:
    """Injected wherever a Secret Manager client is needed. Never reaches Google."""

    def __init__(self, payload: bytes = b"MARKER-FAKE-JOB-PAYLOAD-NOT-A-KEY") -> None:
        self._payload = payload
        self.calls: list = []

    def access_secret_version(self, *, name: str):
        from ugence_model_egress_custody_gcp import AccessedSecretVersion
        self.calls.append(name)
        return AccessedSecretVersion(name=name, payload=self._payload)


def authorization_record(**over) -> dict:
    """A VALID authorization shape, for exercising the path after the owner issues one.

    It authorizes nothing real: the owner's authorization is the one whose digest the
    canonical record pins, and the canonical record pins NOT_GIVEN. This is a test
    double that satisfies the type, exactly as the harness's fake transport satisfies
    the provider protocol.
    """

    from ugence_model_egress_provider_openai import DESIGNATED_MODEL
    record = {
        "schema": "model-egress-unit.live-synthetic-validation-authorization.v1",
        "authorization_id": "auth-meu-validation-0001",
        "nonce": "nonce-" + "0123456789abcdef",
        "authorizing_owner": "Rakesh Mohan — Founder, Ugence Labs",
        "authority_reference": "acceptance://meu/live-synthetic-validation/2026-09-13",
        "issued_at": "2026-09-13T00:00:00+00:00",
        "expires_at": "2026-09-20T00:00:00+00:00",
        "environment": "NON_PRODUCTION",
        "openai_organization_id": "org-a1b2c3d4e5",
        "openai_project_id": "proj_f6g7h8i9j0",
        "openai_service_account_id": "svc-acct-meu-validation-01",
        "provider": "openai",
        "model": DESIGNATED_MODEL,
        "endpoint": "https://api.openai.com/v1/responses",
        "designation_record_digest": "b" * 64,
        "validation_plan_digest": "c" * 64,
        "authorized_request_digests": ["d" * 64],
        "synthetic_non_sensitive_only": True,
        "max_calls": 1,
        "max_input_tokens": 512,
        "max_output_tokens": 128,
        "budget_usd_cents": 100,
        "concurrency": 1,
        "max_retries": 0,
    }
    record.update(over)
    return record


def pinned_validation_record(authorization: dict) -> dict:
    """The canonical validation record with THIS authorization's digest pinned, in a
    temporary copy. The record beside the unit is never edited."""

    from ugence_model_egress_unit import LiveSyntheticValidationAuthorization
    _, validation = canonical_records()
    validation["live_synthetic_validation_authorization"] = \
        LiveSyntheticValidationAuthorization.from_record(authorization).digest()
    return validation
