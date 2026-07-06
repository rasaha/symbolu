# B1.1 Post-Result Forensic Report

## 1. Scope and non-rescue rule

This is **forensic analysis only**. It examines *why* B1.1 landed where it did and what a *future,
separately preregistered* study might do differently. It does **not**:

- alter the B1.1 verdict (`RANDOM_OR_SCRAMBLED_MATCHES`);
- reinterpret the failure as hidden or partial success;
- unblock Track B (**BLOCKED**);
- claim ontology validation, Sanskrit privilege, or semantic truth.

Every "improvement" below is a **hypothesis for a new study**, not evidence about the current result. Any
future attempt requires a **new prereg and a new freeze**; the B1.1 outcome may **not** be reused as a
positive prior. **Structure, not validated meaning.**

## 2. Result recap

**Primary controls (A-win; beat = corrected CI lower bound > 0.5):**

| comparison | AGG A-win | outcome |
|---|---|---|
| A vs R_deranged (crux) | **0.516** | not beaten — near tie; every judge's CI straddles 0.5 |
| A vs R_domain | **0.460** | not beaten — A *loses* |
| A vs R_same | **0.471** | not beaten — A ties/loses |

**Secondary controls:** A vs D **0.548**, A vs S **0.497**, A vs C **0.694**, A vs X **0.581**. A beats the
sparse/surface/neutral controls (C, X) and a bare dictionary gloss (D, on aggregate); A ties scrambled (S).

**Judge caveats (per-judge, all three kept, 0 attention fails):** Llama-3.1 had 382 unparseable verdicts
(~9%, forced to ties); Meta-Llama-3 needed missing-final-brace repair on ~2,420 verdicts (~58%, the B1
`ACCEPT_WITH_CAVEAT` concern realized); gemma-2-9b was cleanest (1 parse-fail, 0 repairs). The **cleanest
judge (gemma) was the most skeptical of A** (overall A-win 0.496, i.e. slightly *against* A), while the two
judges with quality caveats favored A (0.555, 0.563). The verdict is `robust` — it survives dropping
Meta-Llama-3 and dropping Llama's parse-fails.

**Final implication:** the primary success criterion is **not met**; `LIMITED_GENERATION_UTILITY` is **not
earned**; B1.1 does **not** establish H2-specific word-fit utility; B1's `RANDOM_OR_SCRAMBLED_MATCHES`
stands; Track G's `RANDOM_POLARITY_EXPLAINS` negative is preserved.

## 3. What the result most likely means

- **A's revised bridge is stylistically useful but not word-specific.** A reliably beats sparse/surface/
  neutral conditioning (C, X) and a plain dictionary gloss (D), so richer coherent conditioning does help
  generation — but that help is not tied to the *word's own* mapping.
- **Strong symbolic controls produce equal-or-better generations.** R_same, R_domain, R_deranged are all
  fluent, real, coherent bridges; A cannot separate itself from them.
- **R_domain beating A (0.460)** suggests broad symbolic framing can matter *more* than target-specific
  mapping — a mismatched-domain bridge was, if anything, generatively stronger.
- **R_same beating A (0.471)** suggests same-pool random bridge phrases remain generatively strong; drawing
  the "wrong" phrases from the same pool costs nothing.
- **R_deranged near tie (0.516)** means another word's *real* mapping is usually close enough — the crux
  control the whole B1.1 redesign was built around comes back a coin flip. That is the decisive signal:
  word→mapping fit carries no measurable generative advantage.

## 4. Possible limiting factors

*(Each is a candidate explanation, not a proven cause. Several may act together.)*

- **A. Bridge phrases may still be too generic.** Even after the rewrite, the binding/liberating phrases may
  describe broadly-applicable tendencies (release, restraint, clarity) that fit many words.
- **B. Binding/liberating polarity may be too broadly useful.** A two-pole "tendency + its sublimation"
  frame is evocative for almost any reflective prompt, diluting word-specificity.
- **C. Word→varṇa decomposition may be too lossy for English.** G2P→varṇa over English phonology is
  approximate; the varṇa sequence for an English word may not carry a stable, word-distinguishing signal.
- **D. Multi-varṇa composition may dilute signal.** Concatenating several varṇa bridges may blur any
  per-varṇa specificity into a generic multi-theme paragraph.
- **E. Tasks may reward evocative fluency over word-specific mapping.** T1/T3/T5/T6 (reflective paragraph,
  metaphor, tone-match, evoke) reward mood and richness, which any coherent bridge supplies.
- **F. Judge preference may reward style/coherence over mapping fidelity.** LLM judges compare "which reads
  better," not "which bridge belongs to this word" — and the pro-A lean was itself judge-dependent (gemma
  dissented on D/X), consistent with taste rather than fit.
- **G. R controls were intentionally strong and may have captured the same useful structure.** By design the
  R controls are real, fluent, length-matched bridges from the same pool — so they likely carry the same
  generic generative usefulness A has.
