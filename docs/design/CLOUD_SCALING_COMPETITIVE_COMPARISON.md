# Neural Cloud Scaling Controller — Competitive Comparison Guide

**Document Version:** 1.0
**Date:** March 2026
**Status:** Competitive Intelligence
**Classification:** Architecture + Market Analysis

---

## Executive Summary

This document compares SymbolU's Neural Cloud Scaling Controller against the three dominant Kubernetes scaling solutions — **Cast AI**, **ScaleOps**, and **Karpenter** — and defines the 8-layer control stack that separates concerns from raw metric sensing through business policy governance.

**Key finding:** These tools are not direct competitors. They operate at different layers of a scaling stack. Cast AI optimizes cost (Layer 2), Karpenter provisions nodes (Layer 1), ScaleOps predicts load (Layer 3). Our controller occupies **Layer 4 — Decision Quality** — the only layer that asks *"should we scale?"* using multi-signal coherence, deployment awareness, and identity-based anomaly detection.

No competing product provides coherence-gated decision synthesis. Every competitor uses either fixed thresholds (Cast AI, Karpenter) or black-box ML (ScaleOps). Our controller is the first to derive scaling decisions from a consistency-constrained control equation with full explainability.

### What This Controller Is

```
Action_t = d_t · G_t · P_t · S_t

Where:
  S_t = multi-signal pressure (weighted across infra/app/business)
  P_t = plasticity gate (permission to act, based on stability + misalignment)
  G_t = adaptive gain (magnitude, modulated by coherence + time phase)
  d_t = damping (volatility suppression, baseline-relative)
```

Source: `symbolu/cloud_controller/controller.py:231`

### What This Controller Is Not

- Not a node provisioner (Karpenter does that)
- Not a cost optimizer (Cast AI does that)
- Not a traffic predictor (ScaleOps does that)
- Not a replacement for Prometheus/CloudWatch (it wraps them)

It replaces the **decision logic** between sensing and actuation — the part that decides whether a CPU spike means "add pods" or "ignore, it's a batch job."

---

## External Review Evaluation

An external architecture review (ChatGPT) evaluated the 8-layer stack and provided critique. Below is a point-by-point assessment of each claim against the actual codebase.

### Points That Are Correct

| Claim | Verdict | Evidence |
|-------|---------|----------|
| Layer 4 is the correct position for the controller | **Correct** | The controller sits between sensing (L0) and safety bounds (L5), exactly where decision synthesis belongs |
| Stack cleanly separates data plane (L0-L2), intelligence plane (L3-L4), governance plane (L5-L7) | **Correct** | This maps to control systems theory: plant → controller → constraints |
| Layer 2 (Cost) is orthogonal, not strictly sequential | **Correct** | Cost optimization constrains decisions rather than feeding them sequentially. It should be treated as a constraint overlay |
| Layer 3 (Prediction) is augmentative, not foundational | **Correct** | Reactive control (our system) does not require prediction for stability. Prediction improves proactive scaling but is optional |
| Layer 6 (Observability) enables learning, trust, and enterprise adoption | **Correct** | Shadow mode (`shadow/runner.py`, `shadow/divergence.py`, `shadow/reporter.py`) is specifically built for this |
| Missing: feedback loop from L6 → L4 for parameter tuning | **Partially correct** | The replay buffer (`core/replay_buffer.py`) stores high-value incidents, but automated parameter tuning (L6 → L4 closed loop) is not yet implemented. Design doc Section 8, Stage 6 describes this as future work |

### Points That Are Wrong or Already Implemented

| Claim | Verdict | Reality in Codebase |
|-------|---------|-------------------|
| "Identity baseline is missing — should be its own layer" | **Already implemented** | `core/identity_ema.py` — full Identity EMA with fast accumulation loop, slow consolidation loop, conditional update rate (`α_eff = α_base · stability · agreement`), and bootstrap from historical data. It is a first-class module inside L4, not missing |
| "Coherence needs to exist as a state variable, not just computed" | **Already implemented** | `CoherenceResult` (`core/coherence.py:25-32`) carries `coherence`, `c_infra`, `c_app`, `c_business`, `c_cross`, `instability`, and `elevated_count` as persistent state through the pipeline. The `instability` field feeds directly into damping's `U_ema` (asymmetric EMA with temporal smoothing) |
| "Add temporal smoothing and multi-timescale coherence" | **Already implemented** | Damping uses asymmetric EMA (α_up=0.10 for spike detection, α_down=0.20 for recovery) on coherence instability (`core/damping.py:87-90`). Identity EMA operates on two timescales: fast accumulation every cycle, slow consolidation every 240 cycles (`core/identity_ema.py:52-73`, `75-147`) |
| "Replace 'decision' with 'consistency-constrained control synthesis'" | **Terminology upgrade only** | The math is already `A_t = d_t · G_t · P_t · S_t` with P_t gating on system consistency (resistance + misalignment). Calling it "consistency-constrained control synthesis" is accurate labeling of what already exists, not a missing feature |
| "Add BCVF-driven control formulation" | **Not applicable to cloud controller** | BCVF (Bilinear Coherence Validation Framework) exists in the training subsystem (`tests/test_validate_bcvf_signal.py`, `tests/test_bcvf_benchmarks.py`) but operates on neural network hidden states, not infrastructure metrics. The cloud controller's coherence model (`core/coherence.py`) is the infrastructure analog — same principle (multi-signal agreement gating), different domain |

