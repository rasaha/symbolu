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
from typing import Mapping, Optional, Sequence, Tuple, Union

from .custody import is_pinned_secret_version

__all__ = [
    "STEP8_OBLIGATIONS",
    "STEP8_OBLIGATION_COUNT",
    "STEP8_DERIVED_SUBFIELDS",
    "STEP8_ATTESTATION_FIELDS",
    "STEP8_REQUIRED_VALUES",
    "step8_field_counts",
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
    "LIVE_VALIDATION_EXECUTION_POSTURE",
    "FORBIDDEN_CREDENTIAL_HOLDERS",
    "CI_ENVIRONMENT_MARKERS",
    "PRODUCTION_FORM_CUSTODY_ADAPTER",
    "NON_PRODUCTION_VALIDATION_OUTCOME_SCOPE",
    "ExecutionPostureRefused",
    "ExecutionPosture",
    "check_execution_posture",
    "ci_environment_markers_present",
    "sequence_complete",
]

#: Ruling 12: exactly SEVENTEEN mandatory designation obligations, in the owner's order
#: and words, each mapped to the checked field or structured group that represents it.
#: An obligation may be represented by more than one typed field (obligation 14 is two);
#: the count of obligations is seventeen and nothing here adds an eighteenth.
STEP8_OBLIGATIONS: Tuple[Tuple[int, str, Tuple[str, ...]], ...] = (
    (1, "GCP project ID", ("gcp_project_id",)),
    (2, "GCP project number", ("gcp_project_number",)),
    (3, "MEU GCP service-account resource name", ("meu_service_account",)),
    (4, "deployment-platform identity mechanism", ("deployment_platform_identity_mechanism",)),
    (5, "WIF pool/provider and constrained principal binding, or the documented native GCP equivalent",
     ("workload_identity_binding",)),
    (6, "full numeric Secret Manager version resource", ("secret_version",)),
    (7, "secret-level IAM-policy evidence reference", ("iam_policy_evidence_ref",)),
    (8, "Data Access audit-log configuration and retention reference", ("audit_log_config_and_retention_ref",)),
    (9, "approved rotation-runbook reference", ("rotation_runbook_ref",)),
    (10, "OpenAI organization ID", ("openai_organization_id",)),
    (11, "OpenAI project ID", ("openai_project_id",)),
    (12, "OpenAI project service-account ID", ("openai_service_account_id",)),
    (13, "OpenAI role and API-key scope evidence", ("openai_role_and_key_scope_evidence_ref",)),
    (14, "vendor spend-control evidence and hard-stop/advisory classification",
     ("vendor_spend_control_evidence_ref", "vendor_spend_control_classification")),
    (15, "designated-model availability evidence", ("model_availability_evidence_ref",)),
    (16, "applicable data-processing-terms reference", ("data_processing_terms_ref",)),
    (17, "approved processing/data-residency region", ("processing_region",)),
)
STEP8_OBLIGATION_COUNT = len(STEP8_OBLIGATIONS)  # 17, by LP-7 ruling 12

#: Typed subfields the checker derives from an obligation's text and validates beside it
#: (they are not obligations): the IAM binding is on the secret (obligation 7, ruling 4);
#: the key scope is exactly api.responses.write (obligation 13, ruling 7).
STEP8_DERIVED_SUBFIELDS: Tuple[str, ...] = ("iam_binding_scope", "openai_key_scope")

#: Attestation and scoping fields the record must carry (not obligations): the rulings
#: govern the non-production commissioning only; every value is independently checked.
STEP8_ATTESTATION_FIELDS: Tuple[str, ...] = ("environment", "verified_by", "verified_at")

#: The obligation-bearing fields, in the owner's order: seventeen obligations represented
#: by eighteen fields (obligation 14 decomposed). Kept as the checker's iteration order.
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


