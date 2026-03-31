# Scaling Controller Architecture: Futility-Aware Autoscaling

## 1. Problem

Metric-driven autoscalers share a structural blind spot: they cannot distinguish between "metrics are bad because we need more replicas" and "metrics are bad for reasons replicas cannot fix."

When latency rises, the controller scales out. If the root cause is an upstream cascade failure, a corrupted metric, or backpressure from an unrelated service, adding replicas does nothing. But the controller sees the same elevated latency, issues another scale-out, and the cycle continues until hitting a budget cap or infrastructure limit.

Three adversarial patterns expose this:

**Cascading latency injection.** An upstream service fails. Latency climbs across all downstream services regardless of their replica count. The controller interprets this as capacity exhaustion and scales from 4 to 46 replicas before any signal reverses. Cost: 4.47x optimal.

**Noisy metrics.** Random CPU spikes (15% of cycles) trigger small scale-outs. Each individual decision is locally rational. Cumulatively, replicas drift to 31 when 5 are needed. Cost: 4.37x optimal.

**Conflicting signals.** CPU reads low while latency reads high. The controller correctly detects the latency anomaly and scales out, but the problem is a measurement conflict, not a capacity deficit.

The fundamental limitation: the controller's signal chain (`A_t = d_t * G_t * P_t * S_t`) computes *intent to scale* from metric signals. It has no mechanism to evaluate *whether previous scaling actually helped*. Intent and effectiveness are conflated.

---

## 2. Design

The architecture separates intent, evaluation, and execution into three independent layers.

```
Metrics ──► Controller ──► raw_delta ──► FutilityGuard ──► guarded_delta ──► Actuation
                               │                ▲
                               │                │
                               ▼                │
                        EfficiencyEstimator ────┘
                        (observe + classify)
```

### Layer 1: Controller (Intent)

The controller computes a scaling action from the multiplicative signal chain:

```
A_t = damping * gain * plasticity * pressure
```

This produces `raw_delta`: the controller's best judgment given its input signals. The controller is **frozen** — its thresholds, weights, and decision logic are not modified by the layers below.

### Layer 2: EfficiencyEstimator (Evaluation)

After each scale-out event, the estimator opens a 5-cycle evaluation window and measures:

| Signal | Computation | Positive = Helped |
|---|---|---|
| Marginal CPU change | CPU/replica before vs after | Per-replica load decreased |
| Latency improvement | p99 before vs after | Latency dropped |
| Error improvement | Error rate before vs after | Errors dropped |
| Utilization efficiency | CPU/replica vs baseline | Replicas are doing work |

Each event is classified:

- **HELPING** — at least two metrics improved significantly
- **NEUTRAL** — no meaningful change in either direction
- **NOT_HELPING** — no improvement, or utilization collapsed (CPU/replica < 30% of baseline)

The estimator is **observational only**. It has no write path to the controller. It answers one question: "Did that scale-out actually improve anything?"

### Layer 3: ScaleOutFutilityGuard (Execution Filter)

The guard monitors the estimator's output and blocks scale-out when it is provably ineffective.

**Activation requires all of:**
1. NOT_HELPING for >= 5 consecutive cycles
2. Current replicas >= 20
3. (When confidence gating is enabled) Average streak confidence >= threshold

**When active:**
```
delta = min(delta, 0)
```

**Hard constraints:**
- Never activates below 20 replicas
- Never triggers on a single NOT_HELPING cycle
- Never modifies negative delta (scale-in passes through unchanged)
- Resets immediately when the estimator reports HELPING

The guard does not make scaling decisions. It vetoes decisions that the estimator has classified as futile.

---

## 3. Key Design Principles

**Controller remains frozen.** The signal chain (`A_t`) is not modified. No new multiplicative factors, no threshold changes, no additional inputs. The controller computes intent exactly as before.

**Estimator is observational.** It reads metrics and delta history. It writes nothing back to the controller. Removing it changes no scaling behavior.

**Guard operates at the execution layer.** It sits between the controller's decision and actuation. It can only suppress; it cannot initiate. This is the same architectural position as a budget cap or rate limiter — an execution-layer safety constraint.

**Intent and execution are separated.** The controller says "scale out." The estimator says "that won't help." The guard says "then don't." Each layer has a single responsibility and a clean interface. The controller never knows its deltas were blocked. The estimator never knows whether the guard acted on its output.

---

## 4. Validation Results

