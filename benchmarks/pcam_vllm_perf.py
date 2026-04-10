#!/usr/bin/env python3
"""
PCAM real-runtime throughput / latency harness (Phase 5).

Runs a real vLLM ``LLM.generate(prompts)`` twice against the same
model, the same prompts, and the same sampling parameters — once
with vLLM's default LRU evictor, once with PCAM installed as the
live eviction policy via ``benchmarks/vllm_active_bridge.py``. Reports
wall-clock throughput, per-prompt latency, and (where vLLM exposes it)
block-usage statistics so the two policies can be compared directly.

This is the first script in the PCAM roadmap that produces REAL
serving metrics. It is NOT replay-only and it is NOT shadow mode —
the PCAM run has PCAM's decisions actually driving which blocks get
reused inside vLLM's live block pool.

Honesty labels
--------------
- Output carries a banner that distinguishes real serving metrics
  from the Phase 3 replay numbers.
- The real run requires a CUDA-capable GPU and a working vLLM
  install; without either, the script fails clean with an
  actionable message rather than faking results.
- Active mode is known to add per-popleft_n overhead because the
  bridge walks the free list; the harness measures this directly
  and the report carries the overhead number alongside the
  throughput delta so reviewers see both.

Usage
-----

    # Both policies (default then PCAM), one prompt file, JSON output
    python benchmarks/pcam_vllm_perf.py \\
        --model facebook/opt-125m \\
        --prompts-file benchmarks/traces/phase5_prompts.json \\
        --max-tokens 32 \\
        --policy both \\
        --json /tmp/pcam_phase5_perf.json

    # PCAM only (for a smoke test after active-mode bridge changes)
    python benchmarks/pcam_vllm_perf.py \\
        --model facebook/opt-125m \\
        --prompt "Hello" --prompt "World" \\
        --policy pcam

If ``vllm`` is not installed, the script exits with rc=2 and an
install hint. If the installed vllm does not expose the v1 core
block_pool architecture, the script exits with rc=2 and the exact
missing-module name via ``VLLMVersionSupportError``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from simulator.pcam import PCAMConfig  # noqa: E402
from simulator.pcam._report import emit_json, format_table, section_header  # noqa: E402
from benchmarks.vllm_bridge import (  # noqa: E402
    VLLMBridgeUnavailable,
    ensure_vllm_available,
)
from benchmarks.vllm_active_bridge import (  # noqa: E402
    ActiveModeInstallation,
    VLLMVersionSupportError,
    check_vllm_active_mode_supported,
    install_pcam_active_evictor,
    uninstall_pcam_active_evictor,
)


__all__ = [
    "PolicyRunResult",
    "run_policy",
    "render_report",
    "run",
    "main",
]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class PolicyRunResult:
    """Per-policy serving metrics for one vLLM.generate() call."""

    policy: str  # "default" or "pcam"
    model: str
    num_prompts: int
    total_prompt_tokens: int
    total_completion_tokens: int
    wall_time_seconds: float
    tokens_per_second: float
    per_prompt_latency_seconds: List[float] = field(default_factory=list)
    active_mode_stats: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        """Flat metric dict for JSON / report output."""
        latencies = self.per_prompt_latency_seconds
        p50 = statistics.median(latencies) if latencies else 0.0
        p95 = _percentile(latencies, 0.95) if latencies else 0.0
        mean = statistics.mean(latencies) if latencies else 0.0
        return {
            "policy": self.policy,
            "model": self.model,
            "num_prompts": self.num_prompts,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "wall_time_seconds": round(self.wall_time_seconds, 4),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "per_prompt_latency_mean_seconds": round(mean, 4),
            "per_prompt_latency_p50_seconds": round(p50, 4),
            "per_prompt_latency_p95_seconds": round(p95, 4),
            "active_mode_stats": dict(self.active_mode_stats),
        }


def _percentile(values: List[float], q: float) -> float:
    """Simple nearest-rank percentile. q in [0, 1]."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


# ---------------------------------------------------------------------------
# BlockPool reach
# ---------------------------------------------------------------------------


