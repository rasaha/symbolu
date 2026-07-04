# B1 Post-Verdict Exploratory Diagnostic — per-task / per-arm generation effect

**Status:** `POST_VERDICT_EXPLORATORY` — recorded 2026-07-04.
**This does NOT change the B1 verdict.** The pre-registered B1 verdict remains
**`RANDOM_OR_SCRAMBLED_MATCHES`**. Track B remains **BLOCKED**. `LIMITED_GENERATION_UTILITY` is **not
supported**. No ontology validation · no Sanskrit privilege · no semantic-truth claim · no Track G
rescue. **Structure, not validated meaning.**

Source: read-only diagnostic `run_b1_diagnostic.py` (`d663dab`) over the frozen judge run
(`B1_JUDGE_RUN_V2_PROVENANCE`, `b4976b9`) and score (`B1_SCORE_RESULT_ANCHOR`, `5ec5443`). No frozen
artifact, judge file, or score was modified; no re-judge; no re-score.

---

## Main conclusion

The conditioning improved generation on **creative/evocative tasks** versus neutral **X**, but the
improvement was **generic, not H2-specific** — arm A never separated from **random resonance R** on any
task. Direct dictionary meaning (D) outperformed A on several tasks, and A carried a small
factual/accuracy cost on the explanation task (T4).

---

## 1. Task-specific A vs X (improvement over neutral, primary stratum)

| Task | A_vs_X (win-rate [95% CI]) | interpretation |
|------|----------------------------|----------------|
| T5 tone-match | 0.82 [0.75, 0.90] | strong improvement |
| T3 metaphor | 0.76 [0.67, 0.86] | clear improvement |
| T6 evoke | 0.65 [0.54, 0.75] | improvement |
| T2 kind message | 0.58 [0.46, 0.70] | marginal / not robust (CI crosses 0.5) |
| T1 reflective | 0.48 [0.39, 0.57] | no improvement |
| T4 explain accurately | 0.46 [0.36, 0.56] | no improvement; possible accuracy drag |

Improvement over neutral is **task-local**: present on figurative/creative tasks (T3, T5, T6), absent
on the reflective paragraph (T1) and the accurate-explanation task (T4).

## 2. A vs R by task — the H2-specific test

| Task | A_vs_R | beats R? |
|------|--------|----------|
| T1 | 0.49 | no |
| T2 | 0.51 | no |
| T3 | 0.47 | no |
| T4 | 0.53 | no |
| T5 | 0.54 | no |
| T6 | 0.54 | no |

**Every CI straddles 0.5. Tasks where A uniquely beats R: NONE** (primary and privative). Therefore
**no task-local H2-specific signal was found** — wherever A improved over X, random resonance R
produced a similar gain.

## 3. Dictionary-control caveat

D beat A on T1, T2, and T6:

- A_vs_D (T1) = 0.42
- A_vs_D (T2) = 0.41
- A_vs_D (T6) = 0.41

For those tasks, **direct dictionary meaning outperformed resonance** conditioning — the opposite of
what an H2-specific advantage would predict.

## 4. T4 correctness caveat (accuracy tradeoff)

Correctness-problem flag rate on the T4 (explain plainly and accurately) task, per arm:

| Arm | flagged / total | rate |
|-----|-----------------|------|
| A | 30 / 1500 | 2.0% |
| R | 5 / 300 | 1.7% |
| C | 5 / 300 | 1.7% |
| S | 2 / 300 | 0.7% |
| D | 1 / 300 | 0.3% |
| X | 0 / 300 | 0.0% |

**Interpretation:** resonance-style conditioning can increase evocative quality but may carry a small
**factual/correctness cost** — A had the highest T4 problem rate, and neutral X had none.

## 5. R vs X — not measured

The design judged **A vs each control only**; there are no control-vs-control (R-vs-X) packets, so
R's lift over X is **not directly measured**. Because A ≈ R overall (A_vs_R 0.514, CI straddles 0.5),
R's lift over X is *inferred* to be ≈ A's lift over X (A_vs_X 0.627). This is an inference, not a
measurement, and does not affect the verdict.

---

## Final status

```
B0:                                 FROZEN
B1:                                 SCORED
Verdict:                            RANDOM_OR_SCRAMBLED_MATCHES
Track B:                            BLOCKED
H2-specific utility:                not supported
Generic creative/evocative effect:  supported (exploratorily)
Factual/accuracy use:               not supported; possible correctness cost
```

Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. This diagnostic corroborates, and does not overturn, that prior.

**Structure, not validated meaning.** Exploratory only; the pre-registered verdict stands.
