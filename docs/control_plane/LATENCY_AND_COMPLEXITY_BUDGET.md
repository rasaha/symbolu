# Latency and Complexity Budget

*Phase 12. **Architectural targets, not measured production facts.** The numbers below are
design budgets for reasoning about the critical path; the only measured quantities in this
repository are the deterministic complexity proxies from the mock evaluation (component-call
and audit-record counts). Semantics come before optimization (Phase 12 rule).*

## Critical path vs off-path

The synchronous critical path is: normalize → ExecutionGate → ModelPolicy → provider →
TAP → ActionGate → (action). Everything else is off the critical path.

| Stage | On critical path? | Budget class | Target (architectural) | Notes |
|---|---|---|---|---|
| Request normalization | yes | cacheable | ~1–3 ms | pure transform of the envelope |
| PolicyContext resolution | yes | cached | ~1 ms | resolved once, pinned per trace |
| ExecutionGate (eligibility) | yes | cacheable + live-probe | ~2–10 ms cached / probe-bound live | evidence with TTL; stale → re-probe |
| Registry lookup | yes | cached | ~1–5 ms | in-memory record read |
| ModelPolicy (selection) | yes | pure compute | ~1 ms | utility ranking over eligible set |
| Provider execution | yes | **live** | provider-bound (100s ms–s) | dominates the path; not control-plane overhead |
| TAP (assertion governance) | yes | compute + optional evidence | ~2–20 ms | may fetch evidence by reference |
| ActionGate | yes (action requests) | compute | ~1–5 ms | authority-envelope check |
| Telemetry write | **no** (async) | batched | off-path | prospective; never blocks the trace |
| Audit serialization | partial | append + hash | ~0.1–1 ms / record | on-path for the terminal record; mirror async |

**Control-plane overhead** (everything except provider execution and the action itself) is
budgeted at a low tens-of-milliseconds order per request when eligibility evidence is warm.
Provider execution dominates end-to-end latency and is not attributable to the control plane.

## What the evaluation actually measured

The mock evaluation (`MOCK_EVALUATION_REPORT.md`) is deterministic and does **not** measure
wall-clock time. It measures *complexity proxies*:

- Component calls: 129 (glue/orch) vs 130 (unified) across 32 scenarios.
- Audit records: 160 vs 161.

So the enforcement layer's *structural* overhead on this suite is one extra component call
(the fallback re-selection). Real latency must be measured under load before any production
claim; these budgets are targets to test against, not results.

## Overhead-reduction opportunities (design, not yet implemented)

- **Parallel checks.** ExecutionGate conditions are independent and can be evaluated
  concurrently; multiple candidates can be evaluated in parallel.
- **Short-circuit evaluation.** A CRITICAL_GOV failure (residency, network policy) can
  terminate a candidate's evaluation before operational checks run.
- **Cached policy resolution.** PolicyContext is resolved once and pinned; repeated requests
  under the same policy/registry versions reuse it.
- **Batched telemetry.** Observations are off-path and batched to the registry updater.
- **Event-driven invalidation.** Evidence TTL + provider-status events invalidate cached
  eligibility instead of re-probing on every request.

## Complexity risks (carried to falsification)

- The orchestrator must stay a **coordinator**, not absorb decision logic, or it becomes a
  new monolith (Phase 16). The reference orchestrator holds no decision authority by design.
- Reason-code namespacing and audit chaining add fixed per-decision cost; on a hot path with
  trivial routing this can exceed the benefit (the single-provider case in the evaluation).
- Human approval, where required, dominates every software budget — it is the real latency
  floor for approval-gated actions and no amount of control-plane optimization changes it.
