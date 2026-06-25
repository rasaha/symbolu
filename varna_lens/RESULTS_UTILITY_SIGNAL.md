# Results — non-lexical UTILITY test (pre-registered)

> **Layer boundary note** (see `LAYERS_ONTOLOGY_THEORY_IMPLEMENTATION.md`): automata / minimization claims
> classify the current ρ implementation only. They do not classify the completed acoustic ontology or future
> reading-theory variants. This result is an empirical falsification outcome and is untouched by that scoping.

> Pre-registration: `PREREG_UTILITY_SIGNAL.md`. Verdict computed by the registered rule, not by hand. This
> is a separate hypothesis from the lexical NO_SIGNAL result (`RESULTS_ACOUSTIC_SIGNAL.md`), and a positive
> result here would **not** revive the lexical claim. Interpretive lens — **not** part of C×R×S.
>
> **Lexicon-version note:** this INCONCLUSIVE result was produced on the **pre-correction** lexicon. The
> corrected-lexicon re-run is done (commit `38e38d3`) and returned **NO_UTILITY_SIGNAL** — see
> `RESULTS_UTILITY_SIGNAL_CORRECTED_LEXICON.md`. Keep the two archived separately; do not merge.

N = 124 words (one `use_case` each), K=2 paired comparison, scramble preserves antonym pairing / +/− field /
gloss multiset / output length. Practical threshold **MIN_EFFECT = 0.30** on the 1–5 utility scale.

## Control arms (deterministic, full S=20)
| judge | Δ = real − scrambled | 95% CI | real-pref | reads as |
|---|---|---|---|---|
| **surface** (parity) | **+0.007** | −0.013 … +0.027 | 0.573 (CI 0.48–0.66) | **NO_UTILITY_SIGNAL** — real & scrambled indistinguishable on formatting (no template/length artifact) |
| **random** (null) | +0.039 | −0.139 … +0.220 | 0.524 (CI 0.44–0.61) | **NO_UTILITY_SIGNAL** — null judge shows no systematic preference |

## Confirmatory arm — blind LLM judges (7 sub-agents, real vs scrambled-seed0, order randomized & hidden)
- utility(real) − utility(scrambled): **Δ = +0.070**  (95% CI **+0.008 … +0.133**)
- real-preferred rate = 0.573  (95% CI 0.488 … 0.657 — **includes 0.50**)
- real-preferred 69 / scrambled 51 / tie 4

### VERDICT: **INCONCLUSIVE**
Per the pre-registered rule: CI_lower(Δ) > 0, **but Δ = 0.070 is far below MIN_EFFECT = 0.30**, so it is not
a product-meaningful effect → INCONCLUSIVE (not UTILITY_SIGNAL_DETECTED, not NO_UTILITY_SIGNAL).

### Why this is INCONCLUSIVE and not a win — judge unreliability
The judges had a strong **position bias** (preferred the second-shown artifact "B" 80× vs "A" 40×).
Splitting by where the *real* artifact was placed (it was balanced 62/62):

| real shown as | Δ | note |
|---|---|---|
| A | **−0.050** | position bias works *against* real |
| B | **+0.190** | position bias works *for* real |

The effect's **sign flips with position.** Because placement was balanced, the position bias cancels in the
aggregate (leaving the +0.070 content estimate), but the **bias magnitude (~0.12) is larger than the content
effect itself (~0.07)** — the judge is noisier than the thing being measured. The +0.070 is therefore small,
fragile, and below the product threshold by 4×.

### Per-use_case / per-category Δ (LLM, all sub-threshold)
| use_case | Δ | | category | Δ |
|---|---|---|---|---|
| naming | +0.108 | | brand_name | +0.108 |
| creative | +0.104 | | english_everyday | +0.104 |
| affective | +0.083 | | emotionally_loaded | +0.083 |
| journaling | +0.028 | | sanskrit_spiritual | +0.032 |
| | | | neutral_control | +0.024 |

Every cell is below 0.30. Notably the Sanskrit and neutral arms are near zero.

## Interpretation (per pre-registered rules)
**INCONCLUSIVE → no product claim yet.** The real lexicon shows **at most a micro-effect (~0.07 on a 5-point
scale, ~1.7% of usable range)** over a pair-preserving scramble — far below what would matter to a user, and
confounded by a position bias larger than the effect. The honest reading is that **non-lexical utility from
the specific sound→propensity attachment is, at best, negligible**: artifact quality is dominated by the
(identical) template and the lexicon's general richness, both of which the scramble preserves.

This does **not** upgrade Varṇa Lens. Required next steps before any utility claim (from the prereg's
INCONCLUSIVE branch): a **counterbalanced** judge (present each pair in both A/B and B/A orders, average, to
cancel position bias), a larger N and more judges, and possibly narrowing to a single use_case — with the
understanding that the effect ceiling observed (~0.07–0.11) is unlikely to clear MIN_EFFECT even de-biased.
Until then: treat Varṇa Lens as an aesthetic/contemplative mirror with **no special claim** of the real
lexicon over a scrambled one. Still not connected to C×R×S / Conscious Generation.
