# B1.4b — Target-`Y` Admissibility Audit

**Status:** Target-source admissibility audit (docs-only). Not a run, not a dataset, not code.
**Governed by:** `PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`, `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`,
`VARNA_ATTRIBUTE_KCPR_EXPERIMENT_RULES.md`.
**No meaning validated. No dataset built. Nothing run or scored. Track B remains blocked.**
**Structure, not validated meaning.**

Gate being resolved: B1.4b pre-reg §16 — *implementation planning may proceed only if `Y` can be
independently specified; else stop with `Y_NOT_INDEPENDENT`.*

---

## 1. Purpose

This audit decides whether an **independent target `Y`** exists for B1.4b — a measured attribute/propensity
target that F-3 could be tested to predict **without** circularity. It tests **nothing** and builds no data.
Its single deliverable is a terminal admissibility decision (§9) that either opens implementation planning or
stops B1.4b.

Standing constraint carried from the candidate-F spec: the L1 operators are **phonology-parameterized**, so any
`Y` must be one against which a **phonological baseline** can be run (§7). Admissibility of `Y` does **not**
imply F-3 will beat that baseline; the prior stays negative.

---

## 2. `Y` admissibility standard

`Y` is admissible only if **all** hold:

- **Independently measured** — collected by a process unrelated to Symbol-U (existing norms or blinded new
  ratings), not produced from the varṇa pipeline.
- **Not derived from varṇa glosses** — no varṇa/vṛtti/sphere/polarity meaning feeds `Y`.
- **Not dictionary-definition matching** — `Y` is not the word's definition, nor a match-to-definition score.
- **Not target-fitted after seeing F-3** — `Y` is fixed **before** any F-3 feature is computed or fit; no
  peeking.
- **Usable before model fitting/scoring** — available and frozen prior to any decoder/probe fitting.
- **Baseline-testable** — supports scoring F-3 against the full baseline suite (esp. phonology + sentiment).
- **Interpretable as an attribute/propensity target** — a *profile of attributes*, not merely word identity or
  a lexical ID.

Failing any one → inadmissible (not "weak," out of scope).

---

## 3. Candidate `Y` sources

Audited (with representative independent datasets where they exist):

1. **Blind human attribute ratings** (new collection; raters blind to varṇas/F-3/hypothesis)
2. **Existing semantic feature norms** (e.g. McRae 2005; Binder 2016; Buchanan/QCM; CSLB)
3. **Valence / Arousal / Dominance norms** (e.g. Warriner 2013; NRC-VAD)
4. **Concreteness / imageability / familiarity norms** (e.g. Brysbaert 2014; MRC)
5. **Behavioral association norms** (e.g. Small World of Words, De Deyne; USF/Nelson)
6. **Lexical sentiment datasets** (e.g. NRC EmoLex; SentiWordNet)
7. **Dictionary/gloss-derived feature labels** (features read off definitions/WordNet glosses)
8. **LLM-generated attribute ratings** (a model rates concepts on attribute dimensions)
9. **Task-specific human pairwise judgments** (forced-choice attribute comparisons, blinded)

---

## 4. Per-source assessment

Legend: Independence / Gloss-leakage / Phonology-or-sentiment confound / Scalability / Cost — **Low / Med /
High**. "Attribute?" = interpretable as an attribute/propensity profile.

