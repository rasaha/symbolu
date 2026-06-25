# Results — archetype-alignment test (the "missing middle")

> Pre-registration: `PREREG_ARCHETYPE_SIGNAL.md`. Verdict computed by the registered rule, not by hand.
> This is a **separate hypothesis** from the lexical NO_SIGNAL and the utility NO_UTILITY_SIGNAL
> results; this result does **not** revive either of them. Interpretive lens — **not** part of C×R×S.

## The hypothesis tested

Not "can the chain identify the word *doctor*?" (already falsified — lexical NO_SIGNAL) but the
**missing-middle / Sattvic** claim: *does the real varṇa chain depict a role-word's archetypal
**transformation** (doctor: suffering → healing) better than a scrambled lexicon **and** a random
symbolic lexicon, judged blind?*

- **N = 30** role/function words, each with a pre-registered `from → to` archetype authored from the
  role alone (`wordlist_archetype.py`), before any chain was computed.
- For each word, the lens reading rendered as a lexicon-agnostic transformation **arc** (identical
  template across lexicons; only glosses differ).
- **Three lexicons:** **real** (Sanskrit varṇa map), **scrambled** (real (worldly,counter) pairs
  permuted among consonants; vowel essences permuted among vowels — same vocabulary, randomized
  sound→propensity attachment), **random-symbolic** (same arc structure from a neutral, concrete-noun
  pool). S = 20 seeded control lexicons, averaged.
- Required gate: **ARCHETYPE_SIGNAL_DETECTED only if real beats BOTH controls** — CI_lower(Δ_scr) > 0
  **and** CI_lower(Δ_rnd) > 0 (and ≥ MIN_EFFECT = 0.30 for product-meaningfulness).

## Confirmatory arm — 5 blind LLM judges (within-item, hidden lexicon identity, randomized slot order)

Each judge saw the archetype `from → to` and the three chains unlabeled, and scored each chain's fit
1–5. Per-word scores averaged over the 5 judges; bootstrap CI (10 000 resamples) over the 30 words.

| arm | fit (1–5) |
|---|---|
| **real** | **2.987** |
| scrambled | 2.947 |
| random-symbolic | 1.767 |

- **Δ_scr = real − scrambled = +0.040**  (95% CI **−0.233 … +0.313** — contains 0)
- **Δ_rnd = real − random   = +1.220**  (95% CI **+0.88 … +1.54** — excludes 0)

### VERDICT: **NO_ARCHETYPE_SIGNAL**

Per the pre-registered rule, detection requires real to beat **both** controls. Real does **not** beat
scrambled (Δ_scr CI straddles 0). It beats only the random-symbolic control. → NO_ARCHETYPE_SIGNAL.

## Supporting arms (all agree)

| judge | Δ_scr (real − scrambled) | Δ_rnd (real − random) | verdict |
|---|---|---|---|
| **LLM** (5 blind judges) | +0.040  (CI −0.233 … +0.313) | +1.220 (CI +0.88 … +1.54) | **NO_ARCHETYPE_SIGNAL** |
| wordnet (deterministic semantic) | +0.018  (CI −0.019 … +0.057) | +0.388 (CI +0.258 … +0.511) | **NO_ARCHETYPE_SIGNAL** |
| overlap (deterministic literal) | +0.002  (CI −0.009 … +0.017) | +0.009 (CI +0.000 … +0.027) | **NO_ARCHETYPE_SIGNAL** |
| random (null) | +0.147  (CI −0.240 … +0.533) | +0.122 (CI −0.240 … +0.480) | **NO_ARCHETYPE_SIGNAL** |

Every arm shows the **same signature**: real ≈ scrambled, both > random-symbolic. The order-shuffled
real arm ≈ real (wordnet 3.266 vs 3.259), so the (non-)effect doesn't even require the *ordered* chain.

## Why this is a clean falsification, not a near-miss

The two deltas dissociate the two things that could drive "fit":

1. **Δ_scr ≈ 0 (real vs scrambled).** Scrambled keeps the *entire* propensity vocabulary and arc
   structure and only randomizes **which sound carries which propensity** — exactly the acoustic claim.
   Real is statistically indistinguishable from scrambled. **The specific sound→propensity attachment
   carries no archetypal signal.** This is the decisive bar, and it fails.
2. **Δ_rnd ≈ +1.2 (real vs random-symbolic).** The only large effect is real (and scrambled) beating
   *neutral concrete nouns*. That is a **vocabulary** effect — psychological-transformation words
   ("Cruelty into Compassion," "Hope," "Detachment") read as transformations far more readily than
   "canister into north." It is **not** an acoustic effect: a scrambled Sanskrit map wins by the same
   margin. Beating random while tying scrambled is the textbook signature of "the vocabulary helps,
   the sound-mapping does not."

Per-domain Δ_scr (LLM arm) scatters around zero with no consistent sign (knowledge +0.73, craft +0.32,
order −0.32, protection −0.45, spirit −0.47), consistent with noise rather than a real per-domain
acoustic signal. Position bias was modest (mean by displayed slot 2.59 / 2.83 / 2.28) and cannot
explain the result: the random-symbolic arm scores lowest in every slot, and the within-item design
plus balanced trio order cancel slot effects in Δ.

## Interpretation (binding, per prereg)

**NO_ARCHETYPE_SIGNAL → the Sanskrit acoustic model adds no measurable Sattvic / archetypal-function
signal.** The "missing middle" — that sound recovers a word's deeper transformation even though it
can't recover its dictionary meaning — is **not** supported. Apparent archetypal aptness is supplied
by (a) the reader/judge and (b) the *choice to use evocative psychological vocabulary at all*, neither
of which is the sound→propensity map the lens claims as its mechanism.

This is consistent with, and independent of, the two prior falsifications (lexical NO_SIGNAL, utility
NO_UTILITY_SIGNAL). Varṇa Lens remains a **consistent symbolic mirror** whose value is reflective and
reader-supplied, not veridical. The `phoneme_overreach` firewall to C×R×S / Conscious Generation
stands — there is still nothing veridical to transfer.

## What a (hypothetical) positive would and would not have licensed

Even ARCHETYPE_SIGNAL_DETECTED would have licensed only: *"the real chain depicted pre-registered
archetypal transformations better than scrambled and random controls in a blind fit test"* — never
dictionary-meaning recovery, never a quality/semantic score, never a C×R×S feature. The result is
moot: the test returned NO_ARCHETYPE_SIGNAL.

## Reproducibility

```
python archetype_test.py --judge random     # null  → Δ CIs straddle 0
python archetype_test.py --judge overlap     # literal-overlap deterministic
python archetype_test.py --judge wordnet     # semantic deterministic
python archetype_test.py --emit              # blind LLM items + key (confirmatory arm)
```
Fixed seeds (`BASE_SEED = 20240624`, S = 20). The 5 blind-judge score sheets and the slot→arm key are
archived alongside this run; `archetype_test.score_items(judges, key)` recomputes the LLM verdict.
