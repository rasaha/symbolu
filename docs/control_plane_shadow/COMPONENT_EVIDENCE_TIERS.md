# Component Evidence Tiers

*Phase 2. Every component boundary is assigned an evidence tier. **This task may reach at most
TIER 5, and reaches only TIER 3 in practice** (real component, synthetic input) — no live
provider calls, no advisory/enforcement use. Mixed-tier evidence is NOT aggregated into a
stronger global claim (see the rule at the bottom).*

## Tier ladder

| Tier | Meaning | Reached here? |
|---|---|---|
| 0 | documentation-only | — |
| 1 | deterministic mock | yes (provider, action-exec fixtures) |
| 2 | artifact replay | yes (provider outcomes, recorded failures) |
| 3 | real component, synthetic input | **yes — the pilot's ceiling** |
| 4 | real component, recorded operational input | no (no de-identified operational corpus available) |
| 5 | live shadow observation | **no** (gated behind Phase 19 GO; not run) |
| 6 | advisory production use | prohibited |
| 7 | enforcement | prohibited |

## Assignment by boundary

| Boundary | Tier | Justification |
|---|---|---|
| ExecutionGate | **3** | real `execution_gate.gate.evaluate` run on synthetic candidates/requests |
| ModelPolicy | **3** | real `model_selection_experiment.policy.route` run on real `policy_v1`/`registry_v1` + synthetic tasks |
| TAP / assertion governance | **3 (with semantic-gap caveat)** | real `tap_e4 GovernanceResolver.resolve` on synthetic-but-schema-valid records; disposition mapping is adapter-authored, so the *assertion-governance* claim is weaker than the raw engine's *authority-resolution* claim |
| ActionGate | **3** | real `action_gate_ref.gate.evaluate` on synthetic envelopes/policies built via the reference test helpers |
| Provider execution | **1–2** | synthetic fixtures (T1) and recorded provider-failure artifacts (T2); **no live call** |
| Action execution | **1** | simulated only; never executes — cannot exceed deterministic-mock |
| Telemetry | **1** | deterministic in-memory observation; prospective registry queue |
| Audit | **3** | real `control_plane` append-only hash-chained log (unit-tested engine, run for real) |

## Per-boundary tier is the ceiling of any claim about that boundary

- The **ExecutionGate** and **ModelPolicy** boundaries carry genuine TIER-3 evidence: the real
  engines, exercised. Claims about their *integrated behavior* are still bounded by the weakest
  boundary on the path (below).
- The **TAP** boundary is TIER 3 for the *engine* but the *assertion-governance interpretation* is a
  semantic approximation — any claim phrased as "assertion governance validated" is **not** licensed;
  the licensed claim is "a real deterministic governance engine was integrated and its dispositions
  mapped, with a documented semantic gap."
- The **provider** and **action-execution** boundaries never exceed replay/mock. Therefore **no
  end-to-end claim may be stronger than "TIER-3 components connected across TIER-1/2 execution
  boundaries"** — i.e. the *integration* is validated, live *execution* is not.

## No-aggregation rule (enforced in reporting)

The end-to-end evaluation report (Phase 17) **separates** results by tier and never emits a single
headline number that blends, e.g., real-engine disposition fidelity (T3) with mock provider outcomes
(T1). A trace that touches a T1 provider boundary is reported as a T1-ceiling trace for any
execution-outcome claim, even though its governance decisions are T3. The global verdict is the
**minimum** tier across the boundaries a claim depends on, never the maximum.
