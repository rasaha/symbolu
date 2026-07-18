# PRE-REGISTRATION — Acoustic-root / Object-profile Fit (Concrete-Object Pilot)

**Document type:** Pre-registration (confirmatory design for a feasibility/calibration pilot)
**Version:** 1.1
**Changelog:** v1.1 — added the exploratory-only vowel arm (§16); revised §0, §8, §13, §14 header, §15; the consonant-only confirmatory test and its seven §14 labels are unchanged. v1.0 — initial pre-registration.
**Status:** FROZEN. All artifacts in §13 are sha256-committed *before* any fit is computed. No element below may change after results are observed.
**Standing prohibitions:** No implementation in this document. Stage A (the SO(4) operator system) is **not used and not modified** by this pilot. No fit is computed here.

---

## 0. Background, rationale, and declared prior

The acoustic-root theory supplies a fixed *word-side* map (varṇa sequence → vṛtti profile). It lacks an independent *object-side* map (referent → vṛtti profile). This pilot tests whether the fixed word-side profile fits an **independently coded** object profile better than (a) scrambled varṇa tables and (b) mismatched objects, using only concrete objects whose properties are documentable without reference to their names or to any tradition.

**Scope caveat (binding).** The **primary confirmatory test is consonant-only**, using the **consonants** section of the worldly-vṛtti table (`lexicon_wordformation.json`; the file also contains a CANDIDATE/intuition-derived vowels section used only by the exploratory arm §16). Vowels are **not** part of the confirmatory test. A separate **exploratory-only vowel arm** (§16) is pre-registered using a frozen CANDIDATE/INTUITION-DERIVED vowel table; **it cannot change, upgrade, downgrade, or rescue the confirmatory consonant-only verdict (§14)** under any outcome. Consequently this pilot's confirmatory claim applies to the **consonant-only worldly-vṛtti map**, not to the full varṇa system; vowel results are hypothesis-generating signals requiring independent replication, never confirmation.

**Declared prior (stated before data).** Prior pre-registered tests on this lexicon returned NO_SIGNAL for lexical recovery, and the bīja↔sound-feeling test matched the table only ~15% (below chance) against the one independent perceptual channel available. The honest prior is therefore that the primary fit test returns **null**. A null is a valid, expected, publishable outcome. The pilot's principal scientific value is the **reliability and non-circularity checks** (§7): establishing whether an object→vṛtti profile can be coded reliably and non-circularly *at all*. If §7 fails, every fit result is undefined regardless of its value, and that is itself the finding.

## Hypotheses

- **H1 (fit):** the fixed-table word profile fits its own object's independently-coded profile above both nulls, under both rubrics.
- **H0 (null):** word-side profile carries no object-fit information beyond a scrambled table and beyond random object assignment.
- **Auxiliary (privilege):** if any fit exists, Sanskrit fit > other-language fit (directional, secondary).

This pilot can **bound or fail** H1; given N (see §11) it is **not** powered to establish H1 confirmatorily.

---

### 1. Object list (frozen)
The 12 concrete objects, no additions: **dog, cow, horse, elephant, lion, deer, snake, crow, fire, water, mountain, river.** Two classes: **animals** (dog, cow, horse, elephant, lion, deer, snake, crow); **natural elements/features** (fire, water, mountain, river). No deities, archetypes, mythological, or abstract objects. Synonym/variant resolution is fixed in §12, not here.

### 2. Name-blind object-property coding
"Name-blind" = coders are **phoneme-blind** (never shown any word, in any script) and **hypothesis-blind** (unaware that a sound–meaning link is under test). Object **identity is not hidden** (a behavioral dossier of a territorial domesticated carnivore *is* a dog; hiding that is impossible and unnecessary). What is withheld is the *sound* and the *purpose*. Each object is presented as a neutral ID plus a **standardized dossier** assembled by a separate "data librarian" from sound-independent third-party sources (ethology/physiology/cognition for animals; physical-science/geography for elements), one citation per property value. Coders rate **traits only**, never vṛttis (§5).

### 3. Strata
Five candidate strata: **physical, behavioral, emotional, cognitive, symbolic.**

