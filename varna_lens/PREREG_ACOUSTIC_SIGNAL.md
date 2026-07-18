# Pre-registration — Is the varṇa acoustic-root a real latent meaning-signal?

> **Status: PRE-REGISTERED (written before results).** This locks the design, metrics, thresholds, and the
> verdict mapping in advance, so a positive result can't be a post-hoc fit and a negative result can't be
> explained away. Filed for the `varna_lens` interpretive tool — still **not** part of C×R×S; this is the
> gate that would have to be passed *before* the signal could ever be considered for it.

## The question
The lens reads each sound's "worldly propensity" from a frozen lexicon. Across manual testing it *feels*
meaningful — but the interpreter (a human) picks the pronunciation and reads the narrative after seeing the
word. So we cannot yet distinguish:

- **H1 (signal):** acoustic roots carry a real latent meaning-signal — a word's varṇa-essence is
  predictive of its meaning, above chance and above controls.
- **H0 (projection):** there is no signal in the letters; apparent coherence is the interpreter supplying it.

## Design — blind, mechanical meaning-recovery + scrambled-lexicon control
1. **Wordlist** (`wordlist_signal.py`): N ≥ 120 words, each with (language, defensible **native**
   pronunciation, true meaning gloss, coarse valence). Primary subset = **Sanskrit** (the lexicon's home
   turf, where H1 should be strongest and pronunciation = IAST spelling). Secondary = English (g2p) and a
   cross-lingual probe (Japanese / Mandarin / Urdu-Persian), pinned to native phonetics.
2. **Mechanical essence:** for each word, compute the ordered worldly-propensity glosses with the **frozen
   rule, no human in the loop.** (Native pronunciation only — NOT the interpreter's preferred respelling.)
3. **Forced choice:** a **blind judge** that never sees the word or its sounds is shown the essence plus
   **K = 5** candidate meanings — the true one among 4 **valence-matched** distractors — and picks one.
   Chance = 1/K = 0.20.
4. **Controls (identical pipeline, same judge):**
   - **Scrambled lexicon** — randomly permute the sound→vṛtti map (S = 20 seeded scrambles, averaged). This
     is the key control: if the real lexicon carries signal, real ≫ scrambled.
   - **Order-shuffle** — shuffle each word's sounds before reading (tests whether the *order rule* adds
     anything beyond the bag of sounds). Secondary.
   - **Random judge** — a NULL judge that ignores the essence (validates that the harness returns chance).
5. **Judges (both compare real vs scrambled with the SAME judge, so judge quality cancels in the contrast):**
   - **Primary / confirmatory: LLM judge** (Claude, blind). Highest power.
   - **Reproducible arm: WordNet semantic-similarity judge** (deterministic, CPU, no GPU/API). Lower power —
     a null here is *suggestive* not decisive (a weak judge can miss a real signal); a real≫scrambled here
     is strong.

## Primary metric & pre-registered verdict
- **Δ = accuracy(real) − accuracy(scrambled)**, with a **95% bootstrap CI** (10 000 resamples over words).
- **SIGNAL_DETECTED** ⟺ CI_lower(Δ) > 0 **and** CI_lower(accuracy(real)) > 0.20 (chance).
- **NO_SIGNAL** ⟺ 95% CI(Δ) contains 0.
- **INCONCLUSIVE** ⟺ real > chance but Δ CI contains 0 with N too small (report and expand N).
- Secondary (reported, not gating): accuracy(real) − accuracy(order-shuffled); per-language breakdown;
  Sanskrit-only Δ (the strongest test of H1).

## My registered prediction (stated before running)
Given what informal testing already showed — **same sound → same essence regardless of language**, valence
co-movement, and the interpreter's own admission of force-fitting — I predict **real ≈ scrambled ≈ chance
(H0)**, most clearly on the cross-lingual set, and at best a small Sanskrit-only effect. Registering this so
I can be shown wrong.

## What a positive result would (and would not) mean for Conscious Generation
- **If SIGNAL_DETECTED:** the essence carries information. That earns it a *second* gate — a C×R×S-style
  **ablation**: does conditioning generation on the varṇa-essence beat a **scrambled-essence** control on a
  held-out objective? Only passing *that* would justify touching the engine.
- **If NO_SIGNAL:** the lens stays a personal contemplative instrument, **outside** C×R×S. Feeding it into
  the engine would be the `phoneme_overreach` taboo the firewall exists to prevent — meaning leaking from
  letters where it doesn't live.

## Reproducibility
Fixed seeds throughout. `python signal_test.py --judge wordnet` and `--judge random` run CPU-only and are
deterministic. `--judge llm` is the confirmatory run (needs API/pod). Results written to
`RESULTS_ACOUSTIC_SIGNAL.md`. The verdict is computed by the harness from the rule above, not by hand.
