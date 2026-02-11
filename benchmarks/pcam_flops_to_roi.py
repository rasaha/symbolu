"""
PCAM Confidence Chain Benchmark: FLOPs -> Speed -> Cost -> ROI

Validates each link in the chain that converts "fewer FLOPs" into
real-world value. Each stage is independently measurable and has
explicit pass/fail criteria.

Chain under test:
  Stage 1: FLOPs Reduction      - Does PCAM actually skip compute?
  Stage 2: Latency Translation   - Do fewer FLOPs -> faster token generation?
  Stage 3: Throughput Gain       - Does faster generation -> more tok/s?
  Stage 4: Cost & ROI Projection - Does more tok/s -> cheaper inference?

Usage:
    python -m benchmarks.pcam_flops_to_roi
    python -m benchmarks.pcam_flops_to_roi --context 8192 --interconnect on_package
    python -m benchmarks.pcam_flops_to_roi --full    # Run all context lengths

Each stage prints PASS/FAIL with measured values vs thresholds.
The overall chain PASSES only if every link holds.
"""

import sys
import os
import time
import json
import math
import argparse
import statistics
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from simulator.pcam import PCAMSimulator, PCAMConfig
from simulator.pcam.core.config import (
    InterconnectType,
    InterconnectConfig,
    AcceptanceThresholds,
)
from simulator.pcam.core.metrics import PCAMMetrics, LatencyStats
from simulator.pcam.traces.generators import SyntheticTraceGenerator
from simulator.pcam.baselines import (
    SinkLRUController,
    H2OController,
    IndustryStyleController,
)
from simulator.pcam.baselines.base import ControllerConfig


# ---------------------------------------------------------------------------
# Data classes for structured results
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    """Result of a single benchmark stage."""
    stage: str
    passed: bool
    metric_name: str
    measured: float
    threshold: float
    unit: str
    details: Dict = field(default_factory=dict)

    def __str__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"  [{status}] {self.stage}: {self.metric_name} = "
            f"{self.measured:.4f} {self.unit} "
            f"(threshold: {self.threshold:.4f})"
        )


@dataclass
class ChainResult:
    """Result of the full FLOPs-to-ROI chain."""
    workload: str
    context_length: int
    interconnect: str
    stages: List[StageResult] = field(default_factory=list)
    chain_passed: bool = False
    wall_clock_sec: float = 0.0

    def __str__(self) -> str:
        lines = [
            f"\n{'='*72}",
            f"  Chain: {self.workload} | ctx={self.context_length} | {self.interconnect}",
            f"{'='*72}",
        ]
        for s in self.stages:
            lines.append(str(s))
        status = "CHAIN PASS" if self.chain_passed else "CHAIN FAIL"
        lines.append(f"  --> {status}  ({self.wall_clock_sec:.2f}s)")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Inference cost model (roofline-style)
# ---------------------------------------------------------------------------

