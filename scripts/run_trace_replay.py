#!/usr/bin/env python3
"""Track B runner — replay real production traces through the cloud controller and
write the labelled proof artifact.

Uses the FULL traces in data/cloud_traces/ when present (real numbers); otherwise
falls back to the committed fixture slices (clearly tagged as samples). Also runs
the 19 synthetic scenarios for the side-by-side baseline.

    python scripts/run_trace_replay.py            # auto: full traces if fetched, else fixtures
    python scripts/run_trace_replay.py --fixtures # force the small committed slices

Writes:
    Project_documentation/repository/artifacts/cloud_controller_real_validation/track_b_trace_replay.md
    artifacts/cloud_controller_real_validation/track_b_trace_replay.json
"""

import argparse
import json
import os
import sys

# Make repo root importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cloud_controller.replay.adapters import (
    AzureLLMInferenceAdapter,
    AzureVMNoiseAdapter,
)
from cloud_controller.replay.harness import TraceReplayHarness
from cloud_controller.replay import report as report_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FULL = os.path.join(ROOT, "data", "cloud_traces")
FIX = os.path.join(FULL, "fixtures")
OUT = os.path.join(ROOT, "artifacts", "cloud_controller_real_validation")


def _first_vm_noise(base):
    d = os.path.join(base, "azure_vm_noise")
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".csv"):
                return os.path.join(d, f)
    return None


def _pick_traces(force_fixtures, include_vm_noise=False):
    """Return list of (adapter, path, name, data_status_note).

    Headline sources are the Azure LLM inference *arrival* traces — the correct
    real "scaling-demand" signal. The VM-noise dataset measures noisy-neighbor
    *interference*, which is not a valid autoscaling demand driver (mapping it to
    demand drives nonsensical runaway scaling), so it is excluded by default and
    only run with --include-vm-noise for exploration.
    """
    out = []
    llm = AzureLLMInferenceAdapter()
    vmn = AzureVMNoiseAdapter()
    full_llm = os.path.join(FULL, "azure_llm")
    use_full = (not force_fixtures) and os.path.isdir(full_llm)

    if use_full:
        for fn, nm in [("AzureLMMInferenceTrace_multimodal.csv", "azure_lmm_multimodal"),
                       ("AzureLLMInferenceTrace_conv.csv", "azure_llm_conv"),
                       ("AzureLLMInferenceTrace_code.csv", "azure_llm_code")]:
            p = os.path.join(full_llm, fn)
            if os.path.exists(p):
                out.append((llm, p, nm, "FULL"))
        if include_vm_noise:
            vp = _first_vm_noise(FULL)
            if vp:
                out.append((vmn, vp, "azure_vm_noise_EXPLORATORY", "FULL"))
    else:
        out.append((llm, os.path.join(FIX, "azure_llm_conv_sample.csv"), "azure_llm_conv_SAMPLE", "FIXTURE_SAMPLE"))
        out.append((llm, os.path.join(FIX, "azure_llm_code_sample.csv"), "azure_llm_code_SAMPLE", "FIXTURE_SAMPLE"))
        if include_vm_noise:
            out.append((vmn, os.path.join(FIX, "azure_vm_noise_sample.csv"), "azure_vm_noise_SAMPLE_EXPLORATORY", "FIXTURE_SAMPLE"))
    return out


def _synthetic_baseline():
    from cloud_controller.observability.edge_cases import EdgeCaseHarness
    from cloud_controller.observability.scaling_report import ScalingEffectivenessReport
    rep = EdgeCaseHarness().run_all()
    ser = ScalingEffectivenessReport.from_edge_report(rep)
    sev = {}
    for r in rep.results:
        sev[r.severity.value] = sev.get(r.severity.value, 0) + 1
    return {
        "label": "simulated",
        "n_scenarios": len(ser.scenarios),
        "total_scale_outs": ser.total_scale_outs,
        "total_helping": ser.total_helping,
        "total_not_helping": ser.total_not_helping,
        "total_blocked": ser.total_blocked,
        "pct_blocked": round(ser.pct_blocked, 1),
        "severity_counts": sev,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", action="store_true", help="force committed sample slices")
    ap.add_argument("--include-vm-noise", action="store_true",
                    help="also replay the VM-noise interference dataset (exploratory; not a demand driver)")
    ap.add_argument("--base-replicas", type=int, default=5)
    args = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    harness = TraceReplayHarness(base_replicas=args.base_replicas)

    print("Running 19 synthetic scenarios for baseline...")
    synthetic = _synthetic_baseline()
    print(f"  synthetic: {synthetic['total_scale_outs']} scale-outs, "
          f"{synthetic['total_blocked']} blocked, severities {synthetic['severity_counts']}")

    results = []
    for adapter, path, name, status in _pick_traces(args.fixtures, args.include_vm_noise):
        if not os.path.exists(path):
            print(f"  skip {name}: {path} missing")
            continue
        print(f"Replaying {name} ({status}) from {os.path.relpath(path, ROOT)} ...")
        series = adapter.load(path, name=name)
        series.meta["cycle_seconds"] = series.cycle_seconds
        series.meta["data_status"] = status
        res = harness.run(series)
        results.append(res)
        print(f"  cycles={res.n_cycles:,} scale_outs={res.total_scale_outs:,} "
              f"blocked={res.blocked_scale_outs:,} slo {res.slo_breach_off:.3f}->{res.slo_breach_on:.3f} "
              f"safe={res.slo_safe} saved={res.pct_replica_cycles_saved:.1f}%")

    md = report_mod.build_markdown(results, synthetic)
    js = report_mod.build_json(results, synthetic)
    # Fixture-sample runs write to a distinct name so they never clobber the
    # real full-trace artifact.
    stem = "track_b_trace_replay.SAMPLE" if args.fixtures else "track_b_trace_replay"
    md_path = os.path.join(OUT, stem + ".md")
    js_path = os.path.join(OUT, stem + ".json")
    with open(md_path, "w") as f:
        f.write(md)
    with open(js_path, "w") as f:
        json.dump(js, f, indent=2)
    print(f"\nWrote:\n  {md_path}\n  {js_path}")


if __name__ == "__main__":
    main()