| # | Source | Independence | Gloss leakage | Attribute? | Phon/sentiment confound | Scalability | Cost | Admissibility |
|---|---|---|---|---|---|---|---|---|
| 1 | **Blind human attribute ratings** | High | Low (if blinded) | **Yes** | Med (control needed) | Med | **High** (new data) | **Admissible** (gold, but costly) |
| 2 | **Semantic feature norms** (McRae/Binder/CSLB) | High | Low (human-produced, not gloss) | **Yes (strongly)** | Med | Med (fixed word lists) | **Low** (exists, free) | **Admissible — preferred** |
| 3 | **VAD norms** | High | Low | Weak (affective, not attribute) | **High (≈ sentiment)** | High | Low | **Admissible only as confound control**, not primary `Y` |
| 4 | **Concreteness/imageability** | High | Low | Weak | Med–High (freq/phonology) | High | Low | **Admissible only as covariate/control** |
| 5 | **Behavioral association norms** (SWOW/USF) | High | Low | Partial (associates, not attributes) | Med | Med | Low | **Admissible — secondary** |
| 6 | **Lexical sentiment** (EmoLex) | High | Low | No (polarity only) | **High (is the sentiment baseline)** | High | Low | **Rejected as primary** (collapses to sentiment baseline) |
| 7 | **Dictionary/gloss-derived labels** | Low | **High (definitional)** | Yes-but-circular | Med | High | Low | **REJECTED** — gloss leakage |
| 8 | **LLM-generated attribute ratings** | Low–Med | **High/unauditable** | Yes-looking | High (LLM encodes phonology+sentiment) | High | Low | **REJECTED as primary** (decoder-in-disguise; unauditable) |
| 9 | **Task-specific human pairwise judgments** | High | Low (if blinded) | Yes | Med | Low | **High** | **Admissible** (expensive; good for confirmation) |

---

## 5. Preferred `Y` candidates

Strongest admissible candidates, with limitations stated plainly:

- **#2 Established semantic feature-production norms (McRae / Binder / CSLB) — primary.** Human-produced
  attribute features per concept ("is_dangerous", "has_fur", "used_for_X"), collected independently of any
  dictionary definition and of Symbol-U. Gloss-independent, attribute-structured, **free and already frozen**.
  *Limitations:* fixed (mostly concrete-noun) vocabularies; sparse/long-tailed features; English; coverage may
  not intersect the varṇa word set cleanly.
- **#1 Blind human attribute ratings — gold, if funded.** Purpose-built, blinded, best-controlled. *Limitation:*
  real cost and time; overkill before a cheap norm-based screen.
- **#5 Behavioral association norms — secondary/triangulation.** Independent and large. *Limitation:*
  associations are not attributes; noisier mapping to a propensity profile.

Recommended primary `Y` = **#2**, with **#5** as triangulation and **#1/#9** reserved for confirmation. **#3/#4
(VAD, concreteness) are demoted to confound controls**, never the primary target (§6/§7).

---

## 6. Rejected / high-risk `Y` candidates

- **#7 Dictionary/gloss-derived feature labels — rejected.** Reading features off definitions/WordNet glosses
  makes `Y` the dictionary meaning in disguise; predicting it would be circular exactly as the rulebook
  forbids.
- **#8 Unconstrained LLM-generated attributes — rejected as primary.** The LLM sees the word and encodes its
  meaning, sentiment, **and phonology**; its "attributes" are unauditable for leakage and effectively a
  decoder output, not an independent measurement. It cannot serve as the target a decoder is validated
  against.
- **#6 Lexical sentiment as primary — rejected.** Sentiment is already a required *baseline*; using it as `Y`
  guarantees the sentiment baseline explains the result (`SEMANTIC_OR_SENTIMENT_BASELINE_EXPLAINS`).

---

## 7. Phonology-baseline implication

Because the L1 operators are parameterized by phonological features, **every `Y` must be tested against (a) a
plain phonological-feature predictor and (b) a phonological-similarity control**, as co-primary to the run.
Concretely for the preferred `Y`:

- If a phonology-only predictor predicts the feature norms `Y` as well as F-3 does, the result is
  `F_COLLAPSES_TO_PHONOLOGY` regardless of how "semantic" `Y` looks.
- VAD/concreteness/frequency must enter as **nuisance covariates** (partialled out), because they correlate
  with both phonology and the norms and could manufacture a spurious F-3↔`Y` link.

Admissibility of `Y` therefore does **not** lower the bar; it makes the phonology contrast the decisive test,
consistent with the negative prior.

---

## 8. Minimum viable `Y` design (if admissible)

