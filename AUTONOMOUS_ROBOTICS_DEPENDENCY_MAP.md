# Autonomous Robotics (BCVF) — Customer-Data Dependency Map

> **Purpose.** One page that answers: *what is actually pending, and what unblocks it?* Derived from
> `AUTONOMOUS_ROBOTICS_VC_BRIEF_V2.md` (v0.7), `INDUSTRY_FEATURES_ROADMAP.md` §9, and each design doc's
> ship-when-ready criteria (§8/§9). **Source of truth is those files; this is the index.**

## The one finding that drives the raise

Almost everything sandbox-buildable is **built** (1117 tests; 8 post-v0.7 frameworks). What remains is
**not code** — it is real-world validation. And nearly all of it collapses onto **three repeated gates**:

| Gate | What it means | How many features need it |
|---|---|---|
| **G1 — Partner-in-production** | A deployment partner runs the surface in production for **one quarter** without a contract-shape change | **all 6** provisional frameworks + multi-modal |
| **G2 — Real-incident detection** | The surface catches a **real** failure (firmware regression, fleet drift, recall replay, kernel divergence) — not a synthetic one | 5 of 6 |
| **G3 — External auditor sign-off** | TÜV / SGS / DEKRA-equivalent (or AUTOSAR/CycloneDX validator) signs the artifact | **all 6** |

**Implication for the raise:** the entire 77-symbol `PROVISIONAL_API` surface is gated on a *small* set of
real-world inputs — **1–3 design partners + one auditor engagement + one real dataset.** You are not buying
engineering; you are buying *evidence*. That is the seed story, and the Series-A gate (§6.8, one production
reference) is the same input by another name.

---

## Part A — Provisional→Stable: what unblocks each shipped framework

Every framework below is **implemented and tested**; only the graduation evidence is pending. (✅ = already
in-tree; ⛳ = needs the external input named.)

