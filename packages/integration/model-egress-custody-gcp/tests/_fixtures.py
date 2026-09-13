"""Shapes the tests build on. Nothing here designates anything: every value is an
invented shape for a negative or positive path, and no value is a credential."""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from uuid import UUID

from ugence_model_egress_custody_gcp import (
    AccessedSecretVersion, CustodyConfig, RuntimeIdentityAssertion)
from ugence_model_egress_unit import CredentialRequest, canonical_digest

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
TENANT = UUID("11111111-1111-1111-1111-111111111111")
REQUEST_ID = UUID("22222222-2222-2222-2222-222222222222")

PROJECT = "ugence-meu-nonprod-4821"
SA = f"projects/{PROJECT}/serviceAccounts/meu-runtime@{PROJECT}.iam.gserviceaccount.com"
RESOURCE = f"projects/{PROJECT}/secrets/meu-openai-validation/versions/3"
ATTESTED_BY = "Priya Raman — independent reviewer"
DIGEST = canonical_digest("ugence.test/designation/v1", "Designation", {"shape": "only"})

#: A payload shaped like a provider answer but loudly not one.
FAKE_PAYLOAD = "MARKER-FAKE-CUSTODY-PAYLOAD-NOT-A-KEY"


def identity(**over) -> RuntimeIdentityAssertion:
    kwargs = dict(source="attached_service_account", service_account_resource=SA,
                  designated_service_account=SA, designation_attested_by=ATTESTED_BY,
                  designation_record_digest=DIGEST)
    kwargs.update(over)
    return RuntimeIdentityAssertion(**kwargs)


def config(**over) -> CustodyConfig:
    kwargs = dict(custody_authority_id="gsm-meu-nonprod", credential_profile="openai-validation",
                  vendor="openai", secret_version_resource=RESOURCE, identity=identity())
    kwargs.update(over)
    return CustodyConfig(**kwargs)


def designation(**over) -> dict:
    """A COMPLETE, attested step-8 record shape. Designates nothing: every value is an
    invented shape, and the canonical record beside the unit is untouched by this."""

    obligations = {
        "gcp_project_id": PROJECT,
        "gcp_project_number": "000000000000",
        "meu_gcp_service_account_resource_name": SA,
        "deployment_platform_identity_mechanism": "native_gcp_workload_identity",
        "wif_pool_provider_and_constrained_principal_binding_or_native_gcp_equivalent":
            f"native: {SA} attached to the designated Cloud Run Job",
        "full_numeric_secret_manager_version_resource": RESOURCE,
        "secret_level_iam_policy_evidence_reference": "evidence://iam/meu-openai-validation/2026-09-13",
        "data_access_audit_log_configuration_and_retention_reference": "evidence://audit/secretmanager/2026-09-13",
        "approved_rotation_runbook_reference": "runbook://meu-openai-rotation/v1-approved",
        "openai_organization_id": "org-a1b2c3d4e5",
        "openai_project_id": "proj_f6g7h8i9j0",
        "openai_project_service_account_id": "svc-acct-meu-validation-01",
        "openai_role_and_api_key_scope_evidence": "evidence://openai/role-and-key-scope/2026-09-13",
        "vendor_spend_control_evidence_and_hard_stop_or_advisory_classification":
            "evidence://openai/spend-control/2026-09-13 (advisory)",
        "designated_model_availability_evidence": "evidence://openai/models/availability/2026-09-13",
        "applicable_data_processing_terms_reference": "evidence://openai/dpa/2026-09-13",
        "approved_processing_or_data_residency_region": "us",
    }
    record = {"obligation_count": 17, "checked_fields": 23, "obligations": obligations,
              "attestation": {"independently_checked_by": ATTESTED_BY,
                              "environment": "non-production"}}
    for key, value in over.items():
        if key == "obligations":
            record["obligations"] = {**obligations, **value}
        else:
            record[key] = value
    return copy.deepcopy(record)


def request(**over) -> CredentialRequest:
    kwargs = dict(request_id=REQUEST_ID, tenant_id=TENANT, vendor="openai",
                  credential_profile="openai-validation", requested_at=NOW)
    kwargs.update(over)
    return CredentialRequest(**kwargs)


class FakeClient:
    """One permitted call and a record of what it was asked. Any other attribute access
    is an error, which is how a test proves nothing lists secrets or versions."""

    def __init__(self, *, payload: bytes = FAKE_PAYLOAD.encode("utf-8"), name: str = RESOURCE,
                 raises: BaseException = None, answer=None) -> None:
        self._payload = payload
        self._name = name
        self._raises = raises
        self._answer = answer
        self.calls: list = []

    def access_secret_version(self, *, name: str):
        self.calls.append(name)
        if self._raises is not None:
            raise self._raises
        if self._answer is not None:
            return self._answer
        return AccessedSecretVersion(name=self._name, payload=self._payload)

    def __getattr__(self, item):  # list_secrets, list_secret_versions, get_secret, …
        raise AssertionError(f"the adapter reached for {item!r}; only access_secret_version is permitted")
