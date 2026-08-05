# DilChat Secure Chat Backend — Data Model (Phase 3A)

Four relationship-scoped tables added on top of the existing 10 Phase A/B tables.
Portable types (`sa.Uuid`, timezone-aware `DateTime`, `BigInteger`, JSON→JSONB on
PostgreSQL) match the Phase A/B conventions in `base.py`/`orm.py`. Message bodies
are classified **SENSITIVE** and never logged, audited, traced, or placed in the
outbox.

ORM: `src/ugence_dilchat/infrastructure/chat_orm.py`
Migration: `migrations/versions/c3d4e5f6a7b8_secure_chat_backend_core.py`

## `chat_conversations`

One conversation per couple/relationship **instance**.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `couple_id` | uuid FK→`couples` (CASCADE) | **UNIQUE** (`uq_chat_conversation_couple`) |
| `status` | str(16) | `ACTIVE` \| `REVOKED` (CHECK) |
| `next_sequence` | bigint | per-conversation monotonic counter (next value to assign) |
| `version` | int | optimistic-concurrency counter (advisory) |
| `revoked_at` | timestamptz | set at unpair |
| `created_at`/`updated_at` | timestamptz | |

- A later re-pair creates a **new** `couples` row, therefore a new conversation.
- Membership is never stored here; it is resolved from `couple_memberships`.

## `chat_messages`

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | server-generated |
| `conversation_id` | uuid FK→`chat_conversations` (CASCADE) | indexed |
| `couple_id` | uuid FK→`couples` (CASCADE) | denormalised for RLS parity |
| `sender_user_id` | uuid FK→`users` | server-derived, never client-supplied |
| `client_message_id` | str(64) | client idempotency key (required) |
| `server_sequence` | bigint | monotonic, gapless cursor key |
| `body` | text (SENSITIVE) | cleared to `''` on tombstone |
| `created_at` | timestamptz | |
| `deleted_at` | timestamptz | tombstone marker |
| `deleted_by_user_id` | uuid FK→`users` (SET NULL) | |

Constraints/indexes:
- `uq_chat_message_idempotency (conversation_id, sender_user_id, client_message_id)`
- `uq_chat_message_sequence (conversation_id, server_sequence)` — doubles as the cursor index
- `ck_chat_message_body_len` — `length(body) <= 4000`
- `ck_chat_message_seq_positive` — `server_sequence >= 1`

Body policy (single source of truth: `Settings.chat_message_max_code_points = 4000`):
non-empty (not whitespace-only), ≤ 4000 Unicode code points, no NUL / C0-C1 control
characters or unpaired surrogates (newline/carriage-return/tab allowed).

## `chat_read_states`

One forward-only read cursor per member.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `conversation_id` | uuid FK (CASCADE) | |
| `couple_id` | uuid FK (CASCADE) | RLS parity |
| `user_id` | uuid FK→`users` | |
| `last_read_sequence` | bigint | forward-only; ≤ latest message sequence |
| `updated_at` | timestamptz | |

- `uq_chat_read_state_member (conversation_id, user_id)`
- A user updates only their own read state; repeated/backward updates are no-ops.

## `chat_outbox`

Transactional outbox — committed in the **same** transaction as each state change.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `event_type` | str(32) | CHECK: `CONVERSATION_CREATED`, `MESSAGE_CREATED`, `MESSAGE_DELETED`, `READ_STATE_UPDATED`, `CONVERSATION_REVOKED` |
| `schema_version` | int | event-schema version (starts at 1) |
| `conversation_id` | uuid FK (CASCADE) | indexed |
| `couple_id` | uuid FK (SET NULL) | indexed |
| `payload` | json/jsonb | **IDs + minimal metadata only — never a body/token/email/birth data** |
| `created_at` | timestamptz | indexed |
| `published_at` | timestamptz | set by a future relay (Phase 3C); unused for 3A correctness |

- `ix_chat_outbox_unpublished (published_at, created_at)` — for a future relay scan.
- The application (`OutboxRepository`) validates every payload against an allow-list
  of keys so a body can never leak into the outbox.

## Event schema (v1)

| Event | Payload keys |
|-------|--------------|
| `CONVERSATION_CREATED` | `conversation_id`, `couple_id` (+ `reason` on backfill) |
| `MESSAGE_CREATED` | `conversation_id`, `couple_id`, `message_id`, `sender_user_id`, `server_sequence` |
| `MESSAGE_DELETED` | `conversation_id`, `couple_id`, `message_id`, `sender_user_id`, `server_sequence`, `deleted_by_user_id` |
| `READ_STATE_UPDATED` | `conversation_id`, `couple_id`, `user_id`, `last_read_sequence` |
| `CONVERSATION_REVOKED` | `conversation_id`, `couple_id` |

## Entity relationships

```
couples (1) ──< couple_memberships (2 active members)
   │
   └── (1) chat_conversations ──< chat_messages
                               ──< chat_read_states (1 per member)
                               ──< chat_outbox (events)
```
