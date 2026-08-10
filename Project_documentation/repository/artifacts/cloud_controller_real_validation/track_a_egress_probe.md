# Track-A environment probe — container-registry egress

**This is an environment/pre-condition probe, NOT a validation run.** No maturity-ladder
label (`simulated` / `real-trace-replay` / `live-shadow-self-run` / `third-party`)
applies to it. Rung 3 (`live-shadow-self-run`) **remains NOT done** — see §6.

- **Date:** 2026-06-17
- **Branch:** `claude/eloquent-thompson-wjybsd`
- **Host:** managed remote execution container (Claude Code on the web), `linux/amd64`.
- **Egress note:** this host is **not** the "GitHub-only, all-registries-403" sandbox
  described in `Project_documentation/governance/docs/cloud_scaling_real_validation/STATUS.md`. Egress here is
  **selective** (PyPI installs work; `gcr.io` pulls work; other registries vary), so
  the result was probed directly rather than assumed. This artifact refines — and does
  not edit — the STATUS.md environment note.
- **Method:** real `docker pull` attempts against each registry Track A needs, plus
  HTTP reachability probes of registry `/v2/` roots and tool-download hosts.
  **No cluster was created and nothing was simulated.**

---

## 1. Docker daemon status
- Client: **Docker Engine — Community v29.3.1** (buildx v0.31.1, compose v5.1.1),
  present at `/usr/bin/docker`.
- Daemon: **not running at session start** (`/var/run/docker.sock` absent). Started
  successfully here with `dockerd` → overlayfs / containerd-snapshotter, cgroup v1,
  `API listen on /var/run/docker.sock`, "Daemon has completed initialization."
  Non-fatal warnings: `No cpuset support`; `cgroup v1 deprecated`.
- **Conclusion:** the Docker daemon is usable on this host; it is **not** the blocker.

## 2. Tool availability
| tool | status |
|---|---|
| `docker` | ✅ present (daemon startable) |
| `curl` | ✅ present |
| `kind` / `k3d` / `k3s` | ❌ missing |
| `kubectl` | ❌ missing |
| `helm` | ❌ missing |
| `k6` | ❌ missing |

Tool-download host reachability (for installing the missing tools):

| host | result |
|---|---|
| `dl.k8s.io` (kubectl) | HTTP 200 — reachable |
| `github.com/.../releases` (kind) | HTTP 200 — reachable |
| `objects.githubusercontent.com` | HTTP 404 — reachable |
| `get.helm.sh` (helm install script) | HTTP 403 — blocked (helm would need its GitHub-release tarball) |

## 3. Registry reachability — HTTP `/v2/` probe
A `/v2/` `401` is the normal unauthenticated-auth handshake (registry reachable); a
`403` is a block; controls confirm the policy baseline.

| target | result |
|---|---|
| CONTROL `github.com` | HTTP 200 (reachable) |
| CONTROL `raw.githubusercontent.com` | HTTP 200 (reachable) |
| CONTROL `pypi.org` | HTTP 200 (reachable) |
| `registry-1.docker.io/v2/` | HTTP 401 (reachable) |
| `production.cloudfront.docker.com/` | HTTP 403 |
| `registry.k8s.io/v2/` | HTTP 403 |
| `gcr.io/v2/` | HTTP 401 (reachable) |
| `ghcr.io/v2/` | HTTP 401 (reachable) |
| `quay.io/v2/` | HTTP 403 |

## 4. Registry pull results (the decisive test)
Real `docker pull` of a representative image per registry:

