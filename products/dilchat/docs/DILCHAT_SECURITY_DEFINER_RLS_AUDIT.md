# DilChat — SECURITY DEFINER & RLS Audit (Workstream C)

Audit of every PostgreSQL function used by RLS policies, token lookup, membership
checks, and worker authorization, plus the RLS role/infrastructure controls. A
focused hardening migration (`b2c3d4e5f6a7`) closes the findings.

## 1. Function inventory (post-hardening)

| Function | Args | Owner | Security | Volatility | search_path | Granted to |
|----------|------|-------|----------|-----------|-------------|-----------|
| `app_current_user()` | – | postgres (migration owner) | INVOKER | STABLE | `pg_catalog, public` | app, worker, readonly, secfn_owner |
| `app_actor_type()` | – | postgres (migration owner) | INVOKER | STABLE | `pg_catalog, public` | app, worker, readonly, secfn_owner |
| `app_is_active_member(uuid)` | couple id | **dilchat_secfn_owner** | **DEFINER** | STABLE | `pg_catalog, public` | app, worker, readonly |
| `app_find_invitation(text)` | token hash | **dilchat_secfn_owner** | **DEFINER** | STABLE | `pg_catalog, public` | app, worker, readonly |

- **Tables accessed:** `app_is_active_member` → `couple_memberships` (SELECT only);
  `app_find_invitation` → `couple_invitations` (SELECT only). The context helpers
  read only GUC settings (`current_setting`), no tables.
- **Dynamic SQL:** none. All bodies are static parameterized SQL.
- **Policy dependencies:** `app_is_active_member` is used by the `couples`,
  `couple_memberships`, `consent_events`, and `shared_artifacts` policies;
  `app_find_invitation` supports invitation acceptance; the context helpers are used
  by every policy.
- **Return exposure:** `app_is_active_member` returns a **boolean**;
  `app_find_invitation` returns a **single invitation id** matched by exact
  (SHA-256) token hash. Neither returns row contents or enumerates unrelated rows.

## 2. Roles

| Role | super | bypassrls | login | createdb | createrole | Purpose |
|------|-------|-----------|-------|----------|-----------|---------|
| `dilchat_app` | f | f | f | f | f | API runtime |
| `dilchat_worker` | f | f | f | f | f | Background-worker runtime |
| `dilchat_readonly` | f | f | f | f | f | Read-only operational/support |
| `dilchat_secfn_owner` | f | **t** | **f** | f | f | Dedicated NOLOGIN owner of the SECURITY DEFINER helpers |

`dilchat_secfn_owner` has `BYPASSRLS` **only** so the bounded membership check does
not recurse through `couple_memberships`' own policy. It is non-login, owns no
tables, and is not a runtime role. It holds least-privilege `SELECT` on exactly the
two tables its helpers read.

## 3. Required-control checklist

### 3.1 Every SECURITY DEFINER function

| Control | Status |
|---------|--------|
| Explicit fixed `search_path` (`pg_catalog, public`) | ✅ (both) |
| Avoids caller-controlled schema resolution | ✅ (search_path pinned) |
| Owned by a dedicated non-login role, **not** the runtime app role | ✅ (`dilchat_secfn_owner`) |
| `PUBLIC EXECUTE` revoked; execute granted only to runtime roles | ✅ |
| No unbounded dynamic SQL | ✅ (static SQL) |
| Input validation / bounded output | ✅ (exact-match token; boolean/id only) |
| Does not expose unrelated rows or private-object existence | ✅ (boolean / single id) |
| Non-replaceable by runtime roles | ✅ (not owner; tested) |

### 3.2 Runtime roles cannot

| Attempt | Result |
|---------|--------|
| Alter / replace a helper | denied (not owner) — tested |
| Change owner / search_path | denied — tested |
| Grant execute to others | no-op (no grant option); target still cannot execute — tested |
| Create shadow objects in `public` | denied (`CREATE` revoked from PUBLIC + roles) — tested |
| Disable RLS / use BYPASSRLS / assume owner | denied; `rolbypassrls=false` — tested |

## 4. `SET LOCAL` / `set_config` / transaction review

Context is set with `set_config('app.current_user_id', …, is_local => true)` inside
each request/worker transaction (DEC-030); values are transaction-scoped and do not
leak across pooled connections (test
`test_transaction_local_context_does_not_leak_across_pool`). The API sets a pre-auth
`auth` context and upgrades to `user` from the verified JWT before any scoped query;
workers set `worker` before writing.

## 5. Test evidence (real non-owner roles)

`tests/security/test_rls.py` (7) + `tests/security/test_security_definer.py` (7),
run under `SET LOCAL ROLE dilchat_app` / `dilchat_worker` / `dilchat_nogrant`:

- helper owner/security-mode/search_path metadata correct; owner is non-login;
- PUBLIC (a no-grant role) cannot execute restricted helpers;
- runtime cannot replace / alter config / alter owner / effectively grant execute;
- runtime cannot create shadow objects in `public`;
- runtime cannot disable RLS; `rolbypassrls=false`;
- token lookup returns only the intended invitation; membership helper returns a
  boolean (no enumeration);
- stale worker write blocked after revocation; cross-private returns no rows;
  former member loses shared access after unpair; audit/shared artifacts immutable
  (no UPDATE/DELETE grant); pooled context does not leak.

## 6. Findings & resolution

| Finding | Severity | Resolution |
|---------|----------|-----------|
| SECURITY DEFINER helpers had **no fixed search_path** (shadowing risk) | High | Pinned `pg_catalog, public` on all four helpers (migration `b2c3d4e5f6a7`) |
| Helpers owned by the **migration/superuser** role, not a dedicated role | Medium | Moved to non-login `dilchat_secfn_owner` (BYPASSRLS, least-privilege SELECT) |
| `PUBLIC EXECUTE` present on helpers | Medium | Revoked; granted only to runtime roles (+ owner for internal calls) |
| `PUBLIC`/runtime `CREATE` on schema `public` | Low | Revoked explicitly |

## 7. Verdict

**`SECURITY_DEFINER_RLS_HARDENED`.** All SECURITY DEFINER helpers have a fixed
search_path, a dedicated non-login owner, least-privilege table grants, and no
PUBLIC execute; runtime roles cannot alter, replace, re-own, grant, shadow, or
bypass them, proven through real non-owner PostgreSQL roles. The one residual design
choice — `dilchat_secfn_owner` holds `BYPASSRLS` — is required for the bounded,
non-recursive membership check and is scoped to a non-login role with boolean/id
outputs only.
