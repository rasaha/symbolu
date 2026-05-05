# Autonomous Robotics — VC Brief (v2)

**Cognade Labs | BCVF Autonomy Runtime**
*Portable predictor-trust layer between multi-predictor robotics stacks and their planner*
*Version 0.7 — Prepared May 2026*

> **Status.** v0.7 closes the audit's #4 next-step — the
> **apples-to-apples baseline shootout** the v0.3 brief was
> missing. Built four arbitrators at the same predictor-
> arbitration interface (`BCVFArbitrator`, `EKFArbitrator` with
> Mahalanobis 3-sigma outlier rejection, `MajorityVoteArbitrator`
> with cluster-based mode selection, `AnchorArbitrator` as the
> null floor), ran them across all seven characterization
> families × N=10 seeds, and produced the comparison table the
> brief now points at. **Headline finding: BCVF is the only
> arbitrator with non-zero false-attribution suppression on
> Lemma-1-invariant disagreements** — Majority-Vote false-
> attribution score on `constant_bias` is **16.7** (catastrophic),
> EKF is 1.1, BCVF is 0.0. **EKF's Mahalanobis gate also misses
> the heavy-quadratic outlier** (0.0 hit rate vs BCVF / Majority's
> 1.0). BCVF is 8–19× faster per tick than EKF / Majority. v0.6's
> V2 chatter-reduction sweep result is preserved unchanged. The
> characterization primary grid is now certification-grade — 22
> configs × 60 seeds = 1320 cells, every per-config Wilson 95% CI
> lower bound ≥ 0.90 (current min ≈ 0.940). The Q3 SOTIF / ISO
> 26262 traceability template (12 clauses, **25 indexed BCVF
> artifacts**, machine-checked snapshot) landed early in
> `safety_case/`. The fleet harness gained a `StreamingFleetMonitor`
> with rolling-window summaries + threshold alert rules, lifting
> the post-hoc triage tool to a runtime SRE surface. The two
> deferred CSV / Markdown report writers landed —
> `GridSummary.to_csv` / `to_markdown_report` and
> `FleetSummary.to_csv` / `to_markdown_report` emit the frozen
> auditor-facing artifacts the safety-case workstream depends on.
> **The 0.4.0 release ratifies the public-API stability policy** —
> a 38-symbol `STABLE_API` registry + 14-symbol `PROVISIONAL_API`,
> a deprecation cycle in `API_STABILITY.md`, and machine-checked
> tests pinning every entry's resolution + top-level reachability.
> **Hierarchical / group-level BCVF design proposal landed
> post-v0.7** as `HIERARCHICAL_BCVF_DESIGN.md` — research-tier,
> design-only today, gated on three ship-when-ready criteria.
> **Adversarial / spoofing test family** (`adversarial_consistent_bias`)
> added as the 8th characterization family — third polarity bucket
> (`ADVERSARIAL_FAMILIES`), exposes the kernel's UN ECE R155
> cybersecurity scope (Lemma-1 trapdoor at the stealth-bias regime,
> kernel-detected at the loud regime via gate-noise interaction);
> grid expands 1320 → 1560 cells with the same Wilson 95% CI floor
> of 0.90 holding throughout. **Multi-modal predictor inputs** thin-
> shim adapter landed (`predictors/state_space.py` +
> `predictors/multi_modal.py`): lifts lane-frame ``(s, d, psi)``
> predictors to SE(2) at the kernel boundary; the load-bearing
> research finding (`MULTI_MODAL_PREDICTORS_DESIGN.md` §4) is that
> **Lemma 1 invariance carries through the lift even on curved
> lanes** because the body-frame error primitive transforms
> correctly with lane curvature — pinned by
> `test_lemma_1_carries_on_curved_lane`. **Functional-safety
> state machine landed post-v0.7** as
> `SAFETY_STATE_MACHINE_DESIGN.md` + thin-shim implementation in
> `safety_state/`: four-state behavioural contract
> (NORMAL / DEGRADED / FAULT / FAILSAFE) with documented per-
> transition triggers, ASIL decomposition (B for warnings + manual-
> resets, D for safety-critical escalations), direct-jump
> prohibition, and manual-reset audit trail. The state machine is
> the system-level supervisor an ISO 26262 safety case argues
> against; the per-tick V2 chatter mitigation now composes into a
> named system-level posture instead of stopping at the kernel
> boundary. **ROS 2 / DDS / CycloneDX SBOM integration contract
> landed post-v0.7.x** as `ROS2_DDS_SBOM_DESIGN.md` + thin-shim
> implementation across `bcvf_ros2/` (typed `.msg` schemas
> `PredictorTrajectory.msg` + `ConsensusOutput.msg`,
> framework-agnostic `BCVFNode` with rate-limiting +
> per-predictor deadline tracking + `SafetyStateMachine`
> composition, lazy-rclpy adapter), `bcvf_ros2/qos.py` (the
> documented `RELIABLE / VOLATILE / 10 ms / 100 ms` DDS QoS
> profile per-knob rationale), and `safety_case/sbom/` (CycloneDX
> 1.5 generator + the on-disk byte-stable manifest at
> `safety_case/SBOM.cdx.json`). The three first-call questions
> every Tier 1 / OEM customer asks (*does it speak ROS 2?* /
> *what's the DDS QoS profile?* / *where's the SBOM?*) now have
> code answers a reviewer can `cd` into. **Post-landing audit
> pass on the §9-row-#2 implementation surfaced five real bugs +
> four coverage gaps**: silent shape-mismatch zero-padding (a
> consensus-injection vector — predictors with mismatched (K, H)
> are now shape-rejected for the tick instead); clock-backwards
> mute (a sim-time reset / NTP step / suspend-resume used to
> clear every deadline violation in one tick); BCVFNode → state
> machine signal cut (consec_suspect was hardcoded zero, making
> NORMAL→DEGRADED structurally unreachable from this surface —
> now derived from per-predictor consecutive-excluded counts);
> SBOM empty-license schema-invalidity (now rejected at
> SBOMComponent construction); SBOM legacy License-field fall-
> through (now reads PEP 314 License: when PEP 639 License-
> Expression is absent — pyyaml-class packages no longer ship
> with no license attribution). **Replay / record-and-replay
> framework landed post-v0.7.x** as `REPLAY_FRAMEWORK_DESIGN.md`
> + thin-shim implementation in `replay/`: a `ReplayBundle`
> ties `(RunConfig, recorded TrustShapedEpisodeRecord, package
> version, episode metadata)` into a single JSON-serialisable
> artifact a recall investigator opens; `replay_bundle(bundle,
> runner_factory)` runs the bundle's config through the current
> code and surfaces any divergence with field-level + tick-level
> localisation. The bit-identity gate uses `np.array_equal` over
> every per-step array; mismatches return a typed `ReplayResult`
> naming the offending field + tick. SOTIF clause 10
> (operational design + field monitoring) gains the bundle as
> the post-incident-recall evidence artifact; ISO 26262 Part 6
> §11 (verification of software safety requirements) gains the
> bit-identity contract as V&V evidence. SOTIF_TRACEABILITY.md
> regenerates 33 → **35 indexed artifacts**. Strict-validation
> discipline mirrors `analysis/io.py`: corrupt artifacts fail
> loud at load time rather than producing silent zero-fill
> replays. **Post-landing audit pass on the §9-row-#3
> implementation surfaced five real bugs + four coverage gaps**:
> bundle_version asymmetry between __post_init__ and from_dict
> (now both reject loud); dtype-drift invisibility in the
> bit-identity comparator (an int64→int32 flip used to slip
> past — now flagged as a divergence); shallow-copy aliasing
> letting nested run_config mutation corrupt the frozen bundle
> (now deepcopy at every boundary); zero-step records failing
> the analysis/io.py validator (recall investigators can now
> bundle a "collision in initial state" episode); recorded_at
> not validated as ISO 8601 + episode_id accepting whitespace-
> only (now both reject loud at construction). **Real-time /
> no-allocation hot path + p999 budget framework landed
> post-v0.7.x** as `REAL_TIME_BUDGET_DESIGN.md` + thin-shim
> implementation in `realtime/`: a typed `RealTimeBudget`
> contract (target_hz + per-tier ms thresholds for p99 / p999
> / p9999 / max + sample-count gates) is the AUTOSAR-Adaptive
> deal-unlock answer to *"what's your worst-case execution
> time?"*. `LatencyMonitor` ingests one observation per tick,
> classifies against the budget tiers with mutually-exclusive
> counters (a tick exceeding p9999 but not max increments only
> n_p9999_violations), records over-budget violations in a
> bounded ring buffer, and computes p99 / p999 / p9999 / max
> stats on demand. The percentile-availability discipline
> (p999 None below 1000 samples; p9999 None below 10000)
> protects an ISO 26262 §10 integration-verification report
> from including statistically-meaningless small-n claims.
> Composes with `EpisodeDiagnostics.solve_times_ms` via
> `observe_series`; advisory `tracemalloc`-based per-tick
> allocation deltas surface a hotspot without claiming a
> hard "no allocations" contract pure-Python can't deliver.
> SOTIF_TRACEABILITY.md regenerates 35 → **37 indexed
> artifacts**. **Post-landing audit pass on the §9-row-#4
> implementation surfaced seven real bugs + two coverage
> gaps**: NaN / ±Inf silently slipped past the guards and
> polluted every percentile while leaving meets_budget=True
> (now rejected loud as "elapsed_ms must be finite");
> `tracemalloc.start()` was never paired with `.stop()` —
> a global resource leak that left every interpreter
> process paying tracemalloc overhead after a monitor went
> out of scope (now `close()` / context-manager pairs the
> lifecycle, only stops if THIS monitor enabled it);
> `BudgetSummary.allocation_trace` was silently dropped
> from `to_dict()` so a recall investigator opening the
> JSON saw no allocation data even when track_allocations
> was set (now serialised); `bool isinstance int` let
> `mon.observe(True, ...)` slip through as 1.0ms (now
> rejected) while numpy scalars (`np.float64`, `np.int64`)
> were inconsistently rejected (now accepted); equal-tier
> budgets caused mutually-exclusive tier classifier to drop
> the tighter counter (now strict-monotone validator
> rejects equal tiers); empty-monitor returned 0.0
> percentiles silently passing CI gates of the form
> `if summary.p99_ms > budget` when the planner crashed
> before any observation (now returns None for every
> percentile); `BudgetSummary` typed `p999_ms: float`
> instead of `Optional[float]` — type-hint drift that
> broke static analysis (now Optional everywhere). **972 tests passing**
> (post-audit; +9 industry-features-roadmap pins + 6 audit-fix
> pins for the four post-v0.7 features + 70 safety-state-machine
> pins + 12 second-wave audit-fix pins [single-tick-spike chatter
> at startup + rolling-window clear on manual reset + non-
> whitespace operator/reason validation + immutable-tuple
> transition log + force-gated `clear()` + FAILSAFE no-automatic-
> transitions invariant + escalation-wins-over-recovery dispatch
> precedence + batch-mode record replay walks transitions at
> correct tick indices] + 9 API-stability resolutions for the 9
> new provisional symbols + 9 traceability-matrix pins for
> clause-8 / Part-6-§8 evidence wiring + **50 ROS 2 / DDS / SBOM
> integration-contract pins** [12 DDS QoS profile knob validation
> / 19 BCVFNode behaviour incl. rate-limiting + deadline-tracking
> + stale-on-resume + bridge composition + safety-state-machine
> composition / 19 CycloneDX SBOM incl. spec-version + auto-
> discovery + determinism + snapshot byte-equality + license
> rendering for SPDX expressions] + 11 design-doc pins + 12
> additional API-stability resolutions for the new provisional
> surface),
> up from 400 in v0.6 (12 audit pinning tests + 15 statistical-
> significance tests + 20 safety-case-traceability tests + 29
> streaming-monitor tests + 16 report-writer tests + 71 API-
> stability tests + 9 hierarchical-BCVF design-doc pins + 12
> adversarial-family tests + 30 multi-modal tests + 6 provisional-
> resolution tests added post-v0.7). v1 file at
> `AUTONOMOUS_ROBOTICS_VC_BRIEF.md` is preserved for historical
> reference.

