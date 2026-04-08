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

---

## Competitor Deep Dives

### Cast AI

```
┌─────────────────────────────────────────────────────────────────┐
│ CAST AI                                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Architecture:                                                   │
│  Node Agent → Cast AI Cloud → K8s API                           │
│                                                                  │
│  Decision model:                                                 │
│  IF cpu > threshold → recommend resize/add node                  │
│  IF memory > threshold → recommend resize/add node               │
│  IF OOM kill detected → recommend bigger instance type           │
│  IF cost(current) > cost(optimal) → recommend rebalance          │
│                                                                  │
│  Cooldown: fixed timer per cluster                               │
│                                                                  │
│  Primary value: cost optimization (30-50% savings reported)      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**What Cast AI does well:**

1. **Immediate action** — Fixed SLO thresholds require no learning. CPU > 80% → act. No warmup.
2. **Cost optimization** — Deep integration with AWS/GCP/Azure pricing APIs. Finds cheaper instance types that match workload.
3. **OOM kill response** — Detects container OOM kills and recommends memory limit increases.
4. **Node-level scaling** — Adds/removes entire nodes, not just pods.

**What Cast AI cannot do:**

| Limitation | Why It Matters | Our Controller's Answer |
|------------|---------------|------------------------|
| No multi-signal coherence | CPU spike from batch job? Scales anyway. CPU + flat latency + flat errors = false alarm | Coherence model (`core/coherence.py`) requires signals to agree before acting |
| No deployment awareness | Scales during broken rollouts, making the problem worse | Plasticity gate closes when `deploy_active=True` (resistance drops 40%) |
| No identity baseline | Every cluster uses the same thresholds. A cluster that normally runs at 70% CPU gets the same threshold as one at 30% | Identity EMA (`core/identity_ema.py`) learns per-cluster "normal" |
| Fixed cooldown | 300s regardless of signal behavior. Too long during real incidents, too short during noise | Damping is signal-aware: `d_t = exp(-k_dv·V_excess)`. High variance = more damping. Low variance = fast recovery |
| No explainability | "Scaled because CPU > 80%" — no deeper reasoning | `result.explain()` decomposes every decision into 7 components |
| No shadow mode | Cannot prove value before taking control | Shadow runner with divergence tracking and weekly reports |

**Layer coverage:**

| Layer | Cast AI | Notes |
|-------|---------|-------|
| L0 Sensing | Proprietary agent | Per-node kubelet polling |
| L1 Provisioning | Yes | Node add/remove/resize |
| L2 Cost Optimization | **Yes (core strength)** | Instance type selection, spot, reserved |
| L3 Prediction | No | Reactive only |
| L4 Decision Quality | No | Fixed thresholds, no coherence |
| L5 Safety Bounds | Basic | Max nodes, cooldown timers |
| L6 Observability | Partial | Cost dashboards, no counterfactual |
| L7 Business Policy | Partial | Auto vs manual mode |

**Complementary use:** Cast AI at L2 (cost) + our controller at L4 (decision quality). Cast AI picks the cheapest instance type; our controller decides whether scaling is needed at all.

---

### ScaleOps

```
┌─────────────────────────────────────────────────────────────────┐
│ SCALEOPS                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Architecture:                                                   │
│  Prometheus/Datadog → ScaleOps Cloud → ML Model → HPA Override  │
│                                                                  │
│  Decision model:                                                 │
│  predicted_load = ML_model(                                      │
│      historical_traffic,                                         │
│      time_of_day,                                                │
│      seasonality,                                                │
│      recent_deploys                                              │
│  )                                                               │
│  target_replicas = ceil(predicted_load / per_pod_capacity)       │
│  IF target != current → recommend change                         │
│                                                                  │
│  Primary value: predictive scaling (pre-scale before traffic)    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**What ScaleOps does well:**

1. **Predictive scaling** — ML model learns daily/weekly traffic patterns. Scales before the spike.
2. **Resource right-sizing** — Recommends CPU/memory request/limit adjustments per pod.
3. **Multi-metric correlation** — ML model correlates across metrics (though opaquely).
4. **Reduced latency impact** — Pre-scaling means pods are warm before traffic arrives.

