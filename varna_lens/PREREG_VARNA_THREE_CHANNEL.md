# PRE-REGISTRATION (DESIGN) — Varṇa Three-Channel Incremental Validity

**Document type:** Pre-registration design.
**Status:** DESIGN draft — no implementation, no data, no run, no freeze. Frozen-on-commit applies to the artifact list only once a run is approved.
**Standing prohibitions:** No implementation here. Stage A (the SO(4) operator system) is **not used and not modified**. No data collected, nothing computed.

**Core claim under test:** meaning has three distinguishable channels — **contextual**, **etymological**, **varṇa-indexed vṛtti** — and the question is whether the **varṇa channel adds measurable predictive information beyond the other two.**
**Method:** a **residual / nested incremental-validity** regression predicting an **independently-measured** target Y, with a scrambled-table null on the varṇa channel. This is *not* an alignment/RSA test and *not* a decoding test.

> **Read this first — the structural caveat.** If the varṇa channel is *real and affects how words are used*, then it is **already inside the contextual channel** (usage statistics absorb any real form–meaning regularity). In that case varṇa cannot add incrementally — not because it is false, but because it is **screened off** by context. This makes a null here **interpretively ambiguous** (empty vs. real-but-redundant). The design mitigates but cannot fully escape this; see §11 and the Decisiveness-asymmetry callout.

## 1. The three channels, operationalised
1. **Contextual (C).** A **form-blind**, word-level distributional embedding (e.g. word2vec/GloVe trained *without* subword/character n-grams), capturing usage meaning with **no spelling information**. *Sensitivity only:* a contextual-LM embedding (which encodes subwords) — flagged, never primary, because it leaks form.
2. **Etymological (E).** Categorical/structural features from an etymology database (etymological WordNet / Wiktionary-derived): source-language family, borrowing depth, root/morpheme membership, cognate class.
3. **Varṇa (V).** Word → varṇas by a **single frozen tokenizer** (declared in advance; native-IAST for the Sanskrit confirmatory set), → composed **equal-weight, consonant-only** over the frozen `lexicon_wordformation.json` vṛtti vocabulary → a varṇa feature vector. (Ordered/operator composition = exploratory only.)

## 2. Independently-measured target Y
**Y = pre-registered human norm profiles** rating the **concept**: affective norms (valence, arousal, dominance) and sensorimotor/concreteness norms (e.g. Warriner; Brysbaert; Lynott-style inventories). Human-rated, multi-dimensional, available at scale.

## 3. Circularity prevention (hard rule)
- Y must be **raw human ratings**, **not** derived from C, E, or V (no embedding-predicted norms, no etymology-built dimensions).
- No channel feature may be computed from Y.
- Any norm dimension known to have been constructed using word form or etymology is **excluded** from Y in advance.

## 4. Contextual baseline
Primary **C = form-blind word-level distributional embedding**; chosen so that *form-based variance is left available for V to claim* (an LM/subword embedding would silently absorb form and make the test unfair to V). Frozen model + version.

## 5. Etymological baseline
**E = etymology-family + source-language + root/morpheme + borrowing-depth features**, from a frozen etymological resource. Morphological-family membership recorded here (also used for group-CV, §9).

## 6. Varṇa representation
Frozen table → equal-weight consonant-only vṛtti composition (confirmatory). Nuisance covariates (frequency, length, register) are **forced into every model** so V cannot win through them.

## 7. Model comparison — **residual formulation (primary)** + nested-ΔR² equivalent

**Primary framing (conceptually clearest): the residual test.**
1. **Fit C + E first.** Cross-validated `Y ~ nuisance + C + E`; take **out-of-fold** predictions Ŷ_CE.
2. **Compute the residual.** `Y_residual = Y − Ŷ_CE` — the part of Y left unexplained by usage + origin (+ nuisance). *Must use out-of-fold Ŷ_CE; an in-sample residual is contaminated and is a LEAKAGE_FAILURE.*
3. **Test the varṇa channel on the residual.** Does **V(real)** predict `Y_residual`, and does it do so **better than V(scrambled)**?
   - `residual-R²(real)` = out-of-fold R² of `Y_residual ~ V(real)`.
   - `residual-R²(scrambled)` = distribution over N ≥ 1000 permuted tables.