---

## Page 1 — The Problem

### Modern autonomy stacks disagree internally. The planner has no principled way to decide who to trust.

Every modern autonomous-vehicle, drone, mobile-robot, and humanoid
stack converged on the same pattern: **multiple predictors feeding a
planner.** A typical stack combines an HD-map prior, a learned
trajectory predictor, a classical kinematic model, and one or more
redundant sensor channels. When the predictors agree, planning is
routine. **When they disagree, the planner has no principled way to
decide which predictor to trust** — and predictor disagreement is the
regime where the failures that matter live.

That gap is where disengagements, safety-case escalations, and
in-house engineering rebuild-per-program costs concentrate. Programs
we've reviewed treat predictor-disagreement handling as bespoke glue
code rebuilt per stack, per program, and per release. The four
questions that come up earliest in safety review are the ones current
stacks answer least crisply:

| Question a safety case asks | Typical answer in current stacks | What v0.3 ships |
|---|---|---|
| *When two predictors disagree, can the system identify which one is failing — not which the heuristic prefers?* | Designated-primary or majority vote; both fail when the primary or majority is the one drifting. | Per-predictor BCVF cost attribution + outlier-alignment metrics (hit / margin / rank), structurally tested against a seven-family failure taxonomy. |
| *Is there a stated invariance property — something that provably ignores benign disagreement and only fires on genuine failure?* | Threshold-tuned heuristics, calibrated empirically per stack. No formal invariance. | Lemma 1 invariance proof (constant + linear-drift disagreement → exactly zero cost), regression-tested by `run_ablation_grid` across cost orders. |
| *When a predictor is down-weighted at runtime, can an operator reconstruct why?* | Per-component logs; no causal trace from the disagreement signal to the trust decision. | Frame-by-frame `TrustShapedEpisodeRecord` artifact + six observable probes (agreement, spread, coherence, per-step max, predictor-specific, uncertainty-gated) that surface exactly which signal moved the trust distribution. |
| *Can the trust mechanism be tuned without retraining predictors or rewiring the planner?* | Trust logic is entangled with the predictors that feed it; tuning is a release-cycle event. | Planner-agnostic `TrustWeightComputer` (§6.3) + opt-in Consumer V2 Schmitt trigger; both tunable through dataclasses, neither requires retraining. |
| *Can the safety team aggregate signals across the fleet to spot near-failures before they escalate?* | Manual log mining; near-miss detection lives in custom scripts per program. | `aggregate_fleet` harness over JSON-dumped trip records — surfaces argmax flips, near-vetoes, V2 state transitions per vehicle / scenario. |

### Why the gap is structural, not a tooling oversight

Fusion layers — Kalman filters, weighted averages, late-fusion
ensembles — were designed to *combine* honest noisy signals, not to
*distrust* a predictor that is silently wrong. Bolt-on uncertainty
estimators (deep ensembles, MC dropout, evidential networks) produce
numbers but offer **no formal invariance property**; their behaviour
on unseen failure shapes is the unknown a safety case was supposed to
bound.

ISO 21448 (SOTIF) and emerging functional-safety regimes increasingly
call for explicit handling of *silent predictor miscalibration*, not
just sensor failure. Operators and certification bodies want a runtime
layer that can say — under a stated mathematical invariance — "this
predictor is no longer trustworthy, here is the signal, here is the
attribution." A portable, testable runtime for that regime does not
exist today.

### The category we are building for

A **portable predictor-trust runtime** — a first-class layer between
predictor outputs and the planner — with a stated invariance
property, context-normalized trust construction, and a tested
integration contract. Not a replacement for perception, fusion,
prediction, or planning. The missing layer that sits between them.

---

## Page 2 — The Architecture

### What the runtime does, in four steps

BCVF Autonomy Runtime sits between the predictor stack and the
planner. At every planning step it:

1. **Detects disagreement shape.** Distinguishes harmless patterns
   (constant offset between predictors, linear drift) from
   *accelerating* divergence — the disagreement shape that signals
   real failure. The detector has a mathematically proven invariance:
   constant and linear-drift disagreement produce **exactly zero**
   trust signal; only acceleration above the noise floor produces a
   positive one.
2. **Normalizes for context.** Each scenario has its own baseline
   level of disagreement (different prompts, different sensor regimes,
   different geometries). The runtime subtracts a per-source running
   average so a noisy environment does not look like a failure.
3. **Down-weights suspect predictors.** A significance gate filters
   noise residuals; only disagreement that is meaningfully outside
   the per-source noise envelope shifts the trust distribution.
4. **Plans against the weighted consensus.** The planner consumes a
   trust-weighted consensus trajectory rather than a single
   predictor's output, with the per-source trust distribution
   available as a live diagnostic.

### The execution path (pinned by tests, not configurable)

```
  perception / prediction outputs
            │
            ▼
  M predictor trajectories per MPPI rollout  ──►  (K rollouts, M predictors)
            │
            ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  BCVF kernel       — detect disagreement (Lemma 1 invariant)│
  │  Normalization     — per-source EMA mean centering          │
  │  Significance gate — suppress noise residuals               │
  │  Trust softmin     — per-rollout trust distribution         │
  │  Weighted consensus— SE(2)-safe consensus trajectory        │
  └─────────────────────────────────────────────────────────────┘
            │
            ▼
  Planner cost on consensus  ──►  MPPI control selection  ──►  applied control
            │
            ▼
  Per-step trust trace (kernel signal, weights, consensus, decision)
```

The ordering — **predict → score → normalize → trust → consensus →
plan → act** — is a runtime invariant verified by the test suite, not
a configurable option. A predictor whose disagreement is flat or
linearly drifting cannot affect trust weights. A residual below the
significance threshold cannot shape the softmin. A trust distribution
cannot bypass the consensus stage. This is the runtime contract a
safety case can point to.

### Three layers, independently tunable and testable

| Layer | Scope | What it answers |
|---|---|---|
| **Detection kernel** | Per planning step, all predictor pairs | *What is the disagreement signal under the stated invariance?* |
| **Trust shaper** | Per planning step, single trust distribution | *Given the signal and the per-context baseline, which predictors should the consensus down-weight right now?* |
| **Inspection surface** *(v0.3)* | Per tick + per episode + per fleet | *Why did the shaper produce these weights, when did it flip its mind, and how many vehicles in the fleet are close to failing?* |
| **Safety state machine** *(post-v0.7, provisional)* | Per tick — system-level posture (NORMAL / DEGRADED / FAULT / FAILSAFE) | *What is the named behavioural state the planner is conditioning on, what triggered the last transition, and what manual-reset gate latches the FAULT / FAILSAFE recovery path? — see `SAFETY_STATE_MACHINE_DESIGN.md`* |
| **ROS 2 / DDS / SBOM integration contract** *(post-v0.7.x, provisional)* | Bus boundary — `BCVFNode` subscribes to per-predictor topics + publishes `ConsensusOutput`; documented DDS QoS quad; CycloneDX 1.5 manifest | *Does it speak ROS 2? / What's the DDS QoS profile? / Where's the SBOM?* — the three first-call questions every Tier 1 / OEM customer asks, answered with code an integrator can `cd` into. See `ROS2_DDS_SBOM_DESIGN.md`. |
| **Replay / record-and-replay framework** *(post-v0.7.x, provisional)* | Episode boundary — `ReplayBundle` ties `(RunConfig, recorded record, package version, metadata)` into one JSON; `replay_bundle()` re-runs + bit-identity-compares | *Can the recall investigator reproduce what the field saw, bit-identical?* — the Class-A / Class-B / Class-C divergence localises to a specific (field, tick) pair so a kernel diff can be pinpointed. See `REPLAY_FRAMEWORK_DESIGN.md`. |
| **Real-time / p999 budget framework** *(post-v0.7.x, provisional)* | Per-tick — `RealTimeBudget` typed contract + `LatencyMonitor` per-tick observer with mutually-exclusive tier counters + bounded over-budget audit trail | *What's the worst-case execution time, and what happens when you blow it?* — the AUTOSAR-Adaptive deal-unlock question, answered with code. Percentile-availability discipline rejects statistically-meaningless small-n p999 / p9999 claims. See `REAL_TIME_BUDGET_DESIGN.md`. |

