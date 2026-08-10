# Phase 0 — Inventory & Build Plan: Neural Cloud Scaling Controller "real validation"

**Goal of the initiative:** move the controller's maturity claim from
*"validated in simulation (19 synthetic scenarios)"* to
*"validated in simulation + replayed against real production traces + run live in
shadow mode on a real Kubernetes cluster under fault injection"* — **without a
paying customer**, and **without ever fabricating a number**.

This document is the required Phase-0 deliverable: a precise inventory of the
existing module, the exact seams the new harnesses must plug into, an honest
verdict on what is genuinely runnable in this environment, and the build plan.

---

## 1. Where the code actually lives (canonical vs. duplicate)

There are **three on-disk copies** of the package:

| Path | Role |
|---|---|
| `cloud_controller/` (top-level) | **CANONICAL.** `cloud_controller/__init__.py` imports `from cloud_controller.config import …`. This is the code that actually runs. |
| `cloud_controller/cloud_controller/` (nested) | Stale duplicate. Ignore. |
| `symbolu/cloud_controller/` | Duplicate reached only through a compatibility shim. |

`symbolu/__init__.py` installs a meta-path finder (`_SymboluFinder`) whose
`_ROUTING` maps the submodule `cloud_controller` to `""` (top-level). So
`from symbolu.cloud_controller.controller import Controller` **resolves to the
top-level `cloud_controller/` package**, not to `symbolu/cloud_controller/`.

> All tests import via `symbolu.cloud_controller.*`, which the shim redirects to
> the top-level package. **New code targets the top-level `cloud_controller/`
> package.** I verified `signals/prometheus.py` and
> `observability/efficiency_estimator.py` are byte-identical across the copies;
> `shadow/runner.py`, `shadow/reporter.py`, `controller.py`,
> `observability/scaling_report.py` differ only cosmetically and expose the same
> public API documented below.

### 1a. Pre-existing test-collection bug (must fix to verify "tests green")

`tests/cloud_controller/__init__.py` (empty, 0 bytes) makes pytest name that
test package **`cloud_controller`**, which **shadows the real top-level
`cloud_controller` package** in `sys.modules`. The shim's
`importlib.import_module("cloud_controller.config")` then resolves against the
*test* package and dies with `ModuleNotFoundError: No module named
'cloud_controller.config'`. Every `tests/cloud_controller/*` module fails to
collect.

- **Proven fix:** removing that empty `__init__.py` → **702 passed, 4 skipped**
  in 63s. It is safe: the only duplicate basename (`test_signals.py`, also under
  `tests/unit/presentation/`) is namespaced there by its own `__init__.py`
  chain, so no import-mismatch results.
- This is a **pre-existing** breakage, not introduced by this work. We remove the
  empty file as the first implementation step and record the canonical command:
  `python -m pytest tests/cloud_controller -q`.

---

## 2. How shadow mode ingests metrics (the integration seam)

Data flow (Stage 2 + Stage 3), all read-only:

```
Prometheus HTTP API
  └─ PrometheusClient.query_metrics()      → 5 app/infra metrics  (DEFAULT_QUERIES)
  └─ PrometheusClient.query_k8s_state()    → 3 k8s state values    (K8S_QUERIES)
       │
       ▼
  SignalNormalizer.normalize_detailed()    → metrics ∈ roughly [0,1]
       │
       ▼
  Controller.step(metrics, current_replicas, deploy_active, phase,
                  recent_pod_restarts)     → ActionResult(replica_delta, …)
       │
       ├─ HPAWatcher.poll()  → HPASnapshot(current_replicas, desired_replicas)
       │       (desired≠current ⇒ HPA is scaling; delta = desired−current)
       ▼
  DivergenceTracker.compare(action, hpa, metrics)  → DivergenceRecord
  DivergenceTracker.evaluate_pending(current_metrics)  (verdict after lookback)
       │
       ▼
  ShadowReporter.generate(records) → ShadowReport   ← the proof-of-value report
```

Driven by `SignalPipeline.poll_once()` → `ShadowRunner.step()` on a 15s loop.
`ShadowRunner` is purely observational (zero write permissions by construction).

### 2a. What the Prometheus adapter expects (`signals/prometheus.py`)

`PrometheusClient` speaks the plain Prometheus HTTP API
(`/api/v1/query`, `/api/v1/query_range`, `/-/healthy`). The pipeline calls four
methods: `query_metrics()`, `query_k8s_state()`, `range_query()` (bootstrap) and
`instant_query()`. **Anything that quacks like a `PrometheusClient` (those four
methods + `health_check`/`close`) can drive the entire existing pipeline
unchanged** — this is the seam Track B replays into.

**`DEFAULT_QUERIES` — the 5 MVP metrics** (name → PromQL):

