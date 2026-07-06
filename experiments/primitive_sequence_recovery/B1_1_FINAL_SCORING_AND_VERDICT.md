# B1.1 Final Scoring and Verdict (LOCK)

## 1. Scope

This is the **locking record** for B1.1. It consolidates the **already-produced** scoring diagnostics
(`run_b1_1_scorer.py`, `run_b1_1_per_judge_breakdown.py`) and the committed forensic report (`ccad8fb`) into
a single final verdict. It does **not**:

- rerun judges, rerun scoring, or change the judge panel;
- exclude Meta-Llama-3 or any judge post-hoc (the prereg exclusion rule did **not** trigger — 0 attention
  failures);
- rescue or reinterpret the result, or modify any B1.1 artifact / frozen manifest;
- change the B1 verdict, unblock Track B, or claim ontology validation / Sanskrit privilege / semantic truth.

All numbers below are the **committed** aggregate point estimates from the forensic report (`ccad8fb`) and
the per-judge breakdown; the full scoring JSON/MD produced on the model-access host are the source of record
for the item-clustered bootstrap CIs. **Structure, not validated meaning.**

## 2. Prereg primary success criterion

> **A must beat `R_deranged` AND `R_domain` AND `R_same`** (item/word-clustered paired bootstrap, corrected
> CI **lower bound > 0.5**), **survive Holm–Bonferroni** multiplicity correction across the co-primary set,
> **and avoid unacceptable correctness degradation (T4)**.

Beating the weak controls (D, S, C, X) is **necessary but not sufficient**; the positive label is gated on
the three **R** controls. (Source: `b1_1_scorer_config.json` → `primary_success_criterion`,
`verdict_label_rules`.)

## 3. Primary comparison table (A-win; A beats a control iff corrected CI lower bound > 0.5)

| comparison | AGG A-win | criterion | outcome |
|---|---|---|---|
| **A vs R_deranged** (crux) | **0.516** | LB > 0.5 | **NOT beaten** — near tie; every judge's CI straddles 0.5 (not robust) |
| **A vs R_domain** | **0.460** | LB > 0.5 | **NOT beaten** — A *loses* |
| **A vs R_same** | **0.471** | LB > 0.5 | **NOT beaten** — A ties/loses |

**All three co-primaries fail.** A does not beat a single strong symbolic control; on two of three (R_domain,
R_same) A is below 0.5 outright, and on the crux (R_deranged) the point estimate 0.516 is a non-robust near
tie whose CI includes 0.5. Multiplicity correction is moot — the criterion fails before correction, and Holm
correction only makes "beating" harder, never easier.

## 4. Secondary comparison table (necessary-but-not-sufficient controls)

| comparison | AGG A-win | reading |
|---|---|---|
| A vs C (surface facts) | **0.694** | A beats sparse surface conditioning |
| A vs X (neutral filler) | **0.581** | A beats neutral conditioning |
| A vs D (dictionary gloss) | **0.548** | A beats a bare dictionary gloss (aggregate) |
| A vs S (scrambled own varṇa) | **0.497** | A **ties** scrambled — order of its own varṇa bridges does not matter |

A beats the weak/sparse controls, confirming that **richer coherent conditioning helps open generation** —
but that help is **not word-specific**: A cannot separate itself from any fluent, real, coherent bridge, and
scrambling A's own varṇa order costs nothing (S tie). This is the signature of **generic symbolic resonance**,
not H2 word-fit.

## 5. Per-judge caveats (all three judges kept; 0 attention failures → prereg exclusion rule did not trigger)

| judge | parse profile | lean on A |
|---|---|---|
| **gemma-2-9b-it** | cleanest — 1 parse-fail, 0 repairs | **most skeptical of A** (overall A-win ≈ 0.496, slightly *against* A) |
| **Llama-3.1-8B-Instruct** | 382 unparseable (~9%, forced to ties) | favors A (≈ 0.555) |
| **Meta-Llama-3-8B-Instruct** | ~2,420 missing-final-brace repairs (~58%; the B1 `ACCEPT_WITH_CAVEAT` concern realized) | favors A (≈ 0.563) |

**Direction of the caveat is unfavorable to A, not favorable.** The *cleanest* judge (gemma) is the one most
skeptical of A; the two judges carrying parse/repair quality caveats are the ones that lean pro-A. So any
concern that judge-quality problems inflated A points the wrong way for a rescue. The verdict is **robust**:
it survives **dropping Meta-Llama-3** entirely and **dropping Llama's parse-fails** — the co-primaries still
fail. No judge was excluded; the prereg exclusion rule (fail > 1 or > 25% of attention checks) did not fire.

