"""Domain-separated signed payloads (GV-2C-b §7).

Two distinct payload shapes exist — issuance and policy-version revocation —
each under its own domain tag. A signature produced over one can never verify
as the other, and neither can be replayed under a different authority protocol
version, because the protocol identity and version are inside the signed bytes.

The issuance payload binds every field §7 requires:

    authority protocol + version, record id, policy family, policy id, policy
    version, scope, tenant, canonical content digest, canonical policy-body
    digest, approving authority identity, approval evidence reference and
    digest, issuing authority identity, key id, signature algorithm, and the
    issuance timestamp.

Altering any one of them changes the payload bytes and therefore invalidates
the signature — there is no unbound field a holder could rewrite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import PolicyReference

from .canonical import canonical_bytes
from .statuses import AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_VERSION

__all__ = [
    "ISSUANCE_SIGNING_DOMAIN",
    "REVOCATION_SIGNING_DOMAIN",
    "issuance_signing_payload",
    "revocation_signing_payload",
]

#: Domain tag for an issuance signature.
ISSUANCE_SIGNING_DOMAIN = "ugence.uvi.policy-authority/issuance/v1"

#: Domain tag for a policy-version revocation signature. Deliberately distinct
#: from the Risk Authority's envelope revocation, which is a different concept
#: over different artifacts.
REVOCATION_SIGNING_DOMAIN = "ugence.uvi.policy-authority/policy-revocation/v1"


def _reference_fields(reference: PolicyReference) -> dict:
    return {
        "policy_id": reference.policy_id,
        "policy_family": reference.policy_family,
        "version": reference.version,
        "content_digest": reference.content_digest,
        "scope": reference.scope,
        "tenant_id": reference.tenant_id,
    }


def _framed(domain: str, body: dict) -> bytes:
    # The domain is both a byte prefix and a signed field: the prefix makes the
    # two payload families unambiguous even to a naive byte comparison, and the
    # field makes it part of what the signature actually commits to.
    return domain.encode("utf-8") + b"\x00" + canonical_bytes(body)


def issuance_signing_payload(
    *,
    record_id: str,
    reference: PolicyReference,
    policy_body_digest: str,
    approving_authority_id: str,
    approval_ref: str,
    approval_digest: str,
    issuing_authority_id: str,
    key_id: str,
    signature_alg: str,
    issued_at: datetime,
) -> bytes:
    """Return the exact bytes an issuance signature is computed over."""

    body = {
        "domain": ISSUANCE_SIGNING_DOMAIN,
        "authority_protocol": AUTHORITY_PROTOCOL,
        "authority_protocol_version": AUTHORITY_PROTOCOL_VERSION,
        "record_id": record_id,
        "policy_body_digest": policy_body_digest,
        "approving_authority_id": approving_authority_id,
        "approval_ref": approval_ref,
        "approval_digest": approval_digest,
        "issuing_authority_id": issuing_authority_id,
        "key_id": key_id,
        "signature_alg": signature_alg,
        "issued_at": issued_at,
    }
    body.update(_reference_fields(reference))
    return _framed(ISSUANCE_SIGNING_DOMAIN, body)


def revocation_signing_payload(
    *,
    revocation_id: str,
    reference: PolicyReference,
    reason_code: object,
    revoking_authority_id: str,
    key_id: str,
    signature_alg: str,
    revoked_at: datetime,
    replacement_reference: Optional[PolicyReference] = None,
) -> bytes:
    """Return the exact bytes a policy-version revocation signature covers."""

    body = {
        "domain": REVOCATION_SIGNING_DOMAIN,
        "authority_protocol": AUTHORITY_PROTOCOL,
        "authority_protocol_version": AUTHORITY_PROTOCOL_VERSION,
        "revocation_id": revocation_id,
        "reason_code": reason_code,
        "revoking_authority_id": revoking_authority_id,
        "key_id": key_id,
        "signature_alg": signature_alg,
        "revoked_at": revoked_at,
        "replacement": (
            _reference_fields(replacement_reference)
            if replacement_reference is not None
            else None
        ),
    }
    body.update(_reference_fields(reference))
    return _framed(REVOCATION_SIGNING_DOMAIN, body)
