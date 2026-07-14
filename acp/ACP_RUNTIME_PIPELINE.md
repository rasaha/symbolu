# ACP Runtime Pipeline — Deterministic Decision Logic (Task 2)

For every stage: **inputs → outputs → deterministic algorithm → runtime
complexity → failure modes.** Probabilistic scoring is avoided wherever a
deterministic decision is possible; the two places a *measurement* is
unavoidable (residuals, margins) are reduced to deterministic thresholds and
totally-ordered tie-breaks.

Notation: `M` = number of predictors (fixed, ≤ 8), `K` = number of candidate
actions (fixed, ≤ 64), `H` = planning horizon in ticks (fixed), `O` = obstacles
in the validated snapshot (bounded by a hard cap `O_max`).

---

## Stage 1 — Mission Intake

- **Inputs:** raw mission request (goal set, constraints, ODD tags).
- **Outputs:** `AdmittedMission` or `REJECT_MISSION(reason)`.
- **Algorithm:** schema validation + static bounds check (goal count ≤ cap, ODD
  tags ⊆ supported set, no conflicting terminal goals). Pure predicate
  evaluation; no search.
- **Complexity:** `O(|mission fields|)`, constant per tick after admission.
- **Failure modes:** malformed mission → `REJECT_MISSION`; over-scope ODD →
  `REJECT_MISSION`; empty goal set → `REJECT_MISSION`. Fail-closed: an
  unadmitted mission never reaches stage 2.

## Stage 2 — Task Planner

- **Inputs:** `AdmittedMission`, current task-stack state.
- **Outputs:** ordered `TaskStack` (bounded depth) or `FAIL_PLAN(reason)`.
- **Algorithm:** deterministic HTN / precedence decomposition. Fixed method
  library, lexicographic method selection, no learned policy, no random
  restarts. If the existing `planning/htn_planner.py` is deterministic it is
  wrapped here (see reuse audit).
- **Complexity:** `O(T · b)` for `T` tasks, branching `b`, both bounded; worst
  case pinned by a fixed expansion cap.
- **Failure modes:** unreachable goal under current constraints → `FAIL_PLAN`
  (routed to recovery, not silently dropped); expansion-cap hit → `FAIL_PLAN`
  with partial-plan diagnostic.

## Stage 3 — Safety Constraint Resolver

- **Inputs:** `AdmittedMission`, ego pose, map reference, regulatory context.
- **Outputs:** `ConstraintSet` = ordered list of typed hard constraints, plus
  `constraint_set_hash`.
- **Algorithm:** deterministic assembly by lookup + geometry: active geofence
  polygons, speed law for current road/zone class, kinematic envelope for the
  platform, mission-specific keep-outs. No optimization — pure resolution of
  "which hard rules are active here."
- **Complexity:** `O(C)` for `C` candidate constraints, `C` bounded.
- **Failure modes:** missing regulatory context → conservative default
  (most-restrictive constraint) + `DEGRADED` flag, never an empty constraint
  set. An empty `ConstraintSet` is a hard error (fail-closed): decisions require
  a non-empty safety envelope.

## Stage 4 — World State Validation

- **Inputs:** raw world model (ego, obstacles, map, sensor health,
  predictor streams), clock.
- **Outputs:** `WorldSnapshot` (with `snapshot_hash`) or `STALE_WORLD(reason)`.
- **Algorithm — deterministic gates, all fail-closed:**
  1. *Freshness:* every required input's age ≤ its budget (clock-driven).
  2. *Completeness:* every required field present; `obstacles ≤ O_max`.
  3. *Consistency:* ego pose within map bounds; obstacle geometry finite; no NaN/Inf.
  4. *Hash:* content hash over the validated fields → `snapshot_hash`.
- **Complexity:** `O(O + M)`, linear in bounded inputs.
- **Failure modes:** any gate fails → `STALE_WORLD` → recovery. This is the fix
  for the class of "silent zero-fill on corrupt input" bugs the prior kernel
  audit found; corrupt input fails loud here, never proceeds.

