# Neural Cloud Scaling Controller — Modular Design Document

**Status**: Draft
**Origin**: CG ExperientialController (12-parameter minimal controller)
**Target**: Cloud infrastructure adaptive scaling and deployment safety

---

## 1. Problem Statement

Current cloud auto-scaling (AWS ASG, Azure VMSS, Kubernetes HPA) uses:
- Single-signal thresholds (CPU > 70% → add instances)
- Fixed cooldown periods (300s regardless of signal behavior)
- No multi-signal consensus (CPU spike ≠ real load)
- No deployment-awareness (scales during unstable rollouts)
- No learning from past incidents

This controller replaces the decision logic between sensing and actuation.

---

## 2. Core Equation

```
Action_t = d_t · G_t · P_t · S_t
```

Where:
- `S_t` = pressure signal (normalized multi-metric demand score)
- `P_t` = plasticity gate (is it safe to act?)
- `G_t` = adaptive gain (how aggressively?)
- `d_t` = damping (suppress if volatile)

This is the cloud adaptation of `g_eff = d_t · G_t · P_t · ∇L_exp` from the CG controller.

---

## 3. Module Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   SENSE (Module 1)                       │
│  Prometheus/CloudWatch → Normalize → State Vector X_t    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                 INTERPRET (Module 2)                      │
│  2A. Identity EMA      — adaptive baseline               │
│  2B. Coherence Model   — multi-signal agreement          │
│  2C. Resistance Model  — system stability score          │
│  2D. Misalignment Model — proposed change vs. identity   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  DECIDE (Module 3)                        │
│  3A. Plasticity Gate   — P_t: permission to act          │
│  3B. Adaptive Gain     — G_t: action magnitude           │
│  3C. Damping           — d_t: volatility suppression     │
│  3D. Action Policy     — A_t = d_t · G_t · P_t · S_t    │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   ACT (Module 4)                          │
│  Mode A: Observe — log recommendation only               │
│  Mode B: Approve — human confirms before execution       │
│  Mode C: Autonomous — bounded auto-execution             │
│  Actuators: K8s HPA, AWS ASG, Azure VMSS, ArgoCD gate   │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  LEARN (Module 5)                         │
│  5A. Replay Buffer     — priority-weighted incident memory│
│  5B. Baseline Adapt    — Identity EMA slow consolidation │
│  5C. Outcome Tracking  — did the action help?            │
└─────────────────────────────────────────────────────────┘
```

---

## 4. 12-Parameter Configuration

Adapted from `ExperientialControllerConfig` (minimal_controller.py:42-77).

| # | Parameter | CG Default | Cloud Default | Role |
|---|-----------|-----------|---------------|------|
| 1 | `w_infra` | λ_temporal=0.5 | 0.4 | Infrastructure signal weight (CPU, mem, disk) |
| 2 | `w_app` | λ_coherence=0.3 | 0.4 | Application signal weight (latency, errors) |
| 3 | `w_business` | λ_latent=0.1 | 0.2 | Business signal weight (conversions, queue) |
| 4 | `k_r` | 2.0 | 2.0 | Resistance openness scaling |
| 5 | `k_m` | 2.0 | 2.0 | Misalignment suppression scaling |
| 6 | `b_p` | -1.0 | -1.0 | Plasticity floor (gate never fully closes) |
| 7 | `G_base` | 3.0 | 1.0 | Base gain (conservative for cloud) |
| 8 | `G_min` | 0.1 | 0.0 | Minimum gain (0 = allow "do nothing") |
| 9 | `G_max` | 5.0 | 3.0 | Maximum gain (3x max scaling factor) |
| 10 | `k_dv` | 1.0 | 1.0 | Variance sensitivity |
| 11 | `k_dc` | 0.5 | 0.5 | Coherence instability sensitivity |
| 12 | `α_base` | 0.01 | 0.01 | Identity EMA learning rate |

---

## 5. Module Specifications (Detail Sections)

### 5.1 Module 1 — Signal Ingestion & Normalization

**Input sources** (MVP: Prometheus only):
- Infrastructure: `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`
- Application: `http_request_duration_seconds{quantile="0.99"}`, `http_requests_total{code=~"5.."}`
- Capacity: `kube_deployment_status_replicas`, `kube_hpa_status_current_replicas`
- Change events: deploy start/end, config changes (via EventBridge / K8s events)

**Output**: Normalized state vector `X_t` with all signals in [0, 1] range.

**Normalization**: Per-signal z-score against rolling 1-hour window, then sigmoid to [0,1].

```
X_t = [cpu_norm, mem_norm, latency_p99_norm, error_rate_norm,
       queue_depth_norm, request_rate_delta, deploy_flag, time_phase]