The detection kernel is pure mathematics with a published proof. The
trust shaper is the autonomy-validated configuration: per-source mean
centering, then a significance gate, with all-pairs (non-anchor)
predictor enumeration. The inspection surface is the v0.3 SOTIF
deliverable — every tick produces a typed structured record, every
episode rolls up into an `EpisodeSummary`, every fleet of episodes
aggregates into a `FleetSummary` with named events (argmax flips,
near-vetoes, V2 state transitions). Any layer can be replaced or
re-tuned without touching the others.

### Actuator-grade chatter immunity (Consumer V2)

The default V1 softmin is a smooth function — designed for
inference-time logit blending where smoothness is a virtue. On
borderline disagreements driving a physical actuator, smoothness
becomes chatter: the trust-weighted consensus can flip its lead
predictor tick-to-tick. v0.3 ships an opt-in **Schmitt-trigger
state machine** wrapping the V1 shaping pipeline:

* The signal must rise above `engage_threshold` for `T_engage`
  consecutive ticks to engage shaping.
* Once engaged, the signal must drop below a strictly lower
  `disengage_threshold` for `T_disengage` consecutive ticks to
  revert to uniform weights.
* While disengaged, the EMA continues tracking the cost baseline
  (so the deadband / softmin start *warm* on first engagement);
  the §6.6a exclusion counters freeze (so transient spikes don't
  accumulate toward veto in safe-default territory).

This is the standard control-safety pattern that's been keeping
thermostats from flickering for fifty years; v0.3 brings it to the
trust pipeline, with the entire transition history captured in the
typed diagnostic record for post-hoc audit.

### Developer surface — one factory call

```python
from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig, MPPIConfig, MPPIPlanner, CostOrder,
)

bcvf_cfg = BCVFConfig(
    gate_threshold=0.05, gate_beta=400.0, huber_delta=0.5,
    cost_order=CostOrder.SECOND, use_anchor_pairing=False,
)
mppi_cfg = MPPIConfig(
    num_rollouts=256, horizon=20, lambda_c=1.0, bcvf_config=bcvf_cfg,
)
planner = MPPIPlanner(mppi_cfg, perf_cfg, predictors, road, obstacles)
planner.set_ema_alpha(0.05)         # per-context normalization
planner.set_deadband_k_sigma(2.0)   # significance gate
result = planner.plan()
```

Same code runs against synthetic predictors (no compute, no sensors)
and live perception/prediction stacks with no wiring changes — which
makes the library evaluable before any procurement conversation. The
runtime is **pure NumPy, runs on CPU in milliseconds per step, and
has no dependency on torch, ROS, or any platform-specific stack.**

---

## Page 3 — Where We Fit

BCVF Autonomy Runtime sits at a layer that exists in every production
multi-predictor robotics stack but is almost always in-house
engineering glue: the arbitration between disagreeing predictors.
We are **complementary to** the perception, fusion, prediction, and
planning components around that layer, not competitive with them.

### The competitor families and how we relate

| Category | Representative players | What we do differently |
|---|---|---|
| **Classical sensor / state fusion** | Kalman / EKF / UKF, ROS `robot_localization`, MRPT, Apollo perception fusion | Classical fusion combines noisy-but-honest signals into a single estimate. We sit one level up, arbitrating between *predictors* whose outputs the fusion layer fed into — the regime classical fusion is not designed to cover. Composes cleanly: keep the fusion layer, add us at the planner-arbitration boundary. |
| **ML uncertainty estimation** | Deep ensembles, MC dropout, evidential deep learning, conformal prediction | These produce empirically-calibrated uncertainty *numbers*. We produce a per-source trust distribution under a stated mathematical invariance (Lemma 1). Additive: a stack can keep its per-model uncertainty and feed it into our trust-weighting layer as additional context. |
| **Closed AV platform stacks** | Waymo, Cruise, Mobileye, NVIDIA DRIVE, Apollo, Toyota Woven Driver | These are end-to-end stacks with proprietary, non-portable internal arbitration logic. We ship the arbitration layer as a portable, inspectable runtime — an integrator using DRIVE (or similar) can adopt our layer without giving up the rest of their stack. |
| **Open-source AV / robotics stacks** | Autoware, Apollo OSS, OpenPilot, Nav2, MoveIt | These ship stack components and leave predictor-arbitration as glue code in `behavior_planner` / `decision_maker` modules, configured per integrator. We provide a tested runtime dependency for that specific glue — `pip install`-ready (and ROS 2 adapter in progress, §6.4). |
| **Functional-safety tooling** | ANSYS Medini, Vector vTESTstudio, dSPACE SystemDesk, Foretify, Applied Intuition | These document *what* the system should do. We provide the runtime artifact the documentation can refer to — SOTIF's "silent predictor miscalibration handling" question gets a structural answer (Lemma 1 proof) instead of an empirical one ("we tested N scenarios"). Complementary, not competing. |

### The one-sentence statement of fit

Classical fusion combines signals. ML uncertainty estimates noise.
Closed AV stacks bury arbitration inside proprietary code. Open-
source stacks leave it to integrators. We are the missing runtime
**between** predictor outputs and the planner, with a mathematical
invariance a safety case can point to and an extracted consumer
pattern that — as of the §6.3 refactor — is planner-agnostic by
construction.

### What we are not trying to claim

- Not replacing any perception, prediction, fusion, or planning
  component. We arbitrate between predictors; we do not produce
  them.
- Not a full-AV platform. An integrator still needs their sensing,
  localization, prediction, control, and safety-monitor stack; we
  add one missing layer.
- Not universal. The §6.1 multi-scenario scout identified that the
  runtime is **applicable where failure manifests as predictor
  disagreement** — which covers most map-error, multipath, and
  degrading-sensor cases in our suite, but not (e.g.) a camera
  failure that drops a dimension the predictors don't model. We
  document that boundary explicitly in our experimental reports.

---

## Page 4 — Evidence & Roadmap

### Four proof points to know (as of May 2026)

