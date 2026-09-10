"""Signed, authorized, reversible policy-version suspension (`ACC-SUSP-*`).

Suspension is a **pause**, not a withdrawal and not a replacement. A suspended
version keeps its record and stops resolving; a later reinstatement makes it
resolve again. Revocation stays terminal and separate, supersession stays a
replacement, and none of the three implies another.

What makes this store different
-------------------------------
Revocation and supersession are terminal, so their stores hold at most one
record per coordinate and "is it revoked" is answered by *"a record exists"*.
Suspension is reversible, so its store holds an **ordered sequence** and the
current state is the **latest accepted record**. `ACC-SUSP-2` recorded that as
the row where being wrong is expensive; `ACC-SUSP-IA-7` settled it with two
invariants, enforced here at append time and re-checked independently at every
resolution:

**Strict time-monotonicity.** A candidate's ``effective_at`` must be *strictly
later* than the latest accepted record's. Two distinct records may never share
one signed instant, and an older candidate is **refused**, never sorted into
place. Arrival order is not authoritative — the signed instants establish order
— but the append-only log is not retroactively rewritten by inserting an earlier
record.

`[R]` **Why refusal rather than sorting**, recorded because it is the load-
bearing reason: sorting arbitrary arrivals into the history would make *whether
a reinstatement is an orphan* depend on **delivery order**, which is exactly the
property the transition rule exists to deny. The two rules are consistent only
if the log is append-forward.

**Transition validity.** A ``REINSTATE`` is accepted only when the latest
accepted state is ``SUSPEND``. A reinstatement cannot manufacture the transition
it claims to reverse.

**Idempotent replay is not a second append.** An exact replay of an already
stored record — same identity, same signed payload — returns the stored record
unchanged, on the revocation store's precedent. A *different* record at the same
instant is an integrity failure, not a repeat.

What this module does not do
----------------------------
It writes no ``lifecycle_state`` (`ACC-SUSP-1`): ``ADMITTED_LIFECYCLE_STATES``
stays closed exactly as ratified, and a suspended artifact still reads its issued
lifecycle label. It holds no clock — every instant is caller-supplied and
timezone-aware. It grants no authority over agents or roles (`OD-C4=A`), and
issues, activates and suspends **no genuine constitution**: under
`ACC-SUSP-IA-4` this implementation is exercised through deterministic tests and
fixtures only, until the `ACC-FC-5` custody and approving-authority gates close.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from .adapters import AdapterRegistry, PolicyCoordinate
from .canonical import require_tzaware
from .errors import PolicyAuthorityRequestError, PolicySuspensionError
from .payload import suspension_signing_payload
from .records import PolicySuspensionRecord
from .registry import PolicyRegistry
from .signing import PolicySignatureVerifier, PolicySigner
from .statuses import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    KeyEntitlement,
    PolicySuspensionAction,
)

__all__ = [
    "SUSPENSION_SEQUENCE_INADMISSIBLE",
    "reinstate_policy",
    "suspend_policy",
    "suspension_sequence_defect",
    "suspension_state_at",
    "verify_suspension_record",
]

#: The stable typed reason a suspension lifecycle act is refused. Exposed as a
#: constant so consumers branch on the token, never on a message.
SUSPENSION_SEQUENCE_INADMISSIBLE = "SUSPENSION_SEQUENCE_INADMISSIBLE"


def _refuse(detail: str) -> "PolicySuspensionError":
    return PolicySuspensionError(
        f"{SUSPENSION_SEQUENCE_INADMISSIBLE}: {detail}. Nothing has been signed "
        "or registered."
    )


def verify_suspension_record(
    record: PolicySuspensionRecord,
    *,
    coordinate: PolicyCoordinate,
    signature_verifier: PolicySignatureVerifier,
    as_of: datetime,
):
    """Verify one stored record's signature and the signer's entitlement.

    Returns the :class:`~ugence_policy_authority.core.signing.KeyVerification`.
    Used when the record is created and again, independently, at every
    resolution: a stored suspension is never trusted merely because it is
    stored, exactly as a stored revocation is not.
    """

    if record.coordinate != coordinate:
        from .signing import KeyVerification
        from .statuses import KeyVerificationStatus

        return KeyVerification(
            status=KeyVerificationStatus.INVALID_SIGNATURE,
            key_id=record.key_id,
            detail="suspension record targets a different policy coordinate",
        )
    return signature_verifier.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.suspending_authority_id,
        expected_tenant_id=coordinate.tenant_id,
        required_entitlement=KeyEntitlement.SUSPEND_POLICY,
        as_of=as_of,
    )


def suspension_sequence_defect(
    records: Sequence[PolicySuspensionRecord],
) -> Optional[str]:
    """Return why a stored sequence is inadmissible, or ``None`` if it is sound.

    `ACC-SUSP-IA-7`, the resolution-time half. The append-time checks below
    prevent a defective sequence from ever being written through this module;
    this function re-derives the same two invariants from whatever the store
    actually holds, so a history assembled another way — a hand-edited database,
    a restored backup, a registry implementation with a bug — still fails closed
    rather than being believed.

    ``records`` is taken **in stored order**; the check is that stored order is
    already strictly increasing, not that some ordering of it would be.
    """

    previous: Optional[PolicySuspensionRecord] = None
    for record in records:
        if not isinstance(record, PolicySuspensionRecord):
            return "the store holds an object that is not a PolicySuspensionRecord"
        if previous is not None:
            if record.effective_at == previous.effective_at:
                return (
                    "two distinct records share the signed instant "
                    f"{record.effective_at.isoformat()}; equal instants are ambiguous "
                    "and ambiguity fails closed"
                )
            if record.effective_at < previous.effective_at:
                return (
                    "the stored sequence is not strictly monotonic: "
                    f"{record.effective_at.isoformat()} follows "
                    f"{previous.effective_at.isoformat()}"
                )
            if (
                record.action is PolicySuspensionAction.REINSTATE
                and previous.action is not PolicySuspensionAction.SUSPEND
            ):
                return (
                    "a stored REINSTATE does not follow a SUSPEND; a reinstatement "
                    "cannot manufacture the transition it claims to reverse"
                )
        elif record.action is not PolicySuspensionAction.SUSPEND:
            return (
                "the stored history opens with a REINSTATE; there is no prior "
                "suspension for it to lift"
            )
        previous = record
    return None


def suspension_state_at(
    records: Sequence[PolicySuspensionRecord],
    *,
    as_of: datetime,
) -> Optional[PolicySuspensionRecord]:
    """Return the latest record effective at ``as_of``, or ``None``.

    The caller decides what to do with it: a ``SUSPEND`` means paused at that
    instant, a ``REINSTATE`` means the pause was lifted, and ``None`` means the
    version was never paused as of then. Records dated after ``as_of`` are not
    consulted — a future pause does not act on the past.

    This performs **no** validation. Callers run
    :func:`suspension_sequence_defect` first; keeping the two separate is what
    stops a defective history being silently interpreted.
    """

    latest: Optional[PolicySuspensionRecord] = None
    for record in records:
        if record.effective_at <= as_of:
            latest = record
    return latest


def _require_admissible_candidate(
    *,
    coordinate: PolicyCoordinate,
    action: PolicySuspensionAction,
    effective_at: datetime,
    registry: PolicyRegistry,
) -> None:
    """The three `ACC-SUSP-IA-7` append-time refusals, before anything is signed.

    Registry **reads** only. The invariant that governs issuance is unchanged and
    remains provable: nothing from a rejected act is stored, and every refusal
    here happens before the signer and any append are reached.
    """

    if registry.get_issued(coordinate) is None:
        raise _refuse(
            "no issued policy exists under this exact coordinate; a version that "
            "was never issued cannot be suspended or reinstated"
        )
    if registry.revocations_for(coordinate):
        raise _refuse(
            "the named version is already revoked; revocation is terminal, and "
            "pausing or resuming a withdrawn version would imply otherwise"
        )
    if registry.supersessions_for(coordinate):
        raise _refuse(
            "the named version is already superseded; a replaced version is not "
            "paused, and suspending it would imply it could return"
        )

    stored = registry.suspensions_for(coordinate)
    defect = suspension_sequence_defect(stored)
    if defect is not None:
        raise _refuse(f"the stored suspension history is already inadmissible ({defect})")

    latest = stored[-1] if stored else None

    # 1. Equal signed instants are ambiguous; 2. an older candidate would be a
    # retroactive insertion. Both are refused rather than ordered around.
    if latest is not None:
        if effective_at == latest.effective_at:
            raise _refuse(
                "a distinct record already carries the signed instant "
                f"{effective_at.isoformat()} for this coordinate; two distinct "
                "records may not share one instant"
            )
        if effective_at < latest.effective_at:
            raise _refuse(
                f"the candidate's signed instant {effective_at.isoformat()} is not "
                f"strictly later than the latest accepted record's "
                f"{latest.effective_at.isoformat()}; the append-only log is not "
                "rewritten by inserting an earlier record"
            )

    # 3. A reinstatement is valid only from a suspended state.
    current = latest.action if latest is not None else None
    if action is PolicySuspensionAction.REINSTATE and current is not (
        PolicySuspensionAction.SUSPEND
    ):
        raise _refuse(
            "a reinstatement is valid only when the latest accepted state is "
            "SUSPEND; this version is "
            + ("not currently suspended" if current is not None else "not suspended at all")
        )
    if action is PolicySuspensionAction.SUSPEND and current is (
        PolicySuspensionAction.SUSPEND
    ):
        raise _refuse(
            "this version is already suspended; a second SUSPEND would add a "
            "transition that changes nothing and make the history ambiguous"
        )


def _append_lifecycle_act(
    *,
    reference: object,
    suspension_id: str,
    action: PolicySuspensionAction,
    registry: PolicyRegistry,
    adapters: AdapterRegistry,
    signer: PolicySigner,
    signature_verifier: PolicySignatureVerifier,
    effective_at: datetime,
    expected_reference_tenant_id: Optional[str],
    detail: str,
) -> PolicySuspensionRecord:
    if not isinstance(suspension_id, str) or not suspension_id.strip():
        raise PolicyAuthorityRequestError("suspension_id must be non-empty")
    if not isinstance(action, PolicySuspensionAction):
        raise PolicyAuthorityRequestError("action must be a PolicySuspensionAction")
    if not isinstance(adapters, AdapterRegistry):
        raise PolicyAuthorityRequestError("adapters must be an AdapterRegistry")
    # A signer is mandatory: there is no unsigned suspension path.
    if signer is None or not all(
        hasattr(signer, attribute)
        for attribute in ("authority_id", "key_id", "signature_alg", "sign")
    ):
        raise PolicyAuthorityRequestError(
            "a signer is mandatory and must implement PolicySigner — an unsigned "
            "suspension is invalid, not 'suspension pending'"
        )
    if signature_verifier is None or not hasattr(signature_verifier, "verify"):
        raise PolicyAuthorityRequestError(
            "a signature_verifier is mandatory and must implement "
            "PolicySignatureVerifier — the signer's entitlement must be proven"
        )
    effective_at = require_tzaware(effective_at, path="effective_at")

    coordinate = adapters.coordinate_for(reference)
    if (
        expected_reference_tenant_id is not None
        and coordinate.tenant_id != expected_reference_tenant_id
    ):
        raise PolicySuspensionError(
            "cross-tenant suspension rejected: the reference's declared tenant does "
            f"not match {expected_reference_tenant_id!r}"
        )

    _require_admissible_candidate(
        coordinate=coordinate,
        action=action,
        effective_at=effective_at,
        registry=registry,
    )

    # The suspending authority is the signer's — never the issuer's by default.
    suspending_authority_id = signer.authority_id
    if not isinstance(suspending_authority_id, str) or not suspending_authority_id.strip():
        raise PolicySuspensionError("the suspension signer must name a suspending authority")

    signature = bytes(
        signer.sign(
            suspension_signing_payload(
                suspension_id=suspension_id,
                coordinate=coordinate,
                action=action,
                suspending_authority_id=suspending_authority_id,
                key_id=signer.key_id,
                signature_alg=signer.signature_alg,
                effective_at=effective_at,
            )
        )
    )

    record = PolicySuspensionRecord(
        suspension_id=suspension_id,
        coordinate=coordinate,
        action=action,
        suspending_authority_id=suspending_authority_id,
        key_id=signer.key_id,
        signature_alg=signer.signature_alg,
        signature=signature,
        effective_at=effective_at,
        detail=detail,
        authority_protocol=AUTHORITY_PROTOCOL,
        authority_protocol_version=AUTHORITY_PROTOCOL_VERSION,
    )

    # The signer's entitlement is proven *before* the record is stored, so an
    # unauthorized act never enters the registry at all.
    verification = verify_suspension_record(
        record,
        coordinate=coordinate,
        signature_verifier=signature_verifier,
        as_of=effective_at,
    )
    if not verification.valid:
        raise PolicySuspensionError(
            "the signing key is not authorized to suspend or reinstate this policy: "
            f"{verification.status.value}"
            + (f" ({verification.detail})" if verification.detail else "")
        )

    return registry.append_suspension(record)


def suspend_policy(
    *,
    reference: object,
    suspension_id: str,
    registry: PolicyRegistry,
    adapters: AdapterRegistry,
    signer: PolicySigner,
    signature_verifier: PolicySignatureVerifier,
    effective_at: datetime,
    expected_reference_tenant_id: Optional[str] = None,
    detail: str = "",
) -> PolicySuspensionRecord:
    """Pause exactly one issued policy version, with a signed authorized record.

    ``effective_at`` is injected — no clock is read. Resolution fails closed with
    ``SUSPENDED`` at and after this instant, until a later reinstatement.
    """

    return _append_lifecycle_act(
        reference=reference,
        suspension_id=suspension_id,
        action=PolicySuspensionAction.SUSPEND,
        registry=registry,
        adapters=adapters,
        signer=signer,
        signature_verifier=signature_verifier,
        effective_at=effective_at,
        expected_reference_tenant_id=expected_reference_tenant_id,
        detail=detail,
    )


def reinstate_policy(
    *,
    reference: object,
    suspension_id: str,
    registry: PolicyRegistry,
    adapters: AdapterRegistry,
    signer: PolicySigner,
    signature_verifier: PolicySignatureVerifier,
    effective_at: datetime,
    expected_reference_tenant_id: Optional[str] = None,
    detail: str = "",
) -> PolicySuspensionRecord:
    """Lift a pause on exactly one issued policy version (`ACC-SUSP-3`).

    The same entitlement covers both acts: an authority that may pause may
    unpause. Refused unless the latest accepted state for this coordinate is a
    ``SUSPEND``.
    """

    return _append_lifecycle_act(
        reference=reference,
        suspension_id=suspension_id,
        action=PolicySuspensionAction.REINSTATE,
        registry=registry,
        adapters=adapters,
        signer=signer,
        signature_verifier=signature_verifier,
        effective_at=effective_at,
        expected_reference_tenant_id=expected_reference_tenant_id,
        detail=detail,
    )
