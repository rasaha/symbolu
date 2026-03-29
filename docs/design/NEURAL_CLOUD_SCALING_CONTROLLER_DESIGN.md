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

## 8. Implementation Sequence

### Phase 1: Core Library (no cloud dependency)
Extract domain-agnostic math from `minimal_controller.py` into standalone Python module.
No PyTorch — pure stdlib `math` + `numpy`.

### Phase 2: Prometheus Connector
Single integration. Read metrics via `/api/v1/query`. Normalize to state vector.

### Phase 3: Shadow Mode
Run alongside existing HPA. Log what controller would do vs. what HPA did.
Produce delta report: "controller would have prevented N thrash events, caught M incidents earlier."

### Phase 4: Active Mode
Replace HPA decision logic. Either custom metrics adapter or direct replica patching.
Start Mode A (observe), graduate to Mode B (approve), then Mode C (autonomous).

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
