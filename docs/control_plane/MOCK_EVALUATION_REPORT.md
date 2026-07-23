# Mock Integration Evaluation Report (v1)

*Phase 15. Deterministic evaluation of the integration architecture across the 32-scenario
suite (`control_plane/scenarios.py`) under three configurations. **MOCK mode, no live calls,
no real actions.** This is an **architectural integration** evaluation — not production
validation and not a commercial claim. Raw results: `control_plane/eval_results/mock_evaluation_v1.json`
(regenerate with `python3 -m control_plane.eval`).*

## Configurations

| Config | Contracts validated | Invariants enforced | Represents |
|---|---|---|---|
| `glue` | no | no | disconnected components with informal glue |
| `orch` | yes | no | orchestrator that routes + validates versions but does not enforce invariants |
| `unified` | yes | yes | the unified control plane (contracts + invariants) |

## Results (32 scenarios)

| Metric | glue | orch | unified |
|---|---|---|---|
| invalid-transition rate (violations allowed to proceed) | **0.0625** | **0.0625** | **0.0** |
| upstream-exclusion bypass (allowed) | 1 | 1 | 0 |
| fallback correctness | 0 / 1 | 0 / 1 | **1 / 1** |
| violations detected | 2 | 2 | 1 |
| violations blocked | 0 | 0 | 1 |
| audit completeness | 1.0 | 1.0 | 1.0 |
| trace completeness | 1.0 | 1.0 | 1.0 |
| reason-code completeness | 1.0 | 1.0 | 1.0 |
| unauthorized execution | 0 | 0 | 0 |
| false blocking | 0 | 0 | 0 |
| deterministic replay success | — | — | **1.0** |
| total component calls (complexity proxy) | 129 | 129 | 130 |
| total audit records (complexity proxy) | 160 | 160 | 161 |

## Findings

1. **Invariant enforcement — not contracts alone — produces the safety difference.**
   `glue` and `orch` are identical on every safety metric. Contract *validation* (version
   compatibility + required fields) catches malformed hand-offs but does **not** by itself
   prevent an upstream-exclusion bypass or fix fallback. Only the `unified` config, which
   enforces the structural invariants, drives the invalid-transition rate to 0 and the
   upstream-exclusion bypass to 0. This is a **negative finding for "formal contracts add
   measurable value on their own"** (Phase 16): on this suite, contracts are necessary
   plumbing but not sufficient for the safety guarantees — the invariant layer is what pays.

2. **Fallback correctness is the concrete bypass case.** In `glue`/`orch`, a provider
   failure with an available alternative is handled by an in-place retry of the *same*
   candidate — recorded as `RUNTIME.UPSTREAM_EXCLUSION_BYPASSED` (violation detected, not
   blocked). `unified` re-enters eligibility + policy (invariant 19) and correctly switches
   to the fallback candidate (`1/1`). Same eventual *outcome* (COMPLETED), but only `unified`
   reaches it without bypassing the eligibility boundary.

3. **The complexity cost of the safety guarantee is negligible here.** `unified` spends 130
   vs 129 component calls and 161 vs 160 audit records — a single extra call across 32
   scenarios (the fallback re-selection). On this suite the control-plane overhead is ~0.8%
   of component calls. (Complexity is a deterministic call/record proxy, **not** wall-clock
   production latency; see `LATENCY_AND_COMPLEXITY_BUDGET.md`.)

4. **Audit, trace, and reason-code completeness are 1.0 in all three configs**, because the
   append-only hash-chained log and namespaced codes are substrate-level — present whether or
   not invariants are enforced. Determinism holds: every `unified` trace replays identically
   under its pinned historical versions (replay success 1.0, invariant 13).

5. **No unauthorized execution and no false blocking in any config.** No real action executes
   in MOCK regardless of config (invariant: modes), and `unified` never blocks a scenario that
   `glue` legitimately completes — the enforcement is precise, not over-broad.

## What this evaluation does NOT show

- It does **not** show commercial value or production readiness (Phase 15/18 constraint).
- It does **not** exercise ENFORCEMENT, real providers, or real actions (disabled here).
- The single-provider scenario (`single_provider_overhead`, flagged `can_lose`) completes
  identically in all three configs — in a stable single-provider environment the control
  plane's machinery is pure overhead with no safety dividend. That case is where a simple
  sequential script is genuinely sufficient (carried into `LIMITATIONS_AND_FALSIFICATION.md`).

## Bottom line

The integrated architecture is **logically coherent, auditable, deterministic, and
falsifiable** on this suite. Its measurable value is concentrated in the **invariant
enforcement** layer (bypass prevention + correct fallback), not in contract validation alone,
and that value is real only when the environment has something to route around — multiple
providers, real exclusions, real actions. Where it does not, the architecture correctly adds
nothing but overhead.
