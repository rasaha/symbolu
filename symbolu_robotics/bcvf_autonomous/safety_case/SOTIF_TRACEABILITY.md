# SOTIF (ISO 21448) + ISO 26262 Part 6 — BCVF traceability

Generated from ``symbolu_robotics.bcvf_autonomous.safety_case.build_traceability_matrix``.
Do not hand-edit this file — update the matrix in ``traceability.py`` and the doc-render test will refresh this snapshot.

**Scope.** This is the regulator-facing index from BCVF artifacts to the standard clauses they ground. It is *not* a deployment-ready safety case — that document is authored by the deployment partner against their specific operational design domain. The matrix exists so a buyer's safety team can begin a clause-by-clause walk-through on day one of a diligence engagement, instead of waiting for a separate safety-case workstream.

## Index

* ISO 21448 (SOTIF)
  * Clause **5** — Functional and system specification
  * Clause **6** — Hazard identification and risk evaluation (HARA)
  * Clause **7** — Identification and evaluation of triggering conditions
  * Clause **8** — Identification of functional insufficiencies + mitigations
  * Clause **9** — Verification and validation of SOTIF
  * Clause **10** — Methodology — operational design and field monitoring
  * Clause **12** — Process — release to market + configuration management
* ISO 26262 Part 6 (Software)
  * Clause **Part 6 §7** — Specification of software safety requirements
  * Clause **Part 6 §8** — Software architectural design
  * Clause **Part 6 §9** — Software unit design and implementation
  * Clause **Part 6 §9.4.4** — Software unit verification methods
  * Clause **Part 6 §10** — Software integration and integration verification
  * Clause **Part 6 §11** — Verification of software safety requirements

## ISO 21448 (SOTIF)

### Clause 5 — Functional and system specification

**Requirement.** Define the function under analysis, its operational design domain, and the boundary at which inputs / outputs are exchanged with the rest of the system.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.core::compute_bcvf_cost` — BCVF cost kernel (SE(2) body-frame disagreement, second-order, gate × pseudo-Huber)
* `symbolu_robotics.bcvf_autonomous.core::BCVFConfig` — Kernel configuration dataclass — gate threshold, β, Huber δ, lever arm, cost order
* `symbolu_robotics.bcvf_autonomous.manifold::body_frame_error_trajectory` — SE(2) body-frame error primitive — the kernel's signal definition
* `symbolu_robotics.bcvf_autonomous.predictors.base::BicycleConfig` — Vehicle dynamics + predictor interface — the system boundary the kernel arbitrates over
* `symbolu_robotics.bcvf_autonomous.predictors::MultiModalPredictor` — Predictor wrapper for non-SE(2) state spaces (lane-frame, future map-frame). Pairs the native trajectory with the geometry needed to lift it to SE(2) at the kernel boundary; preserves Lemma 1 invariance via the body-frame primitive transforming correctly with lane curvature (see MULTI_MODAL_PREDICTORS_DESIGN.md §4)
* `symbolu_robotics.bcvf_autonomous.predictors::LaneAnchor` — Lane geometry primitive — polyline of SE(2) waypoints + cumulative arc lengths; the metadata a lane-frame predictor pairs with to round-trip through SE(2)
* `symbolu_robotics.bcvf_ros2::BCVFNodeBehaviour` — Framework-agnostic ROS 2 node behaviour — wraps the BCVF trust-shaping bridge with rate-limited publication, per-predictor deadline tracking + stale-on-resume protection, and SafetyStateMachine composition. See ROS2_DDS_SBOM_DESIGN.md §3.3 + §5 for the integration contract; the rclpy-bound subclass lands gated on §6.4 colcon-build execution.
* `symbolu_robotics.bcvf_ros2.qos::DDS_QOS_PROFILE` — Documented DDS QoS profile (RELIABLE / VOLATILE / 10 ms deadline / 100 ms liveliness / KEEP_LAST / depth 1) — the `RELIABLE/VOLATILE/10ms/100ms` quad an integrator copies into their RTI Connext or FastDDS config. See ROS2_DDS_SBOM_DESIGN.md §4 for the per-knob rationale.

**Notes.** BCVF is specified as an arbitration function over M predictor SE(2) trajectories on a fixed horizon H. Inputs: ``(M, H, 3)`` predictor tensor. Outputs: ``(H, 3)`` consensus + ``(M,)`` per-predictor attribution. The kernel is dimensionally explicit (weight matrix in m / rad), deterministic, and fp64-stable — see DESIGN.md §1 + §2. **Multi-modal extension**: predictors with non-SE(2) native output (lane-frame ``(s, d, psi)``) lift to SE(2) at the kernel boundary via ``MultiModalPredictor`` + ``LaneAnchor``; Lemma 1 invariance carries through the lift (proven empirically on straight + curved lanes, pinned by the multi-modal test suite). See ``MULTI_MODAL_PREDICTORS_DESIGN.md`` for the carry-through analysis. **ROS 2 / DDS integration boundary**: the system boundary the kernel exchanges messages across is the ROS 2 ``/bcvf/predictor/*/trajectory`` (input) and ``/bcvf/consensus`` (output) topic pair — typed by ``PredictorTrajectory.msg`` + ``ConsensusOutput.msg`` (see ``bcvf_ros2/msg/``). The DDS QoS profile (RELIABLE / VOLATILE / 10 ms deadline / 100 ms liveliness, ``DDS_QOS_PROFILE`` constant) documents the bus-level contract per ``ROS2_DDS_SBOM_DESIGN.md`` §4. ``BCVFNodeBehaviour`` is the framework-agnostic core (testable without rclpy); the rclpy-bound subclass lands gated on the §6.4 colcon-build execution work.

### Clause 6 — Hazard identification and risk evaluation (HARA)

**Requirement.** Enumerate the named classes of inputs whose mishandling could lead to hazardous behaviour, and assess the associated risk.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.characterization.traces::generate_trace` — Eight-family synthetic SE(2) trace generator — the named hazards (baseline, constant_bias, linear_drift, accelerating, noise_floor, outlier, sensor_dropout) plus the cybersecurity-tier adversarial_consistent_bias family
* `symbolu_robotics.bcvf_autonomous.characterization::ADVERSARIAL_FAMILIES` — Cybersecurity-tier polarity bucket — names the attack-class families the kernel cannot fully detect (stealth-bias spoofs); pairs with the §3.5 DESIGN.md scope-boundary documentation
* `symbolu_robotics.bcvf_autonomous.characterization::run_primary_grid` — Characterization DESIGN.md §4 (per-family thresholds) + §6.1 (Wilson CI floor) — the readable safety contract