## 6. Task-level and correctness (T4) diagnostics

- **Task-level diagnostics** were enabled in the scorer (`task_level_diagnostics: true`) and are recorded in
  the model-access-host scoring report. They are **not** reproduced cell-by-cell here to avoid restating
  numbers not committed to this repo; the aggregate conclusion is unchanged — no task family lifts A above
  the R controls on the primary criterion. (The forensic report notes the open reflective/metaphor/evoke
  tasks reward evocative fluency, which any coherent bridge supplies.)
- **Correctness (T4) tracking** was enabled (`correctness_tracking.enabled: true`) and reported separately
  from creative wins. It does **not** change this verdict: the positive label already fails on the three R
  controls before the correctness gate is reached, so T4 cannot earn `LIMITED_GENERATION_UTILITY`. The
  independent Track F negative **`CORRECTNESS_DEGRADED`** is **preserved** as a standing prior.

## 7. Verdict

**Primary success: NOT MET.** A fails all three co-primary R controls (R_domain and R_same below 0.5;
R_deranged a non-robust near tie). Under the prereg `verdict_label_rules`, "R controls match A" →

### VERDICT: `RANDOM_OR_SCRAMBLED_MATCHES` (robust)

Adjacent labels considered and why this one: `DOMAIN_RESONANCE_MATCHES` ("A ties R_domain") understates the
result — A does not merely tie R_domain, it **loses** (0.460); `DERANGED_RESONANCE_MATCHES` ("A ties
R_deranged") captures only the crux; `NOT_ROBUST` describes the R_deranged near-tie but not the outright
R_domain/R_same failures. The umbrella label **`RANDOM_OR_SCRAMBLED_MATCHES`** ("R controls match A") is the
faithful summary: every strong symbolic control matches or beats A, and scrambling A's own varṇa order (S)
costs nothing. This matches the B1 verdict and the scorer's locked output.

**`LIMITED_GENERATION_UTILITY` is NOT earned** — the positive label requires A to beat R_deranged AND
R_domain AND R_same (multiplicity-corrected, no unacceptable correctness degradation), and it does not.

## 8. No-rescue clause

This null **cannot** be reinterpreted as an ontology signal, a partial/hidden success, or grounds to unblock
Track B (`no_rescue`, `b1_1_scorer_config.json`). Beating the sparse/surface/neutral/dictionary controls
(C/X/D) is **not** the preregistered success criterion and does **not** establish word-fit — moving the
goalposts from the R controls to the C/X wins is explicitly disallowed. No judge may be excluded because the
result is negative. No lexicon may be tweaked post-hoc. The theory-application and R_deranged control-validity
reviews identify targets for a **future, separately preregistered** B1.2; they do **not** alter this result.

## 9. Verdict anchor / final status block

```
document:                   B1.1 FINAL scoring and verdict (LOCK; consolidation, nothing rerun)
reran judges / scoring:     NO
judge panel changed:        NO (all 3 kept; 0 attention fails; exclusion rule did not trigger)
post-hoc judge exclusion:   NONE
primary success:            NOT MET (A fails R_deranged, R_domain, R_same)
  A_vs_R_deranged:          0.516  (near tie; CI straddles 0.5; not robust)
  A_vs_R_domain:            0.460  (A loses)
  A_vs_R_same:              0.471  (A ties/loses)
secondary (necessary only): A_vs_C 0.694 · A_vs_X 0.581 · A_vs_D 0.548 · A_vs_S 0.497 (tie)
B1.1 VERDICT:               RANDOM_OR_SCRAMBLED_MATCHES (robust)
LIMITED_GENERATION_UTILITY: NOT earned
B1 verdict:                 RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:                    BLOCKED
Track G negative:           RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F negative:           CORRECTNESS_DEGRADED — preserved
ontology validation:        NONE
Sanskrit privilege:         NONE
semantic-truth claim:       NONE
future work:                requires new prereg + new freeze (B1.1 not reusable as a positive prior)
```

**Structure, not validated meaning.** B1.1 is locked: the revised, corrected, blinded contrastive design did
not rescue H2. A helps generation only generically (vs sparse/surface/neutral controls) and carries no
measurable word-specific varṇa-fit advantage over strong symbolic controls. The verdict is
`RANDOM_OR_SCRAMBLED_MATCHES`, `LIMITED_GENERATION_UTILITY` is not earned, Track B remains BLOCKED, and the
prior negatives (Track G, Track F) stand.
