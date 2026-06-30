# PRE-REGISTRATION (DESIGN) — Varṇa–Phonetic-Feature Alignment (B0)

**Document type:** Pre-registration design. **The cheapest falsification gate** in the B-ladder — fully automated, deterministic, no audio, no humans.
**Version:** B0 (design draft).
**Status:** DESIGN — not frozen, not run, not implemented. No data, no audio, no fit, no computation. Frozen-on-commit applies to §17 only once a run is approved.
**Standing prohibitions:** No implementation here. Stage A (the SO(4) operator system) is **not used and not modified**. No audio collected. Nothing computed.

> **Relation to Version B / B-ladder.** B0 is the **objective-phonetics** rung *below* Version B. Version B (`PREREG_SYNONYM_SELECTION_VERSION_B.md`) compares the table to **human perception of sound** (listeners, audio). B0 removes humans *and* audio: it compares the table only to an **independent, deterministic phonetic-feature representation** (PanPhon / IPA feature tables). B0 is therefore *further* from perception and ontology than Version B — it tests **representational grounding only**. It is run **first** as a cheap gate: if the table cannot beat a scrambled table on objective phonetic features after controlling for the trivial alphabet grid, the perception claim (B1/B2) is in serious trouble before any recording or recruiting is paid for.

> **Interpretive scope (read first).** B0 measures whether the frozen varṇa table's **meaning-structure** is phonetically iconic at the **articulatory-feature** level, **beyond random tables and beyond the trivial place/manner (varga) grid the table is laid out on**. A positive does **not** prove the meanings are correct, does **not** prove humans perceive anything, and does **not** support Symbol-U. A null bounds the table's phonetic grounding at the feature level only.

---

## 0. Scope and sequencing
B0 answers **one** question: *does the structure derived mechanically from the frozen varṇa table align with an independent phonetic-feature structure of the same varṇas — better than scrambled tables, and beyond the trivial place/manner classes the table inherits from the Sanskrit alphabet?* It deliberately **does not** test composition, word meaning, etymology, intention, human perception, Stage A, or full Symbol-U. It is the bottom rung of the B-ladder; B1 (audio features) and B2 (human perception) are conditional follow-ups (§ "B0 vs B1 vs B2").

## 1. Scientific estimand
The **representational alignment** between (i) a varṇa×varṇa dissimilarity matrix **T** derived *mechanically* from the frozen table's `word_formation_reading` field, and (ii) a varṇa×varṇa dissimilarity matrix **P** derived *mechanically* from an independent articulatory-feature representation (PanPhon over the IAST/IPA segment) — measured as the rank correlation of the two upper triangles, **above** scrambled tables **and above** a coarse place/manner class matrix **C**. No human, no audio, no perception enters.

## 2. Null hypothesis
**H0:** the table-derived structure T is no more aligned with phonetic-feature structure P than a scrambled table, and any raw alignment is fully explained by the coarse place/manner classes C. Formally: Mantel r(T, P) ≤ scrambled distribution, **or** partial-Mantel r(T, P | C) CI lower bound ≤ 0.

## 3. Alternative hypothesis
**H1:** T aligns with P beyond scrambled tables **and** beyond the coarse class grid. Formally: r(T, P) > 95th pct of the scrambled-table null **and** partial-Mantel r(T, P | C) CI lower bound > 0, under **both** T-encodings.

## 4. Inventory and stimulus definition
- **Confirmatory set:** the **34 consonant varṇas** (the source-faithful primary-vṛtti set), each represented as its IAST segment voiced with the inherent /a/ (ka, kha, ga, …) for the phonetic representation. Frozen list = the consonant keys of `lexicon_wordformation.json`.
- **Exploratory arm:** the 12 vowels (flagged CANDIDATE/intuition-derived in the lexicon) — reported separately, never pooled into the confirmatory statistic.
- No audio. The "stimulus" is the **symbolic phoneme**, mapped to features by a frozen library — *not* a recording.

