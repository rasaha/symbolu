# Autonomous Robotics — VC Brief

**Ugence Labs | Autonomous Runtime — the execution-supervision runtime for autonomous systems**
*Runtime Trust Engine · runtime state machine · calibration · drift detection · replay · diagnostics · certification evidence*
*Version 1.2 — Prepared July 2026*

> **Portfolio.** The Autonomous Runtime is a **Specialized AI System** in the Ugence Labs
> platform. Its job is to *supervise execution* on autonomous machines — arbitrate predictors,
> drive the runtime state machine, manage calibration, detect drift, replay incidents, and produce
> certification evidence. A **Runtime Trust Engine** sits at its core, powered by the BCVF trust
> kernel — but the product is the runtime, and an investor does not need to understand BCVF to
> understand it.

```
Ugence Labs
├── Specialized AI Systems
│     ├── Agent Runtime            — reasoning → governed proposals
│     └── Autonomous Runtime       — autonomy software → certified deployment   ◄ this brief
├── AI Control Plane
│     ├── Context Minimization
│     ├── ActionGate
│     └── Autonomous Control Plane (ACP)
└── AI Infrastructure
      ├── Hybrid LLM
      ├── KVPro
      └── Cloud Infrastructure
```

---

## Page 1 — The Problem

### Operators want autonomous robots. There is no runtime layer between autonomy software and certified deployment.

Modern autonomous-vehicle, drone, mobile-robot, and humanoid stacks all arrived at the same
architectural pattern: **fuse multiple predictors.** A typical stack runs an HD-map prior, a
learned end-to-end predictor, a classical kinematic model, and at least one redundant sensor
channel. When the predictors agree, planning is easy. **When they disagree, the planner has no
principled way to decide which one to trust** — and predictor disagreement is exactly the regime
where the failures that matter live.

Industry has converged on a small set of ad-hoc responses: majority voting, hand-tuned weighted
averages, a designated "primary" predictor, threshold-switching to a fallback controller. Each
works in nominal regimes and degrades — often silently — in exactly the corner cases that drive
disengagement statistics, recall events, and safety-case escalations.

But arbitration is only the visible tip. The deeper gap is that **there is no runtime layer
between the autonomy software and a certified deployment.** A team that solves disagreement still
has to build everything that turns a working algorithm into a deployable, supervisable, certifiable
system: a runtime state machine, execution diagnostics, replay for recall investigation,
calibration management, drift detection, sensor attestation, ROS 2 / DDS integration, and the
certification traceability a SOTIF / ISO 26262 case is argued against. Today every program rebuilds
that layer in-house, per stack, per release.

### The hole in the stack

The modern robotics stack is well served — except for one layer:

```
   HAVE          ROS 2  ·  DDS  ·  Nav2  ·  Autoware  ·  Apollo  ·  MoveIt  ·  Isaac
                 (middleware, planning, perception, simulation — mature, broadly adopted)

   MISSING       ┌──────────────────────────────────────────────┐
                 │        EXECUTION-SUPERVISION RUNTIME          │   ◄ the product
                 │  trust · state machine · replay · evidence    │
                 └──────────────────────────────────────────────┘
```

Every production stack has this layer as bespoke in-house glue. No vendor sells it as a portable,
testable runtime with a stated mathematical property and built-in certification evidence. That is
the missing product.

### Why now

ISO 21448 (SOTIF), ISO 26262 (functional safety), and UN ECE R155 (cybersecurity) are
simultaneously tightening requirements for silent-miscalibration handling, system-level fault
posture, and sensor integrity — not just sensor dropout. Programs are hitting the wall where the
algorithm works but the *deployment case* cannot be assembled fast enough. Fusion layers combine
honest signals rather than distrusting a silently-wrong predictor; bolt-on uncertainty estimators
produce numbers with no invariance a safety case can rely on. The runtime layer that closes the gap
does not exist as a product today.

---

## Page 2 — The Runtime

### One runtime that supervises execution

The Ugence Autonomous Runtime is a **code-first Python runtime** that wraps any multi-predictor
robotics stack and continuously supervises its execution. At every planning step it arbitrates
predictors through the Runtime Trust Engine, drives a system-level state machine, manages
calibration, detects drift, records replayable evidence, and maintains certification traceability.

### The execution pipeline

