# Evaluation Report (v1)

*Phase 18. Final evaluation of all methods on `agr_corpus_v1` (eval n=294) across the frozen noise
schedule. Deterministic; no live calls; no real actions. Clean and noisy reported separately; no
blended headline. Raw: `assertion_gate_robustness/eval_results/robustness_v1.json`
(regenerate: `python3 -m assertion_gate_robustness.evaluation`).*

## Headline table

Escape-AUC = area under the unsupported-escape curve over severities 0–0.5 (lower = safer).
fb@0.3 = false-blocking at severity 0.30. Params = rule/parameter count.

| Method | Clean acc | Escape-AUC (all) | Escape-AUC (detectable) | Escape-AUC (silent) | fb@0.3 | Params |
|---|---|---|---|---|---|---|
| A none | 0.23 | 0.500 | 0.500 | 0.500 | 0.00 | 0 |
| D entailment | 0.66 | 0.155 | 0.123 | 0.191 | 0.09 | 0 |
| E ground+entail | 0.78 | 0.026 | 0.010 | 0.057 | 0.13 | 1 |
| **F G_risk** | 0.91 | **0.024** | 0.010 | 0.049 | 0.13 | 2 |
| G abstain | 0.92 | 0.018 | 0.008 | 0.033 | 0.13 | 1 |
| I weighted | 0.66 | 0.021 | 0.000 | 0.046 | 0.37 | 7 |
| J risk-first | 0.92 | 0.021 | 0.009 | 0.043 | 0.13 | 1 |
| **K calibrated** | 0.85 | **0.007** | 0.000 | 0.012 | 0.18 | 2 |
| L tree | 0.92 | 0.010 | 0.000 | 0.020 | 0.21 | 11 |
| **N AssertionGate** | 0.88 | **0.011** | **0.000** | 0.028 | 0.15 | 9 |
| O oracle | 1.00 | 0.000 | 0.000 | 0.000 | 0.00 | 0 |

## Compound-failure partition (2–3 interacting perturbations)

| Method | Escape | False-blocking | Accuracy |
|---|---|---|---|
| F G_risk | 0.071 | 0.119 | 0.73 |
| G abstain | 0.040 | 0.119 | 0.77 |
| K calibrated | **0.018** | 0.209 | 0.70 |
| L tree | 0.053 | 0.254 | 0.73 |
| N AssertionGate | 0.035 | 0.134 | 0.68 |

## High-risk subgroup (severity 0.30, all noise)

| Method | Escape | False-blocking |
|---|---|---|
| F G_risk | 0.053 | 0.177 |
| K calibrated | **0.009** | 0.265 |
| N AssertionGate | 0.026 | 0.206 |

## Correlated-failure condition (severity 0.30)

| Method | Detectable escape | Silent escape | Correlated escape |
|---|---|---|---|
| E ground+entail | 0.018 | 0.154 | 0.445 |
| F G_risk | 0.018 | 0.128 | 0.392 |
| K calibrated | 0.000 | 0.026 | **0.093** |
| N AssertionGate | **0.000** | 0.071 | 0.185 |

## Ablation (drop one signal from the gate, severity 0.30)

| Dropped | Escape | False-blocking | Accuracy |
|---|---|---|---|
| none (full) | 0.026 | 0.149 | 0.71 |
| uncertainty scalar | 0.026 | 0.149 | 0.71 |
| adequacy | 0.026 | 0.149 | 0.73 |
| **conflict** | **0.040** | 0.149 | 0.64 |
| **freshness** | **0.044** | 0.134 | 0.71 |
| authority | 0.026 | 0.149 | 0.71 |
| risk | 0.026 | 0.149 | **0.56** |

## Findings

1. **G_risk does NOT collapse under noise (H0-1 rejected).** Its escape-AUC is 0.024 and never
   exceeds 0.10 through severity 0.50. The AGE "use G_risk" conclusion **survives modest noise** —
   the prior study's feared limitation is only *partially* borne out. G_risk degrades, but
   gracefully.

2. **The thin AssertionGate roughly halves escape vs G_risk** (AUC 0.011 vs 0.024, a 54% reduction;
   compound escape 0.035 vs 0.071; high-risk escape 0.026 vs 0.053) **at a modest false-blocking
   cost** (0.15 vs 0.13). It **meets its preregistered success criteria.** On *detectable* noise it
   reaches **0.000** escape-AUC.

3. **But a 2-parameter calibrated combination (K) is safer than the 9-rule gate on escape
   everywhere** (AUC 0.007 vs 0.011; compound 0.018 vs 0.035; correlated 0.093 vs 0.185) — at a
   higher false-blocking cost (0.18–0.27 vs 0.15–0.21). So the real design axis is **escape vs
   false-blocking**, not "gate vs no-gate", and the *elaborate* gate is **not uniquely justified**:
   a simpler calibrated rule trades onto the same frontier.

4. **No method controls correlated/silent failure (H0-8 confirmed).** Under correlated noise, escape
   is 0.093 (K) to 0.445 (E); every method except K exceeds the 0.15 open-limitation line, and even
   K is far from safe. When grounding and entailment fail *together with high confidence*,
   uncertainty propagation has nothing true to propagate. **This is the central negative finding.**

5. **Ablation: the load-bearing safety signals are CONFLICT and FRESHNESS detection, not the
   aggregate uncertainty scalar.** Dropping the uncertainty scalar, adequacy, or authority leaves
   escape unchanged (0.026); dropping conflict → 0.040, dropping freshness → 0.044. Risk is
   load-bearing for *accuracy* (0.71→0.56) but not escape. This **partially refutes the gate's own
   design thesis** (uncertainty propagation as the lever): the value is in a few specific detectable
   meta-signals, and the gate could be simplified to those.

6. **The complex tree (L, 11 nodes) does not earn its complexity** — worse false-blocking (0.21–0.25)
   than the gate for no escape advantage over K. **H0-10 rejected.**

## Serious-failure examples

- **Correlated retrieval + entailment failure, high-risk medical claim, severity 0.5:** a wrong
  passage is retrieved (support falsely high) and NLI reads it as supporting (confidence 0.85). The
  gate sees a confident, adequate, non-conflicting, fresh signal → **ALLOW** an unsupported claim.
  No method reliably catches this; it is the realistic worst case.
- **High-risk false-blocking (K):** the calibrated rule escalates 27% of genuinely-ALLOW high-risk
  items — a real human-burden cost of buying lower escape.

## What this does NOT show

Synthetic perturbations, not real model/NLI noise; no live calls; the correlated-failure severity
is a modeled worst case, not a measured deployment rate. External validity untested.