| key | PromQL (abridged) | meaning |
|---|---|---|
| `cpu` | `avg(rate(node_cpu_seconds_total{mode!="idle"}[2m]))` | node CPU util |
| `memory` | `1 - avg(MemAvailable/MemTotal)` | memory pressure |
| `latency_p99` | `histogram_quantile(0.99, …http_request_duration_seconds_bucket…)` | p99 latency (s) |
| `error_rate` | `sum(rate(http_requests_total{code=~"5.."}[2m])) / clamp_min(sum(rate(http_requests_total[2m])),0.001)` | 5xx fraction |
| `queue_depth` | `sum(queue_messages_ready)` | queued messages |

**`K8S_QUERIES` — 3 state values:** `pod_restarts`
(`rate(kube_pod_container_status_restarts_total[10m])`), `current_replicas`
(`kube_hpa_status_current_replicas`), `desired_replicas`
(`kube_hpa_status_desired_replicas`). Namespace/deployment label filters are
injected and validated against `^[a-zA-Z0-9._/-]+$`.

### 2b. The canonical metric schema (what every shim must emit)

All adapters (real cluster, trace replay) ultimately produce **one dict per
cycle** with these float keys, normalized to ≈[0,1]:

```
{ "cpu", "memory", "latency_p99", "error_rate", "queue_depth" }
```

plus k8s state `current_replicas`, `desired_replicas`, `pod_restarts`. The
synthetic harness produces them from a scalar `demand ∈ [0,1]` via
`benchmark._demand_to_metrics(d)`:

```
cpu = d ; memory = 0.7d+0.1 ; latency_p99 = min(1, 0.8d+0.05)
error_rate = max(0, 2(d−0.7)) ; queue_depth = 0.9d
```

This is the exact contract the trace-replay adapters reproduce (mapping a real
arrival-rate / utilization series → `demand` → metrics), so the **same**
controller, estimator, guard, divergence tracker and reporter run on real data
with **zero changes to the control core**.

---

## 3. The proof-of-value report schema (exact)

Two complementary reports exist. The "real proof-of-value report" combines both.

### 3a. `ShadowReport` (`shadow/reporter.py`) — divergence + $/replica

Fields: `start_time, end_time, period_label`; `total_decisions,
total_agreements, total_divergences`; verdict counts `controller_correct,
hpa_correct, both_reasonable, inconclusive, pending`; divergence-type counts
`hpa_scales_controller_holds, controller_scales_hpa_holds, opposite_direction,
magnitude_differs`; cost `total_cost_saved, total_pods_saved_minutes`. Derived:
`agreement_rate, controller_advantage, net_improvement`. `$` uses
`DivergenceConfig.cost_per_pod_minute` (default **$0.03/pod·min**). Verdicts are
assigned after a **300s lookback** and are explicitly *correlation, not
causation* (documented limitation in the source).

### 3b. `ScalingEffectivenessReport` (`observability/scaling_report.py`) — "did scaling help, or did we just spend money?"

Built `from_edge_report(...)`. Per-scenario `ScenarioReport`:
`total_scale_outs / helping / neutral / not_helping / blocked_scale_outs`,
`futility` (avg/max NOT_HELPING streak, %time-futile), `causality`
(replica↔latency / replica↔CPU Pearson corr, external-bottleneck %, waste %),
`cost` (`total_excess_replica_cycles, cost_due_to_non_causal_scaling,
cost_prevented_by_guard, residual_cost_after_guard`). Exports `format_report()`,
`to_dict()`/`to_json()`, `to_csv()`. **`blocked_scale_outs` is the headline
"futile scale-outs the guard would have blocked" number.**

### 3c. The gap that blocks a *real* PoV report today

The **`EfficiencyEstimator` + `ScaleOutFutilityGuard`** (which produce the
"blocked futile scale-outs" number) are wired **only inside the offline
`EdgeCaseHarness`** (`observability/edge_cases.py:run_scenario`). They are **not**
present in the live `ShadowRunner` loop. So a real-cluster shadow run currently
yields a `ShadowReport` (divergences + $/replica) but **not** the guard/futility
numbers.

> **Build item:** add a read-only `EfficiencyObserver` (Estimator + Guard,
> `filter_delta` computed but never actuated) into the live shadow cycle so the
> real report includes futile-scale-outs-the-guard-would-have-blocked. Zero
> actuation — it only *records* what the guard would have done.

---

## 4. The 19 synthetic scenarios → real fault-injection mapping (1:1)

Source: `observability/edge_cases.py:build_edge_scenarios()`. Each scenario =
`demand_fn` (load shape) + perturbations / actuation-delay / eviction / cap /
controller-config. The harness loop turns `demand` into metrics, perturbs them,
steps the controller, then runs estimator+guard. Real-world equivalents:

