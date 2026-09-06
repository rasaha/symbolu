"""Strict request models for the additive ``governance_studio.api.v2`` contract (GAS-4).

Same discipline as v1: every model forbids unknown fields, no field accepts a
filesystem path, code, or policy script, and artifacts are carried as JSON objects
validated by the owning package's own models inside the service.

Nothing here describes an authority act. There is no issue, activate, revoke, grant,
authorize, clear or execute request in this module, and ``test_v2_operation_ids.py``
asserts the same of every route built from it.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from .envelope import StrictModel


# --------------------------------------------------------------------------- #
# Constitution
# --------------------------------------------------------------------------- #
class ConstitutionValidateRequest(StrictModel):
    """Structural validation of a constitution document. Mutation-free."""

    constitution: Dict[str, Any]


class ConstitutionPreflightRequest(StrictModel):
    """Dry-run every pre-signing check.

    ``preflight_issuance`` is documented as mutation-free, which is exactly why it is
    the only activation entry point the studio may reach (SD-2): it reports what
    issuance *would* find without performing it.
    """

    constitution: Dict[str, Any]
    record_id: str
    approval_reference: Optional[str] = None
    expected_reference_tenant_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Policy
# --------------------------------------------------------------------------- #
class PolicyPackRequest(StrictModel):
    """A policy pack as authored on the canvas, carried as a JSON object."""

    pack: Dict[str, Any]


class PolicyCompileRequest(StrictModel):
    """Compile a reviewed pack.

    ``approval`` is required and is never defaulted: the compiler's
    ``require_approval`` defaults to True and the studio never overrides it.
    """

    pack: Dict[str, Any]
    approval: Dict[str, Any]


# --------------------------------------------------------------------------- #
# Simulate
# --------------------------------------------------------------------------- #
class SimulateRunRequest(StrictModel):
    """Run a workflow against fixtures, recording every governance decision.

    ``execution_mode`` is constrained to the non-mutating modes. LIVE is not a member
    of the accepted set and cannot be requested.
    """

    workflow: Dict[str, Any]
    execution_mode: str = "DRY_RUN"
    max_quanta: int = 16
    correlation_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Publish
# --------------------------------------------------------------------------- #
class PublishShadowRequest(StrictModel):
    """Hand a compiled release package to the console's SHADOW governed loop.

    There is no non-shadow variant of this request, by construction.
    """

    compiled_package: Dict[str, Any]
    scenario_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# Review (GAS-7, HR-D)
# --------------------------------------------------------------------------- #
class ReviewDecisionRequest(StrictModel):
    """A human's decision on a parked proposal, relayed verbatim (HR-1).

    ``decision`` is the human's word — GRANT or REJECT — and the studio forwards it as
    typed. ``presented_approver`` is the approver reference the review service listed
    as eligible; the studio holds no identity of its own and proves none, which is why
    the review service labels every decision ``PRESENTED_UNPROVEN``. ``justification``
    is required: a decision without one is not relayed.
    """

    approval_id: str = Field(min_length=1)
    decision: Literal["GRANT", "REJECT"]
    presented_approver: Dict[str, Any]
    justification: str = Field(min_length=1)


class ReviewStartShadowRunRequest(StrictModel):
    """Ask the governed runtime worker to start its own shadow run (front-door seam 6,
    FD-10.2), relayed as typed (FD-10.1).

    The one field is the operator's correlation id, a typed token, or nothing. No
    workflow, task, provider, mode or definition digest can be carried here, by
    construction (FD-10.3): the worker holds the definition and its own digest binds
    the run, and the mode word the studio sends is pinned to ``shadow`` in the client.
    """

    correlation_id: Optional[str] = Field(
        default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


# --------------------------------------------------------------------------- #
# Registration (front-door seam 5, FD-9)
# --------------------------------------------------------------------------- #
class RegistryBindingInput(StrictModel):
    """The exact system and configuration a registration is about, as typed fields.

    No ``tenant_id``: the tenant is the deployment's and is never caller-supplied.
    The two required digests are lowercase sha-256 hex the administrator asserts; the
    studio computes none of them.
    """

    binding_id: str
    subject_id: str
    context_id: str
    context_digest: str
    system_id: str
    system_version: str
    configuration_id: str
    configuration_digest: str
    canonical_subject_context_ref: str = ""
    system_manifest_ref: str = ""
    system_manifest_digest: str = ""
    deployment_environment_ref: str = ""


class RegistryValidityInput(StrictModel):
    """The registration window, as ISO-8601 instants with a timezone."""

    issued_at: str
    expires_at: Optional[str] = None
    stale_after: Optional[str] = None


class RegistryRegisterRequest(StrictModel):
    """Register one system for this deployment's tenant (typed intake only, FD-4).

    No ``registration_id`` (derived by the package, never chosen), no ``tenant_id``
    (the deployment's), no ``registered_by`` (the deployment's name and version). The
    ``owner_ref`` is an opaque handle recorded as presented and unproven (FD-9.3); the
    ``classification_label`` is recorded uninterpreted (registry ADR D-2).
    """

    binding: RegistryBindingInput
    owner_ref: str
    classification_label: str
    validity: RegistryValidityInput
    supersedes: str = ""
    notes: str = ""


# --------------------------------------------------------------------------- #
# Data-use declarations (front-door seam 8, FD-12)
# --------------------------------------------------------------------------- #
class DeclarationBindingInput(StrictModel):
    """The exact system and configuration a declaration is about, as typed fields.

    No ``tenant_id``: the tenant is the deployment's and is never caller-supplied.
    The two required digests are lowercase sha-256 hex the declarer asserts; the
    studio computes none of them.
    """

    binding_id: str
    subject_id: str
    context_id: str
    context_digest: str
    system_id: str
    system_version: str
    configuration_id: str
    configuration_digest: str
    deployment_environment_ref: str = ""


class DeclarationValidityInput(StrictModel):
    """The declaration window, as ISO-8601 instants with a timezone."""

    issued_at: str
    expires_at: Optional[str] = None
    stale_after: Optional[str] = None


class DataUseDeclareRequest(StrictModel):
    """Declare one data use for this deployment's tenant (typed intake only, FD-4).

    No ``declaration_id`` (derived by the package, never chosen) and no ``tenant_id``
    (the deployment's). ``data_ref`` is an opaque, non-secret reference — never the
    data, and there is no field that could carry it. ``classification_label``,
    ``purpose_label`` and ``residency_label`` are recorded uninterpreted (DE-2, DE-3),
    and ``declared_by`` is an opaque handle recorded as presented and unproven
    (FD-12.3). Nothing here restricts egress: FD-12.5 invents no restriction for the
    absent egress package.
    """

    binding: DeclarationBindingInput
    data_ref: str
    classification_label: str
    purpose_label: str
    validity: DeclarationValidityInput
    residency_label: str = ""
    supersedes: str = ""
    declared_by: str = ""
    correlation_id: str = ""
    notes: str = ""


# --------------------------------------------------------------------------- #
# Vendor dependencies (front-door seam 9, FD-13)
# --------------------------------------------------------------------------- #
class VendorBindingInput(StrictModel):
    """The exact system and configuration a vendor declaration is about.

    No ``tenant_id``: the tenant is the deployment's and is never caller-supplied.
    The two required digests are lowercase sha-256 hex the declarer asserts; the
    studio computes none of them.
    """

    binding_id: str
    subject_id: str
    context_id: str
    context_digest: str
    system_id: str
    system_version: str
    configuration_id: str
    configuration_digest: str
    deployment_environment_ref: str = ""


class VendorValidityInput(StrictModel):
    """The declaration window, as ISO-8601 instants with a timezone."""

    issued_at: str
    expires_at: Optional[str] = None
    stale_after: Optional[str] = None


class VendorDeclareRequest(StrictModel):
    """Declare one vendor dependency for this deployment's tenant (typed intake, FD-4).

    No ``declaration_id`` (derived by the package, never chosen) and no ``tenant_id``
    (the deployment's). ``vendor_ref`` is an opaque, non-secret reference — never an
    address, endpoint or credential, and there is no field that could carry one.
    ``risk_posture_label`` is recorded uninterpreted (VR-3, FD-13.4): nothing orders,
    compares, ranks or scores it, and there is no field for an approval, onboarding
    status, tier or certification because no package computes one. ``policy_ref`` is
    recorded and never resolved (VR-4), and ``declared_by`` is an opaque handle
    recorded as presented and unproven (FD-12.3, carried forward by FD-13.2).
    """

    binding: VendorBindingInput
    vendor_ref: str
    risk_posture_label: str
    policy_ref: str
    validity: VendorValidityInput
    supersedes: str = ""
    declared_by: str = ""
    correlation_id: str = ""
    notes: str = ""
