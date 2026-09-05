"""Delegation rules — pure, shared by both adapters.

Ratified decision D-3: **one hop**. A delegated grant is refused unless the
delegator's own grant is valid at the same instant, sits in the same tenant, carries
the same role, and covers a scope of which the delegated scope is a subset — never a
wider one and never a sibling. A grant that is itself delegated may not delegate
again; the refusal is typed, so raising the cap later is additive.

This mirrors what Decision Authority already requires of ``DELEGATED_POLICY``
authority: bounded, with a granting reference and an explicit scope
(``packages/capabilities/decision-authority/.../decisions/authority.py:49``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ._canon import require_tzaware
from .grants import RoleGrant
from .principals import scope_covers

__all__ = ["delegation_refusals", "MAX_DELEGATION_HOPS"]

#: Ratified decision D-3. A delegated grant may not itself be delegated.
MAX_DELEGATION_HOPS = 1


def delegation_refusals(grant: RoleGrant, delegator: Optional[RoleGrant],
                        as_of: datetime) -> tuple[str, ...]:
    """Why a delegated grant is inadmissible at ``as_of``; empty means admissible."""

    require_tzaware(as_of, "delegation.as_of")
    if not grant.is_delegated:
        return ()

    reasons: list[str] = []
    if delegator is None:
        return ("the delegating grant does not exist",)
    if delegator.grant_id != grant.delegation_ref:
        reasons.append("delegation_ref does not name the presented delegating grant")
    if delegator.principal_id != grant.delegated_from:
        reasons.append("delegated_from does not name the delegating grant's principal")
    if delegator.tenant_id != grant.tenant_id:
        reasons.append("a delegation may not cross tenants")
    if delegator.is_delegated:
        reasons.append(
            f"delegation stops after {MAX_DELEGATION_HOPS} hop: a delegated grant "
            "may not itself be delegated")
    if not delegator.is_valid_at(as_of):
        reasons.append("the delegating grant is not valid at this instant")
    if delegator.role != grant.role:
        reasons.append(
            f"a delegation may not change the role: '{delegator.role}' -> '{grant.role}'")
    if not scope_covers(delegator.scope, grant.scope):
        reasons.append(
            f"the delegated scope '{grant.scope}' is not within the delegator's "
            f"'{delegator.scope}'; a delegation may only narrow")
    if grant.principal_id == delegator.principal_id:
        reasons.append("a principal may not delegate to itself")
    return tuple(reasons)
