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

## 2. Test evidence (local, real PostgreSQL 16 + Python 3.12)

| Gate | Result |
|------|--------|
| ruff | ✅ clean |
| mypy | ✅ no issues (58 source files) |
| Baseline suite (before) | 201 passed, 0 skipped |
| **Full suite (after)** | **272 passed, 0 skipped** (71 new) |
| PostgreSQL-marked tests collected | 38 (no silent skips) |
| Alembic: base→head, one head, downgrade/re-upgrade | ✅ head `c3d4e5f6a7b8` |
| Backfill (active→1 ACTIVE conv; unpaired→0) | ✅ |
| Idempotency (replay, conflict, concurrent duplicates) | ✅ |
| 20 concurrent unique sends → gapless 1..20 | ✅ |
| **Send/unpair race (no commit after revoke)** | ✅ |
| Delete/read-state after revoke denied | ✅ |
| Account-deletion effect blocks send | ✅ |
| Cross-couple isolation (app + RLS layers) | ✅ |
| RLS under non-owner runtime role | ✅ (7 SQL-level tests) |
| Outbox atomicity (rollback removes state+event) | ✅ |
| Outbox not on user API surface (worker-only read) | ✅ |
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

**`DILCHAT_SECURE_CHAT_BACKEND_CORE_DRAFT_READY`**

All draft-ready criteria are met and independently verified on the PR's current
head via live GitHub CI (§4b): models/migrations complete with one Alembic head;
all API behaviour, idempotency, and the send/unpair race pass; RLS passes under the
real non-owner runtime role; cross-couple isolation and transactional-outbox
consistency pass; full backend regression, existing mobile live integration,
OpenAPI, and fail-closed guards pass; CI is green; no scope leakage.

Per the operating rules, the PR remains **draft, open, and unmerged**; the next
action is an independent backend merge-readiness audit. No auto-merge.

## 4b. CI evidence (live GitHub, current head)

- **PR:** #1347 · **base:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
- **CI-verified head SHA:** `039304db3d6b8ad0d070f80a6d88bd89b91dc3fa`
- All 8 current-head check runs completed with conclusion **success**:

| Workflow · job | Result |
|----------------|--------|
| dilchat-ci · Static quality (ruff, mypy, import, app) | ✅ success |
| dilchat-ci · **PostgreSQL migrations + full test suite** | ✅ success (RLS runtime-role denials visible in the PostgreSQL log confirm the chat RLS tests executed; no silent skip) |
| dilchat-ci · OpenAPI 3.1 + Guna fail-closed guards (incl. **secure-chat contract gate**) | ✅ success |
| dilchat-mobile-ci · Mobile lint / typecheck / test / guards (incl. **contract-drift**) | ✅ success (`secret scan: clean`) |
| dilchat-mobile-ci · **Mobile ↔ live FastAPI + PostgreSQL integration** | ✅ success |
| terminology-ci · terminology | ✅ success |
| API stability registry | ✅ success |
| Safety case + SBOM + traceability | ✅ success |

> Note: the doc-only commit that records this verdict changes no application code
> (verdict/report/PR-body metadata only); it does not alter the CI-verified head's
> behaviour. dilchat-ci re-runs on the docs commit (path `products/dilchat/**`) and
> is expected green.

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
