# BCVF Evaluation Protocol

BCVF is evaluated **only** in its narrowed, falsifiable form: *uncertainty-normalized
consistency between STRUCTURALLY DISTINCT estimators of the SAME latent property*
(`bcvf.py`). It is not privileged; it must earn its place against a fair joint baseline.

## Estimators

Two eligible estimators of the **same latent identity**, e.g. keyboard-identity vs
pointer-identity, or marginal-identity vs coupling-identity. Each provides an identity
score, an uncertainty (σ), a quality, and a missingness status.

**Eligibility (both required, else `BCVF_NOT_ELIGIBLE`):**
- structurally distinct kinds (a fast/slow pair of one stream is **forbidden**;
  identical kinds are rejected);
- each estimator independently shows identity signal on held-out data
  (AUC > `min_marginal_auc`).

## Disagreement

```
q = (z1 − z2)² / (σ1² + σ2² + ε)            normalized disagreement
M_t = η M_{t-1} + ψ(q − κ)                  optional robust temporal accumulation
                                            (ψ = clipped positive part / pseudo-Huber)
```

## Fair, capacity-matched contrast

- `MM_BCVF_NO_DISAGREEMENT` — joint logistic on `[z1, z2, σ1, σ2, noise]`
- `MM_BCVF`                 — same joint logistic on `[z1, z2, σ1, σ2, q]`

Only the 5th input differs (a matched noise feature vs the real disagreement), so BCVF
cannot win on capacity — only on the information in the disagreement. The joint model
receives both estimators AND their uncertainties, so the question is strictly whether
**explicit** disagreement adds value beyond a model that already has the inputs.

## Kill criterion

`MM_BCVF − MM_BCVF_NO_DISAGREEMENT` (paired, participant-clustered bootstrap). BCVF is
unsupported unless it adds a preregistered practical AUC improvement
(`min_auc_improvement`) **without** worsening false challenges
(`max_false_challenge_regression`) or calibration.

## Outcomes

`BCVF_INCREMENTAL_VALUE_SUPPORTED` · `..._SMALL_EFFECT` · `BCVF_NO_INCREMENTAL_VALUE` ·
`BCVF_REGRESSES` · `BCVF_NOT_ELIGIBLE`. Mock data emits `BCVF_PATH_VERIFIED_*` only.

## Explicit exclusions

- No second-order Δ²d primary detector.
- No claim that low disagreement means "safe".
- No challenge deferral based solely on smoothness.
- No fast/slow same-stream pair presented as independent estimators.
- The second-order BCVF term is excluded from primary detection; if ever tested it is
  only as a cheap monotone-additive evidence trigger against Kalman surprise + CUSUM at
  equal probe budget (out of scope here).
