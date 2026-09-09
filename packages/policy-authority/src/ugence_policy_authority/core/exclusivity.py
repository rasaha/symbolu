"""Family-neutral exclusivity: two effective versions may not claim one thing.

`ACC-OVL-1` – `ACC-OVL-8`. The invariant, in the core's own vocabulary: **two
simultaneously effective versions may not hold an equal exclusivity claim within
the same tenant and scope**, unless an explicitly verified supersession
relationship permits it.

How this stays family-neutral
-----------------------------
The core never learns what a claim means. An adapter projects
:class:`~ugence_policy_authority.core.adapters.ExclusivityClaim` tokens; this
module normalises and compares them for **equality**, and pairs them with the
scope and tenant of the artifact's own coordinate — never with anything the
adapter restated. A family with no exclusivity semantics projects nothing and is
unaffected, which is what makes adding this seam invisible to every family that
does not want it.

Where it is enforced, and why in two places
-------------------------------------------
**At issuance**, before the digest, before approval, before signing and before
any mutation — registry reads only, on
:func:`~ugence_policy_authority.core.supersession.require_admissible_supersession`'s
exact precedent. Nothing from a rejected artifact is stored.

**At resolution**, re-derived rather than trusted. Issuance-time enforcement
alone would be a check at the door on a store that can be filled another way —
the same reasoning that makes every suspension ordering rule re-derive, and the
same reasoning that makes a stored revocation re-verify on every use.

There is no tie to break
------------------------
`ACC-OVL-3`: registration order, mapping order and arrival order may **never**
choose a winner. An unresolved overlap **refuses**. A deployment that would have
to guess is told it cannot proceed instead.

The one exception, and only that one
------------------------------------
`ACC-OVL-8`: an overlap is permitted only where the candidate declares the
incumbent as its exact predecessor **and** that supersession verifies. `[G]`
**Delegation is deliberately absent.** It has no contract, no record type and no
ratification in this repository, and inventing one here would be a governance act
wearing an implementation's clothes. Any delegation exception needs its own owner
round covering delegated authority bounds, identity, scope, duration, revocation,
and the monotonic rule that delegated authority cannot exceed issued authority.

What this module is not
-----------------------
It is not a clock — every instant is caller-supplied. It resolves nothing, signs
nothing and stores nothing. And it closes no `ACC-FC-5` gate: no constitution has
been issued, so like supersession and suspension before it, this invariant is
unexercisable in production on the day it lands. `ACC-OVL-4` — no second
constitution until it is implemented and verified — is what has kept the gap
harmless meanwhile, and it holds either way.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional, Sequence, Tuple

from .adapters import ExclusivityClaim, PolicyCoordinate
from .errors import PolicyExclusivityError

__all__ = [
    "EXCLUSIVITY_CONFLICT",
    "ClaimHolder",
    "claim_key",
    "conflicting_holders",
    "effective_claim_holders",
    "intervals_overlap",
    "require_no_exclusivity_conflict",
]

#: The stable typed token an exclusivity refusal carries. Exposed so consumers
#: branch on the token, never on a message.
EXCLUSIVITY_CONFLICT = "EXCLUSIVITY_CONFLICT"

#: What the core compares: the claim, plus the scope and tenant it is held in.
#: Scope and tenant come from the coordinate, so a claim can never reach outside
#: the tenant and scope of the artifact that projected it.
ClaimKey = Tuple[str, str, str, str]


def claim_key(claim: ExclusivityClaim, coordinate: PolicyCoordinate) -> ClaimKey:
    """The exact tuple two artifacts must share for their claims to collide."""

    return (claim.namespace, claim.subject, coordinate.scope, coordinate.tenant_id)


class ClaimHolder:
    """One issued version that holds a claim, and the interval it holds it over."""

    __slots__ = ("coordinate", "effective_from", "effective_to")

    def __init__(
        self,
        coordinate: PolicyCoordinate,
        effective_from: Optional[datetime],
        effective_to: Optional[datetime],
    ) -> None:
        self.coordinate = coordinate
        self.effective_from = effective_from
        self.effective_to = effective_to

    def __repr__(self) -> str:  # pragma: no cover - diagnostic only
        return f"ClaimHolder({self.coordinate.policy_id}@{self.coordinate.version})"


def intervals_overlap(
    a_from: Optional[datetime],
    a_to: Optional[datetime],
    b_from: Optional[datetime],
    b_to: Optional[datetime],
) -> bool:
    """Whether two half-open ``[from, to)`` effective intervals overlap.

    A missing bound is open-ended. Half-open is what makes an immediate handover
    legal: a version ending exactly when its replacement begins does **not**
    overlap it, so a clean succession never trips the invariant.

    `[R]` Overlap is evaluated over the whole interval, not at one instant. An
    overlap that begins next month is still an overlap, and issuance refuses it
    **now** rather than letting it arrive on a live deployment — which is the
    difference between an invariant and a monitor.
    """

    if a_to is not None and b_from is not None and a_to <= b_from:
        return False
    if b_to is not None and a_from is not None and b_to <= a_from:
        return False
    return True


def conflicting_holders(
    *,
    claims: Sequence[ExclusivityClaim],
    coordinate: PolicyCoordinate,
    effective_from: Optional[datetime],
    effective_to: Optional[datetime],
    holders: Iterable[Tuple[ClaimKey, ClaimHolder]],
    permitted: Iterable[PolicyCoordinate] = (),
) -> tuple:
    """Return every ``(key, holder)`` that conflicts with this artifact's claims.

    ``holders`` is what the registry's claim index yields; ``permitted`` names
    coordinates an explicitly verified relationship allows this artifact to
    overlap — in this round, exactly the verified supersession predecessor.

    The artifact never conflicts with **itself**: re-issuing the byte-identical
    version under the same coordinate is idempotent, not a collision.
    """

    wanted = {claim_key(claim, coordinate) for claim in claims}
    if not wanted:
        return ()
    allowed = set(permitted)
    found = []
    for key, holder in holders:
        if key not in wanted:
            continue
        if holder.coordinate == coordinate or holder.coordinate in allowed:
            continue
        if intervals_overlap(
            effective_from, effective_to, holder.effective_from, holder.effective_to
        ):
            found.append((key, holder))
    return tuple(found)


def require_no_exclusivity_conflict(
    *,
    claims: Sequence[ExclusivityClaim],
    coordinate: PolicyCoordinate,
    effective_from: Optional[datetime],
    effective_to: Optional[datetime],
    holders: Iterable[Tuple[ClaimKey, ClaimHolder]],
    permitted: Iterable[PolicyCoordinate] = (),
) -> None:
    """Refuse an artifact whose claims collide, before anything is signed.

    Raises :class:`~ugence_policy_authority.core.errors.PolicyExclusivityError`.
    The message names the claim and the incumbent, because an operator who cannot
    see *which* claim collided with *what* cannot resolve the overlap — and
    resolving it, not guessing past it, is the only way forward.
    """

    conflicts = conflicting_holders(
        claims=claims,
        coordinate=coordinate,
        effective_from=effective_from,
        effective_to=effective_to,
        holders=holders,
        permitted=permitted,
    )
    if not conflicts:
        return
    key, holder = conflicts[0]
    namespace, subject, scope, tenant = key
    raise PolicyExclusivityError(
        f"{EXCLUSIVITY_CONFLICT}: {subject!r} in {namespace!r} is already governed by "
        f"{holder.coordinate.policy_id}@{holder.coordinate.version} over an overlapping "
        f"effective period (scope {scope!r}, tenant {tenant!r}). An unresolved overlap is "
        "refused rather than decided by registration or arrival order; supersede the "
        "incumbent explicitly, or narrow one of the two effective periods. Nothing has "
        "been signed or registered."
    )


def effective_claim_holders(
    *,
    records: Iterable,
    adapters,
    registry,
    exclude: Optional[PolicyCoordinate] = None,
) -> tuple:
    """Derive ``(key, holder)`` pairs from stored issuance records.

    **Derived, never indexed, and that is deliberate.** A side index of claims
    can drift from the records it describes — a write that lands without its
    index entry leaves a claim invisible, which fails *open*. Re-deriving from
    the authoritative records cannot drift, and costs a bounded read: the caller
    passes only one family within one scope and tenant, and only ever calls this
    for an artifact that projects claims at all, so every family without
    exclusivity semantics pays nothing.

    Two judgements, both resolved toward refusal:

    **A record that cannot be described is a conflict, not an absence.** If no
    registered adapter still claims a stored artifact, its claims are unreadable
    — and an incumbent whose claims cannot be read is exactly the "unresolved"
    case `ACC-OVL-3` says must refuse. Skipping it would let an unreadable record
    silently release the thing it governs.

    **A suspended version keeps its claims.** Revocation and supersession are
    terminal, so a version under either can never govern again and its claims are
    released. A suspension is a **pause**: the version can be reinstated, and if
    a second artifact had taken the claim meanwhile, reinstatement would create
    exactly the overlap this invariant forbids — with no act left to refuse it.
    So a pause does not release a claim.
    """

    from .errors import PolicyAuthorityError

    holders = []
    for record in records:
        coordinate = record.coordinate
        if exclude is not None and coordinate == exclude:
            continue
        # Terminal states release the claim; a pause does not.
        if registry.revocations_for(coordinate) or registry.supersessions_for(coordinate):
            continue
        try:
            descriptor = adapters.describe(record.policy)
        except PolicyAuthorityError as exc:
            raise PolicyExclusivityError(
                f"{EXCLUSIVITY_CONFLICT}: the issued version "
                f"{coordinate.policy_id}@{coordinate.version} cannot be described by any "
                f"registered adapter, so what it governs cannot be read ({exc}). An "
                "incumbent whose claims are unreadable is treated as conflicting, never "
                "as absent. Nothing has been signed or registered."
            ) from exc
        if not descriptor.lifecycle_is_active:
            # A lifecycle label is signed and an artifact is immutable, so an
            # inactive version can never become active. It governs nothing.
            continue
        for claim in descriptor.exclusivity_claims:
            holders.append(
                (
                    claim_key(claim, coordinate),
                    ClaimHolder(coordinate, descriptor.effective_from, descriptor.effective_to),
                )
            )
    return tuple(holders)
