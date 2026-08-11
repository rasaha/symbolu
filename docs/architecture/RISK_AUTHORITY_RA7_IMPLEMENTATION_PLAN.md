# Risk Authority RA-7 — Implementation Plan (Non-Binding Sequencing)

> **Status:** Planning companion to the ratified `RISK_AUTHORITY_RA7_SPEC.md`
> (verdict `RA7_PRECONDITIONS_RESOLVED_READY_FOR_IMPLEMENTATION`).
> **Type:** DOCUMENTATION ONLY. No code, no package, no PR is created by this
> document. This is a suggested sequencing for a *future* implementation session,
> not an authorization to implement.
> **Baseline:** default `…monorepo…` @ `e6aa6edf` (RA-6 merge).

This plan sequences the RA-7 build so that each phase is independently reviewable,
preserves every security invariant (spec §21), and requires **no** change to the
RA leaf / Agent Runtime / ActionGate / RA-6 for the core observe→signal loop.

## Guiding constraints (from the spec)

- New package only: `packages/integration/risk-authority-runtime-assurance/`.
- Depends on `ugence-risk-authority` (neutral signal types) + RA-6 status-runtime
  intake. **Never** the reverse; **never** RA into `agent-runtime`.
- Observes via the existing neutral `event_sink` (`agent-runtime/config.py:62`).
- Emits only `AuthorityReassessmentSignal` (`RUNTIME_RISK_ESCALATED`) into the
  existing `AuthorityReassessmentSignalPort.submit`.
- Default consequence: targeted `revoke_envelope` (RA-6 decides breadth).
- Reference evaluator is stateless; no second execution ledger.

## Phase 0 — Package skeleton (no behavior)

- Create the sibling package with `pyproject.toml` mirroring
  `risk-authority-status-runtime` posture; dependency on the RA leaf only.
- No observer wired, no telemetry ingress — just the package boundary and the
  neutral contract stubs (types, Protocols) from spec §23.
- **Exit:** package installs; RA leaf and agent-runtime unchanged; import graph
  matches spec §22.

## Phase 1 — Neutral contracts (types only)

- Define `TrajectoryObservation`, `TrajectoryAssessment`, `RuntimeRiskLevel`
  (`NORMAL`/`ESCALATED`/`UNKNOWN`), `TrajectoryPolicyRef` as pure data/Protocols
  (spec §12–§13, §23). No authority fields (no ALLOW, no scope, no signature).
- **Exit:** contracts compile; property tests assert no authority-granting field
  exists on any RA-7 type (I9).

## Phase 2 — Observer over the existing event seam

- Implement `RuntimeAssuranceObserver` that subscribes to the Agent Runtime
  `event_sink` and derives the per-`(tenant_id, workflow_instance_id)` trajectory
  (spec §11). Read-only; dedupe by `event_id`; re-sequence by
  `sequence_number`/`observed_at`.
- **Exit:** observer builds trajectories from a recorded event stream; agent-runtime
  requires no change; observer-down leaves the runtime unaffected (test 22).

## Phase 3 — Trajectory evaluator (reference rules)

- Implement the evaluator producing `TrajectoryAssessment`:
  cumulative-exposure (read portfolio ledger state — D3/§6), near-boundary repeat,
  retry/loop, data-class progression, context expansion (§14),
  trajectory-policy deviation (against the authority-bound `trajectory_policy_id`).
- Stateless reference; bounded in-memory window only (§24).
- **Exit:** deny-heavy test matrix items 1–3, 16–20 pass; `UNKNOWN` on
  missing/stale/unknown-policy inputs (items 7, 13, 14).

## Phase 4 — Telemetry-trust ingress seam

- Implement the authenticated ingress port (D7/§10, Option B): validate the
  minimum bindings; reject wrong-tenant/workflow/envelope, malformed, and
  unauthenticated producers; dedupe replays; order out-of-order.
- **Exit:** matrix items 6–12 pass; cross-tenant injection rejected (I7);
  forged-but-authenticated telemetry can only over-revoke (fail-safe).

## Phase 5 — RA-6 signal handoff

- On a material `ESCALATED` assessment, construct `AuthorityReassessmentSignal`
  (`RUNTIME_RISK_ESCALATED`, `target_type = ENVELOPE`, references + structured
  reason codes) and `submit()` to the RA-6 intake (spec §18). No direct writer
  calls.
- **Exit:** matrix items 3–5, 23–28 pass; signal-sink-down retries without
  widening; idempotent against already-revoked/expired envelopes.

## Phase 6 — Honesty & docs pass

- Verify latency claims (§25): "event-driven," not "zero-window."
- Confirm RA-4.5/RA-5/RA-6 unchanged, ActionGate exact-action, ACP separate, RA-8
  not pulled in (matrix items 29–35).

## Deferred / separate (NOT this milestone)

- **`trajectory_policy_digest`** additive envelope binding (D2) — a small,
  backward-compatible RA-leaf schema add, signed via `signing_payload()`; land as
  its own reviewed change, not inside the observer package.
- **`assurance_required`** additive signed condition (D4) — same posture; only
  then can ActionGate/pre-effect recheck consume the requirement.
- **RA-8** — wiring Decision Authority reconciliation to the runtime effect.
- **ACP** — separate subsystem entirely.

## Definition of done (reference milestone)

Observe→signal loop closed through existing seams; all §21 invariants hold; the
deny-heavy matrix (§27) green; RA leaf still stdlib-only and independently
installable; agent-runtime still imports no RA; no second authority artifact.
