# B1.2 Mapping-Fidelity Proposal (proposal only — not authorized, not run)

## 1. Scope and the non-rescue rule

This document **proposes** a genuinely different follow-up study, B1.2, focused on **mapping fidelity**, not
generation utility. It is a **proposal only**. It does **not**:

- implement, run, generate, judge, or score anything;
- modify any frozen B1.1 artifact or the freeze manifest;
- modify any source lexicon in `varna_lens/`;
- alter the B1.1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`) or the B1 verdict;
- reuse the B1.1 result as a positive prior;
- unblock Track B (**BLOCKED**);
- claim ontology validation, Sanskrit privilege, or semantic truth.

**Non-rescue rule.** B1.2 is **not** a second attempt to make the *generation-utility* hypothesis pass. That
question was answered (B1.1: A did not beat the strong R controls). B1.2 asks a **different, narrower**
question and can only earn a **different, narrower** label. A null in B1.1 stays a null. Nothing in B1.2 —
positive or negative — reaches back and changes B1.1. Any B1.2 needs its **own** prereg and its **own**
freeze. **Structure, not validated meaning.**

## 2. Why generation utility failed in B1.1

B1.1 gave A (the word's own varṇa bridge) a fair, contrastive, blinded test against seven controls. The
outcome:

- A **beat** the weak controls — surface facts (C, 0.694), neutral filler (X, 0.581), and a bare dictionary
  gloss (D, 0.548 aggregate). Richer coherent conditioning does help open generation.
- A **did not beat** the strong controls — R_deranged (another word's *real* mapping, 0.516, a near tie),
  R_domain (a mismatched-domain real bridge, 0.460, A *loses*), R_same (same-pool random real phrases,
  0.471, A ties/loses). A **tied** scrambled (S, 0.497).

The lesson: **generic symbolic resonance was enough.** Any fluent, coherent, real bridge conditions open
creative tasks about as well as the word's own bridge. The word→mapping *fit* carried no measurable
generative advantage; the crux control (R_deranged) came back a coin flip. **Therefore B1.2 must not run
another open generation task.** Re-running "B1.1 with nicer prose" would only re-measure the same
generic-resonance effect and would not test fit. The failure was not prose quality; it was that open
generation does not force a *wrong* mapping to visibly fail.

## 3. The new research question

> **Under blinded conditions, can the *correct* word→bridge mapping be distinguished from *wrong but equally
> fluent* mappings?**

This is **mapping fidelity**, not generation utility. It does not ask "does A help generation." It asks "is
there recoverable, word-specific information in A that a discriminating task can detect and that a wrong-but-
fluent bridge does not carry." A discriminative task — not open creative writing — is the only way to make a
wrong mapping *fail* rather than merely *read differently*.

## 4. What B1.2 can and cannot prove

**Can (at most):**

- Whether, **within the frozen Symbol-U system**, the word's own bridge is distinguishable from wrong-but-
  fluent bridges under blinded discrimination — i.e. **mapping-fidelity within the system's own terms.**

**Cannot (must not be claimed, even on a positive):**

- that the Symbol-U ontology is validated;
- that Sanskrit/varṇa mappings are privileged, correct, or true;
- that phonemes carry semantic meaning;
- anything about Track B (stays **BLOCKED** regardless of outcome);
- generation utility (that was B1.1's question and it failed).

A positive B1.2 would show only that the system encodes *some* internally-recoverable word-specific
structure — **discriminability, not truth.** **Structure, not validated meaning.**

## 5. Discriminative task design

Replace open creative generation with tasks where a **wrong mapping should visibly fail**. Candidate task
families (a frozen B1.2 would pick a small, pre-specified subset):

- **T-match — best-fit selection.** Present the target word and 4–6 candidate bridges (one correct A, the
  rest wrong-but-fluent real bridges from the controls). Task: pick the bridge that best fits the word.
  Score = correct-selection rate vs chance.
- **T-word — reverse selection.** Present one bridge and 4–6 candidate words; pick the word the bridge
  belongs to. Guards against the model latching onto bridge surface features alone.
- **T-rank — full ranking.** Rank all candidate bridges by fit to the word; score by rank of the correct
  bridge (e.g. mean reciprocal rank).
- **T-odd — deranged detection.** Given the word and a single bridge, decide "is this the word's own mapping
  or another word's mapping?" (correct A vs R_deranged, balanced). Directly targets the crux.
- **T-pair — forced-choice correct-vs-wrong.** Two bridges (correct A vs one wrong-but-real), blinded
  order; pick the better fit. A-win rate vs 0.5.

All tasks are **forced-choice / constraint-satisfaction**, so a wrong mapping can be *scored wrong*, unlike
open prose where it merely reads differently. Bridges are presented **without** varṇa labels or any mapping
metadata (METADATA_ONLY boundary, as in B1.1).

## 6. Arms

The discriminative candidate set per item is drawn from these arms (correct vs wrong-but-fluent):

- **A_correct** — the word's own frozen A bridge (the target).
- **R_deranged** — another word's *real* A bridge (the crux wrong mapping; must be the hardest distractor).
- **R_same** — same-pool random real phrases, count-matched (fluent wrong mapping, no domain signal).
- **R_domain** — a fluent real bridge from a mismatched domain bucket (wrong mapping, different framing).
- **Generic_symbolic** — a high-quality **non-varṇa** symbolic/evocative bridge (baseline: is any resonant
  prose distinguishable, or specifically the varṇa one?).
- **Dictionary** — a plain dictionary gloss (weak-distractor floor / sanity anchor).

A_correct is the only "right" answer; every other arm is a fluent, plausible distractor.

## 7. Strong-control rules (the integrity core)

The study is only meaningful if the **wrong** bridges are genuinely hard to reject:

- Every distractor must be **fluent, real, coherent, and plausible** — no ugly, nonsense, or truncated
  bridges to make A_correct look good. (B1.1 forensic §6 forbids weakening controls.)
- **R_deranged is the crux.** It is another word's *real* mapping and must be length/style-matched to
  A_correct. If A_correct cannot beat R_deranged, there is no mapping-fidelity signal — full stop.
- Distractors must be **length-, register-, and pole-structure-matched** to A_correct so the discriminator
  cannot win on surface form (length, ornateness, number of clauses) instead of fit.
- **No varṇa labels, no Sanskrit terms, no mapping metadata** in any presented bridge (the leakage that B1.1
  caught — `artha`, `Viveka` — must be pre-scanned out with **real G2P**, not illustrative spelling).
- Distractor assignment is **seeded and frozen** (derangement seed, same-pool seed, domain-bucket map) so
  the "wrong" set cannot be hand-curated after seeing results.

## 8. Scoring

- **Primary (mapping-fidelity):** A_correct is chosen / ranked-first **above every strong wrong control**
  — specifically above **R_deranged AND R_domain AND R_same** — at a rate whose word-clustered CI lower
  bound exceeds chance (chance = 1/k for k-way selection; 0.5 for pairwise/odd-one-out).
- **Ranking accuracy:** mean reciprocal rank (or correct-in-top-1 rate) of A_correct across items, vs the
  chance baseline for the candidate-set size.
- **Pairwise A-win:** for T-pair / T-odd, A_correct-win rate vs 0.5 (the B1.1 metric, but now on a
  discriminative task).
- **Calibration vs chance:** every metric reported against its explicit chance floor; "above chance" is the
  bar, not "above the weak controls."
- **Clustering:** **word-clustered** paired bootstrap CIs (item = word), as in B1.1, so per-word
  idiosyncrasy is not counted as independent evidence.
- **Multiplicity:** Holm–Bonferroni across all co-primary comparisons and tasks (as in B1.1's 7-way
  correction).
- **Sensitivities (pre-specified):** drop-each-judge, drop-parse-fail, drop-repaired — the result must
  survive all, as B1.1 required.

## 9. Success criterion (and the only allowed positive label)

**Success** = A_correct beats **R_deranged AND R_domain AND R_same** on the primary discriminative task,
each corrected CI lower bound above the task's chance floor, surviving Holm correction and **all**
pre-specified sensitivities (robust across judges).

The **only** positive label B1.2 may earn is **`MAPPING_FIDELITY_SIGNAL`** — "within the frozen Symbol-U
system, the word's own bridge is blind-distinguishable from wrong-but-fluent bridges." It may **not** be
labeled `LIMITED_GENERATION_UTILITY` (that is B1.1's question and it failed), and it may **not** be escalated
to ontology validation, Sanskrit privilege, semantic truth, or a Track-B unblock. A B1.2 positive is a
**discriminability** claim, nothing more.

## 10. Kill criteria

B1.2 is **killed** (mapping-fidelity **not** supported) if any of:

- A_correct does **not** beat R_deranged (the crux) with a chance-exceeding corrected CI; **or**
- A_correct fails to beat R_domain **or** R_same; **or**
- the result does not survive Holm correction or any pre-specified sensitivity; **or**
- discrimination sits at the chance floor (the discriminator cannot tell correct from wrong).

A kill is **final for B1.2** and, combined with B1.1, would indicate the varṇa mapping carries no
blind-recoverable word-specific signal in either generation or discrimination. **No rescue language, no
"the judges failed to understand," no post-hoc control weakening, no goalpost move to the weak controls.**

## 11. Word-pool options

- **Option A — English G2P pool (as B1.1).** Same 25-word broad English set via G2P→varṇa. *Weakness:*
  English phonology→varṇa is lossy (forensic §4C); if the decomposition itself is noisy, even a real
  fidelity signal may be undetectable. Most comparable to B1.1; weakest stimulus.
- **Option B — small hand-audited English set (recommended for a first B1.2).** A **small** set of English
  words whose varṇa decomposition is manually verified stable and unambiguous, distractors hand-checked for
  fluency and non-synonymy. *Strength:* removes the G2P-noise confound without changing the language.
  *Risk:* small-N; must pre-register the set and freeze it before any peek (§12 handpicking risk).
- **Option C — Sanskrit / IAST exact-varṇa pool.** Words given directly in IAST so the varṇa sequence is
  **exact**, not G2P-approximated. *Important:* this is a **new and different question** ("does the mapping
  work when the varṇa sequence is exact"), **not** a fix to B1.1 and **not** a claim that Sanskrit is
  privileged. It removes the lossy-G2P confound but introduces Sanskrit-leakage risk and a scope change;
  it must be framed as its own hypothesis, not a rescue.

## 12. Risks

- **Overfitting after a failure.** The single biggest risk: designing B1.2 to pass because B1.1 failed.
  Mitigated only by a fresh prereg/freeze, seeded distractors, and pre-committed success/kill thresholds.
- **Generic-prose contamination.** If distractors are not length/register/pole-matched, the discriminator
  wins on surface form, not fit — a false positive. Strong-control rules (§7) are mandatory.
- **Style inference, not fit.** A judge may pick the "more ornate / more on-theme-sounding" bridge rather
  than the *correct* one; the Generic_symbolic arm exists to detect this (if generic resonant prose is
  chosen as often as A_correct, the signal is style, not mapping).
- **Sanskrit / label leakage.** Any varṇa term, Sanskrit word, or mapping metadata in a presented bridge
  leaks the answer (cf. `artha`); a **real-G2P** leak pre-scan is required, not illustrative spelling.
- **Handpicked-word bias.** A hand-audited pool (Option B) risks cherry-picking easy words; the set must be
  frozen and justified before any result is seen.
- **Weak-control drift.** The R controls must stay strong. Any temptation to make distractors easier
  (uglier, shorter, off-topic) invalidates the test — this is the B1.1 §6 failure mode.

## 13. Recommended path

Two honest options; **one open generation re-run is not among them.**

- **Option 1 — Stop the generation/varṇa-utility line.** B1 and B1.1 both returned nulls; Track G returned
  `RANDOM_POLARITY_EXPLAINS`. The accumulated evidence is that the varṇa mapping carries no
  blind-recoverable, word-specific *generative* advantage. Closing the line and recording the negative is a
  fully defensible outcome and arguably the highest-integrity move.
- **Option 2 — Run exactly one mapping-fidelity B1.2** with a **small hand-audited English pool (Option B)**,
  a **discriminative** task (T-odd + T-pair against a **strong, length-matched R_deranged** as the crux),
  strong-control rules enforced, and `MAPPING_FIDELITY_SIGNAL` as the only reachable positive.

**Do NOT** run "B1.1 with nicer prose," do not re-open the generation task, and do not run B1.2 as a way to
relitigate B1.1. If Option 2 is chosen, it stands or falls on its own new prereg and freeze.

**Recommendation:** default to **Option 1** unless there is specific appetite to answer the *distinct*
mapping-fidelity question; if so, **Option 2** as scoped above, once and rigorously.

## 14. Final status block

```
document:                  B1.2 mapping-fidelity PROPOSAL (design only; not authorized, not run)
implements/runs anything:  NO
B1.1 verdict:              UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1 verdict:                RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
B1.1 positive earned:      NONE (LIMITED_GENERATION_UTILITY not earned)
new question:              mapping fidelity (correct vs wrong-but-fluent, blinded discrimination)
only allowed positive:     MAPPING_FIDELITY_SIGNAL (discriminability within the system; NOT utility)
requires:                  new prereg + new freeze (B1.1 not reusable as a positive prior)
Track B:                   BLOCKED (a B1.2 positive would NOT unblock it)
Track G negative:          RANDOM_POLARITY_EXPLAINS (1fe5562; A_vs_R -0.1917, A_vs_X -0.075) — preserved
Track F negative:          CORRECTNESS_DEGRADED — preserved
ontology validation:       NONE
Sanskrit privilege:        NONE
semantic-truth claim:      NONE
```

**Structure, not validated meaning.** This is a proposal for a *different* question; the B1.1 verdict stands,
no result is rescued, Track B remains BLOCKED, and any B1.2 requires its own preregistration and freeze.