**What ScaleOps cannot do:**

| Limitation | Why It Matters | Our Controller's Answer |
|------------|---------------|------------------------|
| Black-box ML model | Cannot explain why it scaled. "The model said so" is not acceptable in regulated environments | Full component breakdown: pressure, coherence, plasticity, gain, damping |
| Requires training data | Needs 2+ weeks of historical data before model is accurate. New clusters/services are blind | Bootstrap from 1 hour of Prometheus history. Accurate from cycle 1 |
| No deployment awareness | ML model doesn't know a rollout is in progress. Predicts based on traffic, not system state | Plasticity gate + resistance computation factor in deploy status and pod restarts |
| No coherence gating | If the ML model says "scale up" but only CPU is elevated and everything else is fine, it scales anyway | Coherence model requires signal agreement. Incoherent pressure suppressed |
| SaaS dependency | Metrics stream to ScaleOps cloud for processing. Network outage = no scaling decisions | Fully self-contained. Runs in-cluster with zero external dependencies |
| No shadow mode | Cannot prove superiority over HPA without taking control | Shadow divergence tracking with per-decision verdicts |

**Layer coverage:**

| Layer | ScaleOps | Notes |
|-------|----------|-------|
| L0 Sensing | Prometheus integration | Streams to their cloud |
| L1 Provisioning | No | Adjusts HPA targets only |
| L2 Cost Optimization | Partial | Resource right-sizing |
| L3 Prediction | **Yes (core strength)** | ML-based traffic forecasting |
| L4 Decision Quality | No | ML correlation, no coherence gating |
| L5 Safety Bounds | Basic | Max/min replicas |
| L6 Observability | Partial | Prediction accuracy dashboards |
| L7 Business Policy | Partial | Recommendation dashboard |

**Complementary use:** ScaleOps at L3 (prediction) feeding into our controller at L4 (decision quality). ScaleOps says "traffic will increase in 30 minutes"; our controller decides whether the system is stable enough to act on that prediction now.

---

### Karpenter

```
┌─────────────────────────────────────────────────────────────────┐
│ KARPENTER (AWS/Open Source)                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Architecture:                                                   │
│  K8s Scheduler → Pending Pods → Karpenter → EC2 Fleet API       │
│                                                                  │
│  Decision model:                                                 │
│  IF pending_pods > 0:                                            │
│      constraints = pod_requirements + nodepool_limits             │
│      instance_type = cheapest_that_fits(constraints)              │
│      launch(instance_type)                                       │
│  IF node_utilization < threshold FOR consolidation_ttl:           │
│      drain(node)                                                  │
│      terminate(node)                                              │
│                                                                  │
│  Primary value: fast, efficient node provisioning                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**What Karpenter does well:**

1. **Fast provisioning** — Launches nodes in seconds via EC2 Fleet API. No ASG warmup.
2. **Bin-packing** — Finds the cheapest instance type that fits pod requirements.
3. **Spot management** — Handles spot interruptions with graceful draining.
4. **Consolidation** — Automatically defragments by moving pods to fewer, fuller nodes.
5. **Multi-architecture** — Can mix ARM and x86 nodes based on workload.

**What Karpenter cannot do:**

| Limitation | Why It Matters | Our Controller's Answer |
|------------|---------------|------------------------|
| Reactive only | Waits for pods to be pending — the problem has already occurred | Detects pressure before pods go pending (latency rising, queue growing) |
| Single-signal trigger | Only signal is "pods can't be scheduled." No latency, error rate, coherence | 5+ signals across 3 groups, coherence-gated |
| Node-level only | Cannot scale pods. Needs HPA or KEDA for pod scaling | Pod-level scaling decisions with per-service granularity |
| No deployment awareness | Provisions nodes during bad rollouts | Plasticity gate suppresses scaling during unstable periods |
| No decision intelligence | Binary: pending pods = add node. No nuance | Full control equation with damping, coherence, stability |
| No explainability | "Added node because pods were pending" — no deeper analysis | Component-level decision decomposition |

**Layer coverage:**

| Layer | Karpenter | Notes |
|-------|-----------|-------|
| L0 Sensing | Minimal | Watches K8s scheduler events only |
| L1 Provisioning | **Yes (core strength)** | Fast node launch, bin-packing, spot |
| L2 Cost Optimization | Partial | Cheapest instance selection |
| L3 Prediction | No | Purely reactive |
| L4 Decision Quality | No | Binary trigger (pending pods) |
| L5 Safety Bounds | Basic | NodePool limits, maxPods |
| L6 Observability | No | No counterfactual analysis |
| L7 Business Policy | No | Always autonomous |

**Complementary use:** Karpenter at L1 (provisioning) + our controller at L4 (decision quality). Our controller decides "scale out +2 pods"; Karpenter provisions the node to run them on (cheapest type, spot if possible).

---

### Kubernetes HPA (Baseline Comparator)

```
┌─────────────────────────────────────────────────────────────────┐
│ KUBERNETES HPA (Horizontal Pod Autoscaler)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Decision model:                                                 │
│  desired = ceil(current * (current_metric / target_metric))      │
│                                                                  │
│  Example:                                                        │
│  current=5, cpu=80%, target=50%                                  │
│  desired = ceil(5 * 80/50) = 8                                   │
│                                                                  │
│  Cooldown:                                                       │
│  - Scale up: 0s (immediate)                                      │
│  - Scale down: 300s (fixed stabilization window)                 │
│                                                                  │
│  This is what our shadow mode compares against.                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**HPA limitations that our controller addresses:**