```

### 5.2 Module 2A — Identity EMA (Adaptive Baseline)

**Origin**: `SelfModel.consolidate_identity()` (identity_layer.py:163-222)

**What changes from CG**: Signal source swaps from hidden states to infrastructure metrics. Math is identical.

**Fast loop** (every evaluation cycle, ~10-30s):
```
accumulator = ema_decay · accumulator + (1 - ema_decay) · X_t
# ema_decay = 0.99
```

**Slow loop** (every consolidation_interval, ~1000 cycles ≈ hours):
```
agreement  = max(0, (cosine_sim(accumulator, baseline) + 1) / 2)
stability  = 1 / (1 + var(accumulator))
α_eff      = max(α_base · stability · agreement, 0.1 · α_base)
baseline   = (1 - α_eff) · baseline + α_eff · normalize(accumulator)
```

**Key property**: Baseline only updates when system is stable AND new signal agrees with current identity. Anomalous periods don't corrupt the baseline.

### 5.3 Module 2B — Coherence Model

**Origin**: CG coherence signals (c_tok, c_lat, c_conv)

**Cloud mapping**:
- `c_infra` = agreement among CPU, memory, disk I/O, network
- `c_app` = agreement among latency, error rate, throughput
- `c_business` = agreement among queue depth, conversion rate (if available)

**V1 implementation** (rule-based):
```
C_t = w_infra · agreement(infra_signals)
    + w_app · agreement(app_signals)
    + w_business · agreement(business_signals)

# agreement(signals) = 1 - normalized_pairwise_variance(signals)
# All signals elevated and agreeing → C_t ≈ 1.0
# Only CPU elevated, rest flat → C_t ≈ 0.3
```

### 5.4 Module 2C — Resistance Model (System Stability)

**Inputs that lower resistance (system is fragile)**:
- High metric variance over last N cycles
- Recent scaling actions (scaled within last 5 minutes)
- Active deployment / rollout in progress
- Pod restart count increasing
- Recent failed health checks

```
R_t = 1.0 - weighted_sum(variance_score, recent_scale_score,
                          deploy_active, restart_score)
