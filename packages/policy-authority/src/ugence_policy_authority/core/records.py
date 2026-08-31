"""Immutable authority records (ADR §14, §15).

Three record shapes, all frozen and deeply immutable, none of which has a field
capable of carrying private key material.

**Construction is not authenticity.** These dataclasses are public and remain
structurally constructible: anyone can build an
:class:`IssuedPolicyRecord` or a :class:`PolicyResolution`. Doing so proves
nothing. Only :func:`~ugence_policy_authority.core.resolution.resolve_policy`
produces an authority-evaluated resolution, and it recomputes the body digest
and verifies every signature from scratch — so a hand-assembled record fails
exactly like a tampered one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Optional

from .adapters import PolicyCoordinate
from .canonical import require_nfc, require_tzaware
from .errors import PolicyAuthorityRequestError
from .payload import (
    issuance_signing_payload,
    revocation_signing_payload,
    supersession_signing_payload,
)
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
    "PolicySupersessionRecord",
    "PolicyResolution",
]

_HEX = frozenset("0123456789abcdef")


def _require_nonempty(value: object, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")
    require_nfc(value, path=name)


def _require_digest(value: object, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise PolicyAuthorityRequestError(f"{name} must be a lowercase 64-char sha-256 hex digest")


@dataclass(frozen=True)
class IssuedPolicyRecord:
    """One issued, signed, digest-bound policy version.

    Binds the exact :class:`PolicyCoordinate`, the owning adapter, the artifact
    itself, the issuer, key id, signature, approval proof reference, issuance
    instant, and the authority protocol version that produced it.
    """

    record_id: str
    coordinate: PolicyCoordinate
    adapter_id: str
    policy_type: str
    policy: Any
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
        if not isinstance(self.coordinate, PolicyCoordinate):
            raise PolicyAuthorityRequestError(
                "IssuedPolicyRecord.coordinate must be a PolicyCoordinate"
            )
        _require_nonempty(self.adapter_id, "IssuedPolicyRecord.adapter_id")
        _require_nonempty(self.policy_type, "IssuedPolicyRecord.policy_type")
        if self.policy is None:
            raise PolicyAuthorityRequestError("IssuedPolicyRecord.policy is required")
        _require_digest(self.policy_body_digest, "IssuedPolicyRecord.policy_body_digest")
        _require_nonempty(self.issuing_authority_id, "IssuedPolicyRecord.issuing_authority_id")
        _require_nonempty(self.key_id, "IssuedPolicyRecord.key_id")
        _require_nonempty(self.signature_alg, "IssuedPolicyRecord.signature_alg")
        if not isinstance(self.signature, (bytes, bytearray)) or not self.signature:
            raise PolicyAuthorityRequestError(
                "IssuedPolicyRecord.signature must be non-empty bytes"
            )
        object.__setattr__(self, "signature", bytes(self.signature))
        _require_nonempty(
            self.approving_authority_id, "IssuedPolicyRecord.approving_authority_id"
        )
        _require_nonempty(self.approval_ref, "IssuedPolicyRecord.approval_ref")
        _require_digest(self.approval_digest, "IssuedPolicyRecord.approval_digest")
        require_tzaware(self.issued_at, path="IssuedPolicyRecord.issued_at")
        _require_nonempty(self.authority_protocol, "IssuedPolicyRecord.authority_protocol")
        _require_nonempty(
            self.authority_protocol_version, "IssuedPolicyRecord.authority_protocol_version"
        )

    def signing_payload(self) -> bytes:
        """Recompute the exact bytes this record's signature must cover."""

        return issuance_signing_payload(
            record_id=self.record_id,
            coordinate=self.coordinate,
            adapter_id=self.adapter_id,
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
    """Revocation of one exact policy version — always signed.

    Targets a complete :class:`PolicyCoordinate` — family, policy identity,
    version, content digest, scope and tenant — so revoking one version can
    never reach another. The signature and revoking authority are mandatory:
    there is no unsigned revocation state, and the issuer is never silently
    substituted as the revoker.
    """

    revocation_id: str
    coordinate: PolicyCoordinate
    reason_code: PolicyRevocationReasonCode
    revoking_authority_id: str
    key_id: str
    signature_alg: str
    signature: bytes
    revoked_at: datetime
    replacement_coordinate: Optional[PolicyCoordinate] = None
    detail: str = ""
    authority_protocol: str = AUTHORITY_PROTOCOL
    authority_protocol_version: str = AUTHORITY_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.revocation_id, "PolicyRevocationRecord.revocation_id")
        if not isinstance(self.coordinate, PolicyCoordinate):
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.coordinate must be a PolicyCoordinate"
            )
        if not isinstance(self.reason_code, PolicyRevocationReasonCode):
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.reason_code must be a PolicyRevocationReasonCode"
            )
        _require_nonempty(
            self.revoking_authority_id, "PolicyRevocationRecord.revoking_authority_id"
        )
        _require_nonempty(self.key_id, "PolicyRevocationRecord.key_id")
        _require_nonempty(self.signature_alg, "PolicyRevocationRecord.signature_alg")
        if not isinstance(self.signature, (bytes, bytearray)) or not self.signature:
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.signature must be non-empty bytes — an unsigned "
                "revocation is not 'revocation pending', it is invalid"
            )
        object.__setattr__(self, "signature", bytes(self.signature))
        require_tzaware(self.revoked_at, path="PolicyRevocationRecord.revoked_at")
        if self.replacement_coordinate is not None and not isinstance(
            self.replacement_coordinate, PolicyCoordinate
        ):
            raise PolicyAuthorityRequestError(
                "PolicyRevocationRecord.replacement_coordinate must be a PolicyCoordinate"
            )

    def signing_payload(self) -> bytes:
        """Recompute the exact bytes this revocation's signature must cover."""

        return revocation_signing_payload(
            revocation_id=self.revocation_id,
            coordinate=self.coordinate,
            reason_code=self.reason_code,
            revoking_authority_id=self.revoking_authority_id,
            key_id=self.key_id,
            signature_alg=self.signature_alg,
            revoked_at=self.revoked_at,
            replacement_coordinate=self.replacement_coordinate,
        )