| registry | image pulled | result | Track-A dependency it serves |
|---|---|---|---|
| **gcr.io** | `gcr.io/google-samples/hello-app:1.0` | ✅ **SUCCESS** — manifest + blobs (19.1 MB) | Online Boutique app images |
| **docker.io** (Hub) | `hello-world:latest` | ⚠️ **FAILED — anonymous pull rate limit** ("You have reached your unauthenticated pull rate limit"); reachable, fixable with `docker login` | kind node image (`kindest/node`), Grafana |
| **registry.k8s.io** | `registry.k8s.io/pause:3.9` | ❌ **FAILED — 403 Forbidden** on manifest HEAD (`/v2/pause/manifests/3.9`) | `pause`, **kube-state-metrics** |
| **quay.io** | `quay.io/prometheus/node-exporter:v1.8.2` | ❌ **FAILED — 403 Forbidden** on manifest HEAD | Prometheus, Alertmanager, node-exporter, prometheus-operator |
| **ghcr.io** | `ghcr.io/stefanprodan/podinfo:6.7.0` | ❌ **FAILED — blob 403** (manifest resolved; blob GET from `pkg-containers.githubusercontent.com` → 403) | Chaos Mesh |

*(The single gcr.io test image was removed after the probe; 0 local images remain.)*

## 5. Exact Track-A blocker
**Container-registry egress is partial: `registry.k8s.io`, `quay.io`, and the `ghcr.io`
blob CDN (`pkg-containers.githubusercontent.com`) return HTTP 403.** Those three host the
monitoring and chaos layers Track A depends on:

- **kube-prometheus-stack** pulls Prometheus / Alertmanager / node-exporter from
  **quay.io (403)** and **kube-state-metrics from registry.k8s.io (403)** → the
  Prometheus + kube-state-metrics stack cannot come up.
- **Chaos Mesh** (external-bottleneck / noisy scenarios) is on **ghcr.io**, whose blob
  fetch **403s** → fault injection cannot be deployed.

Only `gcr.io` (apps) and Docker Hub-with-login (kind node) would succeed; the
monitoring + chaos layers — the substance of the run — are blocked.

**Consequence for the §2.8 pre-flight:** the pre-flight confirms the kube-state-metrics
fix by querying `kube_horizontalpodautoscaler_status_current_replicas`. That series is
produced by **kube-state-metrics (registry.k8s.io, 403)**, and Prometheus itself is
**quay.io (403)** — so the pre-flight **cannot even start**: there is no cluster and no
Prometheus to query.

## 6. Why no `live-shadow-self-run` label was produced
`RUNBOOK.md` §5 requires **all four** to apply the label: (1) real Kubernetes cluster,
(2) real Prometheus scraping real targets, (3) real HPA scaling a real Deployment,
(4) real workload metrics. **None** could be created on this host because the
monitoring-stack images are blocked (§5 above). Per the Track-A directive — *"label
`live-shadow-self-run` only if real cluster + real Prometheus + real HPA + real metrics;
otherwise stop and report the exact blocker — do not simulate"* — the run was **stopped**.
**No live numbers were produced, nothing was simulated, and no label was applied.**
Rung 3 of the maturity ladder remains **NOT done**.

## 7. Required host capabilities for a real Track-A run
A host that can complete Track A needs all of:
- **Outbound egress (auth + blob fetch)** to **`registry.k8s.io`**, **`quay.io`**, and
  **`ghcr.io`** (incl. its blob CDN `pkg-containers.githubusercontent.com`), plus
  **`gcr.io`** and **`docker.io`** (`registry-1.docker.io` + `production.cloudfront.docker.com`).
- A **Docker Hub login** (or a pull-through mirror) to clear the anonymous pull rate limit.
- **Docker daemon** (works here) and the tools installed: **kind ≥0.23** (or `k3d`/`k3s`),
  **kubectl**, **helm ≥3.12**, **k6 ≥0.52**.
- Machine size per `RUNBOOK.md` §1: **8 vCPU / 16 GB RAM / 40 GB disk** (4 vCPU / 8 GB
  with the lighter app subset in §2.6).

With those, follow `Project_documentation/repository/deploy/local-shadow/RUNBOOK.md` from §2.1, run the §2.8 pre-flight,
then the capacity-bound / external-bottleneck / noisy scenarios, and capture
`artifacts/cloud_controller_real_validation/track_a_live_shadow.{md,json}`.
