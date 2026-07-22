# PSE Varṇa Tool — B1.12 Mapping-Source Migration · Final Report

**Scope:** mapping-source replacement only. The PSE architecture, parser, decomposition rules,
trajectory/renderer, abstention, honesty, confidence, and LLM integration are unchanged. **No B1.12
evaluator, scoring protocol, relationship taxonomy, resonance magnitude, explanatory judgment, or
cross-model logic was merged into runtime.**

---

## 1. Migration comparison (done before implementation)

### 1.1 Artifacts

| | Old PSE mapping | B1.12 mapping (now authoritative) |
|---|---|---|
| Path | `varna_lens/lexicon_authoritative.json` | `experiments/primitive_sequence_recovery/frozen/varna_native_stage1_merged_v3.json` |
| sha256 | (retained, comparison only) | `65116f371aca9f24b...` (recorded in provenance) |
| Keyed by | verbose parser keys (`ka`, `kha`, … `ha`, `ksha`) | `canonical_parser_unit` (IAST `k`, `kh`, …) + `source_key` (`ka`, …) + `devanagari` |
| Drive shape | two poles `{sanskrit, english}` (consonants) / string (vowels) | two pole strings `binding_vritti` / `liberating_vritti` |
| Extra runtime-relevant fields | `iast`, `deva`, `varga`, `expanded_properties` (elemental imagery) | `activation_scope`, pole `provenance`, `category`, `aliases`, `parser_reachable` |
| Evaluator/scoring fields | none | **none** (BSR scores, relationship labels, verdicts, agreement live in *separate* B1.12 result dirs, not in this mapping file) |

### 1.2 Runtime consumers of the mapping (renderer/reflection lineage — the "PSE Varṇa Tool")

| Consumer | Reads | Fields used |
|---|---|---|
| `varna_lens.py` (engine) | mapping file | `iast`, `binding_state`, `liberating_state` |
| `pse_renderer.py` | mapping file | `expanded_properties.elemental` (imagery only) |
| `reflect.py` | mapping file | poles (glossary) + `expanded_properties` (`--rich`) |
| `sample_text_rule_harness.py` | via `varna_lens` | poles (transitively) |

> The Symbol-U concern bridge (`symbol_u_bridge/bridge_core.py`) already read the same B1.12 file
> directly, so this migration makes both PSE lineages share one authoritative varṇa→drive substrate.

### 1.3 Differences that had to be handled

| Dimension | Finding | Handling |
|---|---|---|
| Varṇa normalization / keys | v3 uses IAST canonical units; PSE uses verbose keys | Deterministic join by **devanāgarī glyph → source_key → canonical → alias**, priority-ordered |
| Transliteration / Unicode | ś↔ṣ swap corrected in v3 (`supersedes.correction`) | Glyph join maps ष→ṣ (kāma), श→ś (artha) — correction honored (test-guarded) |
| Polarity / pole encoding | v3 poles are single prose strings; engine `_pole_disp` already accepts strings (vowels always did) | Poles passed through **verbatim**; zero engine change |
| Gloss fields | v3 glosses are long prose (24–217 chars) | Preserved verbatim; `_short()` truncates at first `(` deterministically |
| Missing mappings | `ksha` (क्ष) absent by design (`ksha_note`: parser decomposes क्ष→k+ṣ) | Explicit abstention, surfaced as `(no lexicon entry)`; never back-filled |
| Duplicate/conflicting keys | none (adapter fails hard if a key resolves to >1 canonical unit) | Guarded |
| Null poles | only `ḷ`, candrabindu — both non-parser-reachable | Adapter fails hard on any null pole for a consumed key |
| Delimiter collisions | none (`→`, `⤳`, `⟹`, `«`, `»` absent from all glosses) | Verified |
| Elemental imagery | not present in v3 | Preserved as renderer **presentation scaffolding** (not a drive mapping, not invented) |

---

## 2. What was replaced, and with what

* **Replaced:** the varṇa→drive payload (`binding_state` / `liberating_state`) formerly sourced from
  `lexicon_authoritative.json`.
