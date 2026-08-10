# BCVF Autonomous — Observables Framework + Per-Step Trust Diagnostics

Design notes for two pieces ported from `symbolu_bcvf_llm` into the autonomous
product line:

1. **Observables framework** — agreement, ensemble spread (entropy analog),
   coherence-anchored BCVF, BCVF per-step max, predictor-attributed BCVF
   per-step max, uncertainty-gated BCVF per-step max.
2. **Per-step trust diagnostics** — `TrustStepRecord` /
   `TrustShapedEpisodeRecord`, the autonomous analog of BCVF LLM's
   `TrustShapedDecodeResult`.

The goal is to give the autonomous stack the same explanatory surface BCVF
LLM enjoys: at any moment we can say *why* a predictor was trusted or
distrusted, not only that it was.

## §1 Motivation

The current autonomous stack computes per-predictor BCVF cost, EMA-normalizes
it, runs it through a deadband, and softmin-blends the predictor rollouts
into a consensus trajectory the planner ranks. The math kernel is solid; what
is missing is everything *around* it:

* No ensemble-level probes (agreement, spread, coherence) that can be probed
  against ground-truth outcomes (collision, recovery) to validate that BCVF
  is actually firing on the right signal.
* The trust log captures aggregates per planning tick (mean / std / max
  across rollouts) but not the per-step trust state in a structured form
  that survives into a typed artifact for incident review.

Both gaps are filled by porting two BCVF LLM modules with autonomous
semantics: per-token → per-horizon-step inside a tick, and per-decode-step
→ per-planning-tick across an episode.

## §2 Mapping table — BCVF LLM ⇄ BCVF Autonomous

| BCVF LLM concept | Autonomous concept |
| --- | --- |
| `Source` (HF / Mock / Paraphrase) | `BasePredictor` (IMU / LiDAR / VO / GNSS) |
| `(prompt_tokens, choice_tokens)` | `(M, H, 3)` predictor trajectory tensor |
| Per-token step | Per-horizon-step inside a planning tick |
| Per-decode-step record | Per-planning-tick record across an episode |
| Token argmax / EOS | Simulator tick boundary |
| Vocabulary `V` | SE(2) pose dimension `(x, y, theta)` |
| Cross-source agreement on argmax | Predictor agreement within position / heading tolerance |
| `entropy(source_0_logits)` | Ensemble spatial spread (radial dev of predictors) |
| `coherence × first_token_alignment` | `1/(1 + max-step BCVF) × exp(-mean alignment error)` |
| `bcvf_per_step_max` | Same name; same reduction over the BCVF stencil |
| `uncertainty_gated_bcvf_per_step_max` (entropy gate τ=1 nat) | Same name; ensemble-spread gate τ=0.5 m |
| `TrustShapedDecodeResult` | `TrustShapedEpisodeRecord` |
| `TrustShaperStep` | `TrustStepRecord` |
| Decoder loop | `MPPIPlanner.plan()` × simulator |
| `decode_trust_shaped(...)` | `Runner.run()` with `trust_diagnostics_enabled=True` |

