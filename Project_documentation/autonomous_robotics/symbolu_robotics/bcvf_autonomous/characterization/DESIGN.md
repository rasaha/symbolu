# BCVF Autonomous — Characterization Sweep

A regression suite that proves BCVF detects each canonical sensor-failure
class. Ported from `symbolu_bcvf_llm.characterization` with autonomous
semantics: SE(2) trajectory bundles instead of probability sequences,
sensor dropout instead of EOS truncation, sensor-class failure thresholds
instead of softmax invariance thresholds.

The point of the suite is to make a SOTIF / ISO 26262 argument legible:
*"For each named sensor failure class, the BCVF observer either rings
the bell or it doesn't, and we have a numeric threshold on the relevant
quantity that we can certify against."*

## §1 Motivation

The existing autonomous `traces.py` does parameter sweeps with two
trajectories. That's enough to validate the gate / Huber / dt knobs but
not enough to validate the kernel against the canonical failure
taxonomy. Two gaps:

* No `M = 3` bundle structure — outlier-attribution requires "two
  healthy predictors plus one failing predictor" to test that BCVF
  doesn't just notice disagreement, it points at the right offender.
* No noise floor / dropout families — these are the families that
  most often blow up safety arguments, because a system that fires on
  noise is as bad as a system that misses real failures.

This module fills both gaps by porting the seven-family LLM design.

## §2 Family taxonomy

| Family | Maps from LLM | Sensor-failure analog | Should fire BCVF? | Truth label? |
| --- | --- | --- | --- | --- |
| `baseline` | `baseline` | All predictors agree | No | No |
| `constant_bias` | `constant_bias` | Sensor with miscalibrated origin | No (under SECOND order) | No |
| `linear_drift` | `linear_drift` | IMU bias / GNSS clock drift | No (under SECOND order) | No |
| `accelerating` | `accelerating` | Predictor diverging quadratically | Yes | Yes — predictor 1 |
| `noise_floor` | `noise_floor` | All sensors noisy below threshold | No | No |
| `outlier` | `outlier` | One predictor accelerating, others healthy | Yes | Yes — predictor 0 |
| `sensor_dropout` | `eos_truncation` | One sensor freezes (LiDAR / GNSS dropout) | Yes | Yes — dropped predictor |
| `adversarial_consistent_bias` | _no LLM analog_ | Spoofed sensor feeding plausibly-noisy data with a hidden constant bias (UN ECE R155 cybersecurity) | Conditional — see §3.5 | No (Lemma-1 trapdoor) |

The `M = 3` bundle is canonical for outlier attribution: two healthy
predictors form a "majority truth" and the kernel must put more cost
on the third. `M = 4` is supported for parity with the production
autonomous predictor set (IMU + LiDAR + VO + GNSS).

## §3 Polarity convention

* `nominal` families (`baseline`, `constant_bias`, `linear_drift`,
  `noise_floor`) MUST stay below their per-family cost / activation
  thresholds. Failing here is a false-positive — the observer is
  jumpy.
* `failure` families (`accelerating`, `outlier`, `sensor_dropout`)
  MUST exceed their per-family cost / gate / alignment thresholds.
  Failing here is a false-negative — the observer is asleep.
* `adversarial` families (`adversarial_consistent_bias`) are a
  **third polarity** — see §3.5 for the cybersecurity scope. The
  acceptance criterion is bounded-and-well-behaved (no Huber
  overflow); the kernel-layer detection question is regime-
  dependent and reported as the per-config Wilson stats rather
  than gated by a single must-fire / must-stay-quiet rule.

The sweep harness reports all three buckets, by family and by
parameter cell, so a SOTIF audit can read the table directly. The
fleet-level rates are exposed on `GridSummary` as
`false_positive_rate` (nominal-family false alarms),
`false_negative_rate` (failure-family misses), and
`adversarial_pass_rate` (cybersecurity-tier behaviour).

