# B1.4b — Stage-A Decomposition Coverage Audit

**Status:** Coverage audit (docs-only). **No Y matrix, no dataset download, no run, no score.**
**Governed by:** `B1_4B_10_WORD_LAYER_TRACE_DIAGNOSTIC.md` (`7fd7b6e`), `B1_4B_REAL_DATA_PREP_AND_FREEZE_PLAN.md`,
`PREREG_B1_4B_L1_L2_L3_OPERATOR_INTERACTION.md`.
**No meaning validated. Track B remains blocked. Structure, not validated meaning.**

Grounding: `symbolu_neural/structural_v1/features.py` (imported read-only, **not modified**).

---

## 1. Purpose

Before any `Y` freeze, this audit measures whether B1.4b has **enough faithful L1 decomposition coverage** —
i.e. whether real candidate words decompose into the frozen operator chart **without losing characters**. The
10-word trace (`7fd7b6e`) already showed one hard failure (`vāyu`) and heavy character-dropping; this audit
quantifies the problem across the repo-local word pools. It builds no `Y`, runs nothing, and declares no signal.

---

## 2. Stage-A decomposition layer (the real frozen chart)

From `structural_v1/features.py` (read-only):

- **Supported units: 14.**
- **Supported graphemes:** `a, b, d, g, i, k, l, m, n, p, r, s, t, z` — **12 consonants + only 2 vowels
  (`a`, `i`)**.
- **Unsupported characters observed** (dropped in the pools below): the vowels **`e, o, u`**; consonants
  **`c, f, h, j, v, w, x, y`**; and all **diacritics** (`ā, ī, ū, ṛ, ṣ, ṇ, ś, ñ`, …).
- **No-silent-fallback behavior:** `decompose()` **drops** any out-of-chart character with an explicit warning
  and **never** coerces it to a default unit; a word with no chart characters returns an **empty** sequence
  (correct, not a crash).
- **Partial decomposition CAN occur:** a word with a mix of in-chart and out-of-chart characters yields a
  **shortened** unit sequence (the in-chart subset), silently *shorter* than the word — the core risk this
  audit targets.

**Reading:** this chart is a **minimal Stage-A structural testbed** (its own source calls the features
"provisional… not validated… not meaning-carrying"), **not** a faithful phonemic decomposer for real
vocabulary.

---

## 3. Source word pools checked (repo-local only)

- `frozen/word_list.json` — 107 non-excluded Sanskrit-transliteration words.
- `b1_3_revised_layer3/b1_3_human_modulation_concrete_object_candidate_wordlist.json` — 92 English
  concrete-object candidates.
- `b1_3_revised_layer3/b1_3_concrete_object_final_primary_wordlist.json` — present but uses a different
  item/word key (parsed as 0 by the flat reader); its words are a screened **subset** of the 92-candidate
  English pool, so the English coverage rate below applies to it as well.
- `b1_eval_wordlist.json` — empty / unrecognized structure (0 words).
- **No external datasets used.**

---

## 4. Coverage metrics (counts-only, real)

| Pool | Total | Fully decomposable | Partial (chars dropped) | Empty/fail | Char retention | Word retention (full) |
|---|---|---|---|---|---|---|
| `frozen/word_list.json` (Sanskrit) | 107 | **15** | 91 | 1 | **69.2%** | **14.0%** |
| concrete-object candidates (English) | 92 | **9** | 82 | 1 | **63.5%** | **9.8%** |

**Most frequent unsupported characters**
- Sanskrit pool: `ā`(27), `h`(24), `u`(19), `v`(17), `y`(12), `j`(8), `e`(7), `ṣ`(7), `o`(6), `ī`(6), `ṛ`(6), …
- English pool: `e`(64), `o`(36), `c`(17), `h`(14), `u`(13), `f`(9), `w`(8), `y`(4), `j`(2), `v`(2), `x`(1).

**Fully-decomposable Sanskrit words (all 15):** agni, manas, karma, nara, anna, rakta, rasa, bala, mitra,
naraka, sarpa, ratna, nagara, taila, tapas.

**Headline:** across both pools, only **~10–14%** of words decompose **without dropping characters**; **~85–90%**
decompose only **partially** (a third of characters lost on average). The missing vowels `e, o, u` alone
guarantee that most real words are partial.

---

## 5. Faithfulness criteria

- **`FULL_DECOMPOSITION_OK`** — every character maps to a chart unit; the operator trace faithfully represents
  the word. (15/107 Sanskrit; 9/92 English.)
- **`PARTIAL_DECOMPOSITION_RISK`** — some characters dropped; the unit sequence is a **truncated** version of
  the word, so F-3 is computed on a mutilated sequence. (≈91/107; ≈82/92.)
