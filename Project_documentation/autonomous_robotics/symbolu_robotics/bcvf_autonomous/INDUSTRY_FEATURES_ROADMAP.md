# Industry-features roadmap — research-tier

**Status:** roadmap document (no implementation). Items mature
into design docs (with their own ship-when-ready criteria) before
becoming deliverables. This doc lands as the load-bearing
"what's next from a deal-unlock perspective" artifact a buyer
reads alongside the v0.7 brief.

## §1 Why this exists

Post-v0.7 / 0.4.0 the BCVF Autonomous module shipped:

* The **kernel** (Lemma-1-grounded, characterization-validated).
* The **certification grid** (1560 cells × Wilson 95% CI floor 0.90).
* The **runtime monitoring** stack (`StreamingFleetMonitor` +
  `AlertRule`, plus the post-hoc fleet harness + auditor-facing
  CSV / Markdown reports).
* The **safety-case scaffold** (SOTIF / ISO 26262 traceability
  matrix — 12 clauses, 28 indexed artifacts, machine-checked
  snapshot).
* The **API stability commitment** (38-symbol `STABLE_API` +
  20-symbol `PROVISIONAL_API` + deprecation policy).
* The **cybersecurity scope-boundary** (8th characterization
  family + UN ECE R155 §7.3.4 mitigation registry).
* The **multi-modal predictor adapter** (lane-frame → SE(2) lift
  with empirical Lemma-1 carry-through on curved lanes).

What's missing — the gap between "interesting research stack" and
"production safety-critical software a Tier 1 ships" — is
characterised in §2-§8 below. §9 ranks the items by deal-unlock
value; §10 documents the maturation path from roadmap → design doc
→ implementation.

## §2 Real-time / determinism gaps

The kernel is fast in the average case (~3.7 µs / tick at M=3
single-modal) but production AV stacks require **hard real-time
guarantees**, not just fast averages:

* **`p999` latency bound under sustained load.** A 99.9th-percentile
  budget that an integrator can put into an AUTOSAR / DDS deadline.
  Current tests assert `p99 < 5 ms`; an RT system needs p999 + a
  documented worst-case-execution-time.
* **No-allocation hot path.** A real-time loop can't allocate
  arrays per tick (heap alloc → potential GC pause → blown
  deadline). Pre-allocated working buffers + in-place ops + a
  `realtime_mode=True` flag that asserts no allocation under load.
* **Determinism under concurrency.** If two threads ever touch the
  kernel simultaneously, what happens? Currently undocumented; an
  AUTOSAR Adaptive integrator needs an explicit thread-safety
  contract.

**Gap-fill artifact:** a `RealTimeBudget` extension to `BCVFConfig`
that pre-allocates buffers, exposes worst-case-execution-time, and
asserts p999 / p9999 latency under a synthetic 10⁶-tick load test
with held memory.

## §3 ROS 2 / DDS / SBOM integration contracts

Every Tier 1 / OEM / robotics customer's first three questions
look the same:

1. *Does it speak ROS 2?*
2. *What's the DDS QoS profile?*
3. *Where's the SBOM?*

The current `integrations/` module has the argmin-selector adapter
but not yet the ROS 2 / DDS surface. Required additions:

* **Typed ROS 2 message contracts** —
  `bcvf_msgs/PredictorTrajectory.msg`,
  `bcvf_msgs/ConsensusOutput.msg`, plus a `BCVFNode` that
  subscribes to `(M, predictor)` topics and publishes consensus +
  per-predictor attribution. Rate-limited, deadline-aware, with
  documented latency budget vs `RealTimeBudget` (§2).
* **DDS QoS profile** documented as the
  `RELIABLE / VOLATILE / 10ms / 100ms` quad (reliability /
  durability / deadline / liveliness) an integrator copies into
  their config.
* **SBOM (Software Bill of Materials)** in CycloneDX JSON format,
  enumerating every dependency + version + license. SOTIF /
  ISO 26262 packages and most procurement processes require this.