| Framework (provisional symbols) | Roadmap | Pending to graduate to STABLE | Gate type |
|---|---|---|---|
| **Safety state machine** (9) | §9 #1 | ⛳ **3** deployment partners ×1 quarter · ✅ `state_transition_consistency` grid family (in-tree) · ⛳ TÜV review of ASIL table | G1 ×3, G3 |
| **ROS 2 / DDS / SBOM** (12) | §9 #2 | ⛳ 1 partner runs `BCVFNode` in prod ×1 quarter · ⛳ 1 partner accepts SBOM into procurement · ⚙️ RTI Connext + FastDDS interop · ⚙️ colcon build under Humble + Jazzy · ⛳ auditor CycloneDX 1.5 validation | G1, G3, +eng |
| **Replay framework** (10) | §9 #3 | ⛳ 1 partner uses bundle as primary recall artifact ×1 quarter · ⛳ real-recall bit-identity replay · ⛳ Class-A divergence across a real kernel change · ⚙️ signed bundle integrity field · ⛳ auditor sign-off on bundle JSON shape | G1, G2, G3, +eng |
| **Real-time / p999 budget** (7) | §9 #4 | ⛳ 1 AUTOSAR-class partner ×1 quarter · ⚙️ real 10⁶-tick load test · ⚙️ C++-port equivalence within 2× · ⛳ TÜV sign-off on percentile reporting · ⚙️ configurable persistence for over-budget log | G1, G3, +eng |
| **Calibration + drift** (9) | §9 #6 | ⛳ 1 partner on a fleet **≥10 vehicles** ×1 quarter · ⛳ real fleet-drift detection across a known mismatch · ⚙️ signed bundle field (partner key) · ⛳ auditor sign-off on JSON shape · ⛳ `expected_metrics` schema stabilised across **≥3** partners | G1, G2, G3, +eng |
| **Sensor attestation** (10) | §9 #8 | ⛳ 1 partner ×1 quarter against **HSM/TPM** key-resolver · ⛳ real attestation-failure across a firmware regression · ⚙️ asymmetric (ECDSA/X.509) extension subclass · ⛳ auditor sign-off as UN ECE R155 §7.3.4 evidence · ⚙️ replay-cache persistence (cross-process nonce dedup) | G1, G2, G3, +eng |
| **Multi-modal predictors** (6) | (design) | ⛳ a partner exercises **lane-frame predictors** in prod ×1 quarter (= needs the HD-map predictor, row #5) | G1 |

---

## Part B — Pending to BUILD (no customer needed — pure execution)

These are the ⚙️ items above plus the open roadmap rows. None is open research; all have known dependencies.

| Item | Dependency | Effort (brief est.) |
|---|---|---|
| **nuScenes-mini pilot** — fill `datasets/nuscenes.py` + M1–M4 real predictor wrappers → re-run the unchanged pilot runner | **dataset access only** (no customer) | ~3–4 wks |
| **ROS 2 adapter execution** — `.msg` + colcon + real `rclpy` pub/sub + Nav2 CriticPlugin + rosbag test | ROS 2 Humble/Jazzy **environment** | ~3–4 wks |
| **Kernel-side vectorization** — BCVF kernel + MPPI perf-cost (now the dominant latency cost; unblocks 50/100 Hz) | none | scoped |
| **Consumer V2 threshold recalibration** — design correct, calibration wrong for autonomy magnitudes (3 paths in Q2) | measured BCVF magnitudes | ~1 wk |
| **Production-substrate latency** — re-run sweep on TDA4VH / Orin / EPYC | **hardware samples** | 1–2 days/target |
| **HD-map predictor** (row #5) — validates the multi-modal scaffold against a real stack | real predictor stack | 3–4 wks |
| **Persistence / signing / crypto leftovers** — signed replay+calibration bundle fields; over-budget-log persistence; asymmetric attestation; replay-cache persistence | none | small each |
| **C++ port** — the honest surface for a real no-allocation RT guarantee | none | larger |
| **§6.3 parity audit** — re-run S3_accel on post-refactor branch | none | ~25 min |
| **Hierarchical/group BCVF** (row design-only) — only when M > 4–6 predictors; gated on 3 criteria | deferred | research-tier |
| **Domain predictors** (row #9) — learned / V2V / VRU | real stacks + per-engagement | 3–4 wks each |

---

## Part C — Needs a CUSTOMER / partner / auditor (the critical path)

| Need | Unblocks | Brief milestone |
|---|---|---|
| **1st design partner** (adjacent domain — drone / warehouse / industrial) | G1 for most frameworks; multi-modal; fleet harness at real scale | Q3 |
| **Fleet ≥10 vehicles** (can be the same partner) | calibration drift graduation; real fleet aggregation | Q3–Q4 |
| **AUTOSAR-class partner** | real-time budget graduation | Q2–Q3 |
| **1st external integrator** (Nav2/Autoware drop-in confirm) | ROS 2 adapter acceptance | Q2 |
| **External auditor engagement** (TÜV/SGS/DEKRA + CycloneDX validator) | G3 for **all** frameworks; regulator workshop | Q3 |
| **§6.8 production reference** | the **Series-A gate** itself | Q4 |

---

## Bottom line

- **Buildable now (Part B):** the whole list is mechanical/known-dependency — most valuable single move is the
  **nuScenes pilot**, which needs only *dataset access*, not a customer, and converts "1117 internal tests"
  into a real-data result.
- **Customer-gated (Parts A + C):** **1–3 design partners + one auditor + one fleet** graduate ~all 77
  provisional symbols **and** clear the Series-A gate. The gates are repetitive by design — landing the first
  partner unlocks a disproportionate share of the surface.
- **Strategic risk to manage:** the stack is **over-built relative to market pull** (six frameworks shipped
  before one real deployment). Frame Part B as "procurement-ready on day one"; spend the raise on Part C, not
  more frameworks.

*Settled negatives — do not fund: LLM-domain transfer (clean null), Consumer-V2-as-default (non-promotion),
dynamic-exclusion variant (rejected), the S3 3-catastrophe floor (structural).*