## 5. The three matrices (all mechanical, no human coding)
- **P — phonetic-feature dissimilarity (independent representation).** Map each varṇa's IAST segment → IPA → PanPhon articulatory feature vector (place, manner, voicing, aspiration, nasality, etc.). Dissimilarity = (default) **Hamming/weighted-feature-edit distance** over the PanPhon feature vectors; **sensitivity:** cosine over the same vectors. The feature library and its version are frozen (§17). *P is the independent yardstick — it contains no table information.*
- **T — table-derived dissimilarity.**
  - **Primary (T_embed):** embed each varṇa's `word_formation_reading` string in a **frozen public sentence-embedding model** → cosine dissimilarity. No hand-coding, no human mapping.
  - **Sensitivity (T_cat):** an **independently frozen categorical encoding** of (polarity pole + tattva/element + axis position), one-hot/ordinal → dissimilarity. Used only to detect encoding dependence.
- **C — coarse class control (the trivial-confound matrix).** A varṇa×varṇa matrix of **shared coarse place/manner class** = varga membership (ka/ca/ṭa/ta/pa rows) crossed with the manner column (unaspirated-voiceless, aspirated-voiceless, unaspirated-voiced, aspirated-voiced, nasal), plus the semivowel/sibilant/aspirate classes. C captures the **alphabet grid the table is physically laid out on** — the structure that T and P trivially share. Frozen, derived only from standard phonological class membership.

## 6. Alignment statistic
- **Primary alignment:** Mantel / Spearman rank correlation of the upper triangles of **T_embed** and **P**.
- **Trivial-class control (mandatory):** **partial Mantel** of (T_embed, P) **controlling for C** — the only test that distinguishes "the table tracks sound" from "the table is laid out on the same grid as the phonetics." Without this control the result is uninterpretable.
- **Sensitivity:** repeat with **T_cat**; repeat P with cosine vs feature-edit distance. Verdict requires agreement across encodings (§12).

## 7. Scrambled-table null
Permute varṇa→`word_formation_reading` assignment (the meaning labels are shuffled across the 34 consonants), **N = 1000 fixed seeds**, recompute T and both Mantel and partial-Mantel r. The scramble destroys any table-specific structure while preserving the label *set* and the matrices' marginal distributions. **PASS** real > 95th pct; **NULL** real ≤ median; **AMBIGUOUS** in between. Applied to **both** raw Mantel and partial-Mantel.

## 8. Bootstrap confidence intervals
Bootstrap over **varṇas** (resample the 34 consonants with replacement, rebuild T, P, C, recompute r), **N = 2000** → 90% CI on Mantel r and partial-Mantel r. A positive requires the partial-Mantel CI lower bound > 0. (Varṇa-level bootstrap is the honest resampling unit here — there are no raters or recordings to resample in B0.)

## 9. Permutation testing
Mantel label permutation (permute the varṇa labels of one matrix, **N = 10⁴**) → exact-ish p-value for the observed r and partial r. Required **p < 0.05** for both.

## 10. Reliability / sanity gates (replacing human reliability)
B0 has no human ratings, so the reliability gate is **machinery sanity**, frozen in advance:
- **Null-machinery sanity:** scrambling a *random* table yields r ≈ chance (the null is correctly centered).
- **Positive-control sanity:** a *planted* table (one constructed to equal P up to noise) is recovered by the pipeline (the test can detect alignment when it exists).
- **Determinism:** T, P, C are byte-stable across two runs with fixed seeds (no hidden randomness in the embedding/feature extraction).
Failure of any sanity gate → run invalid (not a verdict about the table).

## 11. Trivial-confound checks (beyond C)
- **Inherent-vowel invariance:** because every consonant is voiced with the same /a/, the /a/ contributes a constant feature offset; verify the verdict is unchanged whether the inherent vowel features are included or stripped (the consonant must drive P, not the shared vowel).
- **Aspiration/voicing leakage:** report the partial-Mantel additionally controlling for *only* voicing+aspiration vs *only* place, to localize where any surviving alignment lives.
- **Embedding-artifact check:** confirm T_embed alignment is not an artifact of string length / shared tokens in the reading strings (regress out reading-string length; alignment must survive).

