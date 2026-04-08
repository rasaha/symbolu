# Neural Cloud Scaling Controller — Architecture Specification

**Status**: Draft v2
**Last revised**: 2026-04-08
**Origin**: CG ExperientialController (12-parameter minimal controller)
**Target**: Kubernetes workload scaling — external adaptive controller

---

## 1. System Objective

Provide an external scaling controller for Kubernetes workloads that makes
better scale-out/scale-in decisions than threshold-based autoscalers by
synthesizing multiple metric signals, suppressing action during instability,
and learning a per-service baseline over time.

**Optimization target**: minimize the sum of (a) under-provisioning cost
(elevated latency, errors) and (b) over-provisioning cost (idle replicas),
subject to safety constraints on action rate and magnitude.

**Core equation**:

```
A_t = d_t · G_t · P_t · S_t
```

The controller does not replace the metric collection layer (Prometheus,
CloudWatch) or the pod lifecycle manager (Deployment controller, ASG).
It replaces the **decision policy** between sensing and actuation.

---

## 2. Problem Statement

Standard Kubernetes HPA computes desired replicas as:

```
desiredReplicas = ceil(currentReplicas × (currentMetricValue / targetMetricValue))
```

This is a proportional controller on a single metric (typically CPU). Its
known failure modes include:

- **Single-signal blindness**: a CPU spike from a batch job triggers scale-out
  even when latency, error rate, and queue depth are flat.
- **Fixed cooldown**: HPA's `--horizontal-pod-autoscaler-downscale-stabilization`
  (default 5 min) is time-based, not signal-based. It cannot distinguish
  "signal is still volatile" from "signal has stabilized."
- **No deployment awareness**: HPA will scale during a rolling update, adding
  pods to a deployment that is actively replacing them.
- **No cross-signal coherence**: HPA cannot express "scale only when CPU AND
  latency are both elevated."
- **No memory of past behavior**: each decision is stateless. The same
  misleading signal pattern will trigger the same wrong action repeatedly.

AWS ASG simple/step scaling policies and Azure VMSS autoscale rules share
the same structural limitations: single-metric thresholds with fixed cooldowns.

---

## 3. Scope and Non-Goals

### In scope

- Kubernetes Deployments and StatefulSets (via the `scale` subresource)
- Prometheus as the primary metric source (MVP)
- Pod-level horizontal scaling (replica count changes)
- Shadow mode (observe and log, no mutations)
- Recommend mode (human approves before execution)
- Autonomous mode (bounded auto-execution)
- Per-service configuration and identity learning

### Non-goals

- **Node provisioning**: out of scope. Use Karpenter or Cluster Autoscaler.
- **Vertical scaling**: out of scope. Use VPA.
- **Cost optimization**: the controller optimizes decision quality, not
  instance pricing. Complement with cost tools (Cast AI, Kubecost) if needed.
- **Traffic prediction / forecasting**: this is a reactive controller with
  trend detection, not a predictive model. It does not forecast future load.
- **ML-based policy**: the control law is a bounded adaptive policy with
  12 parameters. There is no neural network, no gradient descent at runtime,
  no model retraining.
- **Multi-cluster federation**: v1 targets a single cluster.
- **Replacing Prometheus or CloudWatch**: the controller wraps these as data
  sources. It does not collect metrics itself.

---

## 4. Control Loop Timing

| Parameter | Default | Notes |
|-----------|---------|-------|
| Poll interval | 15 s | Prometheus instant query per cycle |
| Rolling normalization window | 240 samples (1 h) | Z-score baseline for signal normalization |
| Identity consolidation interval | ~240 cycles (~1 h) | Slow baseline update |
| Cooldown after executed action | 120 s | No new scaling during this window |
| Replay buffer TTL | 200 cycles (~50 min) | Stale incidents expire |
| Data freshness assumption | Metrics are ≤ 30 s old | Prometheus scrape interval ≤ 15 s assumed |

The controller is a synchronous polling loop. Each cycle runs the full
Sense → Interpret → Decide → Act pipeline. There is no event-driven path;
all decisions are made at poll cadence.

---

## 5. Core Equation and Decision Ordering

### 5.1 Core equation

```
A_t = d_t · G_t · P_t · S_t
```

| Variable | Name | Domain | Sign convention |
|----------|------|--------|-----------------|
| S_t | Pressure | ℝ | Positive = scale-out demand; negative = over-provisioned |
| P_t | Plasticity gate | [0.27, 1.0] | Higher = safer to act |
| G_t | Adaptive gain | [G_min, G_max] | Multiplier on action magnitude |
| d_t | Damping | [0.01, 1.0] | 1.0 = no suppression; lower = more suppression |
| A_t | Action score | ℝ | Positive = scale out; negative = scale in |

A_t is then mapped to a discrete replica delta (see Section 9.4).

