# B1.6 — Pilot Target/Scaffold Instantiation Report

**Status:** Instantiation package (docs + manifest + data only). Freezes the actual B1.6 pilot target set and
its instantiated Symbol-U scaffolds so a later generation run can proceed **after an operator evidence freeze**.
**No code, no generation run, no judging, no generated outputs, no evidence freeze.**
**B1.4b′ remains `NULL_RETURN_BOTTOM` and is not reinterpreted. No ontology, no Sanskrit privilege, no validated
meaning, no `ONTOLOGICAL_SIGNAL`, no `L1_L2_L3_ATTRIBUTE_SIGNAL`. Original B1.4b remains blocked. Track B remains
blocked. Structure, not validated meaning.**

**Readiness label: `B1_6_PILOT_SCAFFOLD_INSTANTIATION_READY`.**

Data/manifests: `frozen/b1_6_pilot_targets_scaffolds.json`, `frozen/b1_6_pilot_randomized_control_manifest.json`,
`frozen/b1_6_pilot_scaffold_manifest.json`.
Builds on: prereg (`c1f5028`), prompts/rubric (`17a5ea0`), freeze plan (`1244335`), bridge (`b680063`),
English aspirate amendment (`a629329`), KCPR rulebook (`1937b9f`), KCPR theory accommodation (`029d990`).

---

## 1. Preflight source verification

All required source artifacts verified present and hashed (sha256, 16-char prefix):

| Artifact | sha256 (16) |
|---|---|
| `B1_6_SYMBOLU_GENERATIVE_UTILITY_PREREG.md` | `66db9e67a6f300f0` |
| `B1_6_SYMBOLU_GENERATIVE_UTILITY_PROMPTS_AND_RUBRIC.md` | `080a67086c863156` |
| `B1_6_PILOT_TARGET_SET_AND_SCAFFOLD_FREEZE_PLAN.md` | `196763a368566059` |
| `B1_6_PHONEME_TO_VARNA_BRIDGE_SPEC.md` | `92bf5ec304e75aaa` |
| `frozen/b1_6_phoneme_to_varna_bridge_manifest.json` | `d1851c4abd431ead` |
| `B1_6_PHONEME_TO_VARNA_BRIDGE_ENGLISH_ASPIRATE_AMENDMENT.md` | `5b5e5322ac98df4f` |
| `B1_6_KCPR_POLE_SELECTION_RULEBOOK.md` | `130195313ad25cfb` |
| `frozen/b1_6_kcpr_pole_selection_manifest.json` | `fc5103d7e4c2aba4` |
| `B1_6_KCPR_THEORY_ACCOMMODATION_AUDIT.md` | `81e383ff628b62d4` |
| `B1_6_KCPR_THEORY_AMENDMENT.md` | `f441c84b1e081f36` |
| `track_g_varna_polarity_table.json` | `5f78224c06850788` |
| `track_e_varna_sphere_lexicon.json` | `cf5f8a33d472cae7` |
| `track_g_polarity_axes.json` | `37631d84eb50a611` |
| `stage_a_prime_coverage.py` | `217c9ec98fc876bc` |

Full hashes are recorded in `frozen/b1_6_pilot_scaffold_manifest.json`. **No source-hash mismatch** → not
`B1_6_PILOT_BLOCKED_SOURCE_HASH_MISMATCH`.

## 2. Frozen pilot target set

**24 items, 4 per stratum**, all **English mode**, neutral selection (not chosen for expected Symbol-U success;
non-obscure; non-high-stakes; no Sanskrit privilege). Per-item fields (`item_id`, `TARGET_TEXT`, `target_type`,
`category`, `neutral_context`, `forbidden_hints`, `selection_note`, `language_mode`) are in
`frozen/b1_6_pilot_targets_scaffolds.json`.

| Stratum | Items |
|---|---|
| common concrete words | river, bridge, lantern, mirror |
| abstract concepts | balance, freedom, patience, threshold |
| name-like terms | Maya, Rowan, Nova, Ira |
| symbolic/spiritual terms | lotus, dawn, anchor, mandala |
| brand/product-like terms | Lumen, Verba, Solace, Kite |
| emotionally charged (non-clinical) | grief, wonder, longing, courage |

## 3. Language-mode assignment

**All 24 targets: `language_mode = ENGLISH`.** No `SANSKRIT_TRANSLITERATION` items — Sanskrit mode was **not**
used to make aspirated varṇas reachable (that would be exactly the manipulation the freeze plan forbids). The
Sanskrit aspirated/conjunct keys therefore remain unreachable in this pilot, as the English aspirate amendment
(`a629329`) requires.

## 4. Target decomposition & coverage

