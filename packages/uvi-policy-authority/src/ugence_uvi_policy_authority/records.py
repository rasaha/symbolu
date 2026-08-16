"""Immutable local authority records (GV-2C-b §8).

Three record shapes, all frozen, all deeply immutable (every field is a scalar,
an enum, ``bytes``, a frozen contract dataclass, or a tuple of those), so a
holder can neither mutate a stored record nor mutate a collection it handed in.
There is no field anywhere capable of carrying private key material.

Constructing one of these by hand grants nothing. An
:class:`IssuedPolicyRecord` a caller assembled is just a data structure: trusted
resolution recomputes the body digest and verifies the signature over the
authority payload, so a forged record fails closed exactly like a tampered one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import (
    PolicyFamily,
    PolicyReference,
)

from .errors import PolicyAuthorityRequestError
from .families import UVIPolicy, require_supported_policy
from .payload import issuance_signing_payload, revocation_signing_payload
from .statuses import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
)

__all__ = [
    "IssuedPolicyRecord",
    "PolicyRevocationRecord",
    "PolicyResolution",
]


def _require_tzaware(value: object, name: str) -> None:
    if not isinstance(value, datetime):
        raise PolicyAuthorityRequestError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise PolicyAuthorityRequestError(f"{name} must be timezone-aware")


def _require_nonempty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")


def _require_digest(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(
        c not in "0123456789abcdef" for c in value
    ):
        raise PolicyAuthorityRequestError(f"{name} must be a lowercase 64-char sha-256 hex digest")


@dataclass(frozen=True)
class IssuedPolicyRecord:
    """One issued, signed, digest-bound UVI policy version.

    Binds the exact :class:`PolicyReference`, the policy family and the
    canonical artifact itself, the issuer, the key id, the signature, the
    approval proof reference, the issuance timestamp, and the authority
    protocol version that produced it.
    """

    record_id: str
    policy_reference: PolicyReference
    policy_family: PolicyFamily
    policy: UVIPolicy
    policy_body_digest: str
    issuing_authority_id: str
    key_id: str
    signature_alg: str
    signature: bytes
    approving_authority_id: str
    approval_ref: str
    approval_digest: str
    issued_at: datetime
    authority_protocol: str = AUTHORITY_PROTOCOL
    authority_protocol_version: str = AUTHORITY_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "IssuedPolicyRecord.record_id")
        if not isinstance(self.policy_reference, PolicyReference):
            raise PolicyAuthorityRequestError(
                "IssuedPolicyRecord.policy_reference must be a PolicyReference"
            )
        family = require_supported_policy(self.policy)
        if self.policy_family is not family:
            raise PolicyAuthorityRequestError(
                "IssuedPolicyRecord.policy_family must match the artifact's family"
            )
        if self.policy_reference.policy_family is not family:
            raise PolicyAuthorityRequestError(
                "IssuedPolicyRecord.policy_reference must name the artifact's family"
            )
        _require_digest(self.policy_body_digest, "IssuedPolicyRecord.policy_body_digest")
        _require_nonempty(self.issuing_authority_id, "IssuedPolicyRecord.issuing_authority_id")
        _require_nonempty(self.key_id, "IssuedPolicyRecord.key_id")
        _require_nonempty(self.signature_alg, "IssuedPolicyRecord.signature_alg")
        if not isinstance(self.signature, (bytes, bytearray)) or not self.signature:
            raise PolicyAuthorityRequestError("IssuedPolicyRecord.signature must be non-empty bytes")
        object.__setattr__(self, "signature", bytes(self.signature))
        _require_nonempty(
            self.approving_authority_id, "IssuedPolicyRecord.approving_authority_id"
        )
        _require_nonempty(self.approval_ref, "IssuedPolicyRecord.approval_ref")
        _require_digest(self.approval_digest, "IssuedPolicyRecord.approval_digest")
        _require_tzaware(self.issued_at, "IssuedPolicyRecord.issued_at")
        _require_nonempty(self.authority_protocol, "IssuedPolicyRecord.authority_protocol")
        _require_nonempty(
            self.authority_protocol_version, "IssuedPolicyRecord.authority_protocol_version"
        )

    @property
    def identity_key(self) -> tuple:
        """Identity of the *version slot* this record occupies.

        Deliberately excludes the content digest: two records with the same
        id/family/version/scope/tenant but different content are a conflict,
        not two coexisting versions.
        """

        ref = self.policy_reference
        return (
            ref.policy_id,
            ref.policy_family,
            ref.version,
            ref.scope,
            ref.tenant_id,
        )

    def signing_payload(self) -> bytes:
        """Recompute the exact bytes this record's signature must cover."""

        return issuance_signing_payload(
            record_id=self.record_id,
            reference=self.policy_reference,
            policy_body_digest=self.policy_body_digest,
            approving_authority_id=self.approving_authority_id,
            approval_ref=self.approval_ref,
            approval_digest=self.approval_digest,
            issuing_authority_id=self.issuing_authority_id,
            key_id=self.key_id,
            signature_alg=self.signature_alg,
            issued_at=self.issued_at,
        )