@dataclass(frozen=True)
class PolicyResolution:
    """The outcome of one trusted resolution.

    A policy artifact and its issuance record are present **if and only if** the
    status is ``RESOLVED``; the constructor enforces this, so no caller can ever
    receive a policy alongside a failed status.

    ``historical`` is ``True`` when the answer was produced for an ``as_of``
    strictly before a verified revocation instant under an explicitly selected
    historical rule. A historical answer describes the past and **never implies
    current validity** — it always carries its own explicit ``as_of``.

    The three trailing ``descriptor_*`` fields carry the **adapter descriptor's
    own projection of the artifact**, populated by :func:`resolve_policy` from
    the descriptor it already re-derives. They exist so a consumer that holds no
    adapter registry can nonetheless recompute
    :func:`~ugence_policy_authority.core.canonical.framed_body_digest` over
    ``(adapter_id, policy_type, projection)`` and compare it against
    ``record.policy_body_digest``.

    They add **no new trust claim**. ``resolve_policy`` has already proven that
    exact equality before it returns ``RESOLVED``; publishing the projection
    only makes the proof reproducible on the other side of a package boundary,
    where today the body digest is a one-way hash with nothing to check against.

    They are ``Optional`` because this is a public dataclass anyone may
    hand-assemble, not because absence is an acceptable state for a consumer: a
    verifier that relies on them must **refuse ``None``** rather than skip the
    check. A ``RESOLVED`` resolution produced by ``resolve_policy`` always
    carries all three; the constructor enforces that they are present together
    or absent together, so a partial triple — enough to look checkable and not
    enough to check — cannot exist.
    """

    status: PolicyResolutionStatus
    reason: PolicyResolutionReason
    requested_coordinate: PolicyCoordinate
    as_of: datetime
    policy: Any = None
    record: Optional[IssuedPolicyRecord] = None
    historical: bool = False
    detail: str = ""
    descriptor_adapter_id: Optional[str] = None
    descriptor_policy_type: Optional[str] = None
    descriptor_canonical_projection: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, PolicyResolutionStatus):
            raise PolicyAuthorityRequestError(
                "PolicyResolution.status must be a PolicyResolutionStatus"
            )
        if not isinstance(self.reason, PolicyResolutionReason):
            raise PolicyAuthorityRequestError(
                "PolicyResolution.reason must be a PolicyResolutionReason"
            )
        if not isinstance(self.requested_coordinate, PolicyCoordinate):
            raise PolicyAuthorityRequestError(
                "PolicyResolution.requested_coordinate must be a PolicyCoordinate"
            )
        require_tzaware(self.as_of, path="PolicyResolution.as_of")
        if not isinstance(self.historical, bool):
            raise PolicyAuthorityRequestError("PolicyResolution.historical must be a bool")

        # -- descriptor projection -----------------------------------------
        # All three or none. A partial triple cannot rebuild the digest frame,
        # so admitting one would hand a consumer something that looks checkable
        # and is not.
        present = [
            self.descriptor_adapter_id is not None,
            self.descriptor_policy_type is not None,
            self.descriptor_canonical_projection is not None,
        ]
        if any(present) and not all(present):
            raise PolicyAuthorityRequestError(
                "PolicyResolution descriptor_adapter_id, descriptor_policy_type and "
                "descriptor_canonical_projection must be present together or absent together"
            )
        if all(present):
            if not isinstance(self.descriptor_adapter_id, str):
                raise PolicyAuthorityRequestError(
                    "PolicyResolution.descriptor_adapter_id must be a string"
                )
            if not isinstance(self.descriptor_policy_type, str):
                raise PolicyAuthorityRequestError(
                    "PolicyResolution.descriptor_policy_type must be a string"
                )
            if not isinstance(self.descriptor_canonical_projection, Mapping):
                raise PolicyAuthorityRequestError(
                    "PolicyResolution.descriptor_canonical_projection must be a mapping"
                )
            # Defensively copied and exposed read-only, matching PolicyKeyRing.
            # The copy is shallow, as PolicyKeyRing's is: it stops a caller
            # rebinding or adding top-level keys. Deeper mutation is caught by
            # the digest rather than prevented here — a consumer reframes this
            # projection and compares it against the signed body digest, so a
            # mutated nested value fails that comparison instead of passing.
            object.__setattr__(
                self,
                "descriptor_canonical_projection",
                MappingProxyType(dict(self.descriptor_canonical_projection)),
            )

        if self.status is PolicyResolutionStatus.RESOLVED:
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
            # Nothing was proven, so there is nothing to republish. A projection
            # here would invite a consumer to reframe a digest that no gate
            # reached, which reads as evidence and is not.
            if self.descriptor_adapter_id is not None:
                raise PolicyAuthorityRequestError(
                    "an UNRESOLVED PolicyResolution must not carry a descriptor projection"
                )
            if self.historical:
                raise PolicyAuthorityRequestError(
                    "only a RESOLVED PolicyResolution may be marked historical"
                )

    @property
    def resolved(self) -> bool:
        return self.status is PolicyResolutionStatus.RESOLVED

    @property
    def implies_current_validity(self) -> bool:
        """``True`` only for a non-historical resolved answer.

        A historical answer is explicitly *not* a statement about now.
        """

        return self.resolved and not self.historical

    @classmethod
    def unresolved(
        cls,
        reason: PolicyResolutionReason,
        *,
        requested_coordinate: PolicyCoordinate,
        as_of: datetime,
        detail: str = "",
    ) -> "PolicyResolution":
        return cls(
            status=PolicyResolutionStatus.UNRESOLVED,
            reason=reason,
            requested_coordinate=requested_coordinate,
            as_of=as_of,
            detail=detail,
        )