```
                       Mission
                          │
                          ▼
                       Planner  (MPPI / MPC / sampling)
                          │
   ┌──────────────────────────────────────────────────────────┐
   │            UGENCE AUTONOMOUS RUNTIME (v0.4.0)              │
   │                                                          │
   │     Runtime Trust Engine      — Lemma-1 invariant signal  │
   │     Runtime state machine      — NORMAL/DEGRADED/FAULT/FS  │
   │     Calibration                — signed, versioned configs │
   │     Drift detection            — live envelope monitoring  │
   │     Replay                     — bit-identical recall      │
   │     Diagnostics                — per-tick / episode / fleet │
   │     Sensor attestation         — UN ECE R155 integrity gate│
   │     Certification evidence      — SOTIF / ISO 26262 index  │
   └──────────────────────────────────────────────────────────┘
                          │
                          ▼
                       ROS 2 / DDS  (typed msgs · QoS profile · SBOM)
                          │
                          ▼
                       Robot
```

### It deploys as a fleet, not one robot

The runtime is a per-vehicle supervisor that rolls up to a fleet. Signed calibration sets are
distributed to each vehicle; the streaming diagnostics and drift alerts roll back up to a cloud
fleet surface, so an operator supervises a fleet the way an SRE supervises a service:

```
   Cloud Fleet Manager        ── consumes streaming diagnostics + drift alerts, distributes calibration
          │
          ▼
   Mission Planner            ── per-vehicle mission + planner
          │
          ▼
   Autonomous Runtime         ── per-vehicle execution supervision  ◄ Ugence
          │
          ▼
   Vehicle
          │
          ▼
   Sensors                    ── attested at the runtime boundary
```

### What happens when the AI is wrong

The strongest differentiator is not a feature — it is the **failure behavior**. When a predictor is
silently wrong, the runtime does not crash and does not blindly proceed. It degrades deliberately
and leaves an evidence trail:

```
   Planner proposes action
          │
          ▼
   Runtime validates trust        (Runtime Trust Engine — Lemma-1 invariant)
          │
          ▼
   Unsafe?  ──── no ──►  proceed on trust-weighted consensus
          │ yes
          ▼
   Degrade                        (state machine: NORMAL → DEGRADED, down-weight the suspect predictor)
          │  still unsafe
          ▼
   Failsafe                       (DEGRADED → FAULT → FAILSAFE, manual-reset latched)
          │
          ▼
   Evidence recorded              (bit-identical replay bundle + per-tick diagnostics)
          │
          ▼
   Continue mission               (or hand back to the operator, fully audited)
```

This is the story a safety reviewer and a CTO both want: not "it never fails," but "when a
component fails, the system contains it, records it, and stays accountable."

### The supervision loop — continuous, not a one-shot check

```
   Plan  ──►  Execute  ──►  Observe  ──►  Evaluate  ──►  Adapt  ──►  Continue
    ▲                                                                   │
    └───────────────────────────────────────────────────────────────────┘
```

**Plan** over the multi-predictor consensus; **execute** the selected control; **observe** via
per-tick diagnostics; **evaluate** posture against the calibrated envelope; **adapt** trust weights
and the safety state (*no model is retrained — the runtime adapts trust and posture, not the
predictors*); **continue**, recording every transition as replayable evidence.

### The Runtime Trust Engine — the invariance nothing else in the market has

Powered by the **BCVF trust kernel**, the Runtime Trust Engine turns predictor disagreement into a
signal with a **mathematically proven invariance**: constant offsets and linear drifts between
predictors produce **exactly zero** trust signal; only **accelerating** divergence produces a
positive one. This is a structural property of a 2nd-order operator on the vector-valued
disagreement (Lemma 1, formally proven) — not an empirically calibrated score. No bolt-on
uncertainty estimator shipping in autonomy stacks has it. Lemma 1 is what lets a reviewer say:
*"this signal cannot fire on the benign patterns — therefore a non-zero signal is informative."*
The contract that carries it — **predict → score → normalize → trust → consensus → plan → act** —
is pinned by the test suite, not a configurable option.

### The supervision machinery around the engine

| Subsystem | What it provides | Why deployment needs it |
|---|---|---|
| **Runtime state machine** | A four-state posture — NORMAL / DEGRADED / FAULT / FAILSAFE — with per-transition triggers, ASIL decomposition, direct-jump prohibition, manual-reset audit trail. | The system-level supervisor an ISO 26262 case is argued against. |
| **Calibration + drift detection** | A SHA-256-identified, signable calibration set bundling every runtime config; a detector that alerts when live fleet metrics leave the calibrated envelope. | Configuration management + field monitoring across a fleet. |
| **Replay framework** | A serializable bundle (config + recorded episode + version) re-run against current code, with **bit-identical** divergence localization to the offending field and tick. | The post-incident-recall evidence artifact SOTIF and ISO 26262 V&V ask for. |
| **Diagnostics** | Per-tick trust traces, per-episode records, streaming fleet monitor with threshold alerts. | Turns forensics into a live SRE surface. |
| **Sensor attestation** | A per-message integrity gate (firmware allowlist, freshness/replay windows, HMAC-SHA256) upstream of the engine; integrator wires their HSM/TPM key resolver. | Closes the UN ECE R155 loop — a stealth spoof is rejected before it reaches the engine. |
| **ROS 2 / DDS integration** | Framework-agnostic node, typed `.msg` schemas, documented DDS QoS profile, per-predictor deadline tracking, CycloneDX SBOM. | Answers the OEM's first three questions — *ROS 2? DDS QoS? SBOM?* — with code. |
| **Certification evidence** | A machine-generated index mapping runtime artifacts to SOTIF (ISO 21448) and ISO 26262 Part 6 clauses, refreshed by a test so it cannot drift. | Day-one clause-by-clause diligence for a buyer's safety team. |