- **H. De-Sanskritization removed leakage but also removed distinctive source cues.** Fixing the `artha`
  leak (and earlier Ca/"Viveka") correctly removed confounds, but also stripped any idiosyncratic
  source-specific wording that might have made A's phrases more distinctive.
- **I. The embedding gate stayed blocked.** The real sentence-embedding non-synonym gate never ran
  (`FALLBACK_QUALIFIED`); the local lexical audit was surface-only, so deep paraphrase-synonymy between A
  and the controls could not be ruled out — the controls may be near-paraphrases of A.
- **J. The bridge encodes too few falsifiable word-specific constraints.** A's conditioning is soft, tonal
  guidance; it imposes little that a *wrong* mapping would visibly violate, so wrong mappings rarely fail.

## 5. What could have improved the result *(future-study hypotheses only)*

- **Sharper, more contrastive bridge phrases** with concrete operational constraints unique to each varṇa.
- **Stronger per-word grounding** established before generation (an explicit, checkable word→mapping link).
- **Avoid broadly-useful universals** (clarity, release, protection, purpose, knowledge) unless uniquely
  constrained to the target word.
- **Replace open creative tasks with discriminative tasks** where a *wrong* mapping should visibly fail
  (e.g. forced-choice, constraint-satisfaction, or "which bridge matches this word").
- **Add task-specific expected failure modes** for R_deranged / R_domain so a correct mapping is detectably
  better than a wrong one.
- **Use a smaller, hand-audited word set** where the varṇa decomposition is stable and meaningful, rather
  than a broad English pool.
- **Pre-run a real embedding / paraphrase-similarity gate** (now feasible on a model-access host) to prove
  A and the controls are non-synonymous before generating.
- **Add a human-blind qualitative rubric measuring word-fit specifically** — not beauty or style.
- **Separate creative-fluency scoring from mapping-fidelity scoring** so style gains cannot masquerade as
  fit.
- **Make the A mapping impose testable constraints the R controls should not satisfy.**
- **Freeze a clearer multi-varṇa composition grammar** (which varṇa, which pole, ordering, weighting).
- **Run ablations:** first-varṇa-only · all-varṇa sequence · weighted sequence · binding-only ·
  liberating-only · no-polarity bridge — to locate where (if anywhere) signal lives.
- **Compare directly against high-quality generic symbolic prompts** to quantify the generic-resonance
  baseline A must exceed.

## 6. What probably would NOT help *(and would compromise integrity)*

- Post-hoc lexicon tweaks after seeing the results.
- Excluding a judge *because* the result is negative (no post-hoc judge selection).
- Weakening the R controls, or making them ugly/nonsense so A looks better.
- Adding Sanskrit terms back (re-introducing the leakage that was correctly removed).
- Claiming the model or judges "failed to understand the ontology."
- Using creative-only tasks to inflate A.
- **Moving the goalposts** from the R controls to the C/X wins — beating sparse controls is not the
  preregistered success criterion and does not establish word-fit.

## 7. Design implication for a future B1.2

If a B1.2 is proposed, it must:

- have a **new prereg** and a **new freeze**;
- **not** reuse the B1.1 result as a positive prior;
- make an **explicit up-front decision on the goal**, because the three are different questions:
  - **(a) generation utility** — does A help generation at all (partly shown: yes vs sparse controls, no vs
    strong symbolic controls);
  - **(b) mapping-fidelity** — is the *word's own* mapping detectably better than a wrong one (the open,
    currently-unsupported question);
  - **(c) ontology testing** — which the **current evidence does not support** and which a generation study
    cannot establish;
- preserve **stronger, explicit kill criteria** (as B1/B1.1 did) so a null is again believable.

## 8. Recommended final wording

> B1.1 improved the experimental discipline and removed known leakage/confound paths, but the revised
> mapping did not beat strong random/domain controls. The result suggests that the observed gains are better
> explained by generic symbolic resonance or prompt style than by H2-specific word-fit. Future work would
> need sharper, more falsifiable mappings and tasks that penalize wrong mappings.

## 9. Final status block

```
document:                 B1.1 post-result FORENSIC report (analysis only)
verdict:                  UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
LIMITED_GENERATION_UTILITY: NOT earned
primary success:          NOT met (A fails R_domain, R_same; R_deranged a non-robust near-tie)
B1 verdict:               RANDOM_OR_SCRAMBLED_MATCHES (unchanged)
Track B:                  BLOCKED
Track G negative:         RANDOM_POLARITY_EXPLAINS (1fe5562) — preserved
ontology validation:      NONE
Sanskrit privilege:       NONE
semantic-truth claim:     NONE
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`; A_vs_R −0.1917, A_vs_X −0.075) · Track F
`CORRECTNESS_DEGRADED`. **`R_deranged` was the crux, and it came back a tie.**

**Structure, not validated meaning.** Forensic analysis only; the verdict stands, no rescue, Track B remains
BLOCKED, and any future improvement requires a new preregistered study.