## Stage 5 — Predictor Reliability V2

- **Inputs:** `WorldSnapshot.predictor_streams` (M streams, each a short history
  of `(H,3)` SE(2) trajectories + freshness/health), clock.
- **Outputs:** `TrustReport` = per-predictor `state ∈ {TRUSTED, DEGRADED,
  SUSPECT, FAILED, RECOVERING}`, a trusted-consensus trajectory, and a
  system-level `ABSTAIN` flag when no trusted quorum exists.
- **Algorithm:** deterministic multi-signal detector — innovation residual vs
  robust consensus, persistent-bias significance test, variance, freshness,
  latency, dropout, sensor-health — combined by a **fixed precedence** state
  machine (full spec in `ACP_PREDICTOR_RELIABILITY_V2.md`). Optional BCVF
  2nd-order feature may only shorten detection latency. No softmax, no learned
  weights.
- **Complexity:** `O(M · H)` per tick; all loops bounded by fixed M, H.
- **Failure modes:** < 2 fresh predictors → `ABSTAIN`; ≥ half SUSPECT → `ABSTAIN`
  (no trusted quorum); common-mode (all agree, all wrong) → **undetectable here
  by design** → covered only by the independent-reference hook (deficiency D1).

## Stage 6 — Action Candidate Generation

- **Inputs:** `TaskStack` top goal, `WorldSnapshot`, trusted consensus,
  `ConstraintSet` (for feasibility-aware sampling, not filtering).
- **Outputs:** `Candidates[K]` — a **fixed-size** set of `CandidateAction`, each
  with a predicted trajectory and computed hard+soft features.
- **Algorithm:** deterministic primitive expansion — a fixed motion-primitive
  library (or a fixed lattice) evaluated against the trusted consensus. Seeded,
  fixed count. No stochastic sampling; if a sampler is used it is a fixed
  low-discrepancy sequence, not an RNG.
- **Complexity:** `O(K · H)` trajectory rollout, bounded.
- **Failure modes:** zero candidates generated (e.g. fully blocked) → empty set
  → handed to stage 7 which will yield `NO_SAFE_ACTION` downstream. Never
  fabricates a candidate.

## Stage 7 — Action Admissibility Filter

- **Inputs:** `Candidates[K]`, `ConstraintSet`.
- **Outputs:** `Admissible ⊆ Candidates` (may be empty), each annotated with the
  constraints it passed; rejected candidates annotated with the first violated
  constraint.
- **Algorithm:** **non-compensatory hard gate.** For each candidate, evaluate
  every hard constraint as a boolean predicate; a candidate is admissible iff it
  violates none. Order of evaluation is fixed so the *first* violated constraint
  is the deterministic rejection reason (feeds explainability). No scores here.
- **Complexity:** `O(K · C)`, bounded.
- **Failure modes:** all candidates rejected → empty admissible set (correct, not
  a failure) → `NO_SAFE_ACTION` at stage 8. A malformed candidate feature →
  treated as violation (fail-closed).

## Stage 8 — Action Selection

- **Inputs:** `Admissible`, soft-objective weights (fixed config).
- **Outputs:** exactly one `SelectedAction`, or `NO_SAFE_ACTION`.
- **Algorithm — deterministic, two-tier:**
  1. If `Admissible` is empty → `NO_SAFE_ACTION` (explicit; never rank an
     inadmissible candidate).
  2. Else compute the soft objective (energy/distance/time/comfort, a fixed
     weighted sum on already-admissible actions) and pick the argmin, with a
     **total tie-break**: soft-cost → larger safety margin → lower index. The
     tie-break is total, so the result is unique and replayable.
- **Complexity:** `O(|Admissible|)`.
- **Failure modes:** empty set → `NO_SAFE_ACTION` → recovery. Ties are impossible
  to leave unresolved (total order). Soft weights cannot resurrect an unsafe
  action because unsafe actions never enter this stage (A1).

## Stage 9 — Execution Authorization

- **Inputs:** `SelectedAction`, current (re-read) world state, `snapshot_hash`,
  `constraint_set_hash`, clock.