### 4. Strata allowed in this pilot
- **Allowed (primary):** physical, behavioral, cognitive — genuinely independent third-party data.
- **Allowed (secondary, reported not gating):** emotional, only from pre-existing measured human-affect norms, flagged contamination-prone (human affect toward "snake/fire" is partly culturally/lexically shaped).
- **Excluded entirely:** **symbolic** — it imports tradition and is the primary circularity vector. Its exclusion defines this as a concrete-object pilot.

Two class-specific trait instruments (animal battery; element battery) feed one shared vṛtti codomain. Both frozen in advance.

### 5. Trait → vṛtti rubric — with independent alternate-rubric sensitivity (Rubric A / Rubric B)
- **Step 0 (shared):** operational definitions of each vṛtti in purely behavioral/dynamic terms, with no reference to sounds or to any §1 object (e.g. *ceṣṭā* = self-initiated effortful activity; *krūratā* = harm beyond functional need; *moha* = attachment-behavior persisting without reward; *jāḍya/sthiti* = inertia/stability).
- **Generic trait inventory (shared):** a fixed list of gradable dynamic/relational properties applicable across living and non-living objects (activity, harm/destructive potential, boundary-maintenance, stability/permanence, sustaining/nourishing quality, expansiveness, dependency, predictability, dominance-behavior, …). Authored from the trait inventory and Step-0 definitions **only — never the object list.**
- **Two rubrics, authored independently and frozen before any fitting:**
  - **Rubric A (primary):** a frozen matrix `[trait-dimension × level] → vṛtti weight vector`, each rule justified solely by a vṛtti's Step-0 definition, authored by Team A.
  - **Rubric B (sensitivity):** an independently authored matrix over the **same** trait inventory and **same** Step-0 definitions, by a separate Team B that does **not** see Rubric A. Same constraints.
  - Both are sha256-committed before object coding begins. Aggregation trait-vector → object vṛtti-vector is **mechanical** under each rubric.
- **Primacy and sensitivity rule (binding):**
  - **Rubric A is primary and dispositive for the null verdicts.** The verdict is determined **first** by Rubric A. **If Rubric A returns `TABLE_NULL` or `SPECIFICITY_NULL`, that is the verdict and Rubric B cannot rescue it** — Rubric B is not evaluated for the purpose of overturning a Rubric-A null.
  - **Rubric B affects the verdict only when Rubric A passes both nulls.** In that case: if Rubric B also passes both nulls → `PILOT_POSITIVE`; if Rubric B does not → `RUBRIC_DEPENDENT` (rubric-dependence, **not** confirmation).
  - Equivalently: Rubric B can only *downgrade* a Rubric-A pass to `RUBRIC_DEPENDENT`; it can never *upgrade* a Rubric-A null to a pass.

This isolates subjectivity to two measured/frozen places: trait coding (measured by IRR, §7) and the rubric (now *two* frozen rubrics, whose agreement is itself a sensitivity result). Coders never touch vṛttis.

### 6. Coder blinding
Two independent coder pools — **tradition-naïve** and **tradition-insider** — both phoneme-blind and hypothesis-blind, ≥5 coders each. They rate object dossiers on the trait inventory only. Librarian, rubric-author teams (A and B), and fit-analysts are mutually firewalled; no person spans roles.

### 7. Insider-vs-naïve reliability check (the non-circularity gate)
Krippendorff's α computed (a) within each pool, (b) **between** pools, on both raw trait ratings and the derived vṛtti vectors (per rubric). Floors: **α ≥ 0.67 required, ≥ 0.80 good.** If between-pool α is below floor, trait coding is carrying insider priors → circularity → the affected object/trait is disqualified, or the pilot is declared a measurement/circularity failure (§14). This is the decisive test that object profiles are not the tradition read back in.

### 8. Fit score
- **Object profile:** rubric (A or B) applied to blind trait codings → vṛtti vector in the shared space.
- **Word acoustic profile — three pre-registered composition variants**, each run identically through both nulls (§9–10) and both rubrics:
  - **(a) Consonant-only (PRIMARY / CONFIRMATORY):** sum of `worldly_vritti` one-hot **count vectors** over the word's consonantal varṇas (from frozen `lexicon_wordformation.json`, consonants section). **This variant alone determines the §14 verdict.**
  - **(b) Vowel-only (EXPLORATORY):** sum over the word's vowels using the frozen CANDIDATE vowel table (§16). Feeds only the §16 vowel arm.
  - **(c) Consonant+vowel (EXPLORATORY):** consonants (a) ∪ vowels (b) in one combined vector. Feeds only the §16 vowel arm.
