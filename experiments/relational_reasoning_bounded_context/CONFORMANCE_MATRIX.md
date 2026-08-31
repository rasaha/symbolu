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

## Test totals
`tests/test_btrr.py` 28 + `tests/test_corrections.py` 18 = **46 tests, all passing** (stdlib runner; no
pytest/torch; fixture seeds 883000–883004 only; no reserved scientific seed consumed).

## PyTorch runtime status (F10)
torch is absent in the builder environment. Runtime model execution is **NOT** claimed verified. Retained:
analytic parameter assertions (`config`/`model.analytic_parameter_count`), lazy torch imports
(`model.py`, `trainer.py`). **Outstanding:** actual model-runtime verification (build_model /
parameter_digest / training) pending a torch-capable environment. torch was not installed or vendored.