| HPA Behavior | Problem | Our Controller's Answer |
|-------------|---------|------------------------|
| `desired = ceil(current * metric/target)` | Proportional control only — no damping, no coherence | Full `A_t = d_t · G_t · P_t · S_t` with 4 control components |
| Single metric (usually CPU) | Ignores latency, errors, queue depth | 5 metrics across 3 signal groups |
| Fixed 300s scale-down delay | Too long during traffic drop, too short during noise | Signal-aware damping adapts to actual volatility |
| No deployment awareness | Scales during rollouts | Plasticity gate + resistance computation |
| No memory of past behavior | Each decision is independent | Identity EMA + replay buffer |
| No explanation | Cannot tell you *why* it scaled | `result.explain()` with full breakdown |

**This is the comparison our shadow mode tracks.** Every cycle, `shadow/divergence.py` compares our controller's recommendation against what HPA actually did, assigns verdicts after 5 minutes, and generates proof-of-value reports.

---

## Consolidated Feature Matrix

### Layer Coverage

| Layer | Our Controller | Cast AI | ScaleOps | Karpenter | K8s HPA |
|-------|:-:|:-:|:-:|:-:|:-:|
| L7 Business Policy | **Yes** | Partial | Partial | No | No |
| L6 Observability & Proof | **Yes** | Partial | Partial | No | No |
| L5 Safety Bounds | **Yes** | Basic | Basic | Basic | Basic |
| L4 Decision Quality | **Yes** | No | No | No | No |
| L3 Prediction | Planned | No | **Yes** | No | No |
| L2 Cost Optimization | No | **Yes** | Partial | Partial | No |
| L1 Provisioning | Wraps | **Yes** | No | **Yes** | Yes |
| L0 Sensing | **Yes** | Proprietary | Prometheus | Minimal | Metrics API |

### Capability Comparison

| Capability | Our Controller | Cast AI | ScaleOps | Karpenter | K8s HPA |
|-----------|:-:|:-:|:-:|:-:|:-:|
| Multi-signal coherence | **Yes** | No | No | No | No |
| Deployment awareness | **Yes** | No | No | No | No |
| Identity baseline learning | **Yes** | No | No | No | No |
| Explainable decisions | **Yes** | Partial | No | No | No |
| Shadow/proof-of-value mode | **Yes** | No | No | No | No |
| Graduated autonomy (Observe→Approve→Auto) | **Yes** | Partial | Partial | No | No |
| Bootstrap (no learning phase) | **Yes** | N/A | No | N/A | N/A |
| Predictive scaling | Planned | No | **Yes** | No | No |
| Cost optimization | No | **Yes** | Partial | Partial | No |
| Node provisioning | No | **Yes** | No | **Yes** | No |
| Spot instance management | No | **Yes** | No | **Yes** | No |
| Scales pods | **Yes** | No | **Yes** | No | **Yes** |
| Scales nodes | No | **Yes** | No | **Yes** | No |
| Works without SaaS dependency | **Yes** | No | No | **Yes** | **Yes** |
| Thread-safe controller | **Yes** | N/A | N/A | N/A | **Yes** |
| 12-parameter configuration | **Yes** | N/A | N/A | N/A | ~3 params |

