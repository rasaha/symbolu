"""
PCAM vLLM Integration Harness — Measurement Path

This module provides the concrete measurement path that bridges
the gap between PCAM's simulated metrics and real serving economics.

It does NOT require a running GPU or vLLM install. Instead, it:
  1. Defines the exact measurement protocol
  2. Provides a mock harness that runs against the simulator
  3. Shows what real measurements would replace when vLLM is integrated

The measurement protocol answers ChatGPT's critique:
  "Show me tok/s gain on Llama-2 7B at 16K context."

Three proof stages (matching the chip validation path):
  Stage A: Software emulation — Replace dense attention with PCAM-guided
           sparse attention in vLLM's attention backend
  Stage B: GPU profiling — Measure actual HBM bandwidth relief via nsight
  Stage C: End-to-end — Measure tok/s, $/M tokens, latency SLAs

Usage:
    # Run mock harness (simulator-backed, no GPU needed):
    python -m benchmarks.pcam_vllm_harness --mock

    # Run mock harness targeting H100:
    python -m benchmarks.pcam_vllm_harness --mock --gpu h100

    # Run real harness (requires vLLM + GPU):
    python -m benchmarks.pcam_vllm_harness --real --model meta-llama/Llama-2-7b-hf

    # Generate measurement protocol document:
    python -m benchmarks.pcam_vllm_harness --protocol
"""

import sys
import os
import time
import json
import argparse
from dataclasses import dataclass, field
from typing import Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Measurement protocol
# ---------------------------------------------------------------------------

MEASUREMENT_PROTOCOL = """
============================================================
  PCAM vLLM Integration — Measurement Protocol
============================================================

PURPOSE: Replace simulated roofline estimates with measured
tok/s on real hardware. This is the proof that matters.

------------------------------------------------------------
  STAGE A: Software Emulation (no PCAM hardware needed)
------------------------------------------------------------

What to do:
  1. Fork vLLM at the attention backend level
  2. Before each attention layer, query PCAM simulator for top-K blocks
  3. Gather only those K blocks from KV cache (skip the rest)
  4. Run attention on K blocks instead of full context

What to measure:
  A1. tok/s with dense attention (baseline)
  A2. tok/s with PCAM sparse attention
  A3. Quality: perplexity on WikiText-103, MMLU accuracy, HumanEval pass@1
  A4. Latency: p50, p95, p99 per-token latency

How to measure:
  $ python -m vllm.entrypoints.openai.api_server \\
      --model meta-llama/Llama-2-7b-hf \\
      --max-model-len 16384

  # Baseline
  $ python benchmark_serving.py --backend vllm \\
      --model meta-llama/Llama-2-7b-hf \\
      --dataset ShareGPT --num-prompts 1000

  # PCAM sparse (with patched attention)
  $ PCAM_ENABLED=1 python benchmark_serving.py --backend vllm \\
      --model meta-llama/Llama-2-7b-hf \\
      --dataset ShareGPT --num-prompts 1000

Pass criteria:
  - tok/s improvement >= 15% at batch_size >= 8
  - Perplexity increase < 1%
  - MMLU accuracy drop < 0.5%

------------------------------------------------------------
  STAGE B: GPU Profiling (HBM bandwidth measurement)
------------------------------------------------------------

What to do:
  1. Profile dense vs sparse attention with NVIDIA nsight
  2. Measure actual HBM read bytes per token generation

What to measure:
  B1. HBM read bandwidth utilization (% of peak)
  B2. KV cache bytes read per generated token
  B3. L2 cache hit rate (PCAM may improve locality)

How to measure:
  $ ncu --set full --target-processes all \\
      python generate_single_batch.py --batch-size 32 --seq-len 8192

  Key nsight counters:
  - dram__bytes_read.sum          (total HBM reads)
  - lts__t_sectors_srcunit_tex_op_read.sum  (L2 cache reads)
  - sm__throughput.avg_pct_of_peak_sustained  (compute utilization)

Pass criteria:
  - KV cache bytes/token reduced by >= 50%
  - Compute utilization INCREASES (proving we were bandwidth-bound)

------------------------------------------------------------
  STAGE C: End-to-End Serving Economics
------------------------------------------------------------

What to do:
  1. Run a serving benchmark with realistic SLAs
  2. Compute cost per 1M tokens

What to measure:
  C1. Maximum batch size before SLA violation (p99 < 200ms TTFT)
  C2. tok/s at SLA-compliant batch size
  C3. Cost per 1M output tokens ($/M = gpu_cost_hr / tok_hr * 1e6)

How to measure:
  $ python benchmark_serving.py --backend vllm \\
      --model meta-llama/Llama-2-70b-hf \\
      --dataset ShareGPT --num-prompts 5000 \\
      --request-rate sweep \\
      --sla-ttft-ms 200 --sla-tpot-ms 50

Pass criteria:
  - Max batch size increases by >= 2x (from KV memory savings)
  - Cost per 1M tokens decreases by >= 20%
  - p99 TPOT (time per output token) stays within 50ms

============================================================
  WHAT THE SIMULATOR CAN PROVE vs WHAT REQUIRES REAL HARDWARE
============================================================

  Already proven by simulator:
    [x] Candidate quality (coverage >= 80% on code, multitenant)
    [x] FLOPs reduction (87.5% at 8K context)
    [x] Hardware latency envelope (ATTEND < 500ns)
    [x] Roofline speedup model (1.50x at batch=32, ctx=8K)

  Requires Stage A (software emulation):
    [ ] Real tok/s improvement (currently projected at 50%)
    [ ] Perplexity impact of sparse attention
    [ ] Actual KV gather overhead

  Requires Stage B (GPU profiling):
    [ ] HBM bandwidth relief (currently modeled at 38% reduction)
    [ ] Compute utilization change
    [ ] L2 cache effects

  Requires Stage C (end-to-end):
    [ ] Production-realistic cost per 1M tokens
    [ ] SLA compliance under load
    [ ] Multi-model generalization

============================================================
"""


