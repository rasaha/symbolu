"""Pure selection rules — shared by both adapters, storing nothing.

Every selector filters to grants valid at the caller's instant *first*. A grant
outside its window, or revoked at or before that instant, is simply absent; no
selector ever returns one with a flag attached.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from ._canon import optional_text, require_nonempty, require_tzaware
from .directory import CommitteeReport
from .grants import RoleGrant
from .principals import PrincipalKind, require_scope

__all__ = ["valid_at", "select_for_principal", "select_holders", "build_committee_report"]


def valid_at(grants: Iterable[RoleGrant], as_of: datetime) -> tuple[RoleGrant, ...]:
    """Only the grants in force at ``as_of``, in a stable order."""

    require_tzaware(as_of, "as_of")
    return tuple(sorted((g for g in grants if g.is_valid_at(as_of)),
                        key=lambda g: (g.principal_id, g.role, g.scope, g.grant_id)))


def select_for_principal(grants: Iterable[RoleGrant], *, tenant_id: str, principal_id: str,
                         as_of: datetime) -> tuple[RoleGrant, ...]:
    tenant = require_nonempty(tenant_id, "tenant_id")
    principal = require_nonempty(principal_id, "principal_id")
    return valid_at((g for g in grants
                     if g.tenant_id == tenant and g.principal_id == principal), as_of)


def select_holders(grants: Iterable[RoleGrant], *, tenant_id: str, role: str, scope: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]:
    """Who currently holds ``role`` over a scope covering ``scope``."""

    tenant = require_nonempty(tenant_id, "tenant_id")
    wanted_role = require_nonempty(role, "role")
    wanted_scope = require_scope(scope, "scope")
    return valid_at((g for g in grants
                     if g.tenant_id == tenant and g.role == wanted_role
                     and g.covers(wanted_scope)), as_of)


def build_committee_report(grants: Iterable[RoleGrant], *, tenant_id: str, committee_id: str,
                           role: str, scope: str,
                           as_of: datetime) -> Optional[CommitteeReport]:
    """The committee's quorum and its currently-valid members, or ``None``.

    ``None`` means the committee holds no valid grant of this role over this scope at
    ``as_of`` — the committee is absent, exactly as a lapsed member would be. The
    report never says whether the quorum is met.
    """

    tenant = require_nonempty(tenant_id, "tenant_id")
    committee = require_nonempty(committee_id, "committee_id")
    wanted_role = optional_text(role, "role")
    wanted_scope = require_scope(scope, "scope")
    live = valid_at(grants, as_of)

    committee_grants = [g for g in live
                        if g.tenant_id == tenant and g.principal_id == committee
                        and g.principal.principal_kind is PrincipalKind.COMMITTEE
                        and (not wanted_role or g.role == wanted_role)
                        and g.covers(wanted_scope)]
    if not committee_grants:
        return None
    committee_grant = committee_grants[0]

    members = tuple(g for g in live
                    if g.tenant_id == tenant and g.member_of == committee
                    and g.role == committee_grant.role
                    and committee_grant.covers(g.scope))
    return CommitteeReport(committee=committee_grant.principal, role=committee_grant.role,
                           scope=committee_grant.scope,
                           quorum=committee_grant.principal.quorum, members=members)
