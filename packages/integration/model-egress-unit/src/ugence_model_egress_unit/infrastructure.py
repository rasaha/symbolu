"""LP-7 / step 8 (non-production): the shape of the seventeen designations, and the refusals.

The owner's design rulings of 2026-09-11 (``ADR_UGENCE_LIVE_MODEL_PROVIDER_COMMISSIONING.md``
§0.4) supply no value. This module supplies the *checks* a value must pass before the
record beside the package may carry it: every one of the seventeen is required; none may
be a placeholder, an alias, a secret-shaped string, a human or default-compute identity,
a project-level binding, a key scope wider than ``api.responses.write``, or a value
inferred from another; the record must say ``non-production`` and name who checked it
independently and when. The commissioning status is not touched here. Accepting a
designation closes only the infrastructure-designation blocker (ruling 12): it admits
neither a live call nor a genuine result.

Nothing here reaches Google Cloud or OpenAI. It is string validation over a record, and
a refusal never echoes the refused value, so a secret pasted into the wrong field is
refused without being repeated.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from typing import Optional, Sequence, Tuple, Union

from .custody import is_pinned_secret_version

__all__ = [
    "STEP8_REQUIRED_VALUES",
    "PLACEHOLDER_MARKERS",
    "CREDENTIAL_SHAPE_PREFIXES",
    "OPENAI_KEY_SCOPE",
    "SPEND_CONTROL_CLASSIFICATIONS",
    "IDENTITY_MECHANISMS",
    "MAX_ROTATION_INTERVAL",
    "looks_like_a_credential",
    "DesignationRefused",
    "WorkloadIdentityFederation",
    "NativeGcpWorkloadIdentity",
    "Step8Designation",
    "check_step8_designation",
    "ROTATION_SEQUENCE",
    "RotationRefused",
    "check_rotation_plan",
    "rollback_permitted",
]

#: Ruling 12, in the owner's order and words, as record fields. Seventeen values; the
#: fourteenth (spend-control evidence and classification) is two fields.
STEP8_REQUIRED_VALUES: Tuple[str, ...] = (
    "gcp_project_id",
    "gcp_project_number",
    "meu_service_account",
    "deployment_platform_identity_mechanism",
    "workload_identity_binding",
    "secret_version",
    "iam_policy_evidence_ref",
    "audit_log_config_and_retention_ref",
    "rotation_runbook_ref",
    "openai_organization_id",
    "openai_project_id",
    "openai_service_account_id",
    "openai_role_and_key_scope_evidence_ref",
    "vendor_spend_control_evidence_ref",
    "vendor_spend_control_classification",
    "model_availability_evidence_ref",
    "data_processing_terms_ref",
    "processing_region",
)

#: Tokens that mark a value as not a value. Case-insensitive substring match.
PLACEHOLDER_MARKERS: Tuple[str, ...] = (
    "undesignated", "todo", "tbd", "placeholder", "example", "sample", "changeme",
    "xxx", "<", ">", "{", "}", "your-", "dummy", "fake", "latest", "not-yet", "pending",
)

#: Ruling 3: a secret value, a reversible encoding or a verification digest is never a
#: field of the record. These prefixes are the shapes refused in ANY field; the refusal
#: names the field and never the value.
CREDENTIAL_SHAPE_PREFIXES: Tuple[str, ...] = (
    "sk-", "sk-proj-", "sk-svcacct-", "eyJ", "AIza", "ya29.", "AKIA", "-----BEGIN",
    "xoxb-", "ghp_", "gho_", "glpat-",
)

#: Ruling 7: the one capability the OpenAI role and key may carry.
OPENAI_KEY_SCOPE = "api.responses.write"

#: Ruling 9: the vendor spend control is recorded as what it is, never assumed a stop.
SPEND_CONTROL_CLASSIFICATIONS: Tuple[str, ...] = ("hard_stop", "advisory")

#: Ruling 2: the deployment platform's identity mechanism, one of two.
IDENTITY_MECHANISMS: Tuple[str, ...] = ("workload_identity_federation", "native_gcp_workload_identity")

#: Ruling 6: the maximum normal rotation interval, matching ``custody``.
MAX_ROTATION_INTERVAL = timedelta(days=90)


def looks_like_a_credential(value: str) -> bool:
    """Whether ``value`` has a known credential shape. Scans the whole string, so a
    secret embedded in a longer reference is caught too."""

    if not isinstance(value, str):
        return False
    for prefix in CREDENTIAL_SHAPE_PREFIXES:
        at = value.find(prefix)
        while at != -1:
            if prefix == "eyJ":
                # a JWT: three base64url segments joined by dots
                tail = value[at:]
                parts = tail.split(".")
                if len(parts) >= 3 and all(len(p) >= 8 for p in parts[:3]):
                    return True
            elif prefix == "-----BEGIN":
                if "PRIVATE KEY" in value[at:at + 40].upper():
                    return True
            else:
                rest = value[at + len(prefix):]
                token = "".join(c for c in rest[:48] if c.isalnum() or c in "-_")
                if len(token) >= 8 and (at == 0 or not value[at - 1].isalnum()):
                    return True
            at = value.find(prefix, at + 1)
    return False


class DesignationRefused(ValueError):
    """A step-8 record that may not be accepted, and the first reason why. The
    message names the field and the rule; it never repeats the value."""

    def __init__(self, field_name: str, detail: str) -> None:
        super().__init__(f"{field_name}: {detail}")
        self.field_name = field_name


@dataclass(frozen=True)
class WorkloadIdentityFederation:
    """Ruling 2, MEU outside Google Cloud: every element designated, none inferred."""

    oidc_issuer: str
    audience: str
    subject_constraints: str
    pool: str
    provider: str
    principal_binding: str

    mechanism = "workload_identity_federation"


@dataclass(frozen=True)
class NativeGcpWorkloadIdentity:
    """Ruling 2, MEU on Google Cloud: the native path and the no-static-key evidence."""

    path: str
    no_static_key_evidence_ref: str

    mechanism = "native_gcp_workload_identity"


WorkloadIdentityBinding = Union[WorkloadIdentityFederation, NativeGcpWorkloadIdentity]


@dataclass(frozen=True)
class Step8Designation:
    """The seventeen values of ruling 12, plus the derived scopes, the environment, and
    who checked the record independently and when."""

    gcp_project_id: str
    gcp_project_number: str
    meu_service_account: str
    deployment_platform_identity_mechanism: str
    workload_identity_binding: WorkloadIdentityBinding
    secret_version: str
    iam_policy_evidence_ref: str
    iam_binding_scope: str
    audit_log_config_and_retention_ref: str
    rotation_runbook_ref: str
    openai_organization_id: str
    openai_project_id: str
    openai_service_account_id: str
    openai_role_and_key_scope_evidence_ref: str
    openai_key_scope: str
    vendor_spend_control_evidence_ref: str
    vendor_spend_control_classification: str
    model_availability_evidence_ref: str
    data_processing_terms_ref: str
    processing_region: str
    environment: str
    verified_by: str
    verified_at: Optional[datetime]

    def as_record(self) -> dict:
        out = {}
        for f in fields(self):
            value = getattr(self, f.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, (WorkloadIdentityFederation, NativeGcpWorkloadIdentity)):
                value = {"mechanism": value.mechanism, **{g.name: getattr(value, g.name) for g in fields(value)}}
            out[f.name] = value
        return out


_STRING_FIELDS = tuple(n for n in STEP8_REQUIRED_VALUES if n != "workload_identity_binding") + (
    "iam_binding_scope", "openai_key_scope", "environment", "verified_by")


def _refuse_bad_string(field_name: str, value) -> None:
    if not isinstance(value, str) or not value.strip():
        raise DesignationRefused(field_name, "required; a designation with a value missing is not a designation (ruling 12)")
    if value != value.strip():
        raise DesignationRefused(field_name, "leading or trailing whitespace")
    if looks_like_a_credential(value):
        raise DesignationRefused(field_name, "carries a credential shape; no record holds a secret value, encoding or digest (ruling 3)")
    lowered = value.lower()
    for marker in PLACEHOLDER_MARKERS:
        if marker in lowered:
            raise DesignationRefused(field_name, f"placeholder or alias token {marker!r}; values are supplied, never synthesized (ruling 12)")


def _project_id_ok(project: str) -> bool:
    if not (6 <= len(project) <= 30) or not project[0].isalpha() or project.endswith("-"):
        return False
    return all(c.islower() or c.isdigit() or c == "-" for c in project)


def _service_account_problem(resource: str, project: str) -> Optional[str]:
    prefix = f"projects/{project}/serviceAccounts/"
    if not resource.startswith(prefix):
        return "must be projects/<project>/serviceAccounts/<email> in the designated project (ruling 2)"
    email = resource[len(prefix):]
    local, at, domain = email.partition("@")
    if not at or not local or not domain:
        return "the service-account email is malformed"
    if domain == "developer.gserviceaccount.com" or local.endswith("-compute"):
        return "the default compute identity is not permitted (ruling 2)"
    if domain != f"{project}.iam.gserviceaccount.com":
        return "not a service account of the designated project; a human identity or a foreign project is refused (ruling 2)"
    if email.endswith(".json") or "/" in email:
        return "a service-account key file is not an identity (ruling 2)"
    return None


def check_step8_designation(record: Step8Designation) -> Step8Designation:
    """The record, unchanged, or :class:`DesignationRefused` naming the first failure.

    Missing, padded, secret-shaped and placeholder values are reported before shape
    failures, and shape failures follow the owner's order of ruling 12.
    """

    for name in _STRING_FIELDS:
        _refuse_bad_string(name, getattr(record, name))
    if record.environment != "non-production":
        raise DesignationRefused("environment", "these rulings govern the first non-production commissioning only; a production designation is a separate record (LP-7 preamble, ruling 1)")
    if record.verified_at is None:
        raise DesignationRefused("verified_at", "each value must be independently checked before step 7's live verifier may run (rulings 11, 12)")
    if record.verified_at.tzinfo is None:
        raise DesignationRefused("verified_at", "must be timezone-aware")

    project = record.gcp_project_id
    if not _project_id_ok(project):
        raise DesignationRefused("gcp_project_id", "not a well-formed GCP project ID")
    if not record.gcp_project_number.isdigit():
        raise DesignationRefused("gcp_project_number", "a GCP project number is digits only")

    why = _service_account_problem(record.meu_service_account, project)
    if why is not None:
        raise DesignationRefused("meu_service_account", why)

    if record.deployment_platform_identity_mechanism not in IDENTITY_MECHANISMS:
        raise DesignationRefused("deployment_platform_identity_mechanism", f"one of {IDENTITY_MECHANISMS} (ruling 2)")
    binding = record.workload_identity_binding
    if not isinstance(binding, (WorkloadIdentityFederation, NativeGcpWorkloadIdentity)):
        raise DesignationRefused("workload_identity_binding", "a WorkloadIdentityFederation or NativeGcpWorkloadIdentity record (ruling 2)")
    if binding.mechanism != record.deployment_platform_identity_mechanism:
        raise DesignationRefused("workload_identity_binding", "does not match the declared identity mechanism (ruling 2)")
    for f in fields(binding):
        _refuse_bad_string(f"workload_identity_binding.{f.name}", getattr(binding, f.name))
    if isinstance(binding, WorkloadIdentityFederation):
        if not binding.oidc_issuer.startswith("https://"):
            raise DesignationRefused("workload_identity_binding.oidc_issuer", "an OIDC issuer is an https URL")
        if "/workloadIdentityPools/" not in binding.principal_binding or "/providers/" not in binding.provider and "/providers/" not in binding.principal_binding:
            raise DesignationRefused("workload_identity_binding.principal_binding", "must name the pool and provider it constrains (ruling 2)")
        if binding.principal_binding.rstrip("/").endswith("/*") or binding.principal_binding.endswith("/subject/*"):
            raise DesignationRefused("workload_identity_binding.principal_binding", "an unconstrained principal set is not an exact principal binding (ruling 2)")

    if not is_pinned_secret_version(record.secret_version):
        raise DesignationRefused("secret_version", "must be projects/<project>/secrets/<secret>/versions/<n> with a numeric version; latest and every non-numeric reference are prohibited (ruling 3)")
    if not (record.secret_version.startswith(f"projects/{project}/secrets/")
            or record.secret_version.startswith(f"projects/{record.gcp_project_number}/secrets/")):
        raise DesignationRefused("secret_version", "the secret must live in the designated project, by ID or number (ruling 3)")

    if record.iam_binding_scope != "secret":
        raise DesignationRefused("iam_binding_scope", "roles/secretmanager.secretAccessor is granted on the designated secret only, never with a project-level grant (ruling 4)")

    if not record.openai_organization_id.startswith("org-") or len(record.openai_organization_id) <= 4:
        raise DesignationRefused("openai_organization_id", "must be an OpenAI organization ID (org-…)")
    if not record.openai_project_id.startswith("proj_") or len(record.openai_project_id) <= 5:
        raise DesignationRefused("openai_project_id", "must be an OpenAI project ID (proj_…)")
    if record.openai_key_scope != OPENAI_KEY_SCOPE:
        raise DesignationRefused("openai_key_scope", f"the role and key carry exactly {OPENAI_KEY_SCOPE} and nothing else (ruling 7)")
    if record.vendor_spend_control_classification not in SPEND_CONTROL_CLASSIFICATIONS:
        raise DesignationRefused("vendor_spend_control_classification", f"one of {SPEND_CONTROL_CLASSIFICATIONS}; a vendor limit is recorded as what it is (ruling 9)")
    if record.model_availability_evidence_ref.strip().lower() in {"gpt-5.4-mini-2026-03-17", "gpt-5.4-mini"}:
        raise DesignationRefused("model_availability_evidence_ref", "recording the model name is not availability evidence (ruling 8)")
    return record


# --- ruling 6: rotation as an ordered sequence --------------------------------------

#: The only order a rotation may take, in the owner's eight steps. Revocation and
#: disabling come last; destruction is not in the sequence at all.
ROTATION_SEQUENCE: Tuple[str, ...] = (
    "create_new_openai_service_account_credential",
    "store_as_new_secret_manager_version",
    "designate_candidate_numeric_version",
    "offline_fake_transport_conformance",
    "authorize_controlled_validation_separately",
    "accept_and_activate_candidate_version",
    "verify_successful_operation",
    "revoke_superseded_credential_and_disable_version",
)

DESTRUCTION_STEP = "destroy_old_version_with_retained_evidence_and_authorization"


class RotationRefused(ValueError):
    """A rotation plan that is not the owner's sequence."""


