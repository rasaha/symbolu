# B1 — Native Mechanism Qualitative Review (development-only, docs/data)

**Development verdict: `MAPPINGS_TOO_GENERIC_FOR_COMPOSITION_PREREGISTRATION`.** Exploratory mechanism development
over the existing mappings from commit `2fbdecc3`. It makes **no** semantic-validation claim, selects **no** words by
fit, rewrites **no** mapping, mixes **no** polarity per word, runs **no** judge, and preserves the prior `NO_SIGNAL`.
The vowel poles remain `AUTHORED_PROVISIONAL`. **Structure, not validated meaning.** No `GENUTILITY_*`; no
`ONTOLOGICAL_SIGNAL`. Data: `b1_native_mechanism_qualitative_review/`.

## Selection (fixed before inspecting fit)

**Rule:** the 10 required known examples + fillers chosen to cover a phonological×semantic category matrix
(abstract/concrete/mental/action × positive/negative/neutral × short/long/diphthong vowels ×
aspiration/conjunct/anusvāra/visarga/missing-ṛ) — fillers by **category need, not apparent fit**
(`selected_word_manifest.json`, hash fixed to the word list alone).

**28 selected:** śānti, sukha, bala, jñāna, kṣamā, sattva, mokṣa, ahiṃsā, satya, dharma, yoga, ānanda, deva
(positive); duḥkha, bhaya, krodha, moha, kāma, māyā, mṛtyu (negative); agni, jala, nara, namaḥ, saṃskāra, saṃskṛta,
kṛṣṇa (neutral/concrete); with hṛdaya, saṃskṛta, mṛtyu, kṛṣṇa carrying the missing vocalic ṛ.

## The five fixed views (applied to every word, one uniform rule)

- **A** full binding · **B** full liberating · **C** consonant binding backbone · **D** consonant liberating backbone
  · **E** typed mixed (consonants as vṛtti primitives + vowels/markers as authored-provisional contributions, marked).

## Fit-category distribution by view

| view | DIRECTLY_SPECIFIC | PLAUSIBLY_RELATED | GENERIC_OR_BARNUM | PARTIALLY_CONTRADICTORY | UNINTERPRETABLE (ṛ) |
|---|---|---|---|---|---|
| A full binding | **0** | 6 | 5 | 13 | 4 |
| B full liberating | **0** | 13 | 5 | 6 | 4 |
| C consonant binding | **0** | 6 | 5 | 13 | 4 |
| D consonant liberating | **0** | 13 | 5 | 6 | 4 |
| E typed mixed | **0** | 0 | 24 | 0 | 4 |

**The A↔B mirror is the whole finding.** Binding views fit negative words and contradict positive ones; liberating
views do the reverse. Fit reduces to **one bit — does the fixed polarity match the word's valence** — and never to
word identity. **No view is `DIRECTLY_SPECIFIC` for any word; nothing is `STRONGLY_CONTRADICTORY`** (the mismatches
are thematic, not unit-by-unit inversions).

## Representative readings (exact rows in the appendix; concise here)

- **śānti** (peace) `[ś ā n t i]` — View D liberating: *sublimation · de-fascination · cessation-of-dullness*
  → `PLAUSIBLY_RELATED`, but these are broad spiritual themes. View A binding: *kāma · moha · jāḍya* →
  `PARTIALLY_CONTRADICTORY` (negative reading of "peace"). Vowels add *expansion* (ā) + *ego-doing* (i) — generic.
- **duḥkha** (suffering) `[d u ḥ kh a]` — View A binding: *peevishness · tunnel-vision · compulsion · anxious
  rumination* → `PLAUSIBLY_RELATED`. View B liberating: *forbearance · Attraction/Nectar-pull · Birth-of-cognition*
  → `PARTIALLY_CONTRADICTORY` (positive reading of "suffering").
- **bala** (strength) `[b a l a]` — the two `a`s repeat *Birth of cognition / raw potential* identically; the whole
  reading is `GENERIC_OR_BARNUM`. **`jala` (water) and `nara` (man) share this exact `a…a` scaffold** — three
  unrelated words, near-identical vowel contribution.
- **kṛṣṇa / mṛtyu / hṛdaya / saṃskṛta** — a hole at vocalic ṛ → `UNINTERPRETABLE_DUE_TO_MISSING_UNIT`.

## Adversarial control (generic interpretability made visible)