# R_t ∈ [0, 1]: 1.0 = fully stable, 0.0 = highly fragile
```

**Double-smoothed** (matching CG implementation):
```
R_t = 0.9 · persistent_R + 0.1 · R_t           # Fast blend
persistent_R = 0.95 · persistent_R + 0.05 · R_t  # Slow update
```

### 5.5 Module 2D — Misalignment Model

```
proposed_replicas = current_replicas + round(G_t · S_t)
M_t = |proposed_replicas - current_replicas| / current_replicas
# Scaling from 5→6 = 0.2 misalignment
# Scaling from 5→10 = 1.0 misalignment
```

### 5.6 Module 3A — Plasticity Gate

**Origin**: `PlasticityGate.forward()` (minimal_controller.py:211-261)

```
P_t = sigmoid(k_r · R_t - k_m · M_t + b_p)
```

With defaults (k_r=2.0, k_m=2.0, b_p=-1.0):

| R_t (stability) | M_t (misalignment) | P_t | Interpretation |
|---|---|---|---|
| 1.0 (stable) | 0.0 (small change) | 0.73 | Open — safe to act |
| 1.0 (stable) | 1.0 (large change) | 0.27 | Cautious — large change to stable system |
| 0.0 (fragile) | 0.0 (small change) | 0.27 | Cautious — system already unstable |
| 0.0 (fragile) | 1.0 (large change) | 0.007 | Closed — risky change to fragile system |
| any | any | ≥ sigmoid(b_p)=0.27 | Floor — gate never fully closes |

**Note**: `sigmoid(-1.0) = 0.27` ensures the gate always allows ~27% throughput. This prevents total lockout — a critical safety property.

### 5.7 Module 3B — Adaptive Gain

**Origin**: `AdaptiveGain.compute()` (minimal_controller.py:274-302)

```
f_phase = min(1.0, 0.5 + 0.5 · step / warmup_steps)
f_coh   = 0.5 + 0.5 / (1 + exp(-(C_t - 0.5) · 4.0))
target  = clip(G_base · f_phase · f_coh, G_min, G_max)
```

**Cloud adaptation of f_phase**:
- Instead of training warmup, use time-of-day phase
- Peak hours: f_phase = 1.0 (full responsiveness)
- Off-peak: f_phase = 0.6 (conservative)
- Maintenance window: f_phase = 0.3 (minimal)

**Rate limiting** (critical for cloud — prevents scaling oscillation):
```
max_delta = G_base · 0.1    # Max 10% change per cycle
G_t = clamp(target, prev_G - max_delta, prev_G + max_delta)
```

With G_base=1.0: gain changes by at most ±0.1 per cycle. From G_min=0.0 to G_max=3.0 takes minimum 30 cycles.

### 5.8 Module 3C — Damping

**Origin**: `Damping.compute()` (minimal_controller.py:331-379)

**Asymmetric EMA** (fast spike detection, fast recovery):
```
if variance > V_ema:
    V_ema = 0.90 · V_ema + 0.10 · variance    # Detect spike: α=0.10
else:
    V_ema = 0.80 · V_ema + 0.20 · variance    # Recover: α=0.20
```

**Slow baseline** (self-calibrating):
```
V_baseline = 0.999 · V_baseline + 0.001 · variance
```

**Baseline-relative damping** (key difference from ChatGPT's formula):
```
V_excess = max(0, V_ema / V_baseline - 1.0)    # Only excess over normal
exponent = -(k_dv · V_excess + k_dc · U_ema)
d_t = exp(clamp(exponent, -10, 0))
d_t = max(d_t, 0.01)                           # Hard floor: never fully suppress
d_t = clamp(d_t, prev_d ± 0.1)                 # Rate limit: ±0.1 per cycle
```

**Why baseline-relative matters**: A system with naturally high metric variance (e.g., batch processing cluster) won't be permanently damped. Only variance *above its own normal* triggers damping.

### 5.9 Module 3D — Action Policy

```
A_t = d_t · G_t · P_t · S_t
```

**Action mapping**:

| A_t Range | Action |
|-----------|--------|
| < 0.05 | No action |
| 0.05 – 0.2 | Log recommendation only |
| 0.2 – 0.5 | Scale ±1 replica |
| 0.5 – 1.0 | Scale ±2 replicas |
| > 1.0 | Scale ±3 replicas (max bounded by G_max) |

Negative S_t (system over-provisioned) produces negative A_t → scale down.

### 5.10 Module 4 — Action Layer

**Three operating modes**:

| Mode | Behavior | Target Customer |
|------|----------|----------------|
| A: Observe | Log decisions, no execution | First adoption, POC |
| B: Approve | Webhook/Slack notification, human confirms | Enterprise, regulated |
| C: Autonomous | Direct API calls within bounds | Mature customers |

**Actuator interfaces** (MVP: Kubernetes only):
```
K8sActuator:
  - PATCH /apis/apps/v1/deployments/{name}/scale
  - Or: set HPA custom metric target via metrics adapter

GateActuator:
  - ArgoCD: POST /api/v1/applications/{name}/sync (block/allow)
  - K8s Admission Webhook: reject/allow deployment events when P_t < threshold
