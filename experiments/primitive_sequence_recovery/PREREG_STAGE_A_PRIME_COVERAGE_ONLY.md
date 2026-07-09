# Pre-Registration — Stage A′ Coverage-Only Validation

**Status:** Pre-registration (docs-only). Fixes the **coverage-only** validation design for Stage A′ **before**
any code or data. Not code, not a dataset, not a run.
**Governed by:** `STAGE_A_PRIME_PHONEME_G2P_OPERATOR_LAYER_DESIGN.md` (`341ea1c`),
`B1_4B_STAGE_A_DECOMPOSITION_COVERAGE_AUDIT.md` (`0e2a346`), `SYMBOL_U_L2_VALIDATION_RULEBOOK.md`.
**Frozen Stage A untouched. No meaning validated. B1.4b remains blocked. Track B remains blocked. Structure,
not validated meaning.**

Grounding (read-only, not modified): `symbolu_neural/structural_v1/{features,operators}.py`.

---

## 1. Purpose

This pre-registers a **coverage-only** validation of the proposed Stage A′ phoneme/G2P operator layer. It fixes,
in advance, exactly what "adequate coverage" means and how it will be tested — **G2P/transliteration
normalization coverage, phoneme-inventory coverage, operator-construction sanity, orthogonality/reproducibility,
and a semantic-leakage audit** — so a future Stage A′ implementation cannot be tuned to a passing result. It
**validates no meaning**, builds no data, and authorizes no run. Its sole object is whether Stage A′ can
faithfully **decompose real words into operators**; it says nothing about whether those operators carry
semantic signal (they are expected not to — §15).

---

## 2. Starting state

- **B1.4b blocked at L1** — the frozen 14-grapheme chart yields only 14.0% (Sanskrit) / 9.8% (English) fully
  decomposable words; character-dropping is invalid for a real run (`STAGE_A_PARTIAL_DECOMPOSITION_BLOCKS_REAL_RUN`).
- **Stage A′ design ready** — `341ea1c`: `STAGE_A_PRIME_PHONEME_DESIGN_READY` +
  `STAGE_A_PRIME_COVERAGE_TARGETS_DEFINED` + `STAGE_A_PRIME_REQUIRES_PREREG`.
- **Frozen Stage A untouched** — Stage A′ is a **new versioned layer alongside**, never an edit to
  `symbolu_neural/structural_v1`.
- **No code, no data yet** — this document is the pre-registration that must be approved before any Stage A′
  build begins.

---

## 3. Coverage-only hypothesis

**H_cov (pre-registered):** a language-aware phoneme/G2P Stage A′ front end can decompose the candidate word
pools into a fixed phoneme inventory and construct operators such that **all** coverage targets (§7) and
operator-sanity checks (§10) are met, with **no semantic leakage** (§11).

This is an **engineering/structural** hypothesis about faithful decomposition and operator construction —
**not** a hypothesis about meaning.

---

## 4. Non-hypotheses (explicitly out of scope)

This pre-registration does **not** test, and passing it does **not** claim:

- that varṇa/phoneme operators carry **word-specific semantic/attribute signal**;
- that any F-over-Stage-A′ latent beats the phonological baseline;
- that Stage A′ validates the Symbol-U mapping, KCPR, or any ontology;
- anything about `Y`, decoders, or L3.

Coverage success is necessary plumbing, not evidence of meaning. All prior negatives stand and are **not**
reinterpreted.

---

## 5. Allowed inputs

Stage A′ (as tested here) may consume **only phonological/articulatory information**:

- phoneme inventory (identity), place, manner, voicing, sonority,
- vowel height, backness, rounding, length (if needed), aspiration (if needed),
- stress/prosody **only if separately justified and pre-registered** (default excluded).

All are properties of **sounds**, fixed before any run.

---

## 6. Forbidden inputs

Stage A′ may **never** consume: dictionary meaning; semantic categories; varṇa glosses; vṛtti meanings;
four-sphere labels; polarity meanings; KCPR poles; the target `Y`; attribute tables; any **post-hoc addition
based on test/coverage performance** (inventory or feature changes chosen after seeing results). Any breach →
`STAGE_A_PRIME_SEMANTIC_LEAKAGE_INVALID` (§11/§13).

