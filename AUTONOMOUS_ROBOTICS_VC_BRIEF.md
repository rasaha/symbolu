# Autonomous Robotics — VC Brief

**Ugence Labs | Safety Runtime for Autonomous Robotics — a certifiable trust-and-safety layer for multi-predictor robotics**
*Version 1.0 — Prepared July 2026*

> **Portfolio.** The Safety Runtime is a **Specialized AI System** in the Ugence Labs
> portfolio, alongside the **AI Control Plane** (governance for autonomous agents) and
> **AI Infrastructure** (Hybrid LLM, KVPro, cloud). It is the safety-and-certification
> layer for physical autonomy; it complements — and does not overlap — the other two. This
> brief positions the runtime for investors, not its full engineering surface.

---

## Page 1 — The Problem

### Operators want autonomous robots. Predictor disagreement — and the safety scaffolding around it — is blocking deployment.

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

But arbitration is only the visible tip. Even a team that solves disagreement still has to build
**everything that turns a working algorithm into a deployable, certifiable system**: a system-level
safety state machine, runtime diagnostics, replay for recall investigation, calibration
management, drift detection, sensor attestation, ROS 2 / DDS integration, and the certification
traceability that a SOTIF / ISO 26262 safety case is argued against. Today every program rebuilds
that scaffolding in-house, per stack, per release. The four questions a safety review asks earliest
are the ones current stacks answer least crisply:

| The question a safety case asks | What most current autonomy stacks offer |
|---|---|
| *"When two predictors disagree, can the system identify which one is failing — not which one the heuristic prefers?"* | Designated primary or majority vote; both fail when the primary or majority is the one drifting. |
| *"Is there a stated mathematical invariance — something that provably ignores benign disagreement and only fires on genuine failure?"* | Threshold-tuned heuristics with no formal invariance; behavior characterized empirically per stack. |
| *"When a predictor is down-weighted at runtime, can the operator reconstruct why — and replay the exact incident for a recall investigation?"* | Per-component logs with no causal trace and no bit-identical replay artifact. |
| *"Can the whole layer be handed to a certification team mapped to the clauses it grounds?"* | Certification evidence is assembled by hand, late, and separately from the runtime. |

The problem is not lack of redundancy. It is the absence of a **portable, testable safety runtime**
for the disagreement regime and the certification work that surrounds it. That layer does not exist
as a product today — it is in-house glue, rebuilt every time.

### Why this is a missing software layer, not a tooling gap

Fusion layers (Kalman / EKF, weighted averages, late-fusion ensembles) were designed to *combine*
honest noisy signals, not to *distrust* a predictor that is silently wrong. Bolt-on uncertainty
estimators (deep ensembles, MC dropout, evidential networks) produce numbers with **no formal
invariance property** — their behavior on unseen failure shapes is the unknown the safety case was
supposed to bound. And none of them ship with the surrounding safety machinery a certification body
now expects.

ISO 21448 (SOTIF), ISO 26262 (functional safety), and UN ECE R155 (cybersecurity) increasingly ask
for explicit handling of *silent predictor miscalibration*, *system-level fault posture*, and
*sensor integrity* — not just sensor dropout. Operators want a runtime layer that can say, under a
stated invariance, "this predictor is no longer trustworthy — here is the signal, here is the
attribution, here is the state transition, here is the replayable evidence, and here is the clause
it grounds." **That is the category we build for: the safety runtime between prediction, planning,
execution, and certification.**

---

## Page 2 — The Runtime

### One coherent safety runtime, with a mathematical trust kernel at its core

The Ugence Safety Runtime is a **code-first Python runtime** that wraps any multi-predictor robotics
stack and turns predictor disagreement into a trust-weighted, supervised, auditable, certifiable
planning consensus. At its center is the **BCVF trust kernel** — pure NumPy, with a mathematically
proven invariance property. Around that kernel the runtime provides the system-level safety
machinery that deployment and certification actually require, presented as one contract rather than
a bag of features.

```
                       Applications  (AV · drone · mobile robot · humanoid)
                                 │
                                 ▼
                            Planning  (MPPI / MPC / sampling)
                                 │
        ┌────────────────────────────────────────────────────────────┐
        │            UGENCE SAFETY RUNTIME (v0.4.0)                    │
        │                                                             │
        │   BCVF trust kernel        — Lemma-1 invariant disagreement │
        │   Safety state machine     — NORMAL/DEGRADED/FAULT/FAILSAFE │
        │   Sensor attestation       — UN ECE R155 integrity gate     │
        │   Calibration + drift      — signed config sets, drift alerts│
        │   Runtime diagnostics      — per-tick / episode / fleet      │
        │   Replay framework         — bit-identical recall replay     │
        │   Safety evidence + traceability — SOTIF / ISO 26262 index   │
        └────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                            ROS 2 / DDS  (typed msgs · QoS profile · SBOM)
                                 │
                                 ▼
                            Robot hardware
```