## §4 Functional-safety state machine (ASIL decomposition)

ISO 26262 doesn't just want unit tests — it wants an **executable
safety state machine** with documented transitions and recovery
actions. The current code has a kernel + an arbitration layer but
no behavioural contract that composes them into a *safety
component*. Sketch:

| State | Description | Trigger from prior state | Recovery |
|---|---|---|---|
| `NORMAL` | Every predictor agrees, BCVF quiet, planner gets full-resolution consensus. | (initial) | (none — terminal-good) |
| `DEGRADED` | One predictor flagged near-veto, BCVF firing intermittently. Planner reduces speed envelope. | Per-predictor near-veto count crosses threshold over rolling window | Sustained `NORMAL` for ≥ T_recovery seconds |
| `FAULT` | BCVF fires sustained, exclusion logic triggered. Planner enters minimum-risk maneuver (pull over). | At least one predictor excluded; cannot return to `DEGRADED` without re-inclusion | Manual reset + diagnostic clear |
| `FAILSAFE` | Multiple predictors excluded, kernel unable to form consensus. Planner enters emergency-stop. | ≥ 2 predictors excluded simultaneously | Manual reset + diagnostic clear |

Each transition is **testable and pinned**. ASIL decomposition: the
`NORMAL → DEGRADED` transition is ASIL-B (warning, not safety-
critical); `DEGRADED → FAULT` and `FAULT → FAILSAFE` are ASIL-D
(safety-critical actions). The state machine itself becomes the
SOTIF clause-9 (V&V) artifact — every named hazard input maps to
a named state path.

**This is the single biggest deal-unlock for automotive.** Most
safety teams will not engage on the technical details until they
see a documented state machine.

## §5 Replay / record-and-replay framework

When a fielded vehicle has an incident, the recall investigator
needs **bit-identical replay** of what the kernel saw + did. The
current capability:

* `TrustShapedEpisodeRecord` captures per-tick *output* state. ✓
* But not the per-tick *inputs* — the `(M, H, 3)` predictor tensor
  and the `BCVFConfig` that produced it. ✗

A `ReplayBundle` artifact would record `(config, inputs_per_tick,
output_per_tick)`; `replay_episode(bundle) → TrustShapedEpisodeRecord`
reconstructs the episode bit-exact. The investigator runs the
bundle through the current code and verifies the output matches
what the vehicle reported at incident time. **This is what closes
a recall investigation** — without it, the investigator has only
the output state and must guess at the inputs.

## §6 Calibration parameter management

Every predictor has tuning parameters — sensor noise floor, gate
threshold per scenario, lever arm, Huber `δ`. Production stacks
need:

* **Versioned calibration sets.** Each set has a hash, signed,
  validated against the kernel version (mismatched calibration ↔
  kernel pair refuses to load).
* **Calibration-drift detection.** Over a fleet, are the empirical
  noise floors (from the streaming monitor's per-predictor
  exclusion rate, near-veto rate, etc.) drifting from the
  calibration values? When the drift crosses a threshold, an
  `AlertRule` fires.
* **Per-vehicle / per-region overrides.** A vehicle in Phoenix has
  different sensor characteristics than one in Helsinki —
  calibration set differs without recompile.

Composes cleanly with the existing fleet harness; the streaming
monitor's near-veto + V2-state-flip rosters are already the
drift-detection inputs.

## §7 Sensor attestation / data provenance

UN ECE R155 §7.3.4 asks for sensor attestation — proof the sensor
stream came from the registered hardware. The
`adversarial_consistent_bias` family characterised the kernel-
layer scope-boundary (Lemma-1 trapdoor), but the attestation layer
itself is currently out-of-scope. Adding:

* **Predictor-boundary signature verification.** Each predictor's
  output carries a HMAC over the sensor's raw output + a hardware
  key. Spoofed predictors fail the signature.
* **Provenance metadata** flowing through to
  `TrustShapedEpisodeRecord` so a recall investigator can verify
  which sensor stack version produced each tick.

