# DilChat incident runbook (internal pilot, round PR-C)

For the named operator on call during the internal pilot. Ordered by what the
symptom threatens, not by component.

**Two standing rules.**

1. **Messaging correctness never depends on push or the relay.** If the relay is
   down, chat is still correct: clients poll REST and the outbox holds the work
   (DEC-058, DEC-3C-4, I5). Never "fix" a push problem by touching message state.
2. **Never widen access to diagnose.** Do not connect as the owner role to read
   user data, do not disable RLS, and do not log message bodies, tokens, report
   evidence, or a DSN. If a diagnosis seems to require one of those, stop and
   escalate to the owner instead.

## Triage

| Symptom | First check | Section |
|---|---|---|
| API returns 5xx / will not start | `scripts_preflight` | A |
| API up but `/v1/readiness` is 503 | readiness `checks` body | B |
| Messages send but partners see them late | relay heartbeat | C |
| No push notifications | transport config, then relay | C |
| Suspected data exposure | stop, escalate | E |
| Database lost or corrupted | latest validated backup | D |

## A. Process will not start / 5xx at startup

A production-like process refuses to start on a bad configuration by design
(round PR-A guards): debug on, the local-dev database default, a non-asyncpg
engine, a cleartext push URL, a missing signing key, an unapproved provider, or
retention shorter than the reporting window.

1. Run `python -m ugence_dilchat.scripts_preflight --expect-role <role>` in the
   failing process's environment. It reports which of configuration, database,
   role, or schema failed, without echoing secrets.
2. `configuration: INVALID …` → fix the environment; never relabel the
   environment to dodge a guard.
3. `database: UNREACHABLE` → network/credentials/cluster; check the database
   service first.
4. `db_role: MISMATCH` → **stop**. A process is running on the wrong
   credentials; this is a privilege-separation failure, not a config nit. Fix
   the DSN before starting.
5. `schema: MISMATCH` or `NOT_MIGRATED` → run migrations as the owner role
   (`alembic upgrade head`), then restart. Never let an application process
   migrate.

## B. Readiness 503

`/v1/readiness` returns the failing check. `database: unavailable` → section A/D.
`astrology_provider: invalid_for_production` means a production-like environment
has no approved real provider: this is deliberate — it never serves real
astrology from the synthetic stub. Configure an approved provider with its
recorded licensing decision; do not downgrade the environment label.

## C. Delivery is slow, or push is missing

Messaging is **not** broken here — confirm that first: a client that polls still
sees messages. Then:

1. `python -m ugence_dilchat.scripts_relay_health` — `RELAY_HEARTBEAT_STALE` or
   `MISSING` means the relay is stuck or dead: check its logs, restart it.
   `NOT_CONFIGURED` means no heartbeat path is set, so liveness cannot be
   judged — set one.
2. Check the outbox for rows with a high `attempt_count` and a
   `last_error_code`. Codes are machine-style by construction (`EXPO_*`,
   `TRANSPORT_UNAVAILABLE`, `UNKNOWN_EVENT_TYPE`). `UNKNOWN_EVENT_TYPE` means a
   producer emitted an event this relay build does not know: it fails closed and
   parks rather than dropping. Deploy a relay that handles it; the parked rows
   drain on their own.
3. Provider outage → the relay backs off exponentially and retries. Nothing to
   do; delivery is at-least-once from durably committed rows.
4. Never mark rows published by hand to "clear" a backlog: `published_at` means
   handed to the transport, and forging it silently drops user notifications.

## D. Database loss or corruption

1. Stop web and relay (in that order) so nothing writes during recovery.
2. Restore the latest **validated** dump into a fresh database — see the
   operations runbook §4, including its role cautions.
3. Point `DILCHAT_DATABASE_URL` at the restored database and run preflight for
   each process before starting it.
4. Start web, then relay. Outbox work in the restored state re-drains; push
   notifications lost during the outage are acceptable (push is advisory).
5. Record what window of data was lost. If any of it included safety reports,
   escalate to the owner: report preservation is a commitment to users.

## E. Suspected data exposure

Escalate to the owner immediately; do not investigate by widening access.

Preserve evidence: capture the deployment's configuration posture (preflight
output — it carries no secrets), process logs, and the time window. Do not
delete or purge anything: destructive purging is off, and a hold exists for
exactly this case — set `hold_reason` on affected retention rows so nothing can
become purge-eligible while the matter is open.

## F. What to escalate rather than fix

- Anything requiring owner-role access to user data.
- A safety report that needs a **decision**. A provisioned reviewer may read
  reports and evidence (operations runbook §6), but nothing adjudicates or
  enforces: any outcome is the owner's call, not the operator's.
- Any request to enable `retention_purge_enabled`, which is gated on decisions
  that are not the operator's to make.
- Any request to disable a startup guard, RLS, or the content-freedom posture.
