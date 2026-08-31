# Commercial Positioning

*Phase 18. Product-category framing for the architecture. Claims are separated strictly by
evidence tier — validated vs replay-supported vs mock-integration vs unvalidated vs
hypothesis. No claim is elevated above its evidence.*

## Category

**Enterprise AI Execution Control Plane** — the layer between an enterprise application and
one-or-many AI providers that decides *what can execute*, *what should execute*, *what may be
asserted*, *what may be acted upon*, and records *what actually happened*, under versioned
enterprise policy with an append-only audit trail.

Core capabilities (as designed): execution eligibility · policy-aware model selection ·
assertion governance · action governance · provider abstraction · telemetry and evidence ·
replay and audit.

## Differentiation

| Adjacent category | What it does | What the control plane adds |
|---|---|---|
| Model routers | pick a model by cost/latency/quality | eligibility *before* selection (can-execute vs should-execute), fail-closed governance |
| API gateways | auth, rate-limit, proxy | semantic governance of assertion + action, not just transport |
| Retry libraries | retry on failure | fallback that **re-enters eligibility+policy** (invariant 19), not blind retry |
| LLM observability | record what happened | *decide* what may happen, with an append-only hash-chained decision record |
| Guardrails | filter content/assertions | separates assertion governance from **action** governance (invariants 5, 17) |
| Agent frameworks | orchestrate tool-use loops | a governance/authority layer an agent runs *under*, not another agent runtime |
| Workflow orchestrators | sequence tasks | coordinates decisions without absorbing decision authority; carries versioned contracts |
| Model catalogs | list models + metadata | turns catalog metadata into *eligibility evidence* with TTL and provenance |

The distinguishing spine: **eligibility precedes selection**, **assertion is separate from
action**, **downstream cannot bypass upstream**, and **every terminal outcome is causally
traceable** — none of which the adjacent categories provide together.

## Claims by evidence tier

**Validated capability** (real code, tested, independently):
- ExecutionGate eligibility semantics and ModelPolicy selection over eligible-only candidates
  (execution_gate package, 21 tests, frozen replay_v1 aggregate `8b05b2da798a6222`).

**Replay-supported capability** (deterministic, reproducible here):
- Deterministic replay under pinned historical versions (replay success 1.0 on the suite).
- Append-only hash-chained audit with tamper detection.

**Mock-integration evidence** (this track, MOCK mode, 32 scenarios):
- The integrated decision order is coherent, auditable, and falsifiable.
- Invariant enforcement eliminates upstream-exclusion bypass and corrects fallback at ~0.8%
  component-call overhead on the suite.
- Safe fail-closed degradation when a governance component is unavailable.

**Unvalidated live capability** (designed, NOT demonstrated):
- Real provider execution, real action execution, ENFORCEMENT mode — all disabled here.
- Production latency, throughput, reliability, multi-tenant concurrency.
- Real TAP and real ActionGate behavior (mocked in this track).

**Future product hypothesis** (not evidence):
- That integration produces commercial value in a given enterprise — explicitly *not* claimed;
  the evaluation shows value is conditional on environment instability and is *absent* in the
  stable single-provider case.

## Honest positioning statement

The architecture is **logically coherent, implementable, auditable, and falsifiable**, with
real validated eligibility/selection cores and a deterministic, tamper-evident integration
layer. It is **not** proven in production, and its value is **conditional**: it pays off where
there are multiple providers, real exclusions, governed actions, and audit requirements — and
adds only overhead where there are not. Any go-to-market must lead with the validated and
replay-supported tiers and label the live tier as unproven.
