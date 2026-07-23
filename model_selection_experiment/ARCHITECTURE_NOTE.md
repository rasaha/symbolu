# Architecture Note — Model Selection Policy, Empirically Tested

*Companion to `FALSIFICATION_ASSESSMENT.md`. Answers the three questions the
workstream posed, from the experiment's real numbers (mature regime, 37 tasks,
deterministic). All results are conditional on the synthetic assumptions in
`README.md`.*

---

## Q1 — Is the Model Selection Policy empirically justified?

**Yes, on the primary metric — but conditionally, and not for the reason one might
assume.**

- The policy (arm F) achieves **mean regret 0.016**, versus **0.055** for the best
  simple baseline (static rules, D), **0.093** for cheapest-eligible (C), **0.266**
  for benchmark-only (E), **0.968** for a fixed default (A), and **2.305** for
  unconstrained strongest-model routing (B). That is a **71% regret reduction over
  static rules** and **5.8×** over cheapest-eligible.
- It holds **constraint violations at zero** (vs 43% for the fixed default and 100%
  for strongest-model routing) and produces **100%-complete, internally consistent,
  deterministic** decision records.

**The honest correction the experiment forces:** the policy's justification is *not*
"it enforces constraints" — a plain eligibility filter (arms C, D) also reaches zero
violations. Its differentiated value is the **combination** of (a) lowest regret,
(b) complete per-decision explanations, and (c) cold-start robustness. And the
*absolute* regret gap over a well-tuned static-rules baseline is small (0.039); the
policy's edge **widens with workload heterogeneity, provider heterogeneity, cold
start, and audit requirements, and narrows toward unnecessary in a stable,
homogeneous, one-or-two-provider setting.** Justified — where those conditions hold.

---

## Q2 — Does self-assessment add marginal value?

**Yes, but only at cold start, and only as a bounded prior.**

- ΔRegret (G − F): **−0.081 at cold start** (a 94% cut, 0.086 → 0.005), decaying to
  **−0.006 / −0.007** at partial/mature telemetry.
- Under an **overconfident-advisory stress test** (3× bias, 2× noise), G still does
  **not** underperform F — bounding (confidence-weighted fusion, forbidden from
  asserting infrastructure facts) prevents harm; mature telemetry washes bad
  advisory out entirely.

This exactly matches the prediction of the prior self-assessment investigation:
**useful cold-start metadata, decaying to ~zero marginal value as telemetry
matures, safe because bounded.** Operational implication: **gate self-assessment to
low-telemetry conditions** rather than paying its preflight cost/latency always.

---

## Q3 — What is the appropriate product framing?

| Candidate framing | Verdict |
|---|---|
| Standalone **AI Orchestrator** | **No.** The experiment measures a *decision function*, not an execution engine. Nothing here argues for building orchestration; the value sits in the policy, not the wiring. |
| **Hybrid LLM model-selection capability** | Partly — it is a capability the platform can expose, but this framing undersells the compliance/explanation spine that is the durable differentiator. |
| **ModelGate governance capability** | **Yes — primary framing.** The two results that are both *strong and non-commoditized* are **0% constraint violations** and **100% complete, auditable explanations**. That is a governance capability — the pre-reasoning analogue of ActionGate — with model-selection optimization layered on top. |
| No new product | **No** — the policy beats every simpler baseline on the primary metric; there is measurable value to expose. |

**Recommendation:** frame and build this as a **ModelGate governance capability**
inside the AI Control Plane — a governed, explainable, deterministic
*model-selection policy*, with optimization (quality/cost/latency) as a real but
secondary, telemetry-dependent benefit, and **bounded self-assessment gated to cold
start**. Do **not** frame it as a standalone orchestrator. The orchestrator, if
built, is the commoditized executor of this policy — not the product.

---

## One-paragraph summary

A governed Model Selection Policy measurably reduced selection regret versus every
simpler routing strategy tested (71% below static rules, 5.8× below
cheapest-eligible) while holding hard-constraint violations at zero and producing
fully auditable decision records — but the differentiated, durable value is
**compliance + explainability + cold-start robustness**, not raw optimization, and
the margin over a good static-rules-plus-constraint-filter baseline is modest and
grows only with workload/provider heterogeneity and audit need. Bounded
self-assessment added strong cold-start value that decayed to ~zero with mature
telemetry and caused no harm even when miscalibrated. The right product framing is a
**ModelGate governance capability**, not a standalone AI Orchestrator. Implementation
is justified **conditionally** — where heterogeneity, cold start, and auditability
matter — consistent with the standard that coherence alone is not sufficient reason
to build.