### Summary of External Review

| Category | Count |
|----------|-------|
| Structurally correct observations | 6 |
| Claimed missing but already implemented | 4 |
| Genuine gaps identified | 1 (L6 → L4 feedback loop) |
| Terminology improvements (valid but cosmetic) | 1 |
| Domain confusion (training vs cloud) | 1 |

**Bottom line:** The external review validated the architecture correctly but underestimated what was already built. The one genuine gap — automated parameter tuning via the learning loop — is planned for Stage 6 of the implementation roadmap.

---

## The 8-Layer Cloud Scaling Control Stack

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    GOVERNANCE PLANE                                │
│                                                                    │
│  L7  Business Policy         "WHO approves?"                      │
│       recommend/approval.py   Human-in-the-loop, budget gates     │
│       recommend/webhook.py    Slack/PagerDuty/OpsGenie dispatch   │
│                                                                    │
│  L6  Observability & Proof   "WAS it right?"                      │
│       shadow/divergence.py    Counterfactual divergence tracking   │
│       shadow/reporter.py      Weekly proof-of-value reports       │
│       shadow/hpa_watcher.py   HPA action observation              │
│                                                                    │
│  L5  Safety Bounds           "HOW MUCH is allowed?"               │
│       recommend/safety.py     Rate limits, min/max, cooldown      │
│       recommend/confidence.py Confidence-gated recommendations    │
│                                                                    │
├──────────────────────────────────────────────────────────────────┤
│                   INTELLIGENCE PLANE                               │
│                                                                    │
│  L4  Decision Quality        "SHOULD we scale?"         ← CORE   │
│       controller.py           A_t = d_t · G_t · P_t · S_t        │
│       core/plasticity_gate.py Permission gate (stability-aware)   │
│       core/adaptive_gain.py   Magnitude (coherence-modulated)     │
│       core/damping.py         Volatility suppression              │
│       core/coherence.py       Multi-signal agreement scoring      │
│       core/identity_ema.py    Baseline learning ("what is normal")│
│       core/replay_buffer.py   Priority-weighted incident memory   │
│                                                                    │
│  L3  Prediction              "WHEN will we need to scale?"        │
│       (Not yet built)         Forecasting, seasonal patterns      │
│       ScaleOps occupies this  Proactive, not reactive             │
│                                                                    │
├──────────────────────────────────────────────────────────────────┤
│                      DATA PLANE                                    │
│                                                                    │
│  L2  Cost Optimization       "WHAT instance type?"                │
│       (Constraint overlay)    Right-sizing, spot instances         │
│       Cast AI occupies this   Orthogonal to decision logic        │
│                                                                    │
│  L1  Provisioning            "HOW to get the node?"               │
│       (Actuation substrate)   Bin-packing, node launch            │
│       Karpenter occupies this Our controller wraps, not replaces  │
│                                                                    │
│  L0  Sensing                 "WHAT is happening?"                 │
│       signals/prometheus.py   Prometheus HTTP client + PromQL     │
│       signals/normalizer.py   Raw → [0,1] via z-score + sigmoid  │
│       signals/pipeline.py     Polling loop + phase schedule       │
│                                                                    │
└──────────────────────────────────────────────────────────────────┘
```

### Plane Classification

| Plane | Layers | Purpose | Nature |
|-------|--------|---------|--------|
| **Data Plane** | L0, L1, L2 | Sense, provision, optimize resources | Infrastructure |
| **Intelligence Plane** | L3, L4 | Predict and decide | Control logic |
| **Governance Plane** | L5, L6, L7 | Bound, verify, approve | Policy + trust |

This maps to control systems theory:
- **Data Plane** = plant (the thing being controlled)
- **Intelligence Plane** = controller (the decision maker)
- **Governance Plane** = constraints (what the controller is not allowed to do)

### Layer-by-Layer Specification

---

### Layer 0 — Sensing

**Question answered:** "What is happening right now?"

**Codebase location:** `symbolu/cloud_controller/signals/`

**Components:**

| File | Purpose | Key Detail |
|------|---------|------------|
| `prometheus.py` | Prometheus HTTP client | Instant + range queries, retry logic, PromQL injection prevention |
| `normalizer.py` | Raw metrics → [0, 1] | Z-score + sigmoid for unbounded metrics, direct ratio for bounded |
| `pipeline.py` | Polling orchestrator | 15s cycles, phase schedule, bootstrap from historical data |

**Normalization strategy:**

```
Z-score metrics (CPU, latency, queue depth):
  z = (value - rolling_mean) / rolling_std
  normalized = sigmoid(k · z)    # k per-metric (CPU sharper, queue softer)

