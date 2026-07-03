# DOCS_ONLY — TRACK B B0 FREEZE MANIFEST TEMPLATE — NOT FROZEN — DOES NOT UNBLOCK TRACK B

*Docs-only template. No commit of results, no code change, no model call, no generation, no scoring, no result files, no manifest change. **Hashes are placeholders — nothing is frozen.** Track B remains **BLOCKED**.*

Provenance: readiness audit `7d0c3552035ef860eae92be304da849757c73553`; Stage B0 readiness package `68e04cdfbd13486ae2e5c08c05d1bdf652fc2499`.

---

## 1. Scope

- **Template only** — defines the *fields* a future B0 freeze manifest must carry; it does **not** populate them.
- **Docs-only.** No execution, no model call, no scoring, no manifest transition.
- All hash values are placeholders (`<UNFROZEN>`); no artifact is authored or hashed here.
- **Track B remains BLOCKED**; `status NOT_READY`; `approval_status NOT_APPROVED`. This template changes none of them.

## 2. Freeze manifest purpose

The B0 freeze manifest is the single record that, once **fully populated with real content hashes**, proves every Stage B0 input (§3 of the readiness package) was authored blind, versioned, and locked **before** any approval request. Until every required field holds a real hash and the manifest is signed, B0 is `NOT_FROZEN` and **no approval request may be submitted**. Populating it is *not* execution and *not* unblocking — it is the precondition for *requesting* approval to execute B1.

## 3. Required artifact hash fields (top-level)

Each row must carry a content hash, an author/date, and a "blind-authored" attestation before B0 is frozen.

| # | Artifact | Field | Value |
|---|---|---|---|
| 1 | Prompt set | `hash.prompt_set` | `<UNFROZEN>` |
| 2 | Key-word list | `hash.key_word_list` | `<UNFROZEN>` |
| 3 | Held-out/dev split | `hash.heldout_split` | `<UNFROZEN>` |
| 4 | Model IDs + versions | `hash.model_set` | `<UNFROZEN>` |
| 5 | Decoding parameters | `hash.decode_params` | `<UNFROZEN>` |
| 6 | Seed policy | `hash.seed_policy` | `<UNFROZEN>` |
| 7 | Arm construction rules | `hash.arm_rules` | `<UNFROZEN>` |
| 8 | L1–L5 configuration | `hash.pipeline_config` | `<UNFROZEN>` (record commit SHA) |
| 9 | Vowel-mode policy | `hash.vowel_mode_policy` | `<UNFROZEN>` |
| 10 | Judge rubric | `hash.judge_rubric` | `<UNFROZEN>` |
| 11 | Leak-scanner criteria | `hash.leak_scanner` | `<UNFROZEN>` |
| 12 | Randomization plan | `hash.randomization_plan` | `<UNFROZEN>` |
| 13 | Analysis plan | `hash.analysis_plan` | `<UNFROZEN>` |
| 14 | Kill-label set | `hash.kill_labels` | `<UNFROZEN>` |
| 15 | Approval-record template | `hash.approval_template` | `<UNFROZEN>` |
| 16 | Manifest-transition checklist | `hash.transition_checklist` | `<UNFROZEN>` |

Manifest-level fields: `hash_algorithm: <e.g. sha256>` · `freeze_timestamp: <UNSET>` · `frozen: false` · `b0_status: NOT_FROZEN` · `all_hashes_present: false`.

## 4. Prompt-set hash fields

```
prompt_set:
  hash: <UNFROZEN>
  item_count: <UNSET>
  blind_authored: <attestation UNSET>
  dev_demo_excluded: <mercy/love/anger/peace + fixtures — attestation UNSET>
  semantic_domain_balance: <coverage table UNSET>
  vowel_consonant_balance: <count UNSET>
  privative_a_an_stratum_hash: <UNFROZEN>   # declared stratum, analyzed separately
  fixture_items_excluded_from_natural_run: <list + attestation UNSET>
  post_hoc_edits: none            # any edit ⇒ INVALID_POSTHOC (§12)
```

## 5. Key-word-list hash fields

```
key_word_list:
  hash: <UNFROZEN>
  count: <UNSET>
  g2p_resolvable: <natural-cmudict subset, list UNSET>
  fixture_based: <labeled subset UNSET — not natural-run evidence>
  a_prefix_stratum: <list UNSET — EY→e caveat attached>
  overlap_with_dev_demo: none    # must be empty
```

## 6. Model/decode hash fields

```
model_set:
  hash: <UNFROZEN>
  families_count: <UNSET — must be >= 2>
  models: [ {id: <UNSET>, revision_hash: <UNSET>}, ... ]
decode_params:
  hash: <UNFROZEN>
  temperature: <UNSET>
  top_p: <UNSET>
  max_tokens: <UNSET>
  identical_across_arms: <attestation UNSET>
seed_policy:
  hash: <UNFROZEN>
  seeds: [<UNSET>]
  seeds_per_item: <UNSET — must be >= 2>
  rerun_until_pass: forbidden
```

## 7. Arm-construction hash fields