**Notes.** The eight characterization families ARE the named hazard inputs at the predictor-arbitration interface: ``baseline``, ``constant_bias``, ``linear_drift``, ``accelerating``, ``noise_floor``, ``outlier``, ``sensor_dropout`` (honest-failure modes, polarity = nominal or failure) plus ``adversarial_consistent_bias`` (UN ECE R155 cybersecurity-tier attack class, polarity = adversarial). Each carries an explicit polarity and a formal generator in ``characterization/traces.py`` so a HARA reviewer can re-execute and inspect every input class. The cybersecurity scope-boundary is documented in ``characterization/DESIGN.md`` §3.5.

### Clause 7 — Identification and evaluation of triggering conditions

**Requirement.** Identify discrete triggering conditions for each named hazard and evaluate the system response across the magnitude range of interest.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::FAMILY_MAGNITUDES` — Per-family magnitude grids — the discrete triggering-condition table the sweep scans
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::run_primary_grid` — 22 configs × 60 seeds = 1320-cell certification grid; drives the per-config Wilson-CI floor
* `symbolu_robotics.bcvf_autonomous.analysis.near_veto::find_near_vetoes` — Near-veto detector — flags ticks where a predictor approached but did not cross the exclusion threshold; the SOTIF triggering-condition near-miss surface

**Notes.** ``FAMILY_MAGNITUDES`` is the discrete triggering-condition table — e.g. ``accelerating`` is evaluated at ``accel_mag ∈ {0.1, 0.3, 0.5, 1.0}``. The primary grid evaluates every (family, magnitude) cell at 60 seeds and emits a per-cell pass / fail verdict with Wilson 95% CI lower bound. ``find_near_vetoes`` is the runtime triggering-condition near-miss surface for fielded data.

### Clause 8 — Identification of functional insufficiencies + mitigations