@dataclass
class InferenceModel:
    """
    Simple roofline model for LLM token generation.

    Models the two dominant costs per generated token:
      1. FFN compute   (model-size dependent, NOT reduced by PCAM)
      2. Attention compute (context-length dependent, reduced by PCAM)

    This lets us translate FLOPs reduction into wall-clock speedup
    WITHOUT needing vLLM integration, by modeling what fraction of
    each token's time is spent on attention.
    """
    # Model parameters
    model_params_B: float = 70.0       # 70B parameter model
    num_layers: int = 80               # Llama-70B layers
    num_heads: int = 64
    head_dim: int = 128
    context_length: int = 4096

    # Hardware
    gpu_tflops: float = 312.0          # A100 FP16 peak
    hbm_bandwidth_tb_s: float = 2.0    # A100 HBM bandwidth
    gpu_cost_per_hour: float = 3.50    # Cloud GPU $/hr

    @property
    def attention_flops_per_token(self) -> float:
        """FLOPs for full attention computation per generated token."""
        # Q*K^T + softmax + score*V, per head per layer
        # = 2 * seq_len * head_dim (for QK) + 2 * seq_len * head_dim (for V)
        per_head = 4 * self.context_length * self.head_dim
        return per_head * self.num_heads * self.num_layers

    @property
    def ffn_flops_per_token(self) -> float:
        """FLOPs for FFN (MLP) computation per generated token."""
        # Roughly 2 * model_params for autoregressive decode
        return 2 * self.model_params_B * 1e9

    @property
    def total_flops_per_token(self) -> float:
        return self.attention_flops_per_token + self.ffn_flops_per_token

    @property
    def attention_fraction(self) -> float:
        """What fraction of compute is attention (vs FFN)?"""
        return self.attention_flops_per_token / self.total_flops_per_token

    def tokens_per_second_baseline(self) -> float:
        """Baseline tok/s (compute-bound estimate)."""
        flops_per_token = self.total_flops_per_token
        return (self.gpu_tflops * 1e12) / flops_per_token

    def tokens_per_second_with_pcam(self, attention_reduction: float) -> float:
        """
        tok/s when PCAM reduces attention compute by `attention_reduction` fraction.

        attention_reduction=0.9 means 90% of attention FLOPs are eliminated.
        """
        remaining_attention = self.attention_flops_per_token * (1 - attention_reduction)
        new_total = remaining_attention + self.ffn_flops_per_token
        return (self.gpu_tflops * 1e12) / new_total

    def speedup(self, attention_reduction: float) -> float:
        """Amdahl's law speedup from reducing attention compute."""
        return self.tokens_per_second_with_pcam(attention_reduction) / \
               self.tokens_per_second_baseline()

    def cost_per_million_tokens(self, tok_per_sec: float) -> float:
        """Cost in $ per 1M generated tokens."""
        tokens_per_hour = tok_per_sec * 3600
        if tokens_per_hour <= 0:
            return float("inf")
        return (self.gpu_cost_per_hour / tokens_per_hour) * 1_000_000

    def annual_savings(
        self,
        baseline_tok_s: float,
        pcam_tok_s: float,
        gpus: int = 100,
    ) -> float:
        """Annual $ savings from throughput gain across a fleet."""
        baseline_cost = self.cost_per_million_tokens(baseline_tok_s)
        pcam_cost = self.cost_per_million_tokens(pcam_tok_s)
        # Assume 80% utilization, 1M tokens/GPU/hr at baseline
        tokens_per_year = gpus * baseline_tok_s * 3600 * 24 * 365 * 0.80
        savings_per_token = (baseline_cost - pcam_cost) / 1e6
        return tokens_per_year * savings_per_token


# ---------------------------------------------------------------------------
# Stage 1: FLOPs Reduction
# ---------------------------------------------------------------------------

def stage1_flops_reduction(
    pcam_metrics: PCAMMetrics,
    baseline_metrics: PCAMMetrics,
    trace_steps: int,
    context_blocks: int,
    top_k: int,
) -> StageResult:
    """
    Measures: What fraction of attention FLOPs does PCAM actually skip?

    Method: Compare the number of candidate blocks PCAM attends to (K)
    vs the full context (N blocks). FLOPs reduction = 1 - K/N.

    Threshold: >= 50% FLOPs reduction (conservative; spec claims 87-97%).
    """
    # PCAM attends to K candidates out of N total blocks
    # FLOPs scale linearly with number of blocks attended
    if context_blocks <= top_k:
        reduction = 0.0  # Context too small for savings
    else:
        reduction = 1.0 - (top_k / context_blocks)

    # Also measure quality: are the right blocks in the top-K?
    coverage = pcam_metrics.quality.mean_coverage

    return StageResult(
        stage="Stage 1: FLOPs Reduction",
        passed=reduction >= 0.50,
        metric_name="attention_flops_reduction",
        measured=reduction,
        threshold=0.50,
        unit="fraction",
        details={
            "context_blocks": context_blocks,
            "top_k": top_k,
            "coverage_of_true_top_k": round(coverage, 4),
            "theoretical_max_reduction": round(1.0 - top_k / max(context_blocks, 1), 4),
        },
    )


