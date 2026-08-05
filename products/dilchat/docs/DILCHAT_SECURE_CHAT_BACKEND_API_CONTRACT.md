# DilChat Secure Chat Backend — API Contract (Phase 3A)

Bounded REST surface under the existing `/v1` prefix. Errors use the repository
`Problem` (RFC 7807-style) envelope with a stable machine `code`. The generated
OpenAPI artifact is committed at
[`docs/openapi/dilchat.generated.openapi.json`](openapi/dilchat.generated.openapi.json);
a contract-drift test keeps it in sync.

There is **no arbitrary conversation-creation endpoint** — conversations are
provisioned only through the pairing lifecycle.

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/conversations/current` | The caller's active paired conversation summary. |
| GET | `/v1/conversations/{conversation_id}/messages` | Cursor-paginated messages. |
| POST | `/v1/conversations/{conversation_id}/messages` | Create a message (idempotent). |
| DELETE | `/v1/conversations/{conversation_id}/messages/{message_id}` | Tombstone the caller's own message. |
| PUT | `/v1/conversations/{conversation_id}/read-state` | Advance the caller's read cursor. |

All routes require a valid bearer access token **and** an authoritative ACTIVE
membership of the conversation's couple. A conversation id, message id, or
client-supplied sender never establishes access.

### GET /v1/conversations/current → 200 `ConversationResponse`

```json
{ "conversation_id": "…", "couple_id": "…", "status": "ACTIVE",
  "created_at": "…", "latest_sequence": 12, "last_read_sequence": 9,
  "member_user_ids": ["…","…"] }
```
No active pair (or the pair is revoked) → **404** (`NOT_FOUND`). No message bodies.

### POST …/messages → 201 `MessageResponse`

Request: `{ "client_message_id": "<=64 chars, [A-Za-z0-9._:-]>", "body": "<=4000 code points>" }`

- First request creates the message and returns `server_sequence`, `created_at`,
  `deleted:false`, `body`.
- Exact retry (same key + body) returns the **original** message — no new row, no new event.
- Same key + **different** body → **409** `IDEMPOTENCY_CONFLICT`.
- Concurrent duplicates create exactly one message.
- Empty/whitespace/oversized/control-char body → **422** `VALIDATION_ERROR`.
- Malformed `client_message_id` → **422**.
- Conversation revoked → **409** `CONVERSATION_NOT_ACTIVE`; not a member → **404**.

Idempotency scope: `(conversation, sender, client_message_id)`. The API does not
blindly retry after an ambiguous DB failure.

### GET …/messages → 200 `MessageListResponse`

Query: `cursor` (opaque, optional), `limit` (1–100, default 50).

```json
{ "messages": [ { "message_id":"…","sender_user_id":"…","server_sequence":1,
                  "body":"…","created_at":"…","deleted":false,"deleted_at":null } ],
  "next_cursor": "…", "has_more": true }
```
- Ascending, deterministic order by `server_sequence`; cursor-only (no offset).
- Opaque **versioned** cursor bound to its conversation.
- Malformed cursor → **400** `INVALID_CURSOR`; a cursor from another conversation
  fails closed → **400**.
- `limit` above the maximum → **422** (schema bound); the service also caps at 100.
- Tombstoned messages appear with metadata and `body: null`.
- Revoked conversation → 404/403 per anti-enumeration; no cross-couple leakage.

### DELETE …/messages/{message_id} → 200 `MessageResponse` (tombstone)

- Only the **sender** may delete → otherwise **403** `SCOPE_DENIED`.
- Body cleared; `deleted:true`, `deleted_at` set, metadata retained.
- Repeat deletion is idempotent (no second event).
- Unknown/cross-conversation message id → **404**.
- Denied after relationship revocation.

### PUT …/read-state → 200 `ReadStateResponse`

Request: `{ "last_read_sequence": <int ≥ 0> }`

- Forward-only; repeated/backward values are no-ops (no event).
- Target beyond the latest message → **422** `VALIDATION_ERROR`.
- Emits `READ_STATE_UPDATED` only when the cursor advances.
- Denied after unpair.

## Error codes (added in Phase 3A)

| Code | HTTP | Meaning |
|------|------|---------|
| `CONVERSATION_NOT_ACTIVE` | 409 | Conversation revoked (relationship dissolved). |
| `IDEMPOTENCY_CONFLICT` | 409 | Client message id reused with a different body. |
| `INVALID_CURSOR` | 400 | Malformed or cross-conversation pagination cursor. |

Reused: `AUTH_*` (401), `SCOPE_DENIED` (403), `NOT_FOUND` (404),
`VALIDATION_ERROR` (422). Foreign conversations/messages are **not** disclosed
(uniform 404 / anti-enumeration).

## Anti-enumeration matrix

| Caller | Result |
|--------|--------|
| Not a member (stranger / other pair / forged id) | **404** |
| Member, wrong operation (delete another's message) | **403** |
| Former member after unpair | **403** (existence already known) / **404** at the DB layer via RLS |
