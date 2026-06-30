# PRE-REGISTRATION (DESIGN) — Unified Varṇa Model: One Meaning, Two Fixed Boundaries

**Document type:** Pre-registration design.
**Status:** DESIGN draft — no implementation, no data, no run, no freeze. Frozen-on-commit applies to the artifact list only once a run is approved.
**Standing prohibitions:** No implementation here. Stage A (the SO(4) operator system) is **not used and not modified**. No data collected, nothing computed.

> **Relation to prior work.** This design collapses B0 / Version A / Version B into **one varṇa meaning accessed through two *fixed* boundaries**. It reuses the existing alignment machinery (RSA: Mantel / partial-Mantel / scrambled-table null) conceptually; it does **not** decode single-word meanings by hand (no narration, no joiners).

> **Interpretive scope (read first).** A positive result shows only that the table's per-varṇa structure tracks a **real perceptual (External) or self-effect (Internal) dimension beyond generic iconicity** — a narrow, representational result. It does **not** prove the vṛtti meanings are correct, the compositional word-meaning claim, the (dropped) physical/mental-plane claims, or Symbol-U.

## 0. Shared core model (frozen)
- Each varṇa has **one** fixed vṛtti meaning, taken verbatim from the frozen `lexicon_wordformation.json` (`word_formation_reading`). There are **not** separate internal/external meanings.
- "External" and "internal" are **two boundaries of that one meaning**, selected by a **protocol-level fixed rule**, never per word:
  1. **Spelling → External-boundary test (E).**
  2. **Pronunciation → Internal-boundary test (I).**
- Confirmatory composition is **equal-weight, consonant-only** over the vṛtti vocabulary (as in the synonym-selection scaffold); ordered/operator composition is **exploratory only**.
- Both tests are **alignment (RSA)** tests — they compare *structures across words*, never decode a single word's meaning.

---

## Parallel specification (Requirements 1–7)

| | **E — External boundary** | **I — Internal boundary** |
|---|---|---|
| **1. Estimand** | Alignment between the word×word dissimilarity of the **spelling-derived** varṇa composition (T_E) and the word×word dissimilarity of **independently-measured perception of the written form** (H_E) — above scrambled tables **and** above generic orthographic/visual features. | Alignment between the word×word dissimilarity of the **pronunciation-derived** varṇa composition (T_I) and the word×word dissimilarity of the **measured internal-state change of uttering** (H_I) — above scrambled tables **and** above generic articulatory-effort features. |
| **2. Null / Alt** | H0: r(T_E,H_E) ≤ scramble, or partial-r(T_E,H_E \| O) CI lower ≤ 0. H1: beats scramble **and** partial-Mantel CI lower > 0. | H0: r(T_I,H_I) ≤ scramble, or partial-r(T_I,H_I \| P) CI lower ≤ 0. H1: beats scramble **and** partial CI lower > 0. |
| **3. Input representation** | Word → varṇas by a **frozen orthography→varṇa tokenizer**; **silent/written letters included**; **pronunciation never consulted**. Confirmatory set restricted to **native-varṇa (Devanagari/IAST) words + controlled pseudowords** to avoid the Roman→varṇa transliteration degree of freedom (Roman words = exploratory arm with a *separately frozen* Roman→varṇa map). | Word → varṇas by a **frozen g2p (pronunciation) tokenizer**; **spelling never consulted**; homophones get identical input. |
| **4. Target observable** | **Perception of the written form** by **naïve raters** (blind to any meaning/hypothesis; pseudowords and unfamiliar names preferred) on **K pre-registered perceptual/affective scales chosen from outside the varṇa vocabulary** (e.g. small–large, light–heavy, sharp–round, calm–agitated). Optionally anchored to existing **brand-name/name-form perception norms**. → H_E. | **Internal effect of uttering** measured on the producer: **self-report affect** (valence, arousal, calm–activation), attention; **physiological proxy** (HRV, breathing rate) **if available**. Utterer blind to hypothesis. → H_I. |
| **5. Controls** | **Orthographic/visual** matrix **O**: length, bigram frequency, letterform angularity/curvature, character-set features → partial-Mantel control (the "generic iconicity" confound). | **Articulatory-effort** matrix **P**: syllable count, aspiration count, place-of-articulation effort, duration, voicing → partial-Mantel control (the "generic articulation/breathing" confound). **P is supplied by the B0 PanPhon machinery** (see §13). |
| **6. Scrambled-table null** | Permute varṇa→vṛtti assignment within the table (N≥1000 seeds), rebuild T_E, recompute Mantel + partial-Mantel. PASS > 95th pct; NULL ≤ median. | Same, on T_I. |
| **7. Failure criteria** | Target reliability below floor (Krippendorff α<0.67 / split-half<0.6); tokenizer coverage gaps; null-machinery sanity fails; **pronunciation-invariance breach** (E result changes when only the silent/written-vs-spoken distinction is toggled → leakage from sound); low power. | Target reliability below floor; g2p coverage gaps; sanity fails; **spelling-invariance breach** (I result changes across different spellings of the same pronunciation → leakage from orthography); low power. |