def check_rotation_plan(steps: Sequence[str], *, initial_commissioning: bool = True) -> Tuple[str, ...]:
    """The plan, as a tuple, or :class:`RotationRefused`.

    A plan is accepted only if it is exactly :data:`ROTATION_SEQUENCE` or a prefix of it
    (a rotation may stop before activation; the previous version then stays active).
    :data:`DESTRUCTION_STEP` is refused during initial commissioning and, later, anywhere
    but after the complete sequence.
    """

    plan = tuple(steps)
    if not plan:
        raise RotationRefused("an empty plan rotates nothing")
    if DESTRUCTION_STEP in plan:
        if initial_commissioning:
            raise RotationRefused("no old version may be destroyed during initial commissioning (ruling 6)")
        if plan[:-1] != ROTATION_SEQUENCE or plan[-1] != DESTRUCTION_STEP:
            raise RotationRefused("destruction may follow only the complete sequence, with separately retained evidence and explicit authorization (ruling 6)")
        return plan
    if plan != ROTATION_SEQUENCE[:len(plan)]:
        raise RotationRefused(
            "rotation is: create the new project-scoped OpenAI service-account credential, store it as a "
            "new Secret Manager version, designate that numeric version as a candidate, run the offline "
            "fake-transport conformance checks, separately authorize a controlled validation, accept and "
            "activate the candidate, verify operation, and only then revoke the superseded credential and "
            "disable its version (ruling 6)")
    return plan


def rollback_permitted(*, previous_secret_version_valid: bool, previous_openai_credential_valid: bool,
                       owner_authorized: bool) -> bool:
    """Ruling 6: rollback to the preceding version only while both its Secret Manager
    version and its OpenAI credential remain valid, and the owner has authorized it."""

    return bool(previous_secret_version_valid and previous_openai_credential_valid and owner_authorized)
