# PRE-REGISTRATION — Acoustic Synonym-Selection (Version A)

**Document type:** Pre-registration (rigorous *exploratory* protocol; not the definitive test of the acoustic-root hypothesis)
**Version:** A (1.0). A preferred **Version B**, which removes the target→vṛtti bridge, is defined in §13.
**Status:** FROZEN-ON-COMMIT. All artifacts in §11 are sha256-committed *before* any fit is computed. No element below may change after results are observed.
**Standing prohibitions:** No implementation in this document. Stage A (the SO(4) operator system) is **not used and not modified**. No fit is computed here.

> **Interpretive scope (read first).** *This protocol evaluates the discriminative power of the acoustic representation, not the truth of the philosophical ontology from which it was derived.* A positive result shows the representation carries information; it does **not** prove Sarkar's metaphysics. A null bounds **this** representation on **this** task; it does **not** prove there are no latent acoustic principles. The document is a rigorous **exploratory** protocol and a stepping stone, not the definitive experiment for the whole acoustic-root hypothesis.

---

## 0. Estimand, hypothesis, prior

**Estimand.** Whether a word's **equal-weight, consonant-only, g2p-derived acoustic profile** (from the source-grounded `word_formation_reading` table in `lexicon_wordformation.json`) predicts the **preferred lexical realization** of a target sense among near-synonyms — above a **scrambled** varṇa table and above a **frequency baseline**, after controlling for frequency, register, length, and etymology.

**H1:** acoustic-fit selection accuracy > scrambled **and** > frequency baseline.
**H0:** acoustic-fit ranks synonyms no better than a scrambled table / frequency baseline.

**Conservative prior.** Previous acoustic-root evaluations using lexical *semantic recovery* found no reliable signal. Because the present protocol tests a **different estimand** (preferred lexical *realization* rather than semantic *recovery*), the prior expectation remains conservative but is **not taken as determinative**. This is a calibration/feasibility pilot, not confirmatory validation of Symbol-U.

---

## 1. Composition rule (equal-weight confirmatory; weighting/transitions exploratory)

**Tokenization (confirmatory, fixed).** Strict phonemic **g2p** (CMUdict/ARPABET; no orthography), segmented to **phonemic / akṣara-level units**. Frozen segmentation rule. (Orthographic splitting is forbidden — "believe" = /bɪliːv/ = bi·lī·v, **not** be+lie+ve.)

**Confirmatory composition (LOCKED):**
- **Unit** = phonemic / akṣara-level acoustic reading from the **source-grounded consonant table** (`word_formation_reading`).
- **Aggregation = EQUAL WEIGHT** across units (no positional decay). **Consonant-only; vowels excluded.**
- Result: an order-agnostic, equal-weight consonant-reading profile. No driver/passenger weighting and no transition rule enter the confirmatory analysis.

**Exploratory composition (separately frozen; can never change the confirmatory verdict):**
- **Driver/passenger geometric weighting** (unit 1 = 1.0, 2 = 0.5, …) — introduces order/headedness;
- **Vowel candidate table**, and **consonant + vowel** (λ vowel-into-consonant);
- **Transition-polarity rules** (C→V vs V→C) — exploratory unless and until independently frozen and justified (not justified now).

Rationale: positional decay, transition polarity, and vowels are modeling assumptions *without independent justification*; the confirmatory arm rests only on the source-grounded, assumption-minimal representation.

---

## 2. Confirmatory vs Exploratory (explicit separation)

**Confirmatory (determines the §9 verdict):**
- consonant-only,
- source-grounded table,
- equal-weight composition,
- fixed g2p / varṇa segmentation.

**Exploratory (candidate annotations only; replication-required; never upgrade or rescue the confirmatory verdict):**
- vowel candidate table,
- consonant + vowel,
- driver/passenger (geometric) weighting,
- transition-polarity rule (C→V / V→C).