## §3.5 Cybersecurity scope (UN ECE R155)

The seven non-adversarial families cover **honest** failure modes —
predictors that drift, accelerate, freeze, or noise out without
intent. The eighth family `adversarial_consistent_bias` covers an
**attacker** who has spoofed a sensor to feed plausibly-noisy data
with a hidden constant lateral bias. The attacker's constraint:
match the honest noise floor closely enough that BCVF doesn't
flag the spoofed predictor as anomalous.

### 3.5.1 What the kernel can and cannot detect

The BCVF kernel's second-order Lemma-1 invariance — by design,
constant offset between predictors produces zero second-derivative
disagreement and therefore zero gate-cost — is the **trapdoor**
the attacker exploits. Three regimes characterise the attack:

| Bias range | Gate behaviour | Kernel detection | Cybersecurity implication |
|---|---|---|---|
| **Stealth** (`bias ≪ T`) | Gate stays closed; constant-bias signal sits below the activation threshold. | Provably invisible (Lemma 1). Per-predictor cost is symmetric — kernel can't single out the attacker. | This is the genuine attack window. Defence in depth (cross-modal verification, signature attestation) is the layer that catches it; the kernel cannot. |
| **Transition** (`bias ~ T`) | Gate opens intermittently when noise spikes combine with the bias. | Kernel fires on some seeds, misses on others. Per-config Wilson CIs surface the rate. | Reviewer reads the per-config CI as evidence of the kernel's edge sensitivity in the threshold neighbourhood. |
| **Loud** (`bias ≫ T`) | Gate is open every tick; the constant bias unlocks the noise's second-derivative contribution to cost. | Kernel reliably fires via the gate-noise interaction. | The "obvious" spoof is *not* the cybersecurity concern — BCVF catches it cleanly. |

The `adversarial_consistent_bias` family runs at four magnitudes
(`0.005, 0.01, 0.05, 0.5`) spanning the full arc, so a UN ECE R155
reviewer reading `summarize_grid(...).per_config` sees every
regime's per-cell Wilson CI without needing to guess where the
boundary sits.

### 3.5.2 Planner-layer harm despite kernel-layer silence

The Lemma-1-trapdoor isn't a "no harm" story — the trust-weighted
consensus is dragged toward the attacker's biased trajectory by
approximately `bias × weight_attacker`. With `M = 3` and uniform
trust that's `bias / 3`. Over a long mission the cumulative
heading / lateral error compounds. The dedicated test
`test_adversarial_stealth_attack_succeeds_at_consensus_layer`
pins this — a kernel change that started catching the stealth
attack would *fail* the test, because the documented behaviour is
"BCVF correctly stays quiet, planner-level harm is real, defence
in depth required."

### 3.5.3 Out-of-scope mitigations

The kernel does not mitigate stealth-bias spoofs. The deployment-
partner-side mitigations the safety-case narrative points at:

* **Cross-modal sensor attestation** — independent verification
  that the sensor stream came from the registered hardware (e.g.
  signed firmware + per-message MAC). UN ECE R155 §7.3.4.
* **Cross-class redundancy** — comparing a LiDAR pose estimate
  to a GNSS pose estimate at the post-arbitration layer; bias
  invisible to BCVF between two predictors of the same class
  becomes visible against a different class.
* **Calibration drift monitoring** — a sensor whose constant-bias
  spoof is internally consistent over a single trip will appear
  inconsistent across trips compared to its calibration record.

These layers are out of scope for the BCVF kernel itself; the
characterization grid surfaces the kernel-layer scope boundary
explicitly so the deployment partner knows where to add defence
in depth.

## §4 Per-family acceptance tables

Each family has its own pass criterion. The sweep returns a
`failure_reasons` tuple per cell so an auditor can see exactly
which gate fired.

### 4.1 baseline
* `total_cost < 1e-6`
* `max_acceleration_norm < 1e-6`
* `gate_activations == 0`
* `per_predictor_cost[i] < 1e-6` for all `i`

