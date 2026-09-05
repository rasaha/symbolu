"""Shared builders. Every instant is explicit; no test reads a clock either."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from ugence_governance_contracts.api import Validity

from ugence_authority_directory import (
    InMemoryAuthorityDirectory,
    PrincipalKind,
    PrincipalRef,
    RoleGrant,
    SqliteAuthorityDirectory,
    grant_id_for,
)

TENANT = "tenant-a"
ROLE = "risk-approver"
SUBJECT_KIND = "decision_case"
DIGEST = "a" * 64
OTHER_DIGEST = "b" * 64

#: The scope convention the shipped eligibility adapter derives.
SCOPE = f"approval/{SUBJECT_KIND}/{DIGEST}"
PARENT_SCOPE = f"approval/{SUBJECT_KIND}"
SIBLING_SCOPE = f"approval/{SUBJECT_KIND}/{OTHER_DIGEST}"

T0 = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)
T1 = T0 + timedelta(minutes=5)
T2 = T0 + timedelta(minutes=10)
BEFORE_WINDOW = T0 - timedelta(days=1)
AFTER_WINDOW = T0 + timedelta(days=8)


def window(issued: datetime = T0, *, days: int = 7) -> Validity:
    return Validity(issued_at=issued, expires_at=issued + timedelta(days=days))


def human(principal_id: str = "approver-1") -> PrincipalRef:
    return PrincipalRef(principal_id=principal_id, principal_kind=PrincipalKind.HUMAN,
                        display_ref="directory://people/" + principal_id)


def committee(principal_id: str = "risk-committee", *, quorum: int = 2) -> PrincipalRef:
    return PrincipalRef(principal_id=principal_id, principal_kind=PrincipalKind.COMMITTEE,
                        quorum=quorum)


def grant(principal: PrincipalRef | None = None, *, role: str = ROLE, scope: str = SCOPE,
          validity: Validity | None = None, tenant: str = TENANT, member_of: str = "",
          delegation_ref: str = "", delegated_from: str = "",
          authority_reference: str = "directory://roles/risk-approver") -> RoleGrant:
    who = principal or human()
    win = validity or window()
    return RoleGrant(
        grant_id=grant_id_for(tenant, who.principal_id, role, scope, win), tenant_id=tenant,
        principal=who, role=role, scope=scope, validity=win,
        authority_reference=authority_reference, member_of=member_of,
        delegation_ref=delegation_ref, delegated_from=delegated_from)


def sqlite_path(tmp_path) -> str:
    return os.path.join(str(tmp_path), "directory.sqlite3")


def memory_directory() -> InMemoryAuthorityDirectory:
    return InMemoryAuthorityDirectory()


def sqlite_directory(tmp_path) -> SqliteAuthorityDirectory:
    return SqliteAuthorityDirectory(sqlite_path(tmp_path))
