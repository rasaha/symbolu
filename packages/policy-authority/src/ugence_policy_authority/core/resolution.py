"""The single canonical trusted-resolution entry point (ADR §15, §17).

:func:`resolve_policy` is the only supported way to turn a policy coordinate
into an artifact you may rely on. It fails closed: a policy is returned only
when *every* condition below holds at the explicit, timezone-aware ``as_of``,
and the result shape makes returning a policy alongside a failed status
structurally impossible.

Checks run in this fixed order; exactly one reason is reported:

=============================================  ==========================================
condition                                      reason when it fails
=============================================  ==========================================
requested tenant matches the coordinate        ``TENANT_SCOPE_MISMATCH``
a record exists under the exact coordinate     ``NOT_FOUND``
the stored record carries that coordinate      ``REFERENCE_MISMATCH``
a registered adapter still claims the artifact ``NO_ADAPTER_REGISTERED``
the artifact re-derives the same coordinate    ``ARTIFACT_REFERENCE_MISMATCH``
the artifact still canonicalizes               ``ARTIFACT_NOT_CANONICALIZABLE``
declared digest == recomputed body digest      ``CONTENT_DIGEST_MISMATCH``
signed body digest == recomputed body digest   ``BODY_DIGEST_MISMATCH``
key known / entitled / un-revoked / in window  ``KEY_UNKNOWN`` / ``KEY_REVOKED`` / ``KEY_NOT_ENTITLED``
issuance signature verifies                    ``SIGNATURE_INVALID``
approval proof valid (when re-verified)        ``APPROVAL_PROOF_INVALID``
no unstructured supersession declared          ``SUPERSESSION_REFERENCE_UNSUPPORTED``
lifecycle is active                            ``LIFECYCLE_NOT_ACTIVE``
``as_of`` inside the half-open interval        ``NOT_YET_EFFECTIVE`` / ``EXPIRED``
any revocation record verifies                 ``REVOCATION_INTEGRITY_INVALID``
no verified revocation applies                 ``REVOKED``
=============================================  ==========================================

What a resolution proves, and what it does not
----------------------------------------------
A ``RESOLVED`` answer proves that, **under the trust roots this call was
configured with** and at **this explicit ``as_of``**, the returned artifact was
signed by an authorized key of the named issuing authority over exactly this
body, that external approval evidence verified, that the lifecycle and
effective period admit it, and that no verified revocation applies.

It does **not** authorize any runtime action, does not prove organizational
truth beyond what the configured verifier attested, does not prove the policy
is correct or wise, and — when ``historical`` is set — does **not** imply
current validity.

A ``RESOLVED`` answer also carries the adapter descriptor's own projection —
``descriptor_adapter_id``, ``descriptor_policy_type`` and
``descriptor_canonical_projection`` — because the body-digest equality this
function enforces is otherwise unreproducible downstream: ``policy_body_digest``
is a one-way hash, and a consumer that registers no adapter cannot re-derive the
descriptor to check anything against it. Publishing the projection lets that
consumer recompute :func:`~.canonical.framed_body_digest` over the same frame
and reach the same digest. It is a *republication of an already-enforced
equality*, not an additional claim.

Registry retrieval is **not** resolution, and constructing a record or a
resolution object proves nothing: both are public dataclasses, and a
hand-assembled record reaches every digest, key and signature check here and
fails them.

``expected_reference_tenant_id`` checks the **reference's declared tenant
identity**, not the caller's entitlement — this authority performs no caller
authorization. A ``GLOBAL``-scope coordinate carries the canonical empty tenant
component (:data:`~ugence_policy_authority.core.adapters.GLOBAL_TENANT`) and
matches only a request presenting exactly that.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .adapters import AdapterRegistry, PolicyCoordinate
from .approval import ApprovalEvidenceRef, ApprovalVerifier, require_verified_approval
from .canonical import require_tzaware
from .errors import (
    PolicyApprovalError,
    PolicyAuthorityRequestError,
    PolicyCanonicalizationError,
    UnsupportedPolicyArtifactError,
)
from .records import PolicyResolution
from .registry import PolicyRegistry
from .revocation import verify_revocation_record
from .signing import PolicySignatureVerifier
from .statuses import (
    HistoricalResolutionRule,
    KeyEntitlement,
    KeyVerificationStatus,
    PolicyResolutionReason,
    PolicyResolutionStatus,
)

__all__ = ["resolve_policy"]

_KEY_REASONS = {
    KeyVerificationStatus.UNKNOWN_KEY: PolicyResolutionReason.KEY_UNKNOWN,
    KeyVerificationStatus.REVOKED_KEY: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.KEY_NOT_IN_WINDOW: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.WRONG_AUTHORITY: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.WRONG_TENANT: PolicyResolutionReason.KEY_REVOKED,
    KeyVerificationStatus.NOT_ENTITLED: PolicyResolutionReason.KEY_NOT_ENTITLED,
    KeyVerificationStatus.NO_VERIFIER_CONFIGURED: PolicyResolutionReason.KEY_UNKNOWN,
    KeyVerificationStatus.INVALID_SIGNATURE: PolicyResolutionReason.SIGNATURE_INVALID,
}


def resolve_policy(
    *,
    reference: object,
    expected_reference_tenant_id: str,
    as_of: datetime,
    registry: PolicyRegistry,
    signature_verifier: PolicySignatureVerifier,
    adapters: AdapterRegistry,
    approval_verifier: Optional[ApprovalVerifier] = None,
    historical_resolution: HistoricalResolutionRule = HistoricalResolutionRule.DENY_ALWAYS,
) -> PolicyResolution:
    """Resolve one exact policy version under configured trust, or fail closed.

    ``approval_verifier`` is optional. When supplied, the approval proof bound
    into the issuance record is **re-verified** at ``as_of``, so an approval
    withdrawn after issuance invalidates resolution. When omitted, the approval
    bound into the issuance signature stands as the proof — the signature covers
    the approving authority and the approval artifact digest, so neither can
    have been swapped.
    """

    if not isinstance(adapters, AdapterRegistry):
        raise PolicyAuthorityRequestError("resolve_policy(adapters) must be an AdapterRegistry")
    if not isinstance(expected_reference_tenant_id, str):
        raise PolicyAuthorityRequestError(
            "resolve_policy(expected_reference_tenant_id) must be a string"
        )
    if not isinstance(historical_resolution, HistoricalResolutionRule):
        raise PolicyAuthorityRequestError(
            "resolve_policy(historical_resolution) must be a HistoricalResolutionRule"
        )
    as_of = require_tzaware(as_of, path="resolve_policy(as_of)")
    coordinate: PolicyCoordinate = adapters.coordinate_for(reference)

    def deny(reason: PolicyResolutionReason, detail: str = "") -> PolicyResolution:
        return PolicyResolution.unresolved(
            reason, requested_coordinate=coordinate, as_of=as_of, detail=detail
        )

    # -- tenant / scope ----------------------------------------------------
    # Checked before storage is touched, so a cross-tenant probe never reaches
    # the registry and the answer discloses no other tenant's identifiers.
    if coordinate.tenant_id != expected_reference_tenant_id:
        return deny(
            PolicyResolutionReason.TENANT_SCOPE_MISMATCH,
            "the reference's declared tenant is not the expected reference tenant",
        )

    # -- exact lookup ------------------------------------------------------
    record = registry.get_issued(coordinate)
    if record is None:
        return deny(PolicyResolutionReason.NOT_FOUND, "no issuance record under this coordinate")
    if record.coordinate != coordinate:
        return deny(
            PolicyResolutionReason.REFERENCE_MISMATCH,
            "the stored record does not carry the requested coordinate",
        )

    policy = record.policy

    # -- re-describe the artifact through its adapter ---------------------
    try:
        descriptor = adapters.describe(policy)
    except UnsupportedPolicyArtifactError:
        return deny(
            PolicyResolutionReason.NO_ADAPTER_REGISTERED,
            "no registered adapter claims the stored artifact",
        )
    except PolicyCanonicalizationError as exc:
        return deny(PolicyResolutionReason.ARTIFACT_NOT_CANONICALIZABLE, str(exc))
    except PolicyAuthorityRequestError as exc:
        return deny(PolicyResolutionReason.ARTIFACT_REFERENCE_MISMATCH, str(exc))

    if descriptor.coordinate != coordinate:
        return deny(
            PolicyResolutionReason.ARTIFACT_REFERENCE_MISMATCH,
            "the stored artifact does not re-derive the stored coordinate",
        )

    # -- digest binding ----------------------------------------------------
    try:
        recomputed = descriptor.body_digest()
    except PolicyCanonicalizationError as exc:
        return deny(PolicyResolutionReason.ARTIFACT_NOT_CANONICALIZABLE, str(exc))

    if recomputed != descriptor.declared_content_digest:
        return deny(
            PolicyResolutionReason.CONTENT_DIGEST_MISMATCH,
            "the artifact body does not match its declared content digest",
        )
    if recomputed != record.policy_body_digest:
        return deny(
            PolicyResolutionReason.BODY_DIGEST_MISMATCH,
            "the artifact body does not match the digest bound into the signature",
        )

    # -- issuance key + signature -----------------------------------------
    key_result = signature_verifier.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.issuing_authority_id,
        expected_tenant_id=coordinate.tenant_id,
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
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
            require_verified_approval(
                approval_verifier.verify_approval(
                    coordinate=coordinate,
                    policy_body_digest=record.policy_body_digest,
                    approval=evidence,
                    as_of=as_of,
                ),
                coordinate=coordinate,
                policy_body_digest=record.policy_body_digest,
                approval=evidence,
                issuing_authority_id=record.issuing_authority_id,
                as_of=as_of,
            )
        except PolicyApprovalError as exc:
            return deny(PolicyResolutionReason.APPROVAL_PROOF_INVALID, str(exc))

    # -- unstructured supersession ----------------------------------------
    # v0.1 refuses to issue such an artifact at all; a legacy or hand-assembled
    # record that reaches here fails closed rather than being guessed at.
    if descriptor.declares_supersession:
        return deny(
            PolicyResolutionReason.SUPERSESSION_REFERENCE_UNSUPPORTED,
            "the stored artifact declares a non-empty unstructured supersedes_ref, which "
            "cannot bind an exact predecessor; structured successor references are deferred",
        )

    # -- lifecycle ---------------------------------------------------------
    # A lifecycle label can never override time, and a valid time window can
    # never override an invalid lifecycle: both are checked independently.
    if not descriptor.lifecycle_is_active:
        return deny(
            PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE,
            f"lifecycle state is {descriptor.lifecycle_label}",
        )

    # -- effective period --------------------------------------------------
    # Half-open [effective_from, effective_to): lower inclusive, upper
    # exclusive, a missing bound open-ended.
    if descriptor.effective_from is not None and as_of < descriptor.effective_from:
        return deny(PolicyResolutionReason.NOT_YET_EFFECTIVE, "as_of precedes effective_from")
    if descriptor.effective_to is not None and as_of >= descriptor.effective_to:
        return deny(PolicyResolutionReason.EXPIRED, "as_of is at or after effective_to")

    # -- policy-version revocation ----------------------------------------
    # Every stored revocation is verified before it is applied. An unverifiable
    # one neither denies as a valid revocation nor is ignored: it fails closed
    # as an integrity error (ADR §14.7).
    historical = False
    for revocation in registry.revocations_for(coordinate):
        verification = verify_revocation_record(
            revocation,
            coordinate=coordinate,
            signature_verifier=signature_verifier,
            as_of=as_of,
        )
        if not verification.valid:
            return deny(
                PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID,
                f"a revocation record targets this version but does not verify: "
                f"{verification.status.value}",
            )
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
        # ALLOW_BEFORE_REVOCATION: the answer is explicitly historical and is
        # labelled so it can never be read as current validity.
        historical = True

    return PolicyResolution(
        status=PolicyResolutionStatus.RESOLVED,
        reason=PolicyResolutionReason.RESOLVED,
        requested_coordinate=coordinate,
        as_of=as_of,
        policy=policy,
        record=record,
        historical=historical,
        detail=(
            "historical answer for an as_of before a verified revocation; this does not "
            "imply current validity"
            if historical
            else ""
        ),
        # The descriptor whose body digest was proven equal to
        # ``record.policy_body_digest`` above, published so a consumer holding no
        # adapter registry can rebuild the same frame and reach the same digest.
        # Nothing new is asserted here: the equality is already a precondition of
        # arriving at this return.
        descriptor_adapter_id=descriptor.adapter_id,
        descriptor_policy_type=descriptor.policy_type,
        descriptor_canonical_projection=descriptor.canonical_projection,
    )