- **`EMPTY_DECOMPOSITION_FAIL`** — no chart characters; empty sequence, no operators. (1 each pool; e.g.
  `vāyu`.)
- **`CHARACTER_DROPPING_INVALID_FOR_REAL_RUN`** — a real evidence run must **not** score partially-decomposed
  words: dropping ~30–37% of characters means the L1 trace is unfaithful, so any F-3 / probe result would be a
  statement about a mangled sub-word, not the word. Partial words are therefore **invalid for a real run**, not
  merely noisy.

---

## 6. Impact on B1.4b

- **Only fully-decomposable words?** In principle yes — but that set is **~15 (Sanskrit) / ~9 (English)**, far
  below the pre-registered floor of ≥ ~100 concepts. Even pooled and de-duplicated it is well under 30.
- **A restricted concept universe?** The faithful universe is **too small** to power the F-3-vs-baselines
  contrasts; with < 30 faithful concepts the CV/permutation design has no power and the phonology co-primary
  cannot be meaningfully tested.
- **Or too thin?** **Yes.** Admitting partial words to reach the floor would violate
  `CHARACTER_DROPPING_INVALID_FOR_REAL_RUN`; refusing them leaves too few. **B1.4b's real L1→L2→L3 run is
  blocked at L1**, independent of the (already-unresolved) `Y` question.
- Proceeding would require **either** a faithful G2P→chart expansion (a **new/expanded operator layer** — out
  of scope here; it would change Stage A and must be a separate versioned study, not an edit) **or** accepting a
  < 30-word universe (underpowered). Neither is available now.

---

## 7. Interaction with `Y` selection

This tightens the `Y` gate further. `Y` must overlap the **fully-decomposable concept set** — **not** English
or Sanskrit words in general. The candidate norm sets (McRae/CSLB/Binder) are concrete-noun inventories in
**ordinary English orthography** (replete with `e, o, u, h, c, …`), so their intersection with a **14-grapheme,
a/i-only** faithful set is **near-empty**. Practically: even if a norm set were acquired, its overlap with the
faithful concept universe would fall far below the floor → `Y_TOO_COSTLY` / `Y_NOT_INDEPENDENT` at the coverage
step. The L1 coverage wall dominates the `Y` question.

---

## 8. Reversal-symmetry note (carried forward)

The F-3 limitation from the 10-word trace stands: the current commutator-magnitude summaries are **invariant to
full sequence reversal** (`‖[a,b]‖ = ‖[b,a]‖`; `‖prod − rprod‖` symmetric), demonstrated live by `jala` →
`a-l-a` (non-commutativity `0.000`). Non-reversal order sensitivity remains; any oriented/signed extension must
be separately pre-registered and cannot be added post-hoc. This is secondary to the coverage wall but remains
part of the frozen record.

---

## 9. Eligibility decision

**`STAGE_A_PARTIAL_DECOMPOSITION_BLOCKS_REAL_RUN`.**

- ~85–90% of real words in the repo-local pools decompose only **partially** (character-dropping), which is
  **invalid for a real run** (`CHARACTER_DROPPING_INVALID_FOR_REAL_RUN`).
- The residual **fully-decomposable** set (~15 / ~9) is simultaneously **`STAGE_A_COVERAGE_TOO_THIN`** —
  far below the ≥100 floor and underpowered.
- Net: the frozen 14-grapheme operator layer **cannot faithfully supply L1** for a real B1.4b concept set. The
  real L1→L2→L3 run is **blocked at L1**.

(Not `STAGE_A_COVERAGE_OK_FOR_RESTRICTED_B1_4B`: the restricted set is too small to power the design.
Not `STAGE_A_COVERAGE_INCONCLUSIVE`: the counts are decisive.)

---

## 10. Next gate

**B1.4b remains blocked** — now at **L1**, upstream of and in addition to the unresolved `Y` gate. To move,
one of the following would have to be separately proposed and approved (none is done here):

1. **A new/expanded faithful operator layer** — a documented G2P→unit mapping covering real graphemes/phonemes.
   This **changes Stage A** and therefore must be a **new versioned operator study**, not an edit to the frozen
   layer. Until it exists and passes its own structural gates, B1.4b cannot faithfully run.
2. **Accept a sub-30 faithful concept universe** — explicitly underpowered; would yield at best a labelled
   `INCONCLUSIVE` and cannot support a `Y` freeze; **not recommended**.

`Y`-source metadata acquisition is **not** worthwhile until (1) exists, because the faithful concept set it must
overlap is currently too small. No step is auto-triggered.

---

## 11. Boundary statement

> B1.4b Stage-A decomposition coverage audit completed. No Y matrix created. No semantic validation performed.
> No evidence freeze declared. Track B remains blocked. Structure, not validated meaning.