## 12. Decision labels (answer to Question 4)
- **PHONETIC_ALIGNED** — r(T, P) > 95th pct of the scramble null (p < 0.05) **AND** partial-Mantel r(T, P | C) CI lower bound > 0, **under both T-encodings and both P-distances**. *The positive: the table's meaning-structure is phonetically iconic beyond random tables and beyond the alphabet grid — a property of the representation only.* This is the **only** verdict that licenses spending on B1/B2.
- **PHONETICS_ONLY (TRIVIAL_CLASS_ONLY)** — raw Mantel beats the scramble null **but partial-Mantel collapses** (CI includes 0) → the apparent alignment is **entirely the varga place/manner grid the table is laid out on**, not anything the table adds. **Reported as a negative for the iconicity claim.** (For B0 this is the *expected default*, since the table is physically organized on the varga grid.)
- **TABLE_NULL** — r(T, P) ≤ scramble median → the table's meaning assignments are no more phonetically aligned than randomly relabeled tables. A clean negative.
- **ENCODING_DEPENDENT** — passes under one T-encoding or P-distance but not the other → non-confirmation (not a partial win).
- **INCONCLUSIVE** — ambiguous scramble percentile, or partial-Mantel CI spans 0 with wide bounds (low power from only 34 items).

## 13. Failure criteria
Any sanity gate (§10) fails; PanPhon cannot represent a varṇa (mapping gap > frozen tolerance); fewer than the full 34 consonants map cleanly; inherent-vowel-invariance check fails (P driven by the shared /a/) → run invalid.

## 14. Interpretation rules
- `PHONETIC_ALIGNED` is a statement about the **representation's phonetic grounding**, *not* about meaning correctness, *not* about perception, *not* about Symbol-U.
- `PHONETICS_ONLY` is a **negative for the table** — it means "the table = the alphabet grid," which any faithful transcription of the Sanskrit varṇa order would also satisfy.
- Verdict is set **solely** by the primary T_embed under both encodings with the **mandatory** partial-Mantel control. Raw Mantel without the C-control is never reported as a result.

## 15. NO_SIGNAL interpretation
`TABLE_NULL` / `PHONETICS_ONLY` is **concordant with the prior record** (bīja↔sound-feeling ~15%, below chance; NO_SIGNAL lexical recovery). It bounds the table's phonetic grounding at the **feature level**; it does **not** by itself refute a compositional word-level effect, nor prove the meanings wrong on an untested (perceptual) dimension. But because B0 is the *cheapest and most charitable* test (objective features, no human noise), a B0 null is a **strong** prior-lowering result for B1/B2.

## 16. Replication / escalation requirements
- A `PHONETIC_ALIGNED` result is **provisional** until replicated with an **independently re-frozen** feature library (e.g. IPA feature tables instead of PanPhon) and an **independently re-frozen** embedding model.
- Only a replicated `PHONETIC_ALIGNED` escalates to **B1** (audio features) and then **B2** (human perception). Any other verdict stops the ladder at B0 (the perception tiers are not worth their cost).

## 17. Frozen artifacts (sha256 before any analysis)
`lexicon_wordformation.json` hash; the 34-consonant frozen list + IAST→IPA mapping; PanPhon version + feature set + chosen distance (primary + sensitivity); embedding model + version (T_embed); categorical Encoding (T_cat); the C class-matrix definition; Mantel/partial-Mantel definitions; scramble seeds + N; bootstrap/permutation N; decision rule; sanity-gate thresholds.

## 18. Prohibited researcher degrees of freedom
- No post-hoc choice of T-encoding, P-distance, or embedding model; primary fixed, sensitivities frozen.
- No dropping varṇas after seeing alignment.
- No switching the class-control matrix C, the scramble seeds, or the dissimilarity metric after results.
- **No reporting raw Mantel without the partial-Mantel C-control.**
- No relabeling `PHONETICS_ONLY` or `ENCODING_DEPENDENT` as a partial success.
- No silent inclusion of vowels in the confirmatory statistic (exploratory arm only).

---

## Answers to the five questions

