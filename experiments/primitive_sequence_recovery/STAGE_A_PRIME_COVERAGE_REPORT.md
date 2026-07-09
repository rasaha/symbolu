# Stage A′ — Coverage-Only Report (repo-local pools)

**Status:** Coverage-only run report (repo-local pools). **No Y, no F-3, no semantic scoring. Frozen Stage A
untouched.**
**Governed by:** `PREREG_STAGE_A_PRIME_COVERAGE_ONLY.md` (`e8ba2c9`),
`STAGE_A_PRIME_PHONEME_G2P_OPERATOR_LAYER_DESIGN.md` (`341ea1c`).
**No meaning validated. B1.4b remains blocked. Track B remains blocked. Structure, not validated meaning.**

Harness: `stage_a_prime_coverage.py` · tests: `test_stage_a_prime_coverage.py` (**11/11 PASS**).

---

## 1. What ran

The Stage A′ coverage harness normalized the two **repo-local** word pools into phonemes (per-track), built
operators `M_σ = expm(Σ_j f_{σ,j} G_j)` from articulatory features, and ran operator-sanity + a
semantic-leakage audit. It used **only** the `word`/`spelling` fields (never `dictionary_anchor` or any meaning
field), no external data, no `Y`, and no F-3.

---

## 2. Coverage results (before → after)

| Pool | Track | n | Full decomp. | Char retention | Frozen Stage A (was) |
|---|---|---|---|---|---|
| `frozen/word_list.json` (Sanskrit) | `A_PRIME_SA` | 107 | **107 (100%)** | **100%** | 15/107 (14.0%), 69.2% |
| concrete-object candidates (English) | `A_PRIME_EN` | 92 | **92 (100%)** | **100%** | 9/92 (9.8%), 63.5% |

- **Partial / empty / unsupported: 0** in both pools. `vāyu` (which failed the frozen 14-grapheme chart) now
  decomposes fully under `A_PRIME_SA` → `v aa y u`.
- **Repo-local coverage label:** `STAGE_A_PRIME_COVERAGE_PASS` (both pools clear the ≥95% retention and ≥90%
  full-word targets).

---

## 3. Operator sanity

`STAGE_A_PRIME_OPERATOR_SANITY_PASS` — for every phoneme in the inventory the operator builds deterministically,
is finite (no NaNs), is 4×4, and satisfies `M_σ M_σᵀ = I` (orthogonal; the four generators are skew-symmetric).
Reproducible across repeated construction.

---

## 4. Semantic-leakage audit

Audit **passes** (no findings): the feature schema is 4 finite articulatory floats in [−1, 1] per phoneme; all
normalization rules emit only inventory phonemes; the module reads no forbidden field (`dictionary_anchor`,
attribute/`Y`/gloss/polarity/KCPR). Stage A′ consumes **phonological/articulatory information only**.

---

## 5. Honest limitations (important)

- **`Y_OVERLAP_PENDING` — NOT a full final pass.** The third pre-registered target (≥100 fully-decomposable
  concepts overlapping an **independent `Y`**) cannot be checked because no `Y` concept list exists yet
  (coverage audit `0e2a346`). This report is therefore a **repo-local coverage pass only**; `final_pass =
  False`. A full Stage A′ pass requires a separately-approved `Y`.
- **100% reflects these pools' alphabets, not universal coverage.** The rule tables cover every
  character/diacritic *present in these two pools*; arbitrary vocabulary (other scripts, unusual symbols) could
  still surface unsupported units — which the harness would **report, not drop**.
- **Coverage-oriented G2P, not phonetically accurate.** `A_PRIME_EN` maps every grapheme to *some* phoneme
  (e.g. `c → k` always; silent letters not modeled). It maximizes **retention/decomposability**, the coverage
  metric — it is **not** a validated pronunciation model. `A_PRIME_SA` is a deterministic IAST normalizer, not
  a phonological theory.
- **Reversal-symmetry limitation inherited.** The downstream F-3 features remain invariant to full sequence
  reversal (recorded `7fd7b6e`/`0e2a346`); any oriented extension needs separate pre-registration.

---

## 6. What this does and does not mean

- **Does:** show that a phoneme/transliteration front end removes the L1 *coverage* wall on the repo-local
  pools, deterministically, with orthogonal operators and no leakage.
- **Does NOT:** validate meaning, beat any baseline, or unblock B1.4b. Because Stage A′ is explicitly
  phonology-derived, the phonological baseline stays **decisive and stronger**; the expected downstream outcome
  remains `F_COLLAPSES_TO_PHONOLOGY → ⊥`. A coverage pass is a **substrate** success, not evidence of meaning.

---

## 7. Next gate

A full Stage A′ pass, and any use in a **new B1.4b′** study, still require: (1) an independent `Y` concept list
to resolve `Y_OVERLAP_PENDING`, and (2) separate authorization. **No silent substitution** of Stage A′ into the
existing B1.4b/B1.4a artifacts. Nothing here is auto-triggered.

---

> Stage A′ coverage-only harness completed on repo-local pools. Frozen Stage A untouched. No meaning validated.
> No Y matrix created. Nothing semantically scored. B1.4b remains blocked. Track B remains blocked. Structure,
> not validated meaning.
