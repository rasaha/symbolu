# DilChat Secure Chat Backend — Migration & Rollback (Phase 3A)

Migration: `migrations/versions/c3d4e5f6a7b8_secure_chat_backend_core.py`
Revises: `b2c3d4e5f6a7` (SECURITY DEFINER hardening) · **single head** `c3d4e5f6a7b8`.

## Upgrade

1. **Create tables** (portable DDL, applies on SQLite and PostgreSQL):
   `chat_conversations`, `chat_messages`, `chat_read_states`, `chat_outbox`, with
   their unique constraints, cursor/foreign-key indexes, and CHECK constraints.
2. **PostgreSQL-only** (guarded by dialect check), in order:
   1. **Backfill** — one `ACTIVE` conversation per `ACTIVE` couple that has none
      (`gen_random_uuid()`); a `CONVERSATION_CREATED` outbox event per backfilled
      conversation. **Revoked (UNPAIRED) couples receive no active conversation.**
      Backfill runs **before** `FORCE` RLS so it is not blocked.
   3. **Grants** (least privilege): `SELECT, INSERT, UPDATE` on the three user
      tables to `dilchat_app`/`dilchat_worker`, `SELECT` to `dilchat_readonly`; on
      `chat_outbox` only `INSERT` to the app and `SELECT, INSERT, UPDATE` to the
      worker (no read-only access, no hard `DELETE` anywhere).
   4. **`ENABLE` + `FORCE` RLS** on all four tables.
   5. **Policies** (see the Security & Privacy doc).

The migration reuses the existing `app_is_active_member` / `app_current_user` /
`app_actor_type` helpers — no new SECURITY DEFINER function is introduced.

## Downgrade

Symmetric and deterministic: drop policies → `NO FORCE` / `DISABLE` RLS → revoke
grants → drop the four tables (FK-safe order: outbox, read-states, messages,
conversations). On SQLite the RLS/grant steps are skipped.

## Data safety

- Existing Phase A/B data is untouched; the migration is additive.
- Uniqueness (`uq_chat_conversation_couple`) prevents duplicate conversations,
  including under concurrent acceptance.
- No destructive table rewrite; no production-data assumptions; no production
  secrets.

## Verified (real PostgreSQL 16)

| Check | Result |
|-------|--------|
| `alembic upgrade base → head` | ✅ |
| Exactly one Alembic head | ✅ `c3d4e5f6a7b8` |
| `downgrade -1` then `upgrade head` | ✅ |
| `downgrade base` then `upgrade head` | ✅ |
| Backfill: ACTIVE couple → 1 ACTIVE conversation; UNPAIRED couple → 0 | ✅ |
| Backfill emits `CONVERSATION_CREATED` | ✅ |
| Re-upgrade after downgrade is idempotent in shape | ✅ |

Tests: `tests/integration/test_chat_migrations.py` (marked `postgres`).
