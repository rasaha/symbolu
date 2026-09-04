# E1-S — explicit-key addressing scale-up (implementation; fixtures only)

Preregistration: `docs/research/hybrid_llm/benchmarks/EXPLICIT_KEY_ADDRESSING_SCALEUP_PREREGISTRATION_DRAFT.md`
(ratified 2026-09-04) + companion `E1S_PREREGISTRATION.json` (frozen values, `config_digest`). Reserved seeds
(development 6100–6102, final 6140–6144) fail closed behind the two-key guard until the owner signs
`E1S_EXECUTION_AUTHORIZATION_RECORD.json` and the operator supplies `E1S_EXEC_TOKEN`. Seeds of every prior
experiment block are refused outright. Fixture seeds 886000–886004 are ungated and scientifically inadmissible.

| module | role |
|---|---|
| `e1_import.py` | loads `experiments/bindingslots_e1/{task,models,engine}.py` UNCHANGED (sha256 byte-identity asserted on every load) |
| `keyspace.py` | enterprise-shaped keys `(subject_type, subject_id, relation_type, object_type) -> value`; synonym-paraphrased types, verbatim ordered-pair ids (reserved token class), invisible hash-partitioned pools, held-out (ST, REL) compositions, near-miss profiles as fractions of K (K=32 reproduces E1's counts), splits G1–G8 |
| `config.py` | frozen recipe (E1 selection C1), density ladder (32 / 128 / 512), gates (E1's + G8), seeds, verdict vocabulary |
| `execution.py` | two-key fail-closed guard (BTRR mechanism) |
| `manifest.py` | `config_digest()` binds vocabulary, ladder, recipe, profiles, splits, gates, seeds, E1 source digests |
| `leakage.py` | mechanical leakage suite adapted from E1 (paraphrase overlap, reserved id class, pools, unseen targets, held-out pairs, lexical-overlap bound, no table import) |
| `shortcuts.py` | structure-blind baselines (leave-one-out query-only majority, most-frequent value, random valid key, lexical overlap) + margin rule |
| `gates.py` | E1's `eval_seed_gates`/`nomatch_precision_recall` reused + G8; density-ladder verdict |
| `run.py` | `run_density`, `run_seed`, `anchor_check`, `aggregate`, predictions dump, `rescore_predictions_file` |

E1 reuse: `E1`, `B0`, `collate`, `eval_e1`, `eval_b0`, `param_hash`, `set_determinism` are imported unchanged.
`train_e1` / `train_b0` are replicated line for line only because E1's versions construct `E1()` / `B0()`
with E1's task defaults (vocab 250, 32 slots); this package passes `vocab=226`, `n_slots=K`.

Parameter counts: E1 = V·64 + 2·(64·64+64) + 64 → **22,848** at V=226 (24,384 at E1's V=250);
B0 = V·64 + K·64 + 3·(64·64+64) + (64·32+32) → 30,592 / 36,736 / 61,792 at K = 32 / 128 / 512.

Tests (stdlib runners, fixtures only):
```
python3 -m experiments.explicit_key_scaleup.tests.test_e1s            # torch-free
python3 -m experiments.explicit_key_scaleup.tests.test_e1s_runtime    # torch+numpy; skips without them
```
