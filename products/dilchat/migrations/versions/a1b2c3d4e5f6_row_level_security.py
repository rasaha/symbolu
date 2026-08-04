"""PostgreSQL row-level security backstop (Area D)

Adds a database-level backstop under the application-layer ScopeContext:
- transaction-local context helpers (``app.current_user_id`` / ``app.current_actor_type``);
- distinct non-owner runtime roles (app / worker / read-only) with NOBYPASSRLS;
- ENABLE + FORCE ROW LEVEL SECURITY and policies on all 10 tables.

RLS is a defence-in-depth net, NOT a replacement for the application checks. It is
PostgreSQL-only; on SQLite (unit-test engine) this migration is a no-op.

Ownership note: ``couple_memberships`` membership checks use the SECURITY DEFINER
function ``app_is_active_member`` which must be owned by a role that can bypass RLS
(the migration/owner role). In production the migration owner must be such a role.

Revision ID: a1b2c3d4e5f6
Revises: 9c2b82ab02d2
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "9c2b82ab02d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ALL_TABLES = [
    "users", "user_sessions", "birth_profiles", "natal_chart_snapshots",
    "couples", "couple_memberships", "couple_invitations", "consent_events",
    "shared_artifacts", "audit_events",
]

# Runtime privilege grants. Immutable / append-only tables get no UPDATE/DELETE.
_APPEND_ONLY = {"natal_chart_snapshots", "shared_artifacts", "audit_events"}


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return  # SQLite unit-test engine: RLS is Postgres-only.

    # --- context + membership helper functions ------------------------------ #
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_current_user() RETURNS uuid
        LANGUAGE sql STABLE AS $$
          SELECT nullif(current_setting('app.current_user_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_actor_type() RETURNS text
        LANGUAGE sql STABLE AS $$
          SELECT coalesce(nullif(current_setting('app.current_actor_type', true), ''), 'none')
        $$;
        """
    )
    # SECURITY DEFINER so the membership lookup bypasses RLS (avoids policy recursion).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_is_active_member(p_couple uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER AS $$
          SELECT EXISTS (
            SELECT 1 FROM couple_memberships
            WHERE couple_id = p_couple
              AND user_id = app_current_user()
              AND status = 'ACTIVE'
          )
        $$;
        """
    )
    # Invitation acceptance lookup by token hash, bypassing RLS (holder of the
    # single-use token is authorised even though they are not the inviter).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_find_invitation(p_token_hash text) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER AS $$
          SELECT id FROM couple_invitations WHERE token_hash = p_token_hash
        $$;
        """
    )

    # --- runtime roles (idempotent) ----------------------------------------- #
    for role in ("dilchat_app", "dilchat_worker", "dilchat_readonly"):
        op.execute(
            f"""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                CREATE ROLE {role} NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
              END IF;
            END $$;
            """
        )
    op.execute("GRANT USAGE ON SCHEMA public TO dilchat_app, dilchat_worker, dilchat_readonly")
    op.execute(
        "GRANT EXECUTE ON FUNCTION app_current_user(), app_actor_type(), "
        "app_is_active_member(uuid), app_find_invitation(text) "
        "TO dilchat_app, dilchat_worker, dilchat_readonly"
    )
    for tbl in _ALL_TABLES:
        if tbl in _APPEND_ONLY:
            op.execute(f"GRANT SELECT, INSERT ON {tbl} TO dilchat_app, dilchat_worker")
        else:
            op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO dilchat_app, dilchat_worker")
        op.execute(f"GRANT SELECT ON {tbl} TO dilchat_readonly")

    # --- enable + force RLS ------------------------------------------------- #
    for tbl in _ALL_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")

    # --- policies ----------------------------------------------------------- #
    # users: own row (actor 'user') OR the pre-auth 'auth' path (register/login).
    op.execute(
        "CREATE POLICY users_self ON users FOR ALL "
        "USING (id = app_current_user()) WITH CHECK (id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY users_auth ON users FOR ALL "
        "USING (app_actor_type() = 'auth') WITH CHECK (app_actor_type() = 'auth')"
    )

    # user_sessions: own sessions, plus the 'auth' path for login/refresh.
    op.execute(
        "CREATE POLICY sessions_self ON user_sessions FOR ALL "
        "USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY sessions_auth ON user_sessions FOR ALL "
        "USING (app_actor_type() = 'auth') WITH CHECK (app_actor_type() = 'auth')"
    )

    # birth_profiles + natal snapshots: strictly owner-only.
    op.execute(
        "CREATE POLICY bp_owner ON birth_profiles FOR ALL "
        "USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user())"
    )
    op.execute(
        "CREATE POLICY natal_owner ON natal_chart_snapshots FOR ALL "
        "USING (user_id = app_current_user()) WITH CHECK (user_id = app_current_user())"
    )

    # couples: readable/updatable by active members; creation controlled by the app.
    op.execute(
        "CREATE POLICY couples_member ON couples FOR ALL "
        "USING (app_is_active_member(id)) WITH CHECK (true)"
    )

    # couple_memberships: own row or any row of a couple you actively belong to;
    # writes require an authenticated user (accept/unpair).
    op.execute(
        "CREATE POLICY memberships_read ON couple_memberships FOR SELECT "
        "USING (user_id = app_current_user() OR app_is_active_member(couple_id))"
    )
    op.execute(
        "CREATE POLICY memberships_write ON couple_memberships FOR ALL "
        "USING (app_is_active_member(couple_id) OR user_id = app_current_user()) "
        "WITH CHECK (app_actor_type() IN ('user', 'worker'))"
    )

    # couple_invitations: only the inviter can see/enumerate their invitations
    # (acceptance uses app_find_invitation(), which bypasses RLS by token).
    op.execute(
        "CREATE POLICY inv_owner ON couple_invitations FOR ALL "
        "USING (inviter_user_id = app_current_user()) "
        "WITH CHECK (inviter_user_id = app_current_user() OR app_actor_type() = 'worker')"
    )

    # consent_events: visible to active members; granted only by the granter.
    op.execute(
        "CREATE POLICY consent_member ON consent_events FOR ALL "
        "USING (app_is_active_member(couple_id)) "
        "WITH CHECK (granter_user_id = app_current_user() AND app_is_active_member(couple_id))"
    )

    # shared_artifacts: active members only (append-only via privilege grants).
    op.execute(
        "CREATE POLICY shared_member ON shared_artifacts FOR ALL "
        "USING (app_is_active_member(couple_id)) "
        "WITH CHECK (app_is_active_member(couple_id))"
    )

    # audit_events: actors read their own; inserts allowed; no UPDATE/DELETE grant.
    op.execute(
        "CREATE POLICY audit_read ON audit_events FOR SELECT "
        "USING (actor_user_id = app_current_user())"
    )
    op.execute("CREATE POLICY audit_insert ON audit_events FOR INSERT WITH CHECK (true)")


