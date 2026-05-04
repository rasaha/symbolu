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
| **1** | Functional-safety state machine (§4) | The single biggest gate for automotive engagement. Without it, most safety teams won't read the technical doc. | 2–3 weeks |
| **2** | ROS 2 node + message contracts + DDS QoS profile (§3) | Three first-call questions answered with code. Drone / industrial / mobile-robot partners need this faster than automotive. | 1–2 weeks |
| **3** | Replay / record-and-replay framework (§5) | The recall investigator's tool. Composes cleanly with the existing post-hoc fleet harness. | 1 week |
| **4** | Real-time / no-allocation hot path + p999 budget (§2) | Required for AUTOSAR Adaptive integration. Probably the AUTOSAR partner's first technical objection. | 1–2 weeks |
| **5** | HD-map predictor (validates multi-modal — §8) | Turns the multi-modal scaffold from "design" to "we ran it" against a real predictor stack. | 3–4 weeks |
| **6** | Calibration parameter management + drift detection (§6) | Required for any fleet > 10 vehicles. Streamlines with existing fleet harness. | 2 weeks |
| **7** | SBOM + license compliance (§3) | Procurement gate, not engineering. | 2 days |
| **8** | Sensor attestation interface (§7) | Closes the UN ECE R155 cybersecurity loop the adversarial family opened. | 1 week |
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