This asks directly: *after context and etymology, is there structure left in Y that the **specific** varṇa table captures beyond a scrambled one?*

**Statistical equivalence (stated explicitly):** the residual test is equivalent to the incremental ΔR²(M3 − M2) of the nested models —
- **M1:** Y ~ nuisance + C
- **M2:** Y ~ nuisance + C + E
- **M3:** Y ~ nuisance + C + E + **V(real)**
- **M3′ (null):** Y ~ nuisance + C + E + **V(scrambled)**

— and both are reported. The residual form is **primary for interpretation** (it isolates "what's left for varṇa"); the nested ΔR² is the equivalent quantitative presentation. Same group-aware nested CV, bootstrap CIs over words, and scrambled-table null throughout.

## 8. Scrambled-table null
Permute varṇa→vṛtti assignment (N ≥ 1000 seeds); recompute V; refit M3′ / the residual fit; obtain the **residual-R²(scrambled)** (equivalently ΔR²(scrambled)) distribution. Real must exceed the **95th percentile**. Because real and scrambled V share **identical letters**, this isolates the *specific table* from *generic letter presence*.

## 9. Leakage controls
- **Spelling leakage:** C must be **form-blind** (verified: C cannot predict orthographic-neighbour status above chance). The **scrambled null** is the primary spelling control — real vs scrambled have identical letters, so any real−scrambled gap is *not* generic spelling.
- **Morphology leakage:** **group-aware CV by morpheme family** (whole families held out together); morphological variants deduplicated; morphology features in E.
- **Etymology leakage:** E partialled out in M2; **group-aware CV by etymology family** so test words are not etymological cousins of training words.
- **Synonym/frequency confounds:** frequency/length/register forced into all models; **synonym clusters kept within a single fold** (no straddling train/test).

## 10. Decision labels
- **VARNA_INCREMENTAL** *(the only positive)* — `residual-R²(real)` CI lower > 0 **and** > 95th pct of `residual-R²(scrambled)`, under primary + sensitivity, **replicated**. The specific table captures residual structure beyond context, etymology, and generic form.
- **TABLE_NULL** — `residual-R²(real)` > 0 **but ≤ the scrambled distribution** (real ≈ scrambled). Varṇa predicts some residual, but it is **generic form/letters, not the specific assignments.** *Stronger evidence against the specific table.*
- **SCREENED_OFF** *(replaces CONTEXT_ETYM_ONLY)* — C + E predict Y strongly and **V adds no residual signal** (`residual-R²(real)` CI includes 0). **Interpretation is ambiguous:** varṇa may be empty, **or** real but already absorbed into contextual usage. *Not strong disconfirmation.*
- **LEAKAGE_FAILURE** — any §9 check fails, or the residual was computed in-sample → run invalid.
- **INCONCLUSIVE** — low power / wide CI spanning 0 / primary–sensitivity disagreement.

*(The earlier CONTEXT_ETYM_ONLY label is removed and folded into SCREENED_OFF.)*

## 11. NO_SIGNAL interpretation
Both **TABLE_NULL** and **SCREENED_OFF** are NO_SIGNAL for the varṇa channel, but they are **not equally strong**, and must never be reported as if they were:

- **TABLE_NULL is the stronger result against the theory.** Real ≈ scrambled means the *specific varṇa→vṛtti assignments* add nothing beyond generic letter presence — a direct strike at the table itself, concordant with the prior lexical/bīja nulls.
- **SCREENED_OFF is not strong disconfirmation.** It is an **unresolved redundancy** result: C + E already explain Y, and varṇa contributes nothing *on top* — but this cannot distinguish *"varṇa is empty"* from *"varṇa is real and already inside usage."* Report it as ambiguous, never as a refutation.

So the evidential ordering against the theory is: **TABLE_NULL (strong) > SCREENED_OFF (weak/ambiguous)**, with **VARNA_INCREMENTAL** the only result that supports it.

## 12. What this test does NOT prove
- Not that the vṛtti meanings are "correct"; not composition/decoding; not the metaphysics; not Stage A.
- A **positive** shows only that varṇa carries *some* independent predictive information about Y beyond usage and origin — narrow and representational; it does **not** establish that the information is *meaning* rather than baked-in historical sound-symbolism (the scrambled null guards only the *specific-table* part).
- Incremental prediction ≠ causation or intrinsic meaning.

