"""Compare Phase 4 v5 (post-three-improvements) against Phase 2 v3
baseline. Used by the PHASE4_GPU_FINDINGS.md decision-tree analysis.

Usage:
    python -m ctm_bench.scripts.read_phase4_v5
    python -m ctm_bench.scripts.read_phase4_v5 \\
        --phase4-dir bench_out/4cell_phase4_v5 \\
        --phase2-dir bench_out/4cell_phase2_v3
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _show(label: str, r: dict) -> None:
    print(f"\n=== {label} ===")
    print(f"  tokens/sec:                  {r['tokens_per_second']:.2f}")
    print(
        f"  requests completed:          "
        f"{r['n_requests_completed']}/{r['n_requests_admitted']}"
    )
    print(f"  decode tokens:               {r['n_decode_tokens']}")
    print(f"  swap_out blocks:             {r['swap_out_blocks']}")
    print(f"  swap_in  blocks:             {r.get('swap_in_blocks', 0)}")
    so = max(r.get("swap_out_blocks", 0), 1)
    si = r.get("swap_in_blocks", 0)
    print(f"  swap_in / swap_out:          {si / so:.3f}  (lower = better cache decisions)")
    print(f"  evict_call_count:            {r['evict_call_count']}")
    print(f"  evict_p99 (us):              {r['evict_p99_microseconds']:.1f}")
    counters = (
        "phase4_blocks_captured_with_pre_rope_keys",
        "phase4_window_pruning_invocations",
        "phase4_set_pre_rope_keys_calls",
        "phase4_set_pre_rope_keys_speculative",
        "phase4_capture_subsample_skips",
        "phase4_side_channel_pre_hook_calls",
        "phase4_rotary_pre_hook_calls",
        "phase4_capture_attempts",
        "phase4_trig_blend_evict_calls",
        "phase4_trig_changed_pick",
        "phase4_trig_blend_skips",
        "phase4_trig_score_computes",
        "phase4_trig_score_lookups",
        "phase4_trig_score_cache_misses",
        "phase4_trig_score_compute_exceptions",
    )
    for k in counters:
        if k in r:
            print(f"  {k}: {r[k]}")
    # Derived ratio: of all evict() calls that ran the trig blend,
    # how often did the trig signal actually flip the pick?
    bec = r.get("phase4_trig_blend_evict_calls", 0)
    cp = r.get("phase4_trig_changed_pick", 0)
    if bec > 0:
        print(
            f"  trig_changed_pick / blend_calls: "
            f"{cp / bec * 100:.1f}% (= how often trig overrode base ordering)"
        )
    lookups = r.get("phase4_trig_score_lookups", 0)
    misses = r.get("phase4_trig_score_cache_misses", 0)
    if lookups > 0:
        hit_rate = (lookups - misses) / lookups * 100
        print(
            f"  trig_score cache hit rate: "
            f"{hit_rate:.1f}% ({lookups - misses}/{lookups} lookups, "
            f"{misses} misses) -- I1 optimization"
        )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase4-dir", default="bench_out/4cell_phase4_v5",
    )
    parser.add_argument(
        "--phase2-dir", default="bench_out/4cell_phase2_v3",
    )
    args = parser.parse_args(argv)

    p4_path = Path(args.phase4_dir) / "streaming_summary.json"
    p2_path = Path(args.phase2_dir) / "streaming_summary.json"

    if not p4_path.exists():
        print(f"ERROR: {p4_path} not found", file=sys.stderr)
        return 2
    p4 = json.loads(p4_path.read_text())
    p2 = json.loads(p2_path.read_text()) if p2_path.exists() else None

    if p2:
        _show("Phase 2 (baseline)", p2)
    _show("Phase 4 (three improvements)", p4)

    if p2:
        print("\n=== per-decode-token rates (regime-normalized) ===")

        def rate(r, k):
            return r[k] / max(r["n_decode_tokens"], 1)

        p2_sr = rate(p2, "swap_out_blocks")
        p4_sr = rate(p4, "swap_out_blocks")
        delta_sr = (p4_sr - p2_sr) / max(p2_sr, 1e-9) * 100
        print(
            f"  swap_out/token   P2={p2_sr:.4f}  P4={p4_sr:.4f}  "
            f"delta={delta_sr:+.1f}%"
        )

        p2_ec = rate(p2, "evict_call_count")
        p4_ec = rate(p4, "evict_call_count")
        delta_ec = (p4_ec - p2_ec) / max(p2_ec, 1e-9) * 100
        print(
            f"  evicts/token     P2={p2_ec:.4f}  P4={p4_ec:.4f}  "
            f"delta={delta_ec:+.1f}%"
        )

        tp = (
            (p4["tokens_per_second"] - p2["tokens_per_second"])
            / max(p2["tokens_per_second"], 1e-9)
            * 100
        )
        print(f"  tokens/sec delta: P4 vs P2 = {tp:+.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