### Honest scope

The runtime **supervises** predictors — it does not replace perception, prediction, fusion, or
planning, and it does not catch failures that never manifest as predictor *disagreement*. It has
**no production deployment yet**: validation is on synthetic and realistic-noise predictors, with a
real-sensor pilot as the next step. Every number here is internal. The LLM-trust transfer probe
returned a clean null and is **not** positioned as a product.

---

## Page 3 — Market Position & Customer

### The missing runtime layer between autonomy software and certified deployment

```
   Perception  ──►  Planning  ──►  Execution  ──►  Autonomous Runtime  ──►  Certified deployment
                                                        ▲
                                                     Ugence
```

The Autonomous Runtime is **not** another planner, perception stack, or robotics platform. It is
the runtime layer between all of that and the certification file.

### Who buys this

The runtime targets any program running a multi-predictor stack under a safety or certification
mandate:

- **Autonomous vehicle companies** — passenger AV, robotaxi, trucking
- **Industrial robotics OEMs** — the suppliers who must ship a certifiable system, not a demo
- **Warehouse & logistics robotics** — high-density mobile-robot fleets
- **Defense autonomy** — where fault posture and auditability are procurement gates
- **Mining & heavy industry** — large autonomous machines in unforgiving environments
- **Agriculture** — autonomous ground vehicles at fleet scale
- **Humanoids** — the emerging stack that will inherit every one of these requirements

Within each, the economic buyer is increasingly the **safety / certification owner**, who holds the
SOTIF / ISO 26262 / UN R155 deliverable and today has no runtime artifact to point their clauses at.

### Where this fits with the rest of Ugence

> **The Autonomous Runtime supervises robot execution; the AI Control Plane governs AI decisions.
> Together they form an end-to-end governed autonomy stack** — one runtime accountable for what the
> machine physically does, one control plane accountable for what the AI is authorized to do. Each
> is independently adoptable; deployed together they close the loop from decision to actuation.

### How it differs from adjacent technology

| Category | Representative players | How the Autonomous Runtime differs — and why it is better |
|---|---|---|
| **Classical sensor / state fusion** | Kalman / EKF / UKF, particle filters, ROS `robot_localization`, Apollo fusion | Fusion *combines* honest signals; it cannot represent a predictor that is silently wrong. We sit one level up, detecting disagreement under a formal invariance — and compose with fusion, not replace it. |
| **ML uncertainty estimation** | Deep ensembles, MC dropout, evidential / Bayesian DL, conformal | Calibrated numbers with **no invariance**; unseen-regime behavior is the unknown a safety case must bound. Lemma 1 gives a structural statement no empirical score can. We ingest their scores as context. |
| **Closed AV / robotics platforms** | Waymo, Cruise, Mobileye, Tesla, NVIDIA DRIVE, Apollo, Woven | Proprietary, non-portable internal arbitration the customer cannot inspect or certify. We ship the supervision layer as a portable runtime a DRIVE or Apollo user drops in without giving up the stack. |
| **Open-source AV / robotics stacks** | Autoware, Apollo OSS, OpenPilot, Nav2, MoveIt, Isaac | They ship stack components and leave supervision + certification as per-integrator glue. We provide the missing tested runtime contract *and* the machinery, as one dependency. |
| **Functional-safety & security tooling** | ANSYS medini, Vector, dSPACE, Foretellix | These document *what* the system should do; they don't enforce it at runtime. We produce the runtime artifact — and the traceability index — those documents refer to. Complementary. |

### In one sentence

Classical fusion combines signals; ML uncertainty estimates noise; closed stacks bury arbitration
in proprietary code; open stacks leave it to integrators. The Ugence Autonomous Runtime is the
**missing runtime layer between autonomy software and certified deployment.**

---

## Page 4 — Evidence, Expansion & Ask

### What exists today (runtime v0.4.0, internal evidence)

