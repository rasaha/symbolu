# Pre-registration — Does the varṇa lexicon have NON-LEXICAL utility signal?

> **Status: PRE-REGISTERED (written before results).** Second, independent falsification for `varna_lens`.
> The first test (`PREREG_ACOUSTIC_SIGNAL.md` → `RESULTS_ACOUSTIC_SIGNAL.md`) returned **NO_SIGNAL**: the
> frozen lexicon does **not** decode lexical/dictionary meaning. That result is accepted and not relitigated
> here. This test asks a *different, narrower* question and must pass its own scrambled-control bar before
> any product claim is made. This is still **not** about C×R×S / Conscious Generation, and a positive result
> here would **not** revive the lexical claim.

## The question
Even though Varṇa Lens does not decode meaning, does the **real** lexicon produce **more useful
contemplative / creative / naming / affective artifacts** than a **scrambled** lexicon — same word, same
rule, same template, judged blind?

- **H1 (utility):** real-lexicon artifacts score higher on blind utility than scrambled-lexicon artifacts.
- **H0 (no utility):** real ≈ scrambled; any value is generic (template + the lexicon's general richness),
  not in the specific sound→propensity attachment.

## Design — paired real-vs-scrambled artifacts, blind judge
1. **Wordlist** (`wordlist_utility.py`): N ≥ 120 words across 5 categories (Sanskrit-spiritual, English
   everyday, company/product names, emotionally-loaded, neutral-control), each tagged with ONE `use_case`
   ∈ {journaling, naming, creative, affective}. **No target meaning** — this is not meaning-recovery.
2. **Mechanical artifact** (`utility_test.py`): for each word, render a short interpretive artifact in its
   use_case mode from the lens reading, with **non-claiming** language ("this reading invites…", "as a
   symbolic prompt…"; never "means / reveals / hidden essence / proves").
3. **Paired outputs:** A = real lexicon, B = scrambled lexicon — **identical template, tone, structure, and
   length**. Only the glosses filling the slots differ.
4. **Blind judge** scores each artifact (not knowing which is real) on six 1–5 Likert dims —
   coherence, depth, usefulness, specificity, non-generic, fit-to-use-case — and gives a pairwise
   preference (A / B / tie). Position (which is shown first) is randomized and recorded.
   - **Confirmatory: LLM judge** (blind sub-agents / API). Highest power.
   - **Parity/null arm: deterministic surface judge** (CPU) — scores measurable surface features only; its
     job is to confirm real and scrambled are **indistinguishable on formatting** (expected Δ≈0), so any LLM
     effect can't be a length/structure artifact.
   - **Random-null judge** → must show no systematic preference (~50%).

## Controls — scrambled lexicon
- `S = 20` seeded scrambles, averaged per word. **The scramble permutes the (worldly-pole, spiritual-counter)
  PAIRS as units** among consonant keys, and vowel essences among vowel keys. This **preserves**: antonym
  pairing, positive/negative field structure, the gloss multiset, and output length. It randomizes **only**
  the sound→propensity attachment. (Strongest control: real can win only if *which sound carries which
  propensity* matters for utility — not because the lexicon has nice pairs or a nice template.)

## Primary metric & pre-registered verdict
- **utility_score = mean(coherence, depth, usefulness, specificity, non_generic, fit)** per artifact.
- **Δ = utility_score(real) − utility_score(scrambled)**, 95% **bootstrap CI** (10 000 resamples over words).
- **Practical threshold:** `MIN_EFFECT = 0.30` points (on the 1–5 scale) — a difference smaller than this is
  not product-meaningful even if statistically nonzero.
- **UTILITY_SIGNAL_DETECTED** ⟺ CI_lower(Δ) > 0 **and** Δ ≥ MIN_EFFECT (corroborated by real-preference rate
  > 50% with CI excluding 50%).
- **NO_UTILITY_SIGNAL** ⟺ 95% CI(Δ) contains 0.
- **INCONCLUSIVE** ⟺ CI_lower(Δ) > 0 but Δ < MIN_EFFECT, or N/judge underpowered. → increase N, improve
  judge, or narrow to one use_case; do not productize.
- Secondary (reported, non-gating): per-use_case Δ, per-category Δ, pairwise-preference rate, surface-judge
  parity Δ (should be ≈0), random-null preference (should be ≈50%).

## Registered prediction (before running)
Given the scramble preserves the lexicon's richness, pairing, template, and length, and given the lexical
NO_SIGNAL, I predict **NO_UTILITY_SIGNAL**: artifact quality is dominated by the (identical) template, and
the only lever that could favor real is meaning-fit — which the first test already showed is null. Recording
this so I can be shown wrong.

## Interpretation rules (binding)
- **UTILITY_SIGNAL_DETECTED** → Varṇa Lens may be productized as a symbolic reflection / creativity tool.
  Allowed claim: *"the real lexicon produced measurably more useful reflective artifacts than scrambled
  controls in a blind utility test."* **Not** allowed: any claim that it decodes meaning; any link to C×R×S
  or Conscious Generation.
- **NO_UTILITY_SIGNAL** → treat Varṇa Lens as an aesthetic/random symbolic mirror; a toy / personal
  contemplative tool with **no special claim** about the real lexicon over a scrambled one.
- **INCONCLUSIVE** → no product claim yet.

## Reproducibility
Fixed seeds. `python utility_test.py --judge surface` and `--judge random` run CPU-only and deterministic.
`--judge llm` is the confirmatory arm (blind sub-agents / API). Results → `RESULTS_UTILITY_SIGNAL.md`;
verdict computed by the rule above, not by hand.
