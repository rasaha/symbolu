# MILESTONE_A_PRIME_PREREGISTRATION

> **STATUS — Run-time PRE-REGISTRATION for Milestone A′. DRAFT (not yet frozen).**
> Documentation only. No dataset downloaded, no values inspected, no code, no analysis, no
> Stage A / structural_v1 change, ⊥ preserved. Datasets selected by published, citable
> properties; committed before any data is touched. Binding only after the §11 sha256 freeze.
> A′ is a **falsifier**, not support-seeking validation. **structure, not validated meaning.**

## 0. Object and gate
Estimand: `I(Y ; E | Phonology)` — do gloss-independent sound-symbolism dimensions carry
conditional information about a semantic observable **beyond phonology**, from existing public
data. A′ tests the **additive/atomic** branch only (existing data cannot probe order); per the
revised roadmap an atomic null does **not** logically falsify order-dependent L2 — it is decisive
for the additive branch and a labelled resource stop.

## 1. Selected E / Y / Phonology pairing (committed)
**E (primary, gloss-independent) — dimensions: D1 size/magnitude, D2 shape (angular–round).**
A per-phoneme table constructed (frozen rule, §11) from this exact source set, all measured on
**meaning-free nonwords/pseudowords**:
- Sapir, E. (1929), *J. Exp. Psychol.* 12(3):225–239 — vowel magnitude (size).
- Newman, S. S. (1933), *Am. J. Psychol.* 45(1):53–75 — vowel/consonant size & brightness.
- Köhler, W. (1929/1947), *Gestalt Psychology* — takete/maluma (shape).
- Ramachandran & Hubbard (2001), *J. Consciousness Studies* 8(12):3–34 — bouba/kiki (shape).
- Nielsen & Rendall (2011), *Can. J. Exp. Psychol.* 65(2):115–124 — consonant shape mapping.
- D'Onofrio (2014), *Language and Speech* 57(3):367–393 — pseudoword shape gradience.
- Thompson & Estes (2011), *QJEP* 64(12):2392–2404 — graded sound-symbolic size/shape.
- Knoeferle, Li, Maggioni & Spence (2017), *Sci. Rep.* 7:5562 — feature-level size & shape cues.

**E (secondary, NON-admissible as primary — confounded ceiling):** Winter et al. English
iconicity ratings. Rejected as primary (iconicity is rated **against meaning** → violates §2.3).
Used only as a generous ceiling: **decisive on the null side**; a positive is confounded and
non-decisive.

**Y (primary confirmatory) — semantic SIZE, matched to E-D1:**
- Scott, Keitel, Becirspahic, Yao & Sereno (2019), *Behav. Res. Methods* 51:1258–1270 — **The
  Glasgow Norms**, SIZE scale (primary).
- Robustness alternate: Lynott, Connell, Banks, Brysbaert et al. (2020), **Lancaster
  Sensorimotor Norms** (magnitude-related), *Behav. Res. Methods*.

**Y (secondary/sensitivity):** Warriner, Kuperman & Brysbaert (2013) VAD norms (~13.9k lemmas);
static lexical **embeddings** (fastText/GloVe). Exploratory only.

**Phonology (baseline to beat):** CMU Pronouncing Dictionary v0.7b (word→ARPABET); PanPhon
(Mortensen et al. 2016) per-phoneme articulatory feature vectors; S1/S2 acoustic summary set
(mean sonority, vowel height/backness, voicing ratio, manner proportions, syllable count).
Frequency from SUBTLEX-US (Brysbaert & New 2009).

**Common item set:** `CMUdict ∩ Glasgow-SIZE ∩ E-coverable` English words; one pronunciation per
word; coverage/attrition documented. **Language = English** for maximal coverage/power;
explicitly **not** a Sanskrit-privilege test.

## 2. Justification against A′ §2 admissibility
| §2 criterion | Primary pairing | Verdict |
|---|---|---|
| 1 public/citable | CMUdict, Glasgow Norms, PanPhon, SUBTLEX, listed nonword studies | ✅ |
| 2 externally measured | all third-party | ✅ |
| 3 gloss-independent | primary E from **meaning-free** nonword studies (size/shape) | ✅ (iconicity fails → secondary) |
| 4 not Sanskrit-gloss-derived | English resources | ✅ |
| 5 sound-symbolic ratings | nonword size/shape dimensions | ✅ |
| 6 unit-mappable | phoneme-level E + phoneme features via CMUdict | ✅ |
| 7 sample size | thousands (CMUdict∩Glasgow); feasibility gated numerically (§9.0) | ✅ gated |
| 8 paired semantic observable | Glasgow SIZE as Y | ✅ |

