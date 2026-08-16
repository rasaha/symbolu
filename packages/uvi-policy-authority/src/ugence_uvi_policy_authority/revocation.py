"""Exact-version policy revocation (GV-2C-b §12).

:func:`revoke_policy` is the **only** entry point that may mutate revocation
state. There is no boolean parameter that revokes anything, and setting an
artifact's ``lifecycle_state`` to ``REVOKED`` revokes nothing — that label is a
self-assertion the artifact makes, not an authority act.

Policy-version revocation is deliberately its own concept:

* it targets one **complete exact** :class:`PolicyReference` — id, family,
  version, content digest, scope and tenant — so revoking one version cannot
  reach any other version of the same policy;
* it is **append-only** and timestamped with an injected instant;
* an identical repeat is idempotent; a *different* revocation of the same
  reference is a conflict and is rejected;
* it is **not** authority/key revocation (see
  :meth:`~ugence_uvi_policy_authority.signing.PolicyVerificationKey.revoke`),
  and it is **not** the Risk Authority's envelope revocation. The Risk
  Authority's tenant authority-epoch is not reused here: bumping an envelope
  epoch says nothing about which policy versions remain valid, and a policy
  revocation says nothing about outstanding runtime envelopes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import PolicyReference

from .errors import PolicyAuthorityRequestError, PolicyRevocationError
from .payload import revocation_signing_payload
from .records import PolicyRevocationRecord
from .registry import PolicyRegistry
from .signing import PolicySigner
from .statuses import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    PolicyRevocationReasonCode,
)

__all__ = ["revoke_policy"]


def revoke_policy(
    *,
    reference: PolicyReference,
    revocation_id: str,
    reason_code: PolicyRevocationReasonCode,
    registry: PolicyRegistry,
    revoked_at: datetime,
    signer: Optional[PolicySigner] = None,
    expected_tenant_id: Optional[str] = None,
    replacement_reference: Optional[PolicyReference] = None,
    detail: str = "",
) -> PolicyRevocationRecord:
    """Revoke exactly one issued policy version.

    ``revoked_at`` is injected — no clock is read. Resolution fails closed at
    and after this instant; behaviour strictly before it is governed by the
    resolver's :class:`~ugence_uvi_policy_authority.statuses.HistoricalResolutionRule`.
    """

    if not isinstance(reference, PolicyReference):
        raise PolicyAuthorityRequestError("revoke_policy(reference) must be a PolicyReference")
    if not isinstance(revocation_id, str) or not revocation_id.strip():
        raise PolicyAuthorityRequestError("revoke_policy(revocation_id) must be non-empty")
    if not isinstance(reason_code, PolicyRevocationReasonCode):
        raise PolicyAuthorityRequestError(
            "revoke_policy(reason_code) must be a PolicyRevocationReasonCode; a bare "
            "boolean or lifecycle label cannot revoke a policy"
        )
    if not isinstance(revoked_at, datetime) or revoked_at.tzinfo is None or (
        revoked_at.tzinfo.utcoffset(revoked_at) is None
    ):
        raise PolicyAuthorityRequestError("revoke_policy(revoked_at) must be timezone-aware")
    if replacement_reference is not None and not isinstance(
        replacement_reference, PolicyReference
    ):
        raise PolicyAuthorityRequestError(
            "revoke_policy(replacement_reference) must be a PolicyReference"
        )

    if expected_tenant_id is not None and reference.tenant_id != expected_tenant_id:
        raise PolicyRevocationError(
            f"cross-tenant revocation rejected: reference tenant "
            f"{reference.tenant_id!r} != {expected_tenant_id!r}"
        )
    if replacement_reference is not None and (
        replacement_reference.tenant_id != reference.tenant_id
        or replacement_reference.scope is not reference.scope
    ):
        raise PolicyRevocationError(
            "a replacement policy must be in the same tenant and scope as the version "
            "it replaces"
        )

    # Revocation targets an issued version. Revoking something never issued is a
    # request error, not a silent no-op that would look like success.
    existing = registry.get_issued(reference)
    if existing is None:
        raise PolicyRevocationError(
            "no issued policy exists under this exact reference; nothing to revoke"
        )

    key_id = ""
    signature_alg = ""
    signature = b""
    if signer is not None:
        key_id = signer.key_id
        signature_alg = signer.signature_alg
        signature = bytes(
            signer.sign(
                revocation_signing_payload(
                    revocation_id=revocation_id,
                    reference=reference,
                    reason_code=reason_code,
                    revoking_authority_id=signer.authority_id,
                    key_id=key_id,
                    signature_alg=signature_alg,
                    revoked_at=revoked_at,
                    replacement_reference=replacement_reference,
                )
            )
        )
        revoking_authority_id = signer.authority_id
    else:
        revoking_authority_id = existing.issuing_authority_id

    record = PolicyRevocationRecord(
        revocation_id=revocation_id,
        policy_reference=reference,
        reason_code=reason_code,
        revoking_authority_id=revoking_authority_id,
        revoked_at=revoked_at,
        key_id=key_id,
        signature_alg=signature_alg,
        signature=signature,
        replacement_reference=replacement_reference,
        detail=detail,
        authority_protocol=AUTHORITY_PROTOCOL,
        authority_protocol_version=AUTHORITY_PROTOCOL_VERSION,
    )

    # Append-only. An identical repeat returns the stored record; anything
    # conflicting raises.
    return registry.append_revocation(record)
