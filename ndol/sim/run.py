"""Driver: `python -m ndol.sim.run [--mqsim DIR]`.

Generates baseline (full-attention) and NDOL (read-skip) KV traces, replays
both through MQSim, and reports the MEASURED speedup — device latency from a
validated SSD simulator, not the analytical model.
"""
from __future__ import annotations

import argparse
import sys
import tempfile

from .mqsim import kv_read_skip_traces, run_mqsim


def main() -> int:
    ap = argparse.ArgumentParser(description="NDOL × MQSim measured read-skip benchmark")
    ap.add_argument("--mqsim", default=None, help="MQSim dir (default $NDOL_MQSIM_DIR or /tmp/MQSim)")
    ap.add_argument("--blocks", type=int, default=256)
    ap.add_argument("--steps", type=int, default=32)
    ap.add_argument("--retained", type=int, default=32)
    ap.add_argument("--out", default=None, help="trace output dir (default: temp)")
    args = ap.parse_args()

    out_dir = args.out or tempfile.mkdtemp(prefix="ndol_mqsim_")
    print(f"Generating KV traces in {out_dir} "
          f"(blocks={args.blocks}, steps={args.steps}, retained={args.retained}) ...")
    t = kv_read_skip_traces(out_dir, n_blocks=args.blocks, n_steps=args.steps, retained=args.retained)
    print(f"  baseline (full attention): {t['baseline_requests']:>7} requests")
    print(f"  ndol     (read-skip)     : {t['ndol_requests']:>7} requests "
          f"({t['baseline_requests'] / max(1, t['ndol_requests']):.1f}x fewer)\n")

    try:
        print("Running MQSim on baseline (~20–60s) ...", flush=True)
        base = run_mqsim(t["baseline_trace"], mqsim_dir=args.mqsim)
        print("Running MQSim on ndol (~20–60s) ...", flush=True)
        ndol = run_mqsim(t["ndol_trace"], mqsim_dir=args.mqsim)
    except FileNotFoundError as e:
        print(f"\n[skip] {e}", file=sys.stderr)
        return 2

    print("\n=== MQSim-measured (device latency from validated SSD simulator) ===")
    print(f"{'':<10}{'requests':>10}{'dev_resp_us':>14}{'e2e_delay_us':>14}")
    print("-" * 48)
    print(f"{'baseline':<10}{base.request_count:>10}{base.device_response_time_us:>14.1f}"
          f"{base.end_to_end_delay_us:>14.1f}")
    print(f"{'ndol':<10}{ndol.request_count:>10}{ndol.device_response_time_us:>14.1f}"
          f"{ndol.end_to_end_delay_us:>14.1f}")

    if ndol.end_to_end_delay_us > 0:
        sp_lat = base.end_to_end_delay_us / ndol.end_to_end_delay_us
        sp_work = base.request_count / max(1, ndol.request_count)
        print(f"\nMeasured per-request latency ratio : {sp_lat:.2f}x")
        print(f"Request-volume (work) reduction    : {sp_work:.2f}x")
        print("(Per-request latency reflects queue contention; volume reduction is the "
              "read-skip A_BW. Total device-time win ≈ their product.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
