# Slot Formation Stabilization — Phase-Free Interventions

Tests whether three **training** interventions can make the frozen bounded-slot **S** circuit form
reliably, **without** changing its architecture. Starting point (immutable): PR #1300 five-seed
`PARTIALLY_STABLE` (3/5) → `NOT_READY_FOR_KDA_VALIDATION`.

## Files
- **Audit:** `LIVE_STATE.md/json`, `SOURCE_INVENTORY.json`, `FROZEN_BASELINE_MANIFEST.json`
- **Pre-registration (frozen, integrity-checked):** `ACCEPTANCE_GATES.json`, `EXPERIMENT_MATRIX.json`,
  `SELECTION_RULE.json`, `CONFIG_HASHES.json`, `PREREGISTRATION.md`, `verify_preregistration.py`
- **Interventions (no frozen file modified):** `interventions.py` (optimizer groups + per-group
  warmup, orthogonal slot-key init, curriculum, write-read alignment), `diagnostics.py` (routing
  diagnostics), `_nso.py` (collision-proof loader for the frozen harness).
- **Runner / orchestration:** `stabilize.py` (arm runner), `run_stage_a.py`, `run_stage_b.py`.
- **Classification (pure stdlib):** `classify_stage_a.py`, `select_candidate.py`,
  `classify_stage_b.py`, `complexity_report.py`.

## Reproduce
```bash
python verify_preregistration.py                 # integrity (must pass before training)
python run_stage_a.py --run-id stageA            # B0,O1,O2,K1,C1,R1,CR1 on seeds 3,6,7 (~6 h CPU)
python classify_stage_a.py --results-dir artifacts/stageA --out ../../artifacts/slot_formation_stabilization/diagnostic_classification.json
python select_candidate.py --classification ../../artifacts/slot_formation_stabilization/diagnostic_classification.json
python run_stage_b.py --run-id stageB            # A+, B0, candidate on fresh seeds 8-12 (~3 h CPU)
python classify_stage_b.py --results-dir artifacts/stageB --candidate <ARM>
```

Arms differ ONLY in the pre-registered surfaces (optimizer groups / warmup, initial slot-key
values, curriculum, temporary alignment loss, diagnostics). B0 reproduces the frozen five-seed S
result on 3,6,7. Alignment λ = 0 after step 600 and during all evaluation; it adds no
inference-time parameter or operation. No Phase / KDA / MLA. Not packaging.