- **Outputs:** `ExecutionGrant` (one-shot) or `DENY_COMMIT(reason)`.
- **Algorithm — commit-time gate:**
  1. *Re-validate state (TOCTOU):* re-read safety-critical state; recompute the
     admissibility of `SelectedAction` against the *current* obstacles/margins.
     If the world moved enough to make it inadmissible → `DENY_COMMIT`.
  2. *Bind:* grant carries `snapshot_hash`, `constraint_set_hash`, a single-use
     `nonce`, `issued_t`, `deadline_t`.
  3. *Sign:* integrity tag over the grant (reference: keyed hash; production:
     platform key custody).
- **Complexity:** `O(O + C)` for the re-check, bounded.
- **Failure modes:** stale plan (world moved) → `DENY_COMMIT` → re-enter at stage
  4/5; clock anomaly → `DENY_COMMIT`; this is where a plan computed on now-stale
  state is caught before actuation.

## Stage 10 — Execution

- **Inputs:** `ExecutionGrant`, actuator adapter.
- **Outputs:** actuator command issued **once**, plus `issued` confirmation.
- **Algorithm:** verify grant (signature, nonce unused, `now ≤ deadline_t`),
  mark nonce consumed in the durable at-most-once store, dispatch the command.
- **Complexity:** `O(1)`.
- **Failure modes:** grant expired / nonce reused / signature invalid →
  actuator-reject → recovery. Guarantees at-most-once actuation per decision
  (replay prevention).

## Stage 11 — Runtime Monitoring

- **Inputs:** `ExecutionGrant`, live telemetry, clock, confidence tuple.
- **Outputs:** `nominal` (advance to next tick) or `TRIP(monitor, reason)`.
- **Algorithm — fixed set of deterministic monitors, each a threshold/deadline
  predicate:** tick-deadline watchdog (WCET), intent-divergence (actual vs
  authorized trajectory beyond tolerance), margin collapse (confidence.margin_m
  < floor), predictor-state degradation (stage-5 escalation), comms/actuator
  liveness. Each monitor is independent and bounded.
- **Complexity:** `O(#monitors)`, constant.
- **Failure modes:** any monitor trips → recovery with the tripping monitor as
  the dispositive reason. Monitors are the runtime half of the safety argument
  (stage 7 is decision-time; stage 11 is execution-time).

## Stage 12 — Recovery / Failure State Machine

- **Inputs:** any refusal (`REJECT_MISSION`, `FAIL_PLAN`, `STALE_WORLD`,
  `ABSTAIN`, `NO_SAFE_ACTION`, `DENY_COMMIT`, actuator-reject, `TRIP`).
- **Outputs:** a defined safe posture + a re-entry point.
- **Algorithm:** deterministic failure state machine (full spec in
  `ACP_FAILURE_STATE_MACHINE.md`): every refusal maps to exactly one transition
  into `{NOMINAL, DEGRADED, SAFE_HOLD, MINIMUM_RISK_MANEUVER, EMERGENCY_STOP,
  HANDOVER}`, with documented triggers and manual-reset gates for the terminal
  states.
- **Complexity:** `O(1)` transition lookup.
- **Failure modes:** the failure handler is total — there is no refusal without a
  defined transition. Unknown/aliased refusal → most-restrictive posture
  (fail-closed).

---

## Complexity summary (per tick)

Total per-tick cost is `O(K·H + K·C + M·H + O)` with **every factor a fixed,
validated bound**, so the tick cost has a static worst case — the precondition
for WCET budgeting (A5) and predictable runtime. No stage's cost depends on
unvalidated external input.

## Determinism ledger

| stage | any randomness? | how made deterministic |
|---|---|---|
| 2 Task Planner | method selection | lexicographic, fixed library |
| 5 Predictor Reliability | none | threshold state machine, no softmax |
| 6 Candidate Generation | sampling | fixed primitive set / low-discrepancy, seeded |
| 8 Action Selection | tie-breaks | total order (cost → margin → index) |
| all | time | injected monotonic clock, never ambient |