**Requirement.** Identify functional insufficiencies of the intended function (cases where it does not respond as required) and document mitigations.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.trust::ConsumerV2Config` — Schmitt-trigger consumer V2 — engage / disengage thresholds + dwell-time hysteresis (chatter-immunity argument)
* `symbolu_robotics.bcvf_autonomous.v2_chatter_sweep::run_v2_promotion_decision` — Paired V1-vs-V2 promotion-gate sweep — Wilson CI on chatter rate + exact one-sided McNemar on rescue preservation; documents the chatter-immunity claim
* `symbolu_robotics.bcvf_autonomous.characterization::ADVERSARIAL_FAMILIES` — Cybersecurity-tier polarity bucket — names the attack-class families the kernel cannot fully detect (stealth-bias spoofs); pairs with the §3.5 DESIGN.md scope-boundary documentation
* `symbolu_robotics.bcvf_autonomous.safety_state::SafetyStateMachine` — Functional-safety state machine — four-state behavioural contract (NORMAL / DEGRADED / FAULT / FAILSAFE) with documented per-transition triggers, ASIL decomposition (B for warnings + manual-resets, D for safety-critical escalations), direct-jump prohibition, and manual-reset audit trail. Composes the per-tick BCVF kernel + arbitration runtime into a system-level posture an ISO 26262 safety case can argue against; see SAFETY_STATE_MACHINE_DESIGN.md
* `symbolu_robotics.bcvf_autonomous.safety_state::LEGAL_TRANSITIONS` — Six-edge legal-transition table — the auditor-readable §5 ASIL decomposition rendered as a typed tuple of StateTransition rows; pinned by the test suite so a future contributor cannot quietly add an edge or change an ASIL classification without the PR review noticing

**Notes.** Insufficiency #1 — Lemma 1 invariance (intentional): the SECOND-order kernel does not fire on constant offset or linear drift. Documented as a desired specification property; the ablation grid confirms the invariance is exact (ZEROTH / FIRST orders fire, SECOND does not). Insufficiency #2 — per-tick chatter on borderline disagreements where V1 softmin can flip argmax across consecutive ticks. Mitigation: V2 Schmitt-trigger consumer (``ConsumerV2Config``) with engage / disengage thresholds + dwell-time hysteresis. The v0.6 V2 promotion-decision sweep documents the non-promotion finding and the Q2 recalibration scope. Insufficiency #3 — Lemma-1 trapdoor for cybersecurity: an attacker who spoofs a sensor with a stealth-tier constant-bias signature is invisible to the kernel by construction (the same Lemma-1 invariance that's a specification property in #1 is the attack surface). Documented mitigation is **out-of-scope of the kernel** and lives at the deployment-partner layer: cross-modal sensor attestation, cross-class redundancy, calibration drift monitoring (UN ECE R155 §7.3.4). The ``adversarial_consistent_bias`` family + DESIGN.md §3.5 make the boundary explicit so the safety-case narrative doesn't overclaim. **Insufficiency-handling layer** — the per-tick V2 chatter mitigation composes into the ``SafetyStateMachine`` four-state behavioural contract (NORMAL / DEGRADED / FAULT / FAILSAFE). The state machine is the system-level supervisor a safety case argues against: each transition is ASIL-decomposed (see ``LEGAL_TRANSITIONS`` for the six-edge table), direct jumps from NORMAL to FAULT / FAILSAFE are prohibited (the machine raises ``IllegalTransitionError``), and the FAULT / FAILSAFE states latch behind a manual-reset gate so a quiet kernel cannot auto-resolve a confirmed-failure posture. See ``SAFETY_STATE_MACHINE_DESIGN.md`` for the full design — ship-when-ready criteria for STABLE_API graduation are gated on three deployment partners, the characterization grid's ``state_transition_consistency`` cell family, and an external auditor review of the §5 ASIL table.

### Clause 9 — Verification and validation of SOTIF

**Requirement.** Verify and validate that the function's response to named hazards meets the stated acceptance criteria, with quantified statistical confidence.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::run_primary_grid` — 22 configs × 60 seeds = 1320-cell certification grid; drives the per-config Wilson-CI floor
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::summarize_grid` — Aggregator emitting per-config Wilson 95% CI low/high, min_ci_lower_bound, cells_below_certification_floor
* `symbolu_robotics.bcvf_autonomous.characterization.stats::wilson_ci` — Wilson score CI primitive (closed-form, no scipy) — the stated statistical bound's machinery
* `symbolu_robotics.bcvf_autonomous.baselines::run_shootout` — Apples-to-apples baseline shootout — BCVF vs EKF (Mahalanobis-rejection) vs Majority-Vote vs Anchor across the seven families
* `symbolu_robotics.bcvf_autonomous.pilot::run_pilot` — §6.2 paired A0 vs A3 pilot runner — sign test + Wilson CI + FleetSummary + Lemma-1 negative-control gate
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::_evaluate_thresholds` — Per-family acceptance thresholds — pass / fail rule table the sweep enforces (DESIGN.md §4)
* `symbolu_robotics.bcvf_autonomous.characterization::write_grid_markdown` — Markdown report writer for ``GridSummary`` — emits the regulator-facing certification report (headline gate, per-(family, magnitude) Wilson-CI table, per-family roll-up, failed-config list, methodology block)
* `symbolu_robotics.bcvf_autonomous.characterization::write_grid_csv` — CSV writer for ``GridSummary`` — one row per (family, magnitude) config with Wilson 95% CI low/high, pass count, and certification-floor verdict; RFC-4180 quoted for spreadsheet consumers

