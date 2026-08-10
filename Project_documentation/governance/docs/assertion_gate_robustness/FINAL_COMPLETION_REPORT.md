# AssertionGate Noisy-Signal Robustness Study — Final Completion Report

*Isolated track testing the AGE study's central limitation: does the perfect `G_risk` result survive
realistic signal noise? Deterministic; no live calls; no real actions; no control-plane integration;
no enforcement. No prior AGE / control-plane / frozen artifact modified.*

## Primary question — answered

> Does a thin AssertionGate (grounding + entailment + adequacy + risk + policy) remain reliable when
> its inputs are noisy, incomplete, stale, contradictory, miscalibrated, or from imperfect models?

**Partially, and with a decisive caveat.** On *detectable* noise it is reliable (0.000 escape-AUC).
On *silent/correlated* noise — the realistic worst case — **no method, thin or complex, is reliable**
(escape 0.09–0.45). The thin gate roughly halves unsupported-escape versus `G_risk` under noise, but
a simpler 2-parameter calibrated rule is safer still, so the *elaborate* gate is not uniquely
justified.

## Files created

- **Package `assertion_gate_robustness/`** (12 modules): `verify_prior.py`, `signals.py`,
  `perturbations.py`, `taxonomy.py`, `dataset.py`, `baselines.py`, `policy.py`, `gate.py`,
  `qualification.py`, `calibration.py`, `metrics.py`, `evaluation.py`; `tests/test_robustness.py`;
  `data/v1/corpus.json`; `eval_results/robustness_v1.json`.
- **Docs `docs/assertion_gate_robustness/`** (11): PRIOR_RESULT_AND_SCOPE, SIGNAL_MODEL,
  NOISE_TAXONOMY, FALSIFICATION_PLAN, GROUND_TRUTH_PROTOCOL, DISAGREEMENT_POLICY,
  QUALIFICATION_PROTOCOL, VERSION-less EVALUATION_PROTOCOL, EVALUATION_REPORT,
  LIMITATIONS_AND_FALSIFICATION, ARCHITECTURAL_DECISION, and this report.

## Prior artifacts verified unchanged

`verify_prior.py`: `assertion_governance/data/corpus_v1.json` (`f16ed388…`) and
`evaluation_v1.json` (`90dc6b3a…`) intact. `execution_gate/frozen/replay_v1` aggregate
`8b05b2da798a6222` unchanged. Prior AGE test suite (10) passes unmodified.

## Dataset and design

- `agr_corpus_v1`: **392 base items** → **1176 cases** across CLEAN / CONTROLLED_NOISE /
  COMPOUND_FAILURE. 8 domains, 5 evidence relations, 7 support/claim buckets; 196 high-risk;
  dev/eval 98/294. **Independent** of the frozen 343-item AGE dataset.
- **Ground truth** from two independent annotator rules (A relation-first, B adequacy-first),
  conservatively adjudicated, **8.4% disagreement rate recorded** (not hidden). Methods see only
  observed (possibly perturbed) signals; gold is reality-based.
- **Perturbations:** 22 signal-level (10 silent, 12 detectable) + 3 qualification/policy-level = 25.
- **Noise severities:** 0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50.

## Baselines and tests

- **14 methods:** A none, B confidence, C grounding, D entailment, E ground+entail, F G_risk, G
  abstain, H majority, I weighted, J risk-first, K calibrated, L decision-tree (11 nodes, from
  scratch), N thin AssertionGate (9 rules), O oracle. Tunable ones dev-tuned; parameter counts
  reported.
- **32 tests pass** (22 robustness + 10 prior AGE, unchanged, unmasked).

## Key results

| Metric | F G_risk | N AssertionGate | K calibrated | O oracle |
|---|---|---|---|---|
| clean accuracy | 0.91 | 0.88 | 0.85 | 1.00 |
| escape-AUC (all noise) | 0.024 | 0.011 | **0.007** | 0.000 |
| escape-AUC (detectable) | 0.010 | **0.000** | 0.000 | 0.000 |
| escape-AUC (silent) | 0.049 | 0.028 | 0.012 | 0.000 |
| compound escape | 0.071 | 0.035 | 0.018 | — |
| high-risk escape @0.3 | 0.053 | 0.026 | 0.009 | — |
| correlated escape @0.3 | 0.392 | 0.185 | 0.093 | — |
| false-blocking @0.3 | 0.13 | 0.15 | 0.18 | 0.00 |
| params | 2 | 9 | 2 | 0 |

## Findings summary

- **Clean:** even clean `G_risk` is not perfect on this harder corpus (0.91) — the AGE 1.00 was
  oracle-dependent.
- **Noisy:** `G_risk` degrades gracefully (escape-AUC 0.024, never > 0.10) — **it does not collapse**.
- **Compound failure:** escape rises for all; gate halves `G_risk`'s.
- **Unsupported escape:** thin gate −54% vs `G_risk`; calibrated rule is even lower.
- **False blocking:** gate 0.15, calibrated 0.18 — the real trade-off axis.
- **Qualification accuracy:** semantic-preservation 1.0, new-claim 0, structurally safe under noise.
- **Correlated-failure:** **unsolved by every method** (0.09–0.45) — the central negative finding.
- **Robustness thresholds:** no method exceeds escape 0.10 on all/detectable noise through 0.50; all
  exceed it under correlated failure.
- **Ablation:** load-bearing safety signals are **conflict** and **freshness**, not the aggregate
  uncertainty scalar (gate is over-built).
- **Complexity comparator:** decision tree does not earn its complexity; simplest calibrated rule wins.

## Falsification conclusions

H0-1 rejected (G_risk survives), H0-2 partially holds (abstention close), H0-5 largely rejected
(no over-blocking), H0-7 rejected (qualification safe), **H0-8 confirmed (correlated failure
undetected)**, H0-10 rejected (complexity unjustified).

## Architectural decision

**KEEP ONLY FOR HIGH-RISK DOMAINS** — implemented as the **simplest calibrated conflict/freshness-
aware rule** (not the elaborate 9-rule gate), and **never as a sole safety layer** (no composition
is safe against correlated signal failure). Axes: need = high-risk yes / low-risk no; complexity =
not justified (prefer simplest); scope = high-risk delivery boundaries; maturity = synthetic only,
needs real-signal + correlated-failure validation. This **shifts the AGE recommendation from "use
G_risk" to "use a calibrated conflict/freshness-aware rule scoped to high-risk."**

## Unresolved limitations

Correlated/silent failure (no composition is safe); synthetic noise and rubric annotators (no real
NLI/model-output validation); escape/false-blocking is a policy trade-off, not a solved problem.

## Commit SHAs

| Milestone | SHA | Content |
|---|---|---|
| M1 | `9df5314` | prior-result freeze + signal model |
| M2 | `68678da` | noise taxonomy + falsification plan |
| M3 | `6b63827` | ground-truth protocol + corpus |
| M4 | `8a43174` | baselines A–O |
| M5 | `7c9b2a7` | thin AssertionGate + policy/qualification/calibration |
| M6 | `4c7f33e` | disagreement + qualification policies |
| M7 | `058ef14` | robustness / correlated / ablation / complexity machinery |
| M8 | `4e5b424` | test suite |
| M9 | `dd042f9` | evaluation protocol freeze |
| M10 | `1d26231` | final evaluation report |
| M11 | `705f02b` | falsification + architectural decision |
| M12 | *this commit* | final completion report |