This is where the cybersecurity adversarial-family scope-boundary
becomes a real deployment-side mitigation, not just a documented
limit. Defence in depth at the layer the kernel can't reach on its
own.

## §8 Domain-specific predictors

The current four predictors (IMU, LiDAR, VO, GNSS) cover the
academic baseline. Production stacks are deeper:

* **HD-map predictor** — real implementation of the lane-frame
  predictor the multi-modal scaffold supports. Validates the
  multi-modal `MULTI_MODAL_PREDICTORS_DESIGN.md` §6 ship-when-ready
  criterion #1 (a deployment partner exercises lane-frame
  predictors in production).
* **Learned predictor** (CoverNet / Trajectron++ / in-house LSTM)
  — the §6.2 pilot plan estimates 3–4 weeks per predictor.
* **V2V / V2X predictor** — vehicles broadcasting their planned
  trajectories. Different failure modes (network drop, falsified
  messages) that interact with the cybersecurity surface.
* **Pedestrian / VRU predictor** — separate from ego prediction;
  adds a second BCVF instance arbitrating over VRU-trajectory
  predictors.

Adding *one* (HD-map or learned) is enough to validate the
multi-modal scaffold against a real predictor stack.

## §9 Ranking by deal-unlock value

| Rank | Feature | What it unlocks | Est. effort |
|---|---|---|---|
| **1** | ~~Functional-safety state machine (§4)~~ — design-doc + thin-shim implementation landed post-v0.7; see [`SAFETY_STATE_MACHINE_DESIGN.md`](SAFETY_STATE_MACHINE_DESIGN.md). Surface is `PROVISIONAL_API`; STABLE_API graduation gated on the three §9 ship-when-ready criteria (three deployment partners, characterization-grid `state_transition_consistency` family, external auditor review of the ASIL table). | The single biggest gate for automotive engagement. Without it, most safety teams won't read the technical doc. | ~~2–3 weeks~~ delivered |
| **2** | ~~ROS 2 node + message contracts + DDS QoS profile (§3)~~ — design-doc + thin-shim implementation landed post-v0.7.x; see [`ROS2_DDS_SBOM_DESIGN.md`](ROS2_DDS_SBOM_DESIGN.md). `BCVFNode` (framework-agnostic), `PredictorTrajectory.msg` + `ConsensusOutput.msg` schemas, `DDS_QOS_PROFILE` constant (RELIABLE / VOLATILE / 10 ms / 100 ms), and CycloneDX 1.5 SBOM at `safety_case/SBOM.cdx.json` all in `PROVISIONAL_API`; STABLE_API graduation gated on the five §9 ship-when-ready criteria (one deployment partner running BCVFNode in production for one quarter, one deployment partner accepting the SBOM into procurement, RTI Connext + FastDDS interop, colcon-build artifacts under humble + jazzy, external auditor SBOM validation). | Three first-call questions answered with code. Drone / industrial / mobile-robot partners need this faster than automotive. | ~~1–2 weeks~~ delivered |
| **3** | ~~Replay / record-and-replay framework (§5)~~ — design-doc + thin-shim implementation landed post-v0.7.x; see [`REPLAY_FRAMEWORK_DESIGN.md`](REPLAY_FRAMEWORK_DESIGN.md). `ReplayBundle` ties (RunConfig, recorded TrustShapedEpisodeRecord, package version, episode metadata) into a JSON artifact; `replay_bundle(bundle, runner_factory)` runs the bundle's config through the current code and surfaces any divergence with field-level + tick-level localisation. All ten new symbols in `PROVISIONAL_API`; STABLE_API graduation gated on the five §9 ship-when-ready criteria (deployment-partner usage one quarter, real-recall bit-identity replay, Class-A divergence detection across a kernel change, signed bundle integrity, external auditor sign-off on bundle JSON shape). | The recall investigator's tool. Composes cleanly with the existing post-hoc fleet harness. | ~~1 week~~ delivered |
| **4** | ~~Real-time / no-allocation hot path + p999 budget (§2)~~ — design-doc + thin-shim implementation landed post-v0.7.x; see [`REAL_TIME_BUDGET_DESIGN.md`](REAL_TIME_BUDGET_DESIGN.md). Typed `RealTimeBudget` contract (target_hz + per-tier ms thresholds + sample-count gates) + `LatencyMonitor` per-tick observer with mutually-exclusive tier counters + bounded over-budget audit trail + percentile-availability discipline (p999/p9999 None below sample-count thresholds). All seven new symbols in `PROVISIONAL_API`; STABLE_API graduation gated on the five §9 ship-when-ready criteria (AUTOSAR-class deployment partner one quarter, real 10⁶-tick load test, C++-port equivalence within 2×, external auditor sign-off, configurable persistence layer). | Required for AUTOSAR Adaptive integration. Probably the AUTOSAR partner's first technical objection. | ~~1–2 weeks~~ delivered |
| **5** | HD-map predictor (validates multi-modal — §8) | Turns the multi-modal scaffold from "design" to "we ran it" against a real predictor stack. | 3–4 weeks |
| **6** | ~~Calibration parameter management + drift detection (§6)~~ — design-doc + thin-shim implementation landed post-v0.7.x; see [`CALIBRATION_DESIGN.md`](CALIBRATION_DESIGN.md). Versioned, hash-identified, kernel-version-validated `CalibrationSet` bundles 8 typed configs (BCVFConfig + ConsumerV2Config + BicycleConfig + RealTimeBudget + DDSQoSProfile + SafetyStateMachineConfig + per-predictor FailureConfig + expected_metrics ranges); `CalibrationDriftDetector` walks the calibration's expected ranges against a live `WindowedFleetSummary` and emits typed `CalibrationDriftAlert` records. All nine new symbols in `PROVISIONAL_API`; STABLE_API graduation gated on the five §9 ship-when-ready criteria (deployment partner one quarter on a fleet ≥ 10 vehicles, real fleet drift detection across a known mismatch, signed bundle field, external auditor sign-off, expected_metrics schema stabilised across ≥ 3 deployment partners). | Required for any fleet > 10 vehicles. Streamlines with existing fleet harness. | ~~2 weeks~~ delivered |
| **7** | SBOM + license compliance (§3) | Procurement gate, not engineering. | 2 days |
| **8** | ~~Sensor attestation interface (§7)~~ — design-doc + thin-shim implementation landed post-v0.7.x; see [`SENSOR_ATTESTATION_DESIGN.md`](SENSOR_ATTESTATION_DESIGN.md). Stdlib-only HMAC-SHA256 attestation surface — `SensorAttestation` typed record + `SensorAttestationPolicy` per-predictor verification policy + `SensorAttestationVerifier` running seven §4 checks per attestation (policy lookup, policy-enabled, firmware allowlist, freshness, future-dating, replay, data binding, HMAC signature with constant-time compare). Failed verifications union into the existing `is_excluded` mask alongside deadline + state-machine exclusions — closes SOTIF clause-8 Insufficiency #3 (Lemma-1 trapdoor) with the in-scope mitigation the safety case has been pointing at since v0.7. All ten new symbols in `PROVISIONAL_API`; STABLE_API graduation gated on the five §8 ship-when-ready criteria (deployment partner one quarter against HSM, real attestation-failure across firmware regression, asymmetric-extension subclass, external auditor sign-off for UN ECE R155 §7.3.4, replay-cache persistence layer). | Closes the UN ECE R155 cybersecurity loop the adversarial family opened. | ~~1 week~~ delivered |
| **9** | Learned / V2V / VRU predictors (§8) | Domain expansion. Each is a separate engagement. | 3–4 weeks each |