**Notes.** V&V is layered: (i) deterministic threshold gates per family (``_evaluate_thresholds``); (ii) per-config Wilson 95% CI lower bound floor of 0.90 across the 1320-cell grid (``CERTIFICATION_FLOOR``); (iii) apples-to-apples baseline shootout against EKF / Majority / Anchor; (iv) §6.2 paired A0 vs A3 pilot with one-sided sign test + Wilson CI on win rate. Three sabotage tests in the suite confirm V&V would fail on a broken kernel rather than silently passing. ``write_grid_markdown`` / ``write_grid_csv`` emit the certification report as a frozen audit artifact (headline gate, per-(family, magnitude) Wilson-CI table, methodology block) — what an auditor reads instead of a Python dataclass. **Behavioural-contract layer** — the per-cell threshold gates compose into the ``SafetyStateMachine`` four-state contract: a passing per-cell gate is a per-tick property, the state machine is the system-level posture those per-tick properties accumulate into. The grid's ``state_transition_consistency`` cell family (provisional, ship-when-ready criterion §9.2 of ``SAFETY_STATE_MACHINE_DESIGN.md``) extends V&V to each documented transition with must-fire + must-be-quiet pinning at adjacent thresholds.

### Clause 10 — Methodology — operational design and field monitoring

**Requirement.** Define the methodology for monitoring the system in the field and feeding observed triggering conditions back into hazard analysis.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.trust_diagnostics::TrustShapedEpisodeRecord` — Per-step trust diagnostic record — every tick's weights, BCVF cost, V2 state, near-veto incidence; the post-incident trace a recall investigator opens
* `symbolu_robotics.bcvf_autonomous.analysis::FleetSummary` — Fleet-scale aggregator over episode records — argmax-flips per step, near-vetoes, V2 state distribution, per-predictor exclusion incidence; the field-monitoring evidence pack
* `symbolu_robotics.bcvf_autonomous.analysis.near_veto::find_near_vetoes` — Near-veto detector — flags ticks where a predictor approached but did not cross the exclusion threshold; the SOTIF triggering-condition near-miss surface
* `symbolu_robotics.bcvf_autonomous.analysis::StreamingFleetMonitor` — Online fleet monitor with rolling-window summaries + threshold alerts — converts the post-hoc harness into an SRE-grade runtime monitoring surface (24-hour rolling argmax-flip rate, near-veto rate, V2 engaged fraction)
* `symbolu_robotics.bcvf_autonomous.analysis::AlertRule` — Threshold-based alert specification on a rolling window — the runtime triggering-condition surface a deployment partner wires into alertmanager / Grafana / pager rotations
* `symbolu_robotics.bcvf_autonomous.analysis::write_fleet_markdown` — Markdown report writer for ``FleetSummary`` — emits the field-monitoring narrative (headline aggregates, classification breakdown, per-predictor exclusion incidence, near-veto + V2-state-flip rosters, top-K per-episode index)
* `symbolu_robotics.bcvf_autonomous.analysis::write_fleet_csv` — CSV writer for ``FleetSummary`` — one row per episode with classification, flip rates, near-veto count, fraction engaged, BCVF totals; pinned column order for downstream audit-script ingest
* `symbolu_robotics.bcvf_autonomous.replay::ReplayBundle` — Recall-investigator's recording artifact — ties (RunConfig, recorded TrustShapedEpisodeRecord, package version, episode metadata) into a single JSON-serialisable bundle. The bundle is the post-incident replay surface a recall investigation argues against. See REPLAY_FRAMEWORK_DESIGN.md §2 for the bundle contract; §6 for the strict-validation discipline (corrupt artifacts fail loud, never silently produce zero-fill replays).
* `symbolu_robotics.bcvf_autonomous.replay::replay_bundle` — Bit-identity replay gate — runs the bundle's RunConfig against the current code, compares the freshly-recorded TrustShapedEpisodeRecord against the bundle's recorded record byte-by-byte, and returns a typed ReplayResult naming any per-field / per-step divergences. Class-A divergence (kernel diverged), Class-B divergence (config drift), and Class-C divergence (host non-determinism) all surface loud through the same comparison gate. See REPLAY_FRAMEWORK_DESIGN.md §4 + §5 for the design.

**Notes.** Per-tick ``TrustShapedEpisodeRecord`` is the structured post-incident trace a recall investigator opens. ``FleetSummary`` aggregates across episodes — argmax-flips, near-vetoes, V2 state distribution, per-predictor exclusion incidence — exactly the surface a fleet-scale safety-monitoring tool consumes. ``StreamingFleetMonitor`` plus ``AlertRule`` lift the harness from triage-time to runtime: rolling-window summaries (e.g. 24-hour argmax-flip rate) drive threshold alerts that route into the deployment partner's pager / alertmanager pipeline. Dataset ingest is strict (no silent zero-fill on incomplete payloads) so a corrupt episode surfaces as ``ValueError`` at load time rather than as a quiet metric drift. **Recall-investigation surface**: the ``ReplayBundle`` ties (RunConfig, recorded TrustShapedEpisodeRecord, package version, episode metadata) into a single JSON artifact a recall investigator opens; ``replay_bundle(bundle, runner_factory)`` runs the bundle's config against the current code and surfaces any divergence with field-level + tick-level localisation. Class-A divergence (kernel diverged), Class-B divergence (config drift), and Class-C divergence (host non-determinism) all surface loud through the same comparator. See ``REPLAY_FRAMEWORK_DESIGN.md`` for the full design.

### Clause 12 — Process — release to market + configuration management

**Requirement.** Establish process-level evidence for release to market, including the Software Bill of Materials (SBOM) of every dependency the runtime composition carries into the field.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.safety_case.sbom::generate_cyclonedx_bom` — CycloneDX 1.5 SBOM generator + on-disk snapshot at safety_case/SBOM.cdx.json — the procurement-gate deliverable enumerating every runtime dependency with version + SPDX license. Deterministic + byte-stable; pinned by a snapshot test so a dependency add / version bump fails CI loudly until the manifest is refreshed. See ROS2_DDS_SBOM_DESIGN.md §6 for design rationale.