### The trust kernel — the invariance nothing else in the market has

The **BCVF kernel** turns predictor disagreement into a trust signal with a **mathematically proven
invariance**: constant offsets between predictors (different calibration, fixed bias) produce
**exactly zero** trust signal; linear drifts produce **exactly zero** trust signal; only
**accelerating** divergence produces a positive signal. This is a structural property of a 2nd-order
operator on the vector-valued disagreement (Lemma 1, formally proven in the design spec) — not an
empirically calibrated score.

No bolt-on uncertainty estimator shipping in autonomy stacks has this property. Their numbers are
calibrated on regimes the data covered; their behavior on unseen failure shapes is the unknown a
safety case struggles to bound. Lemma 1 is what lets a reviewer say: *"this signal cannot fire on
the benign patterns — therefore a non-zero signal is informative."* The runtime contract that
carries it — **predict → score → normalize → trust → consensus → plan → act** — is pinned by the
test suite, not a configurable option. A predictor whose disagreement is flat or linearly drifting
cannot move a trust weight; a residual below the significance gate cannot shape the softmin; a
trust distribution cannot bypass the consensus stage.

### The safety machinery around the kernel

Each subsystem is real code, independently testable, composing into one runtime:

| Subsystem | What it provides | Why a safety case needs it |
|---|---|---|
| **Safety state machine** | A four-state system posture — NORMAL / DEGRADED / FAULT / FAILSAFE — with documented per-transition triggers, ASIL decomposition, direct-jump prohibition, and a manual-reset audit trail. | The system-level supervisor an ISO 26262 case is argued against; the kernel's per-tick signal composes into a named posture instead of stopping at the algorithm boundary. |
| **Sensor attestation** | A per-message integrity gate (firmware allowlist, freshness/replay windows, HMAC-SHA256, constant-time compare) upstream of the kernel; the integrator wires their own HSM/TPM key resolver. | Closes the UN ECE R155 loop: a stealth-bias spoof the kernel's invariance cannot see by construction is rejected *before* it reaches the kernel. |
| **Calibration + drift detection** | A frozen, SHA-256-identified calibration set bundling every runtime config into one signable, version-controlled artifact; a drift detector that alerts when live fleet metrics leave the calibrated envelope. | Configuration management and field monitoring — the difference between a lab result and a fleet you can operate and re-certify. |
| **Runtime diagnostics** | Per-tick trust traces, per-episode records, and a streaming fleet monitor with rolling-window summaries and threshold alerts. | Turns "why did the runtime distrust that predictor" from a forensics project into a live SRE surface. |
| **Replay framework** | A single serializable bundle (config + recorded episode + version) that a recall investigator opens and re-runs against current code, with **bit-identical** divergence localization to the offending field and tick. | The post-incident-recall evidence artifact SOTIF and ISO 26262 V&V ask for. |
| **ROS 2 / DDS integration** | Framework-agnostic node with typed `.msg` schemas, a documented DDS QoS profile, rate-limiting and per-predictor deadline tracking, plus a CycloneDX SBOM. | Answers the first three questions every Tier-1 / OEM asks — *does it speak ROS 2? what's the DDS QoS? where's the SBOM?* — with code a reviewer can `cd` into. |
| **Safety evidence + traceability** | A machine-generated index mapping runtime artifacts to the SOTIF (ISO 21448) and ISO 26262 Part 6 clauses they ground. | Lets a buyer's safety team begin a clause-by-clause diligence walk-through on day one, not after a separate workstream. |

The kernel is pure NumPy — no torch, no GPU, milliseconds per step on a single CPU core, evaluable
on synthetic predictors before any procurement conversation. The safety machinery is stdlib-first
and dependency-light for the same reason: it drops into a customer's CI without provisioning new
infrastructure.

### Honest scope (stated up front, because for a safety product the boundary *is* the credibility)

The runtime **arbitrates and supervises** predictors — it does not replace perception, prediction,
fusion, or planning, and it does not catch failures that never manifest as predictor *disagreement*
(a degradation all predictors share is out of scope, documented explicitly). It has **no production
deployment yet**: validation is on synthetic and realistic-noise predictors, with a real-sensor
pilot as the next scheduled step. Every number in this brief is from our own repository and CI, not
a third-party benchmark. The internal LLM-trust transfer probe returned a clean null and is **not**
positioned as a product. Selling the boundary honestly is what makes the part inside it certifiable.

---

## Page 3 — Market Position & Competitive Landscape

### The missing software layer between prediction, planning, execution, and certification