```
arm_rules:
  hash: <UNFROZEN>
  wrapper_hash: <UNFROZEN>              # identical across all arms
  single_slot_varies_only: <attestation UNSET>
  arms:
    A_real:        {generator_hash: <UNFROZEN>}
    R_random:      {generator_hash: <UNFROZEN>}
    S_scrambled:   {generator_hash: <UNFROZEN>}
    C_surface:     {generator_hash: <UNFROZEN>}
    X_neutral:     {generator_hash: <UNFROZEN>}
    D_dictionary:  {generator_hash: <UNFROZEN>}
  length_parity_measured: <pre-judging; imbalance declared as confound UNSET>
pipeline_config:
  hash: <UNFROZEN>
  l1_l5_commit_sha: <UNSET>
  vowel_mode_policy_hash: <UNFROZEN>    # default field_only; positional only as declared stratum
```

## 8. Judge/rubric hash fields

```
judge_rubric:
  hash: <UNFROZEN>
  scales: <UNSET>
  forced_choice_format: <UNSET>
  arm_labels_hidden: <attestation UNSET>
  conditioning_source_hidden: <attestation UNSET>
  dictionary_answer_key_exposed: false
  attention_checks: <UNSET>
  inter_rater_agreement_reported: <plan UNSET>
leak_scanner:
  hash: <UNFROZEN>
  forbidden_patterns: <ontology / sanskrit-privilege / semantic-truth / "therefore means" — UNSET>
randomization_plan:
  hash: <UNFROZEN>
  output_order_seed: <UNSET>
  no_fixed_arm_adjacency: <attestation UNSET>
```

## 9. Analysis-plan hash fields

```
analysis_plan:
  hash: <UNFROZEN>
  co_primaries: [A_vs_D, A_vs_R, A_vs_S, A_vs_X, A_vs_C]
  threshold: <CI-lower-bound > 0 or predeclared effect size — UNSET>
  multiple_comparison_correction: <method UNSET>
  all_arms_reported: true
  all_failures_reported: true
  per_task_type_breakdown: <plan UNSET>
  per_stratum_breakdown: <incl. a-/an- stratum — plan UNSET>
  cherry_picking: forbidden
kill_labels:
  hash: <UNFROZEN>
  set: [NO_SIGNAL, DICTIONARY_DOMINATES, RANDOM_OR_SCRAMBLED_MATCHES,
        SURFACE_STRUCTURE_EXPLAINS, CORRECTNESS_DEGRADED, INVALID_POSTHOC,
        LEAKAGE_FAIL, NOT_ROBUST]
```

## 10. Approval-record placeholder

```
approval_record:
  hash: <UNFROZEN>
  b0_frozen_hash_referenced: <UNSET>     # the exact manifest hash being approved
  authorizer: <UNSET>
  authorization_date: <UNSET>
  scope: "authorizes B1 execution ONLY on the referenced frozen hash"
  status: NOT_APPROVED                   # unchanged; no approval exists
```

## 11. Manifest-transition placeholder

```
manifest_transition:
  hash: <UNFROZEN>
  checklist:
    - b0_fully_frozen: false
    - separate_approval_recorded: false
    - b1_executed: false
    - b2_independent_analysis_complete: false
    - b3_blocker_review_passed: false
  target_fields_if_ever_transitioned:      # NOT changed here; documentation only
    track_b_status: BLOCKED   -> <unchanged>
    status:         NOT_READY -> <unchanged>
    approval_status: NOT_APPROVED -> <unchanged>
  note: "No field is transitioned by this template. B4 transition is considered, never automatic."
```

## 12. Invalid-posthoc rule

Once B0 is declared frozen (every §3 field holds a real hash and `frozen: true` is set), **any** subsequent edit to a hashed artifact ⇒ `INVALID_POSTHOC`: the run/request is void and a **new** B0 manifest with new hashes is required. No silent substitution, no "small fix," no re-hash-in-place. Editing an artifact before freeze is fine; editing after freeze is fatal to that B0.

## 13. Current status

- `B0_FREEZE_MANIFEST_TEMPLATE_CREATED`
- `B0_NOT_FROZEN`
- `TRACK_B_BLOCKED`
- `B1_NOT_APPROVED`
- `NO_MODEL_CALL`
- `NO_RESULT_CHANGE`

(All hashes `<UNFROZEN>`; `frozen: false`; `freeze_timestamp: UNSET`; base manifest unchanged: `track_b_status BLOCKED`, `status NOT_READY`, `approval_status NOT_APPROVED`.)

## 14. Guardrails

- No ontology validation.
- No Sanskrit privilege.
- No semantic-truth claim.
- No Track G rescue.
- No Track B unblock.
- Track G negative preserved: `1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`.
- Track B remains **BLOCKED**.
- Prior PSE negatives remain valid.
- Track F prior remains `CORRECTNESS_DEGRADED`.
- Frozen manifest remains `NOT_READY`.

---

**Final recommendation:** `NEXT: AUTHOR_B0_FREEZE_ARTIFACTS — while Track B remains BLOCKED`

*Authoring the B0 artifacts (blind, then hashing them into this template) is the disciplined next step; it does not execute, does not call a model, does not touch the approval gate, and does not unblock Track B. B1 remains gated behind a separate, explicit approval recorded against a fully frozen manifest hash.*

---

**Structure, not validated meaning.**