**Notes.** **Configuration-management deliverable**: ``safety_case/SBOM.cdx.json`` is a CycloneDX 1.5 manifest enumerating every runtime dependency with version + SPDX license. Generated deterministically by ``safety_case.sbom.generate_cyclonedx_bom`` from installed-package metadata; pinned to byte-equality with the on-disk snapshot so a dependency add or version bump fails CI loudly until the manifest is refreshed. The runtime dependency set is small (numpy + stdlib for the autonomy import graph); optional dependencies (LLM-side anthropic / openai / fastapi etc.) are out of scope — this manifest covers the ``bcvf_autonomous`` import graph only. An OEM's full vehicle-stack SBOM aggregates this manifest alongside their own. See ``ROS2_DDS_SBOM_DESIGN.md`` §6 for design rationale.

## ISO 26262 Part 6 (Software)

### Clause Part 6 §7 — Specification of software safety requirements

**Requirement.** Derive software safety requirements from the system-level safety concept and document the verification criteria for each.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::_evaluate_thresholds` — Per-family acceptance thresholds — pass / fail rule table the sweep enforces (DESIGN.md §4)
* `symbolu_robotics.bcvf_autonomous.characterization::run_primary_grid` — Characterization DESIGN.md §4 (per-family thresholds) + §6.1 (Wilson CI floor) — the readable safety contract

**Notes.** Per-family acceptance tables in ``_evaluate_thresholds`` are the software-level safety requirements, with explicit numeric thresholds per family + the alignment criterion. Each requirement carries a ``failure_reasons`` label so an auditor can trace a failed cell back to the specific gate that fired.

### Clause Part 6 §8 — Software architectural design

**Requirement.** Specify the software architecture, including module decomposition, interfaces between modules, and dependencies between modules.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.core::compute_bcvf_cost` — BCVF cost kernel (SE(2) body-frame disagreement, second-order, gate × pseudo-Huber)
* `symbolu_robotics.bcvf_autonomous.runner::Runner` — Closed-loop scenario runner — module integration test harness exercising kernel + planner + trust + V2
* `symbolu_robotics.bcvf_autonomous.trust::ConsumerV2Config` — Schmitt-trigger consumer V2 — engage / disengage thresholds + dwell-time hysteresis (chatter-immunity argument)
* `symbolu_robotics.bcvf_autonomous.safety_state::SafetyStateMachine` — Functional-safety state machine — four-state behavioural contract (NORMAL / DEGRADED / FAULT / FAILSAFE) with documented per-transition triggers, ASIL decomposition (B for warnings + manual-resets, D for safety-critical escalations), direct-jump prohibition, and manual-reset audit trail. Composes the per-tick BCVF kernel + arbitration runtime into a system-level posture an ISO 26262 safety case can argue against; see SAFETY_STATE_MACHINE_DESIGN.md
* `symbolu_robotics.bcvf_ros2::BCVFNodeBehaviour` — Framework-agnostic ROS 2 node behaviour — wraps the BCVF trust-shaping bridge with rate-limited publication, per-predictor deadline tracking + stale-on-resume protection, and SafetyStateMachine composition. See ROS2_DDS_SBOM_DESIGN.md §3.3 + §5 for the integration contract; the rclpy-bound subclass lands gated on §6.4 colcon-build execution.
* `symbolu_robotics.bcvf_ros2.qos::DDS_QOS_PROFILE` — Documented DDS QoS profile (RELIABLE / VOLATILE / 10 ms deadline / 100 ms liveliness / KEEP_LAST / depth 1) — the `RELIABLE/VOLATILE/10ms/100ms` quad an integrator copies into their RTI Connext or FastDDS config. See ROS2_DDS_SBOM_DESIGN.md §4 for the per-knob rationale.
* `symbolu_robotics.bcvf_autonomous.safety_case.sbom::generate_cyclonedx_bom` — CycloneDX 1.5 SBOM generator + on-disk snapshot at safety_case/SBOM.cdx.json — the procurement-gate deliverable enumerating every runtime dependency with version + SPDX license. Deterministic + byte-stable; pinned by a snapshot test so a dependency add / version bump fails CI loudly until the manifest is refreshed. See ROS2_DDS_SBOM_DESIGN.md §6 for design rationale.

