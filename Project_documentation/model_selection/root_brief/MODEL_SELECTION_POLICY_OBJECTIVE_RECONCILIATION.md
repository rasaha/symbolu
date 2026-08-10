# Model Selection Policy — Objective Reconciliation

*Bounded empirical workstream. Reconciles the intended commercial objective (least-cost sufficient
model) with the implemented mechanism (soft weighted utility). Adds constrained variants B and C as
**separate selectable policies** without modifying the baseline, evaluates A/B/C on the existing
harness, and reaches an evidence-driven recommendation. No production default changed. All numbers
are synthetic (37-task corpus, deterministic); no live calls. Code: `model_selection_reconciliation/`.*

---

## 1. Current implementation

Selection runs in two stages (`model_selection_experiment/policy.py`, `execution_gate/`):

- **Stage A — hard eligibility filter** (`hard_filter`): approved providers, privacy tier,
  residency/on-prem, required modality/tools/structured output, declared context, hard cost ceiling
  (`max_cost`), hard latency SLA (`max_latency_ms`), reliability floor; unknown/stale critical
  evidence → INDETERMINATE (fail-closed).
- **Stage B — soft weighted-utility scoring** (`score`, `route`): over the eligible set,
  `utility = w_q·Q̂ − w_cost·CostNorm − w_lat·LatencyNorm`, then `argmax`, deterministic tie-break by
  model id.

`Q̂` (`predicted_quality`) is a confidence-weighted fusion of provider-declared, benchmark-measured,
runtime-telemetry, and (arm G) advisory evidence, normalized to [0,1].

**The verified gap:** `acceptable_quality_threshold` is read only by `metrics.py` (to *measure*
outcomes) — `policy.py` never reads it. It is **not an enforced selection constraint**. Proven by
test: `test_baseline_and_A_ignore_acceptable_quality_threshold` (selection is invariant to the
threshold across all 37 tasks).

## 2. Intended commercial formalization

> Choose the lowest-cost eligible model that satisfies a minimum quality requirement, with escalation
> or abstention when no model qualifies.

## 3. Exact mathematical difference

**Implemented (Policy A):**
`m* = argmax_{m ∈ eligible} [ w_q·Q̂(m,x) − w_cost·CostNorm(m,x) − w_lat·LatNorm(m,x) ]`
— quality is a *soft term*; no hard `Q̂ ≥ Q_min`; cost is a *penalty*, not the minimand.

**Intended (constrained):**
`m* = argmin_{m ∈ eligible, Q̂(m,x) ≥ Q_min(x)} ExpectedCost(m)`
— quality is a *hard constraint*; cost is the *minimand*; abstain if the feasible set is empty.

The difference is not cosmetic: A optimizes **expected utility**; the intended policy optimizes
**cost subject to a sufficiency floor**. They select different models and fail in different ways.

## 4. Policy variants (implemented, `model_selection_reconciliation/variants.py`)

- **Policy A** — existing soft-utility baseline. Delegates to `policy.route` **verbatim**; preserved
  exactly (test: `test_policy_A_reproduces_baseline_exactly`).
- **Policy B** — hard floor `Q̂ ≥ Q_min` on **predicted** quality, then **minimum expected cost**
  among sufficient; abstain if none. Deterministic tie-break (cost, latency, id).
- **Policy C** — hard floor, then **lexicographic**: cost ↑, latency ↑, quality-margin (Q̂ − Q_min)
  ↓, model-id ↑. (No `reliability` field exists in the registry, so the tertiary key is the quality
  margin, not an invented attribute.)

Selected via explicit config: `route_variant(variant, ...)`. Hard eligibility is unchanged across
variants (test: `test_hard_eligibility_identical_across_variants`).

## 5. Threshold semantics (resolved from repository evidence)

1. **What is `acceptable_quality_threshold`?** A **minimum normalized task-quality score** on [0,1] —
   a customer acceptance threshold. `metrics.py` compares it against **true** quality to score
   "acceptable-quality success." It is **not** a success *probability* and **not** a raw benchmark
   score; it is the fused normalized quality scale.
2. **Is Q̂ calibrated across models/task-classes?** **Imperfectly, and optimistically biased.**
   Measured mean |Q̂ − true| = **0.035 (mature) → 0.058 (cold)**; optimistic miscalibration
   (Q̂ ≥ Q_min but true < Q_min — the dangerous kind) = **0.041 (mature) → 0.090 (cold)**; pessimistic
   ≈ 0. Calibration degrades as telemetry gets staler.
3. **Scope of the threshold?** **Per-task** (each corpus task carries its own value ≈ 0.60–0.80), i.e.
   request/task-class-specific — `Q_min(x)`, not global.
4. **When Q̂ is unknown/stale/low-confidence?** `fuse_quality` always returns a point estimate
   (falling back to declared/benchmark) with per-source confidences; there is **no** confidence
   interval. A point-estimate floor therefore inherits Q̂'s optimistic bias (see Q6).
