"""Whether the step-8 designation record is complete, attested, and the one this
adapter is configured against.

LP-7 ruling 12 makes the seventeen obligations a precondition of any credential
materialization, and the attestation a separate requirement on top of them. This module
is where that precondition is *enforced* rather than assumed: the adapter refuses to
call Secret Manager at all until the record it was handed is complete, independently
verified, and names the same project, service account and secret version the adapter
is bound to.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ugence_model_egress_unit import STEP8_OBLIGATION_COUNT, looks_like_a_credential

from .resource import ResourceRefused, parse_secret_version

__all__ = ["DesignationRefused", "AcceptedDesignation", "check_designation_accepted"]

#: The obligation keys this adapter reads. The record carries all seventeen; these four
#: are the ones that must agree with the adapter's own configuration.
_PROJECT = "gcp_project_id"
_SERVICE_ACCOUNT = "meu_gcp_service_account_resource_name"
_SECRET_VERSION = "full_numeric_secret_manager_version_resource"
_MECHANISM = "deployment_platform_identity_mechanism"


class DesignationRefused(ValueError):
    """The designation record may not back a materialization yet, and why."""


@dataclass(frozen=True)
class AcceptedDesignation:
    """A complete, attested designation, reduced to what custody needs."""

    gcp_project_id: str
    service_account_resource: str
    secret_version_resource: str
    identity_mechanism: str
    attested_by: str


def check_designation_accepted(step8: Any) -> AcceptedDesignation:
    """``step8_required_values`` from ``MEU_LIVE_PROVIDER_DESIGNATION.json``, accepted.

    Refused when: the mapping is absent or misshapen; the obligation count is not
    seventeen; any obligation is missing, blank or still ``UNDESIGNATED``; any
    obligation carries a credential shape; or the independent verification is absent.
    """

    if not isinstance(step8, Mapping):
        raise DesignationRefused("a step8_required_values mapping is required")
    obligations = step8.get("obligations")
    if not isinstance(obligations, Mapping):
        raise DesignationRefused("the designation record carries no obligations mapping")
    if len(obligations) != STEP8_OBLIGATION_COUNT or step8.get("obligation_count") != STEP8_OBLIGATION_COUNT:
        raise DesignationRefused(
            f"the designation record must carry exactly {STEP8_OBLIGATION_COUNT} obligations "
            f"(LP-7 ruling 12); it carries {len(obligations)}")
    undesignated = sorted(k for k, v in obligations.items()
                          if not isinstance(v, str) or not v.strip() or v.strip().startswith("UNDESIGNATED"))
    if undesignated:
        raise DesignationRefused(
            f"{len(undesignated)} of {STEP8_OBLIGATION_COUNT} designation obligations are not supplied "
            f"({undesignated[0]} first); no credential is materialized until every one is (LP-7 ruling 12)")
    for key, value in obligations.items():
        if looks_like_a_credential(value):
            raise DesignationRefused(
                f"obligation {key} carries a credential shape; the designation record names references and "
                f"never a secret value, encoding or digest (LP-7 ruling 3)")
    attestation = step8.get("attestation")
    attested_by = ""
    if isinstance(attestation, Mapping):
        attested_by = str(attestation.get("independently_checked_by") or "").strip()
    if not attested_by:
        raise DesignationRefused(
            "the designation record records no independent verification; supplying the seventeen values is "
            "not the same as someone having checked them (LP-7 ruling 12)")
    if looks_like_a_credential(attested_by):
        raise DesignationRefused("the attestation field carries a credential shape")
    try:
        version = parse_secret_version(str(obligations[_SECRET_VERSION]))
    except ResourceRefused as refused:
        raise DesignationRefused(f"obligation {_SECRET_VERSION}: {refused}") from None
    project = str(obligations[_PROJECT]).strip()
    if version.project not in (project, str(obligations["gcp_project_number"]).strip()):
        raise DesignationRefused(
            f"obligation {_SECRET_VERSION} names a different project than {_PROJECT}; the secret lives in "
            f"the designated project and nowhere else (LP-7 ruling 1)")
    return AcceptedDesignation(
        gcp_project_id=project,
        service_account_resource=str(obligations[_SERVICE_ACCOUNT]).strip(),
        secret_version_resource=version.resource,
        identity_mechanism=str(obligations[_MECHANISM]).strip(),
        attested_by=attested_by,
    )
