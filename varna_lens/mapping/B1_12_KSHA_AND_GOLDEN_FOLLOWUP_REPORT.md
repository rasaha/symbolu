# B1.12 Migration Follow-up — Golden Classification + क्ष Canonical Resolution

Bounded follow-up to the B1.12 mapping-source migration. Two jobs: (1) classify the remaining
golden-test failures and update **only** the safe ones; (2) resolve क्ष canonically per the
authoritative B1.12 `ksha_note`, without inventing a synthetic mapping.

---

## Part 1 — Golden classification

Every failing Layer-2/3/4 assertion was traced to its mechanism. **All 21 failing assertions share one
root cause:** the Layer-2 synthesizer maps each varṇa pole through `layer2_bridge_vocab.json` (64 terse
bridge phrases) via `H._canon(state)`, which keys on the pole's **Sanskrit label**. Under the old
lexicon the poles were `{sanskrit, english}` dicts (`_canon` → short label, e.g. `āśā`). Under B1.12
the poles are **prose strings** (`_canon` → the whole gloss), so the bridge vocab matches **nothing**:
measured coverage is **0/66 poles (0%)**, and every synthesis collapses to `[unresolved]`.

This is caused solely by the gloss replacement (**MAPPING_TEXT_ONLY** origin), but it is **not** a
text-only golden refresh: the "new output" is a degenerate `[unresolved]` string. Re-freezing that
would **mask** that the whole Layer-2 bridge is non-functional; re-keying the bridge requires either
re-authoring the 64 phrases against the new glosses (forbidden semantic authoring) or reading the old
lexicon to re-index them (forbidden old-lexicon dependency). None of the failing inputs
(`love`, `mercy`, `anger`, `peace`, `like`, `mantra`) contain `ksha` or `ś/ṣ`, so **none** are
KSHA_STRUCTURAL_EFFECT, SIBILANT_CORRECTION, or UNEXPECTED_REGRESSION.

| Test | Input(s) | Classification | Old output | New output | Recommended action |
|---|---|---|---|---|---|
| `test_layer2_bridge_vocab` — coverage ≥95% | all consonant glosses | MAPPING_TEXT_ONLY → bridge incompatibility | ≥95% covered | **0%** covered | Do **not** re-freeze; re-author bridge vocab (separate task) |
| `test_layer2_bridge_vocab` — love/mercy/anger/peace "no longer [unresolved]" | love, mercy, anger, peace | MAPPING_TEXT_ONLY → bridge incompatibility | real synthesis | `[unresolved] …` | Do not re-freeze (would mask) |
| `test_layer2_bridge_vocab` — "resolution due to exhaustive coverage" | — | MAPPING_TEXT_ONLY → bridge incompatibility | ≥95% | 0% | Do not re-freeze |
| `test_layer3_dictionary_bridge` — love L2 byte-identical | love | MAPPING_TEXT_ONLY → bridge incompatibility | `separative harshness moves toward compassion/gentleness, and order/dharmic relation is the resolving principle` | `[unresolved] moves toward [unresolved], and [unresolved] is the resolving principle` | Do not re-freeze |
| `test_layer4_attribute_check` — ≥1 SUPPORTED / ≥1 UNSUPPORTED (love, mercy, anger, peace) + love L2 | love, mercy, anger, peace | MAPPING_TEXT_ONLY → bridge incompatibility | mix of SUPPORTED/UNSUPPORTED attrs | all UNRESOLVED (no evidence path) | Do not re-freeze |
| `test_sample_text_rule_harness` — love synthesis == frozen text | love | MAPPING_TEXT_ONLY → bridge incompatibility | frozen synthesis | `[unresolved] …` | Do not re-freeze |
| `test_vowel_positional_polarity` — love L2 byte-identical (default) | love | MAPPING_TEXT_ONLY → bridge incompatibility | frozen synthesis | `[unresolved] …` | Do not re-freeze |
| `test_generation_conditioning_prompt_demo` — conditioning texts differ across arms | calm/"peace" | MAPPING_TEXT_ONLY → bridge incompatibility | arms A/R/S differ | all arms → identical `[unresolved]` | Do not re-freeze |

**Nothing classified as SIBILANT_CORRECTION, KSHA_STRUCTURAL_EFFECT, or UNEXPECTED_REGRESSION.** The
ś↔ṣ correction is already validated (regression on `ṣaṭ`/`śānti` + `test_ssa_glyph_join_respects_sibilant_swap`)
and is not asserted by any of the failing goldens. The `ksha` structural effects seen in the *renderer*
regression (previously `xozence`, `kṣamā`) are resolved by Part 3, not by a golden edit.

---

## Part 2 — Safe golden updates

**No golden was updated.** After classification, **zero** of the 21 failing assertions are safely
updatable:

* They are **not** simple text refreshes — they route through the stale `layer2_bridge_vocab.json`,
  which is keyed to the old `{sanskrit,english}` pole schema and yields 0% coverage on B1.12 string
  poles. Re-freezing their goldens to `[unresolved]` would **mask a genuine incompatibility**, which
  the task forbids.
* There are **no** SIBILANT_CORRECTION goldens among the failures to update.
* The renderer-lineage goldens that *are* safe (deterministic trajectory/roles/element/tone/reflection)
  already **pass** — `renderer_test`, `ontology_test`, `crs_pseudoword_test` are green, and the
  old-vs-new regression report is regenerated deterministically (now **0 structural diffs**).

**Genuine incompatibility, recorded not masked:** the Layer-2/3/4 exploratory synthesis harness needs a
bridge vocabulary authored for the B1.12 substrate. Producing one is semantic authoring (out of scope
for a mapping-source migration) and must be a separate, explicit task. Until then these tests are left
**failing on purpose**.

---