The Safety Runtime is **not** another planner, another perception stack, or another robotics
platform. It is the layer that sits *between* those and the certification file — the layer every
production stack has as in-house glue and no vendor sells as a portable, inspectable, testable
runtime with a stated mathematical property.

**Who buys this.** AV and robotics OEMs and their Tier-1 suppliers; drone-delivery, warehouse, and
industrial-mobile-robot programs; and — critically — the **safety and certification teams** inside
those programs, who own the SOTIF / ISO 26262 / UN R155 deliverable and currently have no runtime
artifact to point their clauses at.

**Why now.** Multi-predictor stacks are universal; certification is the bottleneck. SOTIF, ISO
26262, and UN ECE R155 are simultaneously tightening the requirements for silent-miscalibration
handling, system-level fault posture, and sensor integrity. Programs are hitting the wall where the
algorithm works but the *safety case* cannot be assembled fast enough to deploy.

**Why existing stacks still need it.** Perception, prediction, and planning stacks — open or
closed — produce trajectories. None of them ship a portable, certifiable trust-and-safety runtime
with an invariance a reviewer can rely on, and the closed platforms bury their arbitration inside
proprietary code the customer cannot inspect or certify.

**What deployment pain it removes.** It replaces the per-program rebuild of the entire safety
scaffold — state machine, attestation, calibration, drift, replay, diagnostics, ROS/DDS glue,
traceability — with one adopted runtime, evaluable on a laptop before procurement.

**Why it is hard to replace once adopted.** Once a program's calibration sets are signed against it,
its recall investigations replay through it, its sensor attestation policies are wired to it, and —
above all — its **certification traceability is argued against it**, the runtime is load-bearing in
the safety case. Ripping it out means re-opening the safety file. That is the durable moat.

### How it differs from adjacent technology

| Category | Representative players | How the Safety Runtime differs — and why it is better |
|---|---|---|
| **Classical sensor / state fusion** | Kalman / EKF / UKF, particle filters, ROS `robot_localization`, Apollo perception fusion | Fusion *combines* noisy-but-honest signals; it cannot represent a predictor that is silently wrong. We sit one level up, **detecting disagreement** under a formal invariance and gating trust — and we compose with fusion rather than replacing it. |
| **ML uncertainty estimation** | Deep ensembles, MC dropout, evidential / Bayesian DL, conformal prediction | These produce calibrated numbers with **no invariance**; their unseen-regime behavior is the unknown a safety case must bound. Lemma 1 gives a *structural* statement no empirical score can. We ingest their scores as additional context — additive, not rival. |
| **Closed AV / robotics platforms** | Waymo, Cruise, Mobileye, Tesla, NVIDIA DRIVE, Apollo, Woven | Proprietary, non-portable internal arbitration the customer cannot inspect, certify, or substitute. We ship the arbitration-and-safety layer as a *portable, inspectable runtime* a DRIVE or Apollo user drops in without giving up the rest of the stack. |
| **Open-source AV / robotics stacks** | Autoware, Apollo OSS, OpenPilot, Nav2, MoveIt | They ship stack components and leave arbitration + safety machinery as per-integrator glue. We provide the missing tested runtime contract *and* the surrounding safety subsystems, as a single dependency. |
| **Functional-safety & security tooling** | ANSYS medini, Vector, dSPACE, Foretellix | These document *what* the system should do; they do not enforce it at runtime. We produce the runtime artifact — and the machine-generated traceability index — those documents refer to. Complementary, not competing. |

### Where we do not compete (year one)

We are not trying to win on perception, sensor drivers, full-stack ecosystem breadth, or production
deployment count in the first twelve months. We win on the one thing an autonomy safety case has no
portable answer for today: **a runtime with a proven trust invariance and the certifiable safety
machinery around it.**

### In one sentence

Classical fusion combines signals; ML uncertainty estimates noise; closed stacks bury arbitration
in proprietary code; open stacks leave it to integrators. The Ugence Safety Runtime gives autonomy
programs a **provably invariant trust signal, a supervised safety posture, and a certification-ready
evidence trail** — a different product category than any incumbent is building for.

---

## Page 4 — Evidence & Roadmap

### What exists today (runtime v0.4.0, internal evidence)

