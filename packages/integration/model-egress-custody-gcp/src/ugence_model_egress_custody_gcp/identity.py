"""Which runtime identity may back a production-authoritative lease, and why ADC may not.

The owner's identity clarification of 2026-09-13 (commissioning ADR §0.8) says: native
GCP workload identity attached to the designated Cloud Run Job is production-authoritative
and equivalent to WIF for this non-production commissioning path, while generic
application default credentials are not proof of that identity and never become
production-authoritative.

The distinction this module encodes: **how the process obtained a credential** is not
**which identity that credential is**. ADC is a search order. It finds an attached
service account on Cloud Run, a key file when one is pointed at, and a developer's own
user credential on a laptop, and the calling code cannot tell which from the fact that
ADC succeeded. So the operator declares the SOURCE explicitly, an attached service
account is the only Google-hosted source accepted, and the declared account must be the
exact designated one under an attested designation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ugence_model_egress_unit import CustodyIdentity, is_service_account_resource, looks_like_a_credential

__all__ = [
    "RUNTIME_IDENTITY_SOURCES",
    "PRODUCTION_FORM_IDENTITY_SOURCES",
    "IdentityRefused",
    "RuntimeIdentityAssertion",
    "check_production_identity",
]

#: Every way a process can come to hold Google credentials, as the operator declares it.
RUNTIME_IDENTITY_SOURCES: Tuple[str, ...] = (
    #: Cloud Run / GCE / GKE metadata: the identity is attached to the workload itself.
    "attached_service_account",
    #: An external identity exchanged for a Google one through a WIF pool.
    "workload_identity_federation",
    #: A search order, not an identity. Whatever it found is unverified here.
    "application_default_credentials",
    #: gcloud auth login. A human.
    "developer_credentials",
    #: A downloaded JSON key: itself a credential in the deployment (LP-2).
    "service_account_key_file",
    #: A Secret Manager emulator or any test double.
    "emulator",
)

#: The two sources that can be production-authoritative, each with further conditions.
PRODUCTION_FORM_IDENTITY_SOURCES: Tuple[str, ...] = ("attached_service_account",
                                                     "workload_identity_federation")

_SOURCE_TO_KIND = {
    "attached_service_account": "native_gcp_workload_identity",
    "workload_identity_federation": "workload_identity_federation",
    "application_default_credentials": "application_default_credentials",
    "developer_credentials": "application_default_credentials",
    "emulator": "fake_emulator",
}


class IdentityRefused(ValueError):
    """A runtime identity that may not back a production-authoritative lease."""


@dataclass(frozen=True)
class RuntimeIdentityAssertion:
    """What the operator declares about the process this adapter runs in.

    Identifiers and a digest only. No credential, no key file, no token: a field here
    that carried credential material would be refused by
    :func:`check_production_identity` before anything else happened.
    """

    #: One of :data:`RUNTIME_IDENTITY_SOURCES`.
    source: str
    #: The service account the workload runs as, as ``projects/<p>/serviceAccounts/<email>``.
    service_account_resource: str
    #: Step-8 obligation 3: the designated MEU service-account resource.
    designated_service_account: str = ""
    #: The step-8 attestation: who independently verified the designation record.
    designation_attested_by: str = ""
    #: The digest of the designation record that attestation covers.
    designation_record_digest: str = ""


def _refuse_material(assertion: RuntimeIdentityAssertion) -> Optional[str]:
    for name in ("source", "service_account_resource", "designated_service_account",
                 "designation_attested_by", "designation_record_digest"):
        value = getattr(assertion, name)
        if isinstance(value, str) and looks_like_a_credential(value):
            return (f"{name} carries a credential shape; an identity assertion names WHO the process is "
                    f"and never holds credential material")
    return None


def check_production_identity(assertion: RuntimeIdentityAssertion) -> CustodyIdentity:
    """The :class:`CustodyIdentity` this assertion proves, or :class:`IdentityRefused`.

    Every refusal names the rule. None repeats a value that carried a credential shape.
    """

    if not isinstance(assertion, RuntimeIdentityAssertion):
        raise IdentityRefused(
            "a RuntimeIdentityAssertion is required; a string or a flag asserts no identity")
    material = _refuse_material(assertion)
    if material is not None:
        raise IdentityRefused(material)
    if assertion.source not in RUNTIME_IDENTITY_SOURCES:
        raise IdentityRefused(f"unknown runtime identity source {assertion.source!r}")
    if assertion.source == "service_account_key_file":
        raise IdentityRefused(
            "a downloaded service-account key is itself a credential in the deployment and is refused "
            "(LP-2); the Cloud Run Job runs as its attached service account and downloads nothing")
    if assertion.source == "developer_credentials":
        raise IdentityRefused(
            "developer credentials are a human identity and may never be production-authoritative "
            "(LP-7 ruling 2, LP-8)")
    if assertion.source == "application_default_credentials":
        raise IdentityRefused(
            "application default credentials are a discovery order, not an identity: the credential ADC "
            "finds may be an attached service account, a downloaded key or a developer's own login, and "
            "succeeding proves none of them. Declare source='attached_service_account' with the exact "
            "designated service account (LP-8 identity clarification)")
    if assertion.source == "emulator":
        raise IdentityRefused(
            "an emulator identity is a test double and is never production-authoritative; the fake path "
            "exists so the job can be exercised offline, and its leases say so")
    if not is_service_account_resource(assertion.service_account_resource):
        raise IdentityRefused(
            "the runtime service account must be projects/<project>/serviceAccounts/<email>; the adapter "
            "binds to one exact account and infers none")
    identity = CustodyIdentity(
        kind=_SOURCE_TO_KIND[assertion.source],
        principal=assertion.service_account_resource,
        designated_service_account=assertion.designated_service_account,
        designation_attested_by=assertion.designation_attested_by,
        designation_record_digest=assertion.designation_record_digest,
    )
    why = identity.production_authority_refusal()
    if why is not None:
        raise IdentityRefused(why)
    return identity
