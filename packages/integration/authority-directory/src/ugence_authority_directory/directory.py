"""What the directory answers, and the port both adapters implement.

Three answers, each at a caller-supplied instant, and each reporting **only** grants
valid at that instant:

* which grants a principal holds;
* who holds a role within a scope;
* a committee's quorum and its currently-valid members.

The directory never counts votes, never decides a quorum was met, never authenticates
anyone and never returns an ``ActorType``. A :class:`CommitteeReport` deliberately
carries no "quorum met" field: whether enough members actually approved is the
approval workflow's ledger and Decision Authority's ``required_approvals``, not this
package's business.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from .grants import GrantEvent, RoleGrant
from .principals import PrincipalRef

__all__ = ["CommitteeReport", "AuthorityDirectoryPort"]


@dataclass(frozen=True)
class CommitteeReport:
    """A committee's quorum and the members whose grants are valid at one instant.

    ``quorum`` is what the organization requires; ``members`` is who currently holds
    the role. The report states both and stops there — it never asserts that the
    committee can or did act.
    """

    committee: PrincipalRef
    role: str
    scope: str
    quorum: int
    members: tuple[RoleGrant, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))

    @property
    def member_ids(self) -> tuple[str, ...]:
        return tuple(g.principal_id for g in self.members)


@runtime_checkable
class AuthorityDirectoryPort(Protocol):
    """The directory's own seam. Reports grants; decides nothing."""

    def put_grant(self, grant: RoleGrant, *, as_of: datetime,
                  loaded_by: str = "") -> RoleGrant: ...

    def revoke_grant(self, grant_id: str, *, as_of: datetime,
                     reason: str = "", actor: str = "") -> RoleGrant: ...

    def get_grant(self, grant_id: str) -> Optional[RoleGrant]: ...

    def grants_for(self, *, tenant_id: str, principal_id: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]: ...

    def holders_of(self, *, tenant_id: str, role: str, scope: str,
                   as_of: datetime) -> tuple[RoleGrant, ...]: ...

    def committee_report(self, *, tenant_id: str, committee_id: str, role: str, scope: str,
                         as_of: datetime) -> Optional[CommitteeReport]: ...

    def grant_events(self, grant_id: str) -> tuple[GrantEvent, ...]: ...
