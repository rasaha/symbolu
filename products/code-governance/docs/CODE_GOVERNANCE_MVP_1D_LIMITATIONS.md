# MVP 1D Limitations

> MVP 1D is a bounded **integration + pilot-readiness** phase. It lets Code
> Governance evaluate read-only enterprise signals, explain human intervention,
> measure decision quality, and produce an auditable pilot report — without
> changing code, company systems, or governance policy. This document states the
> boundary explicitly.

## Not production enforcement readiness

A pilot that meets its configured thresholds is **not** proof of perfect safety and
does **not** enable enforcement. Pilot metrics are descriptive; reviewer-derived
error categories are *possible* until ground truth is independently established.

## Explicitly out of scope

- **No execution.** `execution_status()` is `DISABLED` in every mode. No `merge`,
  `execute`, or `dispatch`.
- **No GitHub write path.** No write operation; no approve/merge/close/label/
  comment/modify/deploy of a PR; no GitHub App write permission; no merge credential.
- **No execution provider**, no `ProviderKind`, no `reserve_once`, no authoritative
  execution-consumption ledger.
- **No autonomous policy learning.** Reviewer feedback never changes policy
  automatically; it is audit data.
- **No live non-GitHub clients.** Identity/incident/change-management/health/control
  sources are supplied, validated snapshots in 1D.
- **No credentials in the database.** No access tokens, API keys, private keys, or
  webhook secrets are persisted; credentials never leave the transport boundary.
- **No unrelated employee/company data.** Only governance-relevant identity fields
  are collected; stable subject references, not employee profiles.
- **No external database.** Pilot records reuse the 1C durable store; no
  PostgreSQL/MySQL/Redis/Kafka/cloud DB is added.
- **No autonomous retry of authoritative governance decisions**; no auto-resume of
  external side effects after restart.

## Authority boundary preserved

Adapters supply conditions only. A source stating "checks passed" is not "merge
approved"; "actor active" is not "authorized for this decision"; "no incident" is
not "execution permitted". The DecisionRecord remains the binding governance
decision, ActionGate authorization is still required before clearance, and the
canonical Action Clearance package is unmodified. The only changed product boundary
is `products/code-governance/`.

See `CODE_GOVERNANCE_NEXT_PHASES.md` for what a future enforcement phase would need.
