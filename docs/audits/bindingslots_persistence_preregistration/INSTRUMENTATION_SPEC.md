# Instrumentation spec

All new instrumentation is **observation-only** (detached values; no graph retention; no effect on
loss/optimizer/RNG/data-order/gradients/params). Capture-hook definitions are the frozen
`interventions.install_capture_hooks` (unchanged); the persistence building blocks in
`objectives_persistence.py` read only detached slot-address vectors.

## Per checkpoint (0/60/120/300/600/700/900/1200)

needle; correct-slot probability; correct-slot rank; address margin; slots-off (where scheduled);
randomized-address (where scheduled); current auxiliary coefficient; training loss; primary-task loss;
auxiliary loss; quality (perplexity); distance; slot-contribution magnitude; address-distribution
entropy; routing-state summary.

## Arm-specific

- **H1:** routing-parameter update norm; cumulative displacement from step 600; normalized
  displacement; effective LR; gradient norm.
- **H2:** teacher/student agreement; teacher/student divergence (KL); correct-address teacher mass;
  correct-address student mass; teacher-loss value; teacher checkpoint hash.
- **O1R:** residual objective value; residual coefficient; correct-slot metric under residual supervision.

Schemas: `experiments/bindingslots_persistence/schemas/checkpoint_metrics.schema.json`,
`routing_trajectory.schema.json`, `causal_ablation_result.schema.json`. Exact field definitions are
frozen here before training.
