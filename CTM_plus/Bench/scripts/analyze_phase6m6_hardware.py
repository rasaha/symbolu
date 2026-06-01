"""Phase 6M.6 — hardware (newer-silicon) analyzer for the throughput tax.

Test 2 of `PHASE_6M_THROUGHPUT_RECOVERY_TEST_PLAN.md` (§Test 2). Ingests one
`phase6l_capacity_demo.py --compare` report.json **per GPU** (A100 baseline +
H100 and/or H200) and produces:

  1. the per-GPU aggregate-tps-ratio table (protected/bf16 — the ~0.22× on A100),
  2. the compute-vs-bandwidth **axis attribution**, cross-referenced to Test 1's
     roofline verdict to break the H200 confound.

### The confound this resolves (plan §Test 2)
A100 -> H100 -> H200 changes **two axes at once**: native low-precision compute
(Hopper has INT4/FP8 tensor paths A100 lacks) AND HBM bandwidth (A100 ~2.0 TB/s ->
H100 ~3.35 TB/s -> H200 HBM3e ~4.8 TB/s). A bare H200 throughput gain cannot tell
you which axis caused it. **Test 1's bound classification disambiguates** — pass
it via `--bound-verdict` and this analyzer attributes the gain accordingly.

NO GPU work, NO code change — pure ingestion of committed capacity JSONs.

Usage (CPU, anywhere):
    python CTM_plus/Bench/scripts/analyze_phase6m6_hardware.py \
        --report A100=bench_out/phase6m6/A100_report.json \
        --report H100=bench_out/phase6m6/H100_report.json \
        --report H200=bench_out/phase6m6/H200_report.json \
        --bound-verdict compute-bound \
        --out PHASE_6M6_hardware_report.txt

Self-test (CPU-only, no JSON files needed):
    python CTM_plus/Bench/scripts/analyze_phase6m6_hardware.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Known peak HBM bandwidth (TB/s) — ANNOTATION ONLY (never drives the verdict;
# Test 1's bound classification does). Used to contextualize the ratio table.
GPU_HBM_TBS: Dict[str, float] = {
    "A100": 2.0, "A100-80GB": 2.0,
    "H100": 3.35, "H100-SXM": 3.35,
    "H200": 4.8,
}
# Which GPUs add a native low-precision (INT4/FP8) tensor path vs A100.
GPU_NATIVE_LOWP = {"H100", "H100-SXM", "H200"}

# Test-1 verdict tags (kept in sync with analyze_phase6m5_roofline.py).
V_COMPUTE = "compute-bound"
V_BW_UNCOALESCED = "bandwidth-bound-uncoalesced"
V_BW_COALESCED = "bandwidth-bound-coalesced"
V_OCCUPANCY = "latency/occupancy-bound"
V_UNKNOWN = "unknown"


def _norm_gpu(name: str) -> str:
    n = name.strip().upper().replace("_", "-")
    for key in GPU_HBM_TBS:
        if key.upper() == n:
            return key
    # Loose family match (e.g. "H200-141GB" -> "H200").
    for fam in ("H200", "H100", "A100"):
        if fam in n:
            return fam
    return name.strip()


def load_report(path: Path) -> Dict[str, Optional[float]]:
    """Pull the throughput/density headline from a phase6l report.json."""
    data = json.loads(path.read_text())
    tp = data.get("throughput") or {}
    dn = data.get("density") or {}
    # density block stores demonstrated_density_ratio under analysis too.
    ddr = (dn.get("demonstrated_density_ratio")
           if isinstance(dn, dict) else None)
    if ddr is None:
        ddr = (data.get("analysis") or {}).get("demonstrated_density_ratio")
    return {
        "agg_ratio": tp.get("aggregate_tps_ratio"),
        "protected_agg_tps": tp.get("protected_agg_tps"),
        "bf16_agg_tps": tp.get("bf16_agg_tps"),
        "per_seq_ratio": tp.get("per_seq_tps_ratio"),
        "per_seq_slowdown_x": tp.get("per_seq_slowdown_x"),
        "density_ratio": ddr,
        "mml": data.get("mml"),
    }


def attribute_axis(per_gpu: Dict[str, Dict[str, Optional[float]]],
                   baseline: str, verdict: str,
                   material_abs: float, material_rel: float
                   ) -> Tuple[str, List[str]]:
    """Return (headline, detail_lines) attributing any gain to compute vs
    bandwidth, cross-referenced to Test 1's bound verdict.

    Decision outputs mirror plan §Test 2:
      * improves on H100 AND Test1=compute-bound -> native low-precision compute.
      * improves only on H200 (not H100)         -> HBM bandwidth.
      * no material improvement                  -> structural; STOP.
    """
    base = per_gpu.get(baseline, {})
    base_ratio = base.get("agg_ratio")
    detail: List[str] = []

    def improved(name: str) -> Optional[bool]:
        r = per_gpu.get(name, {}).get("agg_ratio")
        if r is None or base_ratio is None:
            return None
        return (r - base_ratio) >= material_abs and (
            base_ratio <= 0 or (r - base_ratio) / base_ratio >= material_rel)

    h100 = improved("H100")
    h200 = improved("H200")
    h200_beyond_h100 = None
    if ("H100" in per_gpu and "H200" in per_gpu
            and per_gpu["H100"].get("agg_ratio") is not None
            and per_gpu["H200"].get("agg_ratio") is not None):
        d = per_gpu["H200"]["agg_ratio"] - per_gpu["H100"]["agg_ratio"]
        h200_beyond_h100 = d >= material_abs

    for nm in ("H100", "H200"):
        if nm in per_gpu and per_gpu[nm].get("agg_ratio") is not None and base_ratio is not None:
            d = per_gpu[nm]["agg_ratio"] - base_ratio
            detail.append(f"{nm}: agg ratio {per_gpu[nm]['agg_ratio']:.3f} "
                          f"(Δ vs {baseline} {d:+.3f}); "
                          f"{'IMPROVED' if improved(nm) else 'flat'}")

    any_improve = any(x for x in (h100, h200) if x)
    if base_ratio is None:
        return ("INCONCLUSIVE — baseline agg ratio missing from "
                f"{baseline} report.json", detail)

    if not any_improve:
        return ("STRUCTURAL — no material improvement on newer silicon. The "
                "throughput tax is structural to the int4 algorithm. STOP: "
                "batch/offline density is the position, full stop.", detail)

    # Something improved. Attribute via Test 1's verdict.
    if h100 and verdict == V_COMPUTE:
        head = ("COMPUTE axis — improves on H100 and Test 1 = compute-bound: "
                "native low-precision (INT4) tensor compute is the lever. "
                "'Deploy on Hopper' is a zero-NRE throughput answer.")
        if h200_beyond_h100:
            head += (" H200 improves further on top -> HBM bandwidth adds a "
                     "secondary gain.")
        return head, detail

    if h100 and verdict in (V_BW_UNCOALESCED, V_BW_COALESCED):
        return ("BANDWIDTH axis (caution) — improves on H100, but Test 1 = "
                f"{verdict}. H100 raises BOTH compute and bandwidth (2.0->3.35 "
                "TB/s); with a bandwidth-bound kernel the bandwidth bump is the "
                "likely cause. Confirm direction with the H200 leg.", detail)

    if h200 and not h100:
        return ("BANDWIDTH axis — improves on H200 but NOT H100: it is HBM "
                "bandwidth (HBM3e ~4.8 TB/s), not native compute. The gap is "
                "bandwidth-bound; weigh H200 deployment vs the §HBM layout fix.",
                detail)

    if any_improve and verdict == V_UNKNOWN:
        return ("CONFOUNDED — improvement observed but Test 1 verdict not "
                "supplied. Cannot split compute vs bandwidth: H100/H200 raise "
                "both axes at once. Provide --bound-verdict from Test 1 "
                "(6M.5) to attribute. (If only H200 improved, bandwidth is "
                "implicated; if H100 already improved and Test 1 says "
                "compute-bound, native INT4 is the lever.)", detail)

    # Improved, verdict present but not matched above (e.g. occupancy-bound).
    return (f"IMPROVED but verdict={verdict} — improvement seen; re-read with "
            "Test 1. An occupancy/latency verdict warrants re-checking the "
            "operating point before attributing.", detail)


def build_report(per_gpu: Dict[str, Dict[str, Optional[float]]],
                 order: List[str], baseline: str, verdict: str,
                 headline: str, detail: List[str]) -> str:
    L: List[str] = []
    L.append("=" * 78)
    L.append("Phase 6M.6 — Hardware: does newer silicon close the 0.22× tax?")
    L.append("=" * 78)
    L.append(f"baseline: {baseline}   Test-1 bound verdict: {verdict}")
    L.append("")
    hdr = (f"{'GPU':<10} | {'HBM TB/s':>8} | {'native INT4':>11} | "
           f"{'agg ratio':>9} | {'per-seq':>8} | {'density':>8} | {'prot tps':>9}")
    L.append(hdr)
    L.append("-" * len(hdr))
    for g in order:
        d = per_gpu[g]
        hbm = GPU_HBM_TBS.get(g)
        lowp = "yes" if g in GPU_NATIVE_LOWP else "no"
        L.append(
            f"{g:<10} | {('%.2f' % hbm) if hbm else '   ?':>8} | {lowp:>11} | "
            f"{_n(d.get('agg_ratio'), 3):>9} | {_n(d.get('per_seq_ratio'), 3):>8} | "
            f"{_n(d.get('density_ratio'), 3):>8} | {_n(d.get('protected_agg_tps'), 1):>9}")
    L.append("")
    L.append("-" * 78)
    L.append("AXIS ATTRIBUTION:")
    L.append(f"  {headline}")
    if detail:
        L.append("")
        for ln in detail:
            L.append(f"  · {ln}")
    L.append("-" * 78)
    L.append("")
    L.append("Note: HBM TB/s + native-INT4 columns are ANNOTATION; the verdict is")
    L.append("driven by the measured ratios + Test 1's bound classification, NOT by")
    L.append("the spec sheet. Density ratio should be HARDWARE-INVARIANT (~1.83× net,")
    L.append("2.0× raw) — a big swing there flags a measurement problem.")
    return "\n".join(L) + "\n"


def _n(v: Optional[float], nd: int) -> str:
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) else "n/a"


# ---------------------------------------------------------------------------
def _selftest() -> int:
    th = dict(material_abs=0.03, material_rel=0.10)

    def synth(agg, per_seq=None, density=2.0, prot=120.0):
        return {"agg_ratio": agg, "per_seq_ratio": per_seq, "density_ratio": density,
                "protected_agg_tps": prot, "bf16_agg_tps": None,
                "per_seq_slowdown_x": None, "mml": 8192}

    # Case A: improves on H100, Test 1 = compute-bound -> COMPUTE axis.
    pg = {"A100": synth(0.22), "H100": synth(0.40), "H200": synth(0.45)}
    head, _ = attribute_axis(pg, "A100", V_COMPUTE, **th)
    assert head.startswith("COMPUTE axis"), head
    print("  improves@H100 + compute-bound -> COMPUTE axis: PASS")

    # Case B: improves only on H200 (H100 flat) -> BANDWIDTH axis.
    pg = {"A100": synth(0.22), "H100": synth(0.23), "H200": synth(0.40)}
    head, _ = attribute_axis(pg, "A100", V_COMPUTE, **th)
    assert head.startswith("BANDWIDTH axis"), head
    assert "NOT H100" in head, head
    print("  improves@H200 only -> BANDWIDTH axis: PASS")

    # Case C: no improvement anywhere -> STRUCTURAL / STOP.
    pg = {"A100": synth(0.22), "H100": synth(0.23), "H200": synth(0.235)}
    head, _ = attribute_axis(pg, "A100", V_COMPUTE, **th)
    assert head.startswith("STRUCTURAL"), head
    assert "STOP" in head, head
    print("  no improvement -> STRUCTURAL/STOP: PASS")

    # Case D: improves@H100 but Test 1 bandwidth-bound -> BANDWIDTH (caution).
    pg = {"A100": synth(0.22), "H100": synth(0.45)}
    head, _ = attribute_axis(pg, "A100", V_BW_UNCOALESCED, **th)
    assert head.startswith("BANDWIDTH axis (caution)"), head
    print("  improves@H100 + bandwidth-bound -> BANDWIDTH (caution): PASS")

    # Case E: improvement but no Test-1 verdict -> CONFOUNDED.
    pg = {"A100": synth(0.22), "H100": synth(0.40)}
    head, _ = attribute_axis(pg, "A100", V_UNKNOWN, **th)
    assert head.startswith("CONFOUNDED"), head
    print("  improvement + no verdict -> CONFOUNDED: PASS")

    # Case F: relative threshold gates tiny abs gains at low baseline.
    pg = {"A100": synth(0.22), "H100": synth(0.24)}  # +0.02 abs < 0.03
    head, _ = attribute_axis(pg, "A100", V_COMPUTE, **th)
    assert head.startswith("STRUCTURAL"), head
    print("  sub-threshold gain -> STRUCTURAL: PASS")

    # load_report round-trip via a temp file.
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "r.json"
        p.write_text(json.dumps({
            "mml": 8192,
            "throughput": {"aggregate_tps_ratio": 0.22, "protected_agg_tps": 117.0,
                           "bf16_agg_tps": 530.0, "per_seq_tps_ratio": 0.11,
                           "per_seq_slowdown_x": 9.0},
            "density": {"demonstrated_density_ratio": 1.83},
        }))
        r = load_report(p)
        assert abs(r["agg_ratio"] - 0.22) < 1e-9 and abs(r["density_ratio"] - 1.83) < 1e-9
        assert abs(r["protected_agg_tps"] - 117.0) < 1e-9
    print("  load_report round-trip: PASS")

    # _norm_gpu family matching.
    assert _norm_gpu("h200-141gb") == "H200"
    assert _norm_gpu("A100-80GB") == "A100-80GB"
    print("  _norm_gpu family match: PASS")

    print("\nself-test: 8/8 PASS")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Phase 6M.6 hardware analyzer")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--report", action="append", default=[], metavar="GPU=PATH",
                   help="GPU=path-to-report.json (repeatable). e.g. "
                        "A100=bench_out/phase6m6/A100_report.json")
    p.add_argument("--baseline", default=None,
                   help="GPU name to use as baseline (default: A100 if present, "
                        "else the first --report)")
    p.add_argument("--bound-verdict", default=V_UNKNOWN,
                   choices=[V_COMPUTE, V_BW_UNCOALESCED, V_BW_COALESCED,
                            V_OCCUPANCY, V_UNKNOWN],
                   help="Test 1 (6M.5) roofline verdict, to break the H100/H200 "
                        "compute-vs-bandwidth confound")
    p.add_argument("--material-abs", type=float, default=0.03,
                   help="min absolute agg-ratio gain to call 'improved'")
    p.add_argument("--material-rel", type=float, default=0.10,
                   help="min relative agg-ratio gain to call 'improved'")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not args.report:
        p.error("provide at least one --report GPU=PATH (or --selftest)")

    per_gpu: Dict[str, Dict[str, Optional[float]]] = {}
    order: List[str] = []
    for spec in args.report:
        if "=" not in spec:
            p.error(f"--report must be GPU=PATH, got {spec!r}")
        gpu, path = spec.split("=", 1)
        gpu = _norm_gpu(gpu)
        rp = Path(path)
        if not rp.exists():
            p.error(f"report not found: {rp}")
        per_gpu[gpu] = load_report(rp)
        if gpu not in order:
            order.append(gpu)

    # Order the table A100 -> H100 -> H200 where present, else input order.
    pref = [g for g in ("A100", "A100-80GB", "H100", "H100-SXM", "H200") if g in per_gpu]
    order = pref + [g for g in order if g not in pref]

    baseline = args.baseline and _norm_gpu(args.baseline)
    if not baseline or baseline not in per_gpu:
        baseline = next((g for g in ("A100", "A100-80GB") if g in per_gpu),
                        order[0])

    headline, detail = attribute_axis(
        per_gpu, baseline, args.bound_verdict,
        args.material_abs, args.material_rel)
    report = build_report(per_gpu, order, baseline, args.bound_verdict,
                          headline, detail)
    print(report)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
        print(f"Report written to: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
