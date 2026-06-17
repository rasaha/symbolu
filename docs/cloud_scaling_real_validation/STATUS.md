# STATUS — Neural Cloud Scaling Controller: what is real, what is still synthetic

_Last updated: 2026-06-17. This document is the single source of truth for the
controller's validation maturity. Every claim is labelled by **how the number was
produced**; the four labels are never conflated._

## The four labels

| label | meaning |
|---|---|
| `simulated` | the 19 synthetic adversarial scenarios — modelled metrics pipeline, modelled HPA, modelled provisioning |
| `real-trace-replay` | the *unmodified* control core replayed **offline** over a **real public trace**; no live actuation |
| `live-shadow-self-run` | the controller run **read-only on a real cluster** under **our** injected faults; real Prometheus / HPA / app |
| `third-party` | a real workload **we do not control**, measured by a party with no stake in the result |

## The ladder, and exactly where we stand

| Rung | Label | Status | Evidence |
|---|---|---|---|
| 1. Simulation (19 scenarios) | `simulated` | ✅ **Done** | 0 catastrophic/severe/SLO regressions; guard blocked 87/649 scale-outs (13.4%). `cloud_controller/observability/edge_cases.py` |
| 2. Real production-trace replay (offline) | `real-trace-replay` | ✅ **Done (self-run)** | Azure LLM/LMM inference traces; multimodal 1M requests/7 days: 80/2,537 blocked, +0.01pp SLO, 0.74% replica-cycles saved. `artifacts/cloud_controller_real_validation/track_b_trace_replay.md` |
| 3. Live shadow on a real cluster under fault injection (self-run) | `live-shadow-self-run` | 🟡 **Harness built; wiring proven; execution pending a Docker host** | `deploy/local-shadow/` + `tests/cloud_controller/test_shadow_integration.py` (real-HTTP stub) |
| 4. Independent third-party telemetry | `third-party` | ❌ **PENDING** | none — requires an external design partner |

## What is now real (was synthetic before this work)

- **The workload distribution.** Rung 2 feeds the controller a **real** request
  arrival process (1,000,000 real Azure inference requests over 7 days), not a
  hand-built `demand_fn`. This directly closes the "synthetic workload
  distribution" gap for the guard's behaviour.
- **The metrics transport.** Rung 3's wiring test drives the controller over the
  **real Prometheus HTTP API** (`/api/v1/query`), not an in-process mock — proving
  the Stage-2/3 ingestion path works against a real server.
- **The deployment path.** Rung 3 ships a **reproducible real cluster** (kind +
  kube-prometheus-stack + Online Boutique + real HPA + Chaos Mesh) with a 1:1
  mapping from the 19 synthetic scenarios to real faults.

## What is still synthetic / modelled (be honest about it)

- **The demand→metric transfer function** in rung 2 is still the model the
  synthetic suite uses (latency bound by demand, not replica count). Only the
  *workload distribution* feeding it is real. So rung 2 closes the *distribution*
  gap, not the *system-dynamics* gap.
- **The HPA baseline** in rung 2 is the standard threshold model, not real HPA
  telemetry.
- **Rung 3 has not been executed** in this environment. We confirmed precisely
  why: the Docker daemon *can* be started here, but **container-registry blob
  egress is blocked** — `docker pull` gets `403 Forbidden` from
  `production.cloudfront.docker.com` (the network policy is GitHub-only), so kind/
  k3s cannot pull a node image and the apps cannot pull from gcr.io. A real
  cluster is therefore impossible in this sandbox. The harness + wiring are proven;
  the live numbers are produced when someone runs it on a host with normal
  registry access. We ship no fabricated live numbers.
- **Alibaba & Google traces** were not replayed — their data lives behind
  egress-blocked hosts here. The adapters exist and are fixture-tested
  (`PENDING_DATA`), but produced no reported number.
- **Savings are not independently verified.** Rung-2 cost deltas are an offline
  A/B (subject to feedback-trajectory divergence); rung-3 savings would be on
  *our* injected faults. Neither is `third-party`.

## The exact remaining step to reach the next notch

**Rung 4 needs one thing: a free third-party design partner.** Concretely:

1. Find a team that will run **shadow mode** (read-only, zero write permissions,
   zero production risk) on **their** real cluster for ~2 weeks — using the
   existing Stage-3/4 deployment (`deploy/gke/` or `deploy/local-shadow/` adapted
   to their stack) and `scripts/run_live_shadow.py` pointed at *their* Prometheus.
2. Capture the proof-of-value report on **their** workload, which **we do not
   control or curate**.
3. That single artifact — a real savings/SLO report on an outside workload — is
   the only thing that converts `live-shadow-self-run` into `third-party`.

No additional engineering is required to reach rung 4; the read-only shadow path,
the report, and the harness already exist. The missing ingredient is an external
workload and a disinterested observer — i.e., a design partner, not more code.

## Reproduce

```bash
# Rung 2 — real-trace replay (runs anywhere with Python + network to GitHub)
bash scripts/fetch_real_traces.sh
python scripts/run_trace_replay.py        # writes artifacts/cloud_controller_real_validation/track_b_*

# Rung 3 — live shadow (needs a Docker host)
bash deploy/local-shadow/bring_up.sh
bash deploy/local-shadow/run_experiment.sh sudden_10x_spike

# Wiring proof + all harness tests (runs anywhere)
python -m pytest tests/cloud_controller -q
```