- **Fit:** cosine similarity, L2-normalized, computed separately for (a), (b), (c). Order ignored in the primary; an ordered variant is a pre-registered secondary.
- **Caveat (declared):** words have 2–4 consonants → acoustic vectors are very sparse → intrinsically low resolution; sparsity is worse for vowel-only (b) (1–2 vowels/word) (§11).

### 9. Scrambled-table null
Permute `worldly_vritti` among consonants, **N = 1000** seeded scrambles; object profiles untouched. Recompute every word profile and the **mean diagonal fit**. Outcome per rubric: **PASS** if real-table mean diagonal fit > 95th percentile of scrambles (p_scramble < 0.05); **NULL** if real ≤ scramble median; **AMBIGUOUS** otherwise.

### 10. Object-permutation null
Full `[12 words × 12 objects]` fit matrix. Statistic **S = mean(diagonal) − mean(off-diagonal)**. Null from **N = 10⁴** random word↔object label permutations. Pre-registered minimum effect **δ_min = 0.10** (cosine units). Outcome per rubric: **PASS** if p_perm < 0.05 **and** bootstrap 90% CI lower bound of S > 0; **NULL** if S ≤ 0 **and** CI upper bound < δ_min; **AMBIGUOUS** otherwise.

A fit positive under a rubric requires **both** nulls = PASS.

### 11. Failure criteria & power
- Within- or between-pool α below floor → measurement/circularity failure (§14).
- Real fit not clearing scramble → table null. Diagonal not clearing off-diagonal → specificity null.
- **Power note (declared up front):** N = 12 with 2–4-consonant words gives **low power and low resolution**. This is a **calibration/feasibility** pilot, not confirmatory. `PILOT_POSITIVE` is intentionally hard to reach at N = 12 (the §10 CI criterion will rarely clear 0), to prevent over-claiming. A confirmatory run requires pre-registered expansion to **N ≥ 40** concrete nouns by a fixed inclusion rule (independent third-party data exists; no tradition/symbolic content). The expansion list + rule are committed now (§13) so they are not post-hoc.

### 12. Sanskrit vs multilingual (frozen language plan)
Object profiles are name-blind ⇒ **language-invariant**, enabling a diagnostic multilingual design.
- **Primary (gating): Sanskrit.** One word per object, fixed rule = **primary Monier-Williams entry for the basic concrete sense**, committed before profiling (forms locked in §13: dog=śvan, cow=go, horse=aśva, elephant=gaja, lion=siṃha, deer=mṛga, snake=sarpa, crow=kāka, fire=agni, water=jala, mountain=parvata, river=nadī). **No post-hoc synonym choice.**
- **Secondary (reported, not gating): English and one other (Hindi)**, words fixed by the same rule, to test (a) Sanskrit-specificity (directional: Sanskrit fit > other-language fit) and (b) the language-invariance consequence (most languages should mismatch a fixed object profile).
- **Strict:** the gating language is **Sanskrit, declared now.** No choosing the best-performing language after testing.

### 13. Frozen artifacts (sha256-committed before any fitting)
Object list (§1); both trait instruments (§4–5); vṛtti Step-0 definitions (§5); **Rubric A and Rubric B** (§5); per-object word selections for all three languages (§12); composition rule and all three variants (§8); both nulls, seeds, δ_min (§9–10); all thresholds and α-floors (§7, §11); directional predictions; N ≥ 40 expansion list + inclusion rule (§11); the **CANDIDATE / INTUITION-DERIVED vowel table** with its provenance label and the improvement margin **Δ_v** (§16).

---

### 14. Decision labels and decision algorithm
Exactly seven terminal labels. Evaluated in strict precedence order; the first matching condition is the verdict. **Rubric A is dispositive for steps 3–5; Rubric B is consulted only at steps 6–7, only after Rubric A has passed both nulls.**

The seven terminal labels are determined **solely by the consonant-only variant (a) under Rubric A** (with Rubric B acting only per §5). **No vowel result (§16) can change, upgrade, downgrade, or rescue any §14 label.** Vowel outcomes are reported as *separate secondary annotations* (§16), never as the verdict.

