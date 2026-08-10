# Track B — Real production-trace replay (offline)

> **Label: `real-trace-replay`.** Every number below is the unmodified cloud-controller control core (controller + EfficiencyEstimator + ScaleOutFutilityGuard + scorer) run **offline** over a **real public trace**. There is **no live actuation** and **no third-party** involvement. The one variable made real vs. the synthetic suite is the **workload distribution**; the demand→metric transfer function is the same model the synthetic suite uses, and the HPA baseline is the standard threshold model — both disclosed.

## Results on real traces

Each trace is run twice through the **unmodified** control core — guard OFF (raw controller) and guard ON — an A/B counterfactual.

| trace | data | cycles | scale-outs | guard-blocked | SLO Δ (breach-cycles on−off) | replica-cycles Δ (on−off) |
|---|---|--:|--:|--:|--:|--:|
| `azure_lmm_multimodal` | executed | 40,320 | 2,537 | 80 (3.2%) | +4 of 40,320 (+0.010pp) | -2,341 (-0.7%) |
| `azure_llm_conv` | executed | 234 | 14 | 0 (0.0%) | +0 of 234 (+0.000pp) | +0 (-0.0%) |
| `azure_llm_code` | executed | 230 | 20 | 0 (0.0%) | +0 of 230 (+0.000pp) | +0 (-0.0%) |

- **guard-blocked** is measured on the single guard-ON run — the real, intended configuration. Every block fired inside the guard's designed envelope (≥20 replicas **and** ≥5 consecutive NOT_HELPING cycles).
- **SLO Δ** is the change in SLO-breach cycles from enabling the guard. Negative or near-zero = the guard did not hurt SLO. On the long multimodal trace it is a few cycles out of tens of thousands (≈0.01pp) — **near-neutral, but not exactly zero**, so we report the exact count rather than claim "zero".
- **replica-cycles Δ** is the cost change. Negative = the guard saved capacity. Because the controller is a feedback loop, the two trajectories diverge over long horizons; treat the A/B cost delta as **indicative**, not a guaranteed bill. (This is exactly why a *live* run — Track A — is the next rung, and a third party the one after.)

### Provenance

- `azure_lmm_multimodal` — Azure LLM/LMM Inference Trace (2023-2025), Microsoft Azure Public Dataset, github.com/Azure/AzurePublicDataset (license: CC-BY-4.0). n_requests=1000000, duration_seconds=604799.7, load_metric=tokens, capacity_percentile=95.0, real_variable=workload distribution (real request arrival process)
- `azure_llm_conv` — Azure LLM/LMM Inference Trace (2023-2025), Microsoft Azure Public Dataset, github.com/Azure/AzurePublicDataset (license: CC-BY-4.0). n_requests=19366, duration_seconds=3501.7, load_metric=tokens, capacity_percentile=95.0, real_variable=workload distribution (real request arrival process)
- `azure_llm_code` — Azure LLM/LMM Inference Trace (2023-2025), Microsoft Azure Public Dataset, github.com/Azure/AzurePublicDataset (license: CC-BY-4.0). n_requests=8819, duration_seconds=3435.9, load_metric=tokens, capacity_percentile=95.0, real_variable=workload distribution (real request arrival process)

## Real-trace-replay vs. synthetic baseline

| | synthetic (19 scenarios) | real-trace-replay (Azure) |
|---|--:|--:|
| workload | adversarial synthetic demand shapes | real Azure arrival/utilisation distribution |
| total scale-outs | 649 | 2,571 (across 3 traces) |
| guard-blocked | 87 (13.4%) | 80 |
| worst SLO impact from guard | 0 catastrophic / 0 severe | +0.010pp (multimodal: +4 breach-cycles of 40,320) |

**Reading it honestly:** the synthetic suite is *deliberately adversarial* — it over-represents the futile-scaling regime to stress the guard, so it blocks a higher fraction (≈13%). On real Azure inference traffic the futile regime is rarer, so the guard is more selective: it stays **dormant** on the short/mild traces (0 blocks, 0 false positives) and blocks a small fraction on the long multimodal trace. There the cost saving is real but small (~0.7% replica-cycles) and the SLO impact is **near-neutral but not exactly zero** (+0.01pp). We report that honestly rather than rounding it to "zero SLO regressions" — that clean claim belongs only to the *simulated* suite.

## What this does and does not prove

- **Does:** the control core behaves safely and selectively on **real workload distributions**, not just hand-built ones — closing the "synthetic workload distribution" gap. Offline, reproducible.
- **Does not:** prove savings under **live actuation** (Track A, on a real cluster) or **independent** value (third-party — still pending). No live scaling happened here; the HPA baseline is a model.