### §9.1 Recommendation — what to do next

If forced to pick one: **#1 (functional-safety state machine)**.
Reasoning:

* The bcvf_autonomous code today is a *runtime layer* — kernel +
  arbitration + diagnostics. What's missing is the *behavioural
  contract* the runtime composes into: the system as a whole, with
  named states + transitions + recovery actions, that an
  ISO 26262 safety case can argue against.
* Every other feature on §9's list is incremental coverage. The
  state machine is **architectural** — it turns "we have a
  kernel" into "we have a safety component."
* It composes cleanly with what's already shipped: streaming-
  monitor `AlertRule`s become state-transition triggers; the SOTIF
  traceability matrix gains a clause-26262-Part-3 (system safety
  concept) wiring; the characterization grid validates each
  state's must-be-quiet vs must-fire behaviour.

If forced to pick two: state machine + replay (§5). Replay is
independent, lower-effort, and answers the recall-investigator
question directly.

## §10 What this is NOT

* Not a feature list with commitments. Each item is a candidate
  the deployment-partner conversation may or may not promote to
  an implementation; estimates are estimates.
* Not a substitute for the brief's published roadmap. The brief
  states what the next twelve months look like at the company
  level; this doc is the technical roadmap inside the BCVF module.
* Not a re-enumeration of the existing surfaces. Items §2-§8 are
  *gaps*, deliberately distinct from what `STABLE_API` /
  `PROVISIONAL_API` already covers.