| Area | Current state |
|---|---|
| **Runtime Trust Engine (BCVF kernel)** | Pure-NumPy 2nd-order operator with the **Lemma 1 invariance proven** and CI-verified on constructed constant-bias and linear-drift inputs; cost-order ablation confirms the proof empirically. |
| **Validated configuration** | End-to-end on a controlled failure scenario (`S3_map_error_accel`, N=21 paired): catastrophe rate 14.3% vs 23.8% baseline, mean lateral deviation **1.79 m vs 4.30 m**, **sign test p = 0.0072** — the first statistically significant improvement over a no-shaping baseline. |
| **Baseline shootout** | Built at the same arbitration interface as EKF (Mahalanobis 3σ), Majority-Vote, and a null floor. **The only arbitrator with zero false-attribution on Lemma-1-invariant disagreement** (constant-bias: 0.0 vs EKF 1.1 vs Majority 16.7), and 8–19× faster per tick than EKF / Majority. |
| **Runtime state machine** | Four-state supervisor (NORMAL/DEGRADED/FAULT/FAILSAFE) with ASIL decomposition, direct-jump prohibition, manual-reset audit trail. |
| **Calibration + drift** | SHA-256-identified, signable calibration sets; drift detector against live fleet summaries with typed range-violation alerts. |
| **Replay + diagnostics** | Bit-identical incident replay with field/tick divergence localization; per-tick/episode/fleet diagnostics with a streaming monitor. |
| **Sensor attestation** | Stdlib HMAC-SHA256 integrity gate (seven ordered checks, constant-time compare) upstream of the engine — UN ECE R155 scope. |
| **Real-time budget** | A typed worst-case-execution-time contract with p99 / p999 / p9999 percentile monitoring. |
| **ROS 2 / DDS + SBOM** | Framework-agnostic node, typed `.msg` schemas, documented DDS QoS profile, CycloneDX 1.5 SBOM manifest. |
| **Certification evidence** | Machine-generated SOTIF (ISO 21448) + ISO 26262 Part 6 clause index, refreshed by a doc-render test so it cannot drift. |
| **Verification** | Validated through an extensive deterministic verification suite covering runtime supervision, replay, calibration, safety-state transitions, sensor attestation, and certification-evidence generation. All internal; no third-party benchmarks. |

### Market expansion path

The multi-predictor supervision problem is identical across autonomy domains; the runtime expands
one vertical at a time as each stack matures:

```
   Today        Ground robots      (AV / warehouse — the validated home domain)
     │
     ▼
   Next         Industrial robots  (OEM-shipped systems under functional-safety mandate)
     │
     ▼
   Then         Drones             (M = 5–10 predictors; per-source attribution more discriminative)
     │
     ▼
   Then         Humanoids          (inherits every AV safety requirement, higher DOF)
     │
     ▼
   Then         Multi-agent autonomy  (hierarchical / group-level trust across a swarm)
```

### 18-month roadmap (forward-looking — completed capabilities above are not roadmap items)

- **OEM / design-partner pilots** in adjacent domains (drone, warehouse, industrial mobile robot).
- **Real-sensor validation** on public multi-predictor traces (KITTI / nuScenes).
- **ISO 26262 certification** — advance the traceability index into a partner-authored,
  auditor-reviewed safety case against a specific operational design domain.
- **SOTIF certification package** — complete the ISO 21448 evidence set as a deliverable a
  certification body signs.
- **First production deployment**, then **fleet deployment** behind the cloud diagnostics surface.
- **Hardware acceleration** (accelerated kernel path; pure-NumPy reference preserved as the
  certifiable baseline) and **multi-robot support** (hierarchical trust from proposal to shipped).
- **Commercial integrations** — first-class Autoware / Apollo / DRIVE paths and a managed offering.

### The ask

We are raising seed to evolve the Autonomous Runtime from an internally-tested, statistically-
validated runtime into a **pilot-proven, certification-track product** operators adopt without
giving up their existing perception and planning stacks. The technology is live: a proven trust
invariance, a supervised runtime posture, calibration and drift management, bit-identical replay,
sensor attestation, ROS 2 / DDS integration, and a machine-generated certification index — all
CI-verified. Capital is earmarked for OEM pilots, real-sensor validation, the ISO 26262 / SOTIF
certification work, and the first production and fleet deployments.

Predictor disagreement — and the supervision-and-certification layer around it — is a structural gap
in every modern multi-model autonomy stack, across every vertical from AV to humanoids. The next
12–24 months are the window to establish the portable default for that layer, before incumbents
calcify proprietary solutions into lock-in and before open stacks bake un-certifiable glue into
their reference modules. A proven invariance, a runtime that supervises execution around it, and a
pure-NumPy engine that drops into any planner give Ugence a defensible position in that window.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `symbolu_robotics/bcvf_autonomous/` · Runtime v0.4.0*
*Positioning: Specialized AI System · Autonomous Runtime — the execution-supervision runtime between autonomy software and certified deployment · Runtime Trust Engine (BCVF kernel) at its core*
