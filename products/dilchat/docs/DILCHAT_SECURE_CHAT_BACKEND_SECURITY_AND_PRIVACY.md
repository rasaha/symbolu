# DilChat Secure Chat Backend — Security & Privacy (Phase 3A)

Secure chat is defended in depth: **application authorization** and **PostgreSQL
RLS** each independently deny unauthorized access, and both fail closed.

## 1. Authorization model

Every operation follows:

```
authenticated user
 → authoritative ACTIVE relationship membership (couple_memberships)
 → conversation owned by that relationship (chat_conversations.couple_id)
 → operation-specific authorization
```

Authorization is **never** derived from a client-supplied conversation id, message
id, or sender id, nor from cached mobile state, invitation state, or prior
membership. Membership is resolved through the shared `authorize_shared` decision
function (`security/scope.py`, default deny). Existence non-disclosure (INV-9) is
preserved: non-members receive a uniform **404**.

## 2. PostgreSQL Row-Level Security

RLS is `ENABLE`d + `FORCE`d on `chat_conversations`, `chat_messages`,
`chat_read_states`, and `chat_outbox`. Policies reuse the existing transaction-local
context (`app.current_user_id` / `app.current_actor_type`, DEC-030) and the
SECURITY DEFINER helper `app_is_active_member(couple_id)` (DEC-034/DEC-038).

| Table | Policy (USING / WITH CHECK) |
|-------|-----------------------------|
| `chat_conversations` | member-visible: `app_is_active_member(couple_id)` / `true` (app-controlled creation) |
| `chat_messages` | `app_is_active_member(couple_id)` / `app_is_active_member(couple_id) AND sender_user_id = app_current_user()` |
| `chat_read_states` | `app_is_active_member(couple_id)` / `app_is_active_member(couple_id) AND user_id = app_current_user()` |
| `chat_outbox` | INSERT: `true`; SELECT/UPDATE: `app_actor_type() = 'worker'` only |

Consequences:
- Unpair revokes memberships → members instantly lose row visibility.
- A member can only write messages **as themselves** and read-state **for
  themselves** — enforced at the database layer, not just the app.
- The **outbox is never exposed to the user API surface**: the app role may only
  `INSERT`; only the internal `dilchat_worker` role may read/mark-published. The
  read-only reporting role has no outbox access at all.

Runtime roles (`dilchat_app`, `dilchat_worker`, `dilchat_readonly`) are
`NOSUPERUSER NOBYPASSRLS` non-owners; messages grant no hard `DELETE` (tombstone
only). Proven through a **non-owner role** in `tests/security/test_chat_rls.py`.

## 3. Message-content confidentiality

The message `body` is classified **SENSITIVE** and appears in exactly one place —
the `chat_messages.body` column. It is never written to:

- structured logs (a redaction processor also drops `content`/`note`/`body`-like keys);
- audit rows (audit records IDs/action/outcome only);
- tracing spans or metrics labels;
- **outbox payloads** (payloads are IDs + minimal metadata; an allow-list rejects any other key).

Deletion **physically clears** the stored body (`body = ''`) while retaining the
row and metadata (tombstone). Proven by `tests/security/test_chat_no_logging.py`
(log capture on success + error paths; outbox/audit body-absence).

## 4. Input & transport hardening

- Parameterised queries only; no SQL assembled from user input.
- Bounded body length (4000 code points), bounded page size (≤100), bounded cursor
  size; NUL/control-character rejection.
- Request-level idempotency; consistent conversation-row lock ordering; no blind
  retry after ambiguous DB failure.
- No internal SQL error text returned to clients; no token in errors.
- No AI/analytics/astrology/compatibility consumer of message content.

## 5. Account deletion & retention (V1 baseline)

Deterministic V1 behaviour (no broad legal-retention framework is invented here):

- Account deletion **dissolves the active relationship** — the same transactional
  revocation path as unpair — so conversation access is revoked at once. (A
  standalone account-deletion endpoint is Phase 3B; see OQ-CHAT-2.)
- Normal user APIs no longer expose message bodies after revocation.
- Tombstones + minimal audit metadata follow the existing deletion policy; **no
  message body is copied to an audit table or logs**; outbox events reference
  stable internal IDs only.

**Open questions** (recorded, not silently resolved):

| OQ | Question |
|----|----------|
| OQ-CHAT-1 | Do ended couples retain a read-only export of prior messages? Current policy: **no retained access** (parallels OQ-14 for shared artifacts). |
| OQ-CHAT-2 | Exact account-deletion semantics (hard-erase vs tombstone retention window) — deferred to Phase 3B. |

No GDPR/DPDP/HIPAA or other regulatory compliance is claimed without a separate review.

## 6. Threats explicitly tested

Stranger; user in another pair; former partner after unpair; forged conversation
id; forged message id; forged sender; cross-couple cursor; revoked session;
expired token; concurrent unpair; cross-couple SQL under the runtime role; outbox
exposure to app/read-only roles; sender-spoofed message insert; hard-delete
attempt.