* Not a static document. The expected lifecycle: an item moves
  from this roadmap → its own design doc (with §-by-§ analysis +
  ship-when-ready criteria, like `HIERARCHICAL_BCVF_DESIGN.md` or
  `MULTI_MODAL_PREDICTORS_DESIGN.md`) → implementation. The
  roadmap row gets struck through with a pointer to the design doc
  on the way through.

## §11 Maturation path — roadmap → design doc → implementation

The pattern this session established:

1. **Roadmap row** in this doc — name + brief description + effort
   estimate + deal-unlock framing.
2. **Design doc** authored when the item is the next thing the
   deployment-partner conversation needs. Sections cover
   motivation, alternatives considered, API sketch (no
   implementation), Lemma-1 / safety-property carry-through
   analysis, ship-when-ready criteria, what's not in scope. Pinned
   by a doc-presence test (§-headers + non-promotion to
   `STABLE_API` / `PROVISIONAL_API` until the implementation
   ships).
3. **Implementation commit** lands the code + tests + safety-case
   wiring + (optionally) brief update if a published number
   changes. Old roadmap row gets struck through; the design doc
   stays as the architectural record.

Two design docs already follow this pattern:
`HIERARCHICAL_BCVF_DESIGN.md` (research-tier, no implementation
yet) and `MULTI_MODAL_PREDICTORS_DESIGN.md` (research → thin-shim
implementation in `predictors/state_space.py` +
`predictors/multi_modal.py`). The pattern is reusable for every
item §2-§8 promotes.

## §12 Test pin

`tests/test_industry_features_roadmap_doc.py` pins:

1. The doc ships at this path.
2. The nine ranking rows in §9 are present (deletion of a row
   without acknowledgement fails CI).
3. None of the §2-§8 names have leaked into `STABLE_API` /
   `PROVISIONAL_API` — roadmap items carry no integration
   commitment until a design-doc + implementation pair ships.

## §13 Implementation prompt — Item #1 (functional-safety state machine)

This appendix captures a self-contained prompt a fresh Claude
Code session can use to implement §9.1's recommended next pick
(the functional-safety state machine). The prompt is **embedded
in this doc** so the maturation path stays auditable: a future
reader can see exactly what implementation guidance the roadmap
generated, and a future contributor adding a new top-ranked item
can mirror the prompt structure.

### §13.1 Prompt (paste verbatim into a fresh Claude Code session)