---

## Shared sections (Requirements 8–11)

### 8. Decision labels (per boundary; identical scheme)
- **BOUNDARY_ALIGNED** — real > 95th pct scramble (p<0.05) **and** partial-Mantel (controlling O resp. P) CI lower > 0, **under both T-encodings**. The only positive.
- **GENERIC_ONLY** — beats scramble but **partial-Mantel collapses** → the alignment is generic orthographic/visual (E) or articulatory (I) iconicity, **not** the specific table. **A negative.**
- **TABLE_NULL** — real ≤ scramble median. Clean negative.
- **ENCODING_DEPENDENT** — passes one T-encoding not the other. Non-confirmation.
- **RELIABILITY_FAILURE** — target H unreliable. Terminal.
- **INCONCLUSIVE_LOW_POWER** — CI spans 0 / ambiguous.

### 9. What counts as SUPPORT
**Support for one boundary requires BOUNDARY_ALIGNED on that boundary. Support for the unified two-boundary model requires both boundaries supported.** Each supported boundary additionally requires partial-Mantel CI lower > 0 under both encodings **and** independent **replication** (new raters/utterers, re-frozen instrument).

### 10. What counts as NO_SIGNAL
**TABLE_NULL** or **GENERIC_ONLY** on a boundary = NO_SIGNAL for that boundary: the specific varṇa table is not mirrored in that target beyond random tables / beyond generic iconicity. Concordant with the prior record (lexical NO_SIGNAL; bīja ~15%).

### 11. What these tests do NOT prove
- They do **not** prove the vṛtti meanings are "correct."
- They do **not** test composition into full word meaning, etymology, intention, or the dropped physical/mental-plane claims.
- A positive shows only that the table's per-varṇa structure tracks a **real perceptual (E) or self-effect (I) dimension beyond generic iconicity** — a narrow, representational result, not the ontology.
- Neither boundary can validate Symbol-U or Stage A.

---

## 12. How this differs from B0 / Version B / Version A
- **vs B0** (target = idealized articulatory features): here the targets are **human/behavioral** — *perception of the written form* (E) and *self-effect of uttering* (I). B0's articulatory features become the **control P**, not the target.
- **vs Version B** (perceived *sound* qualities from audio): E uses **written-form perception with no audio at all**; I uses **utterance self-effect**, not perception of sound. Different inputs, different targets.
- **vs Version A** (compositional synonym selection through a subjective target→vṛtti bridge): **no bridge** — alignment to independently measured targets. Bridge-free like B, but **two fixed boundaries**.
- **Unifying novelty:** *one* meaning, *two* boundaries, with **frozen boundary-selection** — which removes the per-word spelling/pronunciation degree of freedom that broke the Jesus/Yeshua case.

## 13. Fate of B0 (phonetic alignment): **demote to control, do not retire**
B0's articulatory-feature dissimilarity (PanPhon) is exactly the **generic-articulation control matrix P** the Internal test must beat. So B0 is **repurposed as the partial-Mantel control / diagnostic baseline**, not run as a standalone theory-test. Keep it as an **optional diagnostic**: if the Internal boundary can't beat B0's P, that *is* the GENERIC_ONLY verdict. Retiring it would discard a ready-made, frozen control.

