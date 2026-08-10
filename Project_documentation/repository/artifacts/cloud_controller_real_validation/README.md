# Cloud-controller real-validation artifacts

Outputs of the Track A / Track B real-validation work. **Read
`docs/cloud_scaling_real_validation/STATUS.md` first** — it defines the labels and
the maturity ladder. Every number here is labelled by how it was produced.

| file | label | what it is |
|---|---|---|
| `track_b_trace_replay.md` / `.json` | `real-trace-replay` | **Real, executed.** The unmodified control core replayed offline over real Azure LLM/LMM inference traces (Azure Public Dataset, CC-BY-4.0). Headline: on 1,000,000 real requests / 7 days, the guard blocked 80 of 2,537 scale-outs (3.2%), saving 0.74% replica-cycles at +0.01pp SLO. |
| `realdyn_calibration.md` / `.json` | `real-dynamics-calibration` | **Real, executed.** Estimator + guard run against a real concurrent service whose tail latency emerges from real queuing (NOT k8s, NOT real HPA). Calibration result: 0 harmful false positives / 0 SLO regressions across 4 scenarios; the guard caught real futility only at severe over-provisioning. Produced by `experiments/cloud_scaling_realdyn/run_calibration.py`. |
| `track_a_live_shadow.STUB_EXAMPLE.md` / `.json` | ⚠️ **stub wiring demo — NOT a cluster** | The *shape* of the live-shadow report, produced by the real-HTTP Prometheus stub in `test_shadow_integration.py`. Numbers are from a synthetic stub, not a cluster. Proves the wiring; carries **no** real-cluster claim. |
| `track_a_live_shadow.md` / `.json` | `live-shadow-self-run` | **Produced when you run it** on a Docker host via `deploy/local-shadow/`. Not committed (no cluster in the build env). |
| `tier_a_selftest.STUB_EXAMPLE.md` / `.json` | ⚠️ **tooling self-test — synthetic fixture** | Output of the pre-registered **Tier-A detector** (`cloud_controller/replay/tier_a.py`) on the committed schema fixture, via `scripts/run_tier_a_replay.py`. Validates the tooling end-to-end; the APCY coverage trip-wire **refuses it as evidence by design**. Carries **no** market claim. Spec: `docs/cloud_scaling_real_validation/TIER_A_DETECTOR_SPEC.md`. |
| `tier_a_partner_replay.md` / `.json` | `real-trace-replay (estimate pending live adjudication)` | **Produced when you run real partner exports** (`scripts/run_tier_a_replay.py --manifest ...`): per-cluster Tier-A candidates, APCY (gated by the coverage floor), and one SRE-adjudication worksheet per candidate. Not committed (no partner data here); every number is gated on SRE adjudication before it counts. |

## Reproduce

```bash
# Track B (real numbers, runs anywhere with GitHub egress + Python)
bash scripts/fetch_real_traces.sh
python scripts/run_trace_replay.py

# Track A (needs Docker host)
bash deploy/local-shadow/bring_up.sh
bash deploy/local-shadow/run_experiment.sh sudden_10x_spike

# Tier-A detector (Track B) — tooling self-test on the committed fixture
python scripts/run_tier_a_replay.py
# Real partner exports (per NDA; not committed):
python scripts/run_tier_a_replay.py --manifest partners.json
```

## Honesty contract

- `simulated` ≠ `real-trace-replay` ≠ `live-shadow-self-run` ≠ `third-party`. We
  never round one into another.
- Track B is **offline** (no live actuation). Track A self-run savings are on
  **our** injected faults. Only `third-party` proves independent value, and it is
  **still pending** (needs a free external design partner).
- The controller is **read-only / shadow** throughout — zero write permissions, by
  construction. The futility guard's "blocks" in a live run are a counterfactual;
  it never actuates.