@dataclass(frozen=True)
class PolicyRevocationRecord:
    """Revocation of one exact policy version.

    Targets a complete :class:`PolicyReference` — id, family, version, content
    digest, scope and tenant — so revoking one version can never reach another.
    This is **policy-version** revocation; it is not authority/key revocation
    and it is not the Risk Authority's envelope revocation.
    """

    revocation_id: str
    policy_reference: PolicyReference
    reason_code: PolicyRevocationReasonCode
    revoking_authority_id: str
    revoked_at: datetime
    key_id: str = ""
    signature_alg: str = ""
    signature: bytes = b""
    replacement_reference: Optional[PolicyReference] = None
    detail: str = ""
    authority_protocol: str = AUTHORITY_PROTOCOL
    authority_protocol_version: str = AUTHORITY_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.revocation_id, "PolicyRevocationRecord.revocation_id")
        if not isinstance(self.policy_reference, PolicyReference):
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.policy_reference must be a PolicyReference"
            )
        if not isinstance(self.reason_code, PolicyRevocationReasonCode):
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.reason_code must be a PolicyRevocationReasonCode"
            )
        _require_nonempty(
            self.revoking_authority_id, "PolicyRevocationRecord.revoking_authority_id"
        )
        _require_tzaware(self.revoked_at, "PolicyRevocationRecord.revoked_at")
        if not isinstance(self.signature, (bytes, bytearray)):
            raise PolicyAuthorityRequestError("PolicyRevocationRecord.signature must be bytes")
        object.__setattr__(self, "signature", bytes(self.signature))
        if self.signature and not (self.key_id and self.signature_alg):
            raise PolicyAuthorityRequestError(
                "a signed PolicyRevocationRecord must name its key_id and signature_alg"
            )
        if self.replacement_reference is not None and not isinstance(
            self.replacement_reference, PolicyReference
        ):
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.replacement_reference must be a PolicyReference"
            )

    def signing_payload(self) -> bytes:
        """Recompute the exact bytes this revocation's signature must cover."""

        return revocation_signing_payload(
            revocation_id=self.revocation_id,
            reference=self.policy_reference,
            reason_code=self.reason_code,
            revoking_authority_id=self.revoking_authority_id,
            key_id=self.key_id,
            signature_alg=self.signature_alg,
            revoked_at=self.revoked_at,
            replacement_reference=self.replacement_reference,
        )


@dataclass(frozen=True)
class PolicyResolution:
    """The outcome of one trusted resolution.

    A policy artifact and its issuance record are present **if and only if**
    the status is ``RESOLVED``; the constructor enforces this, so no caller can
    ever receive a policy alongside a failed status, and no failed resolution
    can smuggle a record out.
    """

    status: PolicyResolutionStatus
    reason: PolicyResolutionReason
    requested_reference: PolicyReference
    as_of: datetime
    policy: Optional[UVIPolicy] = None
    record: Optional[IssuedPolicyRecord] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, PolicyResolutionStatus):
            raise PolicyAuthorityRequestError(
                "PolicyResolution.status must be a PolicyResolutionStatus"
            )
        if not isinstance(self.reason, PolicyResolutionReason):
            raise PolicyAuthorityRequestError(
                "PolicyResolution.reason must be a PolicyResolutionReason"
            )
        if not isinstance(self.requested_reference, PolicyReference):
            raise PolicyAuthorityRequestError(
                "PolicyResolution.requested_reference must be a PolicyReference"
            )
        _require_tzaware(self.as_of, "PolicyResolution.as_of")

        resolved = self.status is PolicyResolutionStatus.RESOLVED
        if resolved:
            if self.reason is not PolicyResolutionReason.RESOLVED:
                raise PolicyAuthorityRequestError(
                    "a RESOLVED PolicyResolution must carry reason RESOLVED"
                )
            if self.policy is None or self.record is None:
                raise PolicyAuthorityRequestError(
                    "a RESOLVED PolicyResolution must carry both the policy and its record"
                )
            if self.record.policy is not self.policy:
                raise PolicyAuthorityRequestError(
                    "a RESOLVED PolicyResolution must return the record's own artifact"
                )
        else:
            if self.reason is PolicyResolutionReason.RESOLVED:
                raise PolicyAuthorityRequestError(
                    "an UNRESOLVED PolicyResolution cannot carry reason RESOLVED"
                )
            if self.policy is not None or self.record is not None:
                raise PolicyAuthorityRequestError(
                    "an UNRESOLVED PolicyResolution must not carry a policy or a record"
                )

    @property
    def resolved(self) -> bool:
        return self.status is PolicyResolutionStatus.RESOLVED

    @classmethod
    def unresolved(
        cls,
        reason: PolicyResolutionReason,
        *,
        requested_reference: PolicyReference,
        as_of: datetime,
        detail: str = "",
    ) -> "PolicyResolution":
        return cls(
            status=PolicyResolutionStatus.UNRESOLVED,
            reason=reason,
            requested_reference=requested_reference,
            as_of=as_of,
            detail=detail,
        )
