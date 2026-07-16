#!/usr/bin/env python3
"""CPU self-checks for the two-half-kernel unzip-bound probe — the pure decision logic and
the byte/FLOP accounting, WITHOUT a GPU or Triton. The Triton kernels themselves cannot be
CPU-validated (GPU-only); these tests lock the parts that decide the verdict so a bad probe
run can't silently produce a wrong MEMORY/COMPUTE call.

  python test_unzip_probe_cpu.py        # -> "unzip-probe CPU checks: N/N PASS"
"""
from __future__ import annotations

import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(fname, mod):
    spec = importlib.util.spec_from_file_location(mod, os.path.join(_HERE, fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


PROBE = _load("unzip_bound_probe.py", "unzip_bound_probe")
CLS = _load("08_classify_unzip_bound.py", "classify_unzip_bound")

_n = 0


def check(name, cond):
    global _n
    assert cond, f"FAIL: {name}"
    _n += 1
    print(f"  ok: {name}")


# --------------------------------------------------------------- byte/FLOP model ----
def test_byte_flop_model():
    # ctx=64, BS=32 -> n_blocks=2, S_pad=64; H=4, D=128, DH=64, VNG=4, n_protect=5.
    mc = PROBE.byte_flop_model(64, 4, 128, 32, 5, 32, "compact")
    # block: 2*(2*128)=512; tok: 64+10+64+8+8=154; total=2*4*512 + 64*4*154
    check("compact block_bytes", mc["block_bytes_per_head"] == 512)
    check("compact tok_bytes", mc["tok_bytes_per_head"] == 154)
    check("compact total_bytes", mc["total_fetch_bytes"] == 2 * 4 * 512 + 64 * 4 * 154)
    check("flops = 4*D*S*H", mc["total_dequant_flops"] == 4 * 128 * 64 * 4)
    check("compact protect bytes = 2*n_protect", mc["protect_bytes_per_tok_head"] == 10)

    mf = PROBE.byte_flop_model(64, 4, 128, 32, 5, 32, "full")
    check("full protect bytes = 2*D", mf["protect_bytes_per_tok_head"] == 256)
    check("full tok_bytes", mf["tok_bytes_per_head"] == 64 + 256 + 64 + 8 + 8)
    check("full moves more bytes than compact", mf["total_fetch_bytes"] > mc["total_fetch_bytes"])
    check("same flops regardless of protect", mf["total_dequant_flops"] == mc["total_dequant_flops"])
    # arithmetic intensity is bytes-driven: compact (fewer bytes) has HIGHER AI than full
    check("AI compact > AI full",
          mc["arithmetic_intensity_flop_per_byte"] > mf["arithmetic_intensity_flop_per_byte"])

    mn = PROBE.byte_flop_model(64, 4, 128, 32, 5, 32, "none")
    check("none protect bytes = 0", mn["protect_bytes_per_tok_head"] == 0)


# --------------------------------------------------------------- classify_times ----
def test_classify_times():
    # MEMORY-BOUND: fetch dominates, math tiny -> full ~= fetch (math hidden). This is the
    # exact case the regime-order fix protects (f+m ~= f, so a naive serial test misfires).
    v = CLS.classify_times(45.0, 5.0, 46.0)
    check("memory-bound verdict", v["verdict"] == "MEMORY-BOUND")
    check("memory-bound dominant", v["dominant"] == "memory")
    check("memory-bound overlap hidden", v["overlap"] == "hidden")

    # COMPUTE-BOUND: math dominates, fetch hidden.
    v = CLS.classify_times(5.0, 45.0, 47.0)
    check("compute-bound verdict", v["verdict"] == "COMPUTE-BOUND")
    check("compute-bound dominant", v["dominant"] == "compute")

    # BOTH-TIGHTENABLE: comparable, times add (serial, neither hidden).
    v = CLS.classify_times(25.0, 25.0, 48.0)
    check("both-tightenable verdict", v["verdict"] == "BOTH-TIGHTENABLE")
    check("both-tightenable overlap serial", v["overlap"] == "serial")

    # PARTIALLY-OVERLAPPED: comparable, F between max and sum, balanced.
    v = CLS.classify_times(20.0, 18.0, 27.0)
    check("partial verdict", v["verdict"] == "PARTIALLY-OVERLAPPED")
    check("partial overlap", v["overlap"] == "partial")

    # BALANCED-OVERLAPPED: comparable AND hidden (F ~= max).
    v = CLS.classify_times(20.0, 19.0, 22.0)
    check("balanced-overlapped verdict", v["verdict"] == "BALANCED-OVERLAPPED")

    # memory-bound but serial (fetch dominates yet no overlap) -> BOTH-TIGHTENABLE.
    v = CLS.classify_times(40.0, 20.0, 58.0)
    check("dominant-but-serial -> both", v["verdict"] == "BOTH-TIGHTENABLE")

    # UNAVAILABLE guards.
    check("unavailable on None", CLS.classify_times(None, 5.0, 6.0)["verdict"] == "UNAVAILABLE")
    check("unavailable on zero", CLS.classify_times(0.0, 5.0, 6.0)["verdict"] == "UNAVAILABLE")


# --------------------------------------------------------------- roofline ----
def test_roofline():
    model = PROBE.byte_flop_model(32768, 4, 128, 32, 5, 32, "compact")
    peak = CLS.peaks_for("NVIDIA A100-SXM4-80GB")
    check("peak matched A100-80", peak["hbm_gbps"] == 2039.0)
    # a fetch time that moves bytes near peak -> SATURATED
    B = model["total_fetch_bytes"]
    f_ms_sat = B / (0.90 * peak["hbm_gbps"] * 1e9) * 1e3     # 90% of peak
    r = CLS.roofline(model, f_ms_sat, 1.0, f_ms_sat + 1.0, peak)
    check("roofline saturated", r["bandwidth_state"] == "SATURATED")
    check("roofline util ~0.9", 0.85 <= r["hbm_utilization"] <= 0.95)
    # a slow fetch (10% of peak) -> UNDER-UTILISED
    f_ms_slow = B / (0.10 * peak["hbm_gbps"] * 1e9) * 1e3
    r2 = CLS.roofline(model, f_ms_slow, 1.0, f_ms_slow + 1.0, peak)
    check("roofline under-utilised", r2["bandwidth_state"] == "UNDER-UTILISED")
    # AI is small (bytes >> flops) so the unzip sits in the memory region of the roofline
    check("roofline region memory", r["roofline_region"] == "memory")
    check("roofline unavailable on bad time", CLS.roofline(model, 0.0, 1.0, 1.0, peak)["label"] == "UNAVAILABLE")


def test_peaks_for():
    check("H100 matched", CLS.peaks_for("NVIDIA H100 80GB HBM3")["hbm_gbps"] == 3350.0)
    d = CLS.peaks_for("Some Unlisted GPU")
    check("unknown falls back to default", d["hbm_gbps"] == CLS._DEFAULT_PEAK["hbm_gbps"])
    check("unknown labelled", "UNKNOWN" in d["matched_device"])
    o = CLS.peaks_for("NVIDIA A100-SXM4-80GB", override_hbm=1234.0)
    check("hbm override applied", o["hbm_gbps"] == 1234.0 and "override" in o["matched_device"])


# --------------------------------------------------------------- analyse (end-to-end) ----
def _synthetic_probe(f, m, Fc, Ff, ctxs=(4096, 16384, 32768)):
    per = {}
    for c in ctxs:
        per[str(c)] = {
            "fetch_only_ms": f, "math_only_ms": m, "full_compact_ms": Fc, "full_fullprotect_ms": Ff,
            "S_padded": c, "n_blocks": c // 32, "iters": 100,
            "model_compact": PROBE.byte_flop_model(c, 4, 128, 32, 5, 32, "compact"),
            "model_fullprotect": PROBE.byte_flop_model(c, 4, 128, 32, 5, 32, "full"),
        }
    return {"label": "GPU-measured", "device": {"name": "NVIDIA A100-SXM4-80GB"}, "per_ctx": per}


def test_analyse_end_to_end():
    # memory-bound compact path; full-protect is ~2x slower -> big fp16-pool ablation.
    d = CLS.analyse(_synthetic_probe(40.0, 5.0, 41.0, 80.0))
    check("analyse verdict memory", d["verdict"] == "MEMORY-BOUND")
    check("analyse decision ctx = largest", d["decision_context"] == 32768)
    ab = d["route_a_fp16_pool_ablation"]["fp16_pool_penalty_pct_of_route_a_full"]
    check("analyse ablation ~48-50%", 45.0 <= ab <= 52.0)
    check("analyse lever mentions HBM or compact", ("HBM" in d["lever"]) or ("compact" in d["lever"]))
    check("analyse trend all memory",
          all(v == "MEMORY-BOUND" for v in d["verdict_by_context"].values()))

    # compute-bound path.
    d2 = CLS.analyse(_synthetic_probe(5.0, 40.0, 41.0, 44.0))
    check("analyse verdict compute", d2["verdict"] == "COMPUTE-BOUND")
    check("analyse compute lever mentions math", "math" in d2["lever"].lower())

    # UNAVAILABLE propagation.
    dU = CLS.analyse({"label": "UNAVAILABLE", "error": "no CUDA GPU"})
    check("analyse propagates UNAVAILABLE", dU["verdict"] == "UNAVAILABLE")
    dN = CLS.analyse(None)
    check("analyse handles None", dN["verdict"] == "UNAVAILABLE")


def main():
    for t in (test_byte_flop_model, test_classify_times, test_roofline,
              test_peaks_for, test_analyse_end_to_end):
        t()
    print(f"unzip-probe CPU checks: {_n}/{_n} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