### 5.2 Formal definition of S_t (pressure)

Pressure is a weighted average of per-group demand deviations from neutral.
All input metrics are normalized to [0, 1] before pressure computation.
The neutral point is 0.5 (the sigmoid midpoint of z-score normalization).

```
s_group(g) = mean( metric_i - 0.5 )   for metric_i in group g
S_t = (w_infra · s_infra + w_app · s_app + w_biz · s_biz) / W_total
```

Where `W_total` = sum of weights for groups that have at least one metric
present. If a group has no metrics (e.g., no business signals configured),
its weight is redistributed proportionally to the other groups.

**Post-pressure adjustments** (applied sequentially):

| Adjustment | Condition | Effect |
|-----------|-----------|--------|
| Unplanned drop boost | Replicas decreased without a pending scale-in | +0.0 to +0.3 additive |
| Trend boost | Monotonic pressure rise over 20 cycles | Up to +0.15 additive |
| Latency override | Latency rising while CPU is flat | Use latency as independent pressure signal |
| Recovery boost | Pressure crosses zero upward at low replica count | 2.5× multiplicative for 20 cycles |

These adjustments address known failure modes of pure threshold-based
scaling (cascade latency, cold-start recovery, pod eviction detection).

### 5.3 Dependency-safe decision ordering

The decision ordering is strictly feed-forward. No variable depends on
a value computed later in the same cycle.

```
Step 1 — SENSE
  X_t = normalize(prometheus_query())          # Normalized metric vector

Step 2 — PRESSURE
  S_t = weighted_group_average(X_t)            # Depends on: X_t only
  S_t += adjustments(trend, drop, recovery)    # Depends on: S_t history

Step 3 — INTERPRET
  C_t = coherence(X_t)                         # Depends on: X_t only
  R_t = resistance(deploy_status, restarts,    # Depends on: system state
                   recent_scales, variance)
  M_t = |S_t × G_base| / current_replicas     # Depends on: S_t, G_base (constant)

Step 4 — DECIDE
  P_t = sigmoid(k_r · R_t - k_m · M_t + b_p)  # Depends on: R_t, M_t
  G_t = clip(G_base · f_phase · f_coh(C_t),    # Depends on: C_t
             G_min, G_max)
  d_t = exp(-(k_dv · V_excess + k_dc · U_ema)) # Depends on: metric variance, C_t
  A_t = d_t · G_t · P_t · S_t                  # Depends on: all above

Step 5 — ACT
  delta = score_to_action(A_t)                  # Depends on: A_t
  execute_or_recommend(delta)                   # Depends on: operating mode

Step 6 — LEARN
  replay_buffer.maybe_store(M_t, P_t, A_t)     # Depends on: step 4 outputs
  identity_ema.accumulate(X_t, C_t)             # Depends on: step 1, step 3
```

**Circularity note**: M_t uses `G_base` (a constant), not `G_t` (the
cycle-computed gain). This is intentional — misalignment measures the
*potential* magnitude of a change at base gain, not the final modulated
magnitude. This breaks the circular dependency that would exist if M_t
depended on G_t.

---