**Notes.** Modules: kernel (``core.py``), trust shaping (``trust.py``), planner (``mppi_planner.py``), diagnostics (``trust_diagnostics.py``), runner (``runner.py``), analysis (``analysis/``), safety-state machine (``safety_state/``), ROS 2 integration (``bcvf_ros2/``), SBOM generator (``safety_case/sbom/``). Interfaces are typed dataclasses (``BCVFConfig``, ``RunConfig``, ``ConsumerV2Config``, ``SafetyStateMachineConfig``, ``BCVFNodeConfig``, ``DDSQoSProfile``); each module ships a DESIGN.md. The ``SafetyStateMachine`` is the system-level behavioural-contract module the per-tick runtime composes into. The ``BCVFNodeBehaviour`` (alias ``BCVFNode``) wraps the trust-shaping bridge with the ROS 2 integration contract (rate-limited publication, per-predictor deadline tracking, ``DDS_QOS_PROFILE`` quad). The ``safety_case.sbom`` module emits the configuration-management manifest enumerating every runtime dependency. See ``SAFETY_STATE_MACHINE_DESIGN.md`` for the state machine's four-state contract; ``ROS2_DDS_SBOM_DESIGN.md`` for the integration contract.

### Clause Part 6 §9 — Software unit design and implementation

**Requirement.** Implement each software unit per the architectural design and the unit-level safety requirements.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.core::compute_bcvf_cost` — BCVF cost kernel (SE(2) body-frame disagreement, second-order, gate × pseudo-Huber)
* `symbolu_robotics.bcvf_autonomous.trust::ConsumerV2Config` — Schmitt-trigger consumer V2 — engage / disengage thresholds + dwell-time hysteresis (chatter-immunity argument)
* `symbolu_robotics.bcvf_autonomous.trust_diagnostics::TrustShapedEpisodeRecord` — Per-step trust diagnostic record — every tick's weights, BCVF cost, V2 state, near-veto incidence; the post-incident trace a recall investigator opens

**Notes.** Units are ASIL-style isolated: kernel has zero external dependencies beyond NumPy, V2 hysteresis is a pure state machine, diagnostics are a pure recorder. Determinism: every unit is fp64-stable + RNG-deterministic (seed-in / output-out).

### Clause Part 6 §9.4.4 — Software unit verification methods

**Requirement.** Verify each software unit against its design + safety requirements using methods appropriate for the ASIL (boundary values, equivalence classes, error guessing, structural coverage).

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::run_primary_grid` — 22 configs × 60 seeds = 1320-cell certification grid; drives the per-config Wilson-CI floor
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::summarize_grid` — Aggregator emitting per-config Wilson 95% CI low/high, min_ci_lower_bound, cells_below_certification_floor
* `symbolu_robotics.bcvf_autonomous.characterization.stats::wilson_ci` — Wilson score CI primitive (closed-form, no scipy) — the stated statistical bound's machinery
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::_evaluate_thresholds` — Per-family acceptance thresholds — pass / fail rule table the sweep enforces (DESIGN.md §4)

**Notes.** Boundary values: every family magnitude is evaluated at four points spanning the threshold-edge (e.g. ``accel_mag ∈ {0.1, 0.3, 0.5, 1.0}``). Equivalence classes: the seven families are the equivalence-class partition of input shapes. Structural coverage: 1320 cells × per-(family, magnitude) Wilson 95% CI lower bound floor 0.90 — every unit-level acceptance criterion is exercised at N=60 with a stated statistical bound (see ``CERTIFICATION_FLOOR``).

### Clause Part 6 §10 — Software integration and integration verification

