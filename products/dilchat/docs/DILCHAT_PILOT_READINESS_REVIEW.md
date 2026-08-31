# DilChat internal-pilot readiness review (round PR-E)

**Verdict: the engineering track is complete; the pilot is NOT ready to start.**
Of the 27 checklist items, **10 are fully verified here** and **17 carry an
unresolved dependency** — a deployed environment or an owner/operator decision
no code can make. Every item the repository alone can decide is verified; until
the rest are signed off, "ready" is unclaimable. This review does **not** authorize a public
launch: that remains a separate owner decision (DEC-PR-2).

Reviewed at merged tip `d348977ba` against
[`DILCHAT_PILOT_CHECKLIST.md`](DILCHAT_PILOT_CHECKLIST.md). Evidence labels:
`[V]` verified here, `[I]` inferred, `[R]` requires ratification/sign-off,
`[G]` gap.

## What was actually run

A throwaway PostgreSQL 16 database migrated to head, the real ASGI app under
uvicorn, and the committed operator tooling — not a reading of the code:

| Exercise | Result |
|---|---|
| Migration cycle (upgrade / single head / downgrade / re-upgrade) | OK; head `b8c9d0e1f2a3` |
| Preflight | `PASS`; schema `OK at=b8c9d0e1f2a3` |
| `GET /v1/health` · `GET /v1/readiness` | 200 · 200 |
| Production-like + `fake` provider | refused at construction |
| Relay health probe, unconfigured → configured | exit 2 `NOT_CONFIGURED` → exit 0 `OK age_seconds=0` |
| End-to-end journey (register → profile → invite → accept → conversation → send → partner reads) | 201/201/200/200/201/200; partner saw the body |
| Outbox drain | 4 rows pending → relay published 4 → 0 unpublished |
| Retention dry run | `"deleted": 0`, `"mode": "REPORT_ONLY"`, `purge_enabled false` |
| Backup + restore, with real chat data present | alembic stamp, table set and row counts match; 2 messages restored |
| Reviewer provisioning + audited listing | 43-char one-time key; stored `$argon2id$…`; listing succeeded |
| Full backend suite | **401 passed** |

## 1. Before the first deploy

| # | Item | Label | Evidence |
|---|---|---|---|
| 1.1 | Cluster provisioned; owner can create roles | `[R]` | Environment-specific. The migrations do create all six `dilchat_*` roles when run as an owner — observed in this review — but no pilot cluster exists to certify. |
| 1.2 | Migrations applied as the owner role | `[V]` | `alembic upgrade head` → `b8c9d0e1f2a3 (head)`; exactly one head; full cycle reverses cleanly. |
| 1.3 | `dilchat_app`/`dilchat_worker` granted LOGIN + passwords | `[V]` for the default, `[R]` for the pilot | All six roles are `canlogin=false` as created (`dilchat_secfn_owner` alone has `bypassrls=true`). Granting LOGIN is a deployment act no repository state can attest. |
| 1.4 | Three separate DSNs; web not given the worker DSN | `[V]` mechanism, `[R]` deployment | `scripts_preflight --expect-role` detects a mismatch (proven in round PR-C); the compose definition wires owner/app/worker DSNs to migrate/web/relay separately. Whether the real deployment does so is unverifiable here. |
| 1.5 | ES256 key from a secret store, not the image | `[V]` negative, `[R]` positive | The image ships no key and production-like startup fails without one. That the pilot supplies it from a secret store is an operator fact. |
| 1.6 | Approved provider + recorded licensing decision | `[V]` enforcement, `[R]` decision | `Settings` refuses `fake` in production-like environments (observed) and refuses Swiss without `swiss_production_licensed`. The licensing decision itself is the owner's. |
| 1.7 | `DEBUG=false`, explicit asyncpg DSN | `[V]` | Enforced at construction; pinned by `tests/unit/test_production_guards.py`. |
| 1.8 | `RETENTION_PURGE_ENABLED=false` | `[V]` | Committed default `False`; preflight reports it; no destructive code path exists (source guard). |
| 1.9 | Backup configured **and a restore rehearsed** | `[V]` capability, `[G]` for the pilot | The script restored a database containing real chat rows with full parity. No pilot backup job exists to point at. |
| 1.10 | Migration cycle validated on a disposable copy | `[V]` | Ran clean; the guard also correctly refused a non-disposable database name during this review. |