Ratio metrics (memory, error rate):
  normalized = clamp((value - low) / (high - low), 0, 1)
```

Source: `signals/normalizer.py:225-281`

**Bootstrap capability:** Pre-seeds rolling windows from Prometheus `range_query` history so z-score normalization is accurate from cycle 1. Eliminates the cold-start problem where the first `min_samples` cycles return 0.5 (useless midpoint).

Source: `signals/normalizer.py:310-340` (added in bootstrap implementation)

**What competitors do at this layer:**
- Cast AI: Proprietary agent on each node, polls kubelet
- ScaleOps: Proprietary collector, streams to their cloud
- Karpenter: No sensing — reacts to pending pod events only

**Our advantage:** Open, pluggable, self-calibrating. No proprietary agent required.

---

### Layer 1 — Provisioning

**Question answered:** "How do we get the compute resources?"

**Our position:** We **wrap**, not replace. The controller outputs a replica delta (+N or -N). The underlying provisioner (HPA, ASG, Karpenter) handles actual pod/node creation.

**Integration options** (from design doc Section Stage 5):

| Option | How | Risk Level |
|--------|-----|-----------|
| **A: Custom Metrics Adapter** | Controller exposes `action_score` as Prometheus metric → HPA scales on it | Low — HPA still manages lifecycle |
| **B: Direct Replica Patching** | Controller PATCHes `apps/v1/deployments/{name}/scale` directly | Medium — HPA disabled or as safety net |

**What occupies this layer:**

| Tool | Mechanism | Strength |
|------|-----------|----------|
| **Karpenter** | Watches pending pods → finds cheapest node type → launches | Fast provisioning, spot-aware, bin-packing |
| **Cluster Autoscaler** | Watches pending pods → scales node groups | Simpler, cloud-provider integrated |
| **AWS ASG / Azure VMSS** | Manual rules or HPA target tracking | Native but basic |

---

### Layer 2 — Cost Optimization

**Question answered:** "What is the cheapest way to meet this demand?"

**Our position:** Not built. Intentionally out of scope. This layer is **orthogonal** — it constrains how provisioning happens, not whether scaling should happen.

**Why orthogonal:** A cost optimizer might say "use spot instances" or "use smaller nodes." That doesn't affect whether scaling is needed — it affects the implementation of a scaling decision that was already made at L4.

**What occupies this layer:**

| Tool | Mechanism | Strength |
|------|-----------|----------|
| **Cast AI** | Analyzes workload, recommends instance types, moves pods to cheaper nodes | Deep cloud provider integration, real savings |
| **Kubecost** | Cost allocation, right-sizing recommendations | Observability-focused, no actuation |
| **Spot.io (NetApp)** | Spot instance management, rebalancing | Pure cost play |

---

### Layer 3 — Prediction

**Question answered:** "When will we need to scale?"

**Our position:** Not yet built. Planned for Stage 6 (design doc Section 8). The replay buffer (`core/replay_buffer.py`) stores high-value incidents that will feed Bayesian parameter tuning and pattern recognition.

**Why optional:** Reactive control (our system) is stable without prediction. The control equation `A_t = d_t · G_t · P_t · S_t` responds to current state. Prediction would allow **proactive** scaling (adding capacity before load arrives), which improves latency but is not required for correctness.

**What occupies this layer:**

| Tool | Mechanism | Strength |
|------|-----------|----------|
| **ScaleOps** | ML model trained on historical traffic patterns | Pre-scales before peak, reduces latency |
| **Datadog Forecasts** | Statistical forecasting on metric streams | Integrated with alerting |
| **KEDA** | Event-driven (queue depth, cron triggers) | Simple, predictable |

---

### Layer 4 — Decision Quality (Core Innovation)

**Question answered:** "Should we scale, and by how much?"

**Codebase location:** `symbolu/cloud_controller/controller.py`, `symbolu/cloud_controller/core/`

This is the layer that no competitor occupies. It is the **only** layer that synthesizes multi-signal coherence, system stability, deployment awareness, and identity-based anomaly detection into a single explainable decision.

**The core equation:**

```
Action_t = d_t · G_t · P_t · S_t
```

**Component breakdown:**

| Symbol | Module | What It Does | Key Property |
|--------|--------|-------------|--------------|
| `S_t` | `controller.py:283-307` | Weighted pressure across infra (0.4), app (0.4), business (0.2) | Error rate inverted: low errors ≠ over-provisioned |
| `P_t` | `core/plasticity_gate.py` | `sigmoid(k_r·R_t - k_m·M_t + b_p)` — permission to act | Double-smoothed EMA prevents flicker. Floor at sigmoid(-1) ≈ 0.27 — gate never fully closes |
| `G_t` | `core/adaptive_gain.py` | `clip(G_base · f_phase · f_coh, G_min, G_max)` — how aggressively | Rate-limited ±10% per cycle. Phase-aware (peak/off-peak/maintenance). Bootstrap skips warmup |
| `d_t` | `core/damping.py` | `exp(-k_dv·V_excess - k_dc·U_ema)` — suppress if volatile | Baseline-relative (won't permanently damp high-variance systems). Asymmetric EMA (fast detect, fast recover) |
| `C_t` | `core/coherence.py` | Multi-signal agreement: within-group (70%) + cross-group (30%) | Incoherent pressure (only CPU high) is suppressed |
| `B_t` | `core/identity_ema.py` | Adaptive baseline — learns what "normal" looks like | Conditional update: `α_eff = α_base · stability · agreement`. Anomalies don't corrupt baseline |
| Replay | `core/replay_buffer.py` | Priority-weighted incident memory | TTL-bounded, evicts lowest priority (not FIFO) |

**What no competitor has:**

1. **Coherence gating** — CPU spike with flat latency/errors/queue? Suppressed. Cast AI would scale anyway.
2. **Deployment awareness** — Active rollout? Plasticity gate closes. Prevents scaling into a broken deploy.
3. **Identity baseline** — System learned that "this cluster normally runs at 60% CPU." A 65% spike is normal; an 85% spike is anomalous. Fixed thresholds can't distinguish.
4. **Explainable decisions** — Every action decomposed into pressure, coherence, stability, plasticity, gain, damping. `result.explain()` produces a human-readable breakdown.

---

### Layer 5 — Safety Bounds

**Question answered:** "How much scaling is allowed?"

**Codebase location:** `symbolu/cloud_controller/recommend/safety.py`, `symbolu/cloud_controller/recommend/confidence.py`

**Hard limits (always enforced, even after human approval):**

| Bound | Value | Source |
|-------|-------|--------|
| Max scale-out per action | +50% of current replicas | `safety.py:22` |
| Max scale-in per action | -25% of current replicas | `safety.py:24` |
| Minimum replicas | Never below `min_replicas` | `safety.py:26` |
| Cooldown after action | 120 seconds observation period | `safety.py:28` |

Source: `recommend/safety.py:57-155`

**Confidence gating (only recommend when signals are strong):**

| Level | Action Score | Coherence | Behavior |
|-------|-------------|-----------|----------|
| NONE | ≤ 0.3 | ≤ 0.5 | No recommendation sent |
| LOW | > 0.3 | > 0.5 | Recommend with caveats |
| MEDIUM | ≥ 0.5 | ≥ 0.65 | Standard recommendation |
| HIGH | ≥ 0.7 | ≥ 0.8 | High-confidence recommendation |

Source: `recommend/confidence.py:31-42`

**Continuous safety properties (inside L4):**

| Property | Mechanism | Source |
|----------|-----------|--------|
| Plasticity floor | `sigmoid(b_p=-1.0) ≈ 0.27` — gate never fully closes | `core/plasticity_gate.py` |
| Gain rate limiting | Max ±10% of G_base per cycle | `core/adaptive_gain.py:100` |
| Damping rate limiting | Max ±0.1 per cycle | `core/damping.py:123-130` |
| Damping hard floor | `d_t ≥ 0.01` — never fully suppresses | `core/damping.py:118` |

**What competitors do:** Cast AI has basic cooldowns and max node limits. Karpenter has `maxPods` and `nodepool` limits. Neither has continuous, coherence-aware safety bounds.

---

### Layer 6 — Observability & Proof

**Question answered:** "Was the decision correct?"

**Codebase location:** `symbolu/cloud_controller/shadow/`

This layer is the **sales demo**. It runs the controller alongside existing HPA with zero write permissions, logs every divergence, assigns verdicts after a 5-minute lookback, and generates weekly proof-of-value reports.

**Components:**

| File | Purpose | Key Detail |
|------|---------|------------|
| `shadow/runner.py` | Orchestrates shadow mode pipeline | Polls metrics, runs controller, compares to HPA, optional recommend engine |
| `shadow/hpa_watcher.py` | Observes K8s HPA scaling events | Detects `desired_replicas` changes, maintains 2000-snapshot history |
| `shadow/divergence.py` | Records and evaluates disagreements | 5 divergence types, 5 verdict outcomes, cost estimation |
| `shadow/reporter.py` | Generates proof-of-value reports | Agreement rate, controller advantage, estimated savings |

**Divergence types:**

| Type | Meaning |
|------|---------|
| `HPA_SCALES_CONTROLLER_HOLDS` | HPA aggressive, controller cautious |
| `CONTROLLER_SCALES_HPA_HOLDS` | Controller ahead of HPA |
| `OPPOSITE_DIRECTION` | Disagree on scale-in vs scale-out |
| `MAGNITUDE_DIFFERS` | Same direction, different amounts |
| `AGREEMENT` | Both agree |

**Verdict assignment** (after 5-minute lookback):

| Scenario | Verdict |
|----------|---------|
| HPA scaled, metrics stayed stable | `CONTROLLER_CORRECT` — scaling was unnecessary |
| HPA scaled, metrics improved | `HPA_CORRECT` — scaling helped |
| Controller recommended, metrics degraded | `CONTROLLER_CORRECT` — earlier scaling would have helped |
| Controller recommended, metrics improved without action | `HPA_CORRECT` — no scaling was needed |

Source: `shadow/divergence.py:272-388`

**Important limitation** (stated in source):
> Verdicts are based on correlation, not causation. Treat verdicts as directional signals for human review, not ground truth.

Source: `shadow/divergence.py:15-21`

**Example weekly report output:**

```
Neural Cloud Controller — Shadow Report (Week 13, 2026)
  Total decisions:              2,016
  Agreements with HPA:          1,847 (91.6%)
  Divergences:                  169

  --- Verdicts ---
  Controller correct:           95
  HPA correct:                  37
  Both reasonable:              12
  Inconclusive:                 25

  --- Impact ---
  Net improvement:              +58 better decisions
  Estimated cost savings:       $847.00
