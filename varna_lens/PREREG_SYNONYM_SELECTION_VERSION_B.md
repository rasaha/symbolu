# PRE-REGISTRATION (DESIGN) — Varṇa–Perception Alignment (Synonym Selection, Version B)

**Document type:** Pre-registration design (the **preferred clean gate**; bridge-free on the human side).
**Version:** B (design draft).
**Status:** DESIGN — not frozen, not run. No data, no fit, no computation. Frozen-on-commit applies to §17 once a run is approved.
**Standing prohibitions:** No implementation here. Stage A (the SO(4) operator system) is **not used and not modified**. No data collected, nothing computed.

> **Relation to Version A.** Version A (`PREREG_SYNONYM_SELECTION.md`) tests the **compositional, word-level** synonym-selection claim, but through a **subjective target→vṛtti coding bridge** that reliability gates can *measure* but not *eliminate*. **Version B removes that bridge entirely**: humans judge only acoustic qualities (never meanings/vṛttis), and the frozen table is compared to those judgments. **Version B is the preferred clean gate; Version A is conditional/deferred** (see §0 and Version A §13a). If both are run, the order is **B first, then A** — and A runs only if B returns `PERCEPTION_ALIGNED` *and* a less-subjective word-level bridge is available.

> **Interpretive scope (read first).** Version B evaluates the **representation's alignment with perception** (whether the table's per-varṇa structure is phonetically iconic), **not** the truth of the vṛtti ontology and **not** the compositional word-meaning claim. A positive does not prove the meanings are correct, nor Symbol-U; a null bounds the table's phonetic grounding at the varṇa level only.

## 0. Scope and sequencing
This protocol answers **one** question: *does the acoustic representation derived from the frozen varṇa table correspond to reproducible human perception of sound, better than randomized mappings (and beyond generic phonetics)?* It deliberately **does not** test composition, word meaning, etymology, mythology, intention, Stage A, or full Symbol-U. It is the gate; Version A is the conditional follow-up.

## 1. Scientific estimand
The **representational alignment** between (i) a varṇa-level structure derived *mechanically* from the frozen varṇa table and (ii) a varṇa-level structure of *reproducible human perception of the varṇa sounds*, as the rank correlation between the two varṇa×varṇa dissimilarity matrices — **above** scrambled tables **and above** generic articulatory phonetics. Humans judge only acoustic qualities.

## 2. Null hypothesis
H0: the table-derived structure is no more aligned with perceived-sound structure than a scrambled table, and adds nothing beyond articulatory phonetics. Mantel r(real) ≤ r(scrambled).

## 3. Alternative hypothesis
H1: the table-derived structure aligns with perceived-sound structure beyond scrambled tables **and** beyond articulatory phonetics. r(real) > scrambled distribution **and** partial-Mantel (controlling phonetics) CI lower bound > 0.

## 4. Human judgment protocol
- **Stimuli:** consonant varṇas as **spoken bīja syllables** (audio), each voiced with inherent /a/ (ka, kha, ga, …). Multiple trained speakers; ≥3 recordings per varṇa to average speaker/recording variance. Frozen stimulus set.
- **Task:** each listener rates each varṇa-sound on **K = 5 pre-registered bipolar acoustic scales** — heavy–light, hard–soft, sharp–dull, active–calm, bright–dark — 7-point, **from sound alone**. No spelling shown, no meaning solicited, no Sanskrit knowledge required (naïve listeners preferred).
- **Output:** ratings tensor `[varṇa × scale × rater]`.

## 5. Blindness requirements
- Listeners are **meaning-blind and hypothesis-blind**: never see the written varṇa, never learn it is Sanskrit, never know a table/theory exists.
- Audio-only, randomized order, carrier vowel held constant.
- Analysts are blind to real-vs-scrambled until the frozen rule emits the verdict.

## 6. Randomization
Stimulus order randomized per listener; scale order randomized; speaker assignment counterbalanced; scrambled-table seeds fixed in advance; rater→stimulus exposure balanced.

