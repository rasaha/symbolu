"""The injected approval-verification boundary (GV-2C-b §5).

**Approval is not this package's job.** Deciding that a policy's content is
correct, lawful, and worth adopting is an external human/governance
responsibility. What the Policy Authority owns is the *technical* refusal to
issue anything that is not accompanied by verified external approval evidence.

The boundary is deliberately narrow:

* the caller supplies an :class:`ApprovalEvidenceRef` — a pointer to an
  externally produced approval artifact plus that artifact's digest;
* an injected :class:`ApprovalVerifier` resolves it and returns a structured
  :class:`ApprovalVerification` that **binds** the exact policy identity,
  version, family, tenant/scope, policy-content digest, approving authority,
  approval artifact, and the verification time / approved period;
* the authority then independently re-checks that binding (see
  :func:`require_verified_approval`) before anything is signed or stored.

What is explicitly **not** approval:

* a caller-supplied ``approved=True`` boolean — no such parameter exists;
* a caller-supplied authority *name* — a bare string names nobody;
* an enum label such as ``PolicyLifecycleState.APPROVED_ACTIVE`` on the
  artifact — that is a self-assertion the artifact makes about itself;
* an evidence-status enum of any kind.

The only verifier shipped in production code is
:class:`DenyAllApprovalVerifier`. Deterministic fakes that return
``APPROVED`` exist **only** under ``tests/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_uvi_policy_contracts.api import PolicyReference

from .errors import PolicyApprovalError, PolicyAuthorityRequestError
from .statuses import ApprovalVerificationStatus

__all__ = [
    "ApprovalEvidenceRef",
    "ApprovalVerification",
    "ApprovalVerifier",
    "DenyAllApprovalVerifier",
    "require_verified_approval",
]


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise PolicyAuthorityRequestError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise PolicyAuthorityRequestError(f"{name} must be timezone-aware")
    return value


def _require_digest(value: object, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise PolicyAuthorityRequestError(f"{name} must be a 64-char sha-256 hex digest")
    if any(c not in "0123456789abcdef" for c in value):
        raise PolicyAuthorityRequestError(f"{name} must be a lowercase sha-256 hex digest")
    return value


def _require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")
    return value


@dataclass(frozen=True)
class ApprovalEvidenceRef:
    """A pointer to an externally produced approval artifact.

    Carries no approval *decision* of its own — only where the artifact lives
    and what its bytes digest to, so a verifier can fetch it and the authority
    can bind the exact artifact it was shown into the issuance signature.
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

    Binds the exact policy identity (via :class:`PolicyReference`, which itself
    binds id + family + version + content digest + scope + tenant), the
    approving authority, the approval artifact and its digest, the verification
    time, and optionally the approved effective period.

    ``verified`` and ``status`` are kept consistent structurally: only
    :attr:`ApprovalVerificationStatus.APPROVED` may set ``verified=True``.
    """

    verified: bool
    status: ApprovalVerificationStatus
    policy_reference: PolicyReference
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
        if self.verified and self.status is not ApprovalVerificationStatus.APPROVED:
            raise PolicyAuthorityRequestError(
                "ApprovalVerification.verified may only be True for status APPROVED"
            )
        if not self.verified and self.status is ApprovalVerificationStatus.APPROVED:
            raise PolicyAuthorityRequestError(
                "ApprovalVerification status APPROVED requires verified=True"
            )
        if not isinstance(self.policy_reference, PolicyReference):
            raise PolicyAuthorityRequestError(
                "ApprovalVerification.policy_reference must be a PolicyReference"
            )
        _require_digest(self.policy_body_digest, "ApprovalVerification.policy_body_digest")
        _require_nonempty(
            self.approving_authority_id, "ApprovalVerification.approving_authority_id"
        )
        _require_nonempty(self.approval_ref, "ApprovalVerification.approval_ref")
        _require_digest(self.approval_digest, "ApprovalVerification.approval_digest")
        _require_tzaware(self.verified_at, "ApprovalVerification.verified_at")
        for name in ("approved_from", "approved_to"):
            value = getattr(self, name)
            if value is not None:
                _require_tzaware(value, f"ApprovalVerification.{name}")
        if self.approved_from is not None and self.approved_to is not None:
            if not self.approved_from < self.approved_to:
                raise PolicyAuthorityRequestError(
                    "ApprovalVerification.approved_from must be before approved_to"
                )


@runtime_checkable
class ApprovalVerifier(Protocol):
    """Resolve and verify external approval evidence for one exact policy.

    An implementation must be a *trusted* dependency of the deployment: it is
    the seam through which the organizational approval process reaches the
    authority. It must never be implemented by the caller requesting issuance.
    """

    def verify_approval(
        self,
        *,
        policy_reference: PolicyReference,
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
        policy_reference: PolicyReference,
        policy_body_digest: str,
        approval: ApprovalEvidenceRef,
        as_of: datetime,
    ) -> ApprovalVerification:
        return ApprovalVerification(
            verified=False,
            status=ApprovalVerificationStatus.NO_APPROVAL_AUTHORITY_CONFIGURED,
            policy_reference=policy_reference,
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
    policy_reference: PolicyReference,
    policy_body_digest: str,
    approval: ApprovalEvidenceRef,
    issuing_authority_id: str,
    as_of: datetime,
) -> ApprovalVerification:
    """Re-check a verifier's result and raise unless it truly binds this policy.

    Defence in depth: a verifier that is merely lax — returning ``APPROVED`` for
    a different policy, a different digest, a different tenant, or with the
    issuing authority named as its own approver — is still rejected here. Every
    failure mode raises :class:`PolicyApprovalError`, so no signature is
    produced and no registry mutation occurs.
    """

    if not isinstance(verification, ApprovalVerification):
        raise PolicyApprovalError(
            "approval verifier must return an ApprovalVerification "
            f"(got {type(verification).__name__})"
        )
    if not verification.verified or verification.status is not ApprovalVerificationStatus.APPROVED:
        raise PolicyApprovalError(
            f"approval not granted: {verification.status.value}"
            + (f" ({verification.detail})" if verification.detail else "")
        )

    # The verification must bind *this* policy, on every identity component the
    # reference carries (id, family, version, content digest, scope, tenant).
    if verification.policy_reference != policy_reference:
        raise PolicyApprovalError(
            "approval verification binds a different policy reference than the one "
            "being issued"
        )
    if verification.policy_body_digest != policy_body_digest:
        raise PolicyApprovalError(
            "approval verification binds a different policy body digest"
        )
    if verification.approval_ref != approval.approval_ref:
        raise PolicyApprovalError("approval verification names a different approval artifact")
    if verification.approval_digest != approval.approval_digest:
        raise PolicyApprovalError("approval verification binds a different approval digest")
    if verification.approving_authority_id != approval.approving_authority_id:
        raise PolicyApprovalError(
            "approval verification names a different approving authority than the "
            "supplied approval evidence"
        )

    # The Policy Authority can never be its own approver.
    if verification.approving_authority_id == issuing_authority_id:
        raise PolicyApprovalError(
            f"the issuing authority {issuing_authority_id!r} cannot approve its own "
            "policy; approval is an external responsibility"
        )

    # The approved period, when supplied, must contain the operation instant —
    # inclusive lower bound, exclusive upper bound, matching the contracts'
    # effective-period semantics.
    if verification.approved_from is not None and as_of < verification.approved_from:
        raise PolicyApprovalError("approval is not yet effective at the issuance instant")
    if verification.approved_to is not None and as_of >= verification.approved_to:
        raise PolicyApprovalError("approval has expired at the issuance instant")

    return verification