```

Source: `shadow/reporter.py:74-105`

**What competitors have:** Cast AI shows cost savings dashboards. ScaleOps shows prediction accuracy. Neither provides divergence-tracked counterfactual analysis with per-decision verdicts.

---

### Layer 7 — Business Policy

**Question answered:** "Who decides, and under what rules?"

**Codebase location:** `symbolu/cloud_controller/recommend/`

**Three operating modes** (graduated autonomy):

| Mode | Behavior | Target |
|------|----------|--------|
| **Observe** | Log decisions, no execution | First adoption, POC |
| **Approve** | Webhook notification, human confirms | Enterprise, regulated |
| **Autonomous** | Direct API calls within bounds | Mature customers |

**Approval lifecycle:**

```
PENDING → APPROVED → (executed + cooldown)
PENDING → DISMISSED
PENDING → EXPIRED (after 600s TTL)
```

Source: `recommend/approval.py`

**Notification targets:**

| Target | Formatter | Source |
|--------|-----------|--------|
| Slack | `SlackFormatter` | `recommend/webhook.py` |
| PagerDuty | `PagerDutyFormatter` | `recommend/webhook.py` |
| OpsGenie | `OpsGenieFormatter` | `recommend/webhook.py` |
| Generic HTTP | Raw JSON payload | `recommend/webhook.py` |

**What competitors have:** Cast AI has auto vs manual modes. Karpenter is always autonomous. ScaleOps has a recommendation dashboard. None provides the graduated Observe → Approve → Autonomous path with confidence-gated notification filtering.
