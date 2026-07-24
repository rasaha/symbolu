# Prior Result and Scope

*Phase 1. Records exactly what the AGE experiment established, what it did not, and why this
robustness track is necessary. Prior AGE outcome-bearing artifacts are hashed and guarded by
`assertion_gate_robustness/verify_prior.py` (fails on drift).*

## What the AGE experiment established

1. **Assertion governance is a legitimate delivery-boundary function.** Single existing signals
   (confidence 0.31, grounding 0.38, entailment 0.69, authority 0.37 disposition agreement) are
   each insufficient, most with dangerous unsupported-escape rates.
2. **A dedicated AGE engine is not justified by that evidence.** The reference engine scored 0.974
   and was *strictly dominated* by a trivial composition.
3. **A thin composition — grounding + entailment + a risk rule (`G_risk`) — matched the synthetic
   rubric perfectly (1.00 agreement, 0.00 unsupported-escape).**

## What the AGE experiment did NOT establish

- **That the perfect `G_risk` result survives realistic signal noise.** The evaluation used
  **oracle-clean** grounding/entailment/risk labels. The report explicitly flagged this: "the
  perfect result may depend on unrealistically clean input signals."
- Real model outputs, real NLI/grounding noise, human disposition labels, correlated signal
  failure, stale/conflicting evidence — all untested.

## Prior artifacts (frozen; verified by `verify_prior.py`)

| Artifact | Role | SHA-256 (prefix) |
|---|---|---|
| `assertion_governance/data/corpus_v1.json` | 343-item AGE dataset | `f16ed388…` |
| `assertion_governance/eval_results/evaluation_v1.json` | AGE evaluation outputs | `90dc6b3a…` |

Key numbers preserved (from that eval, oracle-clean signals, eval n=229): `G_risk` agreement
**1.00** / escape **0.00**; `AGE` engine **0.974** / escape **0.00**; best single technique
(entailment) **0.69**.

## Why this track is necessary

The AGE conclusion ("use the thin `G_risk` composition, not a dedicated engine") rests entirely on
oracle-quality signals. If those signals are **noisy, incomplete, stale, contradictory, or
miscalibrated** — as they are in any real deployment — a rule that trusts them blindly may become
unsafe, and a thin gate that *propagates uncertainty* (or even a more complex engine) may be
justified. This track tests that limitation directly.

## Scope discipline

- The **343-item AGE dataset is NOT reused as the primary outcome dataset.** It may serve only as a
  calibration/compatibility reference. This track builds a **new** robustness corpus.
- No prior AGE artifact, and none of ExecutionGate / ModelPolicy / ActionGate / TAP / Unified
  Control Plane / control-plane shadow / frozen replay datasets, is modified.
- No live provider calls, no real actions, no control-plane integration, no enforcement.
