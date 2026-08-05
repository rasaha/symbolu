# PR #1347 — Independent Merge-Readiness Audit (DilChat Phase 3A secure chat backend core)

**Auditor:** independent review session (not the implementation session that authored PR #1347).
**PR:** `rasaha/symbolu#1347` — *DilChat Phase 3A: secure shared chat backend core*
**Audited head:** `3f45385e94dd3c3e6c0f90d4addf4fd71aaa11dc`
**Base branch:** `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
**Audit verdict:** `DILCHAT_SECURE_CHAT_BACKEND_CORE_DRAFT_READY` — the technical core is sound and honestly
CI-gated, but the audit **withholds** `DILCHAT_SECURE_CHAT_BACKEND_CORE_MERGE_READY` and **does not merge**
(reasons in §5). This is not a code-quality blocker; it is a process + evidence-accuracy hold.

---

## 1. Live-state verification (untrusted claims re-checked against GitHub)

| Claim | Verified |
|-------|----------|
| Current PR head = `3f45385e…` | ✅ matches GitHub PR head |
| Parent of `3f45385e` = `039304db` (prior CI-verified head) | ✅ `3f45385e^ == 039304db` |
| Delta `039304db…3f45385e` is documentation-only | ✅ single file changed: `products/dilchat/docs/DILCHAT_SECURE_CHAT_BACKEND_IMPLEMENTATION_REPORT.md` (+34/−15) |
| Reported verdict now `…CORE_DRAFT_READY` | ✅ present in that file |
| Merge-base with base branch = `6e4ba3e…` (claimed start SHA) | ✅ |

**CI on the *exact current head* `3f45385e` (not inherited from `039304db`):** all **8 check runs**
`completed` / `success`, started 16:07:47–53 — a fresh run triggered by the docs commit (16:07:35).
No pending, no failures. (`get_status` reports `pending`/`total_count:0` only because there are no
*legacy commit-status* entries; the authoritative GitHub Actions **check runs** are all green.)

## 2. Core implementation review (read directly at the audited head)

- **Send/unpair race — sound.** `create_message` and `revoke_conversation` both take the same
  `chat_conversations` row lock via `SELECT … FOR UPDATE` (`with_for_update()`). `revoke_conversation`
  and `couples.unpair` share **one** request transaction (`get_session` = one commit per request), so
  the lock is held until the unpair commit; a concurrent send blocks, then re-reads `status == REVOKED`
  and is rejected with `CONVERSATION_NOT_ACTIVE`. No message can commit after revocation is effective.
- **Revoke-before-unpair ordering is load-bearing**, not cosmetic: revoke runs while membership is still
  `ACTIVE`, so `app_is_active_member(couple_id)` returns true and RLS permits the conversation `UPDATE`.
- **RLS — fail-closed.** `ENABLE` + `FORCE ROW LEVEL SECURITY` on all four tables. User-table policies key
  on `app_is_active_member(couple_id)`; message/read-state writes are additionally constrained to self
  (`sender_user_id`/`user_id = app_current_user()`). The **outbox is internal-only**: app role holds
  `INSERT` only; `SELECT`/`UPDATE` are restricted to the `worker` actor. API requests set
  `actor_type='user'` (from the verified JWT, via `set_config(..., is_local => true)`), so the outbox is
  invisible across the entire user API surface.
- **Idempotency** on `(conversation, sender, client_message_id)` with a unique-constraint backstop; retry
  returns the original with no new row/outbox event; same key + different live body → 409.
- **Cursor** is opaque, versioned, and conversation-bound; malformed / wrong-version / cross-conversation
  cursors fail closed with `INVALID_CURSOR` (400).
- **Outbox payload allow-list** (`OutboxRepository._ALLOWED_PAYLOAD_KEYS`) is defense-in-depth that makes a
  message body reaching the outbox impossible even by mistake.
- **Migration** `c3d4e5f6a7b8` — verified **single Alembic head** (linear chain
  `dfd7ee81e09c → 9c2b82ab02d2 → a1b2c3d4e5f6 → b2c3d4e5f6a7 → c3d4e5f6a7b8`), portable DDL, active-pair
  backfill (revoked couples get none), least-privilege grants, deterministic downgrade.

## 3. Test-quality findings

- PostgreSQL-marked tests (`test_chat_concurrency`, `test_chat_migrations`, `test_chat_pagination_perf`,
  `test_chat_rls`) **genuinely run in CI** against a real `postgres:16` service; CI hard-guards against a
  silent skip (a `--collect-only` count that must be ≥1, and a `skipped|xfail` grep that fails the job),
  with `--strict-markers` and `set -o pipefail`.
- **RLS tests use the correct non-owner pattern**: assertions run under `SET LOCAL ROLE dilchat_app` /
  `dilchat_worker` / `dilchat_readonly` (created `NOSUPERUSER NOBYPASSRLS`, non-owner) under `FORCE` RLS.
  Not a bypassed-owner false positive. Owner-connected PG tests (concurrency, pagination) honestly
  disclaim RLS and only assert lock/sequence/query-plan invariants.
- **6 of 8** security claims fully VERIFIED; **2 PARTIAL** (see §4). No hollow/misleading tests found.

## 4. Findings (non-blocking; recommended before a final merge)

1. **Misattributed CI evidence in the implementation report (should-fix).** The PR body / report list
   "API stability registry" and "Safety case + SBOM + traceability" among the 8 checks validating this PR.
   These jobs live in `bcvf-autonomous-ci.yml` and exercise the unrelated `symbolu_robotics/bcvf_autonomous`
   module; one uses `-k "safety_case"` which can pass with zero tests matched. They are green but say
   nothing about the chat backend. The chat-specific evidence rests on dilchat-ci jobs 2 (PG migrations +
   full suite), 3 (OpenAPI + secure-chat contract gate), and 5 (mobile ↔ live FastAPI + PG). The report
   should stop crediting the robotics jobs.
2. **CI trigger is base-branch-coupled.** `dilchat-ci` / `dilchat-mobile-ci` only fire when the PR base is
   exactly `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (the current base — so they fired and
   are green). Retargeting the PR to `main` or any other base would run **zero** backend CI. Fix the merge
   base intentionally, or broaden the workflow triggers before retargeting.
3. **Minor test gaps.** Default page size (50) is never directly asserted (only the max, 100). Outbox
   app-role `UPDATE` denial and worker `UPDATE` capability are not directly asserted (only `SELECT`/`INSERT`),
   though the grants guarantee them.

## 5. Merge decision

**Not merged.** The independent audit deliberately stops short of
`DILCHAT_SECURE_CHAT_BACKEND_CORE_MERGE_READY` because:

- The PR is an explicit **draft**; its own self-declared verdict is `…DRAFT_READY`, and it names "an
  independent backend merge-readiness audit" as the *next* step — not a merge trigger.
- No human authorization to merge has been given; merging is an irreversible outward action.
- The report's CI-evidence section overstates coverage (Finding 1) and should be corrected first.

The technical core (schema, RLS, service invariants, race safety, tests, and the chat-relevant CI gates)
is in genuinely good shape and, once the draft is marked ready, the merge base is fixed intentionally, and
Finding 1 is corrected, the core would meet merge-readiness on its substance. That final decision belongs
to a human maintainer.
