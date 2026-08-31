# DilChat Secure Chat Backend — Implementation Report (Phase 3A)

**Scope:** Backend-only secure shared chat core. Developed independently of open
Mobile Phase 2 PR #1343 (not modified, not used as a base).

## 1. What was built

- **Data model** (`infrastructure/chat_orm.py`): `chat_conversations`,
  `chat_messages`, `chat_read_states`, `chat_outbox`.
- **Migration** (`c3d4e5f6a7b8`): tables, constraints, indexes, active-pair
  backfill, grants, RLS `ENABLE`+`FORCE`, policies. Single head.
- **Repositories** (`repositories/chat.py`) and a transactional **service**
  (`services/chat.py`) with an opaque cursor (`services/chat_cursor.py`).
- **API** (`api/routes/chat.py`, `api/schemas.py`): 5 bounded routes wired into
  the v1 router; conversation provisioning at pairing and transactional revocation
  at unpair (`api/routes/couples.py`).
- **Config** policy constants (`chat_message_max_code_points=4000`,
  `chat_page_default=50`, `chat_page_max=100`).
- **Docs** (this suite) + CI contract gate.

## 2. Test evidence (real PostgreSQL 16 + Python 3.12)

| Gate | Result |
|------|--------|
| ruff | ✅ clean |
| mypy | ✅ no issues (58 source files) |
| Baseline suite (before) | 201 passed, 0 skipped |
| **Full suite (after)** | **274 passed, 0 skipped** (73 new) |
| PostgreSQL-marked tests collected | 39 (no silent skips) |
| Alembic: base→head, one head, downgrade/re-upgrade | ✅ head `c3d4e5f6a7b8` |
| Backfill (active→1 ACTIVE conv; unpaired→0) | ✅ |
| Idempotency (replay, conflict, concurrent duplicates) | ✅ |
| 20 concurrent unique sends → gapless 1..20 | ✅ |
| **Send/unpair race (no commit after revoke)** | ✅ |
| Delete/read-state after revoke denied | ✅ |
| Account-deletion effect blocks send | ✅ |
| Cross-couple isolation (app + RLS layers) | ✅ |
| RLS under non-owner runtime role | ✅ (8 SQL-level tests) |
| **Outbox app-role UPDATE/DELETE denied; worker UPDATE allowed** | ✅ (`test_outbox_app_role_cannot_update_or_delete_worker_may_update`) |
| Outbox atomicity (rollback removes state+event) | ✅ |
| Outbox not on user API surface (worker-only read) | ✅ |
| **Default page size (omit `limit` → exactly 50) + cursor traversal, gapless, no dup** | ✅ (`test_default_page_size_is_fifty_and_cursor_walks_remainder`) |
| Page-size maximum bounded (`limit>100` → 422; service caps at 100) | ✅ |
| Log-leak (body absent from logs/outbox/audit) | ✅ |
| 10,000-message pagination + `EXPLAIN` index scan | ✅ `Index Scan` on `uq_chat_message_sequence`, no `Seq Scan` |
| OpenAPI 3.1 valid; no Guna/compatibility/AI exposure | ✅ 23 paths |
| Rule-pack + provider/licensing fail-closed guards | ✅ unchanged |
| Generated OpenAPI artifact in sync | ✅ |

New chat test files: `tests/unit/test_chat_cursor.py`,
`tests/integration/test_chat_flows.py`, `…/test_chat_concurrency.py`,
`…/test_chat_migrations.py`, `…/test_chat_pagination_perf.py`,
`…/test_chat_contract.py`, `tests/security/test_chat_authz.py`,
`…/test_chat_no_logging.py`, `…/test_chat_rls.py`.

Two focused tests were added during the merge-readiness pass to close audit gaps:
a behavioural **default page-size (50)** test through the public API boundary
(`test_chat_flows.py`) and a real-PostgreSQL **outbox UPDATE/DELETE-denial** test
under the non-owner runtime role (`test_chat_rls.py`). Suite: 272 → **274**;
PostgreSQL-marked: 38 → **39**.

### 10k query plan (evidence)

```
Limit → Index Scan (Forward) using uq_chat_message_sequence on chat_messages
  Index Cond: (conversation_id = $1 AND server_sequence > 5000)
```
No sequential scan, no sort node. Latency is intentionally not asserted (shared runner).

## 3. Existing mobile integration

