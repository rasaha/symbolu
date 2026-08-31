"""Signed, authorized, exact-version policy revocation (ADR §14, P-8).

:func:`revoke_policy` is the **only** entry point that may create revocation
state. There is no boolean parameter that revokes anything, and an artifact
labelling *itself* revoked revokes nothing — that label is a self-assertion.

Ratified properties, all enforced here rather than documented:

* **a revocation signer is mandatory** — there is no unsigned path through the
  public service, and :class:`PolicyRevocationRecord` refuses empty signature
  bytes, so unsigned revocation state cannot exist;
* **the issuer is never silently substituted as the revoker** — the revoking
  authority comes from the signer, and a missing signer is an error, not a
  defaulting opportunity;
* **the revoking key must be authorized for the exact policy scope** — the
  configured trust policy must resolve the key, match its authority and tenant,
  and grant :attr:`KeyEntitlement.REVOKE_POLICY`. A foreign signer with a
  structurally valid signature is rejected;
* **the record binds the complete exact coordinate** — family, policy identity,
  version, content digest, scope and tenant — so revoking one version can never
  reach another;
* **append-only**, with identical repeats idempotent and conflicting records
  rejected.

Policy-version revocation is **not** signing-key revocation (see
:meth:`PolicyVerificationKey.revoke`) and **not** the Risk Authority's envelope
revocation. Three concepts, three owners of the act; none implies another, and
no envelope epoch is reused here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .adapters import AdapterRegistry, PolicyCoordinate
from .canonical import require_tzaware
from .errors import PolicyAuthorityRequestError, PolicyRevocationError
from .payload import revocation_signing_payload
from .records import PolicyRevocationRecord
from .registry import PolicyRegistry
from .signing import PolicySignatureVerifier, PolicySigner
from .statuses import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    KeyEntitlement,
    PolicyRevocationReasonCode,
)

__all__ = ["revoke_policy", "verify_revocation_record"]


def verify_revocation_record(
    record: PolicyRevocationRecord,
    *,
    coordinate: PolicyCoordinate,
    signature_verifier: PolicySignatureVerifier,
    as_of: datetime,
):
    """Verify a stored revocation's signature and the revoker's entitlement.

    Returns the
    :class:`~ugence_policy_authority.core.signing.KeyVerification`. Used both
    when a revocation is created and again, independently, at every resolution:
    a stored revocation is never trusted merely because it is stored.
    """

    if record.coordinate != coordinate:
        from .signing import KeyVerification
        from .statuses import KeyVerificationStatus

        return KeyVerification(
            status=KeyVerificationStatus.INVALID_SIGNATURE,
            key_id=record.key_id,
            detail="revocation record targets a different policy coordinate",
        )
    return signature_verifier.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.revoking_authority_id,
        expected_tenant_id=coordinate.tenant_id,
        required_entitlement=KeyEntitlement.REVOKE_POLICY,
        as_of=as_of,
    )


def revoke_policy(
    *,
    reference: object,
    revocation_id: str,
    reason_code: PolicyRevocationReasonCode,
    registry: PolicyRegistry,
    adapters: AdapterRegistry,
    signer: PolicySigner,
    signature_verifier: PolicySignatureVerifier,
    revoked_at: datetime,
    expected_reference_tenant_id: Optional[str] = None,
    replacement_reference: object = None,
    detail: str = "",
) -> PolicyRevocationRecord:
    """Revoke exactly one issued policy version, with a signed authorized record.

    ``revoked_at`` is injected — no clock is read. Resolution fails closed at
    and after this instant; behaviour strictly before it is governed by the
    resolver's
    :class:`~ugence_policy_authority.core.statuses.HistoricalResolutionRule`,
    which defaults to deny-always.
    """

    if not isinstance(revocation_id, str) or not revocation_id.strip():
        raise PolicyAuthorityRequestError("revoke_policy(revocation_id) must be non-empty")
    if not isinstance(reason_code, PolicyRevocationReasonCode):
        raise PolicyAuthorityRequestError(
            "revoke_policy(reason_code) must be a PolicyRevocationReasonCode; a bare "
            "boolean or lifecycle label cannot revoke a policy"
        )
    if not isinstance(adapters, AdapterRegistry):
        raise PolicyAuthorityRequestError("revoke_policy(adapters) must be an AdapterRegistry")
    # A signer is mandatory: there is no unsigned revocation path.
    if signer is None or not all(
        hasattr(signer, attribute)
        for attribute in ("authority_id", "key_id", "signature_alg", "sign")
    ):
        raise PolicyAuthorityRequestError(
            "revoke_policy(signer) is mandatory and must implement PolicySigner — an "
            "unsigned revocation is invalid, not 'revocation pending'"
        )
    if signature_verifier is None or not hasattr(signature_verifier, "verify"):
        raise PolicyAuthorityRequestError(
            "revoke_policy(signature_verifier) is mandatory and must implement "
            "PolicySignatureVerifier — the revoker's entitlement must be proven"
        )
    revoked_at = require_tzaware(revoked_at, path="revoke_policy(revoked_at)")

    coordinate = adapters.coordinate_for(reference)
    replacement_coordinate = (
        adapters.coordinate_for(replacement_reference)
        if replacement_reference is not None
        else None
    )

    if (
        expected_reference_tenant_id is not None
        and coordinate.tenant_id != expected_reference_tenant_id
    ):
        raise PolicyRevocationError(
            f"cross-tenant revocation rejected: the reference's declared tenant does not "
            f"match {expected_reference_tenant_id!r}"
        )
    if replacement_coordinate is not None and (
        replacement_coordinate.tenant_id != coordinate.tenant_id
        or replacement_coordinate.scope != coordinate.scope
    ):
        raise PolicyRevocationError(
            "a replacement policy must be in the same tenant and scope as the version it "
            "replaces"
        )

    # Revocation targets an issued version. Revoking something never issued is a
    # request error, not a silent no-op that would look like success.
    if registry.get_issued(coordinate) is None:
        raise PolicyRevocationError(
            "no issued policy exists under this exact coordinate; nothing to revoke"
        )

    # The revoking authority is the signer's — never the issuer's by default.
    revoking_authority_id = signer.authority_id
    if not isinstance(revoking_authority_id, str) or not revoking_authority_id.strip():
        raise PolicyRevocationError("the revocation signer must name a revoking authority")

    signature = bytes(
        signer.sign(
            revocation_signing_payload(
                revocation_id=revocation_id,
                coordinate=coordinate,
                reason_code=reason_code,
                revoking_authority_id=revoking_authority_id,
                key_id=signer.key_id,
                signature_alg=signer.signature_alg,
                revoked_at=revoked_at,
                replacement_coordinate=replacement_coordinate,
            )
        )
    )

    record = PolicyRevocationRecord(
        revocation_id=revocation_id,
        coordinate=coordinate,
        reason_code=reason_code,
        revoking_authority_id=revoking_authority_id,
        key_id=signer.key_id,
        signature_alg=signer.signature_alg,
        signature=signature,
        revoked_at=revoked_at,
        replacement_coordinate=replacement_coordinate,
        detail=detail,
        authority_protocol=AUTHORITY_PROTOCOL,
        authority_protocol_version=AUTHORITY_PROTOCOL_VERSION,
    )

    # The revoker's entitlement is proven *before* the record is stored, so an
    # unauthorized revocation never enters the registry at all.
    verification = verify_revocation_record(
        record,
        coordinate=coordinate,
        signature_verifier=signature_verifier,
        as_of=revoked_at,
    )
    if not verification.valid:
        raise PolicyRevocationError(
            f"the revoking key is not authorized to revoke this policy: "
            f"{verification.status.value}"
            + (f" ({verification.detail})" if verification.detail else "")
        )

    # Append-only. An identical repeat returns the stored record; anything
    # conflicting raises.
    return registry.append_revocation(record)