```

### 5.11 Module 5A — Replay Buffer

**Origin**: `ReplayBuffer` (minimal_controller.py:443-487)

**Store trigger**: high misalignment + low plasticity (system was stressed AND couldn't adapt)

**Entry schema**:
```json
{
  "step": 142857,
  "timestamp": "2026-03-29T14:23:01Z",
  "state_vector": [0.82, 0.45, 0.91, ...],
  "coherence": 0.31,
  "plasticity": 0.18,
  "action_taken": "hold",
  "action_score": 0.04,
  "outcome": null,
  "priority": 0.87
}
```

**Capacity**: 256 entries (configurable)
**TTL**: 200 cycles (configurable) — stale incidents expire
**Eviction**: When full, sort by priority, remove lowest (not FIFO)
**Sampling**: Probability-proportional to priority, without replacement

### 5.12 Module 5B — Baseline Adaptation

Identity EMA slow consolidation (Module 2A) handles this. No separate service needed.

### 5.13 Module 5C — Outcome Tracking

After each action, track:
- Did latency decrease within 5 minutes?
- Did error rate decrease?
- Did scaling oscillation occur (scale up then down within 10 minutes)?
- Was the action overridden by a human?

Feed outcomes back as priority weights for replay buffer entries.

---

## 6. Explainability Output

Every decision produces a human-readable breakdown:

```
[2026-03-29 14:23:01] Decision: HOLD SCALING
  Pressure (S_t):      0.72 (moderate — CPU 78%, latency p99 rising)
  Coherence (C_t):     0.31 (low — only CPU elevated, queue/errors flat)
  Stability (R_t):     0.45 (fragile — scaled 2x in last 8 minutes)
  Misalignment (M_t):  0.40 (moderate — proposed +3 replicas from 5)
  Plasticity (P_t):    0.21 (closed)
  Gain (G_t):          0.44
  Damping (d_t):       0.31 (high variance suppression active)
  Action Score (A_t):  0.02 → NO ACTION
  Reason: Incoherent pressure + recent scaling instability
```

---

## 7. What This Replaces vs. Wraps

| Cloud Component | Relationship |
|----------------|-------------|
| AWS ASG Simple/Step Scaling | **Replaces** — static thresholds → coherence-gated decisions |
| AWS ASG Cooldown | **Replaces** — fixed timer → signal-aware damping |
| Azure VMSS Autoscale Rules | **Replaces** — same as ASG |
| K8s HPA Algorithm | **Replaces** — proportional controller → full P_t·G_t·d_t |
| CloudWatch / Azure Monitor | **Wraps** — still the data source |
| Prometheus | **Wraps** — primary MVP data source |
| ASG / VMSS / K8s (resource) | **Wraps** — still the actuator, we replace the policy |
| CodeDeploy / ArgoCD | **Wraps** — plasticity gate as deployment gate |
| KEDA | **Coexists** — KEDA for simple event scaling, controller for multi-signal |

---

## 8. Implementation Stages

### Stage 1 — Core Library Extraction

**Goal**: Standalone controller with zero cloud dependencies.

**What to build**:
- Extract `PlasticityGate`, `AdaptiveGain`, `Damping`, `IdentityEMA`, `ReplayBuffer` from `minimal_controller.py` and `identity_layer.py`
- Remove all PyTorch dependencies — pure stdlib `math` + `numpy` (or stdlib-only)
- Create `InfraControllerConfig` dataclass with the 12 cloud-adapted parameters
- Wire them into a single `Controller.step(state_vector) → ActionResult` function

**Source → Target mapping**:

| CG Source | Cloud Target | What changes |
|-----------|-------------|-------------|
| `PlasticityGate.forward()` (lines 211-261) | `core/plasticity_gate.py` | Remove `nn.Module`, `nn.Sequential` resistance projector. R_t becomes a plain float input instead of neural network output. Keep double-smoothed EMA, sigmoid gate, all constants |
| `AdaptiveGain.compute()` (lines 274-302) | `core/adaptive_gain.py` | Direct port — already pure math, no torch dependency. Replace training warmup with time-of-day phase |
| `Damping.compute()` (lines 331-379) | `core/damping.py` | Direct port — already pure math. Rename `grad_variance` → `metric_variance` |
| `SelfModel.consolidate_identity()` (lines 163-222) | `core/identity_ema.py` | Replace torch tensors with numpy arrays. Keep conditional α_eff, re-normalization, accumulator pattern |
| `ReplayBuffer` (lines 443-487) | `core/replay_buffer.py` | Direct port — already plain Python. Change entry schema from ML states to infra states |
| `ExperientialControllerConfig` (lines 42-78) | `config.py` | Swap λ_temporal/coherence/latent → w_infra/w_app/w_business. Adjust G_base from 3.0→1.0, G_max from 5.0→3.0 |

**Deliverable**: A Python package that can be tested with synthetic signals in a unit test. No cluster needed.

```python
# Stage 1 test: synthetic signal → decision
from cloud_controller import Controller, InfraControllerConfig

