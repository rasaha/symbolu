"""Monotone restriction algebra (RA-4.5 §12).

Computes the effective authority as

    EffectiveAuthority = RiskAuthority ∩ GovernanceRestrictions
    with  EffectiveAuthority ⊆ RiskAuthority   (always)

Only *tightening* operators are applied, and only to dimensions the Risk
Authority scope actually represents. There is no operator, on any dimension,
that can enlarge authority:

    amount ceiling    → min()          (↓ tighten)
    expiry / validity → earliest()     (↓ shorten)
    allow sets        → intersection   (↓ shrink)
    deny sets         → union          (↑ grow denial = tighten)
    required approvals→ union          (↑ strengthen obligation)

Dimensions Risk Authority owns but the governance kernels do not compatibly
represent (signature, revocation, epoch, and — until #1397 — jurisdiction /
autonomy *enforcement*) are passed through **unchanged** from the RA scope; no
composition operator is applied to them, so nothing is silently defaulted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from .contracts import (
    EffectiveConstraints,
    GovernanceRestrictions,
    RiskAuthorityMachineResult,
)

__all__ = ["apply_restrictions", "ALLOW_DIMENSIONS", "DENY_DIMENSIONS"]

#: Allow-set scope dimensions: narrowing removes members (intersection).
ALLOW_DIMENSIONS = (
    "purposes",
    "tools_allow",
    "data_allow",
    "destinations",
    "jurisdictions",
)
#: Deny-set scope dimensions: narrowing adds members (union grows the denial).
DENY_DIMENSIONS = ("tools_deny", "data_deny")


def _min_optional(a: Optional[int], b: Optional[int]) -> Optional[int]:
    """min() treating None as 'unbounded' (so any bound wins)."""

    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _earliest(a: Optional[datetime], b: Optional[datetime]) -> Optional[datetime]:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def apply_restrictions(
    ra: RiskAuthorityMachineResult,
    restrictions: Iterable[GovernanceRestrictions],
) -> EffectiveConstraints:
    """Fold governance ``restrictions`` onto the RA scope, tightening only.

    Returns :class:`EffectiveConstraints` guaranteed ``⊆`` the RA scope on every
    dimension. If the RA result carries no scope (e.g. RA denied / errored before
    a scope existed), returns an empty, non-enlargeable constraint set.
    """

    scope = ra.scope
    if scope is None:
        # No RA scope to bound: there is nothing to preserve or reduce.
        return EffectiveConstraints(
            max_amount_minor_units=0, emptied_dimensions=("<no-ra-scope>",)
        )

    # Seed the effective constraints from the RA-issued scope (the ceiling).
    purposes = set(getattr(scope, "purposes", ()))
    tools_allow = set(getattr(scope, "tools_allow", ()))
    data_allow = set(getattr(scope, "data_allow", ()))
    destinations = set(getattr(scope, "destinations", ()))
    jurisdictions = set(getattr(scope, "jurisdictions", ()))
    tools_deny = set(getattr(scope, "tools_deny", ()))
    data_deny = set(getattr(scope, "data_deny", ()))
    max_autonomy_level = int(getattr(scope, "max_autonomy_level", 0))
    max_amount = getattr(scope, "max_transaction_minor_units", None)
    expires_at = ra.expires_at

    allow_sets = {
        "purposes": purposes,
        "tools_allow": tools_allow,
        "data_allow": data_allow,
        "destinations": destinations,
        "jurisdictions": jurisdictions,
    }
    deny_sets = {"tools_deny": tools_deny, "data_deny": data_deny}
    # Remember which allow dimensions RA authorized as non-empty so we can detect
    # governance intersecting one of them to empty (⇒ empty effective scope).
    ra_nonempty_allow = {dim for dim, s in allow_sets.items() if s}

    required_approvals: set[str] = set()
    obligations: list[tuple[str, str]] = []

    for r in restrictions:
        # Amount ceiling → min() (a lower cap wins; RA cap never raised).
        max_amount = _min_optional(max_amount, r.max_amount_minor_units)
        # Expiry → earliest() (never extends RA validity — F-B).
        expires_at = _earliest(expires_at, r.expires_at)
        # Allow sets → intersection (can only shrink).
        for dim, members in r.allow_intersections.items():
            if dim in allow_sets:
                allow_sets[dim] &= set(members)
        # Deny sets → union (can only grow the denial = tighten).
        for dim, members in r.deny_unions.items():
            if dim in deny_sets:
                deny_sets[dim] |= set(members)
        # Required approvals → union (strengthen obligation).
        required_approvals |= set(r.required_approvals)
        obligations.extend(r.obligations)

    # A dimension RA authorized (non-empty) that governance emptied ⇒ empty scope.
    emptied = tuple(
        sorted(dim for dim in ra_nonempty_allow if not allow_sets[dim])
    )

    return EffectiveConstraints(
        purposes=tuple(sorted(allow_sets["purposes"])),
        tools_allow=tuple(sorted(allow_sets["tools_allow"])),
        tools_deny=tuple(sorted(deny_sets["tools_deny"])),
        data_allow=tuple(sorted(allow_sets["data_allow"])),
        data_deny=tuple(sorted(deny_sets["data_deny"])),
        destinations=tuple(sorted(allow_sets["destinations"])),
        jurisdictions=tuple(sorted(allow_sets["jurisdictions"])),
        max_autonomy_level=max_autonomy_level,
        max_amount_minor_units=max_amount,
        expires_at=expires_at,
        required_approvals=frozenset(required_approvals),
        obligations=tuple(obligations),
        emptied_dimensions=emptied,
    )
