"""CLI entrypoint for the streaming Mode B runner (#3 Phase 1).

Wraps :class:`ctm_bench.runner_vllm_streaming.AsyncEngineDriver`
with a command-line interface that the
``scripts/run_streaming.sh`` shell driver invokes per-cell.

Phase 1 is LRU-only; the CTM+ path remains gated on Phase 2.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Sequence


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run_streaming",
        description=(
            "Run one streaming Mode B cell — AsyncLLMEngine + "
            "preemption-mode-swap + Pareto-bursty arrivals. "
            "LRU-only (#3 Phase 1)."
        ),
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--workload", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--gpu-memory-utilization", type=float, default=0.30,
    )
    parser.add_argument("--swap-space-gb", type=int, default=16)
    parser.add_argument(
        "--arrival-rate", type=float, default=2.0,
        help="Pareto arrivals per second (long-run mean).",
    )
    parser.add_argument(
        "--arrival-alpha", type=float, default=1.5,
        help="Pareto shape parameter; lower = burstier.",
    )
    parser.add_argument(
        "--max-requests", type=int, default=200,
        help="Per-cell request budget.",
    )
    parser.add_argument(
        "--max-wall-seconds", type=float, default=180.0,
        help="Per-cell wall-clock budget.",
    )
    parser.add_argument(
        "--max-decode-tokens", type=int, default=128,
        help="max_tokens per request's SamplingParams.",
    )
    parser.add_argument(
        "--prompt-length-choices",
        default="256,512,1024,2048",
        help=(
            "Comma-separated list of prompt lengths to sample "
            "from in Pareto mode. Match to your workload."
        ),
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
    )
    parser.add_argument(
        "--ctm-plus", action="store_true",
        help=(
            "Enable CTM+ evictor (Phase 2). Forces "
            "--enable-prefix-caching since CTM+'s patch "
            "installs on PrefixCachingBlockAllocator's evictor slot."
        ),
    )
    parser.add_argument(
        "--enable-prefix-caching",
        action="store_true",
        default=None,
        help=(
            "Force prefix caching on. The default is to enable it "
            "iff --ctm-plus is set. Set this flag explicitly for "
            "an apples-to-apples LRU baseline against a Phase 2 "
            "CTM+ cell (both run with prefix caching → both decide "
            "cache-retention → policy is the only difference)."
        ),
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    from ctm_bench.runner_vllm_streaming import (
        AsyncEngineDriver, ArrivalScheduler, ParetoArrivalConfig,
        SwapCounterSampler,
    )

    prompt_lengths = [
        int(s.strip())
        for s in args.prompt_length_choices.split(",")
        if s.strip()
    ]
    if not prompt_lengths:
        print(
            "--prompt-length-choices must list at least one length",
            file=sys.stderr,
        )
        return 2

    scheduler = ArrivalScheduler(
        seed=args.seed,
        pareto=ParetoArrivalConfig(
            base_rate_per_sec=args.arrival_rate,
            alpha=args.arrival_alpha,
        ),
        prompt_length_choices=prompt_lengths,
    )
    sampler = SwapCounterSampler()
    driver = AsyncEngineDriver(
        model=args.model,
        gpu_memory_utilization=args.gpu_memory_utilization,
        swap_space_gb=args.swap_space_gb,
        seed=args.seed,
        ctm_plus_evictor=args.ctm_plus,
        enable_prefix_caching=args.enable_prefix_caching,
        max_decode_tokens=args.max_decode_tokens,
    )

    result = asyncio.new_event_loop().run_until_complete(
        driver.run(
            scheduler=scheduler,
            sampler=sampler,
            max_requests=args.max_requests,
            max_wall_seconds=args.max_wall_seconds,
            workload_name=args.workload,
        )
    )

    summary_path = args.output_dir / "streaming_summary.json"
    summary_path.write_text(
        json.dumps(asdict(result), indent=2, sort_keys=True)
    )
    print(
        f"workload={result.workload_name} "
        f"policy={result.policy_name} "
        f"admitted={result.n_requests_admitted} "
        f"completed={result.n_requests_completed} "
        f"decode_tokens={result.n_decode_tokens} "
        f"swap_out={result.swap_out_blocks} "
        f"preempt={result.preemption_events} "
        f"wall={result.wall_clock_seconds:.2f}s"
    )
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