Positive-abstract words (**śānti, sattva, bala, satya**) all receive the **same** `PLAUSIBLY_RELATED` class under
View D; their liberating consonant backbones are interchangeable broad themes (*sublimation, de-fascination,
cessation-of-dullness, raw-potential*). Relabelling the gloss does not change which reading "fits." A same-length
positive vs negative pair flips only **which polarity** reads coherently — content is not word-specific.

## Error taxonomy (`error_taxonomy.json`)

- **generic_facets_fit_many (dominant):** the inherent `a` (*Birth of cognition / raw potential* | *restless
  starting*) is in nearly every word.
- **polarity_ambiguity:** every unit carries both poles; apparent fit depends on polarity choice.
- **sequence_order_irrelevance:** no rule consumes order; the reading is an ordered *list*, not an order-sensitive
  composition. **Order appears unimportant.**
- **vowel_creates_apparent_fit / vowel_creates_contradiction:** the generic `a` pads every word positively and
  contradicts negative words. **Vowels worsen specificity.**
- **repeated_unit_effects:** repeated `a` repeats an identical facet.
- **missing_vocalic_ṛ:** 4 words uninterpretable.
- **grammatical_structure_ignored / root_vs_surface_mismatch:** a-privative and morphology invisible.
- **post_hoc_narrative_risk (high):** dual poles × broad facets let a story be told for any word.

## Candidate composition mechanisms (`candidate_composition_matrix.json`)

| candidate | post-hoc flexibility | falsifiability | supported? |
|---|---|---|---|
| ORDERED_FACET_SEQUENCE | high | low | current default; not source-grounded |
| ONSET_SEED_PLUS_TRANSFORMERS | high | medium | invented (English apparatus) |
| CONSONANT_BACKBONE_WITH_VOWEL_MODULATION | medium | medium | partially source-aligned; drops generic vowel padding (**cleanest structure**) |
| AKSHARA_LOCAL_COMPOSITION | high | low | invented |
| DOMINANT_OR_DIAGNOSTIC_VARNA | very high | low | invented (maximal cherry-pick) |
| BIDIRECTIONAL_POLARITY_PATH | **low** (poles fixed per whole-word trajectory) | **high** | **only non-cherry-pick, testable option** — but our data show it predicts VALENCE (1 bit), not word identity |
| NULL_OR_NO_COMPOSITION | none | n/a | the honest null the evidence currently favours |

The two least-flexible candidates — **BIDIRECTIONAL_POLARITY_PATH** (falsifiable, no per-unit mixing) and
**CONSONANT_BACKBONE_WITH_VOWEL_MODULATION** (drops the generic `a`) — are the only ones worth future development,
but **neither is ready for pre-registration**: both still bottom out in broad, valence-coupled themes.

## Required conclusions

1. **Most specific:** none reach `DIRECTLY_SPECIFIC`; least-generic are positive-abstract words under View D (still only `PLAUSIBLY_RELATED`).
2. **Most generic:** bala, jala, nara, kāma, agni (repeated-`a` Barnum).
3. **Contradicting:** valence-mismatched fixed polarity (positive words under binding; negative under liberating).
4. **Vowels:** **worsen** specificity (generic padding + contradictions).
5. **Order:** **not** important (no order rule; readings are lists).
6. **One polarity consistently better?** **No** — binding fits negatives, liberating fits positives (valence-coupled).
7. **Consonant-only vs full typed differ materially?** **Yes** — typed adds generic vowel padding that dilutes specificity.
8. **Any candidate ready for pre-registration?** **No.**
9. **Mappings too flexible for a fair rule?** **Yes.**

## Development verdict

**`MAPPINGS_TOO_GENERIC_FOR_COMPOSITION_PREREGISTRATION`** — the mappings encode valence-via-polarity, not word
identity; with dual poles and broad facets they remain too flexible for a fair composition rule. Consistent with the
prior `NO_SIGNAL` (preserved, not overturned).

## Single recommended next action

If development continues, prototype **only** `BIDIRECTIONAL_POLARITY_PATH` (fixed whole-word trajectory, no per-unit
polarity mixing) as a **discrimination probe** — measuring whether it separates words *beyond* valence and beyond a
length-matched unrelated control — **before** any pre-registration, and while first closing the vocalic-ṛ gap and
raising vowel provenance above `AUTHORED_PROVISIONAL`. Do **not** author new vowel meanings and do **not** treat any
development-grade reading as validated.