| # | scenario | class | sim mechanism | real chaos / load experiment | tool |
|---|---|---|---|---|---|
| 1 | delayed_metrics | signal | `MetricDelay(4)` | inflate Prometheus `scrape_interval` / delay metric pipeline on the scrape path | config / Chaos Mesh on prom pod |
| 2 | noisy_spikes | signal | `NoisySpikes(p=.15)` | CPU bursts on random pods | Chaos Mesh **StressChaos** (cpu) |
| 3 | conflicting_signals | signal | cpu low, lat/err high | inject latency on an upstream dep (cpu stays low) | Chaos Mesh **NetworkChaos** delay |
| 4 | slow_provisioning | actuation | `ActuationDelay(5)` | slow node/pod bring-up (init-container sleep, slow image) | manifest / Karpenter |
| 5 | pod_scheduling_delay | actuation | `ActuationDelay(3)` | resource pressure ⇒ pods stay Pending | ResourceQuota / Chaos Mesh **PodChaos** |
| 6 | sudden_10x_spike | shock | 10× demand | step arrival-rate ×10 | **k6** ramping-arrival-rate |
| 7 | cascading_failure | shock | cpu fine, lat↑ err↑ | latency+abort on a downstream service ⇒ cascade | Chaos Mesh **NetworkChaos** + HTTPChaos |
| 8 | spot_interruption | external | `SpotEviction(p=.05)` | kill random replicas mid-load (spot proxy) | Chaos Mesh **PodChaos** pod-kill |
| 9 | budget_cap | external | `BudgetCap(8)` | HPA `maxReplicas=8` / ResourceQuota | manifest |
| 10 | coherence_oscillation | internal | oscillating demand+conflict | oscillating arrival rate near threshold | **k6** |
| 11 | plasticity_stuck_low | internal | cfg `k_r=8,b_p=-3` | controller-config variant (no cluster fault) | config-injection |
| 12 | identity_drift | internal | cfg `alpha_base=.2` | controller-config variant | config-injection |
| 13 | hidden_demand | signal | `MissingSignal(cpu)` | drop the cpu series (stop node-exporter / relabel-drop) | Prometheus relabel / Chaos Mesh |
| 14 | gradual_drift | signal | ultra-slow ramp | ultra-slow arrival ramp | **k6** |
| 15 | metric_corruption | signal | `StuckMetric(cpu=.3)` | freeze cpu series (pause cAdvisor/exporter) | Chaos Mesh PodChaos (pause) |
| 16 | feedback_delay_loop | actuation | `FeedbackAmplifier(8)`+backpressure | actuation/readiness lag + backpressure | NetworkChaos + slow readiness |
| 17 | partial_recovery | shock | spike→dip→spike | spike→dip→spike arrival profile | **k6** |
| 18 | cold_start_amplification | internal | high load from t0 | full load before controller warmup | **k6** start-hot |
| 19 | policy_oscillation | external | `AlternatingBudgetCap(4↔15)` | flip HPA `maxReplicas` 4↔15 on a timer | CronJob / script |

**Feasibility buckets:** load-shape (6,10,14,17,18) → k6 profiles; true infra
chaos (2,3,5,7,8,13,15,16) → Chaos Mesh; config/policy (1,4,9,11,12,19) →
manifests/config. **11 & 12 are controller-internal** and need no cluster fault
(config variants) — they are reproduced identically in both Track A and Track B.

---

## 5. Environment verdict (decisive — and honest)

Probed this sandbox directly:

| capability | result | consequence |
|---|---|---|
| Docker daemon | Initially down; **can be started** (dockerd 29.3.1), but `docker pull` then hits **403 Forbidden on image blobs** (`production.cloudfront.docker.com`) — the GitHub-only egress policy blocks container registries. No kind/k3s/kubectl/helm/k6/Locust either. | **A live cluster cannot run here** (no node/app images can be pulled). Track A is delivered as a fully reproducible harness; its live numbers are **PENDING** execution on a host with normal registry access. We will **not** fabricate them. |
| PyPI | **reachable** (installed pytest 9.1, numpy 2.4) | existing 702 tests + new harness tests run here |
| Egress | **GitHub-only**: `github.com` + `raw.githubusercontent.com` = 200; Azure blob, GCS, TU-Delft, HuggingFace, `api.github.com` = 403 | Real traces must come from files **committed in-git** on GitHub. |
| Alibaba / Google traces | **blocked** (live on Alibaba blob / GCS) | adapters built + unit-tested on fixtures, but **not executed here**; labeled PENDING-DATA. |
| Azure Public Dataset | **fetchable** — `git clone` works; repo commits **782 real CSVs in-git**, incl. `AzureLLMInferenceTrace_{code,conv}.csv` (real LLM inference arrival traces: `TIMESTAMP,ContextTokens,GeneratedTokens`) and `vm-noise-data/*.csv` (real noisy-neighbor throughput series). `gzip`/`xz`/`tar` available (no `unrar`/`7z`, so the `.rar` Functions trace is skipped). | **Track B is genuinely runnable here on REAL Azure traces.** |