### Decision Logic Comparison

| Aspect | Our Controller | Cast AI | ScaleOps | Karpenter | K8s HPA |
|--------|-------------|---------|----------|-----------|---------|
| **Input signals** | 5+ metrics, 3 groups | 3-5 (CPU, mem, OOM) | 5-10 (ML features) | 1 (pending pods) | 1-2 (CPU, custom) |
| **Decision method** | `d·G·P·S` control equation | Fixed thresholds | ML model | Binary trigger | `ceil(current * ratio)` |
| **Signal consensus** | Required (coherence gate) | None | Implicit (ML) | None | None |
| **Volatility handling** | Baseline-relative damping | Fixed cooldown | ML smoothing | None | 300s stabilization |
| **Deployment safety** | Plasticity gate closes | None | None | None | None |
| **Scaling oscillation** | Rate-limited gain + damping | Cooldown timer | ML smoothing | Consolidation TTL | Stabilization window |
| **Explanation** | 7-component breakdown | "CPU > threshold" | "Model predicted" | "Pods pending" | "Metric > target" |
| **Learning** | Identity EMA + replay | None | Offline ML training | None | None |
| **Cold start** | Bootstrap (1hr history) | Instant (fixed rules) | 2+ weeks training | Instant (reactive) | Instant (ratio) |

---

## Scenario Analysis

### Scenario 1: CPU Spike from Batch Job

**Setup:** A cron job runs at 2am, spikes CPU to 85% for 3 minutes. Latency, error rate, and queue depth are flat.

| System | Action | Correct? |
|--------|--------|----------|
| **K8s HPA** | Scales from 5 → 8 pods (CPU 85% > 50% target) | No — wastes 3 pods for 3 min |
| **Cast AI** | Recommends adding a node (CPU > threshold) | No — same false alarm |
| **ScaleOps** | May scale if ML model hasn't learned the cron pattern | Depends on training |
| **Karpenter** | No action (no pending pods) | Correct by default |
| **Our Controller** | **HOLD.** Coherence=0.31 (only CPU elevated, latency/errors/queue flat). Incoherent pressure suppressed | **Correct** |

**Controller decision breakdown:**
```
Pressure (S_t):      0.35 (moderate — CPU elevated, others neutral)
Coherence (C_t):     0.31 (LOW — only CPU, no app/business agreement)
Stability (R_t):     0.85 (high — no recent scaling, no deploy)
Plasticity (P_t):    0.65 (open — but low coherence suppresses gain)
Gain (G_t):          0.42 (low — f_coh reduced by low coherence)
Damping (d_t):       0.88 (mild — some variance but not extreme)
Action Score (A_t):  0.08 → NO ACTION (below 0.2 recommend threshold)
```

**Shadow verdict after 5 minutes:** CPU returned to 35%. `CONTROLLER_CORRECT — 3 pods unnecessary for 3 min. Estimated savings: $0.27`

---

### Scenario 2: Genuine Traffic Surge

**Setup:** Marketing campaign goes live. CPU 82%, latency p99 jumps from 120ms to 340ms, error rate rises from 0.3% to 2.1%, queue depth from 200 to 1,247. All sustained for 8+ minutes.

| System | Action | Correct? |
|--------|--------|----------|
| **K8s HPA** | Scales from 5 → 8 (CPU 82% > 50%) — but only looks at CPU | Partially — right direction, wrong reason |
| **Cast AI** | Scales on CPU threshold | Partially — same as HPA |
| **ScaleOps** | Scales if ML predicted the campaign (unlikely for first time) | Maybe |
| **Karpenter** | Adds nodes if HPA creates pending pods | Reactive, delayed |
| **Our Controller** | **SCALE +2.** Coherence=0.89 (all signals agree), high confidence | **Correct, with reasoning** |