- **972 tests passing** (+602 since v0.2; full post-v0.7 test breakdown above + 9 industry-features-roadmap pins + 6 audit-fix pins for the four post-v0.7 features (B2 adversarial axis validation; C7 multi-modal `psi` interpolated tangent; A1-A2 `resolve_qualified` edge cases) + 70 safety-state-machine pins for the §9.1-recommended functional-safety state machine that landed post-v0.7 + 50 ROS 2 / DDS / SBOM integration-contract pins + 11 design-doc pins for the §9 row-#2 ROS 2 / DDS / SBOM integration that landed post-v0.7.x — the **0.4.0 release ratifies a public-API stability policy**, longer-horizon research items land as design docs gated on explicit ship-when-ready criteria, the 8th `adversarial_consistent_bias` characterization family makes the kernel's **UN ECE R155 cybersecurity scope-boundary** an explicit machine-checkable third polarity in the certification grid, the **multi-modal predictor adapter** lifts lane-frame predictors to SE(2) at the kernel boundary while preserving Lemma 1 invariance through to curved lanes, the **functional-safety state machine** in `safety_state/` (see `SAFETY_STATE_MACHINE_DESIGN.md`) composes the per-tick runtime into a four-state ISO-26262-defensible behavioural contract with documented triggers, ASIL decomposition, direct-jump prohibition and manual-reset-only FAULT / FAILSAFE recovery, the **ROS 2 / DDS / CycloneDX SBOM integration contract** in `bcvf_ros2/` + `safety_case/sbom/` (see `ROS2_DDS_SBOM_DESIGN.md`) answers the three first-call OEM / Tier 1 / robotics customer questions with code (typed `.msg` schemas + framework-agnostic `BCVFNode` + documented DDS QoS quad + CycloneDX 1.5 manifest at `safety_case/SBOM.cdx.json`), and `INDUSTRY_FEATURES_ROADMAP.md` enumerates the eight industry gap-fill items ranked by deal-unlock value — Items #1 (state machine) and #2 (ROS 2 / DDS / SBOM) struck through with pointers to their design docs, the rest still gated on machine-checked non-promotion to the API registry) across the autonomy
  kernel, MPPI planner, trust-weight computer, non-MPPI adapter,
  dataset scaffolds, ROS 2 bridge, the v0.3 SOTIF-readiness
  layer, the v0.4 vectorized predict_batch path, the v0.5 pilot
  runner, the v0.6 V2 promotion-gate sweep, and the v0.7
  apples-to-apples baseline shootout. All committed,
  reproducible, CPU-only.
- **Seven-family characterization sweep — 0% FPR / 0% FNR with a
  Wilson 95% CI lower-bound floor of 0.90 across 22 configs ×
  60 seeds (1320 cells).** Every named sensor-failure class
  (constant bias, linear drift, accelerating divergence, noise
  floor, outlier, sensor dropout, baseline) is validated to fire
  or stay quiet on cue across primary, sensitivity, and ablation
  grids. The primary grid is now sized for a stated statistical
  contract: per-(family, magnitude) Wilson 95% CI lower bound
  must clear 0.90 — the floor is calibrated so two of 60 seed
  failures at any single config trip the alarm, exactly the
  threshold-edge regime (e.g. `accelerating[accel_mag=0.3]`)
  where a small kernel change is most likely to flip pass→fail.
  Current min-CI-lower-bound across the grid: **~0.940** at
  60-of-60 pass; floor headroom: **0.04**. The 567-cell
  sensitivity grid still winner-tuples the V1 defaults as the
  closest-to-canonical all-pass configuration.
- **Apples-to-apples baseline shootout (v0.7).** Four arbitrators
  at the same predictor-arbitration interface (BCVF, EKF with
  Mahalanobis 3-sigma outlier rejection, Majority-Vote, Anchor)
  × seven characterization families × N=10 seeds. **Two
  differentiating findings:** (a) BCVF is the only arbitrator
  with zero false-attribution on Lemma-1-invariant disagreements
  — Majority-Vote scores **16.7** on `constant_bias` and **4.1**
  on `linear_drift`; EKF scores **1.1** and **0.5**; BCVF scores
  **0.000** on both. (b) EKF's Mahalanobis gate misses the
  heavy-quadratic outlier (hit rate **0.0** vs BCVF / Majority
  at **1.0**). BCVF is **8–19× faster** per tick (≈3.7 µs vs EKF
  ≈70 µs / Majority ≈28 µs).
- **§6.2 pilot runner executed end-to-end (v0.5).** N = 21 paired
  scenes, A3 win rate **1.000** vs A0 with Wilson-CI 0.566–1.000
  and one-sided sign-test **p = 0.0312** on the responsive
  failure class (camera-degradation-shape within-horizon
  high-frequency disagreement). Attribution accuracy on the
  injected outlier: **100%**. Lemma-1 negative control passes
  exactly (max BCVF cost = 0.000000 on `constant_bias_sanity`).
  Pilot ran against the documented `RealisticNoiseAdapter`
  bridge — the runner / metrics / FleetSummary / sign test are
  dataset-agnostic and unchanged across adapters.
- **Two synthetic-predictor scenarios independently validated at
  p < 0.05**: `S3_map_error_accel` (N = 21, p = 0.0072) and
  `S3_map_error` (N = 19, p = 0.0192).

Full detail and caveats below.

### What is proved today (v0.2, internal evidence)

| Area | Current state |
|---|---|
| **Test suite** | 751 passing across 27 test modules (+12 pinning tests from the post-v0.7 audit pass; +15 statistical-significance tests; +20 SOTIF / ISO 26262 traceability tests; +29 StreamingFleetMonitor tests; +16 CSV/Markdown report-writer tests; +77 public-API-stability tests [38 stable + 29 provisional resolutions + 10 hand-written]; +9 hierarchical-BCVF design-doc pins; +12 adversarial-family tests; **+24 multi-modal predictor tests** [LaneAnchor geometry primitives / round-trip identity straight + curved / Lift `(s, d, psi) → (x, y, theta)` / `MultiModalPredictor` validation / `unify_to_se2_bundle` mixed-mode + horizon-mismatch / **Lemma 1 carries on straight + curved lane** / different-reference-paths fires kernel / **lane-frame constant-d bias invisible to BCVF (same Lemma-1 trapdoor)**]; **+70 safety-state-machine pins** [4-state enum + 6-edge legal-transition table / parametrized illegal-transition gate / per-trigger fire / non-fire / recovery-dwell / manual-reset / log discipline / SOTIF clause-8 + Part-6-§8 evidence wiring / AlertRule composition / `state_transition_consistency` family at 5 seeds × 3 ASIL-D transitions × {must-fire, must-be-quiet}] **+12 second-wave audit-fix pins** [single-tick-spike chatter at startup (rate predicates divide by capacity, not current length) + rolling-window clear on manual reset for both FAULT and FAILSAFE / non-whitespace operator + reason validation / immutable-tuple transition log / force-gated `clear()` / FAILSAFE no-automatic-transitions invariant under 1000 mixed ticks / escalation-wins-over-recovery dispatch precedence on simultaneous-trigger tick / batch-mode `observe(record)` walks transitions at correct tick indices]); reproducible on CPU in < 4 min (4 host-speed-dependent perf benchmarks + 4 long-running sweep / timing tests deselected) |
| **Adversarial / spoofing test family (post-v0.7)** | `characterization/traces.py` adds an 8th family `adversarial_consistent_bias` covering the UN ECE R155 attacker who feeds plausibly-noisy data with a hidden constant lateral bias. Third polarity bucket `ADVERSARIAL_FAMILIES` joins the existing nominal / failure tuples; the cell-level acceptance is permissive (kernel must be bounded + dimensionally well-behaved). The **cybersecurity-reviewer-facing evidence** is the per-config Wilson stats across magnitudes `(0.005, 0.01, 0.05, 0.5)` spanning the stealth → transition → loud regime, surfaced in `summarize_grid(...).per_config` and rendered into the auditor markdown by `GridSummary.to_markdown_report`. **The Lemma-1 trapdoor is documented behaviour**: stealth-bias spoofs (bias ≪ T) are invisible to the kernel by construction, with planner-layer harm pinned by `test_adversarial_stealth_attack_succeeds_at_consensus_layer` — defence in depth (cross-modal sensor attestation per UN ECE R155 §7.3.4, cross-class redundancy, calibration drift monitoring) is the layer that catches what BCVF cannot. SOTIF clause 6 (HARA) gains the family as a named hazard input; clause 8 (functional insufficiencies + mitigations) names the trapdoor + the deployment-partner-side mitigation registry. Grid expansion: 22 → 26 configs, 1320 → 1560 cells, every per-config Wilson 95% CI lower bound continues to clear the 0.90 floor. |
| **Multi-modal predictor inputs (post-v0.7)** | `predictors/state_space.py` adds a `PredictorStateSpace` enum + `LaneAnchor` polyline geometry; `predictors/multi_modal.py` adds a thin-shim adapter (`MultiModalPredictor`, `lane_frame_to_se2`, `se2_to_lane_frame`, `unify_to_se2_bundle`) that lifts non-SE(2) predictor outputs to the kernel's canonical SE(2) world-frame at the boundary. **The load-bearing research finding** (`MULTI_MODAL_PREDICTORS_DESIGN.md` §4): a pre-implementation hypothesis predicted Lemma 1 invariance would break on curved lanes (constant lane-frame offset → curved SE(2) trajectory → non-zero second-derivative). Empirically the hypothesis is **wrong** — the body-frame error primitive transforms correctly with lane curvature, so a constant lane-frame offset becomes a constant body-frame offset between two predictors regardless of how the lane curves. **Lemma 1 invariance carries through the lift** on both straight and curved lanes; the test suite pins it at radii 50 m and 10 m. The genuine kernel-fire case is two predictors on **different reference paths** (SE(2) straight-line vs lane-frame on a curved lane) — desired behaviour, not an invariance violation. The residual cybersecurity concern (a constant `d` bias in a spoofed lane-frame predictor is invisible to BCVF — same Lemma-1 trapdoor as the SE(2) adversarial case) is pinned and points at the same UN ECE R155 §7.3.4 defence-in-depth mitigation. SOTIF clause 5 (functional spec) gains the multi-modal extension. All six new symbols are in `PROVISIONAL_API` (signature may evolve as a deployment partner exercises lane-frame predictors); `STABLE_API` graduation is gated on three explicit criteria in DESIGN.md §6. |
| **Functional-safety state machine (post-v0.7)** | `safety_state/` package + `SAFETY_STATE_MACHINE_DESIGN.md`. The runtime layer (kernel + arbitration + diagnostics) was a per-tick *signal*; the state machine composes it into a system-level *posture* an ISO 26262 safety case argues against. Four states: **NORMAL** (every predictor agrees, BCVF quiet), **DEGRADED** (one predictor near-veto, BCVF intermittent — planner reduces speed envelope), **FAULT** (sustained BCVF + exclusion logic triggered — planner enters minimum-risk maneuver), **FAILSAFE** (≥ 2 predictors excluded, kernel cannot form quorum — planner enters emergency stop). Six legal transitions; **direct jumps from NORMAL to FAULT or FAILSAFE are prohibited** (the machine raises `IllegalTransitionError`). ASIL decomposition: NORMAL↔DEGRADED + manual resets are **ASIL-B** (warning + bookkeeping); DEGRADED→FAULT and FAULT→FAILSAFE are **ASIL-D** (safety-critical). Trigger conditions are rolling-window predicates over the existing `TrustShapedEpisodeRecord` (`per_step_consec_suspect`, `per_step_is_excluded`, `per_step_bcvf_total`); recovery is automatic on DEGRADED→NORMAL with sustained dwell, **manual-only via `reset_with_diagnostic_clear(operator, reason)`** on FAULT→DEGRADED and FAILSAFE→FAULT. SOTIF clause 8 (functional insufficiencies + mitigations) gains the state machine as the insufficiency-handling layer the V2 chatter mitigation composes into; ISO 26262 Part 6 §8 (architectural design) names it as a system-level architectural module; clause 9 (V&V) acknowledges it as the behavioural-contract layer the per-cell threshold gates compose into; SOTIF_TRACEABILITY.md regenerates 28 → **30 indexed artifacts**. All nine new symbols are in `PROVISIONAL_API` (count lock 20 → **29**); `STABLE_API` graduation is gated on three explicit criteria in `SAFETY_STATE_MACHINE_DESIGN.md` §9: three deployment partners exercising in production for one quarter, the characterization grid's `state_transition_consistency` cell family (seeded in-tree at five seeds × three ASIL-D transitions × {must-fire, must-be-quiet}), and external auditor review of the §5 ASIL table. The §9 row #1 of `INDUSTRY_FEATURES_ROADMAP.md` is struck through with a pointer to the design doc per the §11 maturation path. **70 pinning tests** (4-state enum + legal-edge table; direct-jump-prohibition parametrized over every illegal pair; per-trigger fire / non-fire pins; recovery dwell math; manual-reset operator + reason validation; transition log discipline; rolling-window primitives; SOTIF clause-8 + Part-6-§8 evidence wiring; AlertRule composition with `StreamingFleetMonitor`; `state_transition_consistency` family at five seeds). |
| **ROS 2 / DDS / CycloneDX SBOM integration contract (post-v0.7.x)** | `bcvf_ros2/` companion package + `safety_case/sbom/` generator + `ROS2_DDS_SBOM_DESIGN.md`. Three first-call questions every Tier 1 / OEM customer asks (*does it speak ROS 2? / what's the DDS QoS profile? / where's the SBOM?*) now have code answers a reviewer can `cd` into. **ROS 2 message contract** — typed `bcvf_ros2/msg/PredictorTrajectory.msg` + `bcvf_ros2/msg/ConsensusOutput.msg` (the latter carries the trust distribution + the safety-state-machine state + per-state ASIL classification). **`BCVFNode` (alias of `BCVFNodeBehaviour`)** is framework-agnostic — testable without `rclpy` — wraps the existing `BCVFTrustBridge` with rate-limited publication (`publish_rate_hz`, default 100 Hz), per-predictor deadline tracking (`predictor_deadline_ms`, default 100 ms; deadline-violated predictors flagged in `is_excluded`), stale-on-resume protection (a deadline-violated predictor needs one fresh post-tick message to clear), and `SafetyStateMachine` composition (each tick's exclusion + BCVF totals feed the state machine; resulting state + ASIL class travel in the published `ConsensusOutput`). **DDS QoS profile** — `bcvf_ros2/qos.py` ships the `DDS_QOS_PROFILE` constant (the documented `RELIABLE / VOLATILE / 10 ms deadline / 100 ms liveliness lease / KEEP_LAST / depth 1` quad) as a frozen dataclass with per-knob validation; `build_rclpy_qos_profile` is the lazy-rclpy adapter that converts to a real `rclpy.qos.QoSProfile` at the bus boundary. **CycloneDX 1.5 SBOM** — `safety_case/sbom/generate_cyclonedx_bom()` enumerates every runtime dependency (`numpy` + stdlib for the autonomy import graph) with version + SPDX license, emits a deterministic byte-stable manifest at `safety_case/SBOM.cdx.json`. Compound SPDX expressions (e.g. numpy's `BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0`) render under the CycloneDX `expression` field per the spec. SOTIF clause 5 (functional + system spec) names the ROS 2 / DDS bus boundary; SOTIF clause 12 (release-to-market + configuration management) is added with the SBOM as the configuration-management deliverable; ISO 26262 Part 6 §8 (architectural design) names BCVFNode + DDS QoS + SBOM as architectural modules. SOTIF_TRACEABILITY.md regenerates 30 → **33 indexed artifacts**. Twelve new symbols enter `PROVISIONAL_API` (count lock 29 → **41**); `STABLE_API` graduation gated on five explicit criteria in `ROS2_DDS_SBOM_DESIGN.md` §9 (one deployment partner running BCVFNode in production for one quarter, one deployment partner accepting the SBOM into procurement, RTI Connext + FastDDS interop, colcon-build artifacts under humble + jazzy, external auditor SBOM validation). The §9 row #2 of `INDUSTRY_FEATURES_ROADMAP.md` is struck through with a pointer to the design doc per the §11 maturation path. **50 pinning tests + 11 design-doc pins** (DDS QoS knob validation; BCVFNode rate-limit + deadline + stale-on-resume + safety-state composition; SBOM determinism + snapshot byte-equality + SPDX expression rendering; design-doc section + invariant pins). |
| **Replay / record-and-replay framework (post-v0.7.x)** | `replay/` package + `REPLAY_FRAMEWORK_DESIGN.md`. **The recall-investigator's tool**: `ReplayBundle` ties `(RunConfig, recorded TrustShapedEpisodeRecord, package version, episode metadata, recorded collision flag, recorded total steps)` into a single JSON-serialisable artifact a recall investigation argues against. `replay_bundle(bundle, runner_factory)` runs the bundle's config through the current code via a caller-supplied factory (the runner re-instantiation is integration-specific; the framework doesn't impose one), then `compare_replay()` walks every per-step array (weights / costs / residuals / EMA mean+std / BCVF total / deadband / exclusion / gate activations / V2 signal+state / consec counters) with `np.array_equal(equal_nan=True)` for **bit-identity verification**. A typed `ReplayResult` returns `matches_recorded: bool`, `per_field_divergences: Tuple[str, ...]` (e.g. `"per_step_costs"` or `"n_steps"`), and `per_step_divergences: Tuple[int, ...]` (tick indices that disagree). The §5 design doc names three divergence classes: **Class A** (kernel diverged — same `RunConfig`, different output → point at the kernel diff between record-time and replay-time `package_version`); **Class B** (config drift — bundle JSON shape changed in a backward-compat way, surfaces structurally); **Class C** (host non-determinism — numpy version bump flipped a bit, out of scope per §8). The framework doesn't classify divergences; it surfaces them loud. Strict-validation discipline mirrors `analysis/io.py:episode_record_from_dict`: a malformed `recorded_record` cannot be smuggled past bundle construction; a missing field at JSON load raises `ReplayBundleError` naming the field; an unsupported `bundle_version` raises `ReplayBundleVersionError`. SOTIF clause 10 (operational design + field monitoring) gains the bundle as the post-incident recall artifact; ISO 26262 Part 6 §11 (verification of software safety requirements) gains the bit-identity contract as V&V evidence the recall investigator argues against. SOTIF_TRACEABILITY.md regenerates 33 → **35 indexed artifacts**. Ten new symbols enter `PROVISIONAL_API` (count lock 41 → **51**); `STABLE_API` graduation gated on five explicit criteria in `REPLAY_FRAMEWORK_DESIGN.md` §9 (deployment-partner usage one quarter, real-recall bit-identity replay, Class-A divergence detection across a kernel change, signed bundle integrity field, external auditor sign-off on bundle JSON shape). The §9 row #3 of `INDUSTRY_FEATURES_ROADMAP.md` is struck through with a pointer to the design doc per the §11 maturation path. **35 pinning tests + 10 design-doc pins** (bundle construction + strict validation; round-trip determinism; canonical JSON serialisation; load failure modes; bit-identity gate on identical / diverging records; field-level + tick-level divergence localisation; package-version drift flag; replay-bundle factory composition; build-replay-bundle defaults). |
| **Real-time / p999 budget framework (post-v0.7.x)** | `realtime/` package + `REAL_TIME_BUDGET_DESIGN.md`. **The AUTOSAR-Adaptive deal-unlock answer**: a typed `RealTimeBudget` contract (target_hz + p99/p999/p9999/max ms thresholds + sample-count gates protecting against statistically-meaningless small-n percentile reports) is the integration-contract surface a deployment partner copies into their config. Defaults target a 100 Hz drone tier (deadline 10 ms, p99 budget 8 ms); AUTOSAR partners override per their tier (10 Hz automotive, 50 Hz industrial). `LatencyMonitor` ingests one observation per tick via `observe(elapsed_ms, tick_index=i)` and classifies against the budget tiers with **mutually-exclusive counters** (a tick exceeding p9999 but not max increments only n_p9999_violations — the audit trail is unambiguous about which tier each violation belongs to). Over-budget violations append to a bounded ring buffer (default capacity 100) so the audit log doesn't grow unbounded under sustained violations. `LatencyMonitor.summary()` returns a typed `BudgetSummary` with mean / p50 / p95 / p99 / max + the p999/p9999 percentiles **only when sample count clears the documented threshold** (default min_samples_for_p999=1000, min_samples_for_p9999=10000) — a small-n p999 is statistical noise, not a contract; the framework returns None rather than fabricate a number. Budget validation rejects non-monotone tier configurations (p999 < p99, etc.) at construction so a typo'd deployment-partner config fails loud. `observe_series()` bulk-ingests an `EpisodeDiagnostics.solve_times_ms` array — composes with the existing runner output without a manual loop. Advisory `tracemalloc`-based per-tick allocation deltas surface allocation hotspots (opt-in via `track_allocations=True`); the framework explicitly does NOT claim a "no allocations" contract pure-Python can't deliver, with the C++ port flagged as the right surface for that discipline. ISO 26262 Part 6 §10 (integration verification) gains both `RealTimeBudget` + `LatencyMonitor` as the runtime-deadline V&V evidence. SOTIF_TRACEABILITY.md regenerates 35 → **37 indexed artifacts**. Seven new symbols enter `PROVISIONAL_API` (count lock 51 → **58**); `STABLE_API` graduation gated on five explicit criteria in `REAL_TIME_BUDGET_DESIGN.md` §9 (AUTOSAR-class deployment-partner usage one quarter, real 10⁶-tick load test, C++-port equivalence within 2× on the smallest config, external auditor sign-off on percentile-reporting + over-budget-log format, configurable persistence layer for the over-budget log). The §9 row #4 of `INDUSTRY_FEATURES_ROADMAP.md` is struck through with a pointer to the design doc per the §11 maturation path. **39 pinning tests + 10 design-doc pins** (budget validation incl. monotone-tier check + sample-count floor; mutually-exclusive tier classification; at-threshold non-violation discipline; percentile-availability gate; ring-buffer bounded log; bulk-series ingest; reset semantics; allocation-trace advisory; BudgetSummary serialisation incl. None-preservation for missing percentiles). |
| **Public-API stability commitment (v0.4.0)** | `_api.py` registry — 38-symbol `STABLE_API` + **58-symbol** `PROVISIONAL_API` (was 20; +9 SafetyStateMachine surfaces post-v0.7, +12 ROS 2 / DDS / SBOM integration-contract surfaces post-v0.7.x, +10 replay-framework surfaces post-v0.7.x, +7 real-time-budget surfaces post-v0.7.x), both as flat tuples of canonical `submodule.Symbol` paths machine-checked at every commit. `API_STABILITY.md` documents the three tiers (stable / provisional / internal), the semver mapping (patch / minor / major triggers), and the deprecation cycle (post-1.0 stable removal requires one-minor-version notice + `DeprecationWarning` + release-note line). `__version__ = "0.4.0"` and `VERSION_INFO = (0, 4, 0)` agree by test pin. Top-level `from bcvf_autonomous import X` continues to work for the existing re-exports, but the contract is the explicit 38-symbol registry — the v0.2 brief's "tested integration contract" promise becomes the machine-checkable thing the test suite enforces. |
| **Kernel modules** | `core.py` (V3.1 §3.3–§3.5 + Lemma 1), `manifold.py`, `mppi_planner.py` (delegates to `trust.py`), `runner.py`, `scenarios.py` (S1–S6), `predictors/` (M1–M4 variants with failure injection), pure NumPy, ~4,700 LOC |
| **Consumer-layer extraction (§6.3)** | `trust.py` — planner-agnostic `TrustWeightComputer`. `integrations/` package with `argmin_selector.py` reference adapter + API-contract README. Extraction preserves 190 pre-existing tests bit-identical (behavior-preserving refactor) |
| **Non-MPPI adapter demonstrated** | `integrations/argmin_selector.py` — ArgminSelectorPlanner shares `TrustWeightComputer` with `MPPIPlanner` with **zero code duplication**. 7 integration tests proving Lemma 1 propagates through the non-MPPI path |
| **Multi-scenario validation (§6.1)** | Scout pass identified 2/6 scenarios as responsive (S3-variant family) + 4/6 benign + 1/6 BCVF-inapplicable. Both responsive scenarios pass p < 0.05 |
| **Architectural variant tested and rejected (§6.6a)** | Dynamic predictor exclusion implemented, run at N=21 S3_accel, rejected under strict multi-metric promotion gate. Rotates catastrophes, doesn't reduce the count. Rejection strengthens V1 claim: "V1 is not just simplest, it's what one non-trivial variant failed to improve upon" |
| **Observables framework (v0.3)** | `observables/` — six probes (`PredictorAgreement`, `EnsembleSpread`, `EnsembleHeadingEntropy`, `BCVFPerStepMax`, `BCVFPredictorPerStepMax`, `CoherenceAnchoredBCVF`, `UncertaintyGatedBCVFPerStepMax`). Each consumes the predictor trajectory tensor and returns a typed `ObservableValue` with metadata. Probe harness (`probe_observable`) runs against a labelled corpus and classifies the observable into SAFETY_CORRELATED / UNCORRELATED / ANTI_CORRELATED / NULL bands (AUC + Pearson + Spearman). 36 tests. |
| **Per-step trust diagnostics (v0.3)** | `trust_diagnostics.py` — `TrustStepRecord` per tick + `TrustShapedEpisodeRecord` `(T, M)` stacked arrays + JSON `to_dict()`. Captures weights, residuals (against pre-update EMA, exact), EMA mean/std snapshots, deadband activations, exclusion state, gate counts, V2 state + signal, and exclusion `consec_suspect` / `consec_ok` counters. Wired into `MPPIPlanner.set_trust_diagnostics_enabled` and `Runner` via three `RunConfig` knobs (`trust_diagnostics_enabled`, `trust_diagnostics_path`, `trust_diagnostics_aggregation`). |
| **Characterization sweep (v0.3, certification-grade in v0.7)** | `characterization/` — seven SE(2) trace families (baseline, constant_bias, linear_drift, accelerating, noise_floor, outlier, sensor_dropout) + outlier-attribution metrics (hit / margin / rank). Three grids: `run_primary_grid` (**1320 cells = 22 configs × 60 seeds**, 0% FPR / 0% FNR at V1 defaults, every per-config Wilson 95% CI lower bound ≥ 0.90 with min observed ≈ 0.940), `run_sensitivity_grid` (567-cell `(T, β, δ)` sweep, V1 defaults selected as winner-tuple), `run_ablation_grid` (linear_drift × CostOrder ablation confirms only SECOND order rejects linear drift). The summary returns a typed `GridSummary` exposing per-config Wilson CIs, `min_ci_lower_bound`, and `cells_below_certification_floor` — the stated SOTIF contract is machine-checkable per cell. **`GridSummary.to_csv(path)` and `GridSummary.to_markdown_report(path)`** emit the frozen audit-pack deliverables (the v0.3 deferral note in the DESIGN was retired); the markdown report carries headline gate / per-(family, magnitude) Wilson-CI table / per-family roll-up / failed-config list / methodology block, and renders deterministically up to the timestamp. Three sabotage tests confirm the suite would fail on a broken kernel; one additional sabotage test confirms a synthetic-failure injection at a single config trips `cells_below_certification_floor`. |
| **Consumer V2 — Schmitt-triggered softmin (v0.3)** | `trust.py` ConsumerV2Config + ConsumerState. Top-level state machine wraps the V1 shaping layer (deadband + softmin + §6.6a exclusion); EMA learning continues during UNIFORM so the deadband / softmin start warm on the first ENGAGED tick. Hysteresis defaults: `engage_threshold=0.5`, `disengage_threshold=0.2`, `T_engage=3`, `T_disengage=5`. Opt-in via `ConsumerV2Config(enabled=True)`; default-off preserves bit-for-bit V1 behavior. 21 tests. |
| **Post-hoc fleet analysis harness (v0.3, streaming-grade post-v0.7, audit-pack-grade post-v0.7)** | `analysis/` — `find_argmax_flips` (with `weight_drop` + `max_abs_weight_delta` magnitude metrics), `find_v2_state_flips`, `find_near_vetoes` (predictors that crested 70% of `exclusion_T` without crossing). Batch aggregators `summarize_episode` and `aggregate_fleet` consume per-episode `TrustShapedEpisodeRecord`s and return a `FleetSummary` with per-classification counts, argmax-flip percentile statistics, per-predictor exclusion-incidence rate, and a typed near-veto roster (each event carrying per-episode metadata for triage). `load_episode_from_json` reverses the Runner's diagnostics dump with strict shape validation; corrupt artifacts fail loudly rather than silently producing zero-fill records. **`StreamingFleetMonitor` (post-v0.7)** lifts the harness from triage-time to runtime: `.observe_episode(record)` / `.observe_summary(...)` ingest, `.summary(window=timedelta(hours=24))` returns rolling-window `WindowedFleetSummary`, `.evaluate_alerts([rule])` fires `AlertRule` threshold rules with dotted-path metric paths (`argmax_flips_per_step.p95`, `deadband_fired_rate`, ...) — the runtime SRE surface a deployment partner wires into alertmanager / Grafana. Batch parity is the load-bearing contract: a window-bounded streaming summary is byte-identical to `aggregate_fleet` over the same episodes. **`FleetSummary.to_csv(path)` and `FleetSummary.to_markdown_report(path)` (post-v0.7)** retire the v0.3 deferral note and emit the SOTIF clause-10 frozen artifacts: per-episode CSV (RFC-4180-quoted, pinned column order) and a fleet-level narrative markdown (headline aggregates / classification breakdown / per-predictor exclusion incidence / near-veto + V2-state-flip rosters / top-K per-episode index / methodology block); both work identically on batch and streaming-windowed summaries. 26 batch tests + 29 streaming tests + 8 report-writer tests. |
| **Real-sensor pilot — runner + first execution (§6.2, v0.5)** | `pilot/` package: `scene_evaluator` (Mode A open-loop A0 / A3 paired evaluation), `sign_test` (Wilson CI + one-sided sign test, no scipy), `runner` (writes paired-comparison CSV + `FleetSummary` JSON + markdown report). Executed end-to-end against `RealisticNoiseAdapter` at N = 21: A3 win rate 1.000 with Wilson-CI lower bound 0.566 and sign-test p = 0.0312 on the responsive class; Lemma-1 negative control passes exactly. Three artifacts written to `results/phase_6_2_pre_pilot/`. 16 pilot tests + 11 prior dataset-adapter tests. `datasets/nuscenes.py` stub documents the one-line adapter swap; full execution pending dataset access + the M1–M4 predictor implementations the pilot plan estimates at 3–4 weeks. |
| **Apples-to-apples baseline shootout (v0.7)** | `baselines/` package: `BCVFArbitrator`, `EKFArbitrator` (with `robot_localization`-style Mahalanobis 3-sigma outlier rejection), `MajorityVoteArbitrator` (cluster-mode), `AnchorArbitrator` (null floor), all sharing the same `Arbitrator` protocol consuming `(M, H, 3)` predictor trajectories. Shootout runs every arbitrator × every characterization family × N seeds. Three artifacts (`shootout.csv`, `shootout.json`, `shootout_report.md`) in `results/baseline_shootout/`. The Lemma-1 false-attribution differentiator is the BD-grade headline; the EKF Mahalanobis miss on outlier is the *"this isn't a solved problem with the existing toolkit"* finding. 19 baseline tests, including pinned BD assertions (BCVF false-attr < 1e-6 on constant_bias, EKF > 0.1, Majority > 1.0). |
| **SOTIF / ISO 26262 traceability template (Q3 pulled to post-v0.7)** | `safety_case/` — `traceability.py` builds a clause-by-clause `TraceabilityMatrix` mapping 19 BCVF artifacts (kernel, characterization sweep, V2 hysteresis, fleet harness, per-step diagnostic record, baseline shootout, pilot runner, Wilson CI primitive, ...) to 12 standard clauses: SOTIF (ISO 21448) clauses 5/6/7/8/9/10 and ISO 26262 Part 6 §7/§8/§9/§9.4.4/§10/§11. The on-disk `SOTIF_TRACEABILITY.md` is a deterministic snapshot of the matrix (the test suite pins byte-equality between snapshot and renderer so the doc cannot drift). Every evidence reference is import-time-resolved by the test suite (`module_path::symbol` must exist, or the test fails loudly). The template is the Q3 "regulator-facing template" half of the brief item; the regulator workshop remains a Q3 deliverable. **The artifact half is now BD-callable on day one of a diligence engagement** instead of waiting for "after the safety case is ready." 20 traceability tests. |
| **V2 promotion-gate sweep + decision (v0.6)** | `v2_chatter_sweep.py`: paired V1 vs V2 runner with two-gate decision logic (chatter-reduction Wilson + rescue-preservation McNemar). Executed at N=5 on `S1_normal_driving` (chatter scenario) and `S3_map_error_accel` (rescue scenario), at default thresholds and at 50×-lower thresholds. **Finding: V2 reduces chatter by ≤ 0.6% on autonomy data because BCVF kernel cost exceeds V2's engage threshold even on nominal scenarios → V2 stays ENGAGED → V1 pipeline runs unchanged.** Honest non-promotion. The empirical result upgrades the v0.5 "V2 is opt-in" caveat from defensive to evidence-backed; threshold recalibration is a scoped Q2 followup. 12 sweep-module tests + artifacts in `results/v2_chatter_S1_n5/` and `results/v2_rescue_S3_n5/`. |
| **ROS 2 adapter scaffold (§6.4)** | `symbolu_bcvf_ros2` package with framework-agnostic core + lazy `rclpy` shim. Message dataclasses, bridge class, and 13 tests. `.msg` files + colcon build + real pub/sub pending ~3–4 weeks ROS-environment work |
| **Latency benchmark (§6.5)** | 18-cell (M × K × H) sweep, plus a v0.4 re-run after `predict_batch` vectorization. Smallest config (M=4, K=128, H=10) now p99 ≈ 38 ms (was 76). Per-predictor rollout cost dropped 52–77× across M1–M4 at K=1000, H=50; the new dominant cost is the BCVF kernel and perf-cost evaluation — the next vectorization targets. Production integrators should re-run on their substrate. |
| **`predict_batch` vectorization (v0.4)** | All four reference predictors (M1 IMU, M2 LiDAR, M3 VO, M4 GNSS — including all four GNSS failure modes and M3's tracking-loss freeze branch) ship with vectorized `predict_batch` overrides; default `BasePredictor.predict_batch` falls back to a per-rollout loop so custom predictors without an override still work. Bit-for-bit equivalent to the per-rollout loop (asserted by 11 parametrized tests + 4 ≥ 2× speedup gates). 18 new tests; bumps the per-predictor speedup the audit recommended item #1 from "1–2 weeks of work" to "landed." |
| **Diagnostic-consistency CI (§6.7)** | 18 parametrized invariant tests guarding `total_cost == Σ pair_costs` and `per_predictor.sum() == 2 × bcvf_total` across every (pairing, cost_order) combination |
| **Design specification** | Autonomy DESIGN.md Phase 6 (V2 roadmap) records per-item completion status; v0.3 adds five per-module DESIGN docs (`observables/DESIGN.md`, `characterization/DESIGN.md`, `analysis/DESIGN.md`, `CONSUMER_V2_DESIGN.md`, plus updated `trust_diagnostics` notes). Each module landed with an independent design doc + audit trail. |

All numbers are from our own repository and CI — not third-party
benchmarks. External multi-platform validation and a real-sensor
pilot are the next scheduled steps.

### Honest scope caveats (to preserve credibility)

- **Validated on disagreement-detectable failure modes.** S4
  (camera degradation) produces catastrophes but no predictor
  disagreement — BCVF is inapplicable there. 4/6 scenarios in our
  synthetic suite are benign (A0 handles them). The v0.3
  characterization sweep makes this explicit: seven failure
  families *are* covered, families that don't manifest as
  disagreement still aren't.
- **Validated on synthetic M1–M4 + the realistic-noise adapter
  bridge; real automotive sensor data still pending.** The v0.5
  pilot ran against `RealisticNoiseAdapter` (correlated AR(1)
  noise + 2% non-Gaussian outliers + the four canonical pilot
  failure shapes). The runner / metrics / FleetSummary / sign
  test are dataset-agnostic by construction; rerunning on real
  nuScenes-mini is a `NuScenesAdapter` implementation away. The
  pilot plan §scope-caveats remain in force for any real-data
  result — single-city, single-weather, synthetic ego dynamics.
- **Predictor rollout vectorization landed (v0.4).** All four
  reference predictors (M1–M4) ship with `predict_batch` overrides
  that run K rollouts through the H sequential dynamics steps with
  `(K,)`-shaped state arrays — observed **52–77× per-predictor
  speedup** at K=1000, H=50 vs the prior per-rollout Python loop,
  bit-for-bit equivalent to the reference loop (asserted by 11
  parametrized equivalence tests across all failure modes).
  Custom predictors without an override fall back to the default
  loop. The audit caveat in v0.2/v0.3 ("dominant cost is the
  Python-level per-rollout predictor loop") is now resolved; the
  remaining latency budget is the BCVF kernel and the MPPI
  perf-cost evaluation, which are the next vectorization targets.
- **Drone / industrial rates remain partially out of reach on the
  largest configs.** Automotive 10 Hz now fits at the small config
  (K=128, H=10, p99 ≈ 38 ms). 50 Hz / 100 Hz still need kernel-
  side vectorization; production integrators should re-run the
  benchmark on their target compute substrate.
- **No production deployment.** No operator runs V1 on their
  stack today. §6.8 is the Series-A-gated BD milestone.
- **The 3-catastrophe floor on S3 is scenario-structural.**
  §6.6a empirically confirmed that trust-shaping alternatives
  rotate which seeds fail but do not reduce the count. v0.3
  Consumer V2 reduces *chatter* on borderline disagreements but
  does not, by itself, change this floor. Structural improvement
  requires either a richer predictor set or a higher-level
  safety-monitor layer — both out of V1 scope.
- **Consumer V2 is opt-in, not the default — empirically
  validated as the right call.** The v0.6 chatter-reduction
  sweep (`v2_chatter_sweep.py`, N=5 paired) measured V1 vs V2 on
  `S1_normal_driving`. Median per-seed flip-rate reduction:
  **0.6%** at the default thresholds, **0.5%** at 50×-lower
  thresholds (`engage_threshold=0.01`). Reason: BCVF kernel cost
  on autonomy scenarios — even nominal ones — exceeds V2's
  engage threshold across K=64+ rollouts, so V2 stays ENGAGED
  ~99% of ticks and the V1 pipeline runs unchanged. **The V2
  Schmitt-trigger design is correct (UNIFORM forces uniform
  weights → zero argmax flips); the threshold calibration is
  wrong for the autonomy domain.** Promotion deferred until the
  engage signal / threshold are recalibrated against measured
  autonomy BCVF magnitudes — a Q2 followup, scoped at ~1 week.
  V2 stays an opt-in safety feature for integrators whose
  BCVF magnitudes match the LLM-domain hysteresis design.
- **The fleet analysis harness has been validated end-to-end on
  synthetic episodes only.** Multi-episode aggregation across
  thousands of real trips is the §Q1 + §Q2 follow-on; the
  harness ingests JSON dumps the Runner already produces, so
  this is execution work, not research.
- **LLM-domain transfer is not claimed.** An internal research
  track (`docs/design/BCVF_LLM_TRUST_ROUTING_DESIGN.md` §13)
  tested whether the same BCVF math applies to LLM
  hallucination detection. The N=100 TruthfulQA probe across
  11 candidate observables returned AUC in [0.476, 0.527] —
  a clean null. BCVF does **not** currently transfer to LLM
  trust routing, and we do not position it as a hallucination
  detector. The autonomy result above is not predicated on
  LLM transfer and stands independently.

### 12-month roadmap (de-risking sequence, matches §6.10 — refreshed v0.3)

**Quarter 1 — External validation**
- **§6.2 execution.** Pilot **runner** landed in v0.5; first paired
  execution against `RealisticNoiseAdapter` shipped (N=21, win
  rate 1.000, p=0.0312, Lemma-1 PASS). Q1 follow-on:
  nuScenes-mini download → fill in `datasets/nuscenes.py`
  load_scene() → M1 HD-map / M2 Kalman / M3 lightweight LSTM /
  M4 failure-injected predictor wrappers → re-run the same
  unchanged pilot runner on real data → publish the
  paired-comparison CSV + FleetSummary JSON. Code path is
  identical to the synthetic-noise pre-pilot; the swap is one
  line.
- **§6.3 parity audit.** Re-run §6.1 S3_accel sweep against the
  post-refactor branch to confirm bit-accurate behavior-preservation.
  ~25 min compute. Strengthens the "extraction was zero-risk" claim.
- **§6.5 production-substrate benchmarks.** Re-run latency sweep on
  a TDA4VH / Orin / AMD EPYC sample to produce numbers an
  integrator can plan against. 1–2 days per target.
- ~~**Consumer V2 chatter-reduction sweep.** Re-run §6.1 S3_accel with
  V2 enabled; quantify per-step argmax-flip rate reduction; promote
  V2 to default once chatter reduction is statistically significant
  without harming rescue-pattern reproduction. 1 week.~~ **Landed in
  v0.6 — non-promotion result. The threshold recalibration follow-on
  moves to Q2.**

**Q2 — V2 threshold recalibration (new, was Q1's V2 promotion).**
The v0.6 sweep showed V2's engage threshold doesn't correspond to
autonomy BCVF cost magnitudes. Recalibration paths to investigate:
(a) drive engage signal off `bcvf_total.min(axis=0)` instead of
the mean — least-noisy rollout instead of population view;
(b) threshold against per-tick BCVF distribution mean over a
trailing window instead of a fixed magnitude; (c) ladder of
thresholds calibrated per-scenario class. ~1 week.

**Quarter 2 — Platform integration**
- **§6.4 execution.** `.msg` + colcon + real rclpy pub/sub, Nav2
  `CriticPlugin`, example launch files, rosbag integration test.
  3–4 weeks in a ROS 2 Humble / Jazzy environment.
- **First external-integrator confirmation.** OSS contributor or
  design-partner drops the package into their Nav2 / Autoware
  stack and confirms install + run. Required for §6.4 acceptance.
- ~~**`predict_batch` vectorization** (unblocks drone / industrial
  rates). 1–2 weeks.~~ **Landed in v0.4 — per-predictor cost down
  52–77× at K=1000, H=50.** Follow-on: kernel-side vectorization
  for the now-dominant BCVF + perf-cost evaluation cost.

**Quarter 2 — Pulled forward from Q3**
- ~~**SOTIF / ISO 26262 traceability template.** Map Lemma 1
  invariance + the v0.3 characterization-sweep failure taxonomy +
  per-step diagnostic record + Consumer V2 chatter-immunity proof
  to a safety-case narrative. The five v0.3 artifacts cover the
  bulk of what an auditor's clause-by-clause walk requires; the
  Q3 work is the regulator-facing template + workshop, not new
  code. 2–3 weeks + regulator workshop.~~ **Template half landed
  post-v0.7 in `safety_case/` — 12 clauses (SOTIF 5/6/7/8/9/10 +
  ISO 26262 Part 6 §7/§8/§9/§9.4.4/§10/§11), 19 indexed BCVF
  artifacts, machine-checked snapshot in
  `safety_case/SOTIF_TRACEABILITY.md`. Regulator workshop remains
  a Q3 deliverable; the artifact-half is now BD-callable on day one.**

**Quarter 3 — Safety-case + adjacent-domain pilot**
- **First paid design-partner engagement** (adjacent domain —
  drone / warehouse / industrial mobile robot). Not full AV.

**Quarter 4 — Production reference**
- **§6.8 first production reference customer.** Running V2 (post-
  real-sensor-pilot) on their own stack in their own environment.
  Reference letter or published case study. The fleet analysis
  harness lets the partner publish a *fleet-level* trust-pipeline
  report at handover, not just a single integration report.

### Longer-horizon research (design-only today)

- **Hierarchical / group-level BCVF.** When `M` scales beyond 4–6
  predictors (a full sensor suite with multiple LiDARs + cameras +
  radar + IMU + GNSS), the all-pairs cost grows quadratically and
  per-predictor attribution dilutes. A two-level kernel — first
  within a sensor group, then across group representatives — would
  scale better. Landed post-v0.7 as
  `HIERARCHICAL_BCVF_DESIGN.md`: motivation, two-level structure,
  three representative options (trust-weighted / arithmetic /
  winner-take-all) with Lemma-1 carry-through analysis,
  per-predictor attribution, the new failure modes the hierarchy
  catches (cross-group correlated drift) and *can't* fully solve
  (within-group correlated failure), certification implications
  (~5 new families on the 1320-cell grid), backward-compatibility
  contract (`groups=None` falls through to flat BCVF), and the
  three ship-when-ready criteria gating promotion to a deliverable.
  9 tests pin the doc presence + content + non-promotion of any
  hypothetical hierarchical surface to `STABLE_API` /
  `PROVISIONAL_API`. **No implementation today** — the flat
  `M = 3 / M = 4` kernel remains the production default and the
  certification target.

### The ask

Seed capital to convert a CI-validated research prototype with one
statistically significant autonomy companion result into a
portable, multi-platform predictor-trust runtime that at least one
external operator runs in production. The technology is live —
221 tests, two scenarios validated, planner-agnostic runtime
extracted, real-sensor and ROS 2 scaffolds shipped — and everything
on the remaining roadmap is execution work against known dependencies
(dataset access, ROS 2 install, target hardware, BD engagement),
not open research.

Capital is earmarked for:

1. **External validation** — nuScenes pilot execution (Q1) +
   production-substrate latency re-runs (Q1) + first external-
   integrator confirmation of the ROS 2 adapter (Q2).
2. **Platform integration** — ROS 2 adapter execution (Q2) +
   `predict_batch` vectorization (Q2) + Autoware / Apollo
   reference integrations (Q2–Q3).
3. **Safety-case readiness** — SOTIF / ISO 26262 traceability
   template **landed post-v0.7** (12 clauses, 19 indexed
   artifacts, machine-checked snapshot in
   `safety_case/SOTIF_TRACEABILITY.md`); regulator engagement
   stays Q3.
4. **First production reference** — adjacent-domain design partner
   (Q3) + production reference (Q4).

Series A is conditional on §6.8 (one production reference) landing.
Seed covers the 12 months of de-risking work that makes §6.8
reachable.

---

*Contact: Rakesh Mohan — Cognade Labs*
*Repo: `rasaha/symbolu` · Module: `symbolu_robotics/bcvf_autonomous/`*
*v0.7 · 972 internal tests (audit pinning tests included; published numbers unchanged; characterization primary grid now certification-grade at 1560 cells across 8 families × 26 configs with Wilson 95% CI lower-bound floor 0.90 per (family, magnitude) config — current min ≈ 0.940; Q3 SOTIF / ISO 26262 traceability template pulled forward — 13 clauses across SOTIF 5/6/7/8/9/10/12 and ISO 26262 Part 6 §7/§8/§9/§9.4.4/§10/§11, **37 indexed BCVF artifacts**, machine-checked snapshot in `safety_case/SOTIF_TRACEABILITY.md`; `StreamingFleetMonitor` with rolling-window summaries + threshold alerts lifts the fleet harness from triage to runtime; the two deferred CSV / Markdown report writers landed; **0.4.0 release ratifies a public-API stability policy** — 38-symbol `STABLE_API` + **58-symbol `PROVISIONAL_API`** (was 14, +6 multi-modal surfaces, +9 safety-state-machine surfaces, +12 ROS 2 / DDS / SBOM surfaces, +10 replay-framework surfaces, +7 real-time-budget surfaces), deprecation cycle in `API_STABILITY.md`; **hierarchical / group-level BCVF design proposal** lands as a design-only doc gated on three ship-when-ready criteria; **adversarial / spoofing test family** lands as the 8th family and third polarity bucket — UN ECE R155 cybersecurity scope-boundary pinned via the Lemma-1-trapdoor; **multi-modal predictor inputs** thin-shim adapter lifts lane-frame predictors to SE(2) at the kernel boundary — Lemma 1 invariance verified to carry through curved lanes contrary to the pre-implementation hypothesis; **functional-safety state machine** lands as the §9.1-recommended top-of-roadmap pick — `safety_state/` package + load-bearing `SAFETY_STATE_MACHINE_DESIGN.md` + clause-8 / Part-6-§8 traceability wiring, four-state behavioural contract with ASIL-decomposed transitions and machine-enforced direct-jump prohibition; **ROS 2 / DDS / CycloneDX SBOM integration contract** lands as the §9-row-#2 deal-unlock pick — `bcvf_ros2/` framework-agnostic `BCVFNode` + typed `.msg` schemas + documented `RELIABLE / VOLATILE / 10ms / 100ms` DDS QoS profile + `safety_case/SBOM.cdx.json` CycloneDX 1.5 manifest, load-bearing `ROS2_DDS_SBOM_DESIGN.md`, SOTIF clause-5 boundary + clause-12 release-to-market evidence wiring; **replay / record-and-replay framework** lands as the §9-row-#3 recall-investigator's tool — `replay/` package + load-bearing `REPLAY_FRAMEWORK_DESIGN.md`, `ReplayBundle` + bit-identity comparator with field-level + tick-level divergence localisation, SOTIF clause-10 + Part-6-§11 traceability wiring; **real-time / no-allocation hot path + p999 budget framework** lands as the §9-row-#4 AUTOSAR-Adaptive deal-unlock pick — `realtime/` package + load-bearing `REAL_TIME_BUDGET_DESIGN.md`, typed `RealTimeBudget` contract + `LatencyMonitor` per-tick observer with mutually-exclusive tier counters + percentile-availability discipline rejecting statistically-meaningless small-n p999/p9999 claims, ISO 26262 Part 6 §10 integration-verification evidence wiring; **`INDUSTRY_FEATURES_ROADMAP.md`** documents the eight gap-fill items ranked by deal-unlock value with rows #1 (state machine) + #2 (ROS 2 / DDS / SBOM) + #3 (replay framework) + #4 (real-time budget) struck through with pointers to their design docs, the remaining four (HD-map predictor + calibration drift + sensor attestation + domain-specific predictors) still gated by non-promotion checks against `STABLE_API` / `PROVISIONAL_API`) · apples-to-apples baseline shootout landed (BCVF zero false-attribution on Lemma-1 vs Majority 16.7 / EKF 1.1; EKF misses heavy-quadratic outlier; BCVF 8–19× faster per tick) · V2 promotion-gate sweep landed (median chatter reduction 0.6%, non-promotion, Q2 recalibration scoped) · §6.2 pilot runner executed end-to-end (N=21, win rate 1.000, p=0.0312 on responsive class, Lemma-1 negative control PASS, three artifacts on disk) · 2 synthetic-predictor scenarios p < 0.05 · planner-agnostic runtime extracted (§6.3) · per-step diagnostics + fleet analysis harness · Consumer V2 (Schmitt-triggered) chatter-immunity opt-in (evidence-backed) · `predict_batch` vectorization 52–77× per-predictor speedup · `NuScenesAdapter` stub documents one-line real-data swap*
