# ś / ṣ Mapping-Swap Provenance Audit (read-only)

**Read-only audit. Nothing repaired.** No frozen mapping, preregistration, feature-lift dataset, or prior result
is modified. This traces the palatal `ś` (śa) and retroflex `ṣ` (ṣa) sibilants through the full provenance chain,
locates the guṇa/puruṣārtha swap, and determines whether the frozen artifacts are currently correct.
`EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## Verdict

> **`SWAP_PROVENANCE_RESOLVED_NO_DATA_ERROR`**

The swap existed in the intermediate **authoring/derived** tables (b1_1 draft → b1_2 source lexicon → track_g
v2) but was **detected by the primary-text verification and corrected at v3.1**. The frozen merged lexicon
(`varna_native_stage1_merged_v1.json`) currently assigns **`ś` = tamoguṇa + kāma** and **`ṣ` = rajoguṇa + artha`**
to the **correct atomic phonemes**. The feature-lift study consumes the corrected merged file. One residual
documentation artifact and one historical-consumption caveat are noted below (neither is a data error in a
current/frozen consumed gloss).

## Files & hashes (SHA-256)

| # | File | SHA-256 |
|---|---|---|
| 1 | `b1_2_mapping_fidelity/b1_2_varna_classical_verifications.json` | `a1ad271fae62514284123deb879e58973e82843d186f41aa175710dc9217e1b2` |
| 2 | `b1_2_mapping_fidelity/b1_2_varna_source_lexicon.json` | `e8aeb105027907092b28eb17896fc699cf780f180fe38ca645f7ca94751b5bb7` |
| 3 | `track_g_varna_polarity_table_v2_named_vritti.json` | `7bc0b7c8c11c68c80d76ac974657611946e076a839f2a053bce9f639cd4a2694` |
| 4 | `frozen/varna_polarity_table_v3_1_metadata_refreeze.json` | `9ac712a6afab2d9c1497ea5d085ccac28942fb093f355284ffb0ece55bd64b27` |
| 5 | `frozen/varna_native_stage1_merged_v1.json` | `af4c1f54adbfac2b0e2be88993860dcca5e1ebf41631efec23672786584cca96` |

Codepoints: palatal `ś` = **U+015B**, ASCII key `sha`, devanāgarī श; retroflex `ṣ` = **U+1E63**, ASCII key
`ssa`, devanāgarī ष; dental `s` = U+0073, key `sa`. In every file the **transliteration label stays correctly
bound to its key** (`sha`↔śa, `ssa`↔ṣa) — what moves is the **semantic record**.

## Primary-text ground truth (Sarkar four-varga sibilant scheme)

`śa(sha) = tamoguṇa + kāma` · `ṣa(ssa) = rajoguṇa + artha` · `sa = sattvaguṇa + mokṣa`. Attested verbatim in
file 1 and file 4 `source_quote_verified`.

---

## Trace: `ś` (śa, U+015B, key `sha`)