Each target was normalized and decomposed with the **frozen** Stage A′ decomposer (`A_PRIME_EN`,
`stage_a_prime_coverage.py`, hash `217c9ec98fc876bc`); the phoneme→varṇa **bridge** (`b680063`) and the
**English `ph`→/f/** amendment (`a629329`) were applied; vowels tagged `VOWEL_NO_PROFILE`; `f/z/zh` and any
unmatched consonant tagged `UNSUPPORTED_NO_VARNA`. Consonant-coverage rate = supported / total consonant
phonemes; **eligibility threshold ≥ 0.60** (bridge spec §10).

**All 24 targets passed** (no replacements needed). Coverage: 22 items at **1.00**; `freedom` **0.75** (the `f`
is `UNSUPPORTED_NO_VARNA`); `grief` **0.67** (the `f` unsupported). No target fell below 0.60. Examples:
`dawn → da, va, na` (`w→va` recorded collapse); `anchor → na, ca, ra` (`ch→ca`); `longing → la, nga, nga`;
`grief → ga, ra` (+`f` unsupported). Full per-item phoneme sequences, `VARNA_SEQUENCE`, supported varṇa
sequences, and coverage are in the data file.

## 5. Symbol-U scaffold population

For each target the active frames are populated:

- **`{TARGET_TEXT}`** — the target.
- **`{VARNA_SEQUENCE}`** — per-phoneme, tagged `SUPPORTED`(+varṇa) / `VOWEL_NO_PROFILE` / `UNSUPPORTED_NO_VARNA`.
- **`{VARNA_PROFILE_TABLE}`** — per supported varṇa, the `axis_contributions` copied verbatim from
  `track_g_varna_polarity_table.json` (no invention).
- **`{KCPR_DUAL_POLE_FRAME}`** — per supported varṇa, per contributing axis: **both** named poles (from
  `track_g_polarity_axes.json`), the `worldly_binding_pole` / `liberating_counter_pole` labeling, and the
  candidate `table_lean` sign. **Both poles shown; no "correct" pole selected; opposite pole never hidden.**

**`{CSR_STL_FRAME}` is not populated** — recorded as `DEFERRED_NOT_POPULATED` (CSR/STL deferred for this pilot).

**Leakage:** only **low-leak axis pole names** are rendered. The high-leak per-varṇa vṛtti gloss `notes`
(e.g. "hope / forward-grasping desire") are **not** included — verified: a scan for those gloss tokens returns
empty.

## 6. Vowel & unsupported notation

Recorded visibly in every `VARNA_SEQUENCE`: vowels → `VOWEL_NO_PROFILE`; unsupported consonants (incl. English
`/f/`) → `UNSUPPORTED_NO_VARNA`. **No vowel profiles invented; no unsupported segment coerced to a varṇa.**

## 7. KCPR theory-accommodation metadata

Global scaffold metadata (in both the data file and the scaffold manifest):

```
KCPR_POLICY                       = DUAL_POLE_RENDERING
KCPR_THEORY_STATUS                = THEORY_NONCANONICAL_INPUT_POLARITY
KOSHA                             = DEFERRED
CSR_STL                           = DEFERRED
POLARITY_INPUT_STATUS             = READOUT_SCAFFOLD_ONLY
STAGE_A_OPERATOR_POLARITY_STATUS  = POLARITY_FREE
```

`THEORY_NONCANONICAL_INPUT_POLARITY` is recorded as **metadata**, not as persuasive language to the generator:
the polarity readout is a candidate scaffold for a utility test, **not** a claim that polarity is a real
primitive varṇa input, **not** semantic evidence, **not** ontology; Stage A′ / operator composition remains
polarity-free.

## 8. Randomized Symbol-U control

`frozen/b1_6_pilot_randomized_control_manifest.json`: a **deterministic** control with **seed = 20260708**.
The supported-varṇa→profile association is **shuffled/relabelled** by a seeded permutation (`relabel_map` +
`relabel_map_sha256`), so each varṇa position borrows another varṇa's profile. The scaffold **format**, the
**sequence length**, the **entry count**, and the **dual-pole rendering format** are preserved (same output
budget). It is presented to the generator **exactly as a scaffold** and is **not** revealed as randomized to the
generator or judges. Records the seed, mapping hash, source-table hash, and `generation_run: false`.

## 9. Baseline parity metadata

Recorded in the scaffold manifest: **same** target text, neutral context, output format, prompt/rubric spec,
token budget; a `model_settings` placeholder = `TBD_at_evidence_freeze`; **no arm labels in outputs**; **target
visible to judges** (needed for specificity/non-genericity scoring).

## 10. Scaffold manifest

`frozen/b1_6_pilot_scaffold_manifest.json` records: target-scaffolds hash, randomized-control hash, and the
full sha256 of the bridge manifest, English aspirate amendment, KCPR manifest, KCPR theory amendment + audit,
prompt/rubric doc, prereg doc, varṇa polarity table, sphere lexicon, polarity axes, and decomposer; the
readiness label; `all_targets_eligible: true`; and `generation_run / evidence_freeze_declared: false`.

## 11. Readiness label

**`B1_6_PILOT_SCAFFOLD_INSTANTIATION_READY`.** All targets decomposed and passed coverage
(not `B1_6_PILOT_BLOCKED_TARGET_DECOMPOSITION`); every supported varṇa resolved a profile
(not `..._BLOCKED_PROFILE_LOOKUP`); the randomized control is frozen (not `..._BLOCKED_RANDOMIZED_CONTROL`);
source hashes verified (not `..._BLOCKED_SOURCE_HASH_MISMATCH`); no generation/judge exposure and no high-leak
content (not `..._INVALID_LEAKAGE`).

## 12. Leakage & overclaim guard

- **No generated text.** **No judge exposure.** **No semantic-truth claim.** **No `ONTOLOGICAL_SIGNAL`.** **No
  Sanskrit privilege.** **No target-specific pole selection** (dual-pole; both shown). **No high-leak vṛtti
  notes** (verified absent). **No post-hoc target replacement** (all 24 eligible on first pass; none swapped).
  **No B1.4b′ reinterpretation.** **KCPR polarity readout marked `THEORY_NONCANONICAL_INPUT_POLARITY` and
  scaffold-only.**

## 13. Validation checklist

- [x] Docs/manifest/data only; **no code** committed (the build was a scratchpad data-prep step, not a
  generation harness, and is not committed).
- [x] No generation. [x] No evidence freeze. [x] Source hashes recorded.
- [x] Target set frozen (24 items, hash-pinned). [x] Scaffold placeholders populated
  (`{TARGET_TEXT}`/`{VARNA_SEQUENCE}`/`{VARNA_PROFILE_TABLE}`/`{KCPR_DUAL_POLE_FRAME}`).
- [x] KCPR dual-pole frame populated. [x] `THEORY_NONCANONICAL_INPUT_POLARITY` recorded.
- [x] Randomized control frozen (seed 20260708). [x] CSR/STL deferred. [x] Kosha deferred.
- [x] Prior artifacts untouched (Stage A, Stage A′, scorer, B1.3, B1.4a, B1.4b, B1.4b′, lexicons, prior B1.6
  docs — only new frozen data/manifests + this report added).

---

## Final report

- **Files created:** `frozen/b1_6_pilot_targets_scaffolds.json`,
  `frozen/b1_6_pilot_randomized_control_manifest.json`, `frozen/b1_6_pilot_scaffold_manifest.json`, and this
  report. No prior artifact modified. (Build script kept in scratchpad, not committed.)
- **Commit hash:** (recorded on commit below).
- **Readiness label:** **`B1_6_PILOT_SCAFFOLD_INSTANTIATION_READY`**.
- **Number of pilot targets frozen:** **24**.
- **Target strata summary:** 4 each across common-concrete, abstract, name-like, symbolic/spiritual,
  brand/product, emotionally-charged-non-clinical.
- **All targets passed decomposition/coverage?** **Yes** — 24/24 ≥ 0.60 (22 at 1.00; `freedom` 0.75; `grief`
  0.67); no replacements.
- **Scaffold placeholders populated?** **Yes** — `{TARGET_TEXT}`, `{VARNA_SEQUENCE}`, `{VARNA_PROFILE_TABLE}`,
  `{KCPR_DUAL_POLE_FRAME}`; `{CSR_STL_FRAME}` deferred/not populated.
- **Randomized Symbol-U controls frozen?** **Yes** — deterministic, seed 20260708, format/length preserved.
- **CSR/STL and Kosha deferred?** **Yes** — both deferred.
- **`THEORY_NONCANONICAL_INPUT_POLARITY` recorded?** **Yes** — global scaffold metadata + manifest.
- **No generation run was performed.**
- **No evidence freeze was declared.**
- **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
- **This is not a semantic-decoding or ontology claim** — it is a frozen generative-utility scaffold over
  self-declared unvalidated candidate tables, with the polarity readout explicitly theory-noncanonical.

> B1.6 pilot scaffold instantiation package drafted and frozen docs/manifest/data only. KCPR theory caveat
> recorded. No generation run. No evidence freeze. B1.4b′ remains NULL_RETURN_BOTTOM. Original B1.4b remains
> blocked. Track B remains blocked. Structure, not validated meaning.