5. **Does a hard floor cause excessive abstention?** **Yes at high thresholds** — see Results
   (abstention 0.19 → **0.86** as Q_min goes 0.70 → 0.90).
6. **Should the floor use a lower-confidence bound `LCB(Q̂) ≥ Q_min` instead of `Q̂ ≥ Q_min`?**
   **Conceptually yes** — because Q̂ is optimistically biased, a point floor under-protects (residual
   floor violations persist). But the repository has **no calibrated variance/LCB estimator**, and
   inventing one is out of scope. This is the top open item (see Calibration caveat).

## 6. Experimental protocol

- **Policies:** A, B, C. **Corpus:** 37 tasks (`data/corpus_v1.json`). **Ground truth & scorer:**
  `simulator.py` / `metrics.py`, reused read-only.
- **Evidence regimes:** cold / partial / mature (= stale → fresh telemetry) — the evidence-quality /
  stale-evidence sensitivity axis.
- **Threshold sweep:** `Q_min ∈ {native per-task, 0.60, 0.70, 0.80, 0.90}`.
- **Metrics (both objectives, so neither policy is judged only on the other's home metric):**
  utility-regret (A's objective), floor-violation rate (selected but **true** quality < Q_min),
  false-rejection rate (abstained when a **true**-sufficient model existed), acceptable-quality rate,
  mean selected true cost/latency, cost-efficiency vs the **cheapest true-sufficient** model (B/C's
  objective), tier routing, abstention, and Q̂ calibration.
- **Reproducibility:** full evaluation run twice, byte-identical (verified: `reproducible() == True`).

## 7. Results (mature regime unless noted; full grid in `results/reconciliation_eval_v1.json`)

| Q_min | Policy | utility-regret | floor-violation (true<Q_min) | abstention | acceptable@Q_min | cost-eff vs cheapest-sufficient |
|---|---|---|---|---|---|---|
| native | A | **0.0095** | 0.243 | 0.189 | 0.568 | 1.18 |
| native | B/C | 0.040 | **0.081** | 0.243 | **0.676** | **1.00** |
| 0.70 | A | **0.0095** | 0.297 | 0.189 | 0.514 | 1.52 |
| 0.70 | B/C | 0.018 | **0.081** | 0.297 | **0.622** | **1.12** |
| 0.80 | A | **0.0095** | 0.432 | 0.189 | 0.378 | 1.08 |
| 0.80 | B/C | 0.027 | **0.216** | 0.324 | **0.459** | 1.00 |
| 0.90 | A | **0.0095** | 0.730 | 0.189 | 0.081 | 1.00 |
| 0.90 | B/C | 0.259 | **0.000** | **0.865** | 0.135 | 1.00 |

**Stale-evidence (cold regime):** B/C floor-violation rises to **0.216** (from 0.081 mature) — the
hard floor is materially less effective under stale evidence, because Q̂'s optimistic miscalibration
doubles (0.041 → 0.090).

**B ≡ C** on all 15 grid cells (test-confirmed): lexicographic tie-breaking adds nothing over
min-cost on this corpus.

**Reading it honestly:**
- **The hard floor delivers on its own objective.** At native/moderate thresholds it cuts sufficiency
  failures **~3×** (floor-violation 0.24 → 0.08), raises acceptable-quality rate (0.57 → 0.68), and
  hits the cheapest-sufficient cost target (cost-efficiency 1.00 vs A's 1.18–1.52).
- **But A dominates its own objective** (utility-regret 0.0095 vs 0.018–0.26) — by construction.
- **The floor does not eliminate failures**, because Q̂ is optimistically biased: 8% of picks are
  truly insufficient even with the floor (21% under stale evidence).
- **High thresholds are operationally unstable:** at Q_min = 0.90 the floor forces **86% abstention**
  — the floor is unreachable for most tasks on this corpus.

## 8. Falsification assessment

Each preregistered rejection target, judged against the data:

| Falsification target | Verdict |
|---|---|
| Constrained policy materially increases abstention without meaningful quality gain | **Partly fires** — at Q_min ≥ 0.80 abstention explodes (0.32 → 0.86) for shrinking gains; at ≤ 0.70 abstention rises modestly (0.19 → 0.24–0.30) for a real 3× floor-violation cut. |
| Q̂ too poorly calibrated for a hard threshold | **Partly fires** — Q̂ is optimistically biased (opt. miscal 0.041 mature → 0.090 cold); the point floor under-protects and degrades with stale evidence. A calibrated LCB is needed for a *guaranteed* floor. |
| Cost savings disappear once escalation is included | **Not directly testable** — the repo has no escalation-cost model; B/C's apparent low cost at high Q_min is an artifact of mass abstention, not real saving. Flagged, not claimed. |
| Soft policy achieves equal/better quality at lower total cost | **Fires for utility, not for sufficiency** — A has lower utility-regret and comparable mean cost, but *higher* true-insufficiency (0.24 vs 0.08). "Better" depends on which objective. |
| Threshold sensitivity makes the policy operationally unstable | **Fires at high Q_min** — 0.90 → 86% abstention. Stable only for moderate thresholds. |
| Stale evidence causes false eligibility/rejection | **Fires** — cold regime floor-violation 0.216 vs 0.081 mature. |
| Quality metric not comparable across models | **Not fired** — Q̂ is a common normalized scale; comparability holds, calibration is the live issue, not comparability. |

**Net:** the constrained policy is **neither rejected nor a clear winner.** It is **conditionally
justified** — for sufficiency-critical use, with mature telemetry and a moderate Q_min — and
**contra-indicated** at high thresholds, under stale evidence, or when expected-utility is the goal.

## 9. Recommended policy

**Keep Policy A (soft weighted utility) as the production default. Ship Policy B (hard floor + min
cost) as an explicit, opt-in `sufficiency-constrained` mode. Do NOT ship Policy C** (identical to B
here — no benefit for the added lexicographic complexity). **Do not change the production default.**

Adopt B only where **all** hold: (a) sufficiency is a hard requirement (regulated / high-consequence);
(b) telemetry is mature (calibration adequate); (c) Q_min is set moderately (≤ ~0.70 on this scale).
Outside those conditions, A is preferable.

**Open requirement before B could be a *guaranteed* sufficiency floor:** replace the point-estimate
floor `Q̂ ≥ Q_min` with a calibrated lower-confidence bound `LCB(Q̂) ≥ Q_min` — which requires a
calibrated quality-variance estimator the repository does not yet have (do not invent it).

**Recommended formal equation (matching the recommendation):**
- Default (A): `m* = argmax_{m ∈ eligible} [ w_q·Q̂ − w_cost·CostNorm − w_lat·LatNorm ]`.
- Opt-in sufficiency mode (B): `m* = argmin_{m ∈ eligible, Q̂(m,x) ≥ Q_min(x)} ExpectedCost(m)`, abstain
  if the feasible set is empty — with the explicit caveat that `Q̂ ≥ Q_min` is a *predicted* floor,
  not a *guaranteed* one, until an LCB estimator exists.

## 10. Public-facing wording

Because no validated hard sufficiency floor is the default (and even Policy B does not *guarantee*
sufficiency given Q̂'s optimistic bias), public materials must **not** claim *"always selects the
cheapest sufficient model."* Use:

> **"Selects an eligible model using calibrated quality, cost, latency, and policy evidence."**

For the opt-in mode, if described at all: *"an optional sufficiency-constrained mode filters to models
predicted to meet a configurable quality floor before minimizing cost"* — with "predicted," never
"guaranteed."

## 11. Internal implementation wording

> Default routing = **soft weighted-utility argmax** over the hard-eligible set (quality/cost/latency
> weights); `acceptable_quality_threshold` is currently a **measurement** field, not an enforced
> selection constraint. An opt-in **Policy B** (`route_variant("B", …, q_min=…)`) enforces a hard
> **predicted**-quality floor then minimizes expected cost, abstaining on an empty feasible set.
> Policy B's floor inherits Q̂'s optimistic miscalibration (residual true-insufficiency ~8% mature,
> ~21% cold) and becomes abstention-dominated above Q_min ≈ 0.8; a calibrated LCB floor is required
> before it can be called a guaranteed sufficiency constraint. Policy C (lexicographic) is equivalent
> to B on the current corpus and is not shipped.

---

## Calibration caveat (standalone)

Q̂ is a fused point estimate, **optimistically biased**, with mean absolute error 0.035 (mature) to
0.058 (cold) vs true quality, and optimistic-miscalibration rate 0.041 → 0.090. A hard
point-estimate floor therefore **cannot guarantee** true sufficiency and **degrades under stale
evidence**. Any "sufficiency guarantee" claim requires a calibrated lower-confidence-bound estimator
that does not yet exist in the repository; until then the floor is *predicted*, not *guaranteed*.

## Exact customer-facing claim the evidence supports

> "Ugence model selection chooses an eligible model using calibrated quality, cost, latency, and
> policy evidence, with an optional sufficiency-constrained mode that prefers lower-cost models
> predicted to meet a configurable quality floor."

(No "cheapest sufficient" guarantee; "predicted," not "guaranteed"; no unvalidated production claim.)

## Deliverables index

- Policies A/B/C: `model_selection_reconciliation/variants.py` (baseline imported read-only).
- Tests (incl. the threshold-usage proofs): `model_selection_reconciliation/tests/test_variants.py`
  (9 pass; baseline suite 15 still pass).
- Comparative + threshold-sensitivity evaluation: `model_selection_reconciliation/evaluation.py`,
  results `model_selection_reconciliation/results/reconciliation_eval_v1.json`.
- Commit hash and changed-file list: recorded in the commit that adds this document.