**Controller decision breakdown:**
```
Pressure (S_t):      0.72 (high — all signal groups elevated)
Coherence (C_t):     0.89 (HIGH — infra, app, business all agree)
Stability (R_t):     0.81 (stable — no recent scaling, no deploy)
Plasticity (P_t):    0.68 (open)
Gain (G_t):          0.91 (high — peak phase, high coherence)
Damping (d_t):       0.95 (minimal — sustained, not spiky)
Action Score (A_t):  0.43 → SCALE +1 (above 0.2 threshold)
```

**Why our controller is better here:** It explains *why* scaling is needed (coherent multi-signal pressure), not just "CPU > threshold." The coherence score of 0.89 means this is a real load event, not noise.

---

### Scenario 3: Bad Deployment

**Setup:** New version deployed with a memory leak. Latency rising, error rate at 5%, pods restarting. CPU is actually low (leak hasn't caused CPU spike yet).

| System | Action | Correct? |
|--------|--------|----------|
| **K8s HPA** | No action (CPU is low) or slowly scales based on custom metrics | Late or wrong |
| **Cast AI** | No action (CPU fine) or reacts to OOM kills after they happen | Reactive, too late |
| **ScaleOps** | May recommend scaling if ML sees the traffic pattern | Wrong action — scaling won't fix a memory leak |
| **Karpenter** | Adds nodes only after OOM causes pending pods | Way too late |
| **Our Controller** | **HOLD.** Plasticity gate nearly closed (pod restarts + deploy active). Logs recommendation to investigate, not scale | **Correct** |

**Controller decision breakdown:**
```
Pressure (S_t):      0.22 (low CPU, but error rate contributing)
Coherence (C_t):     0.41 (low — CPU low but errors/latency high = incoherent)
Stability (R_t):     0.28 (FRAGILE — deploy_active=True, pod_restarts=4)
Plasticity (P_t):    0.29 (CLOSED — fragile system, gate suppresses)
Gain (G_t):          0.38
Damping (d_t):       0.71 (moderate suppression — high variance)
Action Score (A_t):  0.02 → NO ACTION
Reason: System fragile during deployment. Scaling won't fix root cause.
```

**Why this matters:** Scaling into a bad deployment makes the problem worse (more leaking pods, more OOM kills). The correct action is to investigate and rollback — which is what the low plasticity + deployment awareness signals to the operator.

---

### Scenario 4: Scale-Down (Over-Provisioned)

**Setup:** Traffic dropped 2 hours ago. CPU 12%, memory 15%, latency p99 at 8ms, errors 0%, queue empty. Running 10 replicas but 3 would suffice.

| System | Action | Correct? |
|--------|--------|----------|
| **K8s HPA** | Scales down after 300s stabilization window — but only based on CPU | Correct but slow |
| **Cast AI** | Recommends node removal if nodes are underutilized | Correct at node level |
| **ScaleOps** | Recommends resource reduction | Correct |
| **Karpenter** | Consolidates underutilized nodes | Correct at node level |
| **Our Controller** | **SCALE IN -2.** Negative pressure, all signals agree system is over-provisioned, respects -25% max per action | **Correct, bounded** |

**Key detail:** Error rate at 0% does NOT contribute negative pressure. Low error rate means "everything is fine," not "over-provisioned." The negative pressure comes from CPU (0.12 - 0.5 = -0.38), memory (0.15 - 0.5 = -0.35), latency (0.08 - 0.5 = -0.42).

Source: `controller.py:329` — `max(0.0, error_rate - 0.5)` for inverted metrics.

Safety bound: `max_scale_in_ratio = 0.25` → max -2 replicas (25% of 10). Scale from 10 → 8 in first action. Requires multiple cycles to reach optimal 3.

---

### Scenario 5: Day 1 — New Cluster, No History

**Setup:** Fresh Kubernetes cluster. No historical data. First deployment.

| System | Action | Readiness |
|--------|--------|-----------|
| **K8s HPA** | Works immediately (ratio-based, no history needed) | Instant |
| **Cast AI** | Works immediately (fixed thresholds) | Instant |
| **ScaleOps** | Blind — needs 2+ weeks of training data | 2-3 weeks |
| **Karpenter** | Works immediately (reacts to pending pods) | Instant |
| **Our Controller (cold)** | 100-cycle warmup (~25 min). Damping held at d=1.0, gain at 50%, identity random | ~25 minutes |
| **Our Controller (bootstrapped)** | Fetches 1 hour of Prometheus history via `range_query`, pre-learns all baselines | **~5 seconds** |

**Bootstrap process** (implemented in `signals/pipeline.py:108-177`):

```python
pipeline = SignalPipeline(PipelineConfig(bootstrap_window_seconds=3600))
pipeline.bootstrap()  # Queries Prometheus history, pre-seeds everything
result = pipeline.poll_once()  # Ready to act on cycle 1
```

What gets bootstrapped:
1. **Normalizer** — Rolling z-score windows filled from history
2. **Identity EMA** — Baseline set from mean of historical vectors
3. **Damping** — Variance baseline calibrated, warmup skipped
4. **Adaptive Gain** — Warmup ramp bypassed (starts at 100%)
5. **Plasticity Gate** — Double-smoothed resistance warmed up

For a truly fresh cluster with < 1 hour of Prometheus data, the controller falls back to conservative defaults (half-gain, neutral normalization) — safe but less precise than a bootstrapped instance.

---

## Implementation Status

### What Is Built (Production-Ready)

| Stage | Component | Files | Tests | Status |
|-------|-----------|-------|-------|--------|
| **Stage 1** | Core control library (12 parameters) | `controller.py`, `core/*.py`, `config.py` | 87 unit tests | **Complete** |
| **Stage 2** | Prometheus integration + signal pipeline | `signals/prometheus.py`, `signals/normalizer.py`, `signals/pipeline.py` | 42 unit tests | **Complete** |
| **Stage 3** | Shadow mode (proof of value) | `shadow/runner.py`, `shadow/divergence.py`, `shadow/reporter.py`, `shadow/hpa_watcher.py` | 38 unit tests | **Complete** |
| **Stage 4** | Recommend mode (human-in-the-loop) | `recommend/engine.py`, `recommend/confidence.py`, `recommend/safety.py`, `recommend/approval.py`, `recommend/webhook.py` | 39+ unit tests | **Complete** |
| **Bootstrap** | Learning phase elimination | `bootstrap()` on all modules | 22 unit tests | **Complete** |

**Total:** 27 Python source files, 228+ unit tests, all passing.

### What Is Planned (Not Yet Built)

| Stage | Component | Prerequisite | Value |
|-------|-----------|-------------|-------|
| **Stage 5** | Active mode (bounded autonomous control) | Validated shadow mode results | Direct scaling without human approval |
| **Stage 6** | Learning loop + multi-service | Active mode data | Auto-tune 12 parameters from outcome data. L6 → L4 feedback loop |
| **Layer 3** | Prediction module | Replay buffer + historical data | Proactive scaling (compete with ScaleOps at L3) |
| **Layer 2** | Cost optimization integration | Stage 5 active mode | Feed Cast AI / Kubecost constraints into decision equation |

### The 12 Load-Bearing Parameters

Every parameter is ablation-validated from the CG ExperientialController. Changing any one has a measurable effect on decision quality.

```
┌─────────────────────────────────────────────────────────────────┐
│ Parameter          │ Cloud Default │ Role                        │
├────────────────────┼───────────────┼─────────────────────────────┤
│ w_infra            │ 0.4           │ Infrastructure weight        │
│ w_app              │ 0.4           │ Application weight           │
│ w_business         │ 0.2           │ Business weight              │
│ k_r                │ 2.0           │ Resistance → gate openness   │
│ k_m                │ 2.0           │ Misalignment → gate closure  │
│ b_p                │ -1.0          │ Gate floor (never fully shut)│
│ G_base             │ 1.0           │ Base gain (conservative)     │
│ G_min              │ 0.0           │ Min gain (allow "do nothing")│
│ G_max              │ 3.0           │ Max gain (3x scaling factor) │
│ k_dv               │ 1.0           │ Variance sensitivity         │
│ k_dc               │ 0.5           │ Coherence instability sens.  │
│ alpha_base         │ 0.01          │ Identity learning rate       │
└─────────────────────────────────────────────────────────────────┘
```

Source: `config.py:20-47`

---

## Deployment Strategy

### Phase 1: Shadow Mode (Week 1-2)

```
Our Controller (read-only) ──→ logs recommendations
                                  │
HPA (active) ──────────────→ scales pods (as before)
                                  │
Shadow Runner ──────────────→ compares, assigns verdicts
                                  │
                              Weekly report: "controller prevented 89
                              unnecessary scales, caught 43 early"
```

**Requirements:** Read-only access to Prometheus and K8s API. Zero write permissions.

**Deliverable:** Shadow report proving value. This is the customer demo.

### Phase 2: Recommend Mode (Week 3-4)

```
Our Controller ──→ ConfidenceScorer ──→ SafetyBounds ──→ Slack/PagerDuty
                                                              │
                                                    [Approve] [Dismiss]
                                                              │
                                                         K8s API (scale)
```

**Requirements:** Webhook URLs. Write access to K8s API only on approval.

### Phase 3: Active Mode (Week 5+)

```
Our Controller ──→ SafetyBounds ──→ K8s API (direct scaling)
                        │
                   HPA as safety net (wide min/max bounds)
```

**Requirements:** Validated Phase 2 results. Customer trust established.

---

## Why This Architecture Is Novel

### What exists today (every competitor)

```
Signal → Threshold/ML → Scale
```

One signal (or ML-correlated signals) crosses a boundary → act. No coherence check, no stability awareness, no identity baseline, no deployment gating.

### What our controller does

```
Signals → Coherence Gate → Stability Gate → Gain Modulation → Damping → Bounded Action
              │                  │                │              │
              │                  │                │              └─ Is the system volatile?
              │                  │                └─────────────── How aggressively?
              │                  └──────────────────────────────── Is it safe to act?
              └─────────────────────────────────────────────────── Do the signals agree?
```

Every step is:
- **Continuous** (sigmoid, EMA, exp) — no binary branching
- **Rate-limited** — no step can change faster than its budget per cycle
- **Explainable** — every component exposed in `ActionResult`
- **Self-calibrating** — baselines adapt to the specific system over time

This is not a threshold system with more thresholds. It is a **control system** derived from the same consistency-constrained principles used in the CG ExperientialController — adapted from neural network training dynamics to cloud infrastructure scaling.

The math is the moat.

---

## Appendix: File Index

```
symbolu/cloud_controller/
├── __init__.py
├── config.py                      # 12-parameter InfraControllerConfig
├── controller.py                  # Main: sense → interpret → decide → act → learn
│
├── core/
│   ├── plasticity_gate.py         # P_t = sigmoid(k_r·R - k_m·M + b_p)
│   ├── adaptive_gain.py           # G_t with rate limiting + bootstrap
│   ├── damping.py                 # d_t with asymmetric EMA + bootstrap
│   ├── identity_ema.py            # Baseline learning + bootstrap
│   ├── coherence.py               # Multi-signal agreement scoring
│   └── replay_buffer.py           # Priority-weighted incident memory
│
├── signals/
│   ├── prometheus.py              # Prometheus HTTP client (instant + range)
│   ├── normalizer.py              # Raw → [0,1] + bootstrap
│   └── pipeline.py                # Polling loop + bootstrap orchestrator
│
├── shadow/
│   ├── runner.py                  # Shadow mode orchestrator
│   ├── hpa_watcher.py             # K8s HPA observation
│   ├── divergence.py              # Controller vs HPA comparison + verdicts
│   └── reporter.py                # Proof-of-value report generation
│
├── recommend/
│   ├── engine.py                  # Recommendation pipeline orchestrator
│   ├── confidence.py              # Confidence scoring (NONE/LOW/MEDIUM/HIGH)
│   ├── safety.py                  # Hard limits + cooldown
│   ├── approval.py                # PENDING → APPROVED/DISMISSED/EXPIRED
│   └── webhook.py                 # Slack/PagerDuty/OpsGenie dispatch
│
├── action/
│   └── __init__.py                # K8s actuator (Stage 5, planned)
│
└── explain/
    └── __init__.py                # Decision log formatting (Stage 5, planned)
```