1. **MEASUREMENT_FAILURE** — within-pool α (either pool) < 0.67. Object trait coding is not reliable; no fit verdict is interpretable. *Terminal.*
2. **CIRCULARITY_FAILURE** — within-pool α ≥ 0.67 **but** between-pool (insider vs naïve) α < 0.67. Object profiles carry insider/tradition priors; the independence requirement fails. *Terminal.*
   *(If 1 or 2 fires, fit tests are not reported as evidence.)*
3. **TABLE_NULL** — reliability gates passed; under **Rubric A**, the scrambled-table test = NULL (real ≤ scramble median). The table's specific assignments carry no object-fit advantage over random assignments. **Rubric B is not evaluated to overturn this.** *Terminal.*
4. **SPECIFICITY_NULL** — reliability passed; under **Rubric A**, scramble cleared but the object-permutation test = NULL (S ≤ 0, CI upper < δ_min). Words do not fit their own objects more than random objects. **Rubric B is not evaluated to overturn this.** *Terminal.*
5. **INCONCLUSIVE_LOW_POWER** — reliability passed; under **Rubric A** at least one null test = AMBIGUOUS (neither PASS nor NULL), i.e. the data can neither clear nor positively confirm the null. The expected outcome at N = 12 if any signal-leaning trend exists. *Terminal.*
6. **RUBRIC_DEPENDENT** — reliability passed; **Rubric A** passes **both** nulls (PASS/PASS), but **Rubric B** does **not** (any NULL or AMBIGUOUS). Report rubric-dependence, **not** confirmation.
7. **PILOT_POSITIVE** — reliability passed; **both** Rubric A **and** Rubric B pass **both** nulls (scramble p < 0.05 and object-permutation p < 0.05 with CI lower bound > 0), under the Sanskrit gating language. Intentionally hard to reach at N = 12; if reached, it warrants the pre-registered N ≥ 40 confirmatory run, not a validation claim.

Secondary outputs (always reported, never change the label): per-rubric and per-language fit tables; Sanskrit-vs-other directional contrast; emotional-stratum exploratory fit; ordered-composition secondary.

### 15. Explicit NO_SIGNAL interpretation
A `TABLE_NULL` or `SPECIFICITY_NULL` verdict is reported as **NO_SIGNAL for object-profile fit**, with these bounded readings:
- **What it means:** within this model class (cosine fit over the worldly-vṛtti count space), this concrete-object set, this rubric, the Sanskrit gating word list, and the **consonant-only** word-side map (§0 scope caveat), the fixed varṇa→vṛtti table carries **no object-fit information beyond a scrambled table** (TABLE_NULL) and/or **no word-to-own-object specificity** (SPECIFICITY_NULL). It is concordant with prior NO_SIGNAL (lexical recovery) and the ~15% bīja↔sound-feeling mismatch.
- **What it does NOT mean:** it does not, by itself, refute the broader projection/kośa ontology, the diachronic-persistence hypothesis, the **full varṇa system including vowels**, or a *different* (e.g. empirically-derived) sound→propensity map. It bounds the **fixed consonant-worldly-vṛtti table's** object-fit in this regime only.
- **Power qualifier:** at N = 12, a null is **absence of evidence**, not strong evidence of absence. A confirmatory NO_SIGNAL claim requires the N ≥ 40 run. `INCONCLUSIVE_LOW_POWER` is reported plainly as such and is **not** dressed up as either support or refutation.
- **Asymmetry guard:** a `PILOT_POSITIVE` is treated as *hypothesis-generating only* (triggering the N ≥ 40 confirmatory pre-registration), never as validation; a `RUBRIC_DEPENDENT` result is treated as **non-confirmation** and reported as a sensitivity failure, not a partial win.
- **Vowel scope:** a consonant-only null is **not** weakened by any vowel annotation. If the vowel arm (§16) yields EXPLORATORY_ONLY or VOWEL_CANDIDATE_SIGNAL, that is logged as a replication-pending candidate against the intuition-derived table, and the confirmatory NO_SIGNAL (consonant-only) stands unchanged.

### 16. Vowel exploratory arm (secondary, non-confirmatory)

