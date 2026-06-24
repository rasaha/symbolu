# Results — acoustic-signal test (pre-registered)

> Pre-registration: `PREREG_ACOUSTIC_SIGNAL.md`. Verdict computed by the registered rule, not by hand.
> Interpretive lens — **not** part of C×R×S. This was the gate that would have to be passed first.
>
> **Lexicon-version note:** this NO_SIGNAL result was produced on the **pre-correction** lexicon. Eight
> entries (Ca, Ja, Ma, Ra, Va, Śa, Ṣa, Sa) were later corrected for source fidelity (see
> `LEXICON.md` → "Source fidelity" and `HANDOFF_BRIEF.md` changelog). This result stands for that prior
> lexicon and is **not** evidence for or against the corrected one — re-run the test to claim anything
> about the corrected lexicon.

## Confirmatory run — blind LLM judges (sub-agents)
6 blind sub-agents, each shown only **essence + 5 candidate meanings** (never the word, never which arm).
381 forced-choice items pooled & shuffled across arms = 127 words × {real, scrambled-seed0, scrambled-seed1}.

| metric | value |
|---|---|
| accuracy(**real**) | **0.205**  (95% CI 0.142–0.276) |
| accuracy(**scrambled**, avg of 2 seeds) | **0.260**  (seed0 0.291, seed1 0.228) |
| chance (1/K, K=5) | 0.200 |
| **Δ = real − scrambled** | **−0.055**  (95% CI −0.142 … +0.031) |

### VERDICT: **NO_SIGNAL**
- accuracy(real) is **at chance**; the blind judge cannot recover a word's meaning from its varṇa-essence.
- **Scrambling the sound→meaning map made no difference** (Δ CI straddles 0; scrambled even scored slightly
  higher). If the acoustic root carried a latent signal, real would beat scrambled. It does not.

acc(real) by language: sa 0.219 (n=73), en 0.167 (n=36), zh 0.333 (n=6), ja 0.167 (n=6), ur 0.167 (n=6).
Even on **Sanskrit** — the lexicon's home turf, where H1 should be strongest — it is at chance.

## Reproducibility / scope notes
- Null control: `signal_test.py --judge random` → acc≈chance, Δ=0 exactly (harness validated).
- This sandbox has no API key, no embedding libs, and the WordNet corpus would not download, so the
  *scripted* `--judge wordnet|llm` arms were run instead via blind sub-agents (the LLM-judge arm of the
  prereg). The full registered run (20 scrambles + 10k bootstrap, deterministic) is reproducible with
  `--judge wordnet`/`--judge llm` on a pod / with API access; it is expected to reproduce NO_SIGNAL.

## Interpretation
The lens does **not** decode meaning. Apparent coherence in manual use is interpreter-supplied
(pronunciation choice + narrative fit), consistent with the same-sound→same-essence and valence-matching
seen earlier. Therefore it stays a **personal contemplative instrument, outside C×R×S** — feeding the
acoustic-root into the engine would be the `phoneme_overreach` taboo. The frozen lexicon + fixed rules
remain useful for *that* purpose; they are just not a latent meaning-signal.