* **Authoritative source now:** the B1.12 frozen mapping `varna_native_stage1_merged_v3.json`
  (`binding_vritti` / `liberating_vritti`, verbatim), consumed through a generated, engine-shaped
  `varna_lens/lexicon_b1_12.json`.
* **Adapter:** `varna_lens/tools/build_varna_mapping_from_b1_12.py` — deterministic, no LLM, no
  authored interpretation; fails explicitly on missing/duplicate/conflicting/null/malformed entries;
  refuses to run if any evaluator/scoring field is detected in the source. It emits:
  * `varna_lens/mapping/varna_mapping_b1_12_canonical.json` (canonical contract: `binding_drive`,
    `liberating_drive`, `mechanical_metadata`),
  * `varna_lens/lexicon_b1_12.json` (engine-shaped runtime file),
  * `varna_lens/mapping/PROVENANCE_B1_12_MAPPING.json` (source + generated-file hashes, coverage).
* **Included from B1.12:** frozen varṇa keys, both vṛtti poles, pole polarity provenance,
  `activation_scope`, `category`, `aliases`, devanāgarī, iast, source version + sha256.
* **Excluded from B1.12 (and asserted absent):** BSR/0–100 scores, relationship-type labels,
  opposition/implication/consequence/no-relationship judgments, evaluator prose, cross-model
  agreement, per-word verdicts, evaluator-derived confidence, any LLM output.

---

## 3. Validation results

| Check | Result |
|---|---|
| Every consumed varṇa resolves against B1.12 or triggers explicit abstention | ✅ 33/34 cons + 12/12 vow mapped; `ksha` → explicit abstention |
| No silent fallback to the old mapping | ✅ missing mapping raises `FileNotFoundError`; default = `lexicon_b1_12.json` |
| No B1.12 evaluator output in runtime | ✅ `test_no_evaluator_fields_in_runtime_artifacts` (and source is a pure mapping) |
| Deterministic decomposition/profile | ✅ adapter byte-identical across runs; `test_adapter_is_deterministic` |
| Unicode/transliteration aliases resolve consistently | ✅ glyph join; ś↔ṣ swap guarded |
| Duplicate/conflicting entries surfaced, not silently selected | ✅ adapter raises on multi-canonical resolution |
| Provenance + hashes recorded | ✅ `PROVENANCE_B1_12_MAPPING.json`; sha matches source (`test_provenance_sha_matches_source`) |
| Old mapping retained only as comparison artifact | ✅ on disk, never the active runtime source |
| Runtime guard suite | ✅ `test_b1_12_mapping_runtime.py` **11/11 PASS** |

---

## 4. Old-vs-new regression (objective; see `MIGRATION_OLD_VS_NEW_REPORT.md`)

24-word corpus (English hybrid/g2p + IAST Sanskrit):

* **Drive/gloss (`essence_short`) changed: 24/24** — this is the intended mapping swap.
* **Structural fields changed: 7 field-diffs, confined to 2 words** (`xozence`, `kṣamā`), **100%
  attributable to the single `ksha` abstention** (both words contain क्ष). No word whose varṇas are
  all mapped changed any structural field (valence, trajectory roles, controlling element, tone,
  deterministic reflection, honesty).
* **New abstentions: 2** (both `ksha`), surfaced explicitly.
* **Honesty violations introduced: 0.**

**Existing PSE test corpus under the new mapping** (recorded, not "fixed"):

| Test | Result | Cause |
|---|---|---|
| `renderer_test.py` | **PASS** | structural invariants (roles/⤳/honesty/single-metaphor/determinism) unaffected |
| `ontology_test.py`, `crs_pseudoword_test.py` | **PASS** | structure-level assertions |
| `test_b1_12_mapping_runtime.py` | **PASS (11/11)** | new guard suite |
| `test_layer2_bridge_vocab.py`, `test_layer3_dictionary_bridge.py`, `test_layer4_attribute_check.py`, `test_sample_text_rule_harness.py`, `test_vowel_positional_polarity.py`, `test_generation_conditioning_prompt_demo.py` | **FAIL** | frozen **byte-identical / gloss-coverage goldens** pinned to the *old* drive text; they necessarily change when the drive payload changes. **Expected consequence of the swap — not a code defect.** Deliberately left unmodified so the change is not hidden. |
| `bija_vrtti_test.py`, `convergence_test.py` | n/a | CLI tools requiring `--emit`/`--score`, not auto-run assertions |
| `archetype_test.py`, `archetype_recovery_test.py`, `signal_test.py` | not run to completion | falsification harnesses needing LLM/wordnet judge backends; unrelated to mapping correctness |