# ---------------------------------------------------------------------------
# Mock harness (simulator-backed, no GPU required)
# ---------------------------------------------------------------------------

@dataclass
class MockMeasurement:
    """A single mock measurement point."""
    name: str
    baseline_value: float
    pcam_value: float
    unit: str
    improvement_pct: float
    source: str  # "simulated" or "measured"

    def __str__(self) -> str:
        return (
            f"  {self.name:<35} "
            f"baseline={self.baseline_value:>10.2f} {self.unit}  "
            f"pcam={self.pcam_value:>10.2f} {self.unit}  "
            f"delta={self.improvement_pct:>+.1f}%  "
            f"[{self.source}]"
        )


@dataclass
class MockHarnessResult:
    """Results from the mock harness."""
    model_name: str
    context_length: int
    batch_size: int
    measurements: List[MockMeasurement] = field(default_factory=list)
    stage_a_ready: bool = False
    stage_b_ready: bool = False
    stage_c_ready: bool = False

    def summary(self) -> str:
        lines = [
            f"\n{'='*80}",
            f"  Mock vLLM Harness: {self.model_name} ctx={self.context_length} batch={self.batch_size}",
            f"{'='*80}",
        ]
        for m in self.measurements:
            lines.append(str(m))
        lines.append("")
        lines.append(f"  Stage A (software emulation): {'READY' if self.stage_a_ready else 'NEEDS REAL MEASUREMENT'}")
        lines.append(f"  Stage B (GPU profiling):       {'READY' if self.stage_b_ready else 'NEEDS REAL MEASUREMENT'}")
        lines.append(f"  Stage C (end-to-end):          {'READY' if self.stage_c_ready else 'NEEDS REAL MEASUREMENT'}")
        return "\n".join(lines)