1. **Does the table's structure align with phonetic-feature structure?** — Measured by Mantel r(T, P). Tested against the scramble null (§7) and bootstrap CI (§8).
2. **Does it beat scrambled varṇa tables?** — §7. PASS requires real > 95th pct of 1000 scrambles, p < 0.05 (§9).
3. **Does alignment survive controlling for trivial place/manner classes?** — §6 partial-Mantel controlling C is **mandatory and dispositive**. This is the single most important test in B0, because the table is physically laid out on the varga (place/manner) grid, so a raw correlation is expected for a trivial reason. Only `r(T, P | C) > 0` counts.
4. **Verdicts** — §12: `PHONETIC_ALIGNED` (beats scramble **and** survives C-control, both encodings) / `PHONETICS_ONLY` (beats scramble but C-control collapses → trivial grid only, a negative) / `TABLE_NULL` (no better than scramble) / `ENCODING_DEPENDENT` / `INCONCLUSIVE`.
5. **Perception, ontology, or representational grounding?** — **Representational grounding only.** B0 contains no listeners (so it cannot test perception) and no meaning-truth criterion (so it cannot test ontology). It asks only whether the *representation* the table induces is phonetically systematic beyond chance and beyond the alphabet grid.

---

## B0 vs B1 vs B2

| | **B0 — phonetic-feature approximation** | **B1 — audio-feature extraction** | **B2 — human perception** |
|---|---|---|---|
| **Stimulus** | symbolic phoneme → frozen feature library | recorded spoken bīja syllables → acoustic features (MFCC/spectral) or audio-model embedding | spoken bīja syllables → human listeners |
| **Yardstick (the "P" side)** | PanPhon/IPA **articulatory** features (idealized) | **acoustic** features of actual recordings | **perceived** acoustic-quality ratings |
| **Cost** | ~zero, deterministic, minutes | medium (speakers, recordings, extraction; possible model API) | high (recruit, run, pay listeners) |
| **Contamination risk** | none (no model judgment, no leakage) | medium (model may transcribe-then-embed; recording/speaker variance) | medium–high (knowledge leakage, demand effects) |
| **What it can prove** | representation is phonetically systematic beyond grid | representation tracks *physical sound* beyond grid | representation tracks *human perception* beyond grid + generic sound-symbolism |
| **What it cannot prove** | perception, ontology, composition | perception, ontology, composition | ontology, composition, meaning-correctness |
| **Estimand distance from the actual claim** | farthest (idealized features) | middle (physical acoustics) | closest (perception) — but still not ontology |
| **Reusable machinery already built** | g2p + frozen ARPABET→varṇa map + `experiments/common` stats | — | — |

**Key relationships.** B0 ⊂ B1 ⊂ B2 in fidelity-to-claim but in *reverse* order of cost and contamination. B0's yardstick (articulatory features) is the **idealized** version of B1's yardstick (acoustic features), which is the **physical** correlate of B2's yardstick (perception). Each rung is *necessary-but-not-sufficient* for the next: if the table doesn't align with idealized features (B0), it is very unlikely to align with messier physical acoustics (B1) or noisier human perception (B2).

## Recommendation: run B0 before B1/B2 — yes

**Run B0 first, as a hard gate.** Reasons:
1. **It is nearly free and fully deterministic** — no audio, no recruiting, no model API, no human noise; the machinery already exists.
2. **It is the most charitable test of the table.** Idealized articulatory features are the cleanest possible "sound" signal — no recording artifacts, no perceptual noise. If the table can't clear *this* bar (beyond the varga grid), the perceptual claim is implausible and B1/B2 spending is unjustified.
3. **It isolates the one confound that dooms naïve versions** — the C-control (place/manner grid). B0 forces that control to the front, where it is cheap to run, before any expensive tier inherits the same confound.
4. **Its verdicts route the ladder.** Only a *replicated* `PHONETIC_ALIGNED` escalates to B1, then to B2. `PHONETICS_ONLY`, `TABLE_NULL`, `ENCODING_DEPENDENT`, or `INCONCLUSIVE` stop at B0.

**Honest caveat carried into any report:** the *expected* B0 outcome, given the prior record and the fact that the table is literally laid out on the varga grid, is `PHONETICS_ONLY` — raw alignment that **collapses** under the C-control. That would be a clean, cheap negative for non-trivial phonetic grounding, and is a perfectly good scientific result. B0 is designed so that the most likely outcome is also a *useful* outcome.

---

> structure, not validated meaning.
