# Results — acoustic-signal test, CORRECTED-LEXICON re-run

> **This is the corrected-lexicon run.** Same pre-registered harness, thresholds, wordlist, judge protocol,
> and metric as `RESULTS_ACOUSTIC_SIGNAL.md` — only the lexicon changed (8 source-corrected entries). The
> prior NO_SIGNAL stays attached to the pre-correction lexicon and is **not** merged with this result.

## Run identity
- **Lexicon version / commit:** `38e38d3` ("Correct varna lexicon source alignment for selected letters")
- **Entries:** 34 consonants + 12 vowels
- **Corrected letters:** Ca, Ja, Ma, Ra, Va, Śa, Ṣa, Sa
- **Test:** `varna_lens/signal_test.py` item generation (frozen rule, K=5, valence-matched forced choice,
  pooled real + 2 seeded scrambles) → blind LLM judges (sub-agents, never see the word/arm) → score by the
  pre-registered rule. Same wordlist (127 words), same seeds, same metric. (Deterministic `--judge
  wordnet`/`llm` need corpus/API absent in this sandbox; the LLM-judge arm was run via blind sub-agents, as
  in the original confirmatory run.)

## PRIMARY VERDICT (recorded before any explanatory analysis)

| metric | value |
|---|---|
| accuracy(real) | **0.173**  (95% CI 0.110–0.244) |
| accuracy(scrambled, avg 2 seeds) | 0.280 |
| chance (1/K) | 0.200 |
| **Δ = real − scrambled** | **−0.106**  (95% bootstrap CI **−0.185 … −0.028**) |

### VERDICT: **NO_SIGNAL**
The SIGNAL_PRESENT gate (CI_lower(Δ) > 0 **and** CI_lower(acc_real) > 0.20) fails on both clauses: real sits
at chance and **Δ is significantly negative** — real did *worse* than a scrambled lexicon. This is the
absence of signal. (Note: the literal 3-way rule emits the catch-all "INCONCLUSIVE" only because Δ's CI
excludes 0 *on the negative side* — an outcome the rule didn't carve out; substantively it is the strongest
form of NO_SIGNAL, the opposite of a positive result. No signal is claimed.)

acc(real) by language: sa 0.219, ja 0.167, ur 0.167, en 0.111, zh 0.000. Even Sanskrit (home turf) is at
chance.

## Comparison vs old pre-correction lexicon

| | acc(real) | acc(scrambled) | Δ (95% CI) | verdict |
|---|---|---|---|---|
| **old (pre-correction)** | 0.205 | 0.260 | −0.055 (−0.142 … +0.031) | NO_SIGNAL |
| **corrected (`38e38d3`)** | 0.173 | 0.280 | −0.106 (−0.185 … −0.028) | NO_SIGNAL |

The source correction did **not** produce acoustic signal. Real remains at chance and, if anything, scored
slightly lower than before (the corrected entries add more abstract/duplicated glosses — e.g. Viveka now on
both Ca and Na, Adharma, Ahaṁkāra — which the blind judge maps to meaning no better, and here slightly
worse, than random reassignments). **trend: none toward signal.**

## Interpretation
The corrected source-aligned lexicon improved textual fidelity but did **not** produce measurable acoustic
signal under the pre-registered test. The lexical sound→meaning claim remains unsupported for the corrected
lexicon, just as for the old one — each result attached to its own lexicon version.
