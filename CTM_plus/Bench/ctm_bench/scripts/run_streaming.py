"""CLI entrypoint for the streaming Mode B runner (#3 Phase 1).

Wraps :class:`ctm_bench.runner_vllm_streaming.AsyncEngineDriver`
with a command-line interface that the
``scripts/run_streaming.sh`` shell driver invokes per-cell.

Phase 1 is LRU-only; the CTM+ path remains gated on Phase 2.
"""

from __future__ import annotations

# Self-bootstrap: when launched as `python -m ctm_bench.scripts.run_streaming`
# from a venv that doesn't have kv_policy on PYTHONPATH (the common case
# on a fresh pod), our runtime imports of `kv_policy.triattention`
# would fail at the first call into the Phase 4 hooks. The helper
# walks up to CTM_plus/KVPolicy and prepends it to sys.path; safe to
# call repeatedly. Catch ImportError because conftest tests already
# expose this helper via a relative import; here we go through the
# ctm_bench package.
from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()

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
        "--phase3-attention",
        action="store_true",
        help=(
            "Phase 3: install the attention-capture hook so real "
            "attention sums reach CTM+'s scoring (the 0.35*attn "
            "term). Requires --ctm-plus. The actual GPU-side "
            "attention extraction is gated on the next GPU run; "
            "the install path itself is CPU-tested."
        ),
    )
    parser.add_argument(
        "--phase3-capture-every-n", type=int, default=4,
        help=(
            "Phase 3 layer subsampling factor. The per-layer "
            "attention capture costs ~2ms per decode step (the "
            ".tolist() + Python aggregation at "
            "vllm_evictor.py:2134-2143). Day 5b May 2026 measured "
            "82%% wall on Qwen2.5-7B chat_32k. Capture from every "
            "Nth Attention layer instead of every one to cut the "
            "overhead. Default 4 (matches the Phase 4 path's "
            "--phase4-capture-every-n production default); set "
            "to 1 for the legacy 'every layer' ablation."
        ),
    )
    parser.add_argument(
        "--phase4-trig-calibration",
        type=Path, default=None,
        help=(
            "Phase 4: path to a TriAttention-style calibration "
            "JSON (QCenterStats.save() output). Loads the "
            "calibration at engine init and configures "
            "CTMEvictorModern to use trig scoring + window-based "
            "pruning. Requires --ctm-plus. Mutually exclusive "
            "with --phase3-attention (competing hypotheses; run "
            "in separate cells)."
        ),
    )
    parser.add_argument(
        "--phase4-window-interval", type=int, default=128,
        help=(
            "Phase 4: trigger window-based pruning every N "
            "decoded tokens. Default 128 (matches TriAttention's "
            "β). Lower = more aggressive pruning."
        ),
    )
    parser.add_argument(
        "--phase4-future-offsets", default=None,
        help=(
            "Phase 4: comma-separated list of future-query "
            "distances Δ for S_trig averaging. Default '1,2,4,8,16'. "
            "Larger sets capture longer-horizon attention "
            "preferences at higher compute cost."
        ),
    )
    parser.add_argument(
        "--phase4-num-layers", type=int, default=0,
        help=(
            "Phase 4: number of transformer layers in the model. "
            "When > number of rotary_emb modules (e.g., on Qwen2.5 "
            "where 28 layers share a single rotary_emb), enables "
            "call-counter layer indexing during pre-RoPE capture so "
            "scoring uses per-layer Q-center stats. Default 0 means "
            "auto-detect from the model's config.num_hidden_layers."
        ),
    )
    parser.add_argument(
        "--phase4-capture-every-n", type=int, default=1,
        help=(
            "Phase 4: only run pre-RoPE K capture every N rotary "
            "firings (at the target layer). Cuts the speculative-"
            "storage overhead (the May 2026 GPU run measured 159K "
            "captures / 60s; N=4 reduces that to ~40K). Default 1 "
            "= no subsample. Use 4 for the production-default "
            "trade-off."
        ),
    )
    parser.add_argument(
        "--phase4-trig-blend-candidate-count", type=int, default=4,
        help=(
            "Phase 4: oversample factor for the trig-blend re-rank "
            "in evict(). The v5 GPU run used 8 (hardcoded); 8x base "
            "scoring per evict accounts for some of the 20%% Python "
            "throughput regression. Default 4 keeps most of the "
            "62%% trig_changed_pick rate at half the cost. Set to "
            "1 to disable trig blending in evict() (trig still "
            "affects window_pruning_pass)."
        ),
    )
    parser.add_argument(
        "--phase4-cython-evictor",
        action="store_true",
        help=(
            "Phase 4: install CTMEvictorModernC (Cython port) "
            "instead of CTMEvictorModern (pure Python). Semantically "
            "identical at the algorithm layer; closes the per-call "
            "Python dispatch overhead the v8 py-spy profile "
            "(PHASE4_GPU_FINDINGS §11) attributed the 20%% throughput "
            "regression to. Requires the compiled .so at "
            "kv_policy/_ctm_evictor.cpython-*.so; build with "
            "`cd CTM_plus/KVPolicy && python3 setup.py build_ext "
            "--inplace`. When the .so is absent this flag is a "
            "silent no-op (Python class). v9 GPU result: 0pp "
            "throughput recovery; see PHASE4_GPU_FINDINGS §12.6."
        ),
    )
    parser.add_argument(
        "--phase4-fast-hooks",
        action="store_true",
        help=(
            "Phase 4: install hooks via direct monkey-patch of "
            "module.forward instead of register_forward_pre_hook. "
            "Skips torch's _call_impl _forward_pre_hooks walk on "
            "every fire — that walk is a slice of the 15%% "
            "_call_impl share in PHASE4_GPU_FINDINGS §11.1, §11.3 "
            "row 2 estimate is 2-5pp recovery (combined with the "
            "implicit row-3 model-level consolidation here, 3-8pp). "
            "Semantically identical to the hook path; same counters, "
            "same firing order. v9 (Cython only) landed at 0pp "
            "recovery; v10 (Cython + fast hooks) is the test of "
            "whether the gap is fixable at the hook-shape layer or "
            "is structurally below it."
        ),
    )
    parser.add_argument(
        "--kv-cache-dtype",
        default=None,
        choices=["auto", "fp8", "fp8_e4m3", "fp8_e5m2", "fp16", "bf16"],
        help=(
            "Override vLLM's KV-cache storage dtype. When unset the "
            "engine picks 'auto' (= model weight dtype). 'fp8' enables "
            "vLLM's hardware-tensor-core FP8 KV path on A100/H100 — "
            "the production competitor to the route-B INT4 KIVI work. "
            "Used by FP8_INT4_THROUGHPUT_RUNBOOK.md to compose the "
            "FP16 baseline vs FP8 KV throughput comparison."
        ),
    )
    parser.add_argument(
        "--int4-kv-route-a",
        action="store_true",
        help=(
            "Route-A: install the KIVI INT4 KV-cache integration — a "
            "monkey-patch of the model's Attention modules that runs "
            "K/V through the INT4 round-trip inside vLLM. This is the "
            "production-path analog of the route-B HF DynamicCache "
            "wrapper (which only the §20 measurement harnesses use). "
            "Orthogonal to --ctm-plus; both compose. See "
            "ROUTE_A_VLLM_CACHE_KV_PLAN.md. NOTE: this tier runs the "
            "INT4 quality path under vLLM; the memory-realizing "
            "paged-buffer swap is the documented follow-up."
        ),
    )
    parser.add_argument(
        "--int4-kv-k-group-size", type=int, default=32,
        help="Route-A INT4: K group-quant size (default 32 = §18.3 ship).",
    )
    parser.add_argument(
        "--int4-kv-v-group-size", type=int, default=32,
        help="Route-A INT4: V group-quant size (default 32 = §18.3 ship).",
    )
    parser.add_argument(
        "--int4-kv-symmetric", action="store_true",
        help=(
            "Route-A INT4: use symmetric quant instead of the default "
            "asymmetric. The §18.3 ship config is asymmetric; this "
            "flag is for ablation only."
        ),
    )
    parser.add_argument(
        "--int4-kv-bits", type=int, default=4,
        help="Route-A INT4: bit width (default 4 = validated KIVI config).",
    )
    parser.add_argument(
        "--int4-kv-sink-size", type=int, default=0,
        help=(
            "Route-A INT4: StreamingLLM sink-FP16 passthrough — keep "
            "the first N positions of each prefill in FP16. The §20.2 "
            "sink-FP16 path applied at the route-A layer. Default 0."
        ),
    )
    parser.add_argument(
        "--int4-kv-num-kv-heads", type=int, default=None,
        help=(
            "Route-A INT4: KV-head count, needed to reshape vLLM's "
            "2-D K/V (num_tokens, num_kv_heads*head_dim) to the 3-D "
            "(S, H, D) the quantizer wants. Default None = auto-detect "
            "from model.config (num_key_value_heads). Pass explicitly "
            "if the run-end log shows skipped_unknown_shape > 0."
        ),
    )
    parser.add_argument(
        "--turboquant-kv",
        action="store_true",
        help=(
            "RETIRED. Selecting this flag will exit with an error. "
            "See CTM_plus/TURBOQUANT_RETIREMENT.md."
        ),
    )
    parser.add_argument(
        "--cache-aware-scheduling",
        action="store_true",
        help=(
            "EXPERIMENTAL — DO NOT ENABLE IN PRODUCTION. Cache-aware "
            "admission scheduling: reorders the engine's waiting "
            "queue by predicted block-aligned prefix-cache hit rate, "
            "with a starvation guard. Two-seed Tier-A measurement on "
            "Qwen-7B chat workload returned an INCONCLUSIVE "
            "realized-hit signal (C/B = 0.903 and 1.115, opposite "
            "signs) with a consistent mild E2E p99 regression "
            "(1.4-1.6x). See PHASE3_CACHE_AWARE_FINDINGS.md for the "
            "full measurement + revisit conditions. The CLI flag is "
            "retained for further experimentation; it is NOT a "
            "production-validated v2 surface. Orthogonal to "
            "--ctm-plus, --int4-kv-route-a, and the shipped "
            "int4_protected backend (different layer)."
        ),
    )
    parser.add_argument(
        "--cache-aware-max-starvation-seconds",
        type=float, default=30.0,
        help=(
            "v2 cache-reuse PR-2: fairness guard. Any request older "
            "than this in the waiting queue is admitted next "
            "regardless of predicted cache-hit rate. Default 30s "
            "(matches the Phase 0 CPU prototype default)."
        ),
    )
    parser.add_argument(
        "--shared-prefix-length",
        type=int, default=0,
        help=(
            "Phase 3A workload shape: when > 0, switches to the "
            "cohort-shared prompt builder used by the Phase 3 "
            "comparison cells. Each request becomes "
            "[cohort_prefix of this length] + [unique tail]. "
            "Default 0 (= legacy Pareto-unique-head shape; "
            "preserves PR-2 behaviour byte-identical)."
        ),
    )
    parser.add_argument(
        "--shared-prefix-unique-tail-choices",
        default="32,64,128,256",
        help=(
            "Phase 3A: comma-separated tail-length choices for the "
            "shared-prefix builder (sampled uniformly per request). "
            "Only used when --shared-prefix-length > 0. Default "
            "matches the chat-shape distribution in the Phase 3 "
            "design (32, 64, 128, 256 tokens)."
        ),
    )
    parser.add_argument(
        "--n-shared-prefixes",
        type=int, default=4,
        help=(
            "Phase 3A: number of distinct shared-prefix cohorts. "
            "Default 4 per the approved cohort design (4 cohorts × "
            "25 requests = 100 reqs at the typical workload size). "
            "Only used when --shared-prefix-length > 0."
        ),
    )
    parser.add_argument(
        "--collect-native-prefix-hits",
        action="store_true",
        help=(
            "Phase 3A: install the prefix-hit probe — a "
            "measurement-only wrap of block_manager.allocate that "
            "counts vLLM's native prefix-cache hits per request. "
            "Default OFF (preserves PR-2 behaviour). Set this for "
            "the Phase 3 cell-comparison harness so cells A/B/C "
            "all report directly-comparable realized-hit numbers."
        ),
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    if getattr(args, "turboquant_kv", False):
        raise SystemExit(
            "TurboQuant/QJL KV path retired after failed local validation; "
            "see TURBOQUANT_RETIREMENT.md"
        )

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

    phase4_offsets = None
    if args.phase4_future_offsets is not None:
        phase4_offsets = [
            int(s.strip())
            for s in args.phase4_future_offsets.split(",")
            if s.strip()
        ]
        if not phase4_offsets:
            print(
                "--phase4-future-offsets must list at least one offset",
                file=sys.stderr,
            )
            return 2

    driver = AsyncEngineDriver(
        model=args.model,
        gpu_memory_utilization=args.gpu_memory_utilization,
        swap_space_gb=args.swap_space_gb,
        seed=args.seed,
        ctm_plus_evictor=args.ctm_plus,
        enable_prefix_caching=args.enable_prefix_caching,
        phase3_attention_capture=args.phase3_attention,
        phase3_capture_every_n=args.phase3_capture_every_n,
        phase4_trig_calibration_path=args.phase4_trig_calibration,
        phase4_window_interval=args.phase4_window_interval,
        phase4_future_offsets=phase4_offsets,
        phase4_num_layers=args.phase4_num_layers,
        phase4_capture_every_n=args.phase4_capture_every_n,
        phase4_trig_blend_candidate_count=args.phase4_trig_blend_candidate_count,
        phase4_use_cython_evictor=args.phase4_cython_evictor,
        phase4_fast_hooks=args.phase4_fast_hooks,
        kv_cache_dtype=args.kv_cache_dtype,
        int4_kv_route_a=args.int4_kv_route_a,
        int4_kv_k_group_size=args.int4_kv_k_group_size,
        int4_kv_v_group_size=args.int4_kv_v_group_size,
        int4_kv_asymmetric=not args.int4_kv_symmetric,
        int4_kv_bits=args.int4_kv_bits,
        int4_kv_sink_size=args.int4_kv_sink_size,
        int4_kv_num_kv_heads=args.int4_kv_num_kv_heads,
        cache_aware_scheduling=args.cache_aware_scheduling,
        cache_aware_max_starvation_seconds=(
            args.cache_aware_max_starvation_seconds
        ),
        shared_prefix_length=args.shared_prefix_length,
        shared_prefix_unique_tail_choices=(
            [int(s.strip())
             for s in args.shared_prefix_unique_tail_choices.split(",")
             if s.strip()]
            if args.shared_prefix_length > 0 else None
        ),
        n_shared_prefixes=args.n_shared_prefixes,
        collect_native_prefix_hits=args.collect_native_prefix_hits,
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
