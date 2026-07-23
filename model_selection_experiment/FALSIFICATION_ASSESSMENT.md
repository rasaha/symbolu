# Falsification Assessment — Does the Policy Layer Earn Its Complexity?

*Experiment: `model_selection_experiment/` · registry_v1 / corpus_v1 (37 tasks) /
policy_v1 · deterministic · results in `results/aggregate_metrics.json`.*

> **Reading discipline.** Every number below is produced by the harness and is
> **conditional on the synthetic assumptions in `README.md`**. The experiment
> shows whether the policy *uses evidence and enforces constraints* better than
> simpler strategies. It does **not** prove real-world benchmarks are predictive.
> Claims are bounded accordingly. The final standard is not "the architecture is
> coherent" — it is "the policy measurably beats simpler baselines on regret,
> compliance, effective cost, and reliability." Coherence alone is rejected.

---

## 1. Pre-registered decision thresholds (stated before reading results)

The policy layer is declared **justified** only if, on the mature regime:

- **T1** mean regret ≤ 0.5 × the best simple constraint-aware baseline (C/D/E);
- **T2** constraint-violation rate ≤ that of every constraint-aware baseline (i.e. 0);
- **T3** explanation completeness = 100% and routing deterministic;
- **T4** self-assessment (G) shows *positive cold-start* marginal value and *no net
  harm* under an overconfident-advisory stress test.

It is declared **weakened / rejected** if any bullet in §3 (the falsification
criteria) fires.

---

## 2. Headline results

Mean **selection regret** (lower is better), by arm and regime:

| Arm | Strategy | cold | mature |
|---|---|---:|---:|
| A | Fixed default | 0.968 | 0.968 |
| B | Strongest (unconstrained) | 2.305 | 2.305 |
| C | Cheapest-eligible | 0.093 | 0.093 |
| D | Static rules | 0.055 | 0.055 |
| E | Benchmark-only | 0.266 | 0.266 |
| **F** | **Policy (no self-assessment)** | 0.086 | **0.016** |
| **G** | **Policy + bounded self-assessment** | **0.005** | **0.0095** |

Compliance and explanation quality (mature):

| Arm | Constraint-violation rate | Quality-threshold success | Explanation completeness |
|---|---:|---:|---:|
| A | 0.432 | 0.189 | — |
| B | 1.000 | 0.000 | — |
| C | 0.000 | 0.297 | — |
| D | 0.000 | 0.622 | — |
| E | 0.054 | 0.676 | — |
| **F** | **0.000** | 0.514 | **1.000** |
| **G** | **0.000** | 0.541 | **1.000** |

Thresholds check: **T1** F regret 0.016 ≤ 0.5 × D (0.0275)? **Yes** (0.016 < 0.0275).
**T2** F/G violations 0 ≤ all constraint-aware baselines? **Yes** (C/D = 0, E = 0.054).
**T3** explanation completeness 100%, determinism check passed, F stability 100%? **Yes.**
**T4** (see §4). All four pre-registered thresholds are met.

---

## 3. Falsification criteria — verdict on each

| Criterion (policy should be rejected/weakened if…) | Result | Fired? |
|---|---|---|
| does not reduce regret over static rules | F 0.016 vs D 0.055 (**−71%**) | **No** |
| no meaningful gain after accounting for complexity | 71% regret cut, but absolute gap 0.039 and D wins on threshold-success | **Partial** |
| cheapest-eligible performs equivalently | C 0.093 vs F 0.016 (**5.8×** worse); C threshold-success 0.297 vs 0.514 | **No** |
| strongest-model dominates at acceptable cost | B violates **100%** of hard constraints; regret 2.305 | **No** |
| explanations unstable or misleading | 100% complete & internally consistent; deterministic; F 100% stable | **No** |
| registry-maintenance burden exceeds benefit | **not measured** (synthetic; no maintenance cost modeled) | **Unknown** |
| self-assessment adds no cold-start value or causes net harm | cold ΔRegret **−0.081**; no net harm even adversarial | **No** |
| governance constraints enforceable equally well without a dedicated policy layer | C and D also reach **0** violations | **Yes (partial)** |

**Two criteria fire, both partially — and both narrow rather than refute the value
claim:**

