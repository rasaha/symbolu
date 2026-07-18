# Feature-Lift Prerun v2 — Repointed to Corrected Lexicon (merged v3)

Regenerates the feature-lift prerun against the **corrected** merged lexicon `varna_native_stage1_merged_v3.json`
(`65116f37…`) — the ś/ṣ swap fix plus the completed vowel layer. **The dataset is unchanged**; only the
mapping-dependent hashes move. `EXPLORATORY / DEVELOPMENT_ONLY / NOT_CONFIRMATORY_EVIDENCE`.

## What stayed identical (verified)

Word selection is by consonant **unit identity**, which v3 does not change, so:
- included 88 words — **identical IDs**; excluded 18 — identical; funnel — identical (106→93→…→88);
- `word_target_table.json`, `split_manifest.json`, `dependency_groups.json`, `candidate_source_list.json`,
  `included/excluded_word_manifest.json`, `sample_failure_funnel.json`, `affective_norm_source_manifest.json`,
  `base_representation_manifest.json` — **byte-identical to prerun v1**.

## What changed (exactly two manifests)

| Manifest | Field | v1 | v2 |
|---|---|---|---|
| `prerun_freeze_manifest.json` | `lexicon_sha256` | `af4c1f54…` | **`65116f37…` (v3)** |
| `shuffle_control_manifest.json` | `real_consonant_to_gloss_sha256` | `af697897…` | **`b7ebb464…`** |

The shuffle hash moves **because** the real consonant→gloss bijection now carries the corrected ś/ṣ glosses
(ś=artha/rajasic, ṣ=kāma/tamasic). That is exactly the intended effect: the feature and its shuffle-null are now
built on the corrected mapping.

## Location & status

- New: `varna_feature_lift_prerun_v2/` (generator `build_varna_feature_lift_prerun_v2.py`, reads merged **v3**,
  reuses the pinned Warriner CSV).
- Retained: `varna_feature_lift_prerun_v1/` (historical, pre-correction).
- Readiness: `READY_FOR_FEATURE_EXTRACTION_AND_LIFT_RUN` (88 ≥ 30). Still **no** embeddings/models/metrics
  computed.

**Run on v2**, not v1: v2 is the dataset bound to the corrected mappings. The raw norm CSV remains git-ignored,
pinned by checksum.