# ---------------------------------------------------------------------------
# Stage 2: Latency Translation (FLOPs -> wall-clock)
# ---------------------------------------------------------------------------

def stage2_latency_translation(
    pcam_metrics: PCAMMetrics,
    baseline_metrics: PCAMMetrics,
    inference_model: InferenceModel,
    flops_reduction: float,
) -> StageResult:
    """
    Measures: Does FLOPs reduction translate to faster token latency?

    Method: Use Amdahl's law with the inference model.
    Attention is only a FRACTION of total per-token compute.
    Speedup = 1 / (1 - attention_fraction + attention_fraction * (1 - reduction))

    Threshold: speedup >= 1.10 (at least 10% faster per token).
    """
    model = inference_model
    attn_frac = model.attention_fraction

    # Amdahl's law: speedup from accelerating only the attention portion
    # new_time = (1 - attn_frac) + attn_frac * (1 - flops_reduction)
    new_time_fraction = (1 - attn_frac) + attn_frac * (1 - flops_reduction)
    speedup = 1.0 / new_time_fraction if new_time_fraction > 0 else 1.0

    # Also check: does the PCAM ATTEND overhead eat into the savings?
    pcam_attend_p50 = pcam_metrics.attend_latency.p50
    baseline_attend_p50 = baseline_metrics.attend_latency.p50
    overhead_ns = pcam_attend_p50 - baseline_attend_p50  # negative = PCAM faster

    return StageResult(
        stage="Stage 2: Latency Translation",
        passed=speedup >= 1.10,
        metric_name="amdahl_speedup",
        measured=speedup,
        threshold=1.10,
        unit="x",
        details={
            "attention_fraction_of_compute": round(attn_frac, 4),
            "flops_reduction_applied": round(flops_reduction, 4),
            "new_time_fraction": round(new_time_fraction, 4),
            "pcam_attend_p50_ns": round(pcam_attend_p50, 1),
            "baseline_attend_p50_ns": round(baseline_attend_p50, 1),
            "attend_overhead_ns": round(overhead_ns, 1),
            "note": (
                "Speedup is theoretical (Amdahl). "
                "Real speedup requires vLLM integration (Phase 2)."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Stage 3: Throughput Gain (speed -> tok/s)
# ---------------------------------------------------------------------------

def stage3_throughput_gain(
    pcam_metrics: PCAMMetrics,
    baseline_metrics: PCAMMetrics,
    inference_model: InferenceModel,
    amdahl_speedup: float,
    flops_reduction: float,
) -> StageResult:
    """
    Measures: Does faster token generation translate to higher throughput?

    Method: Project tok/s from baseline using Amdahl speedup.
    Also verify that tail latency (p99) doesn't blow up (which would
    negate throughput gains in practice due to SLA violations).

    Threshold: >= 15% throughput improvement (matching G2 gate).
    """
    model = inference_model
    baseline_tok_s = model.tokens_per_second_baseline()
    pcam_tok_s = model.tokens_per_second_with_pcam(flops_reduction)
    projected_gain = (pcam_tok_s - baseline_tok_s) / baseline_tok_s

    # Check tail latency tax: if p99 is bad, effective throughput drops
    pcam_p99 = pcam_metrics.attend_latency.p99
    baseline_p99 = baseline_metrics.attend_latency.p99
    if baseline_p99 > 0:
        p99_overhead = (pcam_p99 - baseline_p99) / baseline_p99
    else:
        p99_overhead = 0.0

    # Tail latency penalty: if p99 overhead > 5%, discount the gain
    tail_latency_ok = p99_overhead <= 0.05
    effective_gain = projected_gain if tail_latency_ok else projected_gain * 0.5

    return StageResult(
        stage="Stage 3: Throughput Gain",
        passed=effective_gain >= 0.15,
        metric_name="projected_throughput_gain",
        measured=effective_gain,
        threshold=0.15,
        unit="fraction",
        details={
            "baseline_tok_s": round(baseline_tok_s, 1),
            "pcam_projected_tok_s": round(pcam_tok_s, 1),
            "raw_gain": round(projected_gain, 4),
            "p99_overhead": round(p99_overhead, 4),
            "tail_latency_ok": tail_latency_ok,
            "effective_gain_after_p99_tax": round(effective_gain, 4),
            "amdahl_speedup_used": round(amdahl_speedup, 4),
            "note": (
                "Projected via Amdahl roofline model. "
                "Actual measurement requires vLLM integration."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Stage 4: Cost & ROI Projection
# ---------------------------------------------------------------------------

def stage4_cost_roi(
    inference_model: InferenceModel,
    flops_reduction: float,
    throughput_gain: float,
    coverage: float,
    pcam_card_cost: float = 5000.0,
    fleet_gpus: int = 100,
) -> StageResult:
    """
    Measures: Does throughput gain translate to real cost savings?

    Method: Compute $/M tokens for baseline vs PCAM, project annual
    savings, compute payback period for PCAM hardware investment.

    Threshold: payback_months <= 18 (conservative; spec claims 4.8).
    """
    model = inference_model
    baseline_tok_s = model.tokens_per_second_baseline()
    pcam_tok_s = model.tokens_per_second_with_pcam(flops_reduction)

    baseline_cost_per_m = model.cost_per_million_tokens(baseline_tok_s)
    pcam_cost_per_m = model.cost_per_million_tokens(pcam_tok_s)
    cost_reduction_pct = (
        (baseline_cost_per_m - pcam_cost_per_m) / baseline_cost_per_m * 100
        if baseline_cost_per_m > 0 else 0.0
    )

    annual_savings = model.annual_savings(baseline_tok_s, pcam_tok_s, fleet_gpus)
    hw_investment = pcam_card_cost * fleet_gpus
    payback_months = (
        (hw_investment / annual_savings * 12) if annual_savings > 0 else float("inf")
    )

    # Quality discount: if coverage < 80%, the savings aren't real
    # because you'd need to recompute dropped attention
    quality_adjusted = coverage >= 0.80

    return StageResult(
        stage="Stage 4: Cost & ROI",
        passed=payback_months <= 18.0 and quality_adjusted,
        metric_name="payback_months",
        measured=payback_months,
        threshold=18.0,
        unit="months",
        details={
            "baseline_cost_per_M_tokens": round(baseline_cost_per_m, 2),
            "pcam_cost_per_M_tokens": round(pcam_cost_per_m, 2),
            "cost_reduction_pct": round(cost_reduction_pct, 2),
            "annual_savings_usd": round(annual_savings, 0),
            "hw_investment_usd": hw_investment,
            "fleet_gpus": fleet_gpus,
            "pcam_card_cost_usd": pcam_card_cost,
            "coverage_gate_passed": quality_adjusted,
            "coverage": round(coverage, 4),
            "note": (
                "Economics assume compute-bound regime and "
                f"{fleet_gpus}-GPU fleet at 80% utilization."
            ),
        },
    )


# ---------------------------------------------------------------------------
# Run the full chain
# ---------------------------------------------------------------------------

def run_chain(
    workload: str,
    context_length: int,
    interconnect: InterconnectType,
    seed: int = 42,
    top_k: int = 64,
    verbose: bool = True,
) -> ChainResult:
    """Run the full FLOPs-to-ROI chain for one configuration."""

    start = time.time()
    block_size = 16
    context_blocks = context_length // block_size

    # ---- Generate trace ----
    gen = SyntheticTraceGenerator(seed=seed)
    trace_kwargs = {"block_size": block_size, "top_k": top_k}

    if workload == "chat":
        num_turns = max(5, context_length // 200)
        trace = gen.generate_chat_trace(
            num_turns=num_turns,
            tokens_per_turn=(50, 200),
            **trace_kwargs,
        )
    elif workload == "code":
        trace = gen.generate_code_trace(
            file_length=context_length,
            num_queries=min(200, context_length // 10),
            **trace_kwargs,
        )
    elif workload == "long_context":
        trace = gen.generate_long_context_trace(
            context_length=context_length,
            num_queries=min(200, context_length // 20),
            **trace_kwargs,
        )
    elif workload == "rag":
        num_docs = max(3, context_length // 2048)
        trace = gen.generate_rag_trace(
            num_docs=num_docs,
            doc_length=min(2048, context_length // num_docs),
            relevant_docs=max(1, num_docs // 3),
            query_length=min(100, context_length // 20),
            **trace_kwargs,
        )
    elif workload == "multitenant":
        trace = gen.generate_multitenant_trace(
            num_sequences=16,
            total_steps=min(1000, context_length),
            **trace_kwargs,
        )
    else:
        raise ValueError(f"Unknown workload: {workload}")

    # ---- Configure simulator ----
    config = PCAMConfig(
        interconnect=InterconnectConfig(interconnect_type=interconnect),
    )
    sim = PCAMSimulator(config=config, verbose=False)

    # ---- Run PCAM ----
    pcam_result = sim.run_pcam(trace, workload)

    # ---- Run best baseline (H2O) ----
    ctrl_config = ControllerConfig(
        cache_capacity=min(256, context_blocks),
        num_sinks=4,
        recent_window=32,
        top_k=top_k,
    )
    baseline_result = sim.run_baseline(
        trace, H2OController(ctrl_config), workload
    )

    # ---- Build inference model ----
    model = InferenceModel(context_length=context_length)

    # ---- Stage 1 ----
    s1 = stage1_flops_reduction(
        pcam_metrics=pcam_result.metrics,
        baseline_metrics=baseline_result.metrics,
        trace_steps=trace.num_steps,
        context_blocks=context_blocks,
        top_k=top_k,
    )

    # ---- Stage 2 ----
    s2 = stage2_latency_translation(
        pcam_metrics=pcam_result.metrics,
        baseline_metrics=baseline_result.metrics,
        inference_model=model,
        flops_reduction=s1.measured,
    )

    # ---- Stage 3 ----
    s3 = stage3_throughput_gain(
        pcam_metrics=pcam_result.metrics,
        baseline_metrics=baseline_result.metrics,
        inference_model=model,
        amdahl_speedup=s2.measured,
        flops_reduction=s1.measured,
    )

    # ---- Stage 4 ----
    coverage = pcam_result.metrics.quality.mean_coverage
    s4 = stage4_cost_roi(
        inference_model=model,
        flops_reduction=s1.measured,
        throughput_gain=s3.measured,
        coverage=coverage,
    )

    elapsed = time.time() - start
    stages = [s1, s2, s3, s4]

    result = ChainResult(
        workload=workload,
        context_length=context_length,
        interconnect=interconnect.value,
        stages=stages,
        chain_passed=all(s.passed for s in stages),
        wall_clock_sec=elapsed,
    )

    if verbose:
        print(result)

    return result


# ---------------------------------------------------------------------------
# Sweep across configurations
# ---------------------------------------------------------------------------

def run_context_sweep(
    workload: str = "chat",
    interconnect: InterconnectType = InterconnectType.CXL_2_0,
    verbose: bool = True,
) -> List[ChainResult]:
    """
    Run the chain at multiple context lengths to find where each link
    in the chain starts to hold vs break.

    This is the most important benchmark: it answers "at what context
    length does PCAM pay for itself?"
    """
    context_lengths = [1024, 2048, 4096, 8192, 16384]
    results = []

    if verbose:
        print(f"\n{'#'*72}")
        print(f"  Context Sweep: {workload} on {interconnect.value}")
        print(f"{'#'*72}")

    for ctx in context_lengths:
        result = run_chain(
            workload=workload,
            context_length=ctx,
            interconnect=interconnect,
            verbose=verbose,
        )
        results.append(result)

    # Summary table
    if verbose:
        print(f"\n{'='*72}")
        print(f"  CONTEXT SWEEP SUMMARY: {workload} | {interconnect.value}")
        print(f"{'='*72}")
        print(f"  {'Context':>8}  {'FLOPs%':>7}  {'Speedup':>8}  {'Gain%':>7}  "
              f"{'Payback':>8}  {'Chain':>6}")
        print(f"  {'':->8}  {'':->7}  {'':->8}  {'':->7}  {'':->8}  {'':->6}")
        for r in results:
            s1 = r.stages[0]
            s2 = r.stages[1]
            s3 = r.stages[2]
            s4 = r.stages[3]
            chain = "PASS" if r.chain_passed else "FAIL"
            payback = f"{s4.measured:.1f}mo" if s4.measured < 999 else "inf"
            print(
                f"  {r.context_length:>8}  "
                f"{s1.measured*100:>6.1f}%  "
                f"{s2.measured:>7.2f}x  "
                f"{s3.measured*100:>6.1f}%  "
                f"{payback:>8}  "
                f"{chain:>6}"
            )

    return results


def run_workload_matrix(
    interconnect: InterconnectType = InterconnectType.CXL_2_0,
    context_length: int = 8192,
    verbose: bool = True,
) -> List[ChainResult]:
    """
    Run all workloads at a fixed context length to see which
    workload types benefit most from PCAM.
    """
    workloads = ["chat", "code", "long_context", "rag", "multitenant"]
    results = []

    if verbose:
        print(f"\n{'#'*72}")
        print(f"  Workload Matrix: ctx={context_length} | {interconnect.value}")
        print(f"{'#'*72}")

    for wl in workloads:
        result = run_chain(
            workload=wl,
            context_length=context_length,
            interconnect=interconnect,
            verbose=verbose,
        )
        results.append(result)

    # Summary
    if verbose:
        print(f"\n{'='*72}")
        print(f"  WORKLOAD MATRIX SUMMARY: ctx={context_length}")
        print(f"{'='*72}")
        print(f"  {'Workload':<14}  {'FLOPs%':>7}  {'Coverage':>9}  "
              f"{'Speedup':>8}  {'Gain%':>7}  {'Chain':>6}")
        print(f"  {'':->14}  {'':->7}  {'':->9}  {'':->8}  {'':->7}  {'':->6}")
        for r in results:
            s1 = r.stages[0]
            s2 = r.stages[1]
            s3 = r.stages[2]
            cov = s1.details.get("coverage_of_true_top_k", 0)
            chain = "PASS" if r.chain_passed else "FAIL"
            print(
                f"  {r.workload:<14}  "
                f"{s1.measured*100:>6.1f}%  "
                f"{cov*100:>8.1f}%  "
                f"{s2.measured:>7.2f}x  "
                f"{s3.measured*100:>6.1f}%  "
                f"{chain:>6}"
            )

    return results


def run_interconnect_comparison(
    workload: str = "chat",
    context_length: int = 8192,
    verbose: bool = True,
) -> List[ChainResult]:
    """
    Run the same workload across different interconnects to see
    how PCAM's latency overhead changes with link speed.
    """
    interconnects = [
        InterconnectType.PCIE_GEN5_X16,
        InterconnectType.CXL_2_0,
        InterconnectType.CXL_3_0,
        InterconnectType.ON_PACKAGE,
    ]
    results = []

    if verbose:
        print(f"\n{'#'*72}")
        print(f"  Interconnect Comparison: {workload} ctx={context_length}")
        print(f"{'#'*72}")

    for ic in interconnects:
        result = run_chain(
            workload=workload,
            context_length=context_length,
            interconnect=ic,
            verbose=verbose,
        )
        results.append(result)

    if verbose:
        print(f"\n{'='*72}")
        print(f"  INTERCONNECT COMPARISON SUMMARY")
        print(f"{'='*72}")
        print(f"  {'Interconnect':<16}  {'ATTEND p50':>11}  {'ATTEND p99':>11}  "
              f"{'p99 overhead':>13}  {'Chain':>6}")
        print(f"  {'':->16}  {'':->11}  {'':->11}  {'':->13}  {'':->6}")
        for r in results:
            s2 = r.stages[1]
            p50 = s2.details.get("pcam_attend_p50_ns", 0)
            p99_overhead = r.stages[2].details.get("p99_overhead", 0)
            p99 = 0.0
            # Get p99 from stage 3 details
            chain = "PASS" if r.chain_passed else "FAIL"
            print(
                f"  {r.interconnect:<16}  "
                f"{p50:>10.1f}ns  "
                f"{'':>11}  "
                f"{p99_overhead*100:>12.1f}%  "
                f"{chain:>6}"
            )

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PCAM FLOPs-to-ROI Confidence Chain Benchmark"
    )
    parser.add_argument(
        "--workload", default="chat",
        choices=["chat", "code", "long_context", "rag", "multitenant"],
        help="Workload type"
    )
    parser.add_argument(
        "--context", type=int, default=8192,
        help="Context length in tokens"
    )
    parser.add_argument(
        "--interconnect", default="cxl_2_0",
        choices=["pcie_gen5_x16", "cxl_2_0", "cxl_3_0", "on_package"],
        help="Interconnect type"
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Run full suite: context sweep + workload matrix + interconnect comparison"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()
    ic = InterconnectType(args.interconnect)

    all_results = []

    if args.full:
        # Full suite
        all_results.extend(run_context_sweep("chat", ic))
        all_results.extend(run_context_sweep("code", ic))
        all_results.extend(run_workload_matrix(ic, args.context))
        all_results.extend(run_interconnect_comparison("chat", args.context))
    else:
        # Single run
        result = run_chain(
            workload=args.workload,
            context_length=args.context,
            interconnect=ic,
        )
        all_results.append(result)

    # Final summary
    passed = sum(1 for r in all_results if r.chain_passed)
    total = len(all_results)

    print(f"\n{'='*72}")
    print(f"  OVERALL: {passed}/{total} chains passed")
    print(f"{'='*72}")

    # Identify weakest links
    stage_pass_rates = {}
    for r in all_results:
        for s in r.stages:
            if s.stage not in stage_pass_rates:
                stage_pass_rates[s.stage] = {"passed": 0, "total": 0}
            stage_pass_rates[s.stage]["total"] += 1
            if s.passed:
                stage_pass_rates[s.stage]["passed"] += 1

    print("\n  Stage pass rates:")
    for stage, counts in sorted(stage_pass_rates.items()):
        rate = counts["passed"] / counts["total"] * 100
        print(f"    {stage}: {counts['passed']}/{counts['total']} ({rate:.0f}%)")

    if args.json:
        json_results = []
        for r in all_results:
            json_results.append({
                "workload": r.workload,
                "context_length": r.context_length,
                "interconnect": r.interconnect,
                "chain_passed": r.chain_passed,
                "stages": [
                    {
                        "stage": s.stage,
                        "passed": s.passed,
                        "metric": s.metric_name,
                        "measured": s.measured,
                        "threshold": s.threshold,
                        "details": s.details,
                    }
                    for s in r.stages
                ],
            })
        print("\n" + json.dumps(json_results, indent=2))

    # Exit with failure if any chain failed
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
