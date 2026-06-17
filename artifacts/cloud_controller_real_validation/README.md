# Cloud-controller real-validation artifacts

Outputs of the Track A / Track B real-validation work. **Read
`docs/cloud_scaling_real_validation/STATUS.md` first** — it defines the labels and
the maturity ladder. Every number here is labelled by how it was produced.

| file | label | what it is |
|---|---|---|
| `track_b_trace_replay.md` / `.json` | `real-trace-replay` | **Real, executed.** The unmodified control core replayed offline over real Azure LLM/LMM inference traces (Azure Public Dataset, CC-BY-4.0). Headline: on 1,000,000 real requests / 7 days, the guard blocked 80 of 2,537 scale-outs (3.2%), saving 0.74% replica-cycles at +0.01pp SLO. |
| `track_a_live_shadow.STUB_EXAMPLE.md` / `.json` | ⚠️ **stub wiring demo — NOT a cluster** | The *shape* of the live-shadow report, produced by the real-HTTP Prometheus stub in `test_shadow_integration.py`. Numbers are from a synthetic stub, not a cluster. Proves the wiring; carries **no** real-cluster claim. |
| `track_a_live_shadow.md` / `.json` | `live-shadow-self-run` | **Produced when you run it** on a Docker host via `deploy/local-shadow/`. Not committed (no cluster in the build env). |

## Reproduce

```bash
# Track B (real numbers, runs anywhere with GitHub egress + Python)
bash scripts/fetch_real_traces.sh
python scripts/run_trace_replay.py

# Track A (needs Docker host)
bash deploy/local-shadow/bring_up.sh
bash deploy/local-shadow/run_experiment.sh sudden_10x_spike
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
