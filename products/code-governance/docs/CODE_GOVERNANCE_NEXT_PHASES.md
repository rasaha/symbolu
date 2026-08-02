# Code Governance — Next Phases (out of scope for MVP 1E)

MVP 1E makes the 1D read-only pilot **deployable and operable** — a
security-bounded pilot operator with lifecycle controls, credential isolation,
preflight, observability, a reviewer queue, restart recovery, a kill switch, and
closeout — against a narrowly allowlisted GitHub environment. It changes how a
read-only pilot is *operated*, not what the product is allowed to do. Execution
remains `DISABLED`.

The following are **not** implemented and must not be started under this phase:

| Item | Owner / phase |
|---|---|
| Atomic one-time execution **reservation** / `reserve_once` | execution / idempotency ledger |
| Authoritative authorization-consumption ledger | later |
| GitHub execution provider + write permissions + merge credential | provider (later) |
| Merge / deployment enforcement | later |
| Automatic policy learning / feedback-driven policy change | later (human-driven, separately authorized) |
| Live non-GitHub enterprise clients | product/integration (read-only) |
| Broad multi-tenant SaaS control plane / network control API | later (only with an established secure service pattern) |
| Signed-producer adapter attestation (trust level 3) | later |
| External database | later |
| Production-enforcement-readiness certification | later |

## What a future enforcement phase would build on this foundation

1E provides the deployable, observable, credential-isolated, recoverable operator
substrate an enforcement phase would sit behind. An enforcement phase would add —
**separately, and without weakening any 1E boundary** — a reservation primitive,
an authoritative consumption ledger, a real GitHub execution provider behind
explicit write credentials, and merge/deployment enforcement, each behind its own
authority and credential boundary. Reviewer feedback and pilot metrics inform, but
never automatically drive, such a change.

## Invariants every later phase must preserve

- `execution_status()` stays `DISABLED` until an explicit, separately-authorized
  execution phase; the operator never gains a write path or a write permission.
- Adapters supply conditions only; the operator coordinates but owns no authority,
  issues no binding decision, and never approves/merges/executes.
- Startup and resume require explicit operator actions; recovery performs no
  external call automatically and never auto-resumes an ACTIVE pilot.
- Reviewer assignment is not approval; reviewer feedback never changes policy
  automatically; a successful pilot never enables enforcement.
- Credentials are externally supplied and never persisted; only governance-relevant
  data is collected.
- No new `ProviderKind`; no neutral-contract change; the canonical Action Clearance
  package, ActionGate, TAP, Decision Authority, GPF, StoryGraph, and robotics ACP
  stay unmodified.
- No fabricated live-pilot evidence: results are labeled IMPLEMENTED /
  OFFLINE_VERIFIED / LIVE_SMOKE_VERIFIED / PILOT_DATA_COLLECTED / NOT_RUN honestly.
- The bare acronym "ACP" never appears in new technical surfaces.