**Requirement.** Integrate software units per the architectural design and verify the integrated software behaves as specified.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.runner::Runner` — Closed-loop scenario runner — module integration test harness exercising kernel + planner + trust + V2
* `symbolu_robotics.bcvf_autonomous.pilot::run_pilot` — §6.2 paired A0 vs A3 pilot runner — sign test + Wilson CI + FleetSummary + Lemma-1 negative-control gate
* `symbolu_robotics.bcvf_autonomous.baselines::run_shootout` — Apples-to-apples baseline shootout — BCVF vs EKF (Mahalanobis-rejection) vs Majority-Vote vs Anchor across the seven families
* `symbolu_robotics.bcvf_autonomous.realtime::RealTimeBudget` — Typed real-time budget contract — target_hz + per-tier ms thresholds (p99 / p999 / p9999 / max) + sample-count gates protecting against statistically-meaningless small-n percentile reports. The AUTOSAR-Adaptive deal-unlock answer to *what's your worst-case execution time?*. See REAL_TIME_BUDGET_DESIGN.md §2 for the per-knob rationale; §9 for the five ship-when-ready criteria gating STABLE_API graduation.
* `symbolu_robotics.bcvf_autonomous.realtime::LatencyMonitor` — Per-tick latency observer + budget enforcer — classifies each observation against the budget's tier hierarchy with mutually-exclusive counters, records over-budget violations in a bounded ring buffer, computes p99 / p999 / p9999 / max stats on demand. Composes with the existing EpisodeDiagnostics.solve_times_ms via observe_series; pairs with ReplayBundle for bit-identity replay of an over-budget tick. See REAL_TIME_BUDGET_DESIGN.md §3 + §4 + §5.

**Notes.** End-to-end integration: ``Runner`` exercises kernel + trust + V2 + planner across canonical scenarios (S1 nominal, S3 map-error-accel, etc.). ``run_pilot`` wires the same trust pipeline to a dataset adapter for paired A0 vs A3 evaluation. ``run_shootout`` integrates BCVF with three baseline arbitrators (EKF, Majority, Anchor) over the seven families. **Runtime-budget integration verification**: ``RealTimeBudget`` is the typed contract a deployment partner copies into their config; ``LatencyMonitor`` enforces it at integration time with mutually-exclusive per-tier (p99 / p999 / p9999 / max) violation counters + a bounded over-budget audit trail. The percentile-availability discipline (p999 None below 1000 samples; p9999 None below 10000) protects an ISO 26262 §10 integration-verification report from including statistically-meaningless small-n percentile claims. See ``REAL_TIME_BUDGET_DESIGN.md`` §4 + §9 for the full discipline + ship-when-ready criteria.

### Clause Part 6 §11 — Verification of software safety requirements

**Requirement.** Demonstrate the integrated software meets every software safety requirement, with traceable evidence.

**Evidence artifacts.**
* `symbolu_robotics.bcvf_autonomous.characterization.sweep::summarize_grid` — Aggregator emitting per-config Wilson 95% CI low/high, min_ci_lower_bound, cells_below_certification_floor
* `symbolu_robotics.bcvf_autonomous.pilot::run_pilot` — §6.2 paired A0 vs A3 pilot runner — sign test + Wilson CI + FleetSummary + Lemma-1 negative-control gate
* `symbolu_robotics.bcvf_autonomous.analysis::FleetSummary` — Fleet-scale aggregator over episode records — argmax-flips per step, near-vetoes, V2 state distribution, per-predictor exclusion incidence; the field-monitoring evidence pack
* `symbolu_robotics.bcvf_autonomous.trust_diagnostics::TrustShapedEpisodeRecord` — Per-step trust diagnostic record — every tick's weights, BCVF cost, V2 state, near-veto incidence; the post-incident trace a recall investigator opens
* `symbolu_robotics.bcvf_autonomous.characterization::write_grid_markdown` — Markdown report writer for ``GridSummary`` — emits the regulator-facing certification report (headline gate, per-(family, magnitude) Wilson-CI table, per-family roll-up, failed-config list, methodology block)
* `symbolu_robotics.bcvf_autonomous.analysis::write_fleet_markdown` — Markdown report writer for ``FleetSummary`` — emits the field-monitoring narrative (headline aggregates, classification breakdown, per-predictor exclusion incidence, near-veto + V2-state-flip rosters, top-K per-episode index)
* `symbolu_robotics.bcvf_autonomous.replay::replay_bundle` — Bit-identity replay gate — runs the bundle's RunConfig against the current code, compares the freshly-recorded TrustShapedEpisodeRecord against the bundle's recorded record byte-by-byte, and returns a typed ReplayResult naming any per-field / per-step divergences. Class-A divergence (kernel diverged), Class-B divergence (config drift), and Class-C divergence (host non-determinism) all surface loud through the same comparison gate. See REPLAY_FRAMEWORK_DESIGN.md §4 + §5 for the design.

**Notes.** Requirement-by-requirement traceability: each per-family threshold maps to a passing test in ``test_characterization.py``; each pilot-level acceptance gate (Lemma-1 negative control, responsive-class win rate, attribution accuracy) maps to a passing test in ``test_pilot.py``; each fleet-level metric is round-trip-tested via ``analysis.io`` strict serialisation. **Replay bit-identity contract**: ``replay_bundle(bundle, runner_factory)`` runs a captured ``ReplayBundle``'s ``RunConfig`` against the current code and verifies the freshly-recorded ``TrustShapedEpisodeRecord`` is bit-identical to the bundle's recorded record (np.array_equal with equal_nan=True over every per-step array). Bit-identity is the V&V argument the recall investigator argues against — the lab either reproduces the field-recorded outputs exactly, or the comparator localises the divergence to the specific (field, tick) pair so the kernel diff responsible can be pinpointed. See ``REPLAY_FRAMEWORK_DESIGN.md`` §4 for the design.

## Reverse index — artifact → clauses served

| Artifact | Clauses |
|---|---|
| `symbolu_robotics.bcvf_autonomous.analysis.near_veto::find_near_vetoes` | 7, 10 |
| `symbolu_robotics.bcvf_autonomous.analysis::AlertRule` | 10 |
| `symbolu_robotics.bcvf_autonomous.analysis::FleetSummary` | 10, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.analysis::StreamingFleetMonitor` | 10 |
| `symbolu_robotics.bcvf_autonomous.analysis::write_fleet_csv` | 10 |
| `symbolu_robotics.bcvf_autonomous.analysis::write_fleet_markdown` | 10, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.baselines::run_shootout` | 9, Part 6 §10 |
| `symbolu_robotics.bcvf_autonomous.characterization.stats::wilson_ci` | 9, Part 6 §9.4.4 |
| `symbolu_robotics.bcvf_autonomous.characterization.sweep::FAMILY_MAGNITUDES` | 7 |
| `symbolu_robotics.bcvf_autonomous.characterization.sweep::_evaluate_thresholds` | 9, Part 6 §7, Part 6 §9.4.4 |
| `symbolu_robotics.bcvf_autonomous.characterization.sweep::run_primary_grid` | 7, 9, Part 6 §9.4.4 |
| `symbolu_robotics.bcvf_autonomous.characterization.sweep::summarize_grid` | 9, Part 6 §9.4.4, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.characterization.traces::generate_trace` | 6 |
| `symbolu_robotics.bcvf_autonomous.characterization::ADVERSARIAL_FAMILIES` | 6, 8 |
| `symbolu_robotics.bcvf_autonomous.characterization::run_primary_grid` | 6, Part 6 §7 |
| `symbolu_robotics.bcvf_autonomous.characterization::write_grid_csv` | 9 |
| `symbolu_robotics.bcvf_autonomous.characterization::write_grid_markdown` | 9, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.core::BCVFConfig` | 5 |
| `symbolu_robotics.bcvf_autonomous.core::compute_bcvf_cost` | 5, Part 6 §8, Part 6 §9 |
| `symbolu_robotics.bcvf_autonomous.manifold::body_frame_error_trajectory` | 5 |
| `symbolu_robotics.bcvf_autonomous.pilot::run_pilot` | 9, Part 6 §10, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.predictors.base::BicycleConfig` | 5 |
| `symbolu_robotics.bcvf_autonomous.predictors::LaneAnchor` | 5 |
| `symbolu_robotics.bcvf_autonomous.predictors::MultiModalPredictor` | 5 |
| `symbolu_robotics.bcvf_autonomous.realtime::LatencyMonitor` | Part 6 §10 |
| `symbolu_robotics.bcvf_autonomous.realtime::RealTimeBudget` | Part 6 §10 |
| `symbolu_robotics.bcvf_autonomous.replay::ReplayBundle` | 10 |
| `symbolu_robotics.bcvf_autonomous.replay::replay_bundle` | 10, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.runner::Runner` | Part 6 §8, Part 6 §10 |
| `symbolu_robotics.bcvf_autonomous.safety_case.sbom::generate_cyclonedx_bom` | 12, Part 6 §8 |
| `symbolu_robotics.bcvf_autonomous.safety_state::LEGAL_TRANSITIONS` | 8 |
| `symbolu_robotics.bcvf_autonomous.safety_state::SafetyStateMachine` | 8, Part 6 §8 |
| `symbolu_robotics.bcvf_autonomous.trust::ConsumerV2Config` | 8, Part 6 §8, Part 6 §9 |
| `symbolu_robotics.bcvf_autonomous.trust_diagnostics::TrustShapedEpisodeRecord` | 10, Part 6 §9, Part 6 §11 |
| `symbolu_robotics.bcvf_autonomous.v2_chatter_sweep::run_v2_promotion_decision` | 8 |
| `symbolu_robotics.bcvf_ros2.qos::DDS_QOS_PROFILE` | 5, Part 6 §8 |
| `symbolu_robotics.bcvf_ros2::BCVFNodeBehaviour` | 5, Part 6 §8 |

## Out-of-scope clauses (intentionally not enumerated)

* SOTIF clauses 4 (definitions), 11 (release-to-the-market criteria), 12 (process-related considerations) — governance items owned by the deployment partner.
* ISO 26262 Part 6 §5 (general topics) and §6 (initiation) — process-layer items established by the deployment partner's QM organisation.
* ISO 26262 Parts 1–5, 7–12 — system / hardware / production lifecycle outside the software-arbitration boundary BCVF occupies.
