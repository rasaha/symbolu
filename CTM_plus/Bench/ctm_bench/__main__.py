"""CLI entry: ``python -m ctm_bench [options]``.

Defaults run the full sweep (3 workloads × 3 policies × 1 tier
config = 9 cells) with seed 42 and writes a JSON summary +
markdown report to stdout. Use ``--output-dir`` to write the
report to disk.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Sequence

from ctm_bench.metrics import RunResult, markdown_table, summarize, to_json
from ctm_bench.policies import POLICIES
from ctm_bench.runner_sim import run_sim
from ctm_bench.tier_model import HBM_DDR_NVME_2025, HBM_HBF_NVME_2025
from ctm_bench.workload import (
    AGENTIC_64K,
    AGENTIC_CLUSTERED_64K,
    CHAT_32K,
    RAG_128K,
    WorkloadSpec,
)


_WORKLOADS = {
    "agentic_64k": AGENTIC_64K,
    "agentic_clustered_64k": AGENTIC_CLUSTERED_64K,
    "rag_128k": RAG_128K,
    "chat_32k": CHAT_32K,
}

_TIER_CONFIGS = {
    "hbm_ddr_nvme": HBM_DDR_NVME_2025,
    "hbm_hbf_nvme": HBM_HBF_NVME_2025,
}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ctm_bench",
        description=(
            "CTM+ tier-aware inference benchmark (Mode A — synthetic). "
            "Runs LRU + FIFO + CTM+ on long-context workloads against "
            "a multi-tier cache; reports per-tier byte counters."
        ),
    )
    p.add_argument(
        "--workloads",
        type=str,
        default="agentic_64k,agentic_clustered_64k,rag_128k,chat_32k",
        help=(
            "Comma-separated list of workload names. "
            f"Available: {sorted(_WORKLOADS.keys())}"
        ),
    )
    p.add_argument(
        "--policies",
        type=str,
        default="lru,fifo,ctm_plus",
        help=(
            "Comma-separated policy list. "
            f"Available: {sorted(POLICIES.keys())}"
        ),
    )
    p.add_argument(
        "--tier-config",
        type=str,
        default="hbm_ddr_nvme",
        choices=sorted(_TIER_CONFIGS.keys()),
        help="Memory tier configuration to model.",
    )
    p.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed propagated to every workload + policy.",
    )
    p.add_argument(
        "--hbm-oversubscription",
        type=float,
        default=0.4,
        help=(
            "Tier-0 capacity as a fraction of the working set. "
            "Must be in (0, 1) so spillover engages."
        ),
    )
    p.add_argument(
        "--ema-alpha",
        type=float,
        default=None,
        help=(
            "Override CTM+'s attention_ema_alpha. None (default) "
            "uses the production default in KVCachePolicy. Used "
            "for A/B comparisons against the production setting "
            "(Round 3 ema-alpha sweep)."
        ),
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="If set, writes summary.json + report.md into this dir.",
    )
    p.add_argument(
        "--smoke",
        action="store_true",
        help=(
            "Run a quick smoke variant with reduced contexts; useful "
            "for CI / development sanity checks."
        ),
    )
    return p


def _smokify(spec: WorkloadSpec) -> WorkloadSpec:
    """Return a small variant of `spec` for fast smoke runs."""
    return WorkloadSpec(
        name=f"{spec.name}_smoke",
        pattern=spec.pattern,
        n_concurrent_seqs=min(2, spec.n_concurrent_seqs),
        context_length_tokens=min(1024, spec.context_length_tokens),
        duration_decode_tokens=min(64, spec.duration_decode_tokens),
        block_size_tokens=spec.block_size_tokens,
        seed=spec.seed,
    )


def _resolve_workloads(arg: str, smoke: bool) -> List[WorkloadSpec]:
    names = [n.strip() for n in arg.split(",") if n.strip()]
    out: List[WorkloadSpec] = []
    for n in names:
        if n not in _WORKLOADS:
            raise SystemExit(
                f"unknown workload {n!r}; available: {sorted(_WORKLOADS.keys())}"
            )
        spec = _WORKLOADS[n]
        if smoke:
            spec = _smokify(spec)
        out.append(spec)
    return out


def _resolve_policies(arg: str) -> List[str]:
    names = [n.strip() for n in arg.split(",") if n.strip()]
    for n in names:
        if n not in POLICIES:
            raise SystemExit(
                f"unknown policy {n!r}; available: {sorted(POLICIES.keys())}"
            )
    return names


def main(argv: Sequence[str]) -> int:
    args = _build_parser().parse_args(argv)
    workloads = _resolve_workloads(args.workloads, smoke=args.smoke)
    policies = _resolve_policies(args.policies)
    tier_specs = _TIER_CONFIGS[args.tier_config]

    results: List[RunResult] = []
    for w in workloads:
        for p in policies:
            try:
                r = run_sim(
                    w,
                    p,
                    tier_specs,
                    tier_config_name=args.tier_config,
                    hbm_oversubscription=args.hbm_oversubscription,
                    attention_ema_alpha=args.ema_alpha,
                )
            except ImportError as exc:
                print(
                    f"[skip] {w.name} / {p}: {exc}",
                    file=sys.stderr,
                )
                continue
            results.append(r)
            print(
                f"[ok ] {w.name:>14s} / {p:>9s} "
                f"hbm_hit={r.hbm_hit_rate*100:5.1f}%  "
                f"slow_tier_B/tok={r.slow_tier_bytes_per_decode_token:>10,.0f}  "
                f"wall={r.wall_clock_seconds:5.2f}s",
                file=sys.stderr,
            )

    summary = summarize(results)
    summary_json = to_json(summary)
    report_md = markdown_table(results)

    if args.output_dir:
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "summary.json").write_text(summary_json + "\n")
        (out / "report.md").write_text(report_md)
        print(f"wrote {out / 'summary.json'} + {out / 'report.md'}")
    else:
        print(report_md)
        print(summary_json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