**Excluded entirely (not even exploratory in this pre-registration):**
- any **orthographic** axis,
- any **intention / identity-resonance** axis.

---

## 3. Candidate (synonym) sets

N ≥ 30 pre-registered near-synonym sets, K = 4–6 members each, sharing core denotation but differing in nuance (e.g. {big, large, huge, enormous}). Frozen before any fit. Each member recorded for frequency, length, register, and etymology family. **Homophones excluded** (§6).

---

## 4. Ground truth: preferred lexical realization

"Best word" is **not** used. The target is the **preferred lexical realization** — the synonym that actual usage selects for a given target sense; this asserts conventional realization, **not** superiority.

**Ground truth (frozen before any fit), one of:**
1. **Corpus usage** — for each target sense/context, the empirically most-used synonym in matched contexts (pre-specified corpus + extraction rule); or
2. **Blind human preference** — raters shown only the sense/context and the candidate set as **text**, never the sounds, never the hypothesis; the modal choice is the preferred realization.

Targets, candidate sets, and ground-truth labels are sha256-frozen prior to any acoustic computation.

---

## 5. Target → vṛtti profiling (Version-A bridge — the protocol's weakest element)

The target sense is mapped into the vṛtti space using the **name-blind Rubric A / Rubric B** machinery and the insider-vs-naïve reliability gate from `PREREG_OBJECT_PROFILE_FIT.md` (§5–7). **Rubric A is dispositive; Rubric B is the sensitivity check.**

This is the **single weakest link** (see §13). The reliability gate *measures* its subjectivity (`MEASUREMENT_FAILURE` / `CIRCULARITY_FAILURE`) but cannot remove it. If the bridge fails, no fit result is interpretable. **Version B (§13) removes this step entirely and is the preferred long-term protocol.**

---

## 6. Selection rule & fit

For each set: compute every candidate's acoustic profile (§1) and the target profile (§5); **selected realization = max cosine** to the target. **Accuracy** = fraction of sets where the selected realization = the ground-truth preferred realization. Chance = mean(1/K).

---

## 7. Controls

- **Matched/partialled** within each set on **frequency, register, length, etymology family**.
- **Frequency baseline** (pick the most frequent candidate) reported; acoustic-fit must beat it, not just chance.
- **Homophone exclusion**: homophone candidates removed (acoustics cannot distinguish same-sound words).
- **Homophone-invariance leakage check**: any two words with identical g2p **must** receive identical profiles; if not, orthography has leaked into the pipeline → **run invalid**.
- Etymology is controlled because spelling/morphology is the known confound; register/length because they drive word choice independently of sound.

---

## 8. Nulls

- **Scrambled-table null.** Permute the varṇa→`word_formation_reading` map (consonants among consonants; vowels among vowels for exploratory arms), N = 1000 seeds; object profiles/targets untouched. Recompute accuracy. **PASS** if real > 95th pct; **NULL** if real ≤ median; **AMBIGUOUS** otherwise.
- **Chance / candidate-set null.** Accuracy vs max(chance, frequency-baseline); bootstrap 90% CI over the N sets; effect = accuracy − max(chance, frequency-baseline); pre-registered δ_min = 0.05.

A confirmatory positive requires clearing **both** nulls.

---

## 9. Decision labels

Verdict determined **solely** by the confirmatory arm (consonant-only, equal-weight, source table, g2p), **Rubric A dispositive** (Rubric B sensitivity). Exploratory arms are annotations only and can never change the verdict.

- **MEASUREMENT_FAILURE** — target→vṛtti profiling unreliable (IRR below floor). *Terminal.*
- **CIRCULARITY_FAILURE** — insider vs naïve profiling diverges. *Terminal.*
- **TABLE_NULL** — real ≤ scrambled.
- **SELECTION_NULL** — ≤ chance and ≤ frequency baseline.
- **INCONCLUSIVE_LOW_POWER** — ambiguous (CI spans threshold).
- **RUBRIC_DEPENDENT** — Rubric A passes both nulls, Rubric B does not.
- **PILOT_POSITIVE** — real beats **both** scrambled **and** frequency baseline (p<0.05, CI lower>0) under **both** rubrics, confirmatory arm.