## 14. Preventing per-example switching of spelling/pronunciation
Enforced at four levels, all frozen pre-data:
1. **Protocol binding:** E *always* uses the spelling tokenizer; I *always* uses the g2p tokenizer. The boundary↔tokenizer map is a frozen constant, not a parameter.
2. **Frozen word lists + tokenizations** (sha256): each word's varṇa string for each test is computed once, mechanically, and hashed; it cannot be recomputed or reassigned.
3. **Automated leakage guard:** the E pipeline has **no access** to the g2p table and the I pipeline has **no access** to the orthographic tokenizer; a test that calls the wrong tokenizer fails its sanity check.
4. **Invariance checks (§7):** E must be invariant to pronunciation (silent letters retained); I must be invariant to spelling (homophones identical). A breach voids the run.
No word may appear in a test under the *other* boundary's tokenization, and no item may be moved between tests after results are seen.

---

## Frozen artifacts (sha256 before analysis)
Core table; orthographic tokenizer + (exploratory) Roman→varṇa map; g2p tokenizer; word lists + pseudowords + per-test varṇa strings; the K perceptual scales (E) and affect/physio instrument (I); O and P control definitions; T-encodings; Mantel/partial-Mantel defs; scramble seeds + N; reliability floors; decision rule.

## Prohibited researcher degrees of freedom
No post-hoc scale/encoding selection; no moving words between boundaries; no dropping varṇas/words/raters after seeing alignment; no reporting raw Mantel without the partial control; no relabeling GENERIC_ONLY or ENCODING_DEPENDENT as partial wins.

---

## Critical assessment

**Remaining ambiguity.**
1. **Non-native tokenization.** Roman→varṇa for non-Devanagari words is still a declared convention (a real degree of freedom). Mitigated by making the **confirmatory** set native-varṇa + pseudowords, and quarantining Roman words to a separately-frozen exploratory arm.
2. **Scale choice for E.** The perceptual/affective dimensions must be fixed in advance and drawn from *outside* the vṛtti vocabulary; the exact set is a genuine choice that affects power.
3. **Composition function.** Confirmatory is the weak bag/equal-weight model; the ordered/operator model (the driver/passenger idea) is exploratory because it needs a decoder, which this alignment design deliberately avoids.

**Strongest circularity risk.** The **target measurement leaking the answer.** Two channels of leak: (a) if E raters or I utterers *know the words' meanings*, their perception/affect will track meaning, not form — so the confirmatory set must use **pseudowords and unfamiliar names with naïve participants**; (b) if the E scales (or I affect dimensions) are chosen to **mirror the vṛtti axes**, the test is circular by construction — so the dimensions must come from an **independent, pre-registered inventory**. These two are the make-or-break controls; if either is violated the result is uninterpretable regardless of the statistics.

**Second-strongest risk — and a hard caveat on the External boundary.** Reading activates phonology (sub-vocalization), so the **External (spelling) boundary may not be psychologically separable from pronunciation** in raters' minds — reading a written form can silently evoke its spoken form, contaminating a "spelling-only" measurement with pronunciation. **Therefore External-boundary evidence is interpretable ONLY if the orthographic controls (O) and the silent-letter / homophone invariance checks pass.** If those checks fail — i.e. if the External result moves with pronunciation rather than spelling — the External boundary is **uninterpretable** for that run, regardless of how strong the raw alignment looks. If E and I additionally correlate highly, the "two separable boundaries" claim weakens empirically — itself an informative finding.

**Is this more testable than prior versions?** **Yes — modestly but genuinely.** It (a) **fixes the boundary-selection rule**, removing the per-word spelling/pronunciation freedom that made Jesus/Yeshua produce opposite readings; (b) uses **independently-measured targets** with **bridge-free alignment**; (c) carries **mandatory generic-iconicity controls** that separate "the specific table" from "ordinary sound/shape symbolism." It is the cleanest, least-circular version yet.
**But** the prior from the external literature *and* from this project's own nulls predicts **GENERIC_ONLY / TABLE_NULL** — a real but generic iconicity effect, with the specific table washing out under the partial control. So: more testable, same expected negative — which is exactly why it is worth running rather than arguing.

---

> structure, not validated meaning.
