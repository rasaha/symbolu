"""Phase 6F — acceptance analyzer for the read-path kernel fusion (Test 3 prep).

Test 3 of `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md` is the multi-week CUDA
work that fuses the paged gather + sidecar read + protected-K splice INTO the
int4 attention kernel. **This script does NOT implement that kernel** — it is the
CPU-side ACCEPTANCE check that the (future) experimental kernel, gated behind
`PHASE6F_FUSED_READ=1`, actually killed the gather/copy pass.

It diffs TWO per-kernel profiler CSVs from `bench_phase6_d_profile_gpu.py
--torch-profile-csv` — one with the flag OFF (baseline) and one with it ON
(experimental) — and answers:

  * Did the **gather/copy** self-CUDA share drop to **≤ 1/3** of its pre-6F
    share? (the plan's acceptance metric for the ~19.5% gather/copy pass)
  * What is the total-kernel-time delta (a proxy for the agg-tps move toward
    the ~0.27–0.30× ceiling)?

The gather/copy pass is identified by kernel-name substrings (the eager paged
gather + sidecar reads the attribution doc cites: `aten::index` /
`index_elementwise` / `index_put` / `gather` / `scatter` + copy/contiguous),
NOT by the Phase 6D bucket map — that map sends some of these names to "other",
so matching by name is the robust choice here.

Acceptance is GREEN only if the gather/copy share collapsed AND total time did
not regress. Correctness (byte-eq / COLLAPSE=0 / needle / token-agreement) is a
SEPARATE, non-negotiable gate — see phase6f_correctness_oracle.sh.

Usage (CPU, anywhere — after the GPU A/B run):
    python CTM_plus/Bench/scripts/analyze_phase6f_acceptance.py \
        --before bench_out/phase6f/int4_flagoff_kernels.csv \
        --after  bench_out/phase6f/int4_flagon_kernels.csv \
        --out PHASE_6F_acceptance_report.txt

Self-test (CPU-only):
    python CTM_plus/Bench/scripts/analyze_phase6f_acceptance.py --selftest
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Reuse the committed Phase 6D CSV parser (single source of truth for the CSV
# schema). We do our OWN name matching for the gather/copy pass below.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import analyze_phase6d_profile as p6d  # noqa: E402

# Kernel-name substrings (case-insensitive) that make up the gather/copy
# read-path pass 6F is killing. Per PHASE_6M_ATTRIBUTION_FINDINGS.md the ~19.5%
# pass is the eager paged gather (aten::index / index_elementwise / index_put)
# + scatter + copy/contiguous of the int4 KV + sidecars.
DEFAULT_GATHER_COPY = (
    "index", "gather", "scatter", "copy", "contiguous", "clone",
)
# Names to EXCLUDE even if they match above (avoid false positives, e.g. the
# fused attention kernel's own name, or RoPE which can contain "copy" in mangling).
DEFAULT_EXCLUDE = (
    "flash", "fwd_kernel", "fwd_kvcache", "attention", "gemm", "cutlass",
)

# Acceptance: the gather/copy share must drop to <= this fraction of baseline.
DEFAULT_ACCEPT_FRACTION = 1.0 / 3.0
# Allow a small total-time regression tolerance (profiler noise), as a fraction.
DEFAULT_REGRESS_TOL = 0.05


def _is_gather_copy(name: str, include: Tuple[str, ...],
                    exclude: Tuple[str, ...]) -> bool:
    n = name.lower()
    if any(x in n for x in exclude):
        return False
    return any(x in n for x in include)


def _gather_copy_share(rows: List[Dict[str, object]],
                       include: Tuple[str, ...],
                       exclude: Tuple[str, ...]) -> Tuple[float, float, float]:
    """Return (gather_copy_ns, total_ns, share_in_[0,1])."""
    total = sum(float(r["total_ns"]) for r in rows) or 0.0
    gc = sum(float(r["total_ns"]) for r in rows
             if _is_gather_copy(str(r["name"]), include, exclude))
    return gc, total, (gc / total if total else 0.0)


def analyze(before_csv: Path, after_csv: Path,
            include: Tuple[str, ...], exclude: Tuple[str, ...],
            accept_fraction: float, regress_tol: float) -> Dict[str, object]:
    if not Path(before_csv).exists():
        return {"error": f"file not found: {before_csv}"}
    if not Path(after_csv).exists():
        return {"error": f"file not found: {after_csv}"}
    before_rows = p6d._parse_nsys_csv(before_csv)
    after_rows = p6d._parse_nsys_csv(after_csv)
    if not before_rows:
        return {"error": f"no rows parsed from {before_csv}"}
    if not after_rows:
        return {"error": f"no rows parsed from {after_csv}"}

    gc_b, total_b, share_b = _gather_copy_share(before_rows, include, exclude)
    gc_a, total_a, share_a = _gather_copy_share(after_rows, include, exclude)

    # Acceptance 1: gather/copy share collapsed to <= accept_fraction of baseline.
    share_ok = (share_b > 0) and (share_a <= accept_fraction * share_b)
    # Acceptance 2: total kernel time did not regress (allowing tol).
    time_ratio = (total_a / total_b) if total_b else None
    time_ok = (time_ratio is not None) and (time_ratio <= 1.0 + regress_tol)

    accepted = bool(share_ok and time_ok)

    # Top gather/copy kernels after, for the report (what's left).
    after_gc = sorted(
        [r for r in after_rows if _is_gather_copy(str(r["name"]), include, exclude)],
        key=lambda r: -float(r["total_ns"]))[:8]
    return {
        "before_total_ms": total_b / 1e6,
        "after_total_ms": total_a / 1e6,
        "total_time_ratio": time_ratio,
        "gather_copy_share_before": share_b,
        "gather_copy_share_after": share_a,
        "gather_copy_ms_before": gc_b / 1e6,
        "gather_copy_ms_after": gc_a / 1e6,
        "accept_fraction": accept_fraction,
        "share_ok": share_ok,
        "time_ok": time_ok,
        "accepted": accepted,
        "after_gather_copy_kernels": [
            (str(r["name"]), float(r["total_ns"]) / 1e6) for r in after_gc],
    }


def build_report(a: Dict[str, object]) -> str:
    if "error" in a:
        return f"ERROR: {a['error']}\n"
    L: List[str] = []
    L.append("=" * 78)
    L.append("Phase 6F — read-path fusion ACCEPTANCE (gather/copy A/B)")
    L.append("=" * 78)
    L.append("")
    L.append(f"{'metric':<34} | {'before (off)':>13} | {'after (on)':>12}")
    L.append("-" * 66)
    L.append(f"{'total kernel time (ms)':<34} | {a['before_total_ms']:>13.2f} | "
             f"{a['after_total_ms']:>12.2f}")
    L.append(f"{'gather/copy time (ms)':<34} | {a['gather_copy_ms_before']:>13.2f} | "
             f"{a['gather_copy_ms_after']:>12.2f}")
    L.append(f"{'gather/copy self-CUDA share':<34} | "
             f"{a['gather_copy_share_before']*100:>12.1f}% | "
             f"{a['gather_copy_share_after']*100:>11.1f}%")
    tr = a["total_time_ratio"]
    L.append(f"{'total-time ratio (after/before)':<34} | "
             f"{'':>13} | {(f'{tr:.3f}x' if tr is not None else 'n/a'):>12}")
    L.append("")
    thresh = a["accept_fraction"] * a["gather_copy_share_before"]
    L.append(f"acceptance #1 (share <= 1/3 of baseline = "
             f"{thresh*100:.1f}%): {'PASS' if a['share_ok'] else 'FAIL'}")
    L.append(f"acceptance #2 (no total-time regression):    "
             f"{'PASS' if a['time_ok'] else 'FAIL'}")
    L.append("-" * 78)
    L.append(f"VERDICT: {'ACCEPTED' if a['accepted'] else 'NOT ACCEPTED'}")
    L.append("-" * 78)
    L.append("")
    L.append("NOTE: this is the PERFORMANCE acceptance only. Correctness "
             "(byte-eq + COLLAPSE=0 + hard-needle + token-agreement) is a "
             "SEPARATE, non-negotiable gate — run phase6f_correctness_oracle.sh.")
    L.append("A faster-but-wrong gather is a FAILURE, not a win.")
    if a["after_gather_copy_kernels"]:
        L.append("")
        L.append("Gather/copy kernels remaining after (on):")
        for name, ms in a["after_gather_copy_kernels"]:
            L.append(f"  {ms:>8.2f} ms  {name}")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
def _synth_csv(path: Path, rows: List[Tuple[str, float, int]]) -> None:
    """rows = [(kernel_name, total_us, instances)]; writes the profiler CSV
    schema bench_phase6_d_profile_gpu.py emits (Total Time in ns)."""
    import csv as _csv
    total_us = sum(r[1] for r in rows) or 1.0
    with path.open("w", newline="") as f:
        w = _csv.DictWriter(f, fieldnames=[
            "Time(%)", "Total Time", "Instances", "Avg", "Min", "Max",
            "StdDev", "Name"])
        w.writeheader()
        for name, us, inst in rows:
            w.writerow({
                "Time(%)": f"{us/total_us*100:.2f}",
                "Total Time": f"{int(us*1000)}",  # us -> ns
                "Instances": str(inst), "Avg": "0", "Min": "0", "Max": "0",
                "StdDev": "0", "Name": name})


def _selftest() -> int:
    import tempfile
    INC, EXC = DEFAULT_GATHER_COPY, DEFAULT_EXCLUDE
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # Baseline: big gather/copy pass (index + index_elementwise + copy = 30%).
        before = d / "before.csv"
        _synth_csv(before, [
            ("ampere_gemm_kernel", 600.0, 100),         # excluded (gemm)
            ("at::native::index_elementwise", 200.0, 5000),  # gather
            ("aten::copy_", 100.0, 4000),               # copy
            ("flash::fwd_kernel_int4", 100.0, 28),      # excluded (flash)
        ])
        gc_b, total_b, share_b = _gather_copy_share(
            p6d._parse_nsys_csv(before), INC, EXC)
        assert abs(share_b - 0.30) < 1e-6, share_b   # (200+100)/1000
        print(f"  baseline gather/copy share = {share_b*100:.0f}%: PASS")

        # After fusion: gather/copy folded into the kernel -> tiny.
        after = d / "after.csv"
        _synth_csv(after, [
            ("ampere_gemm_kernel", 600.0, 100),
            ("at::native::index_elementwise", 15.0, 200),
            ("aten::copy_", 5.0, 100),
            ("flash::fwd_kernel_int4", 180.0, 28),
        ])
        a = analyze(before, after, INC, EXC,
                    DEFAULT_ACCEPT_FRACTION, DEFAULT_REGRESS_TOL)
        assert "error" not in a, a
        assert a["gather_copy_share_after"] < 0.05, a["gather_copy_share_after"]
        assert a["share_ok"] and a["time_ok"] and a["accepted"], a
        print("  fusion collapses gather/copy -> ACCEPTED: PASS")

        # Not accepted: gather/copy barely moved.
        after2 = d / "after2.csv"
        _synth_csv(after2, [
            ("ampere_gemm_kernel", 600.0, 100),
            ("at::native::index_elementwise", 180.0, 4800),
            ("aten::copy_", 90.0, 3800),
            ("flash::fwd_kernel_int4", 110.0, 28),
        ])
        a2 = analyze(before, after2, INC, EXC,
                     DEFAULT_ACCEPT_FRACTION, DEFAULT_REGRESS_TOL)
        assert not a2["share_ok"] and not a2["accepted"]
        print("  gather/copy unchanged -> NOT ACCEPTED: PASS")

        # Not accepted: share collapsed BUT total time regressed.
        after3 = d / "after3.csv"
        _synth_csv(after3, [
            ("ampere_gemm_kernel", 600.0, 100),
            ("at::native::index_elementwise", 10.0, 200),
            ("aten::copy_", 5.0, 100),
            ("flash::fwd_kernel_int4", 900.0, 28),
        ])
        a3 = analyze(before, after3, INC, EXC,
                     DEFAULT_ACCEPT_FRACTION, DEFAULT_REGRESS_TOL)
        assert a3["share_ok"] and not a3["time_ok"] and not a3["accepted"]
        print("  share collapsed but time regressed -> NOT ACCEPTED: PASS")

        # Exclusion: a 'copy' substring inside the flash kernel must NOT count.
        assert not _is_gather_copy("flash_fwd_splitkv_copy_kernel", INC, EXC)
        assert _is_gather_copy("aten::index_put_", INC, EXC)
        print("  include/exclude name matching: PASS")

        # Missing input -> error, no crash.
        a4 = analyze(d / "nope.csv", after, INC, EXC,
                     DEFAULT_ACCEPT_FRACTION, DEFAULT_REGRESS_TOL)
        assert "error" in a4
        print("  missing input -> error (no crash): PASS")

        # Report renders both verdicts.
        assert "VERDICT: ACCEPTED" in build_report(a)
        assert "NOT ACCEPTED" in build_report(a2)
        print("  report renders both verdicts: PASS")

    print("\nself-test: 7/7 PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Phase 6F acceptance analyzer")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--before", type=Path,
                    help="profiler CSV with PHASE6F_FUSED_READ=0 (baseline)")
    ap.add_argument("--after", type=Path,
                    help="profiler CSV with PHASE6F_FUSED_READ=1 (experimental)")
    ap.add_argument("--match", default=",".join(DEFAULT_GATHER_COPY),
                    help="comma-separated kernel-name substrings for the "
                         "gather/copy pass (default: index,gather,scatter,copy,...)")
    ap.add_argument("--exclude", default=",".join(DEFAULT_EXCLUDE),
                    help="comma-separated substrings to exclude from the match")
    ap.add_argument("--accept-fraction", type=float, default=DEFAULT_ACCEPT_FRACTION,
                    help="gather/copy share must drop to <= this fraction of baseline")
    ap.add_argument("--regress-tol", type=float, default=DEFAULT_REGRESS_TOL,
                    help="allowed total-time regression fraction (profiler noise)")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.before or not args.after:
        ap.error("--before and --after are required (or --selftest)")

    inc = tuple(s.strip() for s in args.match.split(",") if s.strip())
    exc = tuple(s.strip() for s in args.exclude.split(",") if s.strip())
    a = analyze(args.before, args.after, inc, exc,
                args.accept_fraction, args.regress_tol)
    report = build_report(a)
    print(report)
    if args.out and "error" not in a:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        print(f"Report written to: {args.out}")
    return 0 if a.get("accepted") else 1


if __name__ == "__main__":
    sys.exit(main())
