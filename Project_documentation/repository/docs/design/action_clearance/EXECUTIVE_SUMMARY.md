# Action Clearance v0.1 — Executive Summary

**Status:** PROPOSED · design-only. No package created, no source moved, no runtime behavior changed,
no `ProviderKind` added, no frozen contract or freeze artifact modified.

## What this phase is

The Action Clearance product-core audit (PR #1275) concluded **ACP NOT READY — do not package**,
because the capability the audit was asked to package *did not yet exist* as a single, neutral,
authority-resolved, contract-stable product core. This phase does not migrate code; it **defines** that
capability so a future implementation can begin cleanly. It is the resolution phase for the audit's
three MIGRATION_BLOCKERs.

## The capability

Action Clearance is a new neutral, deterministic capability that answers exactly one question:

> Given an existing exact-action authorization and a set of trusted current-state signals, is that
> exact action clear to execute at this evaluation time?

Its single invariant:

> Action Clearance may preserve, narrow, defer, escalate, or block an existing authorization. It may
> never create authority, broaden authorization, replace ActionGate, dispatch execution, or own the
> authoritative consumption ledger.

## Key decisions (resolving the audit)

| Audit finding | Resolution in this design |
|---|---|
| R1 authority ambiguous (robotics V1 *authorizes*) | **Clear-only.** Action Clearance never mints authorization; robotics grant-minting semantics are not reused. |
| R2 no stable contract | One `Clearance*` family: `ClearanceRequest` / `ClearanceResult` / `ClearanceReceipt` / `ClearanceStatus` / `ClearanceReasonCode` / `TrustedSignal`. |
| R3 no single core | Domain-neutral core + profiles; **GitHub exact-merge** is the first profile. |
| R5 freeze breakage | No source move; robotics local freeze and platform freeze untouched. |
| R8/R9 one-time-use | Downstream execution/idempotency ledger; Action Clearance receives prior-consumption as a signal. |
| authority model | Directly-invoked capability; **no new `ProviderKind`**. |

Result states: **`CLEAR` / `HOLD` / `BLOCK` / `ESCALATE`** (four); `STALE`/`EXPIRED`/`INCOMPLETE`/
`CONFLICT`/`UNTRUSTED` are reason codes. `DENY` is not used. Package: `ugence_action_clearance` /
`ugence-action-clearance` / `packages/capabilities/action-clearance`.

## Baseline reproduced (§3 / §36)

| Check | Result |
|---|---|
| `python -m platform_freeze.verify --manifest platform/PLATFORM_FREEZE_V1.json` | **PASS** — substantive digest `d4ad77e16516e0db6bf2faf3275c8ac8351644e7561d33f157bb55b5a174a1a6` |
| `scripts/validate_terminology.py` | **PASS** (8 governed docs) |
| `scripts/check_doc_links.py` | **PASS** (21 links) |
| `platform_freeze.dependencies.dependency_report()` | **passed=True, 0 violations** |
| Governance Contracts / GPF / Decision Authority | **45 / 84 / 79 passed** |
| ActionGate provider | **30 passed** |
| Robotics Autonomous Control Plane (`autonomous_control_plane/tests`) | **112 passed** |
| control_plane / robotics_reliability_bench | **65 / 47 passed** |
| console (clearance consumer) | **4 passed** |
| execution_gate / execution_gate_shadow | **25 / 23 passed** |
| `platform_freeze/tests` | 19 passed, **2 pre-existing failures** |
| `bounded_shadow_pilot` | 44 passed, **1 pre-existing failure** |
| Robotics local freeze (`Project_documentation/control_plane/acp/ACP_V1_FREEZE.md`) | **byte-accurate** — 13/13 module hashes match; combined `8f8660e293308cf94c983a26a2ae69c9` |

Pre-existing failures (`test_classify_change_reports_evidence`, `test_hiring_baseline_discovery`,
`test_ground_truth_two_class_and_deterministic`) are the same as recorded in prior audit baselines and
are **not** Action-Clearance attributable.

## Validation (§36, after writing the design)

Re-run confirmed: terminology PASS, doc-links PASS, dependency-direction passed=True, platform-freeze
PASS (digest unchanged `d4ad77e1…a174a1a6`), robotics local freeze unchanged
(`8f8660e293308cf94c983a26a2ae69c9`), all six JSON artifacts parse, baseline tests unchanged. No runtime
file changed; no package created; no neutral contract changed; no `ProviderKind` added; no compatibility
shim added; no robotics import changed. The diff contains only `ACTION_CLEARANCE_V0_1_DESIGN_SPEC.md`,
`docs/design/action_clearance/**`, and one cross-reference line in
`UGENCE_CODE_GOVERNANCE_DESIGN_SPEC.md`.

## Verdict

> ## ACTION CLEARANCE V0.1 DESIGN READY WITH PREREQUISITES — resolve the named signal, persistence, state, or replay decisions first

The authority and trust semantics **are** resolved (clear-only; monotonicity; neutral contract family;
directly-invoked capability; no new `ProviderKind`), so the design is not "NOT READY". Canonical
implementation should not begin *unconditionally*, because four implementation-prerequisites remain
open decisions owned by the platform, not this spec:

1. **Signal provenance/trust mechanism** — how `integrity_digest` + `provenance_ref` are verified per
   source (P1, [`THREAT_MODEL.md`](THREAT_MODEL.md), [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md) Q3).
2. **ClearanceReceipt persistence owner** — the shared durable audit service is a roadmap item; the
   receipt owner must be confirmed (P1, [`PERSISTENCE_BOUNDARY.md`](PERSISTENCE_BOUNDARY.md)).
3. **Durable receipt state + supersession** ownership across evaluator/workflow (P1,
   [`STATE_MACHINE.md`](STATE_MACHINE.md)).
4. **One-time-use / replay ledger** — confirm the execution-ledger owner and the atomic reservation
   contract (P0-scoped-to-execution, [`ONE_TIME_USE_AND_REPLAY.md`](ONE_TIME_USE_AND_REPLAY.md)).

With those four decisions made, Phases A–C of [`IMPLEMENTATION_SEQUENCE.md`](IMPLEMENTATION_SEQUENCE.md)
(skeleton, neutral contracts + deterministic evaluator, in-memory reference adapters) can begin
immediately — they depend on none of the four.