## 7. Reliability requirements
- **Inter-rater** reliability per scale (Krippendorff interval α) and **split-half** reliability of the human dissimilarity matrix H. Floors: **α ≥ 0.67**; **split-half r ≥ 0.6**.
- Scales below floor are dropped (frozen rule). If H is unreliable → `RELIABILITY_FAILURE` (terminal; the perception target isn't reproducible).

## 8. Statistical tests
- **H** = perceived-acoustic dissimilarity (Euclidean over z-scored reliability-passing scales), varṇa×varṇa.
- **T** = table-derived dissimilarity. **Primary:** mechanical — embed each varṇa's `word_formation_reading` string in a frozen public sentence-embedding model → cosine dissimilarity (no human coding, no hand-mapping). **Sensitivity (Encoding A/B):** an independently frozen categorical encoding (pole + tattva + varga) → dissimilarity.
- **Alignment statistic:** Mantel / Spearman correlation of the upper triangles of H and T.
- **Phonetics control (mandatory):** **partial Mantel** of (H, T) controlling for an articulatory-feature dissimilarity matrix P (PanPhon) — tests whether the table adds alignment **beyond generic phonetics**.

## 9. Scrambled-table null
Permute varṇa→table-entry assignment (N = 1000 seeds), recompute T and Mantel r. **PASS** real > 95th pct; **NULL** real ≤ median; **AMBIGUOUS** otherwise. Same for partial-Mantel.

## 10. Bootstrap confidence intervals
Bootstrap over **raters** (resample pool, rebuild H, recompute r), N = 2000 → 90% CI on Mantel r and partial-Mantel r. Positive requires CI lower bound > 0.

## 11. Permutation testing
Mantel label permutation (permute varṇa labels of H, N = 10⁴) → p-value for observed r. Required p < 0.05.

## 12. Decision labels
- **RELIABILITY_FAILURE** — H unreliable (α/split-half below floor). *Terminal.*
- **TABLE_NULL** — real ≤ scrambled (table no better than random mappings).
- **PHONETICS_ONLY** — real beats scrambled on raw Mantel but **partial-Mantel collapses** → generic sound-symbolism, not the specific table (reported as a negative for the table).
- **NO_PERCEPTUAL_SIGNAL** — real at/below permutation chance.
- **INCONCLUSIVE_LOW_POWER** — ambiguous (CI spans 0).
- **ENCODING_DEPENDENT** — Encoding A passes, Encoding B does not (analog of RUBRIC_DEPENDENT).
- **PERCEPTION_ALIGNED** — real beats scrambled (p<0.05) **and** partial-Mantel CI lower > 0 **under both encodings**. The positive (and the only verdict that licenses considering Version A).

## 13. Failure criteria
Reliability below floor; fewer than 3 scales survive; scrambled/permutation machinery fails its sanity check (random ≈ chance); **carrier-vowel-invariance check fails** (perception driven by the vowel, not the consonant) → run invalid.

## 14. Interpretation rules
- `PERCEPTION_ALIGNED` = the table's per-varṇa structure is **phonetically iconic** beyond random tables and beyond generic phonetics — a statement about the **representation's alignment with perception**, not about meaning correctness.
- `PHONETICS_ONLY` is a **negative for the table**.
- Verdict set **solely** by the primary embedding-T under both encodings; the phonetics control is mandatory.

## 15. NO_SIGNAL interpretation
`TABLE_NULL` / `NO_PERCEPTUAL_SIGNAL` = the table's varṇa assignments are **not** mirrored in reproducible human sound-perception beyond random mappings — concordant with the prior bīja↔sound-feeling result (~15%, below chance). It bounds the table's **phonetic grounding at the varṇa level**; it does **not** refute a compositional word-level effect, nor prove the meanings wrong on an untested dimension. At pilot N a null is absence of evidence; a confirmatory null needs §16 replication.

## 16. Replication requirements
A `PERCEPTION_ALIGNED` result is **provisional** until replicated with a **new listener pool**, **new speakers/recordings**, and an **independently re-frozen embedding model and stimulus order**. Cross-listener-population replication (e.g. non-Indian-language listeners) is required before any universality claim.

## 17. Frozen artifacts (sha256 before any analysis)
Stimulus recordings + varṇa list; the 5 scales + instrument; embedding model + version (primary T); categorical Encoding A/B; PanPhon feature set (P); Mantel/partial-Mantel definitions; nulls, seeds, N; reliability floors; decision rule; `lexicon_wordformation.json` hash.

## 18. Prohibited researcher degrees of freedom
- No post-hoc scale selection (drop only by the frozen reliability rule).
- No post-hoc choice of T-encoding or embedding model; primary fixed, A/B frozen.
- No dropping varṇas/speakers/listeners after seeing alignment.
- No switching dissimilarity metric, phonetics control, or null seeds after results.
- No reporting raw Mantel without the phonetics-controlled partial Mantel.
- No relabeling `PHONETICS_ONLY` or `ENCODING_DEPENDENT` as a partial success.

---

## What Version B can / cannot prove (carry into any report)
- **Can:** whether the table's per-varṇa structure is phonetically iconic beyond random mappings **and** beyond generic phonetics — a property of the representation.
- **Cannot:** that the vṛtti meanings are correct; the compositional word-meaning claim; Symbol-U; or that any alignment exceeds ordinary documented sound-symbolism.
- **Representation vs ontology:** B measures the representation's phonetic grounding, **not** the ontology's truth — and is in fact *further* from the ontology than Version A (it tests iconicity, orthogonal to meaning correctness).

> structure, not validated meaning.