### 4.2 constant_bias
* `total_cost <= 1e-9` (fp64 precision)
* `max_acceleration_norm <= 1e-9`
* `per_predictor_cost[i] <= 1e-9` for all `i`

### 4.3 linear_drift
* Same as `constant_bias` — second derivative of a linear function
  is zero, so SECOND-order BCVF must register zero cost up to fp64
  noise.

### 4.4 accelerating
* For magnitude `>= 0.3`: `total_cost > 1e-3` AND
  `gate_activations > 0`.
* `total_cost` finite and bounded (Huber upper bound at `1e8`).
* Alignment: truth predictor (the accelerating one) is rank 1, or
  rank 2 with margin `>= 1.0`.

### 4.5 noise_floor
* For `sigma_noise <= 0.01`: `total_cost < 1e-2`.
* For `sigma_noise <= 0.005`: `std(per_predictor_cost) /
  mean(per_predictor_cost) < 0.5` — every predictor should attract
  a similar share of the (small) cost; lopsided attribution on a
  pure noise input is a bug.

### 4.6 outlier
* Truth predictor cost / max(non-truth predictor cost) `>= 1.5`.
* `gate_activations > 0`.
* `total_cost > 1e-3`.
* Alignment (strict): truth predictor must be rank 1.

### 4.7 sensor_dropout
* `total_cost` finite.
* For `0 <= k_dropout < H - 5`: `gate_activations > 0` AND
  `total_cost > 1e-3`. The frozen predictor's pose stops moving
  while others continue, so the disagreement velocity grows
  linearly post-dropout and the gate fires.
* Alignment (loose): dropped predictor is **not last** in the
  per-predictor cost ranking. The default sweep wraps `outlier`
  with dropout on a different predictor, so the outer outlier can
  legitimately dominate the BCVF attribution; the dropout's only
  requirement is that its own predictor doesn't sink to the
  bottom of the rank table.

### 4.8 adversarial_consistent_bias
The cell-level acceptance is **deliberately permissive**. The
family's purpose is to expose the kernel's behaviour across the
stealth → transition → loud bias regime described in §3.5, not to
gate the kernel's correctness on a single must-fire / must-stay-
quiet rule.

* `total_cost` finite (no NaN / inf escape from the Huber bound).
* `total_cost < 1e8` (Huber upper-bound sanity).
* For stealth bias (`bias <= 0.01`): `total_cost < 5.0` —
  catches a kernel that suddenly over-reacts on sub-threshold bias
  (the Lemma-1 trapdoor is the documented behaviour, not a
  regression target).
* No alignment criterion (`truth_label = None` — the kernel
  cannot attribute a Lemma-1-invariant attack at this layer).

The cybersecurity-reviewer-facing evidence is the per-config
Wilson CI plus the cost / gate-activation magnitudes, surfaced in
`summarize_grid(...).per_config` and the auditor markdown report
written by `GridSummary.to_markdown_report`. The reviewer reads
each magnitude row and forms an independent judgement about the
kernel's detection rate at that magnitude, rather than relying on
a binary pass/fail.

## §5 Sweep grids

### 5.1 Primary grid

Every family × magnitude × seed at the V1 default `(T, β, δ) =
(0.2, 100.0, 0.5)`. Magnitudes per family in
`FAMILY_MAGNITUDES`. **60 deterministic seeds (`range(42, 102)`)
per cell** — the audit flagged the prior 3-seed-per-cell coverage
as too narrow for a certification-grade statistical bound. At
the threshold-edge magnitudes (e.g. `accelerating` at `accel_mag
= 0.3`, where the kernel is most likely to flip pass→fail with a
small kernel change) a 3-of-3 pass / 0-of-3 fail flip can land
without the suite catching it. 60 seeds + a per-config Wilson
95% CI lower-bound floor (see §6.1) gives the suite an explicit
statistical contract a SOTIF auditor can quote.