## 6. Module Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    SENSE                                  │
│  Prometheus → SignalNormalizer → X_t ∈ [0,1]^n           │
│  Input: raw PromQL results                               │
│  Output: normalized metric vector X_t                    │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│                  INTERPRET                                │
│  Pressure:    S_t = weighted_group_avg(X_t)    ∈ ℝ      │
│  Coherence:   C_t = signal_agreement(X_t)      ∈ [0,1]  │
│  Resistance:  R_t = system_stability(events)   ∈ [0,1]  │
│  Misalignment: M_t = |S_t·G_base| / replicas  ∈ [0,∞)  │
│  Identity:    I_t = slow_ema(X_t)              ∈ [0,1]^n │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   DECIDE                                  │
│  Plasticity:  P_t = σ(k_r·R_t - k_m·M_t + b_p)         │
│  Gain:        G_t = clip(G_base · f_phase · f_coh)       │
│  Damping:     d_t = exp(-(k_dv·V_excess + k_dc·U_ema))  │
│  Action:      A_t = d_t · G_t · P_t · S_t               │
│  Delta:       Δreplicas = score_to_action(A_t)           │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│                    ACT                                    │
│  Mode A: Shadow  — log recommendation, no mutation       │
│  Mode B: Approve — webhook notification, human confirms  │
│  Mode C: Auto    — bounded execution via K8s scale API   │
│                                                          │
│  Safety bounds applied before any mutation:               │
│    max scale-out +50%, max scale-in -25%, min replicas   │
└────────────────────────┬─────────────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────────────┐
│                   LEARN                                   │
│  Replay buffer:  store high-stress / low-plasticity events│
│  Identity EMA:   slow baseline consolidation (~1h)       │
│  Outcome track:  heuristic attribution (not causal)      │
└──────────────────────────────────────────────────────────┘
```

---

## 7. Configuration Parameters

12 core parameters control all behavior. Source: `cloud_controller/config.py`.

| # | Parameter | Default | Domain | Role |
|---|-----------|---------|--------|------|
| 1 | `w_infra` | 0.4 | [0, 1] | Infrastructure signal weight (CPU, memory) |
| 2 | `w_app` | 0.4 | [0, 1] | Application signal weight (latency, error rate) |
| 3 | `w_business` | 0.2 | [0, 1] | Business signal weight (queue depth) |
| 4 | `k_r` | 2.0 | ℝ+ | Resistance sensitivity in plasticity gate |
| 5 | `k_m` | 2.0 | ℝ+ | Misalignment suppression in plasticity gate |
| 6 | `b_p` | -1.0 | ℝ | Plasticity bias floor (σ(-1) ≈ 0.27) |
| 7 | `G_base` | 1.0 | ℝ+ | Base gain |
| 8 | `G_min` | 0.0 | ℝ≥0 | Minimum gain (0 = allow "do nothing") |
| 9 | `G_max` | 3.0 | ℝ+ | Maximum gain cap |
| 10 | `k_dv` | 1.0 | ℝ+ | Metric variance sensitivity for damping |
| 11 | `k_dc` | 0.5 | ℝ+ | Coherence instability sensitivity for damping |
| 12 | `α_base` | 0.01 | (0, 1) | Identity EMA base learning rate |

Auxiliary (not in core 12): `replay_buffer_size` (256), `replay_ttl` (200 cycles),
`min_replicas` (1), `cooldown_seconds` (120).

---

## 8. Module Specifications — Sense

### 8.1 Signal Ingestion

**Input**: Prometheus HTTP API (`/api/v1/query` instant queries).

MVP metric set:

| Signal | PromQL | Normalization |
|--------|--------|---------------|
| CPU utilization | `rate(node_cpu_seconds_total{mode!="idle"}[2m])` | z-score + sigmoid |
| Memory pressure | `1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)` | Direct ratio [0,1] |
| Latency p99 | `histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[2m]))` | z-score + sigmoid |
| Error rate | `rate(http_requests_total{code=~"5.."}[2m]) / rate(http_requests_total[2m])` | Direct ratio [0,1] |
| Queue depth | Application-specific (e.g., `queue_messages_ready`) | z-score + sigmoid |
| Pod restarts | `rate(kube_pod_container_status_restarts_total[10m])` | > 0 = instability flag |
| Current replicas | `kube_deployment_status_replicas` | Used for M_t and safety bounds |

**Output**: Normalized state vector `X_t ∈ [0, 1]^n`.

### 8.2 Normalization

Two strategies, chosen per metric:

**Z-score + sigmoid** (for unbounded metrics: CPU, latency, queue depth):
```
z = (value - rolling_mean) / rolling_std
normalized = sigmoid(z)
```
Rolling window: 240 samples (1 hour at 15 s intervals). Before `min_samples`
are collected, return 0.5 (neutral). On startup, the window can be
pre-filled from a 1-hour Prometheus `query_range`.

**Direct ratio** (for metrics already in [0, 1]: memory utilization, error rate):
```
normalized = clamp((value - low) / (high - low), 0, 1)
```

### 8.3 Missing signal handling

If an expected metric returns no data from Prometheus (scrape gap, exporter
down), it is omitted from X_t. The coherence model degrades its
`signal_health` score by 0.15 per missing metric (floor 0.3), which reduces
overall coherence and makes the controller more cautious. The pressure
computation redistributes weight from empty groups to populated groups.

---

## 9. Module Specifications — Interpret and Decide

### 9.1 Coherence Model

Source: `cloud_controller/core/coherence.py`

Coherence answers: "do the signals agree that something is actually happening?"

**Within-group agreement** (per metric group):
```
agreement(group) = 1.0 - normalized_variance(group_metrics)
```
A single-metric group returns 0.5 (incomplete evidence).

**Cross-group agreement**:
```
c_cross = 1.0 - min(variance(group_means) / 0.25, 1.0)
```

**Overall coherence**:
```
C_raw = 0.7 · mean(within_group_agreements) + 0.3 · c_cross
C_raw *= signal_health                    # Degrade for missing signals
C_t = ema(C_raw, beta=0.7)               # Temporal smoothing
```

Hysteresis band of ±0.05 prevents oscillation when C_t hovers near a
decision threshold.

**Interpretation**: C_t ≈ 1.0 means all signals agree the system is under
pressure. C_t ≈ 0.3 means only one signal group is elevated (e.g., CPU
spike but latency/errors flat) — likely a false alarm.

### 9.2 Resistance Model

Source: `cloud_controller/controller.py` lines 660-701

Resistance R_t ∈ [0, 1] represents how fragile the system currently is.
Computed as multiplicative penalties from 1.0:

```
R_t = 1.0
if deploy_active:           R_t *= 0.6       # -40%
if recent_restarts > 0:     R_t *= max(0.5, 1.0 - restarts × 0.1)
if recent_scales > 0:       R_t *= max(0.5, 1.0 - scales × 0.1)
if metric_variance > 0:     R_t *= max(0.7, 1.0 - variance × 2.0)
R_t = clamp(R_t, 0.0, 1.0)
```

"Recent" means within the last 20 controller cycles (~5 minutes).

R_t is **not** identity-relative — it depends only on observable system
state. The multiplicative form means penalties compound: a deploy during
high variance and recent scaling produces very low resistance.

### 9.3 Identity EMA (Adaptive Baseline)

Source: `cloud_controller/core/identity_ema.py`

The identity EMA learns "what normal looks like" for this service.
It is a **per-service** baseline, not global.

**Fast loop** (every cycle): accumulate the current metric vector, weighted
by salience (only when coherence > 0.3):
```
accumulator = ema_decay · accumulator + (1 - ema_decay) · X_t
```

**Slow loop** (every ~240 cycles, ~1 hour): conditionally update the
baseline:
```
agreement = max(0, (cosine_sim(accumulator, baseline) + 1) / 2)
stability = 1 / (1 + var(accumulator))
α_eff = clamp(α_base · stability · agreement, 0.1 · α_base, 5 · α_base)
baseline = (1 - α_eff) · baseline + α_eff · normalize(accumulator)
```

**Key property**: the baseline updates slowly and only when the system
is stable AND new observations agree with the existing baseline. An
anomaly (DDoS, cascading failure) does not corrupt the baseline because
`agreement` drops, which reduces `α_eff` to near-zero.

**Bootstrap**: on first run, the baseline can be seeded from the mean of
a 1-hour historical Prometheus query. Without historical data, it
initializes to a neutral vector (all 0.5) and converges within ~2 hours.

**Identity deviation**: cosine distance between current X_t and baseline
I_t. Reported in decision logs. Not used in the control equation directly;
it is an observability signal for operators.

### 9.4 Misalignment Model

```
M_t = |S_t × G_base| / max(current_replicas, 1)
```

M_t measures how large the proposed change is relative to current scale.
It uses `G_base` (a configuration constant), not `G_t`, to avoid circular
dependency (see Section 5.3).

Examples:
- S_t=0.4, G_base=1.0, replicas=10 → M_t = 0.04 (small, gate stays open)
- S_t=1.0, G_base=1.0, replicas=2 → M_t = 0.50 (large, gate partially closes)

### 9.5 Plasticity Gate

Source: `cloud_controller/core/plasticity_gate.py`

```
P_t = σ(k_r · R_t - k_m · M_t + b_p)
```

| R_t | M_t | P_t | Interpretation |
|-----|-----|-----|----------------|
| 1.0 (stable) | 0.0 (small change) | 0.73 | Open — safe to act |
| 1.0 (stable) | 1.0 (large change) | 0.27 | Cautious — large change to stable system |
| 0.0 (fragile) | 0.0 (small change) | 0.27 | Cautious — system already unstable |
| 0.0 (fragile) | 1.0 (large change) | 0.007 | Effectively closed |

**Floor**: σ(b_p) = σ(-1.0) ≈ 0.27. The gate never fully closes. This
is a deliberate safety property — even in the worst case, ~27% of the
action signal passes through, preventing total lockout during genuine
emergencies.

### 9.6 Adaptive Gain

Source: `cloud_controller/core/adaptive_gain.py`

```
f_phase = time_of_day_multiplier(current_time)
f_coh   = 0.5 + 0.5 / (1 + exp(-(C_t - 0.5) × 4.0))
target  = clip(G_base · f_phase · f_coh, G_min, G_max)
G_t     = clamp(target, prev_G - max_delta, prev_G + max_delta)
```

Where `max_delta = G_base × 0.1` (gain changes by at most ±10% of G_base
per cycle).

**Time-of-day phase** (implementation choice, not a product constraint):

| Phase | f_phase | When |
|-------|---------|------|
| Peak | 1.0 | Configurable (e.g., 09:00-18:00) |
| Normal | 0.8 | Default outside peak |
| Off-peak | 0.6 | Configurable (e.g., 22:00-06:00) |
| Maintenance | 0.3 | Configurable blackout windows |

**Rate limiting** prevents scaling oscillation: from G_min=0.0 to G_max=3.0
takes a minimum of 30 cycles (~7.5 minutes).

### 9.7 Damping

Source: `cloud_controller/core/damping.py`

Damping suppresses action when metrics are volatile.

**Asymmetric EMA** (fast spike detection, faster recovery):
```
if variance > V_ema:
    V_ema = 0.90 · V_ema + 0.10 · variance    # Detect spike: α=0.10
