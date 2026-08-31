"""Structured policy-version supersession (`ACC-LC-1`..`ACC-LC-4`, `ACC-LC-IA-*`).

Supersession is **not** a separate public act. There is no ``supersede_policy``
entry point, and there is deliberately none: `ACC-LC-2` ruled that the successor
declares its predecessor at its own issuance and that *one* signed act both
admits the successor and stops the predecessor resolving. A standalone act would
be a second way to reach the same state, and a state reachable two ways is a
state two things must agree about.

What lives here is the machinery that act uses:

* :func:`require_admissible_supersession` — the step-4 predecessor checks
  (`ACC-LC-IA-3`), run before the digest, before approval, before signing and
  before any mutation. It *reads* the registry; it never writes;
* :func:`verify_supersession_record` — the signature and entitlement check, run
  both when the record is created and again, independently, at every
  resolution: a stored supersession is never trusted merely because it is
  stored, exactly as a stored revocation is not.

**Why the issuing key, and not a new entitlement.** The supersession record is
signed by the same key, in the same act, that issues the successor, and is
verified against :attr:`KeyEntitlement.ISSUE_POLICY`. Minting a third
entitlement would let an operator hold "may supersede" without "may issue" — a
capability that cannot be exercised, since the only path to supersession is
issuing a successor.

**Not revocation.** A superseded predecessor is replaced, not withdrawn: it
stops resolving, keeps its record, and carries no revocation reason code. The
two stores are separate and neither implies the other.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .adapters import PolicyCoordinate
from .errors import PolicySupersessionError
from .records import PolicySupersessionRecord
from .registry import PolicyRegistry
from .signing import PolicySignatureVerifier
from .statuses import KeyEntitlement

__all__ = [
    "require_admissible_supersession",
    "verify_supersession_record",
    "SUPERSESSION_PREDECESSOR_INADMISSIBLE",
]

#: The stable typed reason a structured predecessor reference is refused.
#: Exposed as a constant so consumers branch on the token, never on a message.
SUPERSESSION_PREDECESSOR_INADMISSIBLE = "SUPERSESSION_PREDECESSOR_INADMISSIBLE"


def _refuse(detail: str) -> "PolicySupersessionError":
    return PolicySupersessionError(
        f"{SUPERSESSION_PREDECESSOR_INADMISSIBLE}: {detail}. Nothing has been "
        "signed or registered."
    )


def require_admissible_supersession(
    *,
    predecessor: PolicyCoordinate,
    successor: PolicyCoordinate,
    registry: PolicyRegistry,
    as_of: datetime,
) -> None:
    """Refuse an inadmissible predecessor before anything is signed or stored.

    `ACC-LC-IA-3`. Six refusals, each raising
    :class:`~ugence_policy_authority.core.errors.PolicySupersessionError`:

    1. **self-reference** — an artifact naming itself;
    2. **cross-tenant** — a predecessor in another tenant;
    3. **cross-scope** — a predecessor at another scope;
    4. **absent** — no issued record under that exact coordinate;
    5. **revoked** — the predecessor is already revoked;
    6. **already superseded** — some other successor already replaced it.

    This performs registry **reads**. The invariant that governs issuance is
    unchanged and remains provable: *nothing from a rejected artifact is
    stored*. Reads mutate nothing, and every refusal here happens before the
    approval verifier, the signer and any append are reached.
    """

    if not isinstance(predecessor, PolicyCoordinate):
        raise _refuse("the predecessor reference is not a PolicyCoordinate")

    if predecessor == successor:
        raise _refuse("an artifact cannot supersede itself")
    if predecessor.tenant_id != successor.tenant_id:
        raise _refuse(
            "a successor may not supersede a version in another tenant "
            f"({predecessor.tenant_id!r} != {successor.tenant_id!r})"
        )
    if predecessor.scope != successor.scope:
        raise _refuse(
            "a successor may not supersede a version at another scope "
            f"({predecessor.scope!r} != {successor.scope!r})"
        )

    if registry.get_issued(predecessor) is None:
        raise _refuse(
            "no issued policy exists under the named predecessor coordinate; a "
            "successor may not supersede something that was never issued"
        )
    if registry.revocations_for(predecessor):
        raise _refuse(
            "the named predecessor is already revoked; a revoked version is not "
            "superseded, and issuing over it would imply otherwise"
        )
    if registry.supersessions_for(predecessor):
        raise _refuse(
            "the named predecessor is already superseded by another successor; a "
            "version is superseded once or not at all"
        )


def verify_supersession_record(
    record: PolicySupersessionRecord,
    *,
    coordinate: PolicyCoordinate,
    signature_verifier: PolicySignatureVerifier,
    as_of: datetime,
):
    """Verify a stored supersession's signature and the signer's entitlement.

    Returns the
    :class:`~ugence_policy_authority.core.signing.KeyVerification`. Used when
    the record is created and again at every resolution.
    """

    if record.coordinate != coordinate:
        from .signing import KeyVerification
        from .statuses import KeyVerificationStatus

        return KeyVerification(
            status=KeyVerificationStatus.INVALID_SIGNATURE,
            key_id=record.key_id,
            detail="supersession record targets a different policy coordinate",
        )
    return signature_verifier.verify(
        key_id=record.key_id,
        payload=record.signing_payload(),
        signature=record.signature,
        expected_authority_id=record.superseding_authority_id,
        expected_tenant_id=coordinate.tenant_id,
        required_entitlement=KeyEntitlement.ISSUE_POLICY,
        as_of=as_of,
    )