## 13. Comparison to the Boundaries design
- **Why distinct.** Boundaries controls for **generic iconicity** (orthographic O / articulatory P) and asks *"is the table iconic beyond generic form?"* Three-Channel controls for the **other two semantic channels** (C + E) and asks *"does the table add meaning beyond usage and origin?"* **Different baselines, different question, different machinery** (residual / incremental-validity regression vs RSA alignment).
- **Why it remains standalone.** Folding C + E into Boundaries would conflate two distinct controls (generic-form vs semantic-redundancy) and muddy both verdicts. Distinct baseline (C + E, not generic iconicity), distinct target (independently-measured human norms), distinct machinery. It is **not** to be folded into Boundaries.
- **Order.** Run the **cheap mechanical gates first** (B0; the Internal/External boundary tests), because they bound whether the table has *any* non-generic structure and cost far less. Run **Three-Channel after**, as the **theory-central** test: it needs more infrastructure (norms, form-blind embeddings, an etymology DB) and its prior is informed by the cheap gates. They are independent enough that strict ordering isn't required, but cheap-falsification-first is the efficient path.

---

## Decisiveness asymmetry (carry with every result)

> **A positive here is more theory-central than B0 / B / A; a null here is less decisive.** VARNA_INCREMENTAL would be the strongest result in the whole program — it is the most faithful test of the actual three-channel claim. But because a real varṇa effect, if it shaped usage, would already sit inside the contextual channel (the screening-off trap), a **SCREENED_OFF** null cannot refute the theory — only **TABLE_NULL** meaningfully can. Weigh the upside and the null asymmetrically: this design can *strongly confirm* or *weakly fail*, but it cannot *strongly refute* via SCREENED_OFF.

---

## Frozen artifacts (sha256 before analysis)
Core table; frozen varṇa tokenizer; form-blind contextual embedding model + version (C); etymological feature set + source DB (E); the human-norm target set Y + its source; nuisance covariate definitions; varṇa composition rule; group-CV family definitions (morpheme, etymology, synonym); scramble seeds + N; CV folds + seeds; bootstrap N; decision rule.

## Prohibited researcher degrees of freedom
No post-hoc choice of C/E/V representation, embedding model, or norm dimensions; no in-sample residual; no relaxing group-aware CV after seeing results; no dropping words/folds after seeing ΔR²; no reporting incremental ΔR² without the scrambled null; no relabeling SCREENED_OFF as refutation or VARNA-support.

## Skeptical assessment
**Strongest circularity / validity risk — the screening-off trap.** Distributional embeddings already encode essentially all *learnable* semantics — including any **real** form–meaning regularity present in the lexicon. So a genuinely real varṇa effect would **already be in C**, and the residual signal → 0. This means the design can return SCREENED_OFF **whether varṇa is empty or real-but-redundant** — they are not distinguished. Structural, not fixable by better statistics; partially mitigated by a form-blind C (leaves *some* form variance for V) and the scrambled null (isolates the specific table), but not resolved.

**Secondary risks.** (a) Achieving a *truly* form-blind C and clean group-CV (morpheme + etymology + synonym families all held out) is demanding; the realistic failure mode is **LEAKAGE_FAILURE** or an underpowered **INCONCLUSIVE**. (b) Etymology and varṇa are correlated (same-origin words share letters), so E may pre-empt much of V's apparent contribution — conservative, but it can mask a real effect.

**Likely failure mode.** **SCREENED_OFF** — a strong distributional baseline explains most of Y and the varṇa residual ≈ 0 — with the structural ambiguity above making it hard to call decisive.

**Is this more theory-central than B0 / B / A?** **Yes — it is the most faithful formalisation of the three-channel claim** ("does varṇa add beyond context and etymology"). B0/B/A test narrower iconicity/perception sub-claims. **But** it is also the version *most exposed* to the screening-off trap, so it is **most central and least decisive at once**: a positive would be the program's strongest result; a SCREENED_OFF null is genuinely ambiguous (see the Decisiveness-asymmetry callout).

---

> structure, not validated meaning.