Total cells per default invocation:

| Family | Magnitudes | Seeds | Cells |
| --- | ---: | ---: | ---: |
| baseline | 1 | 60 | 60 |
| constant_bias | 4 | 60 | 240 |
| linear_drift | 4 | 60 | 240 |
| accelerating | 4 | 60 | 240 |
| noise_floor | 4 | 60 | 240 |
| outlier | 1 | 60 | 60 |
| sensor_dropout | 4 | 60 | 240 |
| adversarial_consistent_bias | 4 | 60 | 240 |
| **Total** | | | **1560** |

A pass requires every cell to satisfy its family's threshold table
and (where applicable) the alignment criterion. Beyond the per-cell
gate, every (family, magnitude) **config** must additionally meet
the §6.1 Wilson CI floor.

The legacy 3-seed tuple (`LEGACY_PRIMARY_SEEDS = (42, 43, 44)`) is
retained as an exported constant for callers that explicitly want a
smoke-grade smoke run; no internal call site uses it.

### 5.2 Sensitivity grid

Canonical magnitude per family × `(T, β, δ)` cube.

* `T ∈ {0.1, 0.2, 0.5}`
* `β ∈ {50, 100, 200}`
* `δ ∈ {0.25, 0.5, 1.0}`

`SENSITIVITY_SEEDS = (42, 43, 44)` × seven families × 27
parameter cells = 567 cells per default invocation. The winner-
tuple selector (`pick_winner_tuple`) returns the `(T, β, δ)`
closest to the V1 defaults that produces an all-pass row. The
sensitivity grid intentionally keeps a 3-seed cadence — its job
is to cover the parameter cube, not to certify per-config
pass-rate confidence intervals (the primary grid does that).

### 5.3 Ablation grid

`linear_drift` × `CostOrder ∈ {ZEROTH, FIRST, SECOND}` × seeds.
Confirms only `SECOND` rejects linear drift — the other two orders
must fire on it. This is the kernel's order-of-derivative claim
distilled into a regression test.

## §6 Aggregate diagnostics

`summarize_grid(cells)` returns:

* `n_cells` — sweep size.
* `per_family` — per-family pass rate + alignment summary.
* `false_positive_rate` — fraction of nominal-family cells that
  failed (BCVF fired on a quiet input).
* `false_negative_rate` — fraction of failure-family cells that
  failed (BCVF stayed quiet on a real failure).
* `per_config` — list of `PerConfigPassStat` records (one per
  (family, magnitude) cell) with `n`, `passed`, `pass_rate`,
  Wilson-CI `ci_low` / `ci_high`, and a
  `meets_certification_floor` boolean (see §6.1).
* `min_ci_lower_bound` — the worst per-config Wilson lower bound
  in the grid.
* `cells_below_certification_floor` — list of magnitude labels
  whose CI lower bound undershoots the floor; empty list ≡ pass.
* `certification_floor` and `wilson_z` — the bound and z-score in
  effect for this summary.

`pick_winner_tuple(sensitivity_cells)` returns the winner config
plus the full candidate list, ordered by Euclidean distance to the
V1 defaults with tiebreakers (lowest T, highest β, lowest δ) to
match the LLM tiebreaker convention.

### 6.1 Certification floor — Wilson 95% CI lower bound

Every (family, magnitude) cell — i.e. every entry in
`summarize_grid(cells)["per_config"]` — must satisfy

```
ci_low(passed, n, z = 1.96) >= CERTIFICATION_FLOOR  # default 0.90
```

where `ci_low` is the Wilson score lower bound at 95% (two-sided).
At `n = 60` and a clean kernel (60-of-60 pass) the lower bound is
`~0.940`, so the floor of `0.90` leaves the ~5 percentage points of
headroom needed for one statistical failure (`59 / 60 → ~0.911`,
still above the floor) without admitting two failures
(`58 / 60 → ~0.886`, under the floor).

