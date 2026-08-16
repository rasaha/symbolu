"""Domain-separated signed payloads (ADR §12, §14).

Two distinct payload shapes exist — issuance and policy-version revocation —
each under its own versioned domain tag. A signature produced over one can
never verify as the other, and neither can be replayed under a different
authority protocol version, because the protocol identity, the protocol version
and the canonicalization version are all inside the signed bytes.

Both payloads bind the **complete exact** policy coordinate: family, policy
identity, version, content digest, scope and tenant. There is no unbound field
a holder could rewrite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .adapters import PolicyCoordinate
from .canonical import CANONICALIZATION_VERSION, canonical_bytes
from .statuses import AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_ID, AUTHORITY_PROTOCOL_VERSION

__all__ = [
    "ISSUANCE_SIGNING_DOMAIN",
    "REVOCATION_SIGNING_DOMAIN",
    "issuance_signing_payload",
    "revocation_signing_payload",
]

#: Domain tag for an issuance signature.
ISSUANCE_SIGNING_DOMAIN = "ugence.policy-authority/issuance/v1"

#: Domain tag for a policy-version revocation signature. Deliberately distinct
#: from the Risk Authority's envelope revocation, which is a different concept
#: over different artifacts with a different owner.
REVOCATION_SIGNING_DOMAIN = "ugence.policy-authority/policy-revocation/v1"


def _coordinate_fields(coordinate: PolicyCoordinate) -> dict:
    return {
        "policy_family": coordinate.policy_family,
        "policy_id": coordinate.policy_id,
        "version": coordinate.version,
        "content_digest": coordinate.content_digest,
        "scope": coordinate.scope,
        "tenant_id": coordinate.tenant_id,
    }


def _framed(domain: str, body: dict) -> bytes:
    # The domain is both a byte prefix and a signed field: the prefix makes the
    # two payload families unambiguous to a naive byte comparison, and the field
    # makes it part of what the signature commits to.
    return domain.encode("utf-8") + b"\x00" + canonical_bytes(body)


def issuance_signing_payload(
    *,
    record_id: str,
    coordinate: PolicyCoordinate,
    adapter_id: str,
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
        "authority_protocol_id": AUTHORITY_PROTOCOL_ID,
        "canonicalization": CANONICALIZATION_VERSION,
        "record_id": record_id,
        "adapter_id": adapter_id,
        "policy_body_digest": policy_body_digest,
        "approving_authority_id": approving_authority_id,
        "approval_ref": approval_ref,
        "approval_digest": approval_digest,
        "issuing_authority_id": issuing_authority_id,
        "key_id": key_id,
        "signature_alg": signature_alg,
        "issued_at": issued_at,
    }
    body.update(_coordinate_fields(coordinate))
    return _framed(ISSUANCE_SIGNING_DOMAIN, body)


def revocation_signing_payload(
    *,
    revocation_id: str,
    coordinate: PolicyCoordinate,
    reason_code: object,
    revoking_authority_id: str,
    key_id: str,
    signature_alg: str,
    revoked_at: datetime,
    replacement_coordinate: Optional[PolicyCoordinate] = None,
) -> bytes:
    """Return the exact bytes a policy-version revocation signature covers."""

    body = {
        "domain": REVOCATION_SIGNING_DOMAIN,
        "authority_protocol": AUTHORITY_PROTOCOL,
        "authority_protocol_version": AUTHORITY_PROTOCOL_VERSION,
        "authority_protocol_id": AUTHORITY_PROTOCOL_ID,
        "canonicalization": CANONICALIZATION_VERSION,
        "revocation_id": revocation_id,
        "reason_code": reason_code,
        "revoking_authority_id": revoking_authority_id,
        "key_id": key_id,
        "signature_alg": signature_alg,
        "revoked_at": revoked_at,
        "replacement": (
            _coordinate_fields(replacement_coordinate)
            if replacement_coordinate is not None
            else None
        ),
    }
    body.update(_coordinate_fields(coordinate))
    return _framed(REVOCATION_SIGNING_DOMAIN, body)
