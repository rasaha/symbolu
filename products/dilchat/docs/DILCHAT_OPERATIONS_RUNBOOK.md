# DilChat operations runbook — configuration, backup/restore, migrations (round PR-A)

Scope: the production-readiness track's first round (owner record DILCHAT-D-PR,
round PR-A). Covers environment configuration and fail-fast guards, the
telemetry/log content posture, backup/restore, and migration operations for
the **internal pilot** target (D-PR-2). Deployment artifacts, pilot rollout,
and incident runbooks are round PR-C; public production is a separate, later
owner launch decision.

## 1. Processes and roles

| Process | Entry point | DB role | Notes |
|---|---|---|---|
| Web/API | ASGI app `ugence_dilchat.app:create_app` (uvicorn) | `dilchat_app` | Never holds worker outbox privileges (DEC-3C-4 / I6). |
| Outbox relay | `python -m ugence_dilchat.relay` | `dilchat_worker` | Separate process; if down, messaging stays correct and push degrades independently. |
| Migrations | `alembic upgrade head` | owner role | Run before starting either process on a new schema version. |

Roles (`dilchat_app`, `dilchat_worker`, `dilchat_readonly`, `dilchat_safety`,
the SECURITY DEFINER function owner) are **cluster-level**: they are created by
the RLS migrations and must exist in any cluster a dump is restored into
(see §4).

## 2. Environment configuration

All settings are `DILCHAT_`-prefixed (see `.env.example` for the full
reference). Fail-fast guards enforced at startup in **staging/production**
(`config.py::Settings._guard`; pinned by `tests/unit/test_production_guards.py`):

- `DILCHAT_ACCESS_TOKEN_PRIVATE_KEY_PEM` must be set (ES256 signing key).
- `DILCHAT_DEBUG` must be false.
- `DILCHAT_DATABASE_URL` must be explicitly set (the local-development default
  is refused) and must use `postgresql+asyncpg`.
- `DILCHAT_ASTROLOGY_PROVIDER` must be an approved real provider with
  `DILCHAT_SWISS_PRODUCTION_LICENSED=true` (DEC-029/DEC-007) — no fake fallback.
- With `DILCHAT_PUSH_TRANSPORT=expo`, `DILCHAT_EXPO_PUSH_URL` must be https.
- Unknown `DILCHAT_PUSH_TRANSPORT` values are refused in every environment.

A guard violation is a **safe startup failure**: the process exits before
serving traffic. Never work around a guard by relabelling the environment.

`DILCHAT_RETENTION_PURGE_ENABLED` stays `false` until every D-PR-3 gate passes
(purge tests, preservation proofs, boundary tests, backup implications
documented, legal review, dry-run evidence). Enabling it is an owner decision
recorded in the decision log, not an operational toggle.

## 3. Telemetry and log content posture

- Logs are structured JSON (structlog) with a redaction processor
  (`logging.py::_REDACT_KEYS`) dropping secrets, tokens, push/device tokens,
  message bodies, report evidence/description text, coordinates, emails, and
  DSNs — defence in depth on top of call-site discipline.
- `Settings` repr/str never includes the signing key or database DSN.
- The relay stores/logs only machine-style error codes: anything that is not
  `^[A-Z0-9_]{1,64}$` is replaced with `TRANSPORT_UNAVAILABLE` before it can
  reach `last_error_code` or a log line (I7).
- Pinned by `tests/security/test_no_sensitive_logging.py`,
  `tests/security/test_chat_no_logging.py`, and the leaky-transport test in
  `tests/integration/test_relay_flows.py`. Treat any new log call that carries
  user content as a defect.

## 4. Backup and restore

Backups use `pg_dump --format=custom` of the whole database. Validation (run
against every backup procedure change, and periodically against real backups):

```bash
SOURCE_URL=postgresql://…/dilchat \
RESTORE_URL=postgresql://…/dilchat_restore_validate \
  scripts/validate_backup_restore.sh
```

The script dumps the source, restores into the target, and fails unless the
Alembic stamp, public table set, and exact per-table row counts match. CI runs
it after the full test suite (real migrated schema + test data), so the
committed schema is proven restorable on every change.

Cautions:

- **Roles first.** GRANTs and RLS policies reference the `dilchat_*` roles;
  restoring into a cluster without them fails. Same-cluster restores are safe;
  for a new cluster, run the role-creating migrations (or create the roles)
  before `pg_restore`.
- The restore target must be an existing, empty, disposable database; the
  script refuses names that do not look disposable.
- A dump contains **everything**, including message bodies and report
  evidence. Backup artifacts inherit the production data-protection posture:
  encrypt at rest, restrict access, and delete on the same retention clock as
  the database (final policy is a D-PR-3/legal item).

## 5. Migrations

- Forward: `alembic upgrade head` with the owner role, before rolling
  processes onto a new version. Exactly one head is enforced.
- Every migration ships a real `downgrade()`. **Downgrades drop data** — in
  anything production-like they are a last resort; prefer restoring the
  pre-upgrade backup (§4) taken immediately before every production upgrade.
- Cycle validation (upgrade → single head → downgrade → re-upgrade), the same
  script CI runs:

```bash
DILCHAT_DATABASE_URL=postgresql+asyncpg://…/dilchat_validate \
  scripts/validate_migration_cycle.sh
```

  Destructive by design — point it only at a disposable database (the script
  refuses non-disposable-looking names).

## 6. Standard procedures

**Pre-upgrade (pilot):** take a `pg_dump -Fc` backup → run
`validate_backup_restore.sh` against it (fresh disposable target) → `alembic
upgrade head` → start web + relay → check `/v1/health` and relay startup log
line (`relay started transport=…`).

**Recovery:** stop web + relay → restore the latest validated dump into a
fresh database (§4 cautions) → point `DILCHAT_DATABASE_URL` at it → start
web + relay. Push delivery loss during the outage is acceptable by design
(push is advisory, D3C-1/I5); the outbox in the restored state re-drains.
