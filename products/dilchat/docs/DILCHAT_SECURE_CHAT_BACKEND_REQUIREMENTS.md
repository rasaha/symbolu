# DilChat Secure Chat Backend — Requirements (Phase 3A)

**Product:** DilChat (consumer) · **Company:** Ugence Labs
**Scope:** Backend only. **Subordinate to** [`DILCHAT_DECISION_LOG.md`](DILCHAT_DECISION_LOG.md) — on any conflict the Decision Log wins.

Phase 3A delivers the **secure, relationship-scoped, text-only chat backend core**
for the existing paired-relationship (couple) model. It creates backend
foundations only — no mobile/web chat UI, no real-time transport, no AI.

## 1. Objective

A secure partner chat that guarantees:

- exactly **one conversation per active paired relationship instance**;
- only the **two authorized relationship members** can access it;
- durable **text-message persistence**;
- **idempotent** message creation;
- stable **cursor pagination**;
- **read-state** tracking;
- **immediate access revocation** when the pair is dissolved (unpair);
- **no message committed after relationship revocation becomes effective**;
- **no cross-couple data leakage**;
- **no dependency on WebSockets or push** for correctness;
- a **transactional outbox** for later real-time delivery;
- PostgreSQL **RLS and application authorization both fail closed**.

## 2. In scope

| # | Requirement |
|---|-------------|
| R-1 | Durable `chat_conversations`, one per couple (unique `couple_id`). |
| R-2 | Conversation provisioned in the **same transaction** as invitation acceptance; existing active pairs backfilled by migration. |
| R-3 | Text `chat_messages` with server id, monotonic per-conversation `server_sequence`, client idempotency key, bounded body. |
| R-4 | Idempotency scope `(conversation, sender, client_message_id)`; retries return the original; key reuse with a different body conflicts. |
| R-5 | Opaque, versioned **cursor pagination** (default 50, max 100); malformed/cross-conversation cursor fails closed (400). |
| R-6 | `chat_read_states`: one **forward-only** cursor per member; idempotent; cannot exceed the latest message. |
| R-7 | Tombstone deletion (sender-only); body physically cleared, metadata retained. |
| R-8 | Unpair **revokes** the conversation in the authoritative transaction; new sends/reads/read-state immediately denied. |
| R-9 | **Transactional outbox** (`chat_outbox`) committed with each state change; IDs/metadata only, never a body. |
| R-10 | PostgreSQL **RLS** on all user-facing chat tables (`ENABLE` + `FORCE`), non-owner runtime role, fail closed; outbox restricted to the internal worker role. |
| R-11 | Bounded REST surface (see the API contract). No arbitrary conversation-creation endpoint. |
| R-12 | Message content never reaches logs, audit rows, tracing, metrics, or outbox payloads. |

## 3. Out of scope (explicit exclusions)

Mobile/web chat UI; WebSocket/SSE production transport; push notifications;
attachments/images/audio/video; reactions; typing indicators; message editing;
group chat; public profiles; Friends Finder / Relationship Discovery; candidate
ranking; Guna execution; Moon receptivity; compatibility scoring; AI Assist;
conversation preference inference; LLM calls; summarization; sentiment/moderation
classifiers; HTTPS invitation landing pages; App Links / Universal Links; Android
or iOS changes; production deployment; production secrets; payments.

No message content is exposed to any AI, analytics, recommendation, astrology,
inference, or profiling system.

## 4. Concurrency invariants

| Invariant | How it is enforced |
|-----------|--------------------|
| Exactly one message per idempotency key under concurrency | Conversation row lock (`SELECT … FOR UPDATE`) serialises sends; `uq_chat_message_idempotency` is the DB backstop. |
| Gapless, monotonic `server_sequence` | Per-conversation `next_sequence` counter incremented under the conversation row lock. |
| No message commits after revocation is effective | Send and unpair take the **same** conversation row lock; a send re-reads `status` under the lock and is rejected if `REVOKED`. |
| No duplicate conversation under concurrent acceptance | `uq_chat_conversation_couple`. |
| Atomic state + event | Outbox row written in the same transaction; rollback removes both. |

Allowed send-vs-unpair outcomes: (1) message commits, then revocation commits; or
(2) revocation commits first, and the send is rejected. Forbidden: a message
commits after revocation became effective.

## 5. Roadmap position

See [`DILCHAT_IMPLEMENTATION_ROADMAP.md`](DILCHAT_IMPLEMENTATION_ROADMAP.md) §Secure chat.

```
Phase 3A — Secure chat backend core        ← THIS PHASE
Phase 3B — Safety, block/report, retention/export policy
Phase 3C — Real-time delivery transport
Phase 3D — Mobile chat interface
Phase 4A — Conversation evidence
Phase 4B — Guna structural prior
Phase 4C — Moon receptivity
Phase 4D — AI Assist
```

Phase 3A alone does **not** make the product production-ready. Friends Finder /
Relationship Discovery remains a separate requirements track.