Smallest acceptable `Y`, to be frozen **before** any F-3 feature is computed:

- **Concepts:** ≥ ~100 words that (a) have frozen entries in the chosen independent norm set (#2) and (b) admit
  a clean cmudict→varṇa decomposition; pre-listed and frozen.
- **Attributes:** ≥ ~10–20 attribute dimensions per concept from the norm set (or a pre-declared reduction,
  e.g. a fixed feature subset / fixed low-rank projection declared in advance).
- **Blind rating protocol (if #1 used):** raters see the **concept only**, never varṇas, F-3, arm labels, or
  the hypothesis; fixed rubric; randomized item order.
- **Rater blinding:** enforced and documented; a leak check on instructions.
- **Exclusion rules:** drop items lacking norm coverage or clean decomposition; drop raters failing attention
  checks; all rules fixed in advance.
- **Reliability threshold:** pre-registered inter-rater / split-half reliability floor (e.g. ICC or
  Spearman-Brown ≥ a declared value); attributes below floor are dropped **before** fitting.
- **Freeze:** `Y`, the concept list, the attribute set, exclusions, and covariates are **hash-frozen before
  F-3 is fit or scored**. No post-hoc changes.

---

## 9. Terminal decision

**`Y_ADMISSIBLE_FOR_B1_4B_PREP`** — conditioned on the constraints below.

Rationale, held honestly:

- **At least one admissible, independent, attribute-structured `Y` exists:** established human-produced
  **semantic feature norms (#2)**, gloss-independent and already frozen. So the gate question — *can `Y` be
  independently specified?* — is **yes**. Declaring `Y_NOT_INDEPENDENT` or `Y_INCONCLUSIVE` would be false
  pessimism given these datasets exist.
- **Conditions of admissibility (all mandatory):** (i) primary `Y` = independent feature-production norms (#2),
  not gloss-derived (#7) or LLM-generated (#8); (ii) VAD/concreteness/sentiment used **only** as confound
  controls, or the label becomes `Y_ONLY_SENTIMENT_OR_PHONOLOGY`; (iii) phonology baselines co-primary (§7);
  (iv) `Y` frozen before F-3 fitting (§8).
- **This is not encouragement.** Admissibility of `Y` does not touch the negative prior. The expected B1.4b
  outcome remains `F_COLLAPSES_TO_PHONOLOGY → ⊥`; a clean `Y` simply makes that verdict *trustworthy* rather
  than avoidable.

(Labels considered and not selected: `Y_NOT_INDEPENDENT` — false, #2 is independent; `Y_TOO_COSTLY_FOR_CURRENT_STAGE`
— false for #2/#5, which are free existing norms; `Y_ONLY_SENTIMENT_OR_PHONOLOGY` — would apply **only if** the
program fell back to #3/#4/#6 as primary, which the conditions forbid; `Y_INCONCLUSIVE` — false, the question
resolves.)

---

## 10. Next-step gate

Because the decision is `Y_ADMISSIBLE_FOR_B1_4B_PREP`, the next step is **implementation *planning*** (not
implementation), and only under the §9 conditions:

1. Select and **freeze** the primary independent norm set (#2), the concept list, the attribute set, covariates,
   exclusions, and reliability floor (a pre-registration amendment).
2. Freeze the phonology and sentiment baselines as co-primary controls.
3. Only then, under explicit operator authorization, proceed to the B1.4b synthetic harness (pre-reg §13).

If, at freezing, the chosen norm set cannot be secured gloss-independently, or coverage/decomposition leaves
too few items, **B1.4b does not proceed** and the decision reverts to `Y_NOT_INDEPENDENT` /
`Y_TOO_COSTLY_FOR_CURRENT_STAGE`. No implementation, dataset, or run is authorized by this document.

---

## 11. Boundary statement

> B1.4b target-Y admissibility audit completed. No meaning validated. No dataset built. Nothing run or scored.
> Track B remains blocked. Structure, not validated meaning.