*The Layer-2/3/4 golden failures confirm the swap reached the synthesis path and changed only the
drive text; the synthesis rules themselves are unchanged. Re-freezing those goldens is a separate,
explicit decision and was intentionally not taken here.*

---

## 5. Attribution protection

No dynamic weighting, authored stance hint, relationship scoring, or concern-specific interpretation
was added. The runtime symbolic payload for PSE (and Arm D) is now exactly **PSE architecture + the
B1.12 frozen mapping substrate**, with the only deviation being the one source-documented `ksha`
abstention. This keeps a later D−C attribution interpretable: the drive substrate is a single,
hash-pinned frozen artifact with no evaluator-derived signal mixed in.

---

## 6. Final answers

1. **Which old PSE mapping was replaced?** `varna_lens/lexicon_authoritative.json` (the renderer/
   reflection lineage's varṇa→drive payload). Retained on disk as a comparison artifact only.
2. **Which B1.12 mapping became authoritative?** `experiments/primitive_sequence_recovery/frozen/
   varna_native_stage1_merged_v3.json` (sha `65116f371aca9f24...`), via the generated
   `varna_lens/lexicon_b1_12.json`.
3. **Were any entries transformed?** No drive value was transformed — both poles are verbatim. Only
   *re-keying* (glyph/source_key join to PSE parser keys) and *carrier shape* (string poles, already
   supported) were adapted. Display/imagery scaffolding (iast, deva, varga, elemental) was preserved
   unchanged; it is not a drive mapping and is not present in B1.12.
4. **Were any mappings missing or conflicting?** One missing by design: `ksha` (क्ष) — v3 has no
   compound row (decomposes to k+ṣ) → explicit abstention. No conflicts (the adapter fails hard on
   any). The ś↔ṣ sibilant swap in v3 is honored via glyph join.
5. **Which PSE outputs changed?** The drive glosses in the essence chain (all words). Derived
   structure (valence, trajectory roles, controlling element, tone, deterministic reflection,
   honesty) changed only for the 2 corpus words containing the now-abstained `ksha`. Frozen
   Layer-2/3/4 golden-text tests changed accordingly.
6. **Did all tests pass?** The new runtime guard suite passes 11/11; `renderer_test`, `ontology_test`,
   `crs_pseudoword_test` pass. The Layer-2/3/4 golden tests fail as an **expected** consequence of the
   drive-text change and were left unmodified for transparency.
7. **Confirmation:** only the varṇa→drive mapping source changed. No B1.12 scoring machinery
   (evaluator, BSR/0–100 scores, relationship taxonomy, resonance magnitudes, explanatory judgments,
   cross-model logic) was merged into runtime — asserted by the adapter guard and by
   `test_no_evaluator_fields_in_runtime_artifacts`.

---

## 7. Deliverables

| Deliverable | Path |
|---|---|
| Normalized authoritative mapping (canonical contract) | `varna_lens/mapping/varna_mapping_b1_12_canonical.json` |
| Engine-shaped runtime mapping | `varna_lens/lexicon_b1_12.json` |
| Deterministic adapter | `varna_lens/tools/build_varna_mapping_from_b1_12.py` |
| Provenance manifest (hashes, coverage) | `varna_lens/mapping/PROVENANCE_B1_12_MAPPING.json` |
| Updated loaders | `varna_lens/varna_lens.py`, `pse_renderer.py`, `reflect.py` |
| Old-vs-new regression report | `varna_lens/mapping/MIGRATION_OLD_VS_NEW_REPORT.md` |
| Regression harness | `varna_lens/tools/regression_old_vs_new.py`, `tools/_regression_dump.py` |
| Runtime guard tests (no evaluator fields) | `varna_lens/test_b1_12_mapping_runtime.py` |
| This report | `varna_lens/mapping/B1_12_MAPPING_MIGRATION_FINAL_REPORT.md` |
