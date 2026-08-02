# Code Governance — Next Phases (out of scope for MVP 1F)

MVP 1F runs, annotates, analyzes, and closes out a **bounded shadow-pilot
validation** and produces an evidence-based **enforcement-readiness verdict**. It
is an operational validation phase: it measures the existing shadow product and
decides whether enforcement *design* is justified. It does not enforce anything.
Execution remains `DISABLED`.

> **Authoritative stage gates.** The binding, gate-by-gate standard for whether
> Code Governance may proceed from the current shadow-pilot state into the internal
> live pilot, the external enterprise pilot, Phase 2A (enforcement foundation),
> Phase 2B (controlled merge execution), and production rollout lives in
> [`CODE_GOVERNANCE_PHASE_READINESS_REQUIREMENTS.md`](CODE_GOVERNANCE_PHASE_READINESS_REQUIREMENTS.md)
> (machine-readable: [`../artifacts/code_governance_phase_readiness_requirements.json`](../artifacts/code_governance_phase_readiness_requirements.json)).
> This "Next Phases" note is the informal roadmap; the readiness-requirements
> document is the standard that decides progression. Phase 2A and Phase 2B are
> **not** currently approved — the only next authorized activity is provisioning a
> bounded internal live pilot.

The default evidence status is `IMPLEMENTED_AND_OFFLINE_VERIFIED` and the default
readiness verdict is `INSUFFICIENT_LIVE_EVIDENCE` (no live pilot was run) — so the
following remain out of scope and must not be started here:

| Item | Owner / phase |
|---|---|
| Atomic one-time execution **reservation** / `reserve_once` | execution / idempotency ledger |
| Authoritative authorization-consumption ledger | later |
| GitHub execution provider + write permissions + merge credential | provider (later) |
| Merge / deployment enforcement | later |
| Automatic policy change from reviewer feedback | later (human-driven, separately authorized) |
| Broad analytics platform / external production database | later |
| GitHub checks/status writes | later (only under an explicit enforcement mandate) |
| Live enterprise-system clients (beyond read-only GitHub) | product/integration (read-only) |
| Production-enforcement-readiness certification | later |

## What a future enforcement-design phase would require first

Enforcement design should begin only when a real bounded pilot yields
`READY_FOR_ENFORCEMENT_DESIGN`: zero credential leaks, zero write-boundary
violations, zero unexplained integrity failures, complete audit reconstruction,
adequate reviewer-feedback coverage, no unresolved serious possible false CLEAR,
acceptable source reliability, credible incremental value beyond GitHub/CI, bounded
understood disagreements, and explicit limitations. Even then, that verdict
authorizes *design work* — never execution.

## Invariants every later phase must preserve

- `execution_status()` stays `DISABLED` until an explicit, separately-authorized
  execution phase; no verdict, metric, or pilot result enables execution.
- Adapters supply conditions only; the operator coordinates; the study measures.
  None issues a binding decision, approves, merges, or executes.
- Evidence classes are never conflated; supplied snapshots and synthetic scenarios
  are never presented as live enterprise evidence.
- Reviewer agreement is not absolute ground truth; small-sample findings are not
  overstated; no precision/recall/accuracy without a defensible protocol.
- Calibration recommendations never change policy automatically; replay never
  overwrites originals and makes no external call.
- No new `ProviderKind`; no neutral-contract change; the canonical Action Clearance
  package, ActionGate, TAP, Decision Authority, GPF, StoryGraph, and robotics ACP
  stay unmodified. No external production database. Credentials are never persisted.
- The bare acronym "ACP" never appears in new technical surfaces.
