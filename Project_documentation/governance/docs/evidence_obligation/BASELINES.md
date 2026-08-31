# Baselines A–S (Phase 8)

*`evidence_obligation/baselines.py` → `eval_results/baselines.json`. Nineteen obligation policies scored
against the independent gold on held-out-natural (250) and adversarial (100). This measures
**obligation-assignment accuracy and safety**; the ultimate endpoint (downstream utility at equal
safety) is Phase 15.*

## Results

| Baseline | held exact | held accept | held unsafe | adv unsafe |
|---|---|---|---|---|
| A uniform_strong | 0.036 | 0.112 | 0 | 0 |
| B uniform_qualify | 0.000 | 0.000 | 0 | 0 |
| C risk_only | 0.332 | 0.780 | 0 | 0 |
| D domain_only | 0.296 | 0.844 | 33 | 50 |
| E claim_type_only | 0.572 | 0.764 | 10 | 20 |
| F source_role_only | 0.280 | 0.368 | 19 | 50 |
| G claim_type+risk | 0.572 | 0.672 | 3 | 0 |
| H source+authority | 0.020 | 0.040 | 13 | 0 |
| I claim_type+source | 0.564 | 0.784 | 7 | 0 |
| J claim_type+source+risk | 0.560 | 0.660 | 3 | 0 |
| **K global_threshold_reduction** | 0.296 | 0.844 | 33 | **50** |
| L lowrisk_bypass | 0.000 | 0.000 | 0 | 0 |
| **M internal_always_auth** | 0.012 | 0.020 | 17 | 10 |
| **N impl_always_auth** | 0.276 | 0.340 | 19 | **50** |
| **O nogate_all_lowrisk** | 0.000 | 0.176 | 33 | **50** |
| P simple_contextual | 0.568 | 0.772 | 0 | 0 |
| **Q reference** | 0.560 | 0.736 | 6 | **0** |
| R oracle | 1.000 | 1.000 | 0 | 0 |
| **S learned** | **0.820** | **0.892** | **0** | **0** |

## Honest readings (carried into the decision)

1. **The unsafe shortcuts are unsafe, as predicted.** Domain-only (D), source-only (F), global-threshold
   reduction (K), impl-always-authoritative (N), and no-gate-all-low-risk (O) each leak **50/100**
   adversarial unsafe assignments; internal-always-authoritative (M) leaks 10. These validate the
   corresponding nulls in the negative direction and are disqualified on safety.

2. **A simple learned comparator (S) beats the reference component (Q) on accuracy at equal safety.**
   S — most-frequent gold obligation per `(claim_family, risk_tier)`, fit on DEVELOPMENT only — scores
   0.820 exact / 0.892 acceptable with **0 unsafe** on both held-out and adversarial, versus Q's 0.560 /
   0.736 / 6 held-unsafe. This is a **direct H0-13 signal**: on obligation-assignment accuracy, the
   richer component does not beat a simple learned per-(claim-type, risk) lookup. (Caveat: the gold is
   itself substantially a function of claim-type + risk, so a learned map over those features recovers it
   well — this is disclosed and examined in the ablation.)

3. **Several simple safe policies match Q's safety.** C (risk-only), P (simple-contextual), and S all
   reach 0 adversarial unsafe — and C/P/S have **0 held-unsafe** vs Q's 6. On this endpoint Q is not
   safer than the simple safe comparators; its 6 held-unsafe are the high-risk code docstrings gold marks
   HUMAN_REVIEW.

4. **Q must earn its complexity downstream.** Obligation accuracy is not the endpoint. Whether Q's richer
   obligation vocabulary yields better **downstream utility** (clean allow, over-qualification) at equal
   **downstream safety** than C/P/S is decided in Phase 15 and the ablation/complexity challenge
   (Phase 18–19). The baseline table alone points toward simplification (decision 3/4) unless the
   downstream evaluation shows otherwise.

## Determinism

All predictors are pure functions of the item; S is fit only on DEVELOPMENT and never on held-out.
`baselines_sha256` pins the scored result.
