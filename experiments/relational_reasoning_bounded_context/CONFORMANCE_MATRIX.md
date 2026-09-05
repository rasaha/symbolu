# BTRR Implementation Conformance Matrix (post-correction)

Fresh requirement-by-requirement conformance against the original preregistration, Amendment 001,
Amendment 002, and independent implementation-audit findings F1–F7. Implementation commit under
correction: `f53dea6d6efd94e1575d7f8d000a68d3336e582b`. No protocol artifact, gate value, or R1–R12
semantic was changed. Execution remains fail-closed.

## Audit findings F1–F7
| Finding | Correction | Test evidence | Status |
|---|---|---|---|
| **F1** seed authorization at every scientific primitive | Centralized `execution.assert_generation_allowed`; wired into `generate_episode`, `generate_split`, `generate_p0`, `generate_p0_episode`, `trainer.train_checkpoint`, and reached by `replay`/`driver`; no bypass flag (auth only via a token that does not exist) | `test_F1_*` (6): direct calls with 8100/8101/81600 raise before generation; fixtures still run; bogus token rejected | **CLOSED** |
| **F2** R9 full-chain correctness | Per-item conjunction (answer ∧ exact ordered path ∧ latest event ∧ policy) in `metrics.r9_full_chain_correct`; gate `R9_full_chain_correct ≥ 0.60` in `evaluate_gates`; verdict routes its failure to `POLICY_REASONING_FAILED` (blocks VALIDATED) | `test_F2_*` (3): all-correct→1; any single wrong component→0; gate enforced in verdict | **CLOSED** |
| **F3** latest-event effect over global-most-recent | `shortcuts.global_most_recent` baseline + `latest_event_effect`; gate `latest_event − baseline ≥ 0.20` in `evaluate_gates`; verdict adds it to `TEMPORAL_REASONING_FAILED` | `test_F3_*` (2): effect gate present; boundary fail at 0.90−0.75, pass at 0.96−0.75 | **CLOSED** |
| **F4** full structure-blind suite + margin rule | `shortcuts.SUITE` = shuffled_context, query_only, majority_class, most_recent_token, global_most_recent, policy_id_to_outcome; deterministic; `run_suite` emits `shortcut_detected` when any baseline within `structure_blind_margin` (0.10) | `test_F4_*` (2): suite deterministic & complete; margin triggers shortcut | **CLOSED** |
| **F5** distinguish R10 from R11 | Split constructions: `_gen_r10` (no path from root; required fact absent; tenant-pure, no cross-tenant data) vs `_gen_r11` (root path + events exist, but no applicable policy → unsupported); both abstain | `test_F5_*` (2): serializations differ; R10 has no root relation, R11 does; both INSUFFICIENT; R10 tenant-pure | **CLOSED** |
| **F6** stronger length-shortcut check | `length_shortcut_control` exposes lengths by status, a deterministic length-only predictor + its accuracy, overlap flag, and `length_is_trivial_separator`; R10/R11 length-preserving generation | `test_F6_length_control`: applicable; length-only accuracy exposed; ranges overlap; not a trivial separator | **CLOSED** |
| **F7** manifest/replay binding drift | `manifest` adds config_digest, tokenizer_vocab_digest, schema/serializer version; `build_replay_binding` + `verify_replay_binding` bind provenance/seed/phase/checkpoint/prediction/metric/verdict digests and detect drift; `replay.digest_of` | `test_F7_*` (2): each digest change flips `matches`→False with the field named; manifest carries digests | **CLOSED** |

## Preserved conformance (regression-checked, F8)
| Item | Status |
|---|---|
| Tokenizer 80 lexemes / vocab 211 / single-hop untouched | PASS |
| Caps + over-cap rejection | PASS |
| 2901 cap-saturated fixture | PASS |
| Limits 3520 / 384 / 3904 | PASS |
| Parameter count 394,752 / reasoning blocks 131,392 / Δ0 | PASS (analytic) |
| PATH_DISCOVERY hiding | PASS |
| P0 same-checkpoint invariant | PASS |
| Frozen numeric gates unchanged | PASS |
| Verdict precedence (0 protocol → 1 base-capability → …) | PASS |
| Preserved BindingSlots/E1/KDA verdicts co-emitted; forbidden never emitted | PASS |
| Execution lock (EXECUTION_AUTHORIZATION.md unsigned) | PASS |