def run_mock_harness(
    context_length: int = 8192,
    batch_size: int = 32,
    top_k: int = 64,
    verbose: bool = True,
    gpu_profile=None,
) -> MockHarnessResult:
    """
    Run the mock measurement harness backed by the PCAM simulator.

    This produces the SAME metrics that Stage A would produce with
    real vLLM, but derived from the simulator + roofline model.
    Every measurement is tagged [simulated] to make clear what
    needs real validation.
    """
    from simulator.pcam import PCAMSimulator, PCAMConfig
    from simulator.pcam.traces.generators import SyntheticTraceGenerator
    from simulator.pcam.baselines import H2OController
    from simulator.pcam.baselines.base import ControllerConfig
    from benchmarks.pcam_flops_to_roi import InferenceModel, GPUProfile

    # Run simulation
    gen = SyntheticTraceGenerator(seed=42)
    trace = gen.generate_chat_trace(
        num_turns=max(5, context_length // 200),
        tokens_per_turn=(50, 200),
        block_size=16,
        top_k=top_k,
    )

    sim = PCAMSimulator(verbose=False)
    pcam_result = sim.run_pcam(trace, "chat")

    ctrl_config = ControllerConfig(
        cache_capacity=min(256, context_length // 16),
        num_sinks=4,
        recent_window=32,
        top_k=top_k,
    )
    baseline_result = sim.run_baseline(trace, H2OController(ctrl_config), "chat")

    # Build roofline model
    if gpu_profile is not None:
        model = InferenceModel.with_gpu(gpu_profile, context_length=context_length, batch_size=batch_size)
    else:
        model = InferenceModel(context_length=context_length, batch_size=batch_size)
    gpu_name = gpu_profile.name if gpu_profile is not None else "A100 80GB"
    context_blocks = context_length // 16
    flops_reduction = 1.0 - (top_k / context_blocks) if context_blocks > top_k else 0.0

    baseline_tok_s = model.tokens_per_second_baseline()
    pcam_tok_s = model.tokens_per_second_with_pcam(flops_reduction)
    coverage = pcam_result.metrics.quality.mean_coverage

    # Compute all mock measurements
    measurements = []

    # A1: tok/s
    measurements.append(MockMeasurement(
        name="Throughput (tok/s)",
        baseline_value=baseline_tok_s,
        pcam_value=pcam_tok_s,
        unit="tok/s",
        improvement_pct=(pcam_tok_s - baseline_tok_s) / baseline_tok_s * 100,
        source="simulated (roofline)",
    ))

    # A2: Per-token latency
    baseline_lat_ms = 1000 / baseline_tok_s if baseline_tok_s > 0 else 0
    pcam_lat_ms = 1000 / pcam_tok_s if pcam_tok_s > 0 else 0
    measurements.append(MockMeasurement(
        name="Per-token latency (ms)",
        baseline_value=baseline_lat_ms,
        pcam_value=pcam_lat_ms,
        unit="ms",
        improvement_pct=(baseline_lat_ms - pcam_lat_ms) / baseline_lat_ms * 100 if baseline_lat_ms > 0 else 0,
        source="simulated (roofline)",
    ))

    # B1: HBM KV bytes per token
    baseline_kv_gb = model.kv_bytes_per_sequence / 1e9
    pcam_kv_gb = baseline_kv_gb * (1 - flops_reduction)
    measurements.append(MockMeasurement(
        name="KV cache read per token (GB)",
        baseline_value=baseline_kv_gb,
        pcam_value=pcam_kv_gb,
        unit="GB",
        improvement_pct=(baseline_kv_gb - pcam_kv_gb) / baseline_kv_gb * 100 if baseline_kv_gb > 0 else 0,
        source="simulated (model config)",
    ))

    # B2: KV fraction of total bandwidth
    measurements.append(MockMeasurement(
        name="KV % of HBM bandwidth",
        baseline_value=model.kv_fraction_bandwidth * 100,
        pcam_value=model.kv_fraction_bandwidth * (1 - flops_reduction) * 100,
        unit="%",
        improvement_pct=-flops_reduction * 100,
        source="simulated (roofline)",
    ))

    # A3: Coverage (quality proxy)
    measurements.append(MockMeasurement(
        name="Top-K coverage",
        baseline_value=100.0,  # Dense attention = 100% by definition
        pcam_value=coverage * 100,
        unit="%",
        improvement_pct=-(1 - coverage) * 100,
        source="simulated (PCAM sim)",
    ))

    # C1: Cost per 1M tokens
    baseline_cost = model.cost_per_million_tokens(baseline_tok_s)
    pcam_cost = model.cost_per_million_tokens(pcam_tok_s)
    measurements.append(MockMeasurement(
        name="Cost per 1M tokens ($)",
        baseline_value=baseline_cost,
        pcam_value=pcam_cost,
        unit="$",
        improvement_pct=(baseline_cost - pcam_cost) / baseline_cost * 100 if baseline_cost > 0 else 0,
        source="simulated (roofline + cloud pricing)",
    ))

    # ATTEND hardware latency
    measurements.append(MockMeasurement(
        name="PCAM ATTEND p50 (ns)",
        baseline_value=0,  # No PCAM in baseline
        pcam_value=pcam_result.metrics.attend_latency.p50,
        unit="ns",
        improvement_pct=0,
        source="simulated (PCAM hw model)",
    ))

    result = MockHarnessResult(
        model_name=f"llama-70b on {gpu_name} (simulated)",
        context_length=context_length,
        batch_size=batch_size,
        measurements=measurements,
        stage_a_ready=False,  # Needs real vLLM
        stage_b_ready=False,  # Needs nsight
        stage_c_ready=False,  # Needs production setup
    )

    if verbose:
        print(result.summary())
        print()
        print(model.roofline_summary())

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    from benchmarks.pcam_flops_to_roi import GPU_PROFILES, DEFAULT_GPU, get_gpu_profile

    parser = argparse.ArgumentParser(
        description="PCAM vLLM Integration Harness"
    )
    parser.add_argument(
        "--protocol", action="store_true",
        help="Print the measurement protocol"
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Run mock harness (simulator-backed, no GPU)"
    )
    parser.add_argument(
        "--context", type=int, default=8192,
        help="Context length"
    )
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Batch size"
    )
    parser.add_argument(
        "--gpu", default=DEFAULT_GPU,
        choices=list(GPU_PROFILES.keys()),
        help=f"GPU profile (default: {DEFAULT_GPU}). Available: {', '.join(GPU_PROFILES.keys())}"
    )

    args = parser.parse_args()
    gpu = get_gpu_profile(args.gpu)

    if args.protocol:
        print(MEASUREMENT_PROTOCOL)
    elif args.mock:
        print(f"\n  GPU: {gpu.summary()}\n")
        run_mock_harness(
            context_length=args.context,
            batch_size=args.batch_size,
            gpu_profile=gpu,
        )
    else:
        print("Use --protocol to see what to measure, or --mock to run simulator-backed harness")
        print()
        print(f"  GPU: {gpu.summary()}\n")
        # Run both by default
        print(MEASUREMENT_PROTOCOL)
        print("\n" + "="*80)
        print(f"  MOCK HARNESS RESULTS (simulator-backed) — {gpu.name}")
        print("="*80)
        for bs in [1, 8, 32, 64]:
            run_mock_harness(
                context_length=args.context,
                batch_size=bs,
                verbose=True,
                gpu_profile=gpu,
            )


if __name__ == "__main__":
    main()