def _find_block_pool(llm: Any) -> Any:
    """
    Locate the ``BlockPool`` on a live ``vllm.LLM`` instance.

    vLLM's internal attribute path to the block pool has changed
    across the v1 core releases. This helper tries the known paths
    in order and raises ``VLLMVersionSupportError`` if none work.
    """
    errors: List[str] = []
    candidate_paths = [
        # Typical v1 core path: LLM → LLMEngine → KVCacheManager → BlockPool
        ("llm_engine", "kv_cache_manager", "block_pool"),
        # Alternative path used by some 0.7.x / 0.8.x builds
        ("llm_engine", "scheduler", "kv_cache_manager", "block_pool"),
        # Some builds expose the pool on the engine directly
        ("llm_engine", "block_pool"),
    ]
    for path in candidate_paths:
        try:
            node = llm
            for attr in path:
                node = getattr(node, attr)
            return node
        except AttributeError as exc:
            errors.append(f"  path {' → '.join(path)}: {exc}")
    raise VLLMVersionSupportError(
        "Could not locate BlockPool on the vLLM LLM instance. Tried:\n"
        + "\n".join(errors)
        + "\nThe v1 core attribute path may have changed in this vLLM "
        "release. Inspect the engine manually and update _find_block_pool."
    )


# ---------------------------------------------------------------------------
# Single-policy run
# ---------------------------------------------------------------------------


def run_policy(
    *,
    policy: str,
    model: str,
    prompts: List[str],
    max_tokens: int,
    max_blocks: int,
    sink_tokens: int,
    dtype: Optional[str] = None,
    trust_remote_code: bool = False,
) -> PolicyRunResult:
    """
    Build a vllm.LLM, optionally install the PCAM active-mode
    evictor, run generate() on the prompts, and return a timed
    ``PolicyRunResult``.
    """
    if policy not in ("default", "pcam"):
        raise ValueError(f"unknown policy: {policy!r}")

    ensure_vllm_available()
    if policy == "pcam":
        check_vllm_active_mode_supported()

    from vllm import LLM, SamplingParams  # pragma: no cover  (env-dependent)

    llm_kwargs: Dict[str, Any] = {"model": model}
    if dtype is not None:
        llm_kwargs["dtype"] = dtype
    if trust_remote_code:
        llm_kwargs["trust_remote_code"] = True

    llm = LLM(**llm_kwargs)  # pragma: no cover

    installation: Optional[ActiveModeInstallation] = None
    if policy == "pcam":  # pragma: no cover  (env-dependent)
        block_pool = _find_block_pool(llm)
        installation = install_pcam_active_evictor(
            block_pool=block_pool,
            config=PCAMConfig(
                max_blocks=max_blocks,
                sink_tokens=sink_tokens,
            ),
        )

    sampling_params = SamplingParams(max_tokens=max_tokens)  # pragma: no cover

    # Per-prompt latencies: measure each generate() call individually.
    per_prompt_latency: List[float] = []
    total_prompt_tokens = 0
    total_completion_tokens = 0
    wall_start = time.perf_counter()

    for prompt in prompts:  # pragma: no cover
        prompt_start = time.perf_counter()
        outputs = llm.generate([prompt], sampling_params)
        per_prompt_latency.append(time.perf_counter() - prompt_start)
        for output in outputs:
            total_prompt_tokens += len(output.prompt_token_ids)
            total_completion_tokens += len(output.outputs[0].token_ids)

    wall_time = time.perf_counter() - wall_start

    active_stats: Dict[str, Any] = {}
    if installation is not None:  # pragma: no cover
        active_stats = dict(installation.stats)
        uninstall_pcam_active_evictor(installation)

    tokens_generated = total_completion_tokens
    tps = tokens_generated / wall_time if wall_time > 0 else 0.0

    return PolicyRunResult(
        policy=policy,
        model=model,
        num_prompts=len(prompts),
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        wall_time_seconds=wall_time,
        tokens_per_second=tps,
        per_prompt_latency_seconds=per_prompt_latency,
        active_mode_stats=active_stats,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


_DISCLAIMER = (
    "NOTE: REAL SERVING METRICS from vllm.LLM.generate(). Throughput "
    "and latency reflect actual model execution on the host GPU, not "
    "replay or shadow-mode. The PCAM policy row reports numbers "
    "from a run where PCAM's select_victims decisions actually drove "
    "vLLM's block eviction via the Phase 5 active-mode bridge."
)


def render_report(results: List[PolicyRunResult]) -> str:
    lines: List[str] = []
    lines.append(section_header("PCAM vLLM Perf — Real Serving Metrics"))
    lines.append(_DISCLAIMER)

    headers = [
        "policy",
        "tps",
        "wall_sec",
        "mean_ms",
        "p50_ms",
        "p95_ms",
        "prompt_toks",
        "completion_toks",
    ]
    rows: List[List[Any]] = []
    for r in results:
        summary = r.summary()
        rows.append([
            summary["policy"],
            summary["tokens_per_second"],
            summary["wall_time_seconds"],
            round(summary["per_prompt_latency_mean_seconds"] * 1000, 2),
            round(summary["per_prompt_latency_p50_seconds"] * 1000, 2),
            round(summary["per_prompt_latency_p95_seconds"] * 1000, 2),
            summary["total_prompt_tokens"],
            summary["total_completion_tokens"],
        ])
    lines.append("")
    lines.append(format_table(rows, headers))

    # If both policies ran, show the delta explicitly so a reader
    # doesn't have to do the subtraction by hand.
    if len(results) == 2:
        policies = {r.policy: r for r in results}
        if "default" in policies and "pcam" in policies:
            default_tps = policies["default"].tokens_per_second
            pcam_tps = policies["pcam"].tokens_per_second
            if default_tps > 0:
                delta_pct = ((pcam_tps - default_tps) / default_tps) * 100.0
                sign = "+" if delta_pct >= 0 else ""
                lines.append(
                    f"\nPCAM throughput delta vs default LRU: "
                    f"{sign}{delta_pct:.2f}%"
                )

    # Active-mode stats if PCAM ran
    for r in results:
        if r.policy == "pcam" and r.active_mode_stats:
            lines.append("\nActive-mode bridge stats (pcam run)")
            stats_rows = [(k, v) for k, v in r.active_mode_stats.items()]
            lines.append(format_table(stats_rows, ["metric", "value"]))

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_prompts(
    prompts_arg: Optional[List[str]],
    prompts_file: Optional[Path],
) -> List[str]:
    if prompts_file is not None:
        data = json.loads(prompts_file.read_text())
        if not isinstance(data, list):
            raise TypeError(
                f"--prompts-file must contain a JSON list of strings, "
                f"got {type(data).__name__}"
            )
        return [str(x) for x in data]
    if prompts_arg:
        return list(prompts_arg)
    return [
        "Explain PCAM in one sentence.",
        "Name three cache eviction algorithms.",
        "Summarize paged attention in one sentence.",
    ]


def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="PCAM real-runtime throughput / latency harness "
                    "against vLLM with the Phase 5 active-mode bridge.",
    )
    p.add_argument("--model", type=str, default="facebook/opt-125m",
                   help="vllm.LLM model name (default: facebook/opt-125m).")
    p.add_argument("--prompt", action="append", default=None,
                   help="Prompt to benchmark. Repeat for multiple prompts. "
                        "Mutually exclusive with --prompts-file.")
    p.add_argument("--prompts-file", type=Path, default=None,
                   help="Path to a JSON file containing a list of prompt strings.")
    p.add_argument("--max-tokens", type=int, default=64,
                   help="Max completion tokens per prompt (default: 64).")
    p.add_argument("--max-blocks", type=int, default=4096,
                   help="PCAMConfig max_blocks (default: 4096).")
    p.add_argument("--sink-tokens", type=int, default=4,
                   help="PCAMConfig sink_tokens (default: 4).")
    p.add_argument("--policy", type=str, default="both",
                   choices=("default", "pcam", "both"),
                   help="Which policy to run (default: both).")
    p.add_argument("--dtype", type=str, default=None,
                   help="Optional vllm dtype override.")
    p.add_argument("--trust-remote-code", action="store_true",
                   help="Pass trust_remote_code=True to vllm.LLM.")
    p.add_argument("--json", type=Path, default=None,
                   help="If provided, write the full per-policy results "
                        "to this JSON file.")
    p.add_argument("--quiet", action="store_true",
                   help="Suppress the human-readable report.")
    return p


