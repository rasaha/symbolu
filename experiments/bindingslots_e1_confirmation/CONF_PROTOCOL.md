# E1 independent confirmation — frozen protocol

Independent confirmation of the merged PR #1351 result (`EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED`). The
**exact frozen C1 recipe** is reused unchanged; the **task generator, evaluator, leakage suite, and
seeds are independently rebuilt**. Frozen before the final cohort in `results/conf_protocol.json`.
Always preserved: `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`, `KDA_VALIDATION_BLOCKED`.

## What is reused (frozen, not retuned)
- **C1 recipe**: `steps=1200, τ=0.07, train_no_match_frac=0.30, batch=48, lr=1e-3, D=64, 1500 train
  episodes`, learned null key, contrastive episode-local matching, hard top-1 read, ~32 keys/episode.
  Imported directly from the merged `experiments/bindingslots_e1/config.py`.
- **Model architecture** (`models.E1` / `models.B0`) — the frozen bundle.
- **Gate structure + numbers** — the same 17 frozen gates from PR #1351 (`conf_config.GATES`).

## What is independent (new)
- **Task generator** (`conf_task.py`): new vocabulary (56 entity / 22 attribute primitives, 36 values,
  14 filler; new pool salt `e1_conf_pool_v1` → fresh identity partition), a **distinct query template**
  (attribute-anchored, different filler placement/ordering), and **distinct hard-negative profiles**.
  Difficulty is comparable to the validated task (same 3 synonyms/primitive, same 32-key density) — the
  independence is in content, templates, seeds, and evaluator, not in task difficulty.
- **Evaluator** (`conf_eval.py`): metrics re-derived from raw model scores; does **not** call the
  original harness's eval.
- **Leakage suite** (`conf_leakage.py`): independent re-implementation.
- **Fresh seeds**: train-episode seed **71**, dev **[700,701,702]**, final **[5140–5144]** — disjoint
  from every seed used before (V100 28–32, E1 dev 500–502, burned 2028–2032, E1 final 3140–3144, train
  seed 7); asserted mechanically.

## Same held-out categories & density
G1 unseen identity · G2 paraphrase · G3 hard-name confusions · G4 same-entity/different-attribute · G5
recombined facts · G6 no-match · G7 stable. ~32 candidate keys/episode.

## Freeze result (non-reserved)
`determinism_ok = True` (E1 trained twice byte-identical); leakage suite `all_pass = True` (no
query/key exact overlap; disjoint pools; unseen eval identities; no value token in keys; no opaque
per-identity id; lexical-overlap matcher at chance ≈0.05; no external-table import); seed disjointness
`True`. Final seeds unused before lock. Dataset hashes recorded. The final cohort runs once on the
frozen final seeds; no retuning, no gate weakening, no external table in E1 inference.