**16.1 Provenance label.** The vowel table is **CANDIDATE / INTUITION-DERIVED**, flagged as such everywhere it appears. Rationale: the Sarkar source treats vowels as acoustic roots of musical notes (ṣaḍja…), of creation/preservation/destruction (a/u/m), and of vocalization/cosmological functions — **not** as members of the 50-vṛtti scheme the consonants map to. Any vowel→vṛtti assignment is therefore interpretive, not source-grounded like the consonant table. It is **frozen and sha256-committed before testing** (§13), exactly like the confirmatory artifacts, but never inherits their evidentiary status.

**16.2 Three analyses.** Each of (a) consonant-only, (b) vowel-only, (c) consonant+vowel is run through the identical scramble null (§9), object-permutation null (§10), both rubrics (§5), and the Sanskrit gating words (§12), yielding per-variant PASS/NULL/AMBIGUOUS outcomes and effect size S (mean diagonal − off-diagonal).

**16.3 Non-upgrade rule (binding).** The confirmatory verdict is the §14 label from variant (a) under Rubric A. **Vowel variants (b)/(c) can never upgrade it.** The labels below are appended as annotations only.

**16.4 Pre-registered improvement margin.** "Improvement" of (c) over (a) = (c) clears a null that (a) did not (NULL/AMBIGUOUS→PASS), **or** S_(c) − S_(a) ≥ **Δ_v = 0.05** cosine units, with vowel-only (b) itself clearing the scramble null (so the gain is not pure dimensionality inflation). "Reduction" = S_(c) < S_(a), or vowel-only (b) ≤ scramble median.

**16.5 Vowel annotation labels** (evaluated in this precedence, after the §14 verdict is fixed):
1. **EXPLORATORY_ONLY** — variant (a) consonant-only **fails** (§14 = TABLE_NULL, SPECIFICITY_NULL, or INCONCLUSIVE_LOW_POWER) **but** variant (c) consonant+vowel passes both nulls. Reported as **exploratory only, NOT confirmation**: the confirmatory consonant map was insufficient and the apparent fit rests on the intuition-derived vowel table. **Requires independent replication**; the §14 verdict still stands as the (a) label.
2. **VOWEL_CANDIDATE_SIGNAL** — variant (a) did not fail outright and (c) **improves** over (a) per §16.4. A provisional candidate; **requires independent replication** on the N ≥ 40 set with a separately re-frozen vowel table before any interpretation.
3. **VOWEL_NOISE** — vowels **reduce** performance per §16.4 (or vowel-only (b) is null). Reported plainly: the candidate vowel table adds noise, not signal.
4. **VOWEL_NEUTRAL** (default) — vowels neither materially improve nor reduce performance; no candidate-signal claim.

**16.6 Interpretation guard.** EXPLORATORY_ONLY and VOWEL_CANDIDATE_SIGNAL are **hypothesis-generating only**. Because the vowel table is intuition-derived, a positive vowel annotation is a flag to *design a separate, source- or data-grounded vowel pre-registration*, not evidence for acoustic-root theory. A VOWEL_NOISE result is concordant with the declared prior. In no case does a vowel annotation convert a consonant-only null (NO_SIGNAL, §15) into support.

### Strict-prohibition compliance
No mythological objects (§1). No post-hoc illustrative readings (coding is mechanical from frozen rubrics). No changing varṇa glosses (table sha256-frozen, §13). No changing object profiles after results (traits + profiles hash-committed before the fit matrix is computed). No choosing the best language after testing (Sanskrit is the gating language, declared §12). Consonant-only confirmatory scope declared (§0); the vowel arm is exploratory-only, frozen, and non-upgrading (§16); the full varṇa system is not confirmatorily tested. Stage A not used or modified. No fit computed in this document.

---

**Reviewer-facing note.** The pilot's load-bearing result is §7/§14(1–2): whether an object→vṛtti profile can be coded **reliably and non-circularly** at all. If it cannot, the acoustic-fit program is undefined and the labels in §14(3–7) are moot. Only if §7 passes do the fit verdicts carry meaning — against the declared prior that they will read TABLE_NULL or INCONCLUSIVE_LOW_POWER, and within the consonant-only scope of §0.

> structure, not validated meaning.
