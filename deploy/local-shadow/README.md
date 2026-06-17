# Track A — Live shadow on a real Kubernetes cluster under fault injection

This harness runs the **existing Stage-3 shadow controller** (plus the read-only
`EfficiencyObserver`) against a **real** cluster: real Prometheus scraping real
metrics, a real HPA scaling a real multi-service app, and real faults injected by
Chaos Mesh. It captures a real proof-of-value report: futile scale-outs the guard
would have blocked, a $/replica savings estimate, and the SLO-regression count.

> **Status / honesty label.** Everything in this directory is **runnable on a
> Docker host** and produces numbers labelled **`live-shadow-self-run`**. It was
> **NOT executed in the build environment**: the Docker daemon can be started
> there, but the network policy is GitHub-only, so `docker pull` gets `403
> Forbidden` on image blobs (`production.cloudfront.docker.com`) — kind/k3s cannot
> pull a node image and the apps cannot pull from gcr.io, so no cluster can come
> up. This repo therefore ships the *harness*, not live numbers — the
> `artifacts/.../track_a_live_shadow.*` files are produced when you run it. The
> control-core↔Prometheus↔shadow↔guard **wiring is proven here** by
> `tests/cloud_controller/test_shadow_integration.py`, which runs the whole chain
> against a real HTTP Prometheus stub. `live-shadow-self-run` is still **our**
> injected faults on **our** cluster — it is *not* independent third-party
> telemetry (the next, still-pending rung).

The controller is **read-only by construction**: zero write permissions, it never
actuates. HPA does all real scaling; the guard's blocks are a counterfactual.

---

## Prerequisites

- Docker, [`kind`](https://kind.sigs.k8s.io/) (or k3s/k3d), `kubectl`, `helm`.
- [`k6`](https://k6.io/) for load (optional but recommended — it remote-writes RED
  metrics to Prometheus).
- The controller's Python deps: `pip install requests` (and the repo on
  `PYTHONPATH`).
- ~6–8 GB free RAM for the full Online Boutique; see **Lighter app** below.

## One-shot bring-up

```bash
bash deploy/local-shadow/bring_up.sh          # cluster + Prometheus + app + Chaos Mesh + HPA
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090 &
kubectl -n boutique   port-forward svc/frontend 8080:80 &
bash deploy/local-shadow/run_experiment.sh sudden_10x_spike
```

The report lands in `artifacts/cloud_controller_real_validation/track_a_live_shadow.{md,json}`.

## The app

[Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) — 11
microservices with genuine gRPC dependencies (frontend → productcatalog → cart →
currency → …). It is the reference real multi-service app named in the task.

**Lighter app.** On a small machine, scale non-essential services to 0 and keep
the request path (`frontend, productcatalogservice, cartservice, redis-cart,
currencyservice`):

```bash
for d in recommendationservice shippingservice emailservice paymentservice \
         checkoutservice adservice loadgenerator; do
  kubectl -n boutique scale deploy/$d --replicas=0
done
```

## Metric mapping (what Prometheus must expose)

The controller's default queries (`signals/prometheus.py`) expect:

| controller metric | source in this stack | note |
|---|---|---|
| `cpu`, `memory` | node-exporter (kube-prometheus-stack) | works out of the box |
| `latency_p99`, `error_rate` | **k6 remote-write** (`http_req_duration`, `http_req_failed`) | needs the k6 RW output; or add Istio/Envoy RED metrics |
| `queue_depth` | n/a for Boutique | the controller tolerates a missing metric (it warns and uses the rest) |
| `current_replicas`, `desired_replicas`, `pod_restarts` | kube-state-metrics | **metric-name caveat below** |

**kube-state-metrics name caveat.** The code queries the legacy
`kube_hpa_status_current_replicas` / `kube_hpa_status_desired_replicas`. Recent
kube-state-metrics renamed these to
`kube_horizontalpodautoscaler_status_{current,desired}_replicas`. If your replica
queries return nothing, pass a custom query set (override `K8S_QUERIES` /
`PrometheusConfig`) or add a Prometheus recording rule aliasing the new names to
the old. This is the one place the harness may need a one-line adjustment to your
cluster's exporter version.

## Scenario → real fault mapping (the 19 synthetic scenarios)

| # | synthetic scenario | how to make it real here |
|---|---|---|
| 2 | noisy_spikes | `chaos/02_noisy_spikes_cpu_stress.yaml` (StressChaos CPU) |
| 3 | conflicting_signals | `chaos/03_07_upstream_latency.yaml` (NetworkChaos on productcatalog) |
| 6 | sudden_10x_spike | `run_experiment.sh sudden_10x_spike` (k6 ramping-arrival-rate) |
| 7 | cascading_failure | `chaos/03_07_upstream_latency.yaml` + raise delay/abort |
| 8 | spot_interruption | `chaos/08_spot_interruption_podkill.yaml` (PodChaos pod-kill, wrap in a Schedule) |
| 9 | budget_cap | set `frontend-hpa.yaml` `maxReplicas: 8` |
| 10 | coherence_oscillation | `run_experiment.sh coherence_oscillation` (oscillating k6 rate) |
| 14 | gradual_drift | `run_experiment.sh gradual_drift` (ultra-slow k6 ramp) |
| 16 | feedback_delay_loop | `chaos/16_feedback_delay_netem.yaml` + long `readinessProbe.initialDelaySeconds` |
| 17 | partial_recovery | `run_experiment.sh partial_recovery` (spike→dip→spike k6) |
| 18 | cold_start_amplification | `run_experiment.sh cold_start_amplification` (k6 hot from t0) |
| 19 | policy_oscillation | CronJob flipping `frontend-hpa.yaml` `maxReplicas` 4↔15 |
| 1,4,5,13,15 | delayed/slow/stuck/missing metrics | Prometheus `scrape_interval` ↑ / relabel-drop the cpu series / pause an exporter (see below) |
| 11,12 | plasticity_stuck_low, identity_drift | **controller config only** — run `run_live_shadow.py` with a tuned `InfraControllerConfig`; no cluster fault needed (identical to the simulation) |

Signal-path faults (#1,4,5,13,15) are injected at the Prometheus layer, e.g. drop
the cpu series with a `metric_relabel_configs` `drop`, or `kubectl -n boutique
delete pod -l app=node-exporter` style pauses — see the comments in each chaos
file. Controller-internal scenarios (#11,12) carry over unchanged from the
synthetic suite because they are properties of the controller, not the cluster.

## What you get

`run_live_shadow.py` writes `track_a_live_shadow.md` / `.json`:

- **Decision quality vs HPA** — decisions, agreements, divergences, controller-vs-HPA verdicts.
- **Futility guard (counterfactual)** — scale-outs observed and **futile scale-outs the guard would have blocked** (never actuated).
- **$/replica savings estimate** — from the shadow divergence cost model (@ $0.03/replica·min by default).
- **SLO-regression count** — **0 caused by the guard, by construction** (it is read-only), plus observed environment breach cycles for context.

## What it proves (and doesn't)

- **Proves:** the controller runs unmodified against real Prometheus/HPA on a real
  app under real faults, read-only, and the guard's selectivity + SLO-safety hold
  outside a simulator. Reproducible.
- **Does not prove:** independent value. These are **our** faults on **our**
  cluster (`live-shadow-self-run`). Independent third-party telemetry is the next
  rung and is still pending — see `docs/cloud_scaling_real_validation/STATUS.md`.
