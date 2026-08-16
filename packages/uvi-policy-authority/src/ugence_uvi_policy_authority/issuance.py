"""The single canonical issuance entry point (GV-2C-b §10).

:func:`issue_policy` is the only way an :class:`IssuedPolicyRecord` enters the
authority's own trust chain. It executes a fixed order and is written so each
stage's side effects are impossible before the previous stage succeeded:

1. **structural request validation** — every argument's type and shape,
   including that ``issued_at`` is a timezone-aware datetime (the minimum
   validated operation timestamp);
2. **supported-family and identity validation** — exact runtime type, declared
   family agreement, and that the artifact's own metadata derives the reference
   being issued;
3. **canonical body / digest verification** — the body digest is recomputed and
   compared to the artifact's attested ``content_digest``;
4. **approval verification** — the injected verifier is called and its result is
   independently re-checked;
5. **explicit timestamp validation** — lifecycle and effective-period
   admissibility evaluated at ``issued_at``;
6. **signature production** — the injected signer is called;
7. **immutable record construction**;
8. **atomic registry append**.

Proven by tests: the signer is never called when approval fails; the approval
verifier is never called when an earlier structural stage fails; and the
registry is byte-for-byte unchanged after a failure at *any* stage.

**The clock is injected.** No ``datetime.now``, ``datetime.utcnow`` or any other
implicit wall clock exists anywhere in this package — an automated test asserts
that over the whole source tree. The documented convention is deliberately
strict: **a successful issuance reads exactly one caller-supplied instant,
``issued_at``, and derives every timestamp from it** — the approval
verification ``as_of``, the effective-period check, the signed payload and the
record's ``issued_at`` are all that one value. The same inputs therefore
produce byte-identical records on every run.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import (
    PolicyLifecycleState,
    PolicyReference,
)

from .approval import ApprovalEvidenceRef, ApprovalVerifier, require_verified_approval
from .canonical import canonical_policy_body_digest
from .errors import (
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicySigningError,
)
from .families import UVIPolicy, require_supported_policy
from .payload import issuance_signing_payload
from .records import IssuedPolicyRecord
from .registry import PolicyRegistry
from .signing import PolicySigner
from .statuses import AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_VERSION

__all__ = ["issue_policy"]


def _require_tzaware(value: object, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise PolicyAuthorityRequestError(f"{name} must be a datetime")
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise PolicyAuthorityRequestError(f"{name} must be timezone-aware")
    return value


def _require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")
    return value


def issue_policy(
    *,
    policy: UVIPolicy,
    record_id: str,
    approval: ApprovalEvidenceRef,
    approval_verifier: ApprovalVerifier,
    signer: PolicySigner,
    registry: PolicyRegistry,
    issued_at: datetime,
    expected_tenant_id: Optional[str] = None,
) -> IssuedPolicyRecord:
    """Issue, sign, and register one exact UVI policy version.

    There is no ``approved`` flag, no ``signature`` parameter, and no
    ``authority`` string that grants anything: approval arrives only as external
    evidence a trusted verifier confirms, and the signature is produced here.

    Raises a typed :class:`~ugence_uvi_policy_authority.errors.PolicyAuthorityError`
    subclass on every failure, leaving the registry untouched.
    """

    # -- 1. Structural request validation ---------------------------------
    _require_nonempty(record_id, "issue_policy(record_id)")
    if not isinstance(approval, ApprovalEvidenceRef):
        raise PolicyAuthorityRequestError(
            "issue_policy(approval) must be an ApprovalEvidenceRef; a boolean, an "
            "authority name, or a status label is not approval evidence"
        )
    if not hasattr(approval_verifier, "verify_approval"):
        raise PolicyAuthorityRequestError(
            "issue_policy(approval_verifier) must implement ApprovalVerifier"
        )
    for attr in ("authority_id", "key_id", "signature_alg", "sign"):
        if not hasattr(signer, attr):
            raise PolicyAuthorityRequestError(
                "issue_policy(signer) must implement PolicySigner"
            )
    for attr in ("append_issuance", "get_issued"):
        if not hasattr(registry, attr):
            raise PolicyAuthorityRequestError(
                "issue_policy(registry) must implement PolicyRegistry"
            )
    # The minimum validated operation timestamp — the only clock read, and the
    # only thing permitted before approval verification.
    issued_at = _require_tzaware(issued_at, "issue_policy(issued_at)")

    issuing_authority_id = _require_nonempty(signer.authority_id, "signer.authority_id")
    key_id = _require_nonempty(signer.key_id, "signer.key_id")
    signature_alg = _require_nonempty(signer.signature_alg, "signer.signature_alg")

    # -- 2. Supported-family and identity validation ----------------------
    family = require_supported_policy(policy)
    metadata = policy.metadata
    reference: PolicyReference = metadata.to_reference()

    if reference.policy_family is not family:
        raise PolicyAuthorityRequestError(
            "the artifact's derived reference does not name its own family"
        )
    if expected_tenant_id is not None and reference.tenant_id != expected_tenant_id:
        raise PolicyAuthorityRequestError(
            f"policy tenant {reference.tenant_id!r} does not match the expected tenant "
            f"{expected_tenant_id!r}"
        )

    # -- 3. Canonical body / digest verification --------------------------
    policy_body_digest = canonical_policy_body_digest(policy)
    if metadata.content_digest != policy_body_digest:
        raise PolicyDigestMismatchError(
            "the artifact's attested content_digest does not bind its canonical body; "
            "a well-formed 64-hex string is not evidence that the body matches it"
        )

    # -- 4. Approval verification (before any signing or mutation) --------
    verification = approval_verifier.verify_approval(
        policy_reference=reference,
        policy_body_digest=policy_body_digest,
        approval=approval,
        as_of=issued_at,
    )
    verification = require_verified_approval(
        verification,
        policy_reference=reference,
        policy_body_digest=policy_body_digest,
        approval=approval,
        issuing_authority_id=issuing_authority_id,
        as_of=issued_at,
    )

    # -- 5. Explicit timestamp validation ---------------------------------
    # A policy is issued as *active* or not at all. DRAFT, EXPIRED, REVOKED and
    # SUPERSEDED artifacts remain constructible for audit but are never issued.
    if metadata.lifecycle_state is not PolicyLifecycleState.APPROVED_ACTIVE:
        raise PolicyIssuanceError(
            f"cannot issue a {metadata.lifecycle_state.value} artifact as an active "
            "policy; only APPROVED_ACTIVE is issuable"
        )
    # Issuance-time effective-period rules. These do not replace the
    # resolution-time checks: a policy whose window opens later is issuable, and
    # resolution before that instant still fails closed as NOT_YET_EFFECTIVE.
    if metadata.effective_to is not None and issued_at >= metadata.effective_to:
        raise PolicyIssuanceError(
            "cannot issue a policy whose effective period has already elapsed at the "
            "issuance instant"
        )

    # -- 6. Signature production ------------------------------------------
    payload = issuance_signing_payload(
        record_id=record_id,
        reference=reference,
        policy_body_digest=policy_body_digest,
        approving_authority_id=verification.approving_authority_id,
        approval_ref=verification.approval_ref,
        approval_digest=verification.approval_digest,
        issuing_authority_id=issuing_authority_id,
        key_id=key_id,
        signature_alg=signature_alg,
        issued_at=issued_at,
    )
    signature = signer.sign(payload)
    if not isinstance(signature, (bytes, bytearray)) or not signature:
        raise PolicySigningError("signer returned no signature material")

    # -- 7. Immutable record construction ---------------------------------
    record = IssuedPolicyRecord(
        record_id=record_id,
        policy_reference=reference,
        policy_family=family,
        policy=policy,
        policy_body_digest=policy_body_digest,
        issuing_authority_id=issuing_authority_id,
        key_id=key_id,
        signature_alg=signature_alg,
        signature=bytes(signature),
        approving_authority_id=verification.approving_authority_id,
        approval_ref=verification.approval_ref,
        approval_digest=verification.approval_digest,
        issued_at=issued_at,
        authority_protocol=AUTHORITY_PROTOCOL,
        authority_protocol_version=AUTHORITY_PROTOCOL_VERSION,
    )

    # -- 8. Atomic registry append ----------------------------------------
    # The only mutation in the whole function, and the last thing that happens.
    return registry.append_issuance(record)
