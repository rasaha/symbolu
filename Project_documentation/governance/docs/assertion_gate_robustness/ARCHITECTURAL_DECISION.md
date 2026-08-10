# Architectural Decision

*Phase 20. One decision, separated along the four required axes. Grounded in the evaluation, not in
preference.*

## Decision: **KEEP ONLY FOR HIGH-RISK DOMAINS — as the simplest safe rule, not the elaborate gate.**

(Formally: option 2 "KEEP ONLY FOR HIGH-RISK DOMAINS", qualified by option-3/5 evidence — replace the
elaborate gate with the simpler calibrated rule, and never treat any variant as a sole safety layer.)

## The four axes, separated

### Architectural need — **YES, in high-risk domains only**
A delivery-boundary assertion check has real, measurable safety value under noise: it roughly halves
unsupported-escape versus the risk-blind-ish composition and reaches zero escape on *detectable*
noise. But that value is concentrated where escape is costly (high-risk medical/legal/financial/
cyber). In low-risk domains, G_risk's residual escape is tolerable and the layer's extra
false-blocking is not worth its cost. **Need: high-risk yes, low-risk no.**

### Algorithmic complexity — **NOT justified; prefer the simplest safe rule**
The evaluation is unambiguous against complexity: the 2-parameter calibrated combination is safer on
escape than the 9-rule gate and the 11-node tree, everywhere. The elaborate gate is over-built, and
ablation shows only *conflict* and *freshness* detection carry the safety load. **Recommendation:
implement the delivery check as a minimal calibrated rule (support discounted by
confidence/calibration/authority/staleness, plus explicit conflict and freshness gates), tuned to
the domain's escape/false-blocking tolerance — not as a bespoke multi-rule engine.**

### Domain scope — **high-risk delivery boundaries**
Scope the layer to decision-bearing high-risk assertions. Skip it for low-risk informational
answers, where grounding+entailment already suffices and the human-burden cost of extra
escalation/qualification is unjustified.

### Evidence maturity — **synthetic only; not deployment-validated**
All results are synthetic (modeled noise, rubric annotators). The **correlated/silent-failure
limitation is decisive and unsolved**: no method is safe when grounding and entailment fail together
with high confidence. Before any production use, this must be tested on real NLI/grounding noise and
real model outputs, and the layer must be paired with an *independent* check on correlated failure
(e.g. source-independence verification), which this study shows composition alone cannot provide.

## What this overturns and confirms from AGE

- **Confirms:** the delivery-boundary function is real and worth a thin composition (AGE's core
  claim), and a bespoke complex engine is not justified (AGE's negative finding, now *strengthened*
  under noise — complexity is even less justified when the simplest calibrated rule wins).
- **Refutes / qualifies:** AGE's "G_risk is perfect" was oracle-dependent; under noise G_risk leaks,
  and a calibrated, uncertainty-discounting rule is meaningfully safer in high-risk domains. So the
  AGE recommendation shifts from "use G_risk" to "use a calibrated conflict/freshness-aware rule,
  scoped to high-risk."

## One-line answer

**Keep an assertion-delivery check only for high-risk domains, implement it as the simplest
calibrated rule that gates on conflict and freshness (not an elaborate engine), and never rely on
it alone — because no composition of grounding, entailment, and risk is safe against correlated
signal failure.**