## Post-smoke corrections (F11–F16)
| Finding | Correction | Test evidence | Status |
|---|---|---|---|
| **F11** generator RNG seeded from the salted builtin `hash(str)` (`_rng` used `hash(split)`/`hash(role)`); the same (seed, split, index, role) produced different episodes in different interpreters (PYTHONHASHSEED), so the "deterministic generator" was not reproducible across runs and the in-process replay check could not see it | `generator._stable_hash` (sha256-derived) replaces both call sites; `config_digest` does not cover generator source, so existing authorization signatures stay valid; no gate/cap/seed/architecture value changed | `test_F11_*` (2): byte-identical episodes and `fact_hash` across subprocesses with PYTHONHASHSEED 0/1/424242 and vs the in-process reference; no bare `hash(` call site in generator source | **CLOSED** (`b16e4e4c`) |
| **F12** B7 ("instructed trivial abstention") generated no visible flag: its input was byte-shaped identically to B1/B5 (same query, same entity list) with the contradictory label INSUFFICIENT_EVIDENCE, so the preregistered B7 ("abstain when a trivial visible flag says 'absent'", chance 0.5) was unlearnable and poisoned B1/B5 | `base_capability`: the queried entity carries `target_attribute PRESENT` (B1, B5) or `target_attribute ABSENT` (B7) as a visible attribute (within `max_attributes_per_entity`); gold outputs unchanged; RNG consumption unchanged | `test_F12_*` (2): flag present on the queried entity and serialized ENT row for all roles; B1 vs B7 differ only in the flag token | **CLOSED** |
| **F13** constant gold answers + inert structure-blind baselines. `_gen_direct`/`_chain` hard-coded `region EU` (R1–R4 gold always `EU`); `_make_policy` hard-coded `VP_APPROVAL_REQUIRED` with risk forced `HIGH` (R8/R9/R12 gold always that outcome; R8 status always SUPPORTED); `query_only`/`shuffled_context`/`majority_class` emitted `NO_ACTION`, never a gold answer, so were 0.0 by construction. A per-operation constant emitter passed the R1–R4/R9/R12 answer gates with `shortcut_detected=False` (verified torch-free on fixture 883004) | Regions drawn uniformly from {EU, NA, APAC, LATAM} for every entity (R1–R4 answer = queried/tail entity's region); policy outcome uniform over `OUTCOME_VOCAB`, independent of policy_id; R8 root risk 50/50 applicable so POLICY_NOT_APPLICABLE occurs; distractor outcomes uniform; `query_only` = majority gold per query signature, `majority_class` = majority (answer,status) over the cohort, both fitted on gold (optimistic bound, conservative for detection). `shuffled_context` remains a placeholder (`[G]`: needs the model on shuffled inputs) | `test_F13_*` (3): no split has a constant answerable gold; the constant emitter now fails every answer gate and trips `shortcut_detected`; real predictors are between 0 and 0.9 and a perfect model is not flagged | **CLOSED** (ratification assumed; separate commit, revertable) |
| **F14** held-out identity pools carried a visible marker. The `32658677` design made train ids end in digits 0/1/2 and final ids in 6/7/8; no training id ever ended in 6/7/8, so the smoke model (seed 8100, 400×15000) copied the letters and emitted a training-pool digit (`DTWXX7`→`DTWXX1`, `TFDJU7`→`TFDJU1`): P0 copy subtasks were 0.0 by construction | `generator._Mint`: all roles draw the same letters and the same digit set; an id is accepted for a role iff `pool_of(id)` (sha256 partition of the id string, 8 buckets: train 4, dev 2, final 1, unit 1) selects that role. Disjointness is invisible to the model; token and per-position distributions are identical across pools | `test_F14_*` (2): pools pairwise disjoint and classified by `pool_of`; every (position, char) pair of held-out ids occurs in train ids; trailing-digit sets coincide | **CLOSED** |
| **F15** `output.is_valid_output` caught only `OutputParseError`; a well-formed output whose `reasoning_path` exceeded `max_reasoning_path_nodes` raised `SchemaError` and crashed `write_predictions` after the report was written | catches schema-cap and type errors and returns False (an over-cap output is invalid, not an exception) | `test_F15_*` (1) | **CLOSED** |
| **F16** opaque ids shared a token class with high-frequency context tokens. Ids were 5 letters + 1 digit; nine-digit amounts put ~72 digit tokens in every context, so the correct trailing digit was one of ~7 identical tokens while each letter was near-unique. Every content-addressed copy run (ABS run 6, RoPE run 7) copied all letters and lost the digit: B1/B2/B4/B5 `all_but_last_char_match` 1.0, `exact` 0.125 | Ids are 6 letters (24-letter alphabet, 1.9×10⁸ combinations), never a frozen lexeme or an outcome token; hash-partitioned pools unchanged (F14) | Controlled smoke diagnostic (calibration log run 8, seed 8100, ABS, 1500×30000, same episodes as run 6 except the last id character): B1 exact 0.125→**1.0**, B2 0→0.75, B5 0→0.75, B6 0.62→0.88, validity 0.979. `test_F16_*`: all ids letters-only across roles, never a lexeme token, every P0 id answer letters-only | **CLOSED** (ratification assumed; isolated commit, revertable) |

Note: any run produced before `b16e4e4c` (including the seed-8100 smoke calibration runs) is internally
consistent within its process but not bit-reproducible from its seed; runs on development/final seeds must use
code at or after this commit.

## Sibling arm BTRR-RoPE (implementation landed; arm NOT ratified, NOT signed, NOT executed)
Per `BTRR_ROPE_SIBLING_ARM_PREREGISTRATION_DRAFT.md`. Owner decisions [2]–[5] were left unfilled; the
recommended defaults are implemented and isolated (F13 is its own commit; budget/dataset values sit in
`config.ARMS["ROPE"]` and the companion JSON).
| Item | Implementation | Test evidence | Status |
|---|---|---|---|
| backbone opt-in positional flag | `BackboneConfig.positional ∈ {learned_absolute (default), rope}`, `rope_theta`; rotary on Q/K per head (half-split, θ 10 000, all pairs, both layers, parameter-free); ABS path byte-identical | `test_rope_runtime.test_abs_build_byte_identical` (digests recorded before the change, seeds 883000/883001); norm-preserving, position-dependent, relative-only dot products; forward at 3904 | landed |
| arm registry | `config.ARMS` (ABS ratified / ROPE draft), `RESERVED_SEED_ARM_ROLES`, `arm_of_seed`, `arm_param_count` (144,896 / 131,392), `frozen_run_params` (dev/final overrides of budget or dataset size raise; smoke/fixtures may calibrate; a seed runs only under its own arm) | `test_arms` (8) | landed |
| per-arm guard | `execution.record_path_for(arm)`; `guard_seed` resolves (arm, role) and checks the arm's record against `config_digest(arm)`; ROPE seeds 8200 / 8201–8203 / 81700–81704 fail closed | `test_arms.test_rope_seeds_fail_closed_everywhere` | landed |
| digest extension | `manifest.config_payload(arm)` binds arm, positional mechanism, architecture dims, **training recipe incl. `n_train_per_split`**, P0 gates, per-arm seeds. **The BTRR-ABS digest changed** (`ba73d7bc…` → `c75b203a…`); the ABS smoke record must be re-signed by the owner | `test_arms.test_config_digest_binds_arm_and_train_recipe` | landed; closes `[G]` |
| companion JSON | `BTRR_ROPE_SIBLING_ARM_PREREGISTRATION.json` (`ratified:false`), values mirror config | `test_arms.test_companion_json_matches_config` | draft |
| record | `BTRR_ROPE_EXECUTION_AUTHORIZATION_RECORD.json`, every role `authorized:false` | `test_arms.test_rope_record_unsigned_and_scoped` | unsigned |
| run path | `run_experiment(..., arm=)`, `train_checkpoint(..., arm=)`, `build_model(seed, arm)`, report carries `arm`/`arm_ratified`/per-arm digest | `test_rope_runtime.test_rope_arm_end_to_end_on_fixture` (5 updates, fixture 883003) | landed |

## Test totals
`tests/test_btrr.py` 28 + `tests/test_corrections.py` 29 + `tests/test_auth_mechanism.py` 12 + `tests/test_harness.py` 10 + `tests/test_arms.py` 8 + `tests/test_rope_runtime.py` 5 (torch; skips without it) = **92 tests, all passing** (stdlib runner; no
pytest/torch; fixture seeds 883000–883004 only; no reserved scientific seed consumed).

## PyTorch runtime status (F10) — CLOSED

Runtime model execution is now **verified** on a torch-capable GPU (previously the builder environment had
no torch, so this was marked pending). The RunPod mechanical-verification heredoc (fixture seed 883000
only; no reserved scientific seed; no smoke/dev/final run) passed every check.

- **Environment:** RunPod, NVIDIA **RTX 6000 Ada (48 GB)**, driver 595.91.07; **torch 2.4.1+cu121**
  (`torch.version.cuda == 12.1`), CUDA available, fp32 + bf16 supported; Python 3.12.
- **Repo state:** branch `claude/symbolu-bindingslots-audit-rps9xe`, pinned to the corrected
  implementation commit `e4dace0e3552ea6bf5572ecdff4fc5768ee7e2cc`; `28 + 18 = 46` tests pass;
  `EXECUTION_AUTHORIZATION.md` unsigned; reserved seeds fail-closed.

| Runtime check | Result |
|---|---|
| Model instantiation | PASS |
| Total params == 394,752 (runtime) | PASS |
| Reasoning-block params == 131,392 (runtime) | PASS |
| Analytic == runtime param count | PASS |
| Weight tying (head ↔ token embedding) | PASS |
| Forward pass / logits dims `(1, L, 211)` | PASS |
| Output-only CE masking / finite loss (≈ ln 211, untrained) | PASS |
| Backward + optimizer step + parameter change | PASS |
| Checkpoint save/reload | PASS |
| Identical parameter digest after reload | PASS |
| Greedy generation bounded by output_token_limit (384) | PASS |
| 2901-token cap-saturated input (== proven max) forwards | PASS |
| Near-3904 sequence (== max_seq) forwards | PASS |
| Same-checkpoint P0→R invariant (digest identical) | PASS |

Artifact: `/workspace/btrr_runtime_verify.log` (retained on the pod). The `torch.load`
`weights_only=False` FutureWarning is a benign torch 2.4 deprecation notice on a self-produced
checkpoint — not a defect. This runtime verification is a mechanical-plumbing check on a
freshly-initialized model; it is **not** a trained or scientific result.

**Still locked (unchanged):** the smoke experiment (seed 8100) remains
`BTRR_SMOKE_AUTHORIZATION_MECHANISM_MISSING`; execution authorization is unsigned; no reserved scientific
seed was consumed.
