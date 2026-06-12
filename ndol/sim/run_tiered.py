"""W3 experiment driver: `python -m ndol.sim.run_tiered [--mqsim DIR]`.

Measures protect-mask tiering (design doc §9.3 W3) with MQSim. MQSim models one
flash technology per device, so we run each tier on its own t_R-configured
device and compose the result — the physical claim being that the SLC and QLC
tiers are independent regions. This is an HONEST hybrid: MQSim measures each
tier's latency; we volume-weight them. We compare:

  uniform   — all reads on a TLC device (no tiering)
  tiered    — protected/hot reads on SLC, bulk/cold reads on QLC

and report both the latency outcome and the (separate) density rationale.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile

from .mqsim import TIER_T_R_US, make_tier_config, run_mqsim, tiered_kv_traces


def main() -> int:
    ap = argparse.ArgumentParser(description="NDOL × MQSim W3 protect-mask tiering experiment")
    ap.add_argument("--mqsim", default=None)
    ap.add_argument("--protected", type=int, default=8, help="hot/protected blocks (re-read each step)")
    ap.add_argument("--bulk-window", type=int, default=24, help="cold/bulk blocks read per step")
    ap.add_argument("--steps", type=int, default=32)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    mqsim_dir = args.mqsim or os.environ.get("NDOL_MQSIM_DIR", "/tmp/MQSim")
    base_cfg = os.path.join(mqsim_dir, "ssdconfig.xml")
    out_dir = args.out or tempfile.mkdtemp(prefix="ndol_tier_")

    print(f"Generating tiered KV traces in {out_dir} "
          f"(protected={args.protected} hot, bulk_window={args.bulk_window}, steps={args.steps}) ...")
    t = tiered_kv_traces(out_dir, n_protected=args.protected,
                         n_bulk_window=args.bulk_window, n_steps=args.steps)
    print(f"  uniform : {t['uniform_requests']:>6} reads (protected+bulk, → TLC)")
    print(f"  SLC tier: {t['slc_requests']:>6} reads (protected/hot)")
    print(f"  QLC tier: {t['qlc_requests']:>6} reads (bulk/cold)\n")

    if not os.path.exists(os.path.join(mqsim_dir, "MQSim")):
        print(f"[skip] MQSim binary not found in {mqsim_dir}", file=sys.stderr)
        return 2

    cfg = {tier: make_tier_config(base_cfg, os.path.join(out_dir, f"ssd_{tier}.xml"), t_r)
           for tier, t_r in TIER_T_R_US.items()}

    print("Running MQSim per tier ...")
    uni = run_mqsim(t["uniform_trace"], mqsim_dir=mqsim_dir, ssdconfig=cfg["TLC"])
    slc = run_mqsim(t["tier_slc_trace"], mqsim_dir=mqsim_dir, ssdconfig=cfg["SLC"])
    qlc = run_mqsim(t["tier_qlc_trace"], mqsim_dir=mqsim_dir, ssdconfig=cfg["QLC"])

    # Volume-weighted tiered latency (tiers are independent parallel regions).
    n_slc, n_qlc = slc.read_request_count, qlc.read_request_count
    tiered_avg = (n_slc * slc.device_response_time_us + n_qlc * qlc.device_response_time_us) / max(1, n_slc + n_qlc)

    print("\n=== MQSim-measured (device response time, µs) ===")
    print(f"  uniform (TLC, all reads)     : {uni.device_response_time_us:>9.1f}  over {uni.read_request_count} reads")
    print(f"  tier SLC (protected/hot)     : {slc.device_response_time_us:>9.1f}  over {n_slc} reads")
    print(f"  tier QLC (bulk/cold)         : {qlc.device_response_time_us:>9.1f}  over {n_qlc} reads")
    print(f"  tiered (volume-weighted)     : {tiered_avg:>9.1f}")

    if tiered_avg > 0:
        ratio = uni.device_response_time_us / tiered_avg
        verdict = "tiering WINS on latency" if ratio > 1.05 else (
            "tiering ~neutral on latency" if ratio > 0.95 else "tiering LOSES on latency")
        print(f"\n  uniform / tiered latency ratio : {ratio:.2f}x  → {verdict}")
    print("\nNote: even when latency is neutral/negative, protect-mask tiering is a "
          "DENSITY play — bulk lives in dense QLC while protected stays high-fidelity. "
          "That capacity win (int4_protected's thesis) is orthogonal to this latency measurement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