No mobile code was changed. The backend change is **additive and backward
compatible** — existing Phase 1 routes are unchanged (confirmed: all 201 baseline
backend tests still pass, and `test_chat_contract.py` asserts Phase 1 routes
remain). The mobile CI's contract-drift guard is a **subset** check (required
routes present, no banned routes) and stays green; the mobile live-integration
suite runs in CI against a real FastAPI + PostgreSQL backend (see §4b).

## 4. Verdict

**`DILCHAT_SECURE_CHAT_BACKEND_CORE_MERGE_READY`**

All merge-ready criteria are met and independently verified on the PR's final head
via live GitHub CI (§4b): models/migrations complete with one Alembic head; all API
behaviour, idempotency, and the send/unpair race pass; RLS passes under the real
non-owner runtime role; cross-couple isolation, the outbox UPDATE/DELETE-denial,
and transactional-outbox consistency pass; the default page-size behaviour and
page-size maximum are directly asserted; full backend regression, existing mobile
live integration, OpenAPI, and fail-closed guards pass; all required chat-relevant
CI jobs are green on the final head; there are no requested changes or unresolved
review threads; and no excluded scope is present.

This verdict follows an independent backend merge-readiness audit whose three
bounded findings (CI-evidence accuracy, a default page-size assertion, and an
outbox UPDATE-denial assertion) are resolved above and in §4b.

## 4b. CI evidence (live GitHub, final head)

- **PR:** #1347 · **base:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
  (this branch is the repository's authoritative `default_branch`).
- **Final head SHA:** recorded in the PR body; the chat-relevant gates below are
  required to complete `success` on that exact head before merge.

### (A) Chat-relevant gates — these validate the secure-chat backend

| Workflow · job | Validates |
|----------------|-----------|
| dilchat-ci · Static quality (ruff, mypy, import, app) | lint/type/import/app-construction |
| dilchat-ci · **PostgreSQL migrations + full test suite** | real `postgres:16`; full suite unfiltered with `--strict-markers`; anti-skip guards (a `--collect-only` count that fails if the PostgreSQL/RLS tests are not collected, and a `skipped\|xfail` grep that fails the job) prove the chat/RLS tests genuinely execute |
| dilchat-ci · OpenAPI 3.1 + Guna fail-closed guards (incl. **secure-chat contract gate**) | routes present, `client_message_id` required, no message body in the conversation summary, nullable tombstone body, no Guna/AI/compatibility exposure |
| dilchat-mobile-ci · Mobile lint / typecheck / test / guards (incl. **contract-drift**) | mobile toolchain + banned-route/contract-drift guard |
| dilchat-mobile-ci · **Mobile ↔ live FastAPI + PostgreSQL integration** | real `postgres:16` + live FastAPI; fails loud if the backend is not ready |
| terminology-ci · terminology | terminology validation over the changed docs (repo-level, applies here) |

### (B) Repository-level checks that do NOT support the secure-chat verdict

Earlier revisions of this report credited two green repository-level checks
(`API stability registry` and `Safety case + SBOM + traceability`) that
actually exercised the unrelated `symbolu_robotics/bcvf_autonomous` module via
the `bcvf-autonomous-ci.yml` workflow. Those checks said nothing about the chat
backend and were **explicitly not** counted as secure-chat evidence. The
`bcvf-autonomous-ci.yml` workflow has since been removed, so these jobs no
longer run at all.

> **CI-trigger constraint (repository).** `dilchat-ci` and `dilchat-mobile-ci` are
> bound to the current authoritative default branch
> (`pull_request` → `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`;
> `push` → `claude/setup-symbolu-monorepo-**`). Because this PR targets that
> default branch, all chat-relevant gates run. This is intentional and correct
> today; if the default branch is ever **renamed**, these workflow triggers must be
> updated to match or DilChat CI will not run. No CI trigger change is made here
> (kept bounded to avoid duplicate workflow execution / behaviour change).

## 5. Confirmations

- PR #1343 was **not** modified and was **not** used as a base.
- No mobile chat UI; no WebSocket/SSE production transport; no push notifications;
  no attachments; no Friends Finder; no AI Assist; no conversation inference; no
  Guna or Moon runtime; no compatibility score; no production deployment.

## 6. Known limitations / open questions

- OQ-CHAT-1: retained read/export access for ended couples — current policy: none.
- OQ-CHAT-2: standalone account-deletion endpoint semantics — deferred to Phase 3B.
- Real-time delivery (outbox relay/transport) is deferred to Phase 3C.
- Per-message audit is intentionally omitted (the transactional outbox is the event
  record); conversation lifecycle and message deletion are audited.