def run(argv: Optional[List[str]] = None) -> int:
    args = build_argparser().parse_args(argv)

    try:
        prompts = _load_prompts(args.prompt, args.prompts_file)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not prompts:
        print("ERROR: no prompts provided.", file=sys.stderr)
        return 2

    policies_to_run: List[str] = (
        ["default", "pcam"] if args.policy == "both" else [args.policy]
    )

    results: List[PolicyRunResult] = []
    for policy in policies_to_run:
        try:
            result = run_policy(
                policy=policy,
                model=args.model,
                prompts=prompts,
                max_tokens=args.max_tokens,
                max_blocks=args.max_blocks,
                sink_tokens=args.sink_tokens,
                dtype=args.dtype,
                trust_remote_code=args.trust_remote_code,
            )
        except (VLLMBridgeUnavailable, VLLMVersionSupportError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        results.append(result)

    if not args.quiet:
        print(render_report(results))

    if args.json is not None:
        emit_json(
            {
                "config": {
                    "model": args.model,
                    "max_tokens": args.max_tokens,
                    "max_blocks": args.max_blocks,
                    "sink_tokens": args.sink_tokens,
                    "num_prompts": len(prompts),
                },
                "results": [r.summary() for r in results],
            },
            args.json,
        )

    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":  # pragma: no cover
    main()