## Part 3 — क्ष resolved canonically (parser normalization)

Implemented a **narrow, deterministic parser normalization** in `varna_lens.py`, faithful to the
authoritative B1.12 `ksha_note` ("the parser decomposes क्ष → k + ṣ; kṣa is not a merged row"):

* The tokenizer recognizes the conjunct forms and records a transient `ksha` token; a normalization
  pass (`_normalize_conjuncts`) rewrites every `ksha` token to the atomic sequence **`[ka, ssa]` = k + ṣ**,
  in source order, before any drive lookup.
* `ka` and `ssa` resolve against the **authoritative B1.12 mappings** for k (`āśā …`) and ṣ
  (`kāma …` — the sibilant-corrected pole).
* **No synthetic ksha drive row** is invented: `ksha` is absent from `V.CONS`, the runtime lexicon, and
  the canonical mapping (its disposition is now `RESOLVED_BY_PARSER_DECOMPOSITION`).

**Supported forms that converge** to the identical canonical sequence `[ka, ssa]`:

| Form | Path | Result |
|---|---|---|
| `kṣ` (IAST) | `_CONS` → `ksha` → decompose | `ka, ssa` |
| `ksh` (ITRANS-style, added rule) | `_CONS` → `ksha` → decompose | `ka, ssa` |
| `x` | `_CONS` → `ksha` → decompose | `ka, ssa` |
| `kSh` (retroflex ASCII) | `k` + `Sh`→`ssa` directly | `ka, ssa` |
| Devanāgarī `क्ष` | **out of the roman parser's policy** (IAST/roman only); handled by the bridge lineage's Stage-1 parser, which already decomposes क्ष → k + ṣ | `k, ṣ` |

Order is preserved (k before ṣ); the same phonetic input always yields the same canonical sequence;
adding the `ksh` rule does not hijack `sh` (ś), `kh`, or `sha` (verified).

---

## Required invariants — checklist

| Invariant | Status |
|---|---|
| No synthetic semantic mapping for ksha | ✅ `ksha` absent from CONS / lexicon / canonical mapping |
| No fallback to the old lexicon | ✅ runtime resolves only the B1.12 lexicon; missing → hard error |
| No evaluator or scoring data enters runtime | ✅ guard suite `test_no_evaluator_fields_in_runtime_artifacts` |
| Same phonetic input → same canonical sequence | ✅ `test_same_input_same_sequence_deterministic` |
| क्ष, kṣ, and equivalents converge where policy allows | ✅ kṣ/ksh/x/kSh → `[ka, ssa]`; Devanāgarī handled by Stage-1 parser |
| Final sequence uses authoritative B1.12 mappings for k and ṣ | ✅ `test_decomposition_uses_authoritative_b1_12_k_and_ss` |
| Existing non-ksha outputs unchanged | ✅ old-vs-new regression: **0 structural diffs**; `test_non_conjunct_words_unchanged` |

---

## Validation results (by category)

| Suite | Result | Notes |
|---|---|---|
| B1.12 runtime guard (`test_b1_12_mapping_runtime`) | **PASS 11/11** | ksha disposition updated to decomposition |
| ksha normalization (`test_ksha_normalization`) | **PASS 9/9** | dedicated new suite |
| `renderer_test` | **PASS** | `xozence` now decomposes; structural invariants hold |
| `ontology_test`, `crs_pseudoword_test` | **PASS** | |
| Old-vs-new regression harness | **0 structural diffs**, 0 abstentions, 0 honesty violations | ksha structural effect eliminated |
| Layer-2/3/4 golden tests | **FAIL — 21 assertions** | genuine bridge-vocab incompatibility; not masked |

**Tests fixed by ksha normalization:** the renderer-lineage `ksha` structural effects (`xozence`,
`kṣamā`) — old-vs-new structural diffs went **7 → 0**; new dedicated ksha suite (9) added.
**Tests fixed by safe golden updates:** none (none were safe).
**Remaining failures:** the 21 Layer-2/3/4 bridge-vocab assertions (reported, not masked).

---

## Final report

1. **Which goldens were updated and why?** None. Every failing golden routes through the stale
   `layer2_bridge_vocab.json` (0% coverage on B1.12 string poles); refreshing them would mask a genuine
   incompatibility. The only golden-adjacent artifact regenerated is the deterministic old-vs-new
   regression report (now 0 structural diffs). Two `ksha` assertions in the guard suite were updated to
   the new decomposition behavior (not a golden refresh — a behavior-contract change from Part 3).
2. **Was ksha decomposed into k + ṣ?** Yes — deterministically, at parse time, via a narrow parser
   normalization; `[ka, ssa]` using the authoritative B1.12 k and ṣ mappings; no synthetic row.
3. **Which transliteration forms are supported?** `kṣ`, `ksh`, `x`, `kSh` converge in the roman/IAST
   parser; Devanāgarī `क्ष` is out of that parser's policy and is decomposed by the bridge lineage's
   Stage-1 parser. All converge to `k + ṣ`.
4. **Did any structural outputs change?** Yes, and only the intended one: words containing the conjunct
   (`xozence`, `kṣamā`) now decompose to k + ṣ instead of dropping an unmapped `ksha` beat. All
   non-conjunct outputs are byte-identical (regression: 0 structural diffs). No structural change was
   introduced by the mapping itself.
5. **Do all tests pass?** The B1.12 guard (11/11), ksha (9/9), renderer, ontology, and crs suites pass;
   the old-vs-new regression is clean. The 6 Layer-2/3/4 golden tests remain failing **by design** — a
   genuine bridge-vocab incompatibility that must be resolved by a separate re-authoring task, not by
   masking.
6. **Confirmation:** no synthetic ksha mapping was introduced; no evaluator/scoring data entered
   runtime; no fallback to the old lexicon.
