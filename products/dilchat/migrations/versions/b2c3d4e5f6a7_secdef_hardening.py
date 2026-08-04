"""SECURITY DEFINER hardening (Workstream C)

Hardens the RLS helper functions:
- move the two SECURITY DEFINER helpers to a dedicated NOLOGIN owner role
  (``dilchat_secfn_owner``) so runtime roles can never alter/replace them;
- pin an explicit ``search_path = pg_catalog, public`` on every helper so a runtime
  role cannot redirect them through a shadow object;
- revoke ``PUBLIC`` execute and grant execute only to the runtime roles.

The dedicated owner has BYPASSRLS (required so the bounded, boolean-returning
membership check does not recurse through couple_memberships' own policy); it is a
non-login role distinct from every runtime role, and the helpers return only a
boolean / a single id, so no rows leak.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SECDEF = ["app_is_active_member(uuid)", "app_find_invitation(text)"]
_INVOKER = ["app_current_user()", "app_actor_type()"]
_ALL = _SECDEF + _INVOKER
_RUNTIME = "dilchat_app, dilchat_worker, dilchat_readonly"


def _pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _pg():
        return
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'dilchat_secfn_owner') THEN
            CREATE ROLE dilchat_secfn_owner NOLOGIN NOINHERIT BYPASSRLS
              NOCREATEDB NOCREATEROLE;
          END IF;
        END $$;
        """
    )
    # Dedicated owner for the SECURITY DEFINER helpers.
    for fn in _SECDEF:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO dilchat_secfn_owner")
    # The definer runs as this owner: it bypasses RLS but still needs table-level
    # SELECT on EXACTLY the tables its helpers read (least privilege).
    op.execute("GRANT SELECT ON couple_memberships TO dilchat_secfn_owner")
    op.execute("GRANT SELECT ON couple_invitations TO dilchat_secfn_owner")
    # Pin search_path on every helper (defeats shadow-object redirection).
    for fn in _ALL:
        op.execute(f"ALTER FUNCTION {fn} SET search_path = pg_catalog, public")
    # Lock down execute privileges.
    for fn in _ALL:
        op.execute(f"REVOKE ALL ON FUNCTION {fn} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO {_RUNTIME}")
    # The SECURITY DEFINER helpers (running as dilchat_secfn_owner) internally call
    # the context helpers, so the owner needs EXECUTE on those too.
    for fn in _INVOKER:
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO dilchat_secfn_owner")
    # Belt-and-braces: runtime roles must not be able to create shadow objects in
    # public (PG15+ already removes PUBLIC CREATE, but assert it explicitly).
    op.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
    op.execute("REVOKE CREATE ON SCHEMA public FROM dilchat_app, dilchat_worker, dilchat_readonly")


def downgrade() -> None:
    if not _pg():
        return
    # Reassign helpers back to the migration role and relax config/grants.
    op.execute("REVOKE SELECT ON couple_memberships FROM dilchat_secfn_owner")
    op.execute("REVOKE SELECT ON couple_invitations FROM dilchat_secfn_owner")
    for fn in _SECDEF:
        op.execute(f"ALTER FUNCTION {fn} OWNER TO CURRENT_USER")
    for fn in _ALL:
        op.execute(f"ALTER FUNCTION {fn} RESET search_path")
        op.execute(f"GRANT EXECUTE ON FUNCTION {fn} TO PUBLIC")
    # dilchat_secfn_owner is left in place (may be shared / own nothing after reassign).
