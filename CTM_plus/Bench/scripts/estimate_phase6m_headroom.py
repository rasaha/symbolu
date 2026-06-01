"""Phase 6M — Tier-0 throughput-headroom calculator (CPU-only, no GPU/ncu).

Estimates the BEST-CASE int4_protected decode-throughput recovery if some
fraction of the measured int4 tax (paged gather + eager KV orchestration, and/or
the attention-kernel overhead) were removed — WITHOUT running anything on a GPU
and WITHOUT needing the ncu-locked profiling counters.

It is a back-of-envelope Amdahl's-law bound from the ALREADY-MEASURED 6D kernel
profile (Phase 6M.6, A100, this session). It does NOT predict what a real kernel
rewrite will achieve — it bounds the ceiling so you can decide whether the
engineering (Test 3 / 6F) is worth funding before spending a profiling pod.

Model (honest + simple):
  int4 decode GPU time is split into:
    - shared work (GEMMs etc.) — identical to bf16, NOT removable
    - gather/orchestration tax  — the eager paged-gather + slot bookkeeping
    - attention-kernel tax       — int4 decode attention beyond bf16's
    - other int4-only residue
  If we remove fraction f_gather of the gather tax and f_attn of the attention
  tax, the new int4 GPU time shrinks, and the throughput ratio vs bf16 improves
  proportionally (decode is GPU-work-bound at saturation — Phase 6M.4).

  new_ratio = base_ratio * (int4_time / (int4_time - removed))

Defaults are the measured shares from PHASE_6M6 (A100, 2026-06-01):
  gather (index_elementwise) = 25.1% of int4 self-CUDA
  attention (flash_fwd+varlen+splitkv) = 21.0%
  base aggregate ratio at saturation (locked Phase 6L) = 0.22x

CAVEATS baked into the output:
  - This is an UPPER BOUND. Real fusion leaves residue; never reaches the bound.
  - int4 cannot reach bf16 parity (it reads packed KV + sidecars, dequants/token).
  - Removing the gather is the Test-3 engineering arm — not a config flip.
  - Closed tracks (int8-V, n_protect, sidecar diet) are NOT modeled — off-limits.

Usage:
  python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py            # measured defaults
  python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py \
      --base-ratio 0.22 --gather-share 0.251 --attn-share 0.210 \
      --remove-gather 0.7 --remove-attn 0.3
  python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py --from-csv \
      bench_out/phase6m6/A100_int4_captured_kernels.csv          # derive shares
  python CTM_plus/Bench/scripts/estimate_phase6m_headroom.py --selftest
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Measured defaults (PHASE_6M6, A100, this session). int4 self-CUDA total 131.3s.
DEFAULT_BASE_RATIO = 0.22          # locked Phase 6L aggregate at saturation
DEFAULT_GATHER_SHARE = 0.251       # index_elementwise (paged gather + orchestration)
DEFAULT_ATTN_SHARE = 0.210         # flash_fwd + varlen_fwd + splitkv
# The plan's stated realistic software ceiling, for cross-checking the estimate.
PLAN_CEILING_LO, PLAN_CEILING_HI = 0.27, 0.30

# Substrings to derive shares from a profiler CSV (--from-csv). Reuses the same
# name-matching idea as analyze_phase6f_acceptance.
GATHER_MATCH = ("index", "gather", "scatter", "sort", "unique", "nonzero",
                "bitwise_and")
GATHER_EXCLUDE = ("flash", "fwd_kernel", "fwd_kvcache", "attention", "gemm",
                  "cutlass", "addmm", "linear", "matmul")
ATTN_MATCH = ("flash_fwd", "fwd_kvcache", "varlen_fwd", "splitkv")


def _shares_from_csv(path: Path) -> Optional[Tuple[float, float]]:
    """Derive (gather_share, attn_share) of int4 self-CUDA from a profiler CSV."""
    import analyze_phase6d_profile as p6d
    rows = p6d._parse_nsys_csv(path)
    if not rows:
        return None
    total = sum(float(r["total_ns"]) for r in rows) or 0.0
    if total <= 0:
        return None

    def share(match, exclude=()):
        s = 0.0
        for r in rows:
            n = str(r["name"]).lower()
            if any(x in n for x in exclude):
                continue
            if any(x in n for x in match):
                s += float(r["total_ns"])
        return s / total

    return share(GATHER_MATCH, GATHER_EXCLUDE), share(ATTN_MATCH)


def estimate(base_ratio: float, gather_share: float, attn_share: float,
             remove_gather: float, remove_attn: float) -> Dict[str, float]:
    """Amdahl bound on the new throughput ratio.

    Treat int4 GPU time as 1.0; gather_share + attn_share are fractions of it.
    Removing remove_gather*gather_share + remove_attn*attn_share shrinks the
    time; throughput scales inversely.
    """
    removed = remove_gather * gather_share + remove_attn * attn_share
    removed = max(0.0, min(removed, 0.999))   # can't remove >100%
    speedup = 1.0 / (1.0 - removed)
    new_ratio = base_ratio * speedup
    return {
        "base_ratio": base_ratio,
        "gather_share": gather_share,
        "attn_share": attn_share,
        "remove_gather": remove_gather,
        "remove_attn": remove_attn,
        "fraction_removed": removed,
        "speedup": speedup,
        "new_ratio": new_ratio,
        "new_per_user_slowdown_x": (1.0 / new_ratio) if new_ratio > 0 else float("inf"),
    }


def _scenarios(base: float, g: float, a: float) -> List[Tuple[str, float, float]]:
    """(label, remove_gather, remove_attn) — bracketing cases."""
    return [
        ("no change (baseline)",                 0.0, 0.0),
        ("gather fully fused (attn untouched)",   1.0, 0.0),
        ("gather 2/3 fused (realistic 6F)",       0.667, 0.0),
        ("gather fully + attn 1/3",               1.0, 0.333),
        ("THEORETICAL MAX (both fully gone)",     1.0, 1.0),
    ]


def build_report(base: float, g: float, a: float, source: str) -> str:
    L: List[str] = []
    L.append("=" * 78)
    L.append("Phase 6M — Tier-0 throughput-headroom estimate (Amdahl bound, CPU-only)")
    L.append("=" * 78)
    L.append(f"inputs ({source}):")
    L.append(f"  base aggregate ratio (int4/bf16) : {base:.3f}x")
    L.append(f"  gather/orchestration share        : {g*100:.1f}% of int4 GPU time")
    L.append(f"  attention-kernel share            : {a*100:.1f}% of int4 GPU time")
    L.append("")
    L.append(f"{'scenario':<38} | {'removed':>8} | {'ratio':>7} | {'slower/user':>11}")
    L.append("-" * 76)
    for label, rg, ra in _scenarios(base, g, a):
        e = estimate(base, g, a, rg, ra)
        L.append(f"{label:<38} | {e['fraction_removed']*100:>6.1f}% | "
                 f"{e['new_ratio']:>6.3f}x | {e['new_per_user_slowdown_x']:>9.1f}x")
    L.append("-" * 76)
    L.append("")
    # Cross-check the realistic case against the plan's stated ceiling.
    realistic = estimate(base, g, a, 0.667, 0.0)["new_ratio"]
    L.append(f"Realistic (gather 2/3 fused, attn untouched): ~{realistic:.2f}x")
    L.append(f"Plan's stated software ceiling:               {PLAN_CEILING_LO:.2f}-"
             f"{PLAN_CEILING_HI:.2f}x")
    inside = PLAN_CEILING_LO - 0.03 <= realistic <= PLAN_CEILING_HI + 0.05
    L.append(f"  -> {'CONSISTENT with the plan ceiling.' if inside else 'OUTSIDE the plan ceiling — re-check inputs.'}")
    L.append("")
    L.append("HONEST CAVEATS (read before quoting any number):")
    L.append("  * UPPER BOUND. Real fusion leaves residue + adds its own reads;")
    L.append("    the achieved ratio will be BELOW these figures.")
    L.append("  * int4 CANNOT reach bf16 parity (1.0x) — it reads packed KV +")
    L.append("    scale + xmin + protected and dequants every token. Irreducible.")
    L.append("  * Removing the gather IS the Test-3 (6F) engineering arm — code,")
    L.append("    not a config flip. This estimate only sizes the prize.")
    L.append("  * Closed tracks (int8-V, n_protect, sidecar diet) NOT modeled —")
    L.append("    off-limits (6G.2 RED). Density + quality remain the product.")
    L.append("  * Assumes GPU-work-bound at saturation (Phase 6M.4); valid at the")
    L.append("    real operating point, not at low-B short-context.")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
def _selftest() -> int:
    # 1. No removal -> ratio unchanged.
    e = estimate(0.22, 0.25, 0.21, 0.0, 0.0)
    assert abs(e["new_ratio"] - 0.22) < 1e-9, e
    print("  no removal -> unchanged: PASS")

    # 2. Remove all gather (25%) -> speedup 1/0.75 = 1.333 -> 0.22*1.333=0.293.
    e = estimate(0.22, 0.25, 0.21, 1.0, 0.0)
    assert abs(e["speedup"] - 1.0 / 0.75) < 1e-9, e["speedup"]
    assert abs(e["new_ratio"] - 0.22 * (1.0 / 0.75)) < 1e-9, e["new_ratio"]
    print(f"  remove all gather -> {e['new_ratio']:.3f}x: PASS")

    # 3. Realistic (2/3 gather) lands in the plan's ~0.27-0.30 ceiling band.
    e = estimate(0.22, 0.251, 0.21, 0.667, 0.0)
    assert 0.24 <= e["new_ratio"] <= 0.30, e["new_ratio"]
    print(f"  realistic 2/3 gather -> {e['new_ratio']:.3f}x (in band): PASS")

    # 4. Theoretical max < parity (cannot hit 1.0 from 0.22 by removing <50%).
    e = estimate(0.22, 0.25, 0.21, 1.0, 1.0)
    assert e["new_ratio"] < 1.0, e["new_ratio"]
    print(f"  theoretical max -> {e['new_ratio']:.3f}x (< parity): PASS")

    # 5. Removal capped at 100% (no divide-by-zero / negative time).
    e = estimate(0.22, 0.9, 0.9, 1.0, 1.0)
    assert e["fraction_removed"] <= 0.999 and e["new_ratio"] > e["base_ratio"]
    print("  removal capped, no blowup: PASS")

    # 6. Monotonic: more removal -> higher ratio.
    r1 = estimate(0.22, 0.25, 0.21, 0.3, 0.0)["new_ratio"]
    r2 = estimate(0.22, 0.25, 0.21, 0.6, 0.0)["new_ratio"]
    assert r2 > r1, (r1, r2)
    print("  monotonic in removal: PASS")

    # 7. CSV share derivation on a synthetic profiler CSV.
    import tempfile, csv as _csv
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "k.csv"
        rows = [("ampere_gemm", 400.0), ("aten::index_elementwise", 250.0),
                ("aten::sort", 50.0), ("flash_fwd_splitkv", 200.0),
                ("_vllm_fa2_C::varlen_fwd", 100.0)]
        tot = sum(r[1] for r in rows)
        with p.open("w", newline="") as f:
            w = _csv.DictWriter(f, fieldnames=["Time(%)", "Total Time",
                "Instances", "Avg", "Min", "Max", "StdDev", "Name"])
            w.writeheader()
            for n, us in rows:
                w.writerow({"Time(%)": f"{us/tot*100:.1f}", "Total Time": str(int(us*1000)),
                            "Instances": "1", "Avg": "0", "Min": "0", "Max": "0",
                            "StdDev": "0", "Name": n})
        sh = _shares_from_csv(p)
        assert sh is not None
        gshare, ashare = sh
        # gather = (250+50)/1000 = 0.30 ; attn = (200+100)/1000 = 0.30
        assert abs(gshare - 0.30) < 1e-6, gshare
        assert abs(ashare - 0.30) < 1e-6, ashare
        print(f"  CSV share derivation g={gshare:.2f} a={ashare:.2f}: PASS")

    print("\nself-test: 7/7 PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Phase 6M Tier-0 headroom estimator")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--base-ratio", type=float, default=DEFAULT_BASE_RATIO,
                   help="int4/bf16 aggregate throughput ratio at the operating "
                        "point (default 0.22 = locked Phase 6L saturation)")
    p.add_argument("--gather-share", type=float, default=DEFAULT_GATHER_SHARE)
    p.add_argument("--attn-share", type=float, default=DEFAULT_ATTN_SHARE)
    p.add_argument("--remove-gather", type=float, default=None,
                   help="if set, print a single scenario removing this fraction "
                        "of the gather tax (0-1)")
    p.add_argument("--remove-attn", type=float, default=0.0)
    p.add_argument("--from-csv", type=Path, default=None,
                   help="derive gather/attn shares from a profiler CSV "
                        "(bench_phase6_d_profile_gpu.py --torch-profile-csv)")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()

    g, a, source = args.gather_share, args.attn_share, "measured defaults (PHASE_6M6)"
    if args.from_csv:
        if not args.from_csv.exists():
            p.error(f"CSV not found: {args.from_csv}")
        sh = _shares_from_csv(args.from_csv)
        if sh is None:
            p.error(f"could not derive shares from {args.from_csv}")
        g, a = sh
        source = f"derived from {args.from_csv.name}"

    if args.remove_gather is not None:
        e = estimate(args.base_ratio, g, a, args.remove_gather, args.remove_attn)
        print(f"remove_gather={args.remove_gather:.2f} remove_attn={args.remove_attn:.2f} "
              f"-> {e['new_ratio']:.3f}x agg ({e['new_per_user_slowdown_x']:.1f}x slower/user); "
              f"UPPER BOUND, < bf16 parity by construction.")
        return 0

    report = build_report(args.base_ratio, g, a, source)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        print(f"Report written to: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
