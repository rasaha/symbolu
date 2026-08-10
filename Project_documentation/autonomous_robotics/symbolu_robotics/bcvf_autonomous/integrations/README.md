# Planner adapters — TrustWeightComputer integration contract

**§6.3 deliverable.** The autonomy-validated trust-shaping pattern
(§5.1: BCVF kernel → per-source EMA mean centering → significance
gate → softmin; optional §6.6a exclusion) is packaged in
`symbolu_robotics.bcvf_autonomous.trust.TrustWeightComputer` as a
planner-agnostic, stateful class. This README specifies the contract
any planner adapter must meet to consume it.

## API contract

### Inputs

At every planning step, the adapter produces a tensor of predictor
trajectories:

```
trajectories: np.ndarray of shape (K, M, H, 3), dtype float64
    K = number of candidate plans / rollouts
    M = number of predictors (>= 2)
    H = planning horizon (>= 3 for SECOND-order BCVF)
    3 = SE(2) pose (x, y, θ)
```

The adapter is responsible for producing this tensor — that's the
planner-specific part. Common patterns:

- **MPPI**: sample K control sequences, roll each out under all M
  predictors (see `symbolu_robotics.bcvf_autonomous.mppi_planner`).
- **MPC (one-shot)**: enumerate K candidate action sequences from an
  optimizer's inner loop, roll each out under all M predictors.
- **Sampling-based (RRT*-like)**: collect K candidate paths from the
  tree, evaluate each against all M predictors.
- **Selection-only (no optimization)**: K = 1 with a pre-computed
  trajectory; the computer returns a single trust distribution the
  adapter uses as an arbitration signal.

### Calling

```python
from symbolu_robotics.bcvf_autonomous.trust import TrustWeightComputer
from symbolu_robotics.bcvf_autonomous.core import BCVFConfig, CostOrder

computer = TrustWeightComputer(BCVFConfig(
    lambda_c=1.0,                   # > 0 activates BCVF; <= 0 returns uniform
    gate_threshold=0.05,
    gate_beta=400.0,
    huber_delta=0.5,
    use_anchor_pairing=False,       # V2 default — see §2.4.5
    cost_order=CostOrder.SECOND,
))
computer.set_ema_alpha(0.05)        # autonomy-validated default
computer.set_deadband_k_sigma(2.0)  # autonomy-validated default

for episode in episodes:
    computer.reset()                 # clear per-episode state
    for planning_step in episode:
        trajectories = adapter.rollout_predictors(...)  # (K, M, H, 3)
        result = computer.compute(trajectories)
        weights = result.weights                         # (K, M)
        # ... adapter uses weights to form consensus / select action ...
```

### Outputs

```
result: TrustWeightResult dataclass
    weights:                  (K, M), rows sum to 1
    bcvf_total:               (K,), diagnostic sum of pair BCVF cost
    per_pred_cost:            (K, M), raw per-source cost (pre-EMA)
    ema_mean:                 (M,) or None
    ema_std:                  (M,) or None
    deadband_active_count:    int, # rollouts below deadband threshold
    is_excluded:              (M,) bool or None
```

### What the adapter does with `weights`

The `TrustWeightComputer` is **advisory**. It outputs a trust
distribution; how the planner uses it is the adapter's concern:

- **MPPI reference adapter** (`mppi_planner.py`): computes a
  trust-weighted consensus trajectory per rollout (`(K, H, 3)`),
  scores that consensus against the performance cost, applies MPPI
  softmax to pick the next control.
- **Argmin selector** (non-MPPI reference, see below): computes the
  trust-weighted consensus per rollout, picks the single rollout with
  the lowest performance cost — no MPPI softmax.
- **MPC adapter** (future): feeds `weights` into the MPC cost
  function as a per-predictor weighting on the disagreement term.
- **Routing adapter** (future): picks the single predictor with
  `argmax(weights[0])` (K = 1 case) and uses its trajectory directly.

## Contract guarantees

The `TrustWeightComputer` guarantees:

1. **Lemma 1 invariance is preserved.** When all pairwise predictor
   disagreements are constant or linear-drift in time, per-source
   cost is exactly zero, so trust weights are uniform and the
   consensus equals the equal-weight mean. See §2.6 of the LLM
   design doc for the formal proof (applies to the SE(2) case as a
   special dimension-agnostic instance).
2. **No kernel modification.** Calling the computer runs the same
   `core.compute_bcvf_cost_batch` the autonomy kernel has always run.
   Tests in `tests/test_core.py` stay valid.
3. **State lifecycle is episode-scoped.** EMA mean/variance and
   exclusion counters live across `compute()` calls within a
   `reset()`-bounded episode. `reset()` clears them.
4. **Setters never break running state.** Calling `set_ema_alpha`
   mid-episode re-initializes the EMA (next `compute()` seeds it
   from that step's cost), never leaving a mixed half-EMA/half-raw
   configuration.
5. **`lambda_c <= 0` short-circuits to uniform weights.** No kernel
   call is made. Matches the A0 baseline semantics.

## Deviations from V1 planner behavior

The refactor in `5114f44` is **behavior-preserving** at the test-level
bit-accuracy. All 190 autonomy tests pass unchanged. Any new adapter
must also preserve these invariants or document its deviation
explicitly.

## Example non-MPPI adapter (argmin selector)

A minimal non-MPPI reference lives in `integrations/argmin_selector.py`.
It demonstrates that `TrustWeightComputer` is genuinely decoupled
from MPPI:

- Builds the `(K, M, H, 3)` tensor the same way MPPI does.
- Calls `computer.compute(trajectories)` to get weights.
- Computes the trust-weighted consensus trajectory per rollout.
- Evaluates `compute_perf_cost` on each consensus trajectory.
- Picks the **single argmin-cost rollout** (no MPPI softmax).
- Returns its first control.

This is a legitimate planning loop — one that would behave similarly
to MPPI under zero-noise candidates but degrades gracefully to a
"best-so-far" rule under stochastic rollouts. It uses **the same
trust computer** the MPPI planner uses, with **zero code duplication**
between the two planners.

## Adding a new adapter

1. Create `integrations/my_planner.py`.
2. Hold a `TrustWeightComputer` instance on the planner class.
3. In the planning loop, produce `(K, M, H, 3)` trajectories and call
   `computer.compute(...)`.
4. Use `result.weights` to form consensus / select action per your
   planner's rule.
5. Write an integration test in `tests/test_<my_planner>.py` that
   verifies (a) planner works with the computer disabled (lambda_c=0),
   (b) weights-row-sum-to-1 invariant, (c) Lemma 1 invariance on
   constant-bias / linear-drift predictor inputs.
6. Document any deviations from the V1 invariants above.

Do not modify `trust.py` unless you are adding a capability the
autonomy-validated pattern does not cover. If you need to tune
trust-shaping behavior, use the setters (`set_ema_alpha`,
`set_deadband_k_sigma`, `set_exclusion`, `set_trust_temperature`)
rather than reaching into internal state.