The mapping is tight enough that a probe report from BCVF LLM
(SAFETY_CORRELATED / UNCORRELATED / ANTI_CORRELATED / NULL bands)
reads identically here, modulo the polarity of the outcome label
(positive event = collision in autonomous, positive event =
correct answer in LLM — caller responsibility, not the
framework's).

## §3 Observables — public surface

All observables implement the `Observable` Protocol:

```python
class Observable(Protocol):
    name: str
    higher_means_more_suspicious: bool
    def observe(
        self,
        trajectories: np.ndarray,           # (M, H, 3)
        ground_truth: Optional[np.ndarray]  # (H, 3) or None
    ) -> ObservableValue: ...
```

`ObservableValue` carries `scalar`, optional `per_predictor`
decomposition `(M,)`, and `metadata` for diagnostics. Six
implementations land in this port:

* **`PredictorAgreementObservable`** — fraction of horizon steps
  where every predictor sits within `(pos_tol, heading_tol)` of
  the ensemble mean. Cheapest probe — no kernel call. Polarity:
  suspicion (higher = predictors disagree more often).
* **`EnsembleSpreadObservable`** — mean over horizon of per-step
  radial deviation of predictors from the ensemble mean. The
  spatial analog of LLM next-token entropy. Polarity: suspicion.
* **`EnsembleHeadingEntropyObservable`** — circular-statistics
  dispersion of predictor headings (`1 - |mean(unit_vectors)|`).
  Polarity: suspicion.
* **`BCVFPerStepMaxObservable`** — max across horizon steps of
  the summed-across-pairs BCVF cost for that step. Direct port of
  the LLM `bcvf_per_step_max` reduction. Polarity: suspicion.
* **`BCVFPredictorPerStepMaxObservable`** — max across horizon
  steps of the BCVF cost attributed to a single predictor (sum of
  pair costs containing it). The "lone failing predictor" probe.
  Polarity: suspicion.
* **`CoherenceAnchoredBCVFObservable`** — `1/(1+max_step_bcvf) ×
  exp(-mean_alignment_error / scale)`. The autonomous analog of
  the LLM coherence-anchored BCVF. Defaults alignment to 1.0 when
  ground truth is unavailable so the observable doubles as a
  pure-stability probe at planning time. Polarity: trust.
* **`UncertaintyGatedBCVFPerStepMaxObservable`** — the same
  `bcvf_per_step_max` reduction restricted to horizon steps where
  ensemble spread exceeds a pre-committed threshold (default
  τ = 0.5 m). The autonomous analog of the LLM entropy-gated
  observable. Polarity: suspicion.

The probe harness `probe_observable(observable, samples)` accepts
an iterable of `(trajectories, outcome_label, ground_truth_or_None)`
and reports Pearson r, Spearman ρ, AUC, and a classification band
(`SAFETY_CORRELATED` / `UNCORRELATED` / `ANTI_CORRELATED` / `NULL`).

## §4 Per-step trust diagnostics — public surface

Three building blocks:

* `TrustStepRecord` — typed record for one planning tick. Holds
  the rollout-aggregated weights `(M,)`, per-predictor cost `(M,)`,
  EMA state `(M,)`, deadband / exclusion flags, and BCVF total.
* `TrustShapedEpisodeRecord` — episode container. Stacks the
  per-tick records into `(T, M)` arrays plus a few `(T,)` scalars
  (BCVF total, deadband-active count, gate activations) and keeps
  the raw record list. `to_dict()` serializes to JSON.
* `TrustDiagnosticsRecorder` — stateful per-episode recorder.
  Consumes `TrustWeightResult` instances directly from the
  consumer-layer `TrustWeightComputer`, so non-MPPI planners can
  reuse the same recorder.

Each tick's `(K, M)` weight matrix is collapsed into the per-tick
`(M,)` record via `RolloutAggregation`:

* `MEAN` (default) — population view. Best for "what did the
  trust pipeline believe on average this tick?"
* `ARGMIN_TOTAL` — pick the rollout with the lowest summed
  per-predictor cost as a stand-in for "the rollout the planner
  chose." Useful when the recorder lives outside the planner and
  cannot ask which rollout won.

### Wiring

The `MPPIPlanner` exposes `set_trust_diagnostics_enabled(enabled,
aggregation)` and `get_trust_diagnostics()`. The recorder ticks
once per `plan()` call regardless of `lambda_c` so the `(T, M)`
arrays line up with simulator tick indices — uniform-weight
records are emitted when BCVF is inactive.

`Runner.run()` wires the recorder via three `RunConfig` knobs:

* `trust_diagnostics_enabled: bool` — turn it on in-memory only.
* `trust_diagnostics_path: Optional[str]` — also dump to JSON.
* `trust_diagnostics_aggregation: "mean" | "argmin_total"`.

`Runner.trust_diagnostics()` returns the finalized
`TrustShapedEpisodeRecord` after `run()` completes.

## §5 Performance budget

* Observables run *outside* the hot planning loop — a probe
  pass over a logged corpus, not inside `plan()`. The per-step
  kernel helper `compute_bcvf_per_step` is `O(pairs × H)` and
  uses the same vectorized primitives as `compute_bcvf_cost`;
  it is allocation-cheap.
* The trust-diagnostics recorder runs *inside* `plan()` but
  stores ~ `(K, M)` of float64 per tick (a few bytes per
  predictor per tick). For T=200 ticks × M=4 predictors that
  is ~6 KB per episode — small enough to leave on by default
  during testing and turn off only for production fleets where
  the per-episode artifact storage is the budget concern.
* Neither change touches the trust kernel itself; the legacy
  trust log path is preserved bit-for-bit.

## §6 What is intentionally *not* in scope

* No port of the BCVF LLM `Source` / `Decoder` abstraction —
  predictors are concrete; an abstraction adds nothing today.
* No port of speculative decoding — MPPI's H-step rollout
  already provides lookahead.
* No port of the paraphrase source — multi-modal sensors are
  the autonomous analog and they are already concrete.
* No port of the §14a Scout consumer variants — that's the next
  recommended port, *after* this one's observables prove the
  signal exists.

## §7 Test surface

`tests/test_observables.py` covers:

* `compute_bcvf_per_step` reproduces `compute_bcvf_cost.total_cost`.
* Each observable returns the expected polarity on a synthetic
  failure trace (one predictor injected with a constant bias).
* The probe harness produces `SAFETY_CORRELATED` for an
  observable known to discriminate, `NULL` for `n < 40`,
  `UNCORRELATED` for noise.

`tests/test_trust_diagnostics.py` covers:

* `TrustStepRecord` shapes match the input `TrustWeightResult`.
* Both `MEAN` and `ARGMIN_TOTAL` aggregations produce sensible
  records.
* `TrustShapedEpisodeRecord.to_dict()` round-trips through JSON.
* `MPPIPlanner.set_trust_diagnostics_enabled(True)` produces
  non-empty per-tick records after a multi-step planning loop.