| Area | Current state |
|---|---|
| **BCVF trust kernel** | Pure-NumPy 2nd-order operator with the **Lemma 1 invariance proven** and CI-verified on constructed constant-bias and linear-drift inputs; cost-order ablation (ZEROTH/FIRST/SECOND) confirms the proof empirically. |
| **Validated configuration** | End-to-end on a controlled failure scenario (`S3_map_error_accel`, N=21 paired): catastrophe rate 14.3% vs 23.8% baseline, mean lateral deviation **1.79 m vs 4.30 m**, **sign test p = 0.0072**. First statistically significant improvement over a no-shaping baseline. |
| **Baseline shootout** | BCVF built at the same arbitration interface as EKF (Mahalanobis 3σ), Majority-Vote, and a null floor, across the full failure taxonomy. **BCVF is the only arbitrator with zero false-attribution on Lemma-1-invariant disagreement** (constant-bias: BCVF 0.0 vs EKF 1.1 vs Majority 16.7), and 8–19× faster per tick than EKF / Majority. |
| **Safety state machine** | Four-state supervisor (NORMAL/DEGRADED/FAULT/FAILSAFE) with ASIL decomposition, direct-jump prohibition, and manual-reset audit trail. |
| **Sensor attestation** | Stdlib HMAC-SHA256 integrity gate (seven ordered checks, constant-time compare, integrator-supplied key resolver), upstream of the kernel — UN ECE R155 scope. |
| **Calibration + drift** | SHA-256-identified, signable calibration sets; drift detector against live fleet summaries with typed range-violation alerts. |
| **Diagnostics + replay** | Per-tick/episode/fleet diagnostics with a streaming monitor; a replay framework with **bit-identical** divergence localization for recall investigation. |
| **Real-time budget** | A typed worst-case-execution-time contract with p99 / p999 / p9999 percentile monitoring (the AUTOSAR-Adaptive "what's your WCET?" answer). |
| **ROS 2 / DDS + SBOM** | Framework-agnostic node, typed `.msg` schemas, documented DDS QoS profile, and a CycloneDX 1.5 SBOM manifest. |
| **Certification traceability** | Machine-generated SOTIF (ISO 21448) + ISO 26262 Part 6 clause index, refreshed by a doc-render test so it cannot drift from the code. |
| **Test suite** | A comprehensive, CI-pinned suite — **900+ tests** across kernel, planner, safety machinery, integration contracts, and evidence generators. All numbers internal; no third-party benchmarks. |

### 18-month roadmap (forward-looking — completed capabilities above are not roadmap items)

**Near term — pilots and real sensor data**
- **OEM / design-partner pilots** in adjacent robotics domains (drone, warehouse, industrial mobile
  robot) where the multi-predictor pattern exists and safety-case pressure is real.
- **Real-sensor validation** on public multi-predictor traces (KITTI / nuScenes) to move beyond
  synthetic and realistic-noise predictors.

**Mid term — certification and production**
- **ISO 26262 certification** engagement — advance the traceability index into a partner-authored,
  auditor-reviewed safety case against a specific operational design domain.
- **SOTIF certification package** — complete the ISO 21448 evidence set (triggering conditions,
  functional insufficiencies, V&V) as a deliverable a certification body signs.
- **First production deployment** with a reference customer, behind the safety state machine and
  the read-only diagnostics surface.

**Longer term — scale and commercial breadth**
- **Fleet deployment** — the streaming monitor, drift detection, and calibration bundles operated
  across a live fleet as a managed field-monitoring surface.
- **Hardware acceleration** — an accelerated kernel path for high-rate stacks while preserving the
  pure-NumPy reference as the certifiable baseline.
- **Multi-robot support** — the hierarchical / group-level trust design advanced from proposal to
  shipped capability for swarms and multi-agent coordination.
- **Commercial integrations** — first-class Autoware / Apollo / DRIVE integration paths and a
  managed runtime offering.

### The ask

We are raising seed to evolve the Safety Runtime from an internally-tested, statistically-validated
runtime into a **pilot-proven, certification-track product** operators adopt without giving up their
existing perception and planning stacks. The technology is live: a proven trust invariance, a
supervised safety posture, sensor attestation, calibration and drift management, bit-identical
replay, ROS 2 / DDS integration, and a machine-generated certification index — all CI-pinned. The
capital is earmarked for OEM pilots, real-sensor validation, the ISO 26262 / SOTIF certification
work, and the first production and fleet deployments.

Predictor disagreement — and the safety scaffolding around it — is a structural gap in every modern
multi-model autonomy stack. The next 12–24 months are the window to establish the portable default
for that layer, before incumbents calcify proprietary in-house solutions into vendor lock-in and
before open stacks bake un-certifiable glue into their reference modules. A proven invariance, a
certifiable safety runtime around it, and a pure-NumPy kernel that drops into any planner give
Ugence a defensible position in that window.

---

*Contact: Rakesh Mohan — Ugence Labs*
*Repo: `rasaha/symbolu` · Module: `symbolu_robotics/bcvf_autonomous/` · Runtime v0.4.0*
*Positioning: Specialized AI System · safety runtime for autonomous robotics · BCVF trust kernel + safety, integrity, operations, and certification subsystems*
