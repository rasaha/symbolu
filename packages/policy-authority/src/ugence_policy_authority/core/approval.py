"""The injected approval-verification boundary (ADR §11, P-5).

**Approval is not this package's job.** Deciding that a policy's content is
correct, lawful, and worth adopting is an external governance responsibility.
What the Ugence Policy Authority owns is the *technical* refusal to issue
anything not accompanied by verified external approval evidence.

* the caller supplies an :class:`ApprovalEvidenceRef` — a pointer to an
  externally produced approval artifact plus that artifact's digest;
* an injected :class:`ApprovalVerifier`, **selected and trusted by the
  composition root**, resolves it and returns a structured
  :class:`ApprovalVerification` binding the exact policy coordinate, body
  digest, approving authority, approval artifact, verification time and
  approved period;
* the authority then **independently re-checks** that binding
  (:func:`require_verified_approval`) before anything is signed or stored, so a
  merely lax verifier is still constrained.

Explicitly **not** approval: a caller ``approved=True`` (no such parameter
exists), a bare authority name, a lifecycle label the artifact asserts about
itself, an evidence-status enum, or a fabricated duck-typed object.

The only verifier shipped anywhere in this distribution is
:class:`DenyAllApprovalVerifier`. No allow-all verifier and no public test
verifier ships — deterministic fakes live only in the test tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from .adapters import PolicyCoordinate
from .canonical import require_nfc, require_tzaware
from .errors import PolicyApprovalError, PolicyAuthorityRequestError
from .statuses import ApprovalVerificationStatus

__all__ = [
    "ApprovalEvidenceRef",
    "ApprovalVerification",
    "ApprovalVerifier",
    "DenyAllApprovalVerifier",
    "require_verified_approval",
]

_HEX = frozenset("0123456789abcdef")


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(c not in _HEX for c in value):
        raise PolicyAuthorityRequestError(f"{name} must be a lowercase 64-char sha-256 hex digest")
    return value


def _require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")
    return require_nfc(value, path=name)


@dataclass(frozen=True)
class ApprovalEvidenceRef:
    """A pointer to an externally produced approval artifact.

    Carries no approval *decision* of its own — only where the artifact lives,
    what its bytes digest to, and which authority issued it, so a verifier can
    fetch it and the authority can bind the exact artifact it was shown into the
    issuance signature.
    """

    approval_ref: str
    approval_digest: str
    approving_authority_id: str

    def __post_init__(self) -> None:
        _require_nonempty(self.approval_ref, "ApprovalEvidenceRef.approval_ref")
        _require_digest(self.approval_digest, "ApprovalEvidenceRef.approval_digest")
        _require_nonempty(
            self.approving_authority_id, "ApprovalEvidenceRef.approving_authority_id"
        )


@dataclass(frozen=True)
class ApprovalVerification:
    """The structured result an approval verifier must return.

    Binds the exact policy coordinate (family, id, version, content digest,
    scope, tenant), the policy-body digest, the approving authority, the
    approval artifact and its digest, the verification time, and optionally the
    approved validity period.
    """

    verified: bool
    status: ApprovalVerificationStatus
    coordinate: PolicyCoordinate
    policy_body_digest: str
    approving_authority_id: str
    approval_ref: str
    approval_digest: str
    verified_at: datetime
    approved_from: Optional[datetime] = None
    approved_to: Optional[datetime] = None
    detail: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.status, ApprovalVerificationStatus):
            raise PolicyAuthorityRequestError(
                "ApprovalVerification.status must be an ApprovalVerificationStatus"
            )
        if not isinstance(self.verified, bool):
            raise PolicyAuthorityRequestError("ApprovalVerification.verified must be a bool")
        if self.verified is not (self.status is ApprovalVerificationStatus.APPROVED):
            raise PolicyAuthorityRequestError(
                "ApprovalVerification.verified is True if and only if status is APPROVED"
            )
        if not isinstance(self.coordinate, PolicyCoordinate):
            raise PolicyAuthorityRequestError(
                "ApprovalVerification.coordinate must be a PolicyCoordinate"
            )
        _require_digest(self.policy_body_digest, "ApprovalVerification.policy_body_digest")
        _require_nonempty(
            self.approving_authority_id, "ApprovalVerification.approving_authority_id"
        )
        _require_nonempty(self.approval_ref, "ApprovalVerification.approval_ref")
        _require_digest(self.approval_digest, "ApprovalVerification.approval_digest")
        require_tzaware(self.verified_at, path="ApprovalVerification.verified_at")
        for name in ("approved_from", "approved_to"):
            value = getattr(self, name)
            if value is not None:
                require_tzaware(value, path=f"ApprovalVerification.{name}")
        if self.approved_from is not None and self.approved_to is not None:
            if not self.approved_from < self.approved_to:
                raise PolicyAuthorityRequestError(
                    "ApprovalVerification.approved_from must be before approved_to"
                )


@runtime_checkable
class ApprovalVerifier(Protocol):
    """Resolve and verify external approval evidence for one exact policy.

    An implementation is a *trusted dependency chosen by the composition root*:
    it is the seam through which the organizational approval process reaches
    the authority. It must never be supplied by the party requesting issuance.
    """

    def verify_approval(
        self,
        *,
        coordinate: PolicyCoordinate,
        policy_body_digest: str,
        approval: ApprovalEvidenceRef,
        as_of: datetime,
    ) -> ApprovalVerification:
        """Return a structured verification, never raising for a plain refusal."""
        ...


class DenyAllApprovalVerifier:
    """The production default: no approval authority is wired up, so deny.

    Shipping this rather than an allow-all placeholder means an incompletely
    configured deployment cannot issue policy at all — the failure mode is a
    refusal, never an unapproved issuance.
    """

    def verify_approval(
        self,
        *,
        coordinate: PolicyCoordinate,
        policy_body_digest: str,
        approval: ApprovalEvidenceRef,
        as_of: datetime,
    ) -> ApprovalVerification:
        return ApprovalVerification(
            verified=False,
            status=ApprovalVerificationStatus.NO_APPROVAL_AUTHORITY_CONFIGURED,
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approving_authority_id=approval.approving_authority_id,
            approval_ref=approval.approval_ref,
            approval_digest=approval.approval_digest,
            verified_at=as_of,
            detail="no approval authority configured; issuance denied by default",
        )


def require_verified_approval(
    verification: object,
    *,
    coordinate: PolicyCoordinate,
    policy_body_digest: str,
    approval: ApprovalEvidenceRef,
    issuing_authority_id: str,
    as_of: datetime,
) -> ApprovalVerification:
    """Re-check a verifier's result and raise unless it truly binds this policy.

    Defence in depth. A verifier that is merely lax — returning ``APPROVED`` for
    a different policy, digest, tenant, or artifact, or naming the issuing
    authority as its own approver — is rejected here. A fabricated duck-typed
    return value is rejected too: only a real
    :class:`ApprovalVerification` (whose own constructor enforces the
    verified/status invariant) is accepted.

    Every failure raises :class:`PolicyApprovalError`, so no signature is
    produced and no registry mutation occurs.
    """

    if type(verification) is not ApprovalVerification:
        raise PolicyApprovalError(
            "approval verifier must return an ApprovalVerification "
            f"(got {type(verification).__name__})"
        )
    if not verification.verified or verification.status is not ApprovalVerificationStatus.APPROVED:
        raise PolicyApprovalError(
            f"approval not granted: {verification.status.value}"
            + (f" ({verification.detail})" if verification.detail else "")
        )

    if verification.coordinate != coordinate:
        raise PolicyApprovalError(
            "approval verification binds a different policy coordinate than the one "
            "being issued"
        )
    if verification.policy_body_digest != policy_body_digest:
        raise PolicyApprovalError("approval verification binds a different policy body digest")
    if verification.approval_ref != approval.approval_ref:
        raise PolicyApprovalError("approval verification names a different approval artifact")
    if verification.approval_digest != approval.approval_digest:
        raise PolicyApprovalError("approval verification binds a different approval digest")
    if verification.approving_authority_id != approval.approving_authority_id:
        raise PolicyApprovalError(
            "approval verification names a different approving authority than the "
            "supplied approval evidence"
        )

    # The Policy Authority can never be its own approver (P-5).
    if verification.approving_authority_id == issuing_authority_id:
        raise PolicyApprovalError(
            f"the issuing authority {issuing_authority_id!r} cannot approve its own "
            "policy; approval is an external responsibility"
        )

    # Half-open approved period: inclusive lower bound, exclusive upper bound.
    if verification.approved_from is not None and as_of < verification.approved_from:
        raise PolicyApprovalError("approval is not yet effective at the issuance instant")
    if verification.approved_to is not None and as_of >= verification.approved_to:
        raise PolicyApprovalError("approval has expired at the issuance instant")

    return verification
