# Falsification Pre-Registration — Real-Model Shadow Pilot

*Registered BEFORE any real-model results exist (none do — see `PILOT_STATUS.md`).
This document fixes the thresholds and the "material" definitions in advance so the
eventual real run cannot be graded post-hoc. Evaluate ONLY on the shadow set; the
policy is never tuned on shadow.*

---

## Primary hypothesis

The corrected policy **F2** (minimum-quality as an eligibility gate) can, using only
routing-time information, select the best eligible real model well enough to beat
simpler baselines on selection regret and cost-per-successful-task, without material
quality loss versus strongest-eligible routing.

## "Material" definitions (fixed now)

- **material regret improvement**: ≥ 20% lower mean selection regret than static rules (arm D).
- **material cost improvement**: ≥ 15% lower cost per successful task than strongest-eligible (arm B).
- **acceptable quality loss**: ≤ 2 percentage points lower quality-threshold success than arm B,
  where an **abstention that is correctly routed to human review counts as a deferral, not a failure**
  (report quality-threshold success both ways: abstention-as-failure and abstention-as-deferral).
- **excessive abstention**: > 20% of shadow tasks abstained when ≥1 model actually met the quality bar.
- **material G benefit**: ≥ 10% lower cold-start regret for G vs F2 *after* preflight cost/latency are charged.

## Pre-registered success criteria (all must hold to recommend "build")

1. F2 mean selection regret ≥ 20% below static rules (D).
2. F2 cost per successful task ≥ 15% below strongest-eligible (B).
3. F2 quality-threshold success ≤ 2 pp below B (abstention-as-deferral accounting).
4. Zero hard-policy violations by F2 and G.
5. Explanation completeness ≥ 95%.
6. G shows positive cold-start benefit vs F2 after preflight is charged.
7. G shows **no material benefit in the mature regime** (consistent with the prior
   self-assessment finding; a large mature-regime G benefit would itself be surprising
   and require scrutiny).

## Pre-registered rejection / weakening criteria (any one weakens the hypothesis)

- F2 does not materially beat static rules on regret.
- F2 does not improve cost per successful task.
- Strongest-eligible (B) is economically acceptable AND materially safer (fewer quality failures).
- Cheapest-eligible (C) performs equivalently to F2.
- Minimum-quality gating causes excessive abstention (>20% false abstention).
- Registry/telemetry maintenance burden outweighs measured savings (assessed qualitatively; the
  pilot cannot fully measure maintenance cost).
- Gains disappear outside the development set (dev→shadow generalization gap).
- G fails to improve cold start after preflight cost, OR G causes instability / model starvation.
- Explanations incomplete or inconsistent.
- Benefit concentrated in only 1–2 engineered task cases (report per-class breakdown to check).

## Recommendation mapping (fixed now)

- **All success criteria hold, broad across classes** → Category 3 (bounded, governed
  Hybrid LLM model-selection capability).
- **Compliance + explanation value hold but optimization margin is small / class-narrow**
  → Category 2 (internal deterministic rules) or a slim Category 3.
- **F2 ≈ static rules or ≈ cheapest, no cost win** → Category 1 (stop) or Category 2.
- **Category 4/5 (standalone product / broad orchestrator)** → NOT recommended unless the
  real-model results clearly justify a standalone product boundary (per the workstream's
  explicit constraint). The prior phases already argued against this.

## Status of this pre-registration

No real-model data exists, so **none of the above has been evaluated**. The
self-test (stub) numbers in `SELF_TEST_REPORT.md` are explicitly excluded from this
falsification test — they validate the harness, not the hypothesis.