else:
    V_ema = 0.80 · V_ema + 0.20 · variance    # Recover: α=0.20
```

**Baseline-relative damping** (self-calibrating):
```
V_baseline = 0.999 · V_baseline + 0.001 · variance
V_excess = max(0, V_ema / V_baseline - 1.0)
exponent = -(k_dv · V_excess + k_dc · U_ema)
d_t = exp(clamp(exponent, -10, 0))
d_t = max(d_t, 0.01)                          # Hard floor
d_t = clamp(d_t, prev_d ± 0.1)                # Rate limit
```

**Why baseline-relative**: a batch-processing workload has naturally high
metric variance. Raw-variance damping would permanently suppress it.
Baseline-relative damping only activates when variance exceeds the
service's own normal level.

### 9.8 Action Policy and Scale-In

**Action score to replica delta mapping**:

| |A_t| Range | Action |
|-------------|--------|
| < 0.05 | No action (dead zone) |
| 0.05 – 0.2 | Log recommendation only |
| 0.2 – 0.5 | ±1 replica |
| 0.5 – 1.0 | ±2 replicas |
| > 1.0 | ±3 replicas (bounded by safety limits) |

Sign of A_t determines direction: positive = scale out, negative = scale in.

**Scale-in asymmetry** (conservative by design):

Scale-in uses 2× the threshold of scale-out. This means stronger negative
pressure is required to remove replicas than to add them. Rationale:
adding a pod is fast and low-risk; removing a pod can cause request
failures if load returns.

Additional scale-in protections:
- **Maximum rate**: -1 replica per cycle normally. -2 only after 30+
  sustained calm cycles (pressure < -0.02).
- **Baseline memory floor**: never scale below 80% of the highest
  replica count observed in the recent window. This prevents collapse
  to minimum replicas immediately after a demand spike.
- **Minimum replicas**: never below the configured `min_replicas`.
- **Weak-signal forced drain**: if A_t < -0.005 AND replicas > 10
  AND sustained calm > 15 cycles, force -1 to escape the "stuck at
  high replicas" plateau. Still respects the baseline memory floor.

---

## 10. Module Specifications — Act

### 10.1 Operating Modes

| Mode | Behavior | K8s permissions required |
|------|----------|------------------------|
| Shadow (DRY_RUN) | Log decisions, compare to HPA, no mutations | Read-only (get deployments, get pods) |
| Approve | Webhook notification, human confirms | Read + write (patch scale) |
| Autonomous | Bounded auto-execution | Read + write (patch scale) |

Mode is set per deployment at configuration time. Recommend starting in
Shadow for ≥2 weeks before enabling Approve or Autonomous.

### 10.2 Actuator: Kubernetes Scale API

Source: `cloud_controller/action/k8s_actuator.py`

The controller scales workloads via the standard Kubernetes scale subresource:

```
PATCH /apis/apps/v1/namespaces/{ns}/deployments/{name}/scale
Content-Type: application/strategic-merge-patch+json
{"spec": {"replicas": <desired>}}
```

This is the same API that `kubectl scale` uses. It works with Deployments
and StatefulSets. The controller authenticates via in-cluster ServiceAccount
or explicit kubeconfig.

**Retry**: max 2 retries with 1 s delay on API errors (429, 5xx).

**Alternative mode (HPA_METRIC)**: instead of patching replicas directly,
the controller can expose `action_score` as a Prometheus metric. HPA is
then configured with a custom metric target pointing at that metric. This
preserves HPA as the pod lifecycle manager while the controller provides
the decision signal. (Note: this mode is scaffolded but not production-ready;
it requires a Prometheus adapter or custom metrics APIService.)

### 10.3 Safety Bounds

Source: `cloud_controller/recommend/safety.py`

These limits are enforced on every action, regardless of operating mode,
even after human approval:

| Bound | Default | Rationale |
|-------|---------|-----------|
| Max scale-out per action | +50% of current replicas | Prevent runaway scaling |
| Max scale-in per action | -25% of current replicas | Gradual drain |
| Minimum replicas | 1 (configurable) | Never scale to zero |
| Post-action cooldown | 120 s | Let metrics stabilize before next decision |

### 10.4 Policy Engine

Source: `cloud_controller/action/policy.py`

Customer-configurable rules layered on top of safety bounds:

- **Absolute replica bounds**: min/max replicas per deployment
- **Blackout windows**: time ranges where scaling is blocked (supports
  day-of-week, wraps midnight)
- **Rate limits**: max actions per deployment per hour
- **Per-deployment overrides**: different policies per namespace/deployment

### 10.5 Recommendation Pipeline

Source: `cloud_controller/recommend/engine.py`

```
Controller ActionResult
  → Confidence scoring (action_score > threshold AND coherence > threshold)
  → Dedup check (skip if pending recommendation for same service)
  → Safety bounds (clamp delta)
  → Policy engine (blackout, rate limit, absolute bounds)
  → Create Recommendation (PENDING state)
  → Webhook notifications (Slack, PagerDuty, OpsGenie)
  → Approval tracking
  → On approval → Actuator executes