## 3. Feature freeze
Frozen blocks (no post-hoc additions):
- **E_feat:** per-word aggregates of frozen per-phoneme D1/D2 values (§4).
- **PHON_feat:** per-word aggregates of PanPhon articulatory features + acoustic summary set.
- **BAG_feat:** phoneme-count vector (unordered) — bag-of-units control.
- **NUIS_feat:** word length (phonemes & letters), syllable count, log SUBTLEX frequency.
- **SENT_feat (QUARANTINED — exploratory only):** a public sentiment-lexicon score. **Excluded
  from every confirmatory model** because it is derived from / correlated with affective ratings
  and can leak `Y` (and is in any case off-axis for a size endpoint). Used only in clearly-marked
  exploratory VAD analyses, never in the confirmatory ladder.

## 4. Aggregation rules
Per word, each per-phoneme value set aggregated by a **fixed, generous** rule {mean, sum, min,
max} over the phoneme sequence, **identically** for E_feat and PHON_feat (neither side
advantaged). Order/position deliberately excluded (additive branch). BAG_feat = raw counts.
Frozen; no per-dimension tuning.

## 5. CMI estimator (numpy-feasible confirmatory; optional deps marked)
- **Confirmatory predictive estimator — ridge regression (numpy only).** Closed-form
  `β = (XᵀX + λI)⁻¹Xᵀy` on z-scored features; `λ` chosen by **leakage-free nested GCV** over the
  frozen grid `λ ∈ {0.01,0.1,1,10,100}×n` inside training folds (procedure frozen, not a value).
  Out-of-fold **ΔR²** of `Y~[PHON+E]` vs `Y~[PHON]` is the operational signal. No scipy/sklearn
  required (uses `numpy.linalg` only).
- **Confirmatory CMI — linear-Gaussian / partial correlation (numpy only).** Partial correlation
  of `Y` and `E_feat` given `PHON_feat` via residualization with closed-form ridge; reported with
  the relabel null (§7). Numpy-only.
- **OPTIONAL sensitivity (marked dependency, NON-decisive):** (a) gradient-boosted trees
  **[requires scikit-learn]** to check whether nonlinearity overturns a null; (b) KSG k-NN CMI
  **[requires a `digamma` implementation — numpy-codeable, or scipy.special]**. Neither affects
  the confirmatory decision; both run only if their dependency is present and are reported as
  sensitivity. If absent, A′ proceeds on the numpy-only confirmatory estimators.
- **Interpretation (frozen):** OOF ΔR² **lower-bounds** true CMI but **upper-bounds** what a
  constrained gloss-independent downstream model recovers — the decision-relevant quantity. The
  linear confirmatory is deliberately **conservative**; the optional GBT sensitivity guards
  against a linear-only false null. Significance is never read from a raw MI point estimate
  without the relabel null.

## 6. Incremental predictive baselines (confirmatory ladder — SENT excluded)
Same OOF folds throughout:
1. `PHON_feat` alone — conditioning floor (the baseline E must beat).
2. `PHON_feat + E_feat` — test contrast (decisive: 2 vs 1 > 0).
3. `PHON_feat + BAG_feat` — bag-of-units control.
4. `NUIS_feat`, and `NUIS_feat + E_feat` — length/frequency control.
E passes only if it adds over **phonology specifically** (2 ≫ 1) and is not subsumed by 3–4.
SENT_feat appears **only** in exploratory VAD analyses (§10), never here.

## 7. Relabel / null controls
- **Relabel null:** permute the phoneme→E-value assignment **K=1000×** (marginals preserved),
  recompute E_feat, refit, build the ΔR² null; real E must exceed the **95th percentile**.
- **Random-E control:** replace per-phoneme E with random values matched to E's marginals (K×).
- Calibrate the estimator's tendency to manufacture signal from noise.

## 8. K / folds / random seeds (frozen)
- Permutations: **K=1000** (relabel and random each).
- CV: **10-fold, grouped by lemma/stem** (no inflectional leakage), **repeated 5×** → 50 OOF
  estimates averaged.
- Bootstrap CIs: **2000** grouped resamples.
- Seeds (fixed ints): CV repeats `[101,102,103,104,105]`; permutation RNG `20260629`; bootstrap
  `4242`; ridge/init `7`. No time- or entropy-based randomness.

## 9. Decision procedure — feasibility first, then PASS vs ⊥/FAIL (cleanly separated)

**§9.0 Feasibility gate → INCONCLUSIVE (computed on inputs only; no `Y` values touched).**
Evaluated *before* any test. If **any** fails → **INCONCLUSIVE** (no inference, no ⊥): re-pair or
re-power A′; **do not** proceed.
- **Effective N:** unique lemma groups in the common item set **N_eff ≥ 800** (power floor to
  detect partial-r ≥ 0.10 at 80%, α=.05 two-sided: N ≈ (1.96+0.842)²/0.10² + 2 ≈ 786 → 800).