def step8_field_counts() -> dict:
    """The obligation count and the checked-field count, from the definitions themselves.

    ``obligations`` is seventeen (LP-7 ruling 12). ``checked_fields`` is every top-level
    field of :class:`Step8Designation` the checker validates: the obligation-bearing
    fields, the derived subfields and the attestation fields. The identity-binding group
    carries further typed subfields inside its own record, counted separately.
    """

    obligation_fields = tuple(f for _, _, names in STEP8_OBLIGATIONS for f in names)
    assert obligation_fields == STEP8_REQUIRED_VALUES, "the obligation map and the field order disagree"
    top = tuple(f.name for f in fields(Step8Designation))
    assert set(top) == set(STEP8_REQUIRED_VALUES) | set(STEP8_DERIVED_SUBFIELDS) | set(STEP8_ATTESTATION_FIELDS)
    return {
        "obligations": STEP8_OBLIGATION_COUNT,
        "checked_fields": len(top),
        "obligation_bearing_fields": len(STEP8_REQUIRED_VALUES),
        "derived_subfields": len(STEP8_DERIVED_SUBFIELDS),
        "attestation_fields": len(STEP8_ATTESTATION_FIELDS),
        "identity_binding_subfields": {"workload_identity_federation": len(fields(WorkloadIdentityFederation)),
                                       "native_gcp_workload_identity": len(fields(NativeGcpWorkloadIdentity))},
        "statement": (f"{STEP8_OBLIGATION_COUNT} mandatory designation obligations represented by "
                      f"{len(top)} checked fields"),
    }


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


# --- LP-8 (2026-09-12): where the credential may be possessed and exercised -----------

#: LP-8: the initial genuine-provider validation runs through a DEPLOYED MEU instance in
#: the dedicated non-production GCP project, under the instance's dedicated non-human
#: workload identity. Nothing else may possess or exercise the credential.
LIVE_VALIDATION_EXECUTION_POSTURE = "DEPLOYED_MEU_INSTANCE"

#: LP-8, in the owner's words and order: none of these may possess or exercise the
#: credential. A posture naming one of them is refused, and so is a claimed
#: DEPLOYED_MEU_INSTANCE posture presented from inside a CI runner.
FORBIDDEN_CREDENTIAL_HOLDERS: Tuple[str, ...] = (
    "DEVELOPER_MACHINE",
    "CI_RUNNER",
    "BROWSER",
    "SHARED_HOSTING_ENVIRONMENT",
    "PRODUCTION_BUSINESS_WORKFLOW",
)

#: Environment variables that CI systems set on their runners. Any one present means the
#: process is a CI runner whatever posture it claims; the live verifier refuses before
#: touching anything. Offline fake-transport testing is what runs in CI (LP-8).
CI_ENVIRONMENT_MARKERS: Tuple[str, ...] = (
    "CI", "GITHUB_ACTIONS", "GITLAB_CI", "BUILDKITE", "CIRCLECI", "TRAVIS", "TF_BUILD",
    "JENKINS_URL", "TEAMCITY_VERSION", "BITBUCKET_BUILD_NUMBER", "CODEBUILD_BUILD_ID",
    "CLOUD_BUILD", "DRONE",
)

#: LP-8: the validation uses the production-form Secret Manager custody adapter over a
#: pinned numeric version. The reference adapter and the fake-path
#: ``PinnedSecretVersionCustodyAdapter`` over an injected reader never satisfy it.
PRODUCTION_FORM_CUSTODY_ADAPTER = "PRODUCTION_FORM_SECRET_MANAGER_ADAPTER"

#: LP-8, last sentence: what a successful non-production validation is evidence for, and
#: what it is not.
NON_PRODUCTION_VALIDATION_OUTCOME_SCOPE = (
    "evidence toward the owner's MET decision for the NON-PRODUCTION commissioning record only; "
    "authorizes no production commissioning, which needs its own commissioning record"
)


class ExecutionPostureRefused(RuntimeError):
    """An execution posture under which the credential may not be possessed or
    exercised (LP-8). The message names the field and the rule, never the value."""

    def __init__(self, field_name: str, detail: str) -> None:
        super().__init__(f"{field_name}: {detail}")
        self.field_name = field_name