```

Confidence levels:
- NONE: |A_t| ≤ 0.3 or C_t ≤ 0.5
- LOW: marginal scores
- MEDIUM: A_t ∈ [0.5, 0.7] and C_t > 0.5
- HIGH: A_t > 0.7 and C_t > 0.8

Only MEDIUM and HIGH produce notifications. LOW is logged only.

---

## 11. Module Specifications — Learn

### 11.1 Replay Buffer

Source: `cloud_controller/core/replay_buffer.py`

**Store trigger**: M_t > 0.3 AND P_t < 0.4 (the system was stressed and
the gate was partially closed — these are the interesting events to
remember).

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

- Capacity: 256 entries (configurable)
- TTL: 200 cycles (~50 min) — stale entries expire
- Eviction: when full, sort by priority, remove lowest (not FIFO)
- Sampling: probability-proportional to priority

### 11.2 Baseline Adaptation

Handled by Identity EMA (Section 9.3). No separate service needed.

### 11.3 Outcome Tracking

After each executed action, the controller observes whether metrics
improved within a configurable window (default: 5 minutes):

- Did latency p99 decrease?
- Did error rate decrease?
- Did scaling oscillation occur (scale up then down within 10 min)?
- Was the action overridden by a human?

**Important caveat**: outcome attribution is **heuristic, not causal**.
The controller cannot distinguish "metrics improved because of the scaling
action" from "metrics improved because load naturally decreased." The
outcome score is used only to adjust replay buffer priority weights —
it does not directly modify the 12 core parameters. Any future parameter
auto-tuning (Section 16.5) must treat these outcomes as noisy signals,
not ground truth.

**Implementation status**: outcome tracking is defined but not yet wired
into the production recommendation pipeline. Replay buffer priority is
currently set at store time based on M_t and P_t values.

---

## 12. Safety Invariants

These properties hold unconditionally, regardless of parameter values,
operating mode, or input signals:

| Invariant | Mechanism | Bound |
|-----------|-----------|-------|
| Plasticity never fully closes | σ(b_p) floor | P_t ≥ 0.27 |
| Damping never fully suppresses | Hard floor | d_t ≥ 0.01 |
| Gain is bounded | Clamp | G_t ∈ [G_min, G_max] |
| Gain changes slowly | Rate limit | ΔG ≤ G_base × 0.1 per cycle |
| Damping changes slowly | Rate limit | Δd ≤ 0.1 per cycle |
| Scale-out bounded per action | Safety bounds | ≤ +50% of current replicas |
| Scale-in bounded per action | Safety bounds | ≤ -25% of current replicas |
| Minimum replicas enforced | Hard floor | ≥ min_replicas (default 1) |
| Post-action cooldown | Timer | 120 s no-act window |
| Baseline not corrupted by anomalies | Conditional α_eff | Requires stability + agreement |
| Scale-in requires stronger signal | 2× threshold asymmetry | Harder to remove than to add |
| Baseline memory floor | 80% of recent peak | Prevents collapse after spike |

---

## 13. Failure Modes and Fallback Behavior

| Failure | Detection | Fallback |
|---------|-----------|----------|
| Prometheus unreachable | HTTP timeout / connection error | Skip cycle, log warning. After N consecutive failures, alert operator. Controller takes no action without fresh data. |
| K8s API unreachable | API client error on PATCH | Retry 2× with 1 s delay. If still failing, log error and skip execution. Recommendation stays PENDING. |
| All metrics missing | Empty X_t | pressure = 0 → A_t = 0 → no action. Signal health degrades coherence. |
| NaN / Inf in computation | Checked per module | Clamp or skip. d_t and G_t have hard floors. P_t is bounded by sigmoid. |
| Controller process crash | Standard K8s liveness probe | Deployment restarts the pod. State is lost (acceptable — controller converges within minutes from neutral). Identity EMA baseline is optionally persisted to a ConfigMap or PVC. |
| HPA and controller conflict | Both try to set replicas | Avoided by operating mode: in Shadow, controller doesn't mutate. In Autonomous, HPA should be disabled or set to wide min/max as emergency backstop. In HPA_METRIC mode, HPA is the sole actuator. |
| Scaling oscillation detected | 2+ opposing actions within 10 min | Resistance drops (recent_scales penalty), plasticity gate closes, damping increases. Controller self-suppresses. |

**Design principle**: the controller fails safe. On any error, it does
nothing rather than taking a potentially harmful action. The worst case
for a controller failure is "scaling reverts to whatever was configured
before" (HPA, manual, or nothing).

---

## 14. Observability and Explainability

Every decision produces a structured log entry. Example:

```
[2026-03-29 14:23:01] Decision: HOLD
  Pressure (S_t):      0.72 (moderate — CPU 78%, latency p99 rising)
  Coherence (C_t):     0.31 (low — only CPU elevated, queue/errors flat)
  Resistance (R_t):    0.45 (fragile — scaled 2× in last 8 minutes)
  Misalignment (M_t):  0.40 (moderate — proposed +3 replicas from 5)
  Plasticity (P_t):    0.21 (closed)
  Gain (G_t):          0.44
  Damping (d_t):       0.31 (high variance suppression active)
  Action Score (A_t):  0.02 → NO ACTION
  Identity deviation:  0.18 (normal)
  Reason: Incoherent pressure + recent scaling instability