ctrl = Controller(InfraControllerConfig())
result = ctrl.step(
    metrics={"cpu": 0.82, "latency_p99": 0.45, "error_rate": 0.12,
             "queue_depth": 0.38, "memory": 0.55, "request_rate": 0.71},
    deploy_active=False,
    time_phase="peak"
)
# result.action_score = 0.34
# result.recommendation = "scale +1"
# result.explanation = "Moderate coherent pressure, system stable..."
```

**Validation**: Unit tests with known input/output pairs. Verify:
- Plasticity gate closes when R_t=0, M_t=1 (P_t ≈ 0.007)
- Damping suppresses when variance is 5x baseline (d_t < 0.4)
- Gain rate-limits to ±10% per step
- Identity EMA doesn't update when stability < 0.2

**Estimated scope**: ~800 lines of Python across 7 files.

---

### Stage 2 — Prometheus Integration & Signal Pipeline

**Goal**: Read real metrics from a Kubernetes cluster, normalize to state vector.

**What to build**:
- Prometheus HTTP client (`/api/v1/query` and `/api/v1/query_range`)
- Signal normalizer: raw metric values → [0, 1] via rolling z-score + sigmoid
- Coherence calculator: pairwise agreement across signal groups
- Resistance estimator: variance + recent scaling events + deploy status → R_t
- State vector assembler: combine all signals into `X_t`

**Prometheus queries (MVP set)**:

| Signal | PromQL | Normalization |
|--------|--------|---------------|
| CPU utilization | `rate(node_cpu_seconds_total{mode!="idle"}[2m])` | z-score against 1h rolling mean |
| Memory pressure | `1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)` | Direct ratio [0,1] |
| Latency p99 | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[2m]))` | z-score against 1h rolling |
| Error rate | `rate(http_requests_total{code=~"5.."}[2m]) / rate(http_requests_total[2m])` | Direct ratio [0,1] |
| Queue depth | `queue_messages_ready` or `kube_pod_container_resource_requests` | z-score against 1h rolling |
| Request rate | `rate(http_requests_total[2m])` | z-score for delta detection |
| Pod restarts | `rate(kube_pod_container_status_restarts_total[10m])` | > 0 = instability signal |
| HPA current replicas | `kube_hpa_status_current_replicas` | Used for misalignment calc |

**Polling interval**: Every 15 seconds (configurable). Controller runs `step()` each poll.

**Deliverable**: Controller running against a real or simulated Prometheus endpoint, producing decision logs to stdout/file.

```
[14:23:01] X_t=[cpu=0.78, mem=0.42, lat=0.65, err=0.08, queue=0.31, req=0.72]
[14:23:01] Coherence=0.61, Resistance=0.73, Misalignment=0.15
[14:23:01] P_t=0.65, G_t=0.82, d_t=0.91 → A_t=0.49 → RECOMMEND: scale +1
```

**Validation**: Run against a test cluster with `k6` or `locust` generating load patterns:
- Steady load → controller says "no action" (correct)
- Ramp up → controller recommends scale-out before HPA threshold fires
- Spike + recover → controller damps, HPA would thrash