**Bottom line:** Track B (offline replay on real Azure traces) executes here and
yields *real numbers*. Track A executes on a Docker/k8s host; here we deliver the
runnable harness + a stub-Prometheus integration test that proves the wiring,
and mark the live run PENDING.

---

## 6. Build plan

### Track B — offline replay of real production traces (runnable here)
New package `cloud_controller/replay/`:
- `replay_source.py` — `ReplayPrometheusClient` duck-typing `PrometheusClient`
  (`query_metrics`, `query_k8s_state`, `range_query`, `instant_query`,
  `health_check`, `close`) serving a loaded trace at a cursor. Drives the
  **existing** `SignalPipeline`/`ShadowRunner` unchanged.
- `adapters/` — schema → canonical-metrics converters:
  - `azure_llm.py` (executed): arrival timestamps → per-bucket arrival rate →
    `demand` → metrics. Bursty ⇒ noisy-spikes / sudden-spike families.
  - `azure_vm_noise.py` (executed): throughput series → normalized cpu/util.
  - `alibaba_microservices.py`, `google_borg.py`, `azure_functions.py`
    (schema + tiny committed fixtures; **not executed** — PENDING-DATA).
- `efficiency_observer.py` — read-only Estimator+Guard wrapper (shared with
  Track A) to compute blocked-futile-scale-outs without actuation.
- `harness.py` — runs a trace through ShadowRunner + EfficiencyObserver; emits a
  Track-B summary (blocked %, SLO-safety, divergence/cost) labeled
  `real-trace-replay`, plus a synthetic-baseline comparison.
- `scripts/fetch_real_traces.sh` — clones Azure repo, extracts CSVs into
  `data/cloud_traces/` (gitignored; a small slice committed as a test fixture).
- Tests: `tests/cloud_controller/test_replay.py` (adapter parsing on fixtures +
  replay smoke + estimator/guard wiring).

### Track A — live shadow on a real cluster (harness here, run PENDING)
New `deploy/local-shadow/`:
- `kind-cluster.yaml`, install notes for kube-prometheus-stack, the demo app
  (lightest real microservices option), k6 load, Chaos Mesh.
- `chaos/` — one experiment per feasible scenario from §4.
- `run_shadow_live.sh` — bring-up → deploy → load → point ShadowRunner (+
  EfficiencyObserver) at real Prometheus → chaos → write report to `artifacts/`.
- `cloud_controller/shadow/efficiency_observer.py` — the live read-only guard
  observer (same component as Track B).
- **Runs here:** `tests/cloud_controller/test_shadow_integration.py` — a stub
  HTTP Prometheus serving the exact PromQL, proving the ShadowRunner↔Prometheus
  wiring end-to-end (labeled `integration-test (stub Prometheus, not a
  cluster)`). The **live** report is PENDING and never fabricated.

### Phase 3 — artifacts + honest pitchbook
- `artifacts/cloud_controller_real_validation/`: Track-B report (md + raw
  JSON/CSV, REAL); Track-A live-report template + integration-test output (live
  numbers PENDING).
- Update `docs/UGENCE_PITCHBOOK.md` + `docs/CLOUD_SCALING_CONTROLLER_VC_BRIEF.md`:
  replace the bare "19 scenarios" claim with the explicit **maturity ladder**,
  every number labeled `simulated / real-trace-replay / live-shadow-self-run /
  third-party`.
- `docs/cloud_scaling_real_validation/STATUS.md`: what is now real, what is still
  synthetic, and the exact remaining step (a free third-party design partner).

### Labeling discipline (non-negotiable)
Every number carries one of: **simulated** (19 scenarios) · **real-trace-replay**
(offline, no live actuation) · **live-shadow-self-run** (real cluster, *our*
injected faults) · **third-party** (independent — still PENDING). Track A savings
are on injected faults; Track B has no live actuation; only a third party proves
independent value. The controller stays **read-only / shadow** throughout.

---

## 7. Maturity ladder (target end-state)

1. **Simulation — 19 synthetic scenarios** … ✅ done (pre-existing).
2. **Real production-trace replay (offline)** … Track B — REAL here on Azure
   traces; Alibaba/Google adapters ready, data PENDING.
3. **Live shadow on a real cluster under fault injection (self-run)** … Track A —
   harness ready; execution PENDING a Docker/k8s host.
4. **Independent third-party telemetry** … ❌ STILL PENDING — needs an
   external/free design partner. No amount of self-run work reaches this rung.