| File | binding gloss | guṇa / puruṣārtha (classical assoc.) | citation | copied/renamed/swapped/normalized | state |
|---|---|---|---|---|---|
| 1 classical_verifications | kāma — worldly/physical desire; the tamasic pull | **śa = tamoguṇa; kāma (physical longing)** | Sarkar: "Śa is the acoustic root of tamoguṇa … kāma" | authored **correct**; **swap detected here** (`v2_drift_note`: "BOTH v2 AND the lexicon MIS-ASSIGN śa") | ✅ correct |
| 2 source_lexicon | "worldly purpose possessed as acquisition, status, or control" | **rajoguṇa + artha** (`sanskrit_label`) | source_note: "Śa = acoustic root of rajoguṇa … artha" | **SWAPPED** (retroflex ṣa's artha/rajas record filed under palatal śa) | ❌ swapped |
| 3 track_g v2 | "mutative drive / material pursuit" | note: "Classical root: rajo-guna / artha" | — | **SWAPPED** (inherited from #2) | ❌ swapped |
| 4 v3.1 refreeze | kāma — worldly/physical desire; the tamasic pull | **śa = tamoguṇa; kāma** | Sarkar (verified): "Śa … tamoguṇa … kāma" | **CORRECTED** — re-derived from #1 (`differs_from_v2=True`; "v3 corrects by following primary text") | ✅ correct |
| 5 merged v1 | kāma — worldly/physical desire … the tamasic pull toward the crude | (guṇa carried in provenance, not the merged pole) | via `source_key=sha` | **copied** from #4 (verbatim binding pole) | ✅ correct |

## Trace: `ṣ` (ṣa, U+1E63, key `ssa`)

| File | binding gloss | guṇa / puruṣārtha (classical assoc.) | citation | copied/renamed/swapped/normalized | state |
|---|---|---|---|---|---|
| 1 classical_verifications | artha as possessive acquisition (rajasic grasping) | **ṣa = rajoguṇa; artha** | Sarkar: "ṣa … artha … rajoguṇa" | authored **correct**; `v2_drift_note`: "SIBILANT SWAP CONFIRMED … derived tables SWAP them" | ✅ correct |
| 2 source_lexicon | "sensory craving bound to inertia" | **Kāma / Tamoguṇa** (`sanskrit_label`) | source_note: "acoustic root of tamoguṇa … kāma" | **SWAPPED** (palatal śa's kāma/tamas record filed under retroflex ṣa) | ❌ swapped |
| 3 track_g v2 | "static inertia / worldly desire" | note: "Classical root: tamo-guna / kama" | — | **SWAPPED** (inherited from #2) | ❌ swapped |
| 4 v3.1 refreeze | artha as possessive acquisition (rajasic grasping to acquire) | **ṣa = rajoguṇa; artha** | Sarkar (verified): "ṣa … artha … rajoguṇa" | **CORRECTED** — re-derived from #1 | ✅ correct |
| 5 merged v1 | artha as possessive acquisition … (rajasic grasping to acquire) | (guṇa carried in provenance) | via `source_key=ssa` | **copied** from #4 (verbatim binding pole) | ✅ correct |

Also confirmed present with the swap: the **b1_1 experimental draft**
(`b1_1_experimental_contrastive_lexicon_draft.json`): `sha`→"rajoguṇa + artha", `ssa`→"Kāma / Tamoguṇa" —
identical to file 2. So the swap belongs to the b1_1/source-lexicon **authoring layer**.

---

## Determinations

1. **Where the mis-filing first entered.** The **authoring/derived-lexicon layer**:
   `b1_1_experimental_contrastive_lexicon_draft.json` and its successor
   `b1_2_varna_source_lexicon.json` (file 2), then propagated to `track_g_varna_polarity_table_v2` (file 3).
   It did **not** enter at the primary-text verification (file 1), which is the corrective **authority** that
   **detected** it.

2. **Label swap or semantic swap?** **Semantic-record swap**, not a label rename. In every file the
   transliteration stayed correctly bound to its key (`sha`↔śa, `ssa`↔ṣa). What was transposed between the two
   phonemes was the **guṇa + puruṣārtha + binding-expression content**: the artha/rajas record sat under palatal
   śa and the kāma/tamas record under retroflex ṣa. Consuming key `sha` from file 2/3 therefore returned the
   **wrong identity** (artha/rajas) despite a correct `śa` label.

3. **Does the frozen merged lexicon assign the intended glosses to the correct phonemes?** **Yes.**
   `ś` (U+015B) → kāma / tamasic; `ṣ` (U+1E63) → artha / rajasic — matching the primary text.

4. **Are `ś = tamoguṇa + kāma` and `ṣ = rajoguṇa + artha` attached to the intended atomic identities now?**
   **Yes**, in files 4 and 5 (the frozen, consumed artifacts).

5. **Did any experiment consume the wrong identity despite hash consistency?** **Yes, but only pre-v3, superseded
   artifacts.** The b1_1 draft, `b1_2_varna_source_lexicon.json`, and `track_g_v2` embody the swapped ś/ṣ
   semantics; any **B1.1 / B1.2 mapping-fidelity** scoring that read the `ś` or `ṣ` binding expression consumed
   the swapped content. These are **exploratory and superseded by v3.1** — they are **not** the confirmatory
   backbone. The current confirmatory B1 line, the merged lexicon, and the **frozen 88-word feature-lift dataset
   all use the corrected assignment**; the B1.12 result files carry **no guṇa layer at all** (they use the
   corrected `binding_vritti`). A full re-scoring of historical B1.1/B1.2 `ś`/`ṣ` items is **out of scope** for
   this read-only audit and is flagged, not performed.

## Residual notes (not data errors in consumed glosses)

- **v3.1 `source_note` residue.** In file 4 the operative fields (`worldly_binding_distortion`,
  `classical_associations`, `source_quote_verified`) are corrected, but the non-operative `source_note` field for
  `sha`/`ssa` still carries the **pre-correction swapped** wording (e.g. `sha` `source_note` = "rajoguṇa +
  artha"). This is a stale documentation field, not the consumed pole; the merged lexicon does not read it. Worth
  cleaning in a future refreeze, but it changes no gloss.
- **Pole-split provenance.** `ṣ` (`ssa`) carries `binding_pole_provenance = AUTHORED_PROVISIONAL` for the
  binding/liberating *split*, while the **guṇa itself** (rajoguṇa) is primary-text-attested. The two should not be
  conflated.

## Guardrails
Read-only audit; no repair performed; no frozen mapping, preregistration, feature-lift dataset, or prior result
modified. The frozen merged lexicon is correct for `ś`/`ṣ`. Structure, not validated meaning.