@dataclass(frozen=True)
class ExecutionPosture:
    """Where the live validation is about to execute, as the executing process asserts
    it. Accepted only when it is the deployed MEU instance, under its non-human workload
    identity, through the production-form custody adapter, in a non-production
    environment, and not inside a CI runner."""

    posture: str
    instance_reference: str
    workload_identity_principal: str
    custody_adapter: str
    environment: str = "non-production"


def ci_environment_markers_present(variables: Mapping[str, str]) -> Tuple[str, ...]:
    """The CI markers set in ``variables``, in :data:`CI_ENVIRONMENT_MARKERS` order.
    Non-empty means: the process those variables describe is a CI runner. This unit
    never reads its own process environment (the boundary tests forbid it); the caller
    that may, the validation command, passes the marker names' values in."""

    return tuple(m for m in CI_ENVIRONMENT_MARKERS if str(variables.get(m, "")).strip() not in ("", "0", "false", "False"))


def check_execution_posture(posture: ExecutionPosture, *, variables: Mapping[str, str]) -> ExecutionPosture:
    """``posture`` back, or :class:`ExecutionPostureRefused` naming the first rule broken.

    Order: a CI runner is refused first, whatever it claims; then a posture that is not
    the deployed MEU instance (each forbidden holder is named as itself); then the
    instance reference and the workload-identity principal (required, no placeholder, no
    credential shape, not a human or default-compute identity); then the custody adapter
    (production-form only); then the environment (non-production only).
    """

    markers = ci_environment_markers_present(variables)
    if markers:
        raise ExecutionPostureRefused(
            "environment", f"a CI runner ({', '.join(markers)} set) may not possess or exercise the credential; "
                           "offline fake-transport testing is what runs in CI (LP-8)")
    if not isinstance(posture, ExecutionPosture):
        raise ExecutionPostureRefused("posture", "an ExecutionPosture record is required; a string or a flag asserts nothing (LP-8)")
    if posture.posture in FORBIDDEN_CREDENTIAL_HOLDERS:
        raise ExecutionPostureRefused("posture", f"{posture.posture} may not possess or exercise the credential (LP-8)")
    if posture.posture != LIVE_VALIDATION_EXECUTION_POSTURE:
        raise ExecutionPostureRefused("posture", f"only {LIVE_VALIDATION_EXECUTION_POSTURE} may execute the validation (LP-8)")
    for name in ("instance_reference", "workload_identity_principal"):
        try:
            _refuse_bad_string(name, getattr(posture, name))
        except DesignationRefused as refused:
            raise ExecutionPostureRefused(name, str(refused).split(": ", 1)[1]) from None
    principal = posture.workload_identity_principal
    lowered = principal.lower()
    if lowered.startswith("user:") or "@gmail." in lowered or "@googlemail." in lowered or "-compute@" in lowered \
            or lowered.endswith("developer.gserviceaccount.com"):
        raise ExecutionPostureRefused("workload_identity_principal", "a human or default-compute identity is not the dedicated non-human workload identity (LP-8, ruling 2)")
    if not (lowered.startswith("principal://") or lowered.startswith("principalset://") or lowered.startswith("serviceaccount:")
            or ".iam.gserviceaccount.com" in lowered):
        raise ExecutionPostureRefused("workload_identity_principal", "must be the instance's workload-identity principal or its service-account identity (LP-8)")
    if posture.custody_adapter != PRODUCTION_FORM_CUSTODY_ADAPTER:
        raise ExecutionPostureRefused("custody_adapter", f"only {PRODUCTION_FORM_CUSTODY_ADAPTER} may materialize the credential for the validation; the reference and fake-path adapters never satisfy row 12 (LP-8)")
    if str(posture.environment).strip().lower() != "non-production":
        raise ExecutionPostureRefused("environment", "the initial validation is non-production only; production is another commissioning record (LP-8)")
    return posture


def sequence_complete(calls_consumed: int, max_calls: int) -> bool:
    """LP-8: the validation exercises EXACTLY the separately authorized number of live
    calls. Fewer is an incomplete validation; more is impossible, because the durable
    ledger refuses the call after ``max_calls``. Only equality completes the sequence."""

    return type(calls_consumed) is int and type(max_calls) is int and 1 <= max_calls and calls_consumed == max_calls