The floor is the regression suite's stated statistical contract:
*"with 95% confidence, the true pass rate at every primary-grid
config is at least 0.90."* If a kernel change pushes any single
config below that bound, `tests/test_characterization.py` fails
loudly with the offending config's magnitude label and observed
CI in the assertion message.

The bound is configurable per-summarisation via
`summarize_grid(cells, z=..., certification_floor=...)` for
callers that want to quote a stricter contract (e.g. 99% CI low
≥ 0.95 for a fully-funded SOTIF programme).

## §6.2 Frozen artifacts — CSV + Markdown report writers

`GridSummary` exposes two regulator-facing writers so a SOTIF /
ISO 26262 audit pack ships frozen deliverables instead of a Python
dataclass. Both are pure stdlib (no extra dependencies):

* `summary.to_csv(path)` — one row per (family, magnitude) config
  with the per-config Wilson 95% CI, pass count, pass rate, and
  ``meets_certification_floor`` boolean. RFC-4180-quoted via the
  stdlib `csv` module so a downstream Excel / pandas / audit
  script consumer can rely on the column order
  (`GRID_CSV_FIELDS`).
* `summary.to_markdown_report(path)` — regulator-friendly markdown
  with five sections: headline gate, per-(family, magnitude)
  results, per-family roll-up, configs below the certification
  floor (explicitly named, even if empty), and a methodology
  block (Wilson z, certification floor, source). Deterministic
  up to the `generated_at` timestamp; pass an explicit
  `datetime` for byte-stable snapshots.

`render_grid_csv` / `render_grid_markdown` produce the strings
without writing to disk — useful for piping to a fluentd / Kafka /
S3 sink directly. `write_grid_csv` / `write_grid_markdown` write
files (and `mkdir(parents=True, exist_ok=True)` on the way).

The writers were explicitly deferred in the v0.3 design comment
*"the sweep returns dataclass cells; a caller can pipe them to
CSV or markdown via dataclasses.asdict"*. Post-v0.7 the SOTIF
clause-9 V&V evidence pack and the ISO 26262 Part 6 §11
verification-of-software-safety-requirements artifact are
explicitly auditor-facing — a regulator wants a frozen deliverable,
not an expectation that a caller will write one. The deferral is
retired.

## §7 What is intentionally not in scope

* No simulator integration — the families synthesize trajectories
  directly. A future port can wire an MPPI rollout into the cell
  evaluator if a closed-loop characterization is ever needed.
* No valid-mask support in the BCVF kernel itself — the
  `sensor_dropout` family models dropout via pose freezing rather
  than logical masking. Real autonomous SLAM stacks behave the same
  way; logical masking would require a kernel change.
* No automatic acceptance-table tuning — the per-family thresholds
  are hand-set against the SE(2) magnitudes that match the
  autonomous stack's nominal motion (5 m/s straight line). Tuning
  for other dynamic regimes is a caller responsibility.

## §8 Acceptance criteria for the suite itself

The port lands when:

1. Every nominal family passes at the V1 default cell.
2. Every failure family passes at the V1 default cell, including
   the alignment criterion for outlier / sensor_dropout.
3. The ablation grid shows ZEROTH and FIRST cost orders fire on
   linear_drift while SECOND rejects it.
4. The sensitivity grid yields at least one all-pass winner tuple
   close to the V1 defaults.
5. Every per-config Wilson 95% CI lower bound on the 1560-cell
   primary grid clears `CERTIFICATION_FLOOR = 0.90` (§6.1). The
   minimum lower bound across the grid (the "weakest cell") is
   reported in `summarize_grid(...)["min_ci_lower_bound"]`.

Tests in `tests/test_characterization.py` enforce (1)–(5) directly.
The §6.1 certification gate is the statistical-significance bar the
audit asked the suite to anchor; (1)–(4) remain the
correctness-of-direction gates.