---

## 7. Coverage targets (frozen pass thresholds)

Stage A′ **passes coverage** only if **all** hold on the frozen test pools (§8):

- **≥ 95% character/phoneme retention** — near-zero dropping after G2P/normalization.
- **≥ 90% fully decomposable words** — the large majority decompose with no unsupported units.
- **≥ 100 fully decomposable concepts overlapping an independent `Y`** — the faithful set that also has norm
  coverage clears the floor. *(This target is checkable only once a `Y` concept list is available; until then
  it is reported as PENDING and cannot be marked PASS.)*
- **No silent fallback** — every unsupported phoneme/character is reported, never coerced.
- **Unsupported units explicitly reported** — a per-run coverage log enumerating all drops.

Any target failed → `STAGE_A_PRIME_COVERAGE_FAIL`. The `Y`-overlap target PENDING → coverage cannot be declared
`PASS` (at most a partial, `Y`-independent pass on retention/decomposability, reported as such).

---

## 8. Test pools

- **Repo-local pools (primary, already present):** `frozen/word_list.json` (Sanskrit transliteration, 107
  non-excluded); the B1.3 English concrete-object candidate pool (92). These are the pools whose frozen-chart
  coverage was 14.0% / 9.8% and are the direct before/after comparison for Stage A′.
- **Track split:** the Sanskrit pool is tested under `A_PRIME_SA`; the English pool under `A_PRIME_EN`. Results
  are **reported per track**, never silently pooled.
- **No external datasets** are acquired for this coverage pre-registration; the `Y`-overlap target (§7) remains
  PENDING until a separately-approved `Y` concept list exists.
- The pool lists, their word counts, and the per-track assignment are **frozen** in the pre-registration
  amendment before any run.

---

## 9. Stage A′ outputs (what a run would produce)

For each word, Stage A′ would emit (all deterministic, logged):

- the **normalized phoneme sequence** (from the frozen G2P/transliteration rules),
- the **per-word coverage record**: retained phonemes, any **unsupported units** (explicitly listed), retention
  fraction, and a `full / partial / empty` decomposition flag,
- the **operator sequence** `M_σ` for the retained phonemes,
- a **run-level coverage report**: retention %, fully-decomposable %, empty count, unsupported-unit frequency
  table.

No semantic output, no `Y`, no F-3 scoring is produced by the coverage run.

---

## 10. Operator sanity checks

For every phoneme in the frozen inventory and every constructed `M_σ`:

- **Construction** — `M_σ = expm(Σ_j f_{σ,j} G_j)` builds without error for all inventory phonemes.
- **Orthogonality** — if skew-symmetric generators are used, verify `G_j = −G_jᵀ` and `M_σ M_σᵀ = I` within a
  pre-registered numerical tolerance (as frozen Stage A asserts). Non-orthogonal generator choices are out of
  scope for this coverage pre-registration.
- **Determinism / reproducibility** — identical inputs (and fixed seeds, if any) yield identical phoneme
  sequences and operators across repeated runs.
- **Finiteness / boundedness** — all feature values lie in the declared bounded range; no non-finite operator
  entries.

All checks pass → `STAGE_A_PRIME_OPERATOR_SANITY_PASS`; any failure → `STAGE_A_PRIME_OPERATOR_SANITY_FAIL`.

---

## 11. Semantic-leakage audit

A mandatory static + provenance audit that Stage A′ contains **no** forbidden input (§6):

- **Feature-chart provenance** — every feature dimension is articulatory/phonological with a documented,
  meaning-free source; no gloss/attribute/polarity/`Y`-derived value.
- **G2P/normalization rules** — map spelling→phonemes only; no lookup keyed on word meaning or attributes.
- **No target contact** — the layer never reads `Y`, decoders, KCPR, or any attribute table.
- **No performance-tuning** — inventory/features are fixed from linguistic standards, not adjusted after seeing
  coverage results.

