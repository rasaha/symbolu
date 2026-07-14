# Varṇa Feature-Lift Study — Preregistration V1 (auxiliary-signal utility, not semantic truth)

**Docs-only preregistration.** No feature computed, no model run, no words selected, no labels pulled, no result.
Outcome-blind: the design, controls, metrics, contrasts, and success/failure thresholds are fixed **before** any
evaluation. `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

**Reframe (the point of this study).** This does **not** test whether the varṇa mappings are "true meanings,"
recover dictionary meaning, uniquely identify words, or establish sound-symbolism as linguistic truth. It tests a
strictly weaker, engineering question: **does a frozen, pronunciation-derived varṇa feature provide useful
incremental signal on a measurable held-out task, beyond a strong base representation and beyond a shuffled-mapping
control?** A small, repeatable, cheap lift is a success; the feature does not need to "pass." Truth is not the
objective — measured utility is.

Does **not** modify the parser, lexicon, mappings, the Varṇa–Affliction Resolution Test (V1/V1.1), or any B1.x
artifact. This is a separate study (not B-numbered; a downstream-utility experiment).

---

## 1. Utility hypothesis (the only claim under test)

> **H_lift.** Adding a frozen varṇa-mapping feature `f(w)` to a base representation of a Sanskrit word improves
> held-out prediction of an **independent** affective target, and the improvement is **not** reproduced by a
> shuffled-mapping feature — i.e. the improvement is attributable to the *specific* varṇa→affliction assignments,
> not to prompt length, generic negative language, dimensionality, or regularization.

Null (default, assumed until shown otherwise): real and shuffled features perform equally, and/or neither beats
no-feature on held-out data.

## 2. Frozen inputs (read-only)

- Parser `sanskrit_stage1_parser.py` (`d885391f…`), `PARSER_SPEC_v1`; consonant occurrences only
  (`type=="consonant"`), matching the Resolution Test primary arm.
- Lexicon `frozen/varna_native_stage1_merged_v1.json` (`af4c1f54…`); **33 confirmatory-backbone consonants**,
  each with its verbatim frozen binding gloss.
- **Composition = multiset, no order** (multiplicity preserved via occurrence-level inclusion; order **not** used
  — consistent with the frozen AND-composition / no-progression theory). This makes the feature theory-faithful
  *and* sidesteps the order question entirely.

## 3. Target / labels (independent, non-circular) — fixed before any run

- **Source:** an established, public **affective-norms lexicon** for English words (e.g. NRC-VAD or
  Warriner et al. Valence/Arousal/Dominance) — a source produced with **zero** knowledge of Sanskrit phonology or
  the varṇa mappings. The exact lexicon + version is pinned at the pre-run freeze.
- **Mapping to words:** each attested Sanskrit word → its **single dominant ordinary English gloss** (recorded at
  word-precommit time); the gloss must exist in the norms lexicon or the word is excluded (recorded, not
  replaced).
- **Primary target: Arousal / Activation** — chosen because the frozen afflictions differ sharply in activation
  (e.g. *restless striving*, *craving* = activating; *inertia/torpor*, *defeatist collapse*, *self-doubt* =
  deactivating) even though they are uniformly negative in valence. **Secondary targets:** Valence, Dominance
  (reported, not primary — valence is expected to be low-discrimination because all binding glosses are negative).
- **Why non-circular:** labels are human affective ratings of English concepts, independent of the varṇa
  mappings and of Sanskrit phonology; the feature is derived from the frozen mappings. No shared source.

## 4. Feature encoding `f(w)` (fixed before any run)

`f(w) = (1/n) Σ_{i=1}^{n} e(a_i)` — **mean-pooled**, **multiplicity preserved**, **order-free**, where `e(a_i)` =
a **frozen sentence-embedding of the varṇa's exact binding gloss** from a pinned encoder (model id + revision +
hash fixed before results; the encoder is never tuned). `n` = consonant-occurrence count.
- **Secondary diagnostic encoding:** a 33-dim occurrence-count (bag-of-varṇa-identity) vector + linear probe —
  tests whether *identity* alone predicts, independent of gloss content. (Note: the shuffled control below is
  meaningful only for the gloss-content encoding, which is therefore primary.)

## 5. Three matched arms

For each word: **(none)** base features only · **(real)** base + `f_real(w)` · **(shuffled)** base +
`f_shuffled(w)`.
- **Base features:** the pinned base model's representation of the word's gloss (an LLM/text embedding) — so the
  test is whether the varṇa feature adds signal **on top of** what the model already encodes (the honest
  auxiliary-layer bar). A **secondary standalone** arm (feature alone vs. shuffled vs. chance) is also reported,
  to detect whether the mapping carries *any* affect signal even if the base already saturates it.
- **Shuffled control (critical):** a **random permutation of the 33-consonant → gloss bijection**, applied
  globally, then features recomputed. Repeated over **K ≥ 1000 permutation seeds** to form a null distribution.
  Shuffled preserves feature dimensionality, the pooling, multiplicity, *and the generic-negativity of the gloss
  pool* — so any real-vs-shuffled gap isolates the **specific assignments**.

## 6. Held-out protocol (leakage-controlled)

Nothing is tuned on the test words: the mappings are frozen (never fit to data); labels come from an independent
lexicon; the word list, gloss choices, encoder, base model, task head, and **all hyperparameters** are
**pre-committed before any test-set metric is seen**. Use a locked train/test split (or nested CV with an
outer test fold touched once). Report per-fold and pooled. Words used to *choose* encoder/hyperparameters (if
any dev tuning occurs) are disjoint from the test set.

## 7. Metrics & contrasts

Predict the continuous target; metric `M` = held-out **Spearman ρ** (primary) and **R²** (secondary) between
predicted and true norm (or AUC if binarized high/low, reported secondarily). Primary contrasts:
```
Δ_real-none     = M_real − M_none
Δ_real-shuffled = M_real − M_shuffled   (M_shuffled = mean over the K permutations)
```
- **Permutation p-value:** fraction of shuffle seeds with `M_shuffled ≥ M_real` (primary inferential test for
  `Δ_real-shuffled`).
- **Bootstrap CI** over words for `Δ_real-none`.
- Report across **≥ 3 seeds** and, where feasible, **≥ 2 base models**.
- **Leave-one-word-out** influence: recompute the effect dropping each word, to confirm the gain is **not
  concentrated** in one or two words.

## 8. Success criteria (a win — deliberately generous for a cheap auxiliary feature)

**All** of:
- `Δ_real-none > 0` **and** `Δ_real-shuffled > 0` on held-out data;
- permutation p ≤ 0.05 for `Δ_real-shuffled` (real beats the shuffled null);
- the bootstrap CI for `Δ_real-none` excludes 0;
- effect **consistent** in sign across seeds/models;
- effect **not** concentrated in ≤ 2 words (leave-one-word-out);
- no material degradation on an unrelated held-out sanity task (feature does not corrupt base signal).
**Even a small effect that meets these is a WIN** — grounds to keep the feature for further development. Magnitude
is reported honestly; a large effect is not required.

## 9. Failure / null conditions (reported, never softened)

- `Δ_real-shuffled ≈ 0` (real ≈ shuffled) → any apparent gain is length/negativity/dimensionality, **not** the
  specific mappings → the feature carries no assignment-specific signal.
- `Δ_real-none ≤ 0` → the base representation already saturates or the feature hurts.
- effect concentrated in ≤ 2 words, or sign-inconsistent across seeds/models → not a usable feature.
- Any of these is an honest, reportable negative; no post-hoc target/encoding switching to rescue it (the target,
  encoder, and word list are pre-committed).

## 10. Leakage & circularity audits (pre-declared)

- **Label independence:** the affective lexicon must predate / be independent of this project (recorded).
- **Base-model varṇa-naïveté:** confirm the base model has no special knowledge of the varṇa→affliction table
  (it is an obscure internal artifact); the feature must add signal the base lacks.
- **Shuffled = the negativity/length control:** the shuffled pool is the same 33 negative glosses, so a real
  advantage cannot be "generic negativity."
- **No per-word tuning; no target/encoder switching after seeing test metrics.**
- **Gloss→word translation caveat (disclosed):** the target is the affect of the *English gloss*, a translation
  proxy for the referent's affect; this is a known limitation, not a hidden assumption.

## 11. Relationship to the Varṇa–Affliction Resolution Test (kept separate)

The Resolution Test (V1/V1.1) is **not** the primary evidence for model utility and is **not** merged here. It
serves a different role: interpreting what the mappings claim, exposing embodiment/reconciliation patterns, and
**generating hypotheses** about which downstream targets are promising (e.g. it motivated *activation* as the
primary target). Utility is established by **representation → downstream task → held-out ablation → measured
lift**, not by resolution adjudication. No words, scores, or conclusions are imported across the two studies.

## 12. What a positive result would and would not establish

**Would:** that the specific frozen varṇa multiset carries **cheap, real, held-out incremental signal** for an
affective target — enough to justify keeping it as an auxiliary feature and investigating further. **Would not:**
that varṇas encode meaning as truth, that the mappings are "correct," that dictionary meaning is recovered, that
order matters, or anything universal/ontological. Utility ≠ truth; a useful weak signal is the entire claim.

## 13. Readiness

**`READY_FOR_PRERUN_FREEZE`** — the design, controls, contrasts, and thresholds are specified outcome-blind. The
next gate (a separate step) is a **pre-run freeze**: pin the exact norms lexicon+version, the encoder
id+revision+hash, the base model(s), the precommitted attested-word list with glosses, the split, and all
hyperparameters — **before** any metric is computed — then run §5–§7 and report §8–§9. This environment lacks the
ML dependencies (`torch`/`numpy`/embedding models), so the run occurs elsewhere; nothing is run here.

## Guardrails
Docs-only, outcome-blind. Utility (measured lift), not semantic truth. Parser, lexicon, mappings, the
Varṇa–Affliction Resolution Test, and all B1.x artifacts unchanged; no feature/label/run/freeze produced here.
Structure, not validated meaning.