---

### Stage 3 — Shadow Mode (Proof of Value)

**Goal**: Run controller alongside existing HPA, log divergence, prove value.

**What to build**:
- Shadow runner: polls metrics, runs controller, records recommendation
- HPA watcher: polls `kube_hpa_status_desired_replicas` to see what HPA actually did
- Delta logger: records every divergence between controller and HPA
- Summary reporter: daily/weekly report of avoided thrash, early detections, false positives

**Shadow log format**:
```
[14:23:01] DIVERGENCE
  HPA action:        scale 5 → 8 (CPU 82% > threshold 70%)
  Controller action:  HOLD (coherence=0.31 — only CPU elevated)
  Reason:            Incoherent pressure — latency flat, queue flat, errors flat
  Verdict:           PENDING (check if CPU returned to normal within 5 min)

[14:28:01] VERDICT for [14:23:01]
  CPU returned to 54% within 4 minutes (single process spike)
  Controller was CORRECT — HPA would have wasted 3 pods for 4 minutes
  Estimated cost saved: $0.12 (3 pods × 4 min × $0.03/pod-min)
```

**Delta report** (weekly):
```
Neural Cloud Controller — Shadow Report (Week 13, 2026)
  Total decisions:              2,016
  Agreements with HPA:          1,847 (91.6%)
  Controller caught earlier:       43 (controller scaled 2-5 min before HPA)
  Controller prevented thrash:     89 (HPA scaled unnecessarily)
  Controller too conservative:     37 (should have scaled, didn't)
  Net improvement:                 95 better decisions
  Estimated cost savings:         $847/week
```

**This report is the sales demo.** Run it against a prospect's cluster for 2 weeks.

**Deployment**: Kubernetes Deployment or DaemonSet, read-only access to Prometheus and K8s API. Zero write permissions — purely observational.

**Validation**: Run for 2+ weeks on a real cluster. Manual review of all divergences. Tune parameters based on false positives/negatives.

---

### Stage 4 — Recommend Mode (Human-in-the-Loop)

**Goal**: Controller sends actionable recommendations, human approves.

**What to build**:
- Webhook integration: Slack / PagerDuty / OpsGenie notification on high-confidence recommendations
- Approval API: human clicks "approve" → controller executes the action
- Explanation UI: web dashboard showing current state, controller reasoning, history
- Confidence scoring: only recommend when action score > threshold AND coherence > 0.5

**Notification example** (Slack):
```
⚠️ Neural Cloud Controller — Scale Recommendation
Service: api-gateway (prod)
Current replicas: 5
Recommended: 7 (+2)
Confidence: HIGH

Signals:
  CPU: 84% ↑ (sustained 8 min)
  Latency p99: 340ms ↑ (was 120ms baseline)
  Error rate: 2.1% ↑ (was 0.3%)
  Queue depth: 1,247 ↑ (was 200)
  Coherence: 0.89 (all signals agree)
  System stability: 0.81 (stable)

[Approve] [Dismiss] [Details]
```

**Safety bounds** (always enforced, even on approval):
- Max scale-out: +50% of current replicas per action
- Max scale-in: -25% of current replicas per action
- Minimum replicas: never below the HPA minReplicas setting
- Cooldown after action: controller enters observation mode for 2 minutes

**Deliverable**: Operator receives recommendations, can approve/dismiss, sees full reasoning.

---

### Stage 5 — Active Mode (Bounded Autonomous Control)

**Goal**: Controller directly manages scaling within strict policy bounds.

**What to build**:
- K8s actuator: PATCH `apps/v1/deployments/{name}/scale` or set HPA custom metric
- Policy engine: customer-configurable safety limits (max replicas, max change rate, blackout windows)
- Rollback trigger: if metrics degrade within 3 minutes of action, auto-revert
- Audit log: every action recorded with full state snapshot and reasoning

**Two integration options**:

Option A — Custom Metrics Adapter:
```
Controller → exposes action_score as Prometheus metric
HPA → configured to scale on controller_action_score metric
HPA still manages pod lifecycle — controller provides the signal
```