- *Complexity vs gain.* The regret reduction is large in **relative** terms (71% vs
  the best simple baseline) but **small in absolute terms** (0.039), and static
  rules (D) actually deliver **more** quality-threshold successes (0.622 vs 0.514).
  The policy optimizes *utility* (the business's own quality/cost/latency weights);
  D over-provisions quality relative to those weights. Whether the policy's win is
  worth its complexity therefore **depends on how heterogeneous and cost-sensitive
  the workload is** — see §5.
- *Constraint enforcement is not unique to the policy.* Any constraint-first filter
  (C, D) reaches zero violations. **The policy's differentiated value is not "it
  enforces constraints" — it is the combination of enforcement + lowest regret +
  complete, auditable explanations + cold-start self-assessment.** This is the most
  important honest correction the experiment produces.

---

## 4. Self-assessment ablation (mandatory) — G vs F

ΔRegret = G − F (negative = G better), by regime:

| Regime | F regret | G regret | Δ (G−F) | Δ threshold-success |
|---|---:|---:|---:|---:|
| cold | 0.086 | 0.005 | **−0.081** | +0.135 |
| partial | 0.016 | 0.010 | −0.006 | +0.027 |
| mature | 0.016 | 0.0095 | −0.007 | +0.027 |

**Pre-registered hypothesis — confirmed.** Bounded self-assessment cuts cold-start
regret by **94%** (0.086 → 0.005) and lifts cold-start threshold-success by 13.5
points, then its marginal value **collapses toward zero** as telemetry matures
(−0.006 to −0.007). This is exactly the regime-dependent, decaying value predicted
in `CAPABILITY_NEGOTIATION_SELF_ASSESSMENT_RESEARCH.md`.

**Harm test — overconfident advisory (3× bias, 2× noise).** Regret delta vs F:
cold −0.078, partial −0.003, mature −0.007. Even a badly miscalibrated advisory
**does not make G worse than F** — because it is *bounded* (confidence-weighted,
fused with other evidence, forbidden from asserting infrastructure facts). At
maturity telemetry dominates and washes the bad advisory out entirely. Conclusion:
**bounded self-assessment is safe precisely because it is bounded; the value comes
from the cold-start regime and nowhere else.**

Minor cost: G adds a preflight cost/latency charge (reflected in cost/latency
metrics) and shows slightly lower routing stability at the partial regime (0.973 vs
F's 1.000). Its warm-regime benefit does not justify that tax — so G should be
**gated to low-telemetry conditions**, not run always.

---

## 5. Failure analysis — where the policy is weak or merely adequate

1. **Regret vs quality-threshold divergence.** F/G minimize utility-regret but score
   *lower* on quality-threshold success than static rules D (0.514/0.541 vs 0.622),
   because the quality threshold is modeled as a **soft target**, not a hard
   constraint, and the utility-optimal pick under cost/latency pressure can fall
   below it. **Design implication:** if an enterprise needs the quality bar
   *guaranteed*, `acceptable_quality_threshold` should be promoted to a hard
   constraint (feeding eligibility), after which the policy would dominate D on both
   axes. This is a real, actionable finding, not a wash.
2. **The context trap is a shared blind spot.** All arms filter on *declared*
   context; none detects the declared-vs-effective gap (200k declared / 128k
   effective). F even **violates once at cold start** (rate 0.027) by selecting the
   trapped model, and only avoids it at maturity because telemetry improves its
   quality estimate for the *safe* model — an **emergent, not principled**, escape.
   **Design implication:** effective context must be a *measured* registry field
   feeding eligibility, per the policy spec's declared/measured provenance split.
   The experiment did not exercise that field, and it shows.
3. **The policy is not cheap.** Cost per successful task: F ≈ 26.8 vs the naive
   default A ≈ 1.6. The policy *buys* quality/utility; it is not a cost minimizer.
   That is correct given the business weights, but a cost-obsessed deployment must
   confirm per-priority behavior (cost-first tasks do route to cheap models; the
   aggregate mixes priorities).
4. **Registry-maintenance burden is unmodeled.** The one falsification criterion the
   experiment **cannot** answer: whether keeping the registry (benchmarks, telemetry,
   effective-context measurements) current costs more than the routing benefit. This
   is an operational question requiring real deployment data.
5. **External validity.** Everything here is conditional on benchmarks/telemetry
   being informative-but-noisy signals of true quality. The experiment proves the
   policy *uses* such signals correctly; it does **not** prove real signals are
   predictive. That is phase-two work with real telemetry.

---

## 6. Overall falsification verdict

**The policy layer is not falsified — but the value claim is narrowed and
conditional.**

- On the **primary metric (regret)** the policy beats every simpler baseline,
  including the strong static-rules baseline, by a wide *relative* margin, and does
  so while holding constraint violations at zero and explanations at 100%
  completeness. All four pre-registered thresholds are met.
- **Bounded self-assessment earns a place — but only as a cold-start prior**, with
  near-zero warm-regime value and no net harm. Gate it to low-telemetry conditions.
- **The differentiated, durable value is compliance + auditable explanation +
  cold-start robustness, not raw optimization.** Simple constraint filters already
  enforce constraints; simple static rules already get close on regret in a *stable,
  homogeneous* setting. The policy's edge widens with **task heterogeneity, provider
  heterogeneity, cold start, and the need for per-decision auditability** — and
  shrinks toward "unnecessary" in a homogeneous, stable, one-or-two-provider
  deployment.

**Recommendation to implement is therefore CONDITIONAL, not automatic** — consistent
with the final decision standard. See `ARCHITECTURE_NOTE.md`.