Any breach → `STAGE_A_PRIME_SEMANTIC_LEAKAGE_INVALID` (dispositive; overrides any coverage/sanity pass).

---

## 12. Failure conditions

The coverage-only validation **fails / invalidates** if any hold:

- a coverage target (§7) is not met → `STAGE_A_PRIME_COVERAGE_FAIL`;
- an operator-sanity check (§10) fails → `STAGE_A_PRIME_OPERATOR_SANITY_FAIL`;
- any forbidden input reaches the layer (§11) → `STAGE_A_PRIME_SEMANTIC_LEAKAGE_INVALID`;
- silent fallback / unreported drops are detected → coverage fail;
- results are not reproducible / not deterministic → operator-sanity fail;
- the outcome cannot be resolved as specified → `STAGE_A_PRIME_INCONCLUSIVE`.

A leakage invalidation **overrides** any coverage or sanity pass.

---

## 13. Terminal labels

- **`STAGE_A_PRIME_COVERAGE_PASS`** — all coverage targets (§7) met on the frozen pools (with `Y`-overlap either
  met or explicitly reported as the only PENDING item, per §7).
- **`STAGE_A_PRIME_COVERAGE_FAIL`** — one or more coverage targets not met.
- **`STAGE_A_PRIME_OPERATOR_SANITY_PASS`** — construction/orthogonality/reproducibility/finiteness all pass.
- **`STAGE_A_PRIME_OPERATOR_SANITY_FAIL`** — any operator-sanity check fails.
- **`STAGE_A_PRIME_SEMANTIC_LEAKAGE_INVALID`** — a forbidden input entered the layer (dispositive).
- **`STAGE_A_PRIME_INCONCLUSIVE`** — the coverage question could not be resolved as specified.

No semantic/positive label exists here. **No `L1_L2_L3_ATTRIBUTE_SIGNAL`, no ONTOLOGICAL_SIGNAL, no Sanskrit
privilege.**

---

## 14. Relation to B1.4b

- Stage A′ coverage success **only unblocks L1 coverage**; it **does not validate meaning** and grants no
  semantic claim.
- Even a full `STAGE_A_PRIME_COVERAGE_PASS` + `STAGE_A_PRIME_OPERATOR_SANITY_PASS` leaves B1.4b **blocked** on
  its other gates (independent `Y`, the semantic pre-registration).
- Using Stage A′ in B1.4b requires a **new versioned study (B1.4b′)** that explicitly adopts Stage A′ as L1 —
  **never** a silent substitution into the existing B1.4b/B1.4a artifacts, which stay as-is.
- The F-3 **reversal-symmetry** limitation is inherited and must be carried into any B1.4b′ pre-registration.

---

## 15. Expected result

Coverage is expected to be **achievable** (a phoneme layer should decompose real words far better than the
14-grapheme chart) — but this is an **engineering** expectation, not a semantic one. Passing coverage **does
not** move the semantic prior: because Stage A′ is explicitly **phonology-derived**, the phonological baseline
remains **decisive and likely stronger**, so the expected downstream B1.4b′ outcome remains
`F_COLLAPSES_TO_PHONOLOGY → ⊥`. A faithful Stage A′ makes that eventual verdict **more trustworthy**, not more
favorable. A coverage pass is a substrate success, not evidence of meaning.

---

## 16. Next gate

After this pre-registration is approved, the next step is **implementation of the Stage A′ coverage harness
only** (G2P/normalizer + inventory + operator construction + the §10/§11 checks), run **on the repo-local pools
only**, producing the coverage report — **no `Y` acquisition, no F-3, no scoring, no semantic run**. Only if
coverage + sanity + leakage all pass, and separately if an independent `Y` clears its own gate, would a **new
B1.4b′** be considered under further authorization. No implementation is authorized by this document.

---

## 17. Boundary statement

> Stage A′ coverage-only pre-registration completed. Frozen Stage A untouched. No meaning validated. No dataset
> built. Nothing run or scored. B1.4b remains blocked. Track B remains blocked. Structure, not validated
> meaning.
