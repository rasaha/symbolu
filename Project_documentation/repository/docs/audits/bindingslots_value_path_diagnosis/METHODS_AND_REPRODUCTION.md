# Methods and reproduction feasibility

**Diagnostic phase only. No fix is implemented. KDA validation remains BLOCKED.**

## Why reproduction-for-instrumentation is necessary and authorized

The merged persistence screen (`NO_PERSISTENCE_INTERVENTION_SELECTED`, PR #1340, merge `05dcee8e`)
committed per-checkpoint *metrics* but **no model-weight checkpoints** (`*.pt` are git-ignored by
repository policy). The value-path and gradient diagnostics require the model's **internal tensors**
(slot values, reads, memory contributions, per-loss gradients), which are not in the committed
evidence. There is therefore no shortcut: the historical runs must be re-executed to observe their
internals.

This is authorized as **deterministic reproduction-for-instrumentation**: the exact original training
schedule and optimizer steps are re-run with no step added, removed, or altered. The runs are
deterministic (CPU fp32, `random.seed(s)`/`torch.manual_seed(s)`, data order `Random(seed*991+7)`,
dropout 0, `torch.set_num_threads(4)`), and the diagnostics never advance the training RNG, so the
re-execution is **bit-identical** to the committed run.

## Reproduction proof

- **Control determinism (frozen before failure exemplars):** A+ seed 25 reproduced byte-identically —
  `needle_by_dist` and `ppl` exact, trajectory exact at every common checkpoint — establishing the
  EXACT-equality gate on a control, not on a failure seed.
- **Gate:** every cohort run is compared field-by-field against its committed `raw_record`
  (`needle_by_dist`, `ppl`, `binding_by_k`, `supersession`, `source`, `multihop`, the full
  `trajectory` including correct-slot probability / rank / address margin / grad norms, `ablation`,
  `loss_log`) for **exact equality**. Only wall-clock `train_s` is excluded. A run that fails is
  `INSTRUMENTED_REPRODUCTION_FAILED` and its tensors are not used as evidence.
- **No extra steps:** `torch.optim.AdamW.step` is wrapped only to *count* steps; every run is asserted
  to take exactly 1200 optimizer steps.

## Instrumentation is a pure observer

- Snapshots at **600 / 700 / 900 / 1200** are `deepcopy`s taken at the committed `record(step)`
  boundary. `deepcopy` consumes no torch RNG and touches no optimizer state; training reproduction
  always uses the **stock** frozen forward.
- The instrumented `BindingSlots.forward` is **byte-identical** to the frozen forward when
  `mode=None` (proven: identical logits) and only otherwise captures tensors or applies a single
  isolated oracle read override.
- All later diagnostic evaluations run on **frozen** snapshots with **zero** optimizer steps; model
  state hashes are asserted unchanged across every diagnostic.

## Architecture binding (no fusion gate)

The live read path is
`u_read = Σ_j r[j]·slot[j] ; c_mem = W_o(u_read) ; h_post = h_pre + c_mem`, with the slot
contribution added into the block residual alongside the local-window attention
(`x = x + local(n1 x) + slots(n1 x)`). **There is no learned read or fusion gate** — the only gate is
the *write* gate `sigmoid(gate(x))` inside the slot memory. Fusion-gate values, sensitivity, and
gradients are therefore never reported. Captured tensors and shapes are enumerated in
`tensor_manifest.json`.

## Cohort and thresholds are frozen before inspection

The cohort (`cohort.json`, symmetric {A+, R0, O1R, H2} × {23, 24, 25}) is recovered mechanically from
the merged ledger and committed before any tensor is inspected. Every decision threshold
(`diagnosis_classify.py` `FROZEN_CONSTANTS`) is fixed from the read-path structure and control runs,
never from the failure exemplars, and the reproduction gate is EXACT equality with no free parameter.
