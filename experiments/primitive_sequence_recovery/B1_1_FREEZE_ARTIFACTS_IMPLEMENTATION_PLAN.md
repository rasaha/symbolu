# B1.1 Freeze-Artifacts Implementation Plan (documentation/planning only)

## Scope and non-claims

Planning document only. Lists the files/validators to create in the next implementation gate. **No freeze ·
no model / generation / scoring / judging · no final config · no manifest.** Does **not** modify B1, change
the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology / Sanskrit
privilege / semantic-truth claim. **Structure, not validated meaning.**

## 1. File inventory to create in the next implementation gate

**Config files (start as `*.template.json`, `TEMPLATE_NOT_FROZEN`):**
- `b1_1_arm_construction_config.json`
- `b1_1_generation_config.json`
- `b1_1_seeds_config.json`
- `b1_1_judge_panel_config.json`
- `b1_1_scorer_config.json`
- `b1_1_leak_and_packet_config.json`
- `b1_1_freeze_manifest.json` *(built LAST, only at the freeze gate — not now)*

**Validator scripts:**
- `run_b1_1_freeze_artifact_validation.py`
- `run_b1_1_freeze_manifest_verifier.py`

Already committed (bound at freeze): `b1_1_experimental_contrastive_lexicon_draft.json` (lexicon),
`b1_1_bridge_pool_draft.json` (bridge pool).

## 2. JSON schema expectations per config

- **arm_construction**: `arms` (exactly A/D/S/R_same/R_deranged/R_domain/C/X), per-arm `construction_rule`,
  `no_target_self` (R_same/R_deranged), `same_pool` (R_same), `deranged_source` (R_deranged, other-word real
  mapping + derangement seed), `domain_mismatch` (R_domain forbidden/allowed domain lists), `style_length_norm`,
  `exclusion_rules`, `seeds` (placeholders).
- **generation**: `generation_model_id` (PLACEHOLDER_REQUIRED), `provider_runtime` (PLACEHOLDER_REQUIRED),
  `model_revision` (PLACEHOLDER_REQUIRED_IF_AVAILABLE), `temperature`, `top_p`, `max_tokens`,
  `number_of_samples`, `retry_policy`, `failure_policy`, `prompt_template`, `task_templates`,
  `generation_authorized: false`.
- **seeds**: `arm_construction_seed`, `task_order_seed`, `prompt_order_seed`, `generation_seed`,
  `judge_packet_shuffle_seed`, `scoring_bootstrap_seed`, `deterministic: true`.
- **judge_panel**: `judge_model_ids` (PLACEHOLDER_REQUIRED), `judge_prompt`, `output_schema`, `parser_rules`,
  `qc_rules`, `replacement_policy`, `exclusion_policy`, `no_post_hoc_selection: true`.
- **scorer**: `primary_comparisons` (A vs R_deranged/R_domain/R_same), `secondary_comparisons`
  (A vs D/S/C/X), `ci_policy`, `multiplicity_correction`, `task_level_diagnostics`, `correctness_tracking`,
  `verdict_label_rules`.
- **leak_and_packet**: `leak_checks`, `forbidden_label_leakage`, `varna_sanskrit_leakage`,
  `blinded_packet_format`, `packet_hashing`, `packet_persistence_sample`, `raw_output_persistence`,
  `judge_output_persistence`.
- **freeze_manifest** *(future, freeze gate only)*: sha256 of all bound artifacts, paths,
  `generation_authorized`, `fallback_qualification`, `embedding_gate_status`, `b1_verdict_anchor`,
  `track_b_anchor`, `created_at`, `commit_hash`, `not_ontology_validation: true`.

## 3. Validator responsibilities

- `run_b1_1_freeze_artifact_validation.py` — validate each config's schema, required keys, no residual
  `PLACEHOLDER_REQUIRED` in a *final* (non-template) config, arms exactly the 8, primary comparisons include
  all three R controls, `generation_authorized:false`, embedding/fallback status correct, B1 + Track B
  anchors present, no forbidden framing in the bridge, all artifact sha256 computed.
- `run_b1_1_freeze_manifest_verifier.py` — recompute sha256 of every bound artifact and fail on any mismatch
  (`INVALID_POSTHOC` guard).

## 4. Dependency-free implementation rule

Validators and config-builders must be **pure stdlib** (json/hashlib/pathlib/re) — **no network, no model,
no embeddings, no third-party deps**. (The embedding gate is the only model-dependent step and remains
BLOCKED/owed, outside this path.)

## 5. Exact future config-file paths

```
experiments/primitive_sequence_recovery/b1_1_arm_construction_config.json
experiments/primitive_sequence_recovery/b1_1_generation_config.json
experiments/primitive_sequence_recovery/b1_1_seeds_config.json
experiments/primitive_sequence_recovery/b1_1_judge_panel_config.json
experiments/primitive_sequence_recovery/b1_1_scorer_config.json
experiments/primitive_sequence_recovery/b1_1_leak_and_packet_config.json
experiments/primitive_sequence_recovery/b1_1_freeze_manifest.json
```

## 6. Exact future validator-script paths

```
experiments/primitive_sequence_recovery/run_b1_1_freeze_artifact_validation.py
experiments/primitive_sequence_recovery/run_b1_1_freeze_manifest_verifier.py
```

## 7. Freeze readiness

Remains **`NOT_READY_FOR_FREEZE`** — templates and plans do not satisfy the freeze checklist; final configs
must be authored, validated, and hash-bound first.

## 8. Generation authorization

**Not authorized.** Generation requires the separate `B1_1_GENERATION_AUTHORIZATION` gate; no config or
template here authorizes a model call.

## Final status
```
B1 verdict: RANDOM_OR_SCRAMBLED_MATCHES (unchanged) · Track B: BLOCKED
Freeze status: NOT_READY_FOR_FREEZE · Bridge: PASS_BRIDGE_DRAFT / FALLBACK_QUALIFIED
Embedding gate: BLOCKED_DEPENDENCY_UNAVAILABLE (owed) · Generation: NOT authorized
```
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` (`1fe5562`) · Track F `CORRECTNESS_DEGRADED`.
`R_deranged` remains the crux. **Structure, not validated meaning.**