Option B — Direct Replica Patching:
```
Controller → PATCH deployment replicas directly
HPA → disabled or set to very wide min/max as safety net
Controller owns scaling — HPA is emergency fallback only
```

Recommend Option A for initial active mode (less risk, HPA as safety net).

**Deployment gate integration**:
- ArgoCD: controller exposes `/api/readiness` endpoint
- ArgoCD Sync pre-hook calls endpoint: if P_t < 0.3 → block sync, return reason
- Operator sees: "Deployment blocked: system stability 0.34, recent scaling oscillation detected. Retry in ~10 min."

**Validation**: Run in active mode on staging first (2 weeks), then canary on one production service, then expand.

---

### Stage 6 — Learning Loop & Multi-Service

**Goal**: Controller improves over time, scales to multiple services.

**What to build**:
- Outcome attribution: after each action, measure whether metrics improved within 5 minutes
- Replay-driven tuning: use replay buffer to identify systematic errors (e.g., consistently too conservative during morning traffic ramp)
- Parameter auto-tuning: Bayesian optimization over the 12 parameters using outcome data
- Multi-service support: one controller instance per service, shared identity EMA for cluster-wide patterns
- Cross-service coherence: detect correlated scaling needs across services (if API gateway scales, downstream services likely need to scale too)

**Parameter tuning loop**:
```
Weekly:
  1. Sample 50 replay entries (priority-weighted)
  2. For each: what would different parameters have produced?
  3. Optimize parameters to maximize: correct_decisions / total_decisions
  4. Apply new parameters with warmup ramp (don't jump to new values)
```

This stage is where the controller becomes customer-specific and the moat deepens.

---

## 9. Files to Create

```
symbolu/cloud_controller/
├── __init__.py
├── config.py                  # 12-parameter InfraControllerConfig
├── core/
│   ├── __init__.py
│   ├── plasticity_gate.py     # P_t = sigmoid(k_r·R - k_m·M + b_p)
│   ├── adaptive_gain.py       # G_t with rate limiting
│   ├── damping.py             # d_t with asymmetric EMA + baseline-relative
│   ├── identity_ema.py        # Slow baseline consolidation
│   ├── coherence.py           # Multi-signal agreement scoring
│   └── replay_buffer.py       # Priority-weighted, TTL-bounded
├── signals/
│   ├── __init__.py
│   ├── normalizer.py          # Raw metrics → [0,1] state vector
│   ├── prometheus.py          # Prometheus query adapter
│   └── resistance.py          # System stability computation
├── action/
│   ├── __init__.py
│   ├── policy.py              # A_t → action mapping
│   ├── k8s_actuator.py        # Kubernetes scaling API
│   └── gate_actuator.py       # Deployment gate (ArgoCD webhook)
├── explain/
│   ├── __init__.py
│   └── decision_log.py        # Human-readable decision breakdown
└── controller.py              # Main loop: sense → interpret → decide → act → learn
```

---

## 10. Math Corrections vs. ChatGPT Product Architecture

ChatGPT's product architecture captures the first-order structure correctly. The following second-order properties from the actual CG implementation are critical and must be preserved:

1. **Damping uses baseline-relative variance**, not raw variance — prevents permanent damping of high-variance systems
2. **Asymmetric EMA** (α_up=0.10, α_down=0.20) — fast spike detection + fast recovery
3. **Double-smoothed resistance** (two nested EMAs: α=0.1 fast, α=0.05 slow) — momentum prevents gate flicker
4. **Rate limiting on gain AND damping** (±10% and ±0.1 per cycle) — bounded velocity prevents oscillation
5. **Identity EMA conditional update** (α_eff = α_base × stability × agreement) — anomalies don't corrupt baseline
6. **Replay eviction by priority** (not FIFO) — severe incidents persist, minor ones get displaced
7. **Plasticity floor** (sigmoid(b_p=-1.0) = 0.27) — gate never fully closes, always allows partial action

These are not implementation details — they are stability guarantees.