```text
I'm working on the BCVF autonomous module in the rasaha/symbolu
repo. The active branch is claude/audit-bcvf-features-Iajos.
Total tests in default suite right now: 652 passing. v0.7 brief
AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md is the active doc.

INDUSTRY_FEATURES_ROADMAP.md §9 ranks the next industry features
by deal-unlock value. §9.1 names Item #1 — the functional-safety
state machine — as the recommended next pick. This prompt
implements that item.

IMPLEMENTATION TASK

Build a SafetyStateMachine module that composes the existing
runtime layer (kernel + arbitration + diagnostics) into a named
behavioural contract an ISO 26262 safety case can argue against.
Four states:

  NORMAL    — every predictor agrees, BCVF quiet, planner gets
              full-resolution consensus.
  DEGRADED  — one predictor flagged near-veto, BCVF firing
              intermittently. Planner reduces speed envelope.
  FAULT     — BCVF fires sustained, exclusion logic triggered.
              Planner enters minimum-risk maneuver (pull over).
  FAILSAFE  — multiple predictors excluded, kernel unable to
              form consensus. Planner enters emergency-stop.

ASIL DECOMPOSITION

  NORMAL → DEGRADED        ASIL-B  (warning, not safety-critical)
  DEGRADED → NORMAL        ASIL-B
  DEGRADED → FAULT         ASIL-D  (safety-critical action)
  FAULT → FAILSAFE         ASIL-D
  FAULT → DEGRADED         ASIL-B  (manual-reset path)
  FAILSAFE → FAULT         ASIL-B  (manual-reset path)

Direct-jump transitions (NORMAL → FAULT, NORMAL → FAILSAFE) are
DISALLOWED — the machine must walk through DEGRADED. The state
machine itself enforces this; an attempted illegal transition
raises SafetyStateMachineError.

DESIGN DOC FIRST

Following the pattern from HIERARCHICAL_BCVF_DESIGN.md and
MULTI_MODAL_PREDICTORS_DESIGN.md, write the design doc BEFORE
the implementation. The doc lives at
  symbolu_robotics/bcvf_autonomous/SAFETY_STATE_MACHINE_DESIGN.md
and covers:
  §1 Why this exists (kernel = runtime layer; state machine =
     behavioural contract; the architectural piece that turns
     "we have a kernel" into "we have a safety component").
  §2 Four states + state-transition diagram.
  §3 Trigger conditions per transition — drawn from the existing
     TrustShapedEpisodeRecord fields (per_step_is_excluded,
     per_step_consec_suspect, per_step_bcvf_total) over a
     configurable rolling window.
  §4 Recovery conditions — sustained-NORMAL dwell, manual reset,
     diagnostic clear.
  §5 ASIL decomposition (table + reasoning per row).
  §6 Direct-jump prohibition (NORMAL cannot jump to FAULT or
     FAILSAFE; machine raises on attempt).
  §7 Composition with existing surfaces:
     * StreamingFleetMonitor's AlertRules become state-transition
       triggers.
     * SOTIF traceability matrix gains clause-26262-Part-3 (system
       safety concept) wiring with the state machine as evidence.
     * Characterization grid validates each state's must-be-quiet
       vs must-fire behaviour (per-state cells).
  §8 What this is NOT (not a planner replacement; not a generic
     state-machine library; not a substitute for the deployment
     partner's safety case).
  §9 Ship-when-ready criteria for STABLE_API graduation:
     1. Three deployment partners exercise the state machine in
        production for one quarter without a state-graph change
        request.
     2. The characterization grid extends with a state_transition
        consistency family asserting each transition fires under
        the documented trigger condition + does NOT fire under
        adjacent conditions.
     3. ASIL decomposition is reviewed by a TÜV / external
        auditor (out-of-sandbox manual gate; pinned in §9 as the
        promotion checkpoint).
  §10 API sketch (no implementation in the doc, just the type
      signatures the implementation will satisfy).

IMPLEMENTATION

After the design doc, ship:

  symbolu_robotics/bcvf_autonomous/safety_state/
    DESIGN.md            — pointer to top-level
                           SAFETY_STATE_MACHINE_DESIGN.md
    __init__.py          — public exports
    state.py             — SafetyState enum + transition table
    machine.py           — SafetyStateMachine class with
                           .observe() / .state / .transition_log
    triggers.py          — TriggerCondition primitives that read
                           TrustShapedEpisodeRecord
    errors.py            — SafetyStateMachineError +
                           IllegalTransitionError

Public API surface (provisional):
  SafetyState (enum: NORMAL, DEGRADED, FAULT, FAILSAFE)
  SafetyStateMachine(config) — observe(record, classification=None)
    → SafetyState
  StateTransition (frozen dataclass: from_state, to_state, trigger,
    asil)
  TriggerCondition (Protocol — evaluates against a rolling window)
  StateTransitionLog (every transition timestamped + cause-named)
  SafetyStateMachineConfig (rolling window length, dwell times,
    per-transition thresholds — all exposed for calibration)

PINNING TESTS (target ~25-30, in
tests/test_safety_state_machine.py)

  * 4-state enum + transition table machine-checked against the
    design doc's §2 table.
  * Direct-jump prohibition: every (s_from, s_to) pair NOT in
    the documented transition table raises IllegalTransitionError.
  * NORMAL → DEGRADED fires when the trigger condition crosses
    threshold; doesn't fire below.
  * DEGRADED → FAULT requires exclusion + sustained BCVF activity;
    doesn't fire on a single-tick spike.
  * FAULT → FAILSAFE requires ≥ 2 excluded predictors.
  * Recovery: sustained NORMAL for T_recovery seconds returns
    DEGRADED → NORMAL.
  * Manual reset: FAULT → DEGRADED and FAILSAFE → FAULT only via
    explicit reset_with_diagnostic_clear() call.
  * StateTransitionLog records every transition with timestamp +
    triggering condition name.
  * Composition with StreamingFleetMonitor: an AlertRule on
    DEGRADED-rate fires correctly when the state machine spends
    > X% of ticks in DEGRADED.
  * Composition with SOTIF clause 8 (functional insufficiencies):
    each ASIL-D transition is referenced as evidence in the
    traceability matrix.
  * Characterization grid: a new state_transition_consistency
    family with the per-transition trigger / non-trigger cells.

SAFETY-CASE INTEGRATION

  * safety_case/traceability.py: clause 8 (functional
    insufficiencies + mitigations) gains the state machine as
    evidence for the insufficiency-handling layer. New evidence
    artifact _SAFETY_STATE_MACHINE.
  * SOTIF_TRACEABILITY.md regenerated (28 → 30 indexed artifacts).
  * Clause 9 (V&V) notes acknowledge the state machine as the
    behavioural-contract layer the per-cell threshold gates
    compose into.

API STABILITY

All new symbols enter PROVISIONAL_API per the §9 ship-when-ready
criteria. _api.py PROVISIONAL_API count goes 20 → ~26. The count
lock in test_api_stability.py (EXPECTED_PROVISIONAL_COUNT) gets
bumped explicitly so the PR review has to acknowledge it.

INDUSTRY_FEATURES_ROADMAP.md UPDATE

§9 row #1 (Functional-safety state machine) gets struck through
with a pointer to SAFETY_STATE_MACHINE_DESIGN.md per the
maturation path documented in §11. The non-promotion gate test
in test_industry_features_roadmap_doc.py needs the
SafetyStateMachine token REMOVED from _ROADMAP_TOKENS since it's
now a provisional surface (alternatively, leave it and add a
narrow exception — your call, but document the reasoning).

BRIEF UPDATE (only if a published number changes)

Per the v0.7 / 0.4.0 maturation discipline: the brief stays at
v0.7 unless a published number moves. Test count goes 652 → ~680;
§1 capability list gains the state-machine bullet; the
architecture-summary table gets a new row; the footer narrative
blurb names SAFETY_STATE_MACHINE_DESIGN.md as the load-bearing
new artifact. No headline number (BCVF 0.000 false-attribution,
p=0.0312, win rate 1.000, etc.) moves.

CONSTRAINT

CPU-only sandbox. No internet, no nuscenes-devkit, no ROS, no
GPU. All work must be doable with what's already in the repo +
NumPy + stdlib.

WORKFLOW

1. Audit the existing surfaces the state machine composes with —
   re-read TrustShapedEpisodeRecord, StreamingFleetMonitor,
   AlertRule, the SOTIF clause 8 evidence list. Confirm the API
   surfaces I'm proposing actually compose cleanly; flag any
   mismatch.
2. Write SAFETY_STATE_MACHINE_DESIGN.md first. Pin the doc with
   section-header tests before writing the implementation.
3. Implement state.py / machine.py / triggers.py / errors.py.
4. Add tests/test_safety_state_machine.py with the contracts
   above.
5. Wire the safety_case clause-8 evidence + regenerate snapshot.
6. Update PROVISIONAL_API + bump count lock.
7. Strike through INDUSTRY_FEATURES_ROADMAP.md §9 row #1.
8. Run full bcvf_autonomous suite (skip slow + perf benchmarks
   per existing convention); confirm 652 → ~680 passing.
9. Update the brief.
10. Commit each logical piece as a self-contained commit
    (design doc; implementation + tests; safety-case integration;
    API stability bump; roadmap strike-through; brief).
11. Push to claude/audit-bcvf-features-Iajos.

After implementation lands, do an INDEPENDENT critical audit pass
on the new code (same discipline as the prior audit-fix commits
in this session — find at least one real bug or coverage gap and
pin it). Real safety-component code shipped without an audit pass
is not real safety-component code.
```

