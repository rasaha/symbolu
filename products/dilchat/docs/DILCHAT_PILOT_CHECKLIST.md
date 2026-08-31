# DilChat internal-pilot deployment checklist (round PR-C)

Release target is a **controlled internal pilot** with authorized participants
and non-public distribution (DEC-PR-2). Working through this list does **not**
authorize a public launch — that is a separate owner decision that re-assesses
privacy/legal gates, moderation operations, retention, provider credentials and
licensing, incident response, and production support.

Every item is either verifiable by a command in this repository or an explicit
owner/operator sign-off. Do not tick an item because it "should" hold.

## 1. Before the first deploy

| # | Item | How it is verified |
|---|---|---|
| 1.1 | Database cluster provisioned; owner role can create roles | operator |
| 1.2 | Migrations applied as the **owner** role | `alembic upgrade head` |
| 1.3 | `dilchat_app` / `dilchat_worker` granted LOGIN + passwords (migrations create them NOLOGIN — they are RLS postures, not accounts) | `ALTER ROLE … WITH LOGIN PASSWORD …` |
| 1.4 | Three separate DSNs exist (owner / app / worker) and the web process is **not** given the worker DSN | `python -m ugence_dilchat.scripts_preflight --expect-role dilchat_app` on web; `--expect-role dilchat_worker` on relay |
| 1.5 | ES256 signing key supplied via the platform secret store, not a file in the image | operator |
| 1.6 | Approved astrology provider configured with the recorded licensing decision | preflight `astrology_provider`; startup fails otherwise |
| 1.7 | `DILCHAT_DEBUG=false`, explicit `postgresql+asyncpg` DSN | enforced at startup (round PR-A guards) |
| 1.8 | `DILCHAT_RETENTION_PURGE_ENABLED=false` | preflight `retention_purge_enabled` |
| 1.9 | Backup job configured, and a restore **actually rehearsed** | `scripts/validate_backup_restore.sh` |
| 1.10 | Migration cycle validated on a disposable copy | `scripts/validate_migration_cycle.sh` |

## 2. Pilot participants and data

| # | Item | Verified by |
|---|---|---|
| 2.1 | Participants are authorized and know this is a pilot | owner |
| 2.2 | Distribution is non-public (internal build channel) | owner |
| 2.3 | Participants informed that reports are recorded and **read by a named internal reviewer**, but that no adjudication or enforcement workflow exists yet (DEC-3B-3) | owner |
| 2.3a | At least one individual reviewer principal provisioned, and a named person accountable for reading reports | `scripts_moderation provision-reviewer`; owner |
| 2.4 | Push, if enabled, is disclosed as content-free delivery notices only | owner |
| 2.5 | A named operator owns the pilot's incident response | owner |

## 3. Deploy

| # | Item | Verified by |
|---|---|---|
| 3.1 | Preflight passes for **each** process with its expected role | `scripts_preflight` (exit 0) |
| 3.2 | Web liveness and readiness respond | `GET /v1/health`, `GET /v1/readiness` (200) |
| 3.3 | Readiness refuses a production-like environment with a fake provider | already enforced; returns 503 |
| 3.4 | Relay running with a heartbeat path configured | `python -m ugence_dilchat.scripts_relay_health` (exit 0) |
| 3.5 | Relay is a **separate** process with no HTTP surface | deployment definition |
| 3.6 | Push transport deliberate: `null` (drains, sends nothing) or `expo` with pilot credentials | preflight `push_transport` |

## 4. After deploy, before inviting participants

| # | Item | Verified by |
|---|---|---|
| 4.1 | One end-to-end journey on the deployed stack: register → profile → invite → accept → consent → chat | operator |
| 4.2 | Outbox drains (no rows stuck unpublished) | relay logs / outbox inspection |
| 4.3 | Retention dry run runs clean | `python -m ugence_dilchat.scripts_retention_report` (`"deleted": 0`) |
| 4.4 | Logs contain no message body, token, evidence, or DSN | spot-check against the telemetry posture |
| 4.5 | A fresh backup taken **after** the first real data exists, and validated | `scripts/validate_backup_restore.sh` |

## 5. Explicitly NOT part of pilot readiness

- Public production launch (separate owner decision).
- Moderation **adjudication**: reviewers can read reports and evidence, but
  nothing resolves, dismisses, or enforces — that is a later ratified product.
- Destructive retention purging (`retention_purge_enabled` stays `false`).
- AI Assist, Guna execution, compatibility scoring (parked, DEC-PR-5).
