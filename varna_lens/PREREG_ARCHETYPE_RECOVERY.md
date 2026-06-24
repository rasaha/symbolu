# Pre-registration — Archetype RECOVERY (forced-choice "absolute match")

> **Status: PRE-REGISTERED (written before judging).** Stricter re-test of the archetype hypothesis
> after `RESULTS_ARCHETYPE_SIGNAL.md` returned NO_ARCHETYPE_SIGNAL on a soft 1–5 fit rating. The
> critique answered here: a soft rating lets a reader *project* a fit onto any evocative chain. This
> test removes projection by requiring an **absolute match** — pick the one correct archetype from a
> lineup. Still **not** a meaning claim, still **not** part of C×R×S. A positive result would license
> only a narrow archetype-recovery claim and would not revive the lexical/utility results.
>
> **Multiple-testing note:** this is the 4th pre-registered probe of the lens. Re-testing until
> something passes inflates false-positive risk. Mitigation: fixed design, scrambled **and** random
> controls, an above-chance floor, and a verdict computed by rule. A single bare pass here is
> suggestive, not conclusive; confirmation would require a fresh word set + judges.

## The question
If the real sound→propensity map is an **absolute** match to a word's archetypal transformation, then
the **real** chain should let a blind judge **identify the word's own archetype** out of a lineup —
above chance, and better than a **scrambled** lexicon and a **random-symbolic** lexicon. A wrong
mapping (scrambled) should not recover the archetype; it should fall to chance.

## Design
- **Wordlist:** the same 30 role words with pre-authored `from → to` archetypes (`wordlist_archetype.py`).
- **Forced-choice lineup:** for each word, **K = 6** archetype options = the correct one + 5 decoys
  drawn from the other words' archetypes (seeded, fixed). **chance = 1/6 ≈ 0.167.**
- **Chains:** the lens reading rendered as the same lexicon-agnostic arc as the prior test, under
  three lexicons — **real**, **scrambled** (pairs permuted among consonants; essences among vowels —
  same vocabulary, wrong attachment), **random-symbolic** (neutral-noun pool). S = 20 seeded controls.
- **Task:** the blind judge sees ONLY a chain + the 6 options and picks the index. Right/wrong; no
  soft scale. Blind to which lexicon produced the chain.
  - **Confirmatory: LLM judges** (blind sub-agents), multiple per arm, accuracy averaged per word.
  - **Null arm: `random`** → must land at chance.
  - **Deterministic arm: `wordnet`** → reproducible semantic baseline.

## Metric & pre-registered verdict (computed by `archetype_recovery_test.py`)
- accuracy(real/scrambled/random) = fraction of words whose archetype is correctly recovered.
- Δ_scr = acc(real) − acc(scrambled); Δ_rnd = acc(real) − acc(random); 95% bootstrap CI over words.
- **ARCHETYPE_RECOVERY_SIGNAL** ⟺ CI_lower(acc_real) > chance **AND** CI_lower(Δ_scr) > 0 **AND**
  CI_lower(Δ_rnd) > 0. (Real beats the guessing floor *and* both controls.)
- **NO_ARCHETYPE_RECOVERY_SIGNAL** otherwise.

## Registered prediction (before judging)
Given three prior nulls and that scrambling preserves the whole vocabulary, I predict
**NO_ARCHETYPE_RECOVERY_SIGNAL** — real may edge the neutral-noun arm but will not clearly beat
scrambled, and may not clear chance. Recorded so the result can prove me wrong.

## Reproducibility
Fixed seeds (`BASE_SEED = 20240624`, K = 6, S = 20). `--judge random` / `--judge wordnet` are CPU
deterministic. `--emit real|scrambled|random` produces the blind LLM items; picks are archived and
`score_items` recomputes the verdict. Results → `RESULTS_ARCHETYPE_RECOVERY.md`.