## 2. Participants and data

Every item here is an owner decision about people, not a property of the code.

| # | Item | Label | Note |
|---|---|---|---|
| 2.1 | Participants authorized and know it is a pilot | `[R]` | No participants exist yet. |
| 2.2 | Distribution non-public | `[R]` | No build has been distributed. |
| 2.3 | Participants told reports are read but not adjudicated | `[R]` | The statement is now true of the system (round PR-D); communicating it is the owner's. |
| 2.3a | A reviewer principal provisioned and a named person accountable | `[V]` mechanism, `[R]` person | Provisioning, one-time key, Argon2-at-rest and an audited listing all exercised here. Who that person is cannot be decided by code. |
| 2.4 | Push disclosed as content-free notices | `[V]` claim, `[R]` disclosure | The transport port carries tokens only, and the notification body is the fixed generic string; the disclosure itself is the owner's. |
| 2.5 | A named operator owns incident response | `[R]` | The runbook exists; the name does not. |

## 3. Deploy

| # | Item | Label | Evidence |
|---|---|---|---|
| 3.1 | Preflight passes per process with its expected role | `[V]` capability, `[R]` deployment | Preflight `PASS` observed; per-process role assertion proven in PR-C. Needs the real deployment to be conclusive. |
| 3.2 | Liveness and readiness respond | `[V]` | 200 and 200 against the running app. |
| 3.3 | Readiness refuses production-like + fake provider | `[V]` (stronger than written) | Startup itself is refused before readiness is ever served. |
| 3.4 | Relay running with a heartbeat configured | `[V]` capability, `[R]` deployment | Probe fails closed unconfigured (exit 2) and reports `OK age_seconds=0` when fed a live heartbeat. |
| 3.5 | Relay separate, no HTTP surface | `[V]` | YAML parse: only `web` publishes a port; relay's command is `python -m ugence_dilchat.relay`. |
| 3.6 | Push transport deliberate | `[V]` default, `[R]` choice | Defaults to `null` in both the example env and compose; choosing `expo` plus credentials is an owner act. |

## 4. After deploy, before inviting participants

| # | Item | Label | Evidence |
|---|---|---|---|
| 4.1 | One end-to-end journey on the deployed stack | `[V]` on a local stack, `[R]` on the pilot | Full journey succeeded against the real app, partner included. Not the deployed stack, which does not exist. |
| 4.2 | Outbox drains | `[V]` | 4 pending → published 4 → 0 unpublished. |
| 4.3 | Retention dry run clean | `[V]` | `"deleted": 0`, `REPORT_ONLY`. |
| 4.4 | Logs carry no body, token, evidence, or DSN | `[V]` for this run | A sentinel message body appears 0 times in server output; no bearer/password/DSN strings. Reinforced by the redaction processor and the relay error-code clamp. |
| 4.5 | Fresh backup after real data, validated | `[V]` capability, `[G]` for the pilot | Validated against a database holding real messages. |

## Blocking gaps

1. `[G]` **No pilot environment exists.** Fourteen items are deployment- or
   people-dependent. The engineering work is done; the pilot has not begun.
2. `[G]` **No backup job.** The validation script is proven, but nothing runs it
   on a schedule against a real database, and no restore has been rehearsed
   against pilot data.
3. `[R]` **Unmade owner decisions**, each blocking on its own: the Swiss
   licensing decision, the named incident-response operator, the named
   accountable reviewer, participant authorization and disclosures, and the
   push-transport choice.

## Standing limits

- Destructive retention purging stays unimplemented; `retention_purge_enabled`
  remains `false`, gated on legal/privacy review of the period, purge and
  preservation tests, and dry-run evidence (DEC-PR-3).
- Moderation reads; it never adjudicates (DEC-PR-4, DEC-3B-3).
- AI Assist and Guna execution remain parked (DEC-PR-5).
- A successful internal pilot never auto-authorizes a public launch (DEC-PR-2).