def downgrade() -> None:
    if not _is_postgres():
        return
    policies = {
        "users": ["users_self", "users_auth"],
        "user_sessions": ["sessions_self", "sessions_auth"],
        "birth_profiles": ["bp_owner"],
        "natal_chart_snapshots": ["natal_owner"],
        "couples": ["couples_member"],
        "couple_memberships": ["memberships_read", "memberships_write"],
        "couple_invitations": ["inv_owner"],
        "consent_events": ["consent_member"],
        "shared_artifacts": ["shared_member"],
        "audit_events": ["audit_read", "audit_insert"],
    }
    for tbl, names in policies.items():
        for name in names:
            op.execute(f"DROP POLICY IF EXISTS {name} ON {tbl}")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")
    for tbl in _ALL_TABLES:
        op.execute(
            f"REVOKE ALL ON {tbl} FROM dilchat_app, dilchat_worker, dilchat_readonly"
        )
    op.execute("DROP FUNCTION IF EXISTS app_find_invitation(text)")
    op.execute("DROP FUNCTION IF EXISTS app_is_active_member(uuid)")
    op.execute("DROP FUNCTION IF EXISTS app_actor_type()")
    op.execute("DROP FUNCTION IF EXISTS app_current_user()")
    # Roles are cluster-global and may be shared; revoke schema usage but leave the
    # role objects in place (dropping them can fail if they own other grants).
    op.execute(
        "REVOKE USAGE ON SCHEMA public FROM dilchat_app, dilchat_worker, dilchat_readonly"
    )