Tested across 19 adversarial scenarios covering signal corruption, actuation delay, system shocks, budget constraints, and controller pathologies.

### Safety

| Metric | Result |
|---|---|
| Catastrophic failures | 0 |
| Severe failures | 0 |
| SLO regressions | 0 (across all 19 scenarios) |
| Severity regressions | 0 |
| False positives | 0 (no beneficial scale-out was blocked) |

### Cost Reduction

| Scenario | Before Guard | After Guard | Savings |
|---|---|---|---|
| cascading_failure | 4.47x | 3.36x | -1.11x |
| noisy_spikes | 4.37x | 3.60x | -0.77x |
| cold_start_amplification | 3.31x | 2.93x | -0.38x |
| hidden_demand | 2.41x | 2.21x | -0.20x |
| coherence_oscillation | 3.77x | 3.67x | -0.10x |

### Guard Statistics

| Metric | Value |
|---|---|
| Total scale-out events | 649 |
| Blocked by guard | 87 (13.4%) |
| Scenarios affected | 5 of 19 |
| Scenarios unchanged | 14 of 19 |

The guard intervenes in exactly the scenarios where scaling is ineffective and is invisible in all others.

### Severity Distribution

| Level | Count |
|---|---|
| PASS | 9 |
| MILD | 3 |
| MODERATE | 7 |
| SEVERE | 0 |
| CATASTROPHIC | 0 |

---

## 5. Confidence Gating Analysis

The estimator produces a confidence score (0-1) for each classification. We tested whether requiring minimum confidence before guard activation would reduce false positives.

### What Was Tested

Adding a confidence gate to the guard: activate only when the average confidence across the NOT_HELPING streak exceeds a threshold (tested at 0.4, 0.5, 0.6).

### Why It Was Not Enabled

**Timing mismatch.** The estimator's evaluation window is 5 cycles. During rapid scale-out (the exact phase where the guard adds most value), classifications are tentative with confidence ~0.30. By the time evaluations complete and confidence rises to 0.70-0.80, the scale-out burst is over and there is nothing left to block.

Concrete example: in cascading_failure, the guard needs to activate at cycle 131 (replicas = 26). At threshold 0.5, the first evaluated confidence arrives at cycle 139. By then, without the guard, replicas would be at 30+ and the controller has stopped issuing +1 deltas. The confidence gate reduces blocked events from 22 to 5 and increases cost from 3.36x to 3.70x.

**No false positives to filter.** Across all 19 scenarios, the guard without confidence gating produced zero false positives — no SLO regressions, no severity regressions. Confidence gating solves a problem that does not exist in the current scenario set.

### Conclusion

Confidence data is captured and reported for observability. The gating threshold is set to 0.0 (disabled). If a future scenario demonstrates a false positive, the infrastructure is ready to enable at threshold 0.5.

---

## 6. Final Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SCALING SYSTEM                        │
│                                                         │
│  ┌──────────────┐   raw_delta   ┌──────────────────┐   │
│  │  Controller   │─────────────►│  FutilityGuard    │   │
│  │  (intent)     │              │  (execution gate) │   │
│  │              │              │                    │   │
│  │  A_t = d*G*P*S│              │  IF not_helping≥5 │   │
│  │  → delta      │              │  AND replicas≥20  │   │
│  └──────────────┘              │  THEN delta=0     │   │
│         │                       └────────┬─────────┘   │
│         │ metrics                        │              │
│         ▼                        guarded_delta          │
│  ┌──────────────┐                        │              │
│  │  Efficiency   │────── state ──────────┘              │
│  │  Estimator    │                                      │
│  │  (evaluate)   │        ┌──────────────┐              │
│  │               │───────►│  Report      │              │
│  │  HELPING /    │        │  (observe)   │              │
│  │  NOT_HELPING  │        └──────────────┘              │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

**Controller** = decision engine. Computes intent from metric signals. Frozen.

**EfficiencyEstimator** = causality detector. Evaluates whether scaling actions improved metrics. Observational.

**ScaleOutFutilityGuard** = safety execution filter. Blocks scale-out when consecutive evidence shows it is ineffective. Suppressive only.

The system reduces cost by 0.10x-1.11x on adversarial scenarios, blocks 13.4% of scale-outs, produces zero false positives, and preserves all SLOs. The controller does not know the guard exists. The guard does not know the controller's reasoning. Each layer operates on its own evidence within its own scope.
