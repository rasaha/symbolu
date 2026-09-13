"""Provisioning statements for tenant-bound runtime identities (LP-6 step 4).

This module emits SQL; it never executes DDL at import or at startup, and it never
carries a credential. A deployment's migration identity (``meu_migrator``, assuming the
owner role during a reviewed migration) runs what :func:`identity_statements` returns;
the login credential for the new identity is set afterwards through the deployment's
database custody, which is not this package.

An identity is one login role per (tenant, side): it inherits the side's grants
through membership in ``meu_worker`` or ``meu_unit`` and is bound to exactly one
tenant in ``role_tenant_binding``, after which the ``identity_binding`` policy ignores
whatever tenant its session claims. :func:`identity_report` lists every login member
of the runtime roles and whether it is bound, so a deployment gate can refuse to run
with an unbound login identity, which the database itself cannot forbid.
"""

from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from .schema import BINDING_TABLE, OWNER_ROLE, SCHEMA_NAME, UNIT_ROLE, WORKER_ROLE

__all__ = ["identity_name", "identity_statements", "bind_identity", "identity_report"]

_SIDES = {"worker": WORKER_ROLE, "unit": UNIT_ROLE}


def identity_name(side: str, tenant_id: UUID) -> str:
    """``meu_worker_t_<first 12 hex of the tenant>``: derivable, never colliding across
    sides, and short enough for PostgreSQL's 63-character identifier limit."""

    if side not in _SIDES:
        raise ValueError("side is 'worker' or 'unit'")
    return f"{_SIDES[side]}_t_{UUID(str(tenant_id)).hex[:12]}"


def identity_statements(side: str, tenant_id: UUID, *, login: bool = True) -> List[str]:
    """The statements a migrator runs, as the owner, to create one bound identity.

    No password: the credential is set out of band by the deployment's custody
    (``ALTER ROLE ... PASSWORD`` or certificate mapping), never by this package.
    """

    name = identity_name(side, tenant_id)
    group = _SIDES[side]
    tenant = str(UUID(str(tenant_id)))
    return [
        f"CREATE ROLE {name} {'LOGIN' if login else 'NOLOGIN'} NOSUPERUSER NOBYPASSRLS "
        f"NOCREATEDB NOCREATEROLE INHERIT IN ROLE {group}",
        f"SET ROLE {OWNER_ROLE}",
        f"INSERT INTO {SCHEMA_NAME}.{BINDING_TABLE} (role_name, tenant_id) VALUES ('{name}', '{tenant}')",
        "RESET ROLE",
    ]


def bind_identity(conn, role_name: str, tenant_id: UUID) -> None:
    """Write the binding row as the owner. For a migrator or a test cluster only."""

    with conn.cursor() as cur:
        cur.execute(f"SET ROLE {OWNER_ROLE}")
        try:
            cur.execute(
                f"INSERT INTO {SCHEMA_NAME}.{BINDING_TABLE} (role_name, tenant_id) VALUES (%s, %s)",
                (role_name, str(UUID(str(tenant_id)))))
        finally:
            cur.execute("RESET ROLE")


def identity_report(conn) -> List[dict]:
    """Every login member of a runtime role, with its binding. An unbound login
    identity is a finding a deployment gate refuses on; the reference path's
    NOLOGIN group roles are not listed."""

    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT m.rolname, g.rolname AS group_role, b.tenant_id::text
                FROM pg_auth_members am
                JOIN pg_roles m ON m.oid = am.member
                JOIN pg_roles g ON g.oid = am.roleid
                LEFT JOIN {SCHEMA_NAME}.{BINDING_TABLE} b ON b.role_name = m.rolname
                WHERE g.rolname IN (%s, %s) AND m.rolcanlogin
                ORDER BY m.rolname""", (WORKER_ROLE, UNIT_ROLE))
        return [{"role": r[0], "group": r[1], "tenant_id": r[2], "bound": r[2] is not None}
                for r in cur.fetchall()]