### §13.2 Why the prompt lives in this doc

Three reasons the prompt is captured in-tree rather than emailed
or pasted into a chat:

1. **Auditability.** A future reviewer asking *"how did the
   safety state machine get scoped?"* finds the original prompt
   in this file alongside the §4 gap analysis it operationalises.
2. **Reuse.** When §9 row #2 (ROS 2 / DDS / SBOM) becomes the
   next pick, the contributor copies the §13 prompt structure —
   audit existing surfaces → design doc first → ship-when-ready
   criteria → safety-case integration → API stability bump →
   roadmap strike-through → brief → audit pass — and adapts the
   content. The discipline is the artifact, not the specific
   prompt text.
3. **Drift detection.** The prompt names specific surfaces
   (`TrustShapedEpisodeRecord`, `StreamingFleetMonitor`,
   `AlertRule`, SOTIF clause 8). If a future refactor renames any
   of those, the implementer's first-step audit catches the drift
   before writing code against stale references.

### §13.3 Prompt template for future top-ranked items

When §9 row N is promoted to "next pick," its implementation
prompt should mirror §13.1's structure:

  * **Context** — branch + commit + test-passing count + brief
    version. Self-contained so a fresh session has no implicit
    state.
  * **Implementation task** — what's being built and why this
    item now (deal-unlock framing from §9).
  * **Design doc first** — the maturation path from §11 says
    design doc precedes implementation. The prompt names the
    target file path + required §-headers.
  * **Implementation** — module structure + public API surface
    sketch (provisional names in `PROVISIONAL_API`).
  * **Pinning tests** — the regression locks the implementation
    must ship with.
  * **Safety-case integration** — which SOTIF / ISO 26262 clause
    gains evidence; SOTIF_TRACEABILITY.md snapshot regeneration.
  * **API stability** — PROVISIONAL_API entries + count-lock bump.
  * **Roadmap update** — strike through the §9 row + maintain
    the non-promotion gate test (or remove the token from
    `_ROADMAP_TOKENS` per §13.1's note).
  * **Brief update** — only if a published number moves.
  * **Constraint** — sandbox limits.
  * **Workflow** — numbered steps the implementer follows.
  * **Audit pass** — the explicit discipline of finding at least
    one real bug or coverage gap on the new code, even when CI
    passes.

Future contributors adding a new top-ranked item to §9 should
add a sibling §13.N "Implementation prompt — Item #N" appendix
following the same outline. The non-promotion gate in §12 +
`test_industry_features_roadmap_doc.py` keeps the discipline
honest: a token added to the prompt without an actual design-doc
+ implementation pair fails the gate.
