# Configuration

`InfraControllerConfig` is a 12-parameter controller configuration (plus auxiliary
and operational fields). Defaults are conservative for cloud scaling. Behavior is
**unchanged** from the pre-packaging controller; this document only describes it.

```python
from ugence_cloud_scaling_controller import InfraControllerConfig, CloudScalingController
cfg = InfraControllerConfig(w_infra=0.4, w_app=0.4, w_business=0.2)
ctrl = CloudScalingController(cfg)
```

## Core equation

```
Action_t = d_t * G_t * P_t * S_t
  P_t = sigmoid(k_r * R_t - k_m * M_t + b_p)          # plasticity gate
  G_t = clip(G_base * f_phase * f_coh, G_min, G_max)  # adaptive gain
  d_t = exp(-k_dv * V_excess - k_dc * U_t)            # damping
  S_t = weighted pressure from normalized metrics     # signal
```

## Parameters

| Field | Default | Meaning |
|-------|---------|---------|
| `w_infra` | 0.4 | Infrastructure signal weight (cpu, memory). |
| `w_app` | 0.4 | Application signal weight (latency_p99, error_rate). |
| `w_business` | 0.2 | Business signal weight (queue_depth). |
| `k_r` | 2.0 | Plasticity: resistance openness scaling. |
| `k_m` | 2.0 | Plasticity: misalignment suppression scaling. |
| `b_p` | -1.0 | Plasticity: bias floor (gate never fully closes). |
| `G_base` | 1.0 | Base gain (higher → more aggressive scaling). |
| `G_min` | 0.0 | Minimum gain (0 allows "do nothing"). |
| `G_max` | 3.0 | Maximum gain. |
| `k_dv` | 1.0 | Damping: metric variance sensitivity. |
| `k_dc` | 0.5 | Damping: coherence instability sensitivity. |
| `alpha_base` | 0.01 | Identity EMA learning rate. |
| `replay_buffer_size` | 256 | Replay buffer capacity. |
| `replay_ttl` | 200 | Cycles before replay entries expire. |
| `identity_dim` | 5 | Baseline state-vector dimension. |
| `cycle_interval_seconds` | 15.0 | Evaluation cadence (advisory metadata). |
| `warmup_steps` | 100 | Warmup cycles (delta clamped during warmup). |
| `damping_warmup_steps` | 50 | Cycles holding d=1.0 after start. |
| `consolidation_interval` | 240 | Cycles between identity updates. |
| `replay_interval` | 100 | Cycles between replay sampling. |
| `action_thresholds` | `{no_action:0.05, recommend:0.2, scale_1:0.5, scale_2:1.0}` | Score→action mapping. |
| `max_scale_out_ratio` | 0.5 | Max +50% replicas per action. |
| `max_scale_in_ratio` | 0.25 | Max -25% replicas per action. |
| `min_replicas` | 1 | Never recommend below this. |

## Safety bounds & behavior notes

- **Asymmetric scale-in:** scale-in requires 2× the action score of scale-out.
- **Startup clamp:** during `warmup_steps`, replica delta is clamped to ±1.
- **Scale-in floor:** the controller remembers recent capacity needs and will not
  recommend below ~80% of the recent peak.
- **High-replica gating & futility tapering:** deltas are capped/suppressed at high
  replica counts and after repeated futile scale-outs.
- `config.validate()` returns human-readable warnings for risky parameter values
  (it does not raise).

## Determinism

For a fixed config and input sequence, all decision fields (`action_score`,
`recommendation`, `replica_delta`, `pressure`, and the plasticity/gain/damping/
coherence breakdowns) are deterministic. The only nondeterministic field is
`identity_deviation` (see [EVIDENCE_AND_LIMITATIONS.md](EVIDENCE_AND_LIMITATIONS.md)).
