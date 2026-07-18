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

---

## Deterministic-judge re-run (post binding/liberating rename) — 2026-06-25

> Reproducible re-run of the **same** pre-registered harness (`signal_test.py`, K=5, 127 words, valence-
> matched forced choice, N_SCRAMBLE=20 seeded scrambles, N_BOOT=10000) on the current lexicon after the
> `positive/negative → liberating_state/binding_state` ontology rename. The rename was byte-identical to the
> engine reading (0/42 golden mismatches), so this also confirms the rename did not perturb the test. Uses
> the **deterministic CPU judges** (`random`, `wordnet`) — fully reproducible, no API/sub-agent needed — and
> so is a distinct, independently-checkable judge arm from the LLM-sub-agent run above.

- **Lexicon / commit:** `c326bc1` (corrected entries Ca, Ja, Ma, Ra, Va, Śa, Ṣa, Sa; states renamed). 34 consonants + 12 vowels.
- **Confirmatory LLM judge:** not run here (no `ANTHROPIC_API_KEY` in this environment); covered by the sub-agent arm above.

| judge | accuracy(real) | accuracy(scrambled, 20 seeds) | order-shuffled | Δ = real − scrambled (95% CI) | rule verdict |
|---|---|---|---|---|---|
| `random` (null baseline) | 0.181 (CI 0.118–0.252) | 0.181 | 0.181 | −0.000 (−0.000 … −0.000) | null behaves: real ≡ scrambled, at chance |
| **`wordnet`** (deterministic semantic) | **0.213** (CI 0.142–0.283) | 0.215 | 0.213 | **−0.003 (−0.067 … +0.062)** | **NO_SIGNAL** |

acc(real) by language (wordnet): en 0.250, sa 0.233, ja 0.167, ur 0.000, zh 0.000. Sanskrit (home turf) sits at chance.

### VERDICT: **NO_SIGNAL** (reproduced)
The SIGNAL_DETECTED gate (`CI_lower(Δ) > 0` **and** `CI_lower(acc_real) > 0.20`) fails on both clauses: real
sits at chance and Δ's CI brackets 0. The `random` null arm confirms no machinery leakage (real ≡ scrambled,
Δ = 0 to floating-point). **acc(real) ≈ acc(scrambled) ≈ acc(order-shuffled) ≈ chance** — neither the lexicon
mapping nor phoneme order recovers meaning.

This is exactly the **relabeling-invariance** prediction: a gloss-blind / token-identity recovery score is
invariant under permuting the lexicon, so real ≡ scrambled is the degenerate expectation, and only true
gloss-semantics could break the tie — which it does not. The corrected, source-aligned, renamed lexicon
remains **without recoverable sound→meaning signal**; the falsification stands across both the LLM-sub-agent
and the deterministic-judge arms.
