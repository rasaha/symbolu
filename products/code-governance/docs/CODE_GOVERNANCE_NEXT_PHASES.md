# Code Governance — Next Phases (out of scope for MVP 1D)

MVP 1D adds read-only enterprise signal adapters, a bounded shadow-pilot runner,
and measurable human-intervention quality on top of the 1A/1B/1C shadow workflow +
durable audit store. It is an integration + pilot-readiness phase: it changes what
signals the shadow path can read and how pilot quality is measured, not what the
product is allowed to do. Execution remains `DISABLED`.

The following are **not** implemented and must not be started under this phase:

| Item | Owner / phase |
|---|---|
| Atomic one-time execution **reservation** / `reserve_once` | execution / idempotency ledger |
| Authoritative execution-consumption ledger | later |
| GitHub execution provider (`EXTERNAL_EXECUTION`) + merge credential + write permissions | provider (later) |
| Enforced merge (direct + squash), merge queue, rebase, deployment enforcement | later |
| Live non-GitHub enterprise clients (Okta/Entra/ServiceNow/Jira/PagerDuty/Datadog/K8s/cloud) | product/integration (read-only) |
| Autonomous policy-learning / feedback-driven policy change | later (human-driven, separately authorized) |
| Signed-producer (trust level 3) adapter attestation | later |
| External database (PostgreSQL/MySQL/Redis/Kafka/cloud) | later |
| Production-enforcement-readiness certification | later |

## What a future enforcement phase would build on this foundation

1D provides the read-only signal front-end, the provenance-bound registry, and the
measured pilot substrate an enforcement phase needs. An enforcement phase would
add — **separately, and without weakening any 1D boundary** — a reservation
primitive, an authoritative consumption ledger, a real GitHub execution provider
behind explicit write credentials, and live read-only source clients, each behind
its own authority and credential boundary. Reviewer feedback and pilot metrics
inform, but never automatically drive, such a change.

## Invariants every later phase must preserve

- `execution_status()` stays `DISABLED` until an explicit, separately-authorized
  execution phase; adapters and the pilot never gain a write path.
- Adapters supply conditions only; they never create authority, approve, authorize,
  merge, or execute. Source failures fail closed and never become positive signals.
- ActionGate authorization is required before Action Clearance; `CLEAR` is not
  execution; the DecisionRecord remains the binding decision.
- No new `ProviderKind`; no neutral-contract change; the canonical Action Clearance
  package, ActionGate, TAP, Decision Authority, GPF, StoryGraph, and robotics ACP
  stay unmodified.
- Credentials never enter the durable store; only governance-relevant data is
  collected; no unrelated employee/company data.
- Reviewer feedback never automatically changes policy; a successful pilot never
  enables enforcement automatically.
- The bare acronym "ACP" never appears in new technical surfaces.
