# Track-A runbook — `live-shadow-self-run` on a real cluster

Concise operator checklist for a host **with container-registry egress** (the one
thing the build sandbox lacked: `docker pull` there is 403 on image blobs, so no
cluster could start). This runs the **read-only** controller in shadow next to a
real HPA under real faults and emits a real proof-of-value report. Treat the first
run as a **calibration**, not a savings demo (see §4). Detail/background:
`deploy/local-shadow/README.md`.

---

## 1. Machine requirements
- Linux host, **8 vCPU / 16 GB RAM / 40 GB disk** for full Online Boutique
  (4 vCPU / 8 GB works with the lighter subset in §2.6). Nested-virt/privileged
  Docker OK.
- **Outbound egress to container registries** (`docker.io`, `registry.k8s.io`,
  `gcr.io`, `ghcr.io`, `quay.io`) — non-negotiable; this is what makes Track A
  possible.
- Tools: `docker` (daemon running), `kind` ≥0.23 (or `k3d`/`k3s`), `kubectl`,
  `helm` ≥3.12, `k6` ≥0.52 (has `experimental-prometheus-rw`).
- The repo checked out, Python ≥3.10 with `requests`, and repo root on
  `PYTHONPATH` (the controller is pure-stdlib + `requests`).

## 2. Exact commands

### 2.1 One-shot bring-up (cluster + Prometheus + app + HPA + Chaos Mesh)
```bash
bash deploy/local-shadow/bring_up.sh
```
This is the scripted form of 2.2–2.5; run those individually if you prefer.

### 2.2 Cluster
```bash
kind create cluster --config deploy/local-shadow/kind-cluster.yaml   # 1 cp + 2 workers
```

### 2.3 Prometheus + node-exporter + kube-state-metrics (remote-write enabled for k6)
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts && helm repo update
helm upgrade --install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace \
  --set prometheus.prometheusSpec.enableRemoteWriteReceiver=true --wait
```

### 2.4 Online Boutique (real multi-service app) + a real HPA on the frontend
```bash
kubectl create namespace boutique
kubectl -n boutique apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/microservices-demo/main/release/kubernetes-manifests.yaml
kubectl -n boutique apply -f deploy/local-shadow/frontend-hpa.yaml      # minReplicas 1, maxReplicas 20
kubectl -n boutique rollout status deploy/frontend --timeout=5m
```

### 2.5 Chaos Mesh
```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org && helm repo update
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh -n chaos-mesh --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock --wait
```

### 2.6 (optional) lighter app — keep only the request path
```bash
for d in recommendationservice shippingservice emailservice paymentservice \
         checkoutservice adservice loadgenerator; do
  kubectl -n boutique scale deploy/$d --replicas=0; done
```

### 2.7 Expose endpoints, then run the three calibration scenarios
```bash
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090 &
kubectl -n boutique   port-forward svc/frontend 8080:80 &

# capacity-bound (scaling SHOULD help), external-bottleneck (should NOT), noisy/interference
bash deploy/local-shadow/run_experiment.sh sudden_10x_spike      # capacity-bound load via k6
bash deploy/local-shadow/run_experiment.sh cascading_failure     # NetworkChaos on productcatalog → external bottleneck
bash deploy/local-shadow/run_experiment.sh noisy_spikes          # StressChaos CPU → interference
```
`run_experiment.sh` injects the matching `chaos/*.yaml`, drives the matching
`k6-load.js` profile (k6 remote-writes `http_req_duration`/`http_req_failed` to
Prometheus → the controller's `latency_p99`/`error_rate`), and runs the read-only
shadow for the duration. To run the shadow alone against ambient traffic:
```bash
python scripts/run_live_shadow.py --prometheus-url http://localhost:9090 \
    --namespace boutique --deployment frontend --max-cycles 240 --poll-interval 15
```

### 2.8 Pre-flight: confirm the controller can read real HPA state
The kube-state-metrics fix queries modern names with a legacy fallback. Verify the
replica signals are non-null before trusting a run:
```bash
curl -s 'http://localhost:9090/api/v1/query?query=kube_horizontalpodautoscaler_status_current_replicas{namespace="boutique",horizontalpodautoscaler="frontend"}' | grep -q '"value"' \
  && echo "HPA replicas readable" || echo "FAIL: replica metric empty — check kube-state-metrics version/labels"
```

## 3. Expected artifacts
- `artifacts/cloud_controller_real_validation/track_a_live_shadow.md` and `.json`
  (`LiveEfficiencyReport`): cycles; decisions / agreements / divergences vs HPA;
  controller-vs-HPA verdicts; **futile scale-outs the guard would have blocked**
  (counterfactual); **$/replica savings estimate**; **SLO-regression count = 0 by
  construction** (read-only) + observed breach cycles for context.
- Per-scenario console summary (state mix, blocked count, breach cycles).
- The exact Prometheus/k6/chaos resources remain in-cluster for audit.

## 4. Pass/fail criteria (calibration framing — not a savings demo)
**Wiring pass (must all hold):** Prometheus reachable; §2.8 returns non-null
replicas; `cpu, latency_p99, error_rate, current/desired_replicas` populate each
cycle; the shadow loop completes `--max-cycles` without errors.

**Safety pass (the real bar — mirrors the offline calibration):**
- `SLO-regressions caused by the guard = 0` (guaranteed: read-only, never actuates).
- **capacity-bound scenario:** guard does **not** block a scale-out that real
  metrics show was helping → **harmful-false-positives = 0**, and it does not flag
  a genuinely-helpful scale-out as futile (`wrong-on-help = 0`).
- **external-bottleneck scenario:** when the guard *does* act, real throughput is
  flat / latency unrelieved across the blocked scale-outs (true positives).

**Fail conditions:** replica/latency metrics empty (metric-mapping mismatch — see
README "kube-state-metrics name caveat"); **any** harmful false positive (guard
blocked a scale-out that real throughput/latency shows relieved a real
constraint); any SLO regression attributable to the controller (should be
structurally impossible — if observed, treat as a wiring bug).

## 5. Labeling the result `live-shadow-self-run`
Apply the label **only if all four are true**, else do not use it:
1. real Kubernetes cluster (kind/k3s), 2. real Prometheus scraping real targets,
3. real HPA actually scaling the Deployment, 4. real workload metrics (real app +
k6/real traffic). `scripts/run_live_shadow.py` stamps `live-shadow-self-run` in
the report; keep it **only** under these conditions.
- It remains **our faults on our cluster** — `live-shadow-self-run`, **not**
  `third-party`. Do not imply independent validation.
- Savings remain an **estimate** under injected faults; report them as such.

## 6. What would strengthen vs weaken the current claim
**Strengthen:** real `latency_p99` stays elevated while CPU is low and HPA scales
out, and the guard (or controller-vs-HPA divergence) flags it with real metrics
proving more replicas didn't help — i.e. the external-bottleneck case caught on a
real cluster with **0 harmful FP, 0 SLO regressions**, reproduced across ≥2 runs.
This converts the offline-calibration safety result into an on-cluster one.

**Weaken:** any harmful false positive on real noisy metrics (the live risk
flagged by calibration: the estimator's NOT_HELPING leans on utilization
collapse); the guard never reaching its ≥20-replica regime so it never acts
(value unproven, not unsafe); or metric attribution noise making controller-vs-HPA
verdicts unreliable. None of these would touch the safety claim; they bound the
**value** claim — which only an independent **third-party** run can close.
