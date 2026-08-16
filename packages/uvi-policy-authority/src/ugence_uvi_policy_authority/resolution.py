"""The single canonical trusted-resolution entry point (GV-2C-b §11).

:func:`resolve_policy` is the only supported way to turn a
:class:`PolicyReference` into a policy artifact you may rely on. It fails
closed: a policy is returned only when *every* condition below holds at the
explicit, timezone-aware ``as_of``, and the result shape makes it structurally
impossible to return a policy alongside a failed status.

Checks are evaluated in this fixed order, and exactly one reason is reported:

============================================  ===================================
condition                                     reason when it fails
============================================  ===================================
requested tenant/scope matches the reference  ``TENANT_SCOPE_MISMATCH``
a record exists under the exact reference     ``NOT_FOUND``
the stored record's reference is that one     ``REFERENCE_MISMATCH``
the artifact's metadata derives that ref      ``ARTIFACT_REFERENCE_MISMATCH``
recomputed body digest == content digest      ``CONTENT_DIGEST_MISMATCH``
recomputed body digest == signed body digest  ``BODY_DIGEST_MISMATCH``
key known / un-revoked / in window            ``KEY_UNKNOWN`` / ``KEY_REVOKED``
issuance signature verifies                   ``SIGNATURE_INVALID``
approval proof valid under the configured rule ``APPROVAL_PROOF_INVALID``
lifecycle is ``APPROVED_ACTIVE``               ``LIFECYCLE_NOT_ACTIVE`` / ``SUPERSEDED``
``as_of`` within the effective period          ``NOT_YET_EFFECTIVE`` / ``EXPIRED``
no targeted revocation applies                 ``REVOKED``
no undetermined supersession                   ``SUPERSESSION_UNDETERMINED``
============================================  ===================================

Registry lookup alone proves nothing: a record a caller assembled and appended
by hand reaches exactly the same digest, key and signature checks as an
authority-issued one, and fails them.

**Historical resolution.** Revocation is absolute at and after ``revoked_at``.
Whether a resolution with ``as_of`` strictly *before* ``revoked_at`` may still
succeed is an explicit, configured decision — :class:`HistoricalResolutionRule`
— and the default is :attr:`HistoricalResolutionRule.DENY_ALWAYS`, under which a
revoked version never resolves at any ``as_of``.

**Supersession.** See :class:`SupersessionRule`. The merged contracts carry
``supersedes_ref`` as an unstructured ``str``, which cannot bind a complete
exact reference, so the authority never infers a binding supersession from it —
it either ignores it (default) or fails closed with a typed deferred status.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import PolicyLifecycleState, PolicyReference

from .approval import ApprovalEvidenceRef, ApprovalVerifier, require_verified_approval
from .canonical import canonical_policy_body_digest
from .errors import PolicyApprovalError, PolicyAuthorityRequestError
from .records import PolicyResolution
from .registry import PolicyRegistry
from .signing import PolicySignatureVerifier
from .statuses import (
    HistoricalResolutionRule,
    KeyVerificationStatus,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    SupersessionRule,
)

__all__ = ["resolve_policy"]

_KEY_REASONS = {
    KeyVerificationStatus.UNKNOWN_KEY: PolicyResolutionReason.KEY_UNKNOWN,
    KeyVerificationStatus.REVOKED_KEY: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.KEY_NOT_IN_WINDOW: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.WRONG_AUTHORITY: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.WRONG_TENANT: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.NO_VERIFIER_CONFIGURED: PolicyResolutionReason.KEY_UNKNOWN,
    KeyVerificationStatus.INVALID_SIGNATURE: PolicyResolutionReason.SIGNATURE_INVALID,
}


def resolve_policy(
    *,
    reference: PolicyReference,
    expected_tenant_id: str,
    as_of: datetime,
    registry: PolicyRegistry,
    signature_verifier: PolicySignatureVerifier,
    approval_verifier: Optional[ApprovalVerifier] = None,
    historical_resolution: HistoricalResolutionRule = HistoricalResolutionRule.DENY_ALWAYS,
    supersession: SupersessionRule = SupersessionRule.SELF_DECLARED_ONLY,
) -> PolicyResolution:
    """Resolve one exact policy version under configured trust, or fail closed.

    ``approval_verifier`` is optional: when supplied, the approval proof stored
    on the issuance record is **re-verified** at ``as_of``, so an approval
    withdrawn after issuance invalidates resolution. When omitted, the approval
    bound into the issuance signature stands as the proof (the signature covers
    the approving authority and the approval artifact digest, so it cannot have
    been swapped) and no fresh check is performed.
    """

    if not isinstance(reference, PolicyReference):
        raise PolicyAuthorityRequestError("resolve_policy(reference) must be a PolicyReference")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.tzinfo.utcoffset(as_of) is None:
        raise PolicyAuthorityRequestError("resolve_policy(as_of) must be timezone-aware")
    if not isinstance(expected_tenant_id, str):
        raise PolicyAuthorityRequestError("resolve_policy(expected_tenant_id) must be a string")
    if not isinstance(historical_resolution, HistoricalResolutionRule):
        raise PolicyAuthorityRequestError(
            "resolve_policy(historical_resolution) must be a HistoricalResolutionRule"
        )
    if not isinstance(supersession, SupersessionRule):
        raise PolicyAuthorityRequestError(
            "resolve_policy(supersession) must be a SupersessionRule"
        )

    def deny(reason: PolicyResolutionReason, detail: str = "") -> PolicyResolution:
        return PolicyResolution.unresolved(
            reason, requested_reference=reference, as_of=as_of, detail=detail
        )

    # -- tenant / scope ----------------------------------------------------
    # Checked before the registry is touched, so a cross-tenant probe never even
    # reaches storage.
    if reference.tenant_id != expected_tenant_id:
        return deny(
            PolicyResolutionReason.TENANT_SCOPE_MISMATCH,
            "the reference is not scoped to the requesting tenant",
        )

    # -- exact lookup ------------------------------------------------------
    record = registry.get_issued(reference)
    if record is None:
        return deny(PolicyResolutionReason.NOT_FOUND, "no issuance record under this reference")

    if record.policy_reference != reference:
        return deny(
            PolicyResolutionReason.REFERENCE_MISMATCH,
            "the stored record does not carry the requested reference",
        )

    policy = record.policy
    metadata = policy.metadata

    # The artifact must itself derive the reference it was stored under, so a
    # record cannot pair one reference with a different policy body.
    if metadata.to_reference() != reference:
        return deny(
            PolicyResolutionReason.ARTIFACT_REFERENCE_MISMATCH,
            "the stored artifact's metadata does not derive the stored reference",
        )

    # -- digest binding ----------------------------------------------------
    recomputed = canonical_policy_body_digest(policy)
    if recomputed != metadata.content_digest:
        return deny(
            PolicyResolutionReason.CONTENT_DIGEST_MISMATCH,
            "the artifact body does not match its attested content digest",
        )
    if recomputed != record.policy_body_digest:
        return deny(
            PolicyResolutionReason.BODY_DIGEST_MISMATCH,
            "the artifact body does not match the digest bound into the signature",
        )

    # -- key + signature ---------------------------------------------------
    key_result = signature_verifier.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id=reference.tenant_id,
        as_of=as_of,
    )
    if not key_result.valid:
        return deny(
            _KEY_REASONS.get(key_result.status, PolicyResolutionReason.SIGNATURE_INVALID),
            key_result.detail,
        )

    # -- approval proof ----------------------------------------------------
    if approval_verifier is not None:
        evidence = ApprovalEvidenceRef(
            approval_ref=record.approval_ref,
            approval_digest=record.approval_digest,
            approving_authority_id=record.approving_authority_id,
        )
        try:
            verification = approval_verifier.verify_approval(
                policy_reference=reference,
                policy_body_digest=record.policy_body_digest,
                approval=evidence,
                as_of=as_of,
            )
            require_verified_approval(
                verification,
                policy_reference=reference,
                policy_body_digest=record.policy_body_digest,
                approval=evidence,
                issuing_authority_id=record.issuing_authority_id,
                as_of=as_of,
            )
        except PolicyApprovalError as exc:
            return deny(PolicyResolutionReason.APPROVAL_PROOF_INVALID, str(exc))

    # -- lifecycle ---------------------------------------------------------
    # A lifecycle label can never override time, and a valid time window can
    # never override an invalid lifecycle: both are checked, independently.
    if metadata.lifecycle_state is PolicyLifecycleState.SUPERSEDED:
        return deny(
            PolicyResolutionReason.SUPERSEDED, "the artifact declares itself superseded"
        )
    if metadata.lifecycle_state is not PolicyLifecycleState.APPROVED_ACTIVE:
        return deny(
            PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE,
            f"lifecycle state is {metadata.lifecycle_state.value}",
        )

    # -- effective period --------------------------------------------------
    # Half-open [effective_from, effective_to): lower bound inclusive, upper
    # bound exclusive, a missing upper bound open-ended.
    if metadata.effective_from is not None and as_of < metadata.effective_from:
        return deny(PolicyResolutionReason.NOT_YET_EFFECTIVE, "as_of precedes effective_from")
    if metadata.effective_to is not None and as_of >= metadata.effective_to:
        return deny(PolicyResolutionReason.EXPIRED, "as_of is at or after effective_to")

    # -- policy-version revocation ----------------------------------------
    # A recorded revocation denies on presence. Its own signature is *not*
    # required to be verifiable: an unverifiable revocation still denies, so the
    # failure direction here is closed, never open.
    for revocation in registry.revocations_for(reference):
        if as_of >= revocation.revoked_at:
            return deny(
                PolicyResolutionReason.REVOKED,
                f"revoked at {revocation.revoked_at.isoformat()} "
                f"({revocation.reason_code.value})",
            )
        if historical_resolution is HistoricalResolutionRule.DENY_ALWAYS:
            return deny(
                PolicyResolutionReason.REVOKED,
                "revoked; historical resolution before the revocation instant is not "
                "permitted under DENY_ALWAYS",
            )
        # ALLOW_BEFORE_REVOCATION: an explicitly historical as_of may proceed.

    # -- supersession ------------------------------------------------------
    if supersession is SupersessionRule.STRICT_UNDETERMINED_ON_SUCCESSOR:
        for other in registry.issued_records_for_identity(
            policy_id=reference.policy_id,
            policy_family=reference.policy_family,
            scope=reference.scope,
            tenant_id=reference.tenant_id,
        ):
            if other.policy_reference == reference:
                continue
            if (other.policy.metadata.supersedes_ref or "").strip():
                return deny(
                    PolicyResolutionReason.SUPERSESSION_UNDETERMINED,
                    "another issued version declares an unstructured supersedes_ref; the "
                    "merged contracts do not carry enough information to determine "
                    "whether it binds this version",
                )

    return PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_reference=reference,
        as_of=as_of,
        policy=policy,
        record=record,
    )
