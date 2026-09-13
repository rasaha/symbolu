"""Chain and obligation identifiers, derived — never chosen, never circular.

Rule section 6a fixes the bytes; this module is that specification executed. Two
properties it exists to hold:

* **Nothing is derived from the record that carries it.** An identifier computed
  over its own record's digest could never be constructed, because the record
  cannot be digested until its identifiers are known. ``chain_id`` therefore takes
  only inputs fixed in step 0 — tenant, candidate, anomaly family, family seed and
  the classifier-issued chain instance — and ``obligation_id`` takes the chain
  identifier plus the introducing record's *role* as a constant, never its digest.
* **Identifiers are chain-scoped.** They are unique and stable within one
  ``chain_id`` and are not comparable across chains. An identical candidate
  returning after a terminating outcome carries a fresh chain instance, so it
  receives a different chain and an entirely disjoint set of obligations.

Deriving an identifier is a pure function of caller-supplied inputs. This module
computes nothing *across* records and reads nothing.
"""

from __future__ import annotations

from enum import Enum

from ._canon import domain_digest, normalize_tenant, require_nonempty, require_ordinal
from .errors import ContractViolation


class IntroducingRole(str, Enum):
    """Which record introduced an obligation. A constant in the preimage, not a digest."""

    CLASSIFICATION = "CLASSIFICATION"
    CONFIRMATION_AMENDMENT = "CONFIRMATION_AMENDMENT"


def chain_id(
    *,
    tenant: str,
    candidate_digest: str,
    anomaly_family: str,
    family_seed_digest: str,
    chain_instance_id: str,
) -> str:
    """The chain identifier, from step 0's five inputs.

    The chain instance is issued by the classifier before the first graph record and
    is what distinguishes a resubmitted candidate from its predecessor when the
    digest, the family and the reused seed are all identical.
    """

    return domain_digest(
        "chain_id",
        {
            "anomaly_family": require_nonempty(anomaly_family, "anomaly_family"),
            "candidate_digest": require_nonempty(candidate_digest, "candidate_digest"),
            "chain_instance_id": require_nonempty(chain_instance_id, "chain_instance_id"),
            "family_seed_digest": require_nonempty(family_seed_digest, "family_seed_digest"),
            "tenant": normalize_tenant(tenant),
        },
    )


def obligation_id(
    *,
    chain: str,
    introducing_role: IntroducingRole | str,
    obligation_kind: str,
    coordinate: str,
    ordinal: int,
) -> str:
    """An obligation identifier, scoped to one chain."""

    role = introducing_role.value if isinstance(introducing_role, IntroducingRole) else introducing_role
    if role not in {member.value for member in IntroducingRole}:
        raise ContractViolation(
            "introducing_role must be CLASSIFICATION or CONFIRMATION_AMENDMENT"
        )
    return domain_digest(
        "obligation_id",
        {
            "chain_id": require_nonempty(chain, "chain"),
            "coordinate": require_nonempty(coordinate, "coordinate"),
            "introducing_role": role,
            "obligation_kind": require_nonempty(obligation_kind, "obligation_kind"),
            "ordinal": require_ordinal(ordinal, "ordinal"),
        },
    )


def assign_ordinals(specs) -> tuple[tuple[str, str, int], ...]:
    """Canonical ordinal assignment over ``(kind, coordinate)`` pairs.

    Sorted by kind then coordinate; the ordinal distinguishes repeats of one pair and
    nothing else, so two callers given the same specifications assign the same
    ordinals. A pure sort: it introduces no obligation and decides nothing.
    """

    assigned: list[tuple[str, str, int]] = []
    seen: dict[tuple[str, str], int] = {}
    for kind, coordinate in sorted(
        (require_nonempty(k, "obligation_kind"), require_nonempty(c, "coordinate"))
        for k, c in specs
    ):
        nth = seen.get((kind, coordinate), 0)
        seen[(kind, coordinate)] = nth + 1
        assigned.append((kind, coordinate, nth))
    return tuple(assigned)