- **Coverage:** E table covers **≥ 90%** of phoneme tokens; per item **≥ 90%** of phonemes
  covered (else drop item); if **> 20%** of items dropped → INCONCLUSIVE.
- **Collinearity (E vs PHON, no Y):** unique E variance `U = 1 − R²(E_feat ~ PHON_feat)`.
  INCONCLUSIVE if **mean U < 0.10**, or **any** retained E dimension `U < 0.05`, or **max VIF
  > 10** among combined features, or **max canonical correlation(E,PHON) > 0.95**.

**§9.1 Test (only if §9.0 passes) → PASS vs ⊥/FAIL (mutually exclusive, both are real inferences).**
- **PASS (A′ clears the gate):** on the **primary endpoint (Glasgow SIZE)**, incremental
  partial-r ≥ **0.10**, bootstrap 95% CI **excludes 0**, **and** statistic **> relabel-null 95th
  pct**, **and** not eliminated by the acoustic/articulatory baseline (E beats phonology
  specifically), after §10 correction.
- **⊥ / FAIL (genuine negative → terminate):** feasibility met **and** incremental partial-r
  **< 0.05**, or CI includes 0, or ≤ relabel-null 95th pct on the primary endpoint → **return ⊥**,
  terminate per roadmap (additive-branch caveat). If the confounded-ceiling E **also** nulls,
  report the negative as strong.
- **Marginal (0.05 ≤ partial-r < 0.10, feasibility met):** **suggestive, not a pass** → repeat
  with larger/better-separated pairing; not ⊥.

Clean separation: ⊥/FAIL is reachable **only** when §9.0 feasibility is satisfied; an
infeasible run is **INCONCLUSIVE**, never ⊥.

## 10. Multiple-comparison correction
- **Single primary confirmatory endpoint: Glasgow SIZE** (matched to E-D1). One test → no
  confirmatory inflation.
- **Secondary (Holm–Bonferroni within family, exploratory):** VAD valence/arousal/dominance;
  Lancaster magnitude (robustness); E-D2 shape (no standard matched Y → reported descriptively).
- **Exploratory (own-family correction, never folded into the confirmatory decision):** iconicity
  ceiling; embedding-Y; any SENT_feat analysis.

## 11. sha256 freeze procedure
1. **Before any Y join or value inspection:** write as immutable files — (a) per-phoneme E table
   + the extraction rule (z-score each source's reported per-phoneme values on D1/D2; ±1 coding
   where only categorical poles are reported; average across covering sources); (b) item list
   (keys only, no Y); (c) PHON/NUIS feature tables; (d) the source-citation manifest; (e) this
   pre-registration; (f) seed/K/threshold config.
2. Record the **sha256 of each artifact** in this document's freeze block.
3. Only after all hashes are recorded may Glasgow SIZE values be joined and §5–§10 run.
4. Any post-freeze change = **logged amendment** (new hash, date, rationale) **before** unblinding.

## 12. Gate rule — no downstream work without an A′ PASS (binding)
**No Milestone B–G work begins unless A′ returns PASS (§9.1).** Explicitly includes the **B.0
synthetic harness**, any `F` (L2), any decoder (L3), and all comparative work (G). **⊥/FAIL →
terminate** (labelled resource stop, additive-branch caveat). **INCONCLUSIVE → re-pair/re-power
A′ only.** Hard precondition, not a soft preference.

## Recommendation — Y operationalization (UPDATED; overrides prior VAD-primary suggestion)
**Primary confirmatory `Y` = a semantic SIZE norm (Glasgow SIZE); VAD demoted to
secondary/exploratory.** Reason: the *gloss-independent* primary `E` resolves to **size/magnitude
and shape** dimensions (the robust, replicated nonword effects), not affect. Valence is therefore
**theoretically mismatched** to `E` and is the wrong sole primary endpoint; testing E-magnitude
against a semantic **size** observable is the strongest a-priori sound-symbolism→meaning link.
VAD remains valuable as a secondary check (does size/shape E incidentally predict affect beyond
phonology?) but cannot be the confirmatory endpoint. Admissibility does not reject either Y; the
switch is driven by **construct alignment with the selected E dimensions**, exactly the re-check
requested. If a size norm proves infeasible (coverage/N), the pre-registered fallback is Lancaster
magnitude as primary, then VAD only if no size-like observable clears §9.0.

---
> **A′ is a falsifier · No dataset downloaded · No values inspected · No code · ⊥ preserved ·
> Stage A untouched.** **structure, not validated meaning.**
