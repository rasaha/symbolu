"""The single canonical issuance entry point (ADR §11, §13).

:func:`issue_policy` is the only way an
:class:`~ugence_policy_authority.core.records.IssuedPolicyRecord` enters the
authority's trust chain. It executes a fixed, observable order, and each
stage's collaborators are unreachable until the previous stage has succeeded:

1. **request structure** — argument types and shapes, including that
   ``issued_at`` is a timezone-aware datetime (validated, not yet *used*);
2. **adapter/family recognition** — a registered adapter must claim the artifact;
3. **exact identity derivation** — the adapter yields the complete coordinate;
4. **supersession admissibility** — a non-empty unstructured ``supersedes_ref``
   is rejected here, before any collaborator is touched; a **structured**
   predecessor coordinate (`ACC-LC-IA-1`) is checked for admissibility here
   too, which reads the registry (`ACC-LC-IA-3`);
5. **canonical body digest and declared-digest equality**;
6. **approval verification**;
7. **lifecycle/effectivity at the explicit issuance instant**;
8. **signing**;
9. **record construction**;
10. **atomic process-local registry append** — the successor and, when one is
    declared, its supersession record, as one act (`ACC-LC-2`).

Proven by instrumented call-count tests: a structural, family, supersession or
digest failure never invokes the approval verifier; an approval failure never
invokes the signer; a signing failure never mutates the registry; and the
registry is byte-identical after a failure at *any* stage.

**What step 4 may touch.** It reads the registry when a structured predecessor
is declared — the predecessor must exist and be admissible before anything is
signed. The guarantee is and remains that **nothing from a rejected artifact is
stored**: reads mutate nothing, and no append happens anywhere but step 10.

**Determinism.** No wall clock, no random UUID, no environment lookup, no
network call, no hidden global state. The issuance instant is injected and read
exactly once; identical inputs produce byte-identical records.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .adapters import AdapterRegistry, PolicyCoordinate
from .approval import ApprovalEvidenceRef, ApprovalVerifier, require_verified_approval
from .canonical import require_tzaware
from .errors import (
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicySigningError,
    PolicySupersessionError,
    UnsupportedSupersessionError,
)
from .payload import issuance_signing_payload
from .records import IssuedPolicyRecord, PolicySupersessionRecord
from .registry import PolicyRegistry
from .payload import supersession_signing_payload
from .signing import PolicySignatureVerifier, PolicySigner
from .supersession import (
    require_admissible_supersession,
    verify_supersession_record,
)
from .statuses import AUTHORITY_PROTOCOL, AUTHORITY_PROTOCOL_VERSION

__all__ = ["issue_policy", "SUPERSESSION_REFERENCE_UNSUPPORTED"]

#: The stable typed reason a non-empty unstructured supersession reference is
#: refused. Exposed as a constant so consumers can branch on the exact token
#: without string-matching a message.
SUPERSESSION_REFERENCE_UNSUPPORTED = "SUPERSESSION_REFERENCE_UNSUPPORTED"


def _require_nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyAuthorityRequestError(f"{name} must be a non-empty string")
    return value


def issue_policy(
    *,
    policy: object,
    record_id: str,
    approval: ApprovalEvidenceRef,
    approval_verifier: ApprovalVerifier,
    signer: PolicySigner,
    registry: PolicyRegistry,
    adapters: AdapterRegistry,
    issued_at: datetime,
    expected_reference_tenant_id: Optional[str] = None,
    supersession_id: Optional[str] = None,
    signature_verifier: Optional[PolicySignatureVerifier] = None,
) -> IssuedPolicyRecord:
    """Issue, sign, and register one exact policy version.

    There is no ``approved`` flag, no ``signature`` parameter, and no authority
    string that grants anything: approval arrives only as external evidence a
    trusted verifier confirms, and the signature is produced here.

    Raises a typed
    :class:`~ugence_policy_authority.core.errors.PolicyAuthorityError` subclass
    on every failure, leaving the registry untouched.
    """

    # -- 1. Request structure ---------------------------------------------
    _require_nonempty(record_id, "issue_policy(record_id)")
    if type(approval) is not ApprovalEvidenceRef:
        raise PolicyAuthorityRequestError(
            "issue_policy(approval) must be an ApprovalEvidenceRef; a boolean, an "
            "authority name, a status label, or a duck-typed stand-in is not approval "
            "evidence"
        )
    if not hasattr(approval_verifier, "verify_approval"):
        raise PolicyAuthorityRequestError(
            "issue_policy(approval_verifier) must implement ApprovalVerifier"
        )
    for attribute in ("authority_id", "key_id", "signature_alg", "sign"):
        if not hasattr(signer, attribute):
            raise PolicyAuthorityRequestError("issue_policy(signer) must implement PolicySigner")
    for attribute in ("append_issuance", "get_issued"):
        if not hasattr(registry, attribute):
            raise PolicyAuthorityRequestError(
                "issue_policy(registry) must implement PolicyRegistry"
            )
    if not isinstance(adapters, AdapterRegistry):
        raise PolicyAuthorityRequestError("issue_policy(adapters) must be an AdapterRegistry")
    # Validated here; *used* from stage 6 onward. Validation is not a clock read.
    issued_at = require_tzaware(issued_at, path="issue_policy(issued_at)")

    issuing_authority_id = _require_nonempty(signer.authority_id, "signer.authority_id")
    key_id = _require_nonempty(signer.key_id, "signer.key_id")
    signature_alg = _require_nonempty(signer.signature_alg, "signer.signature_alg")

    # -- 2/3. Adapter recognition and exact identity derivation -----------
    descriptor = adapters.describe(policy)
    coordinate: PolicyCoordinate = descriptor.coordinate

    if (
        expected_reference_tenant_id is not None
        and coordinate.tenant_id != expected_reference_tenant_id
    ):
        raise PolicyAuthorityRequestError(
            f"the artifact's declared tenant {coordinate.tenant_id!r} does not match the "
            f"expected reference tenant {expected_reference_tenant_id!r}"
        )

    # -- 4. Supersession admissibility ------------------------------------
    # Before the digest, before approval, before any clock use, before signing,
    # and before any registry access. Nothing from a rejected artifact is stored.
    if descriptor.declares_supersession:
        raise UnsupportedSupersessionError(
            f"{SUPERSESSION_REFERENCE_UNSUPPORTED}: the artifact declares a non-empty "
            f"unstructured supersedes_ref ({descriptor.supersedes_ref!r}). It cannot bind a "
            "complete exact policy coordinate, and guessing one would be an unsigned "
            "authority decision. Structured successor references are a separate, deferred "
            "contract milestone; nothing has been signed or registered."
        )

    # A structured predecessor (`ACC-LC-IA-1`) is admissible only if it exists
    # and is replaceable. This reads the registry; it writes nothing, and every
    # refusal below precedes the approval verifier, the signer and step 10.
    predecessor: Optional[PolicyCoordinate] = descriptor.supersedes_coordinate
    if predecessor is not None:
        if not isinstance(supersession_id, str) or not supersession_id.strip():
            raise PolicyAuthorityRequestError(
                "issue_policy(supersession_id) must be a non-empty string when the "
                "artifact declares a structured predecessor: the supersession record "
                "is signed, and a signed record needs an identity"
            )
        if signature_verifier is None or not hasattr(signature_verifier, "verify"):
            raise PolicyAuthorityRequestError(
                "issue_policy(signature_verifier) is mandatory when the artifact "
                "declares a structured predecessor — the superseding key's "
                "entitlement must be proven before the record is stored"
            )
        require_admissible_supersession(
            predecessor=predecessor,
            successor=coordinate,
            registry=registry,
            as_of=issued_at,
        )

    # -- 5. Canonical body digest and declared-digest equality ------------
    policy_body_digest = descriptor.body_digest()
    if descriptor.declared_content_digest != policy_body_digest:
        raise PolicyDigestMismatchError(
            "the artifact's declared content_digest does not bind its canonical body; a "
            "well-formed 64-hex string is not evidence that the body matches it"
        )
    if coordinate.content_digest != policy_body_digest:
        raise PolicyDigestMismatchError(
            "the artifact's derived coordinate does not carry its computed body digest"
        )

    # -- 6. Approval verification (before any signing or mutation) --------
    verification = require_verified_approval(
        approval_verifier.verify_approval(
            coordinate=coordinate,
            policy_body_digest=policy_body_digest,
            approval=approval,
            as_of=issued_at,
        ),
        coordinate=coordinate,
        policy_body_digest=policy_body_digest,
        approval=approval,
        issuing_authority_id=issuing_authority_id,
        as_of=issued_at,
    )

    # -- 7. Lifecycle and effectivity at the explicit issuance instant ----
    if not descriptor.lifecycle_is_active:
        raise PolicyIssuanceError(
            f"cannot issue a {descriptor.lifecycle_label} artifact as an active policy; "
            "only an active lifecycle state is issuable"
        )
    if descriptor.effective_to is not None and issued_at >= descriptor.effective_to:
        raise PolicyIssuanceError(
            "cannot issue a policy whose effective period has already elapsed at the "
            "issuance instant"
        )

    # -- 8. Signing --------------------------------------------------------
    payload = issuance_signing_payload(
        record_id=record_id,
        coordinate=coordinate,
        adapter_id=descriptor.adapter_id,
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

    # -- 9. Record construction -------------------------------------------
    record = IssuedPolicyRecord(
        record_id=record_id,
        coordinate=coordinate,
        adapter_id=descriptor.adapter_id,
        policy_type=descriptor.policy_type,
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

    # -- 10. Atomic process-local registry append -------------------------
    # The only mutation in the whole function, and the last thing that happens.
    if predecessor is None:
        return registry.append_issuance(record)

    # `ACC-LC-2`: one signed act admits the successor and stops the predecessor
    # resolving. The supersession is signed by the issuing key, in this act, and
    # its entitlement is proven before it is stored.
    supersession_signature = signer.sign(
        supersession_signing_payload(
            supersession_id=supersession_id,
            coordinate=predecessor,
            successor_coordinate=coordinate,
            superseding_authority_id=issuing_authority_id,
            key_id=key_id,
            signature_alg=signature_alg,
            superseded_at=issued_at,
        )
    )
    if not isinstance(supersession_signature, (bytes, bytearray)) or not (
        supersession_signature
    ):
        raise PolicySigningError("signer returned no supersession signature material")

    supersession = PolicySupersessionRecord(
        supersession_id=supersession_id,
        coordinate=predecessor,
        successor_coordinate=coordinate,
        superseding_authority_id=issuing_authority_id,
        key_id=key_id,
        signature_alg=signature_alg,
        signature=bytes(supersession_signature),
        superseded_at=issued_at,
    )
    verification = verify_supersession_record(
        supersession,
        coordinate=predecessor,
        signature_verifier=signature_verifier,
        as_of=issued_at,
    )
    if not verification.valid:
        raise PolicySupersessionError(
            "the issuing key is not authorized to supersede this policy: "
            f"{verification.status.value}"
            + (f" ({verification.detail})" if verification.detail else "")
        )

    issued, _ = registry.append_issuance_with_supersession(record, supersession)
    return issued