@dataclass(frozen=True)
class PolicySupersessionRecord:
    """One version superseded by another — always signed (`ACC-LC-IA-2`).

    Written by the *same* signed act that issues the successor (`ACC-LC-2`), and
    stored in its own append-only store. It exists because an issued record is
    immutable and its ``lifecycle_state`` is signed artifact content: nothing can
    edit a predecessor into ``SUPERSEDED``, so the transition is expressed as an
    append — exactly as revocation already is — and resolution consults it.

    Both coordinates are complete, so a supersession can never reach a version it
    does not name. This is **not** revocation: the predecessor is not withdrawn,
    it is replaced, and it remains readable as history.
    """

    supersession_id: str
    coordinate: PolicyCoordinate
    successor_coordinate: PolicyCoordinate
    superseding_authority_id: str
    key_id: str
    signature_alg: str
    signature: bytes
    superseded_at: datetime
    detail: str = ""
    authority_protocol: str = AUTHORITY_PROTOCOL
    authority_protocol_version: str = AUTHORITY_PROTOCOL_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.supersession_id, "PolicySupersessionRecord.supersession_id")
        for name in ("coordinate", "successor_coordinate"):
            if not isinstance(getattr(self, name), PolicyCoordinate):
                raise PolicyAuthorityRequestError(
                    f"PolicySupersessionRecord.{name} must be a PolicyCoordinate"
                )
        if self.coordinate == self.successor_coordinate:
            raise PolicyAuthorityRequestError(
                "PolicySupersessionRecord: a version cannot supersede itself"
            )
        _require_nonempty(
            self.superseding_authority_id,
            "PolicySupersessionRecord.superseding_authority_id",
        )
        _require_nonempty(self.key_id, "PolicySupersessionRecord.key_id")
        _require_nonempty(self.signature_alg, "PolicySupersessionRecord.signature_alg")
        if not isinstance(self.signature, (bytes, bytearray)) or not self.signature:
            raise PolicyAuthorityRequestError(
                "PolicySupersessionRecord.signature must be non-empty bytes — an "
                "unsigned supersession is not 'supersession pending', it is invalid"
            )
        object.__setattr__(self, "signature", bytes(self.signature))
        require_tzaware(self.superseded_at, path="PolicySupersessionRecord.superseded_at")

    def signing_payload(self) -> bytes:
        """Recompute the exact bytes this supersession's signature must cover."""

        return supersession_signing_payload(
            supersession_id=self.supersession_id,
            coordinate=self.coordinate,
            successor_coordinate=self.successor_coordinate,
            superseding_authority_id=self.superseding_authority_id,
            key_id=self.key_id,
            signature_alg=self.signature_alg,
            superseded_at=self.superseded_at,
        )