**Exploratory annotations** (never change the above; replication-required, never confirmation): `ORDER_CANDIDATE_SIGNAL`, `VOWEL_CANDIDATE_SIGNAL`, `TRANSITION_CANDIDATE_SIGNAL`, `EXPLORATORY_ONLY` (confirmatory fails but an exploratory variant passes).

---

## 10. NO_SIGNAL interpretation

A `TABLE_NULL` / `SELECTION_NULL` means: the **equal-weight consonant-only acoustic profile selects the preferred lexical realization no better than random varṇa assignments / frequency**, on this candidate set and task. Per §0's interpretive scope, this **bounds this representation on this task**; it does **not** prove there are no latent acoustic principles, nor refute the exploratory order/vowel/transition variants, a different table, or the broader theory. At pilot N a null is **absence of evidence**, not strong evidence of absence. Any exploratory `*_CANDIDATE_SIGNAL` is hypothesis-generating only and triggers a separate, independently-frozen replication — never a validation claim. A `PILOT_POSITIVE` shows the representation **carries information**; it does **not** prove the ontology it came from.

---

## 11. Frozen artifacts (sha256-committed before any fit)

Composition rule + segmentation (§1); confirmatory/exploratory split (§2); synonym sets (§3); targets + ground truth (§4); Rubrics A/B + rubric + reliability floors (§5); fit metric (§6); controls + homophone list (§7); nulls, seeds, δ_min (§8); all thresholds; `lexicon_wordformation.json` hash; decision labels (§9).

---

## 12. What this does NOT test

No result is evidence about:
- **etymology** (historical origin),
- **contextual meaning** directly,
- **mythology** / symbolic / archetypal reference,
- **Chaldean / gematria numerology** or any letter-number system,
- **intention / identity resonance**,
- **Stage A SO(4)** operator structure,
- **full Symbol-U validation**.

It tests one narrow thing: whether an equal-weight, consonant-only, g2p acoustic profile predicts preferred lexical realization among synonyms, vs a scrambled table and a frequency baseline.

---

## 13. Primary limitation & Version B (preferred future protocol)

**The weakest link is the target → vṛtti profiling bridge (§5).** Mapping a target sense into the vṛtti space is an irreducibly subjective step; the insider-vs-naïve gate *measures* that subjectivity but cannot remove it. This document is therefore **Version A**.

**Version B (preferred; expected long-term protocol).** Remove the `target → vṛtti` bridge entirely. Instead, collect **pairwise human judgments of acoustic/felt qualities** directly among synonyms (e.g. "which of these two sounds harder / brighter / heavier?"), and compare that human acoustic ordering to the **table-derived** ordering, against a scrambled control. This tests the table against *perceived sound qualities* — the one channel that demonstrably exists (cf. the 0.83 bīja inter-judge agreement) — without ever asking anyone to assign a sense to a vṛtti. It is cleaner and less subjective, and avoids this design's main vulnerability. If/when Version B is run, Version A becomes a historical stepping stone rather than the final form.

---

## 14. Prohibitions

- **g2p tokenization only**; orthographic splitting forbidden ("believe ≠ be+lie+ve"). Orthographic and intention/identity axes are **excluded entirely**, not exploratory.
- **No driver/passenger weighting, vowels, or transition rules in the confirmatory arm** — exploratory only.
- **No post-hoc** synonym/candidate/target/ground-truth selection or mode-switching; all frozen (sha256) before any fit.
- **No changing** the table, composition, controls, or labels after results.
- **Homophone-invariance enforced** (leakage check, §7).
- **Stage A untouched**; **no fit computed** in this document.

> structure, not validated meaning.