```

**Prometheus metrics exported by the controller** (for dashboarding):

| Metric | Type | Description |
|--------|------|-------------|
| `ncc_pressure` | Gauge | S_t per service |
| `ncc_coherence` | Gauge | C_t per service |
| `ncc_resistance` | Gauge | R_t per service |
| `ncc_plasticity` | Gauge | P_t per service |
| `ncc_gain` | Gauge | G_t per service |
| `ncc_damping` | Gauge | d_t per service |
| `ncc_action_score` | Gauge | A_t per service |
| `ncc_replicas_current` | Gauge | Current replica count |
| `ncc_replicas_recommended` | Gauge | Recommended replica count |
| `ncc_decisions_total` | Counter | Total decisions by type (hold/scale_out/scale_in) |
| `ncc_actions_executed_total` | Counter | Actions actually executed |

---

## 15. Product Integration Model

The controller is an **external decision layer**. It does not modify or
replace the internals of any cloud product. It reads metrics from standard
APIs and writes scaling commands through standard APIs.

| System | Relationship | How |
|--------|-------------|-----|
| Prometheus | **Reads from** | Standard HTTP query API (`/api/v1/query`) |
| Kubernetes Deployments | **Writes to** | `PATCH .../deployments/{name}/scale` (standard scale subresource) |
| Kubernetes HPA | **Replaces or coexists** | In Autonomous mode, disable HPA or set wide min/max as backstop. In HPA_METRIC mode, controller provides a custom metric that HPA consumes. In Shadow mode, HPA runs normally; controller observes. |
| KEDA | **Coexists** | KEDA handles event-driven scaling (queue triggers, cron). Controller handles multi-signal steady-state scaling. No conflict if targeting different deployments. If targeting the same deployment, one should be primary. |
| ArgoCD | **Future: gate integration** | Planned: controller exposes a readiness endpoint; ArgoCD pre-sync hook checks it. Not yet implemented. |
| AWS ASG / Azure VMSS | **Out of scope for v1** | The controller targets Kubernetes. ASG/VMSS integration would require separate actuator implementations using their respective APIs. |
| CloudWatch / Azure Monitor | **Potential future metric source** | Not implemented in v1. Would require a signal adapter similar to the Prometheus adapter. |
| Slack / PagerDuty / OpsGenie | **Sends notifications to** | Webhook integration for Approve mode recommendations. |

**What this controller does NOT do**:
- It does not run inside HPA. It is a separate Deployment.
- It does not intercept or monkey-patch Kubernetes controllers.
- It does not require CRDs or admission webhooks (though a future
  deployment gate could optionally use an admission webhook).
- It does not require cluster-admin privileges. It needs `get` on
  deployments/pods/events and `patch` on the scale subresource.

---

## 16. Implementation Stages

### 16.1 Stage 1 — Core Library (no cloud dependencies)

**Goal**: standalone Python package testable with synthetic signals.

**Deliverable**: `cloud_controller/` package with:
- `core/`: plasticity_gate, adaptive_gain, damping, identity_ema,
  coherence, replay_buffer
- `controller.py`: `Controller.step(metrics, ...) → ActionResult`
- `config.py`: 12-parameter `InfraControllerConfig`

No Prometheus, no Kubernetes, no network calls. Pure computation.

**Validation**: unit tests with known input/output pairs:
- P_t ≈ 0.007 when R_t=0, M_t=1
- d_t < 0.4 when variance is 5× baseline
- G_t rate-limits to ±10% per step
- Identity EMA does not update when stability < 0.2

### 16.2 Stage 2 — Prometheus Integration

**Goal**: read real metrics from a Kubernetes cluster.

**Deliverable**: `signals/` package with:
- Prometheus HTTP client
- Signal normalizer (z-score + sigmoid or direct ratio)
- Signal pipeline (poll loop, phase detection)
- Resistance estimator

**Validation**: run against a test cluster with `k6` or `locust`:
- Steady load → no action (correct baseline)
- Ramp up → controller recommends scale-out
- Spike + recover → controller damps, avoids thrash

### 16.3 Stage 3 — Shadow Mode

**Goal**: run alongside existing HPA, log divergence, measure value.

**Deliverable**: Shadow runner that:
- Polls metrics, runs controller, records recommendation
- Watches `kube_hpa_status_desired_replicas` for what HPA actually did
- Logs every divergence with explanation
- Produces weekly summary (agreements, early catches, prevented thrash,
  false negatives)

**Deployment**: Kubernetes Deployment with read-only RBAC. Zero write
permissions.

**Validation**: run for ≥2 weeks on a real cluster. Manual review of all
divergences. Tune parameters based on false positive/negative rates.

### 16.4 Stage 4 — Recommend Mode

**Goal**: controller sends recommendations, human approves.

**Deliverable**:
- Webhook notifications (Slack/PagerDuty/OpsGenie)
- Approval API (human clicks approve → controller executes)
- Confidence scoring (only recommend when score AND coherence exceed
  thresholds)

**Safety**: all safety bounds (Section 10.3) enforced even after approval.

### 16.5 Stage 5 — Autonomous Mode

**Goal**: bounded auto-execution.

**Deliverable**:
- K8s actuator (PATCH deployment scale)
- Policy engine (rate limits, blackout windows, absolute bounds)
- Post-action cooldown
- Audit log (every action with full state snapshot)

**Rollout**: staging for 2 weeks → canary on one production service →
expand after validation.

### 16.6 Stage 6 — Learning Loop (future)

**Goal**: controller improves over time using outcome data.

**Approach** (conservative):
- Replay-driven parameter review: sample replay entries, simulate what
  different parameters would have produced, identify systematic errors
- Parameter changes applied with warmup ramp (no sudden jumps)
- Multi-service: one controller instance per service, optionally shared
  cluster-wide identity EMA for common patterns

**Caveat**: outcome attribution is heuristic (Section 11.3). Any automated
parameter tuning must be treated as an optimization over noisy signals,
not deterministic reward. Human review of proposed parameter changes is
recommended before applying them.

---

## 17. Validation Plan

### 17.1 Unit tests (Stage 1)

Test each module in isolation with deterministic inputs. Verify all
safety invariants from Section 12 hold under adversarial inputs
(NaN, Inf, extreme values, empty metrics).

### 17.2 Simulation tests (Stage 1-2)

Synthetic signal generators for common patterns:
- Steady state (no action expected)
- Linear ramp (scale-out expected)
- Spike + recovery (damp expected, no thrash)
- Rolling deployment (resistance drops, gate closes)
- Cascading latency (latency override fires)
- Single-metric false alarm (coherence suppresses)

### 17.3 Shadow validation (Stage 3)

| Metric | Target |
|--------|--------|
| Agreement with HPA | > 85% (most decisions should agree) |
| Prevented thrash | > 0 (controller catches at least some unnecessary scaling) |
| False negatives | < 5% (controller rarely misses genuine need to scale) |
| Decision latency | < 1 s per cycle |

### 17.4 Production validation (Stage 4-5)

- All actions audited for 30 days
- No scaling oscillation caused by the controller
- Latency p99 does not degrade compared to HPA-only baseline
- Operator satisfaction: recommendations are understandable and actionable

---

## 18. File Layout

```
cloud_controller/
├── __init__.py
├── config.py                  # 12-parameter InfraControllerConfig
├── controller.py              # Main: sense → interpret → decide → act → learn
├── core/
│   ├── plasticity_gate.py     # P_t
│   ├── adaptive_gain.py       # G_t
│   ├── damping.py             # d_t
│   ├── identity_ema.py        # Baseline learning
│   ├── coherence.py           # C_t
│   └── replay_buffer.py       # Priority-weighted incident memory
├── signals/
│   ├── normalizer.py          # Raw metrics → [0,1]
│   ├── prometheus.py          # Prometheus query adapter
│   ├── pipeline.py            # Poll loop, phase detection
│   └── resistance.py          # R_t computation
├── action/
│   ├── policy.py              # Customer safety rules
│   ├── k8s_actuator.py        # PATCH deployment scale
│   └── feedback.py            # Post-action outcome observation
├── recommend/
│   ├── engine.py              # Recommendation pipeline
│   ├── confidence.py          # Confidence scoring
│   ├── safety.py              # Hard safety bounds
│   └── webhook.py             # Slack/PagerDuty/OpsGenie notifications
├── shadow/
│   └── reporter.py            # Shadow mode divergence logging
├── observability/
│   ├── exporter.py            # Prometheus metric export
│   └── decision_log.py        # Structured decision logging
└── orchestrator.py            # Production loop orchestration
```
