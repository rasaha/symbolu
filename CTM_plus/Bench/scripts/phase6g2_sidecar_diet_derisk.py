#!/usr/bin/env python3
# Phase 6G.2 — sidecar-diet DE-RISK analyzer (measure before you cut).
#
# Phase 6G audited the int4_protected sidecars (~3.4-4.0 GB) and found the
# classic "diet" (fp8 / coarser groups) has a ~2.5 GB ceiling because it only
# *shrinks* tensors. The higher-leverage move is to *eliminate* metadata
# tensors by exploiting their distribution — but only where the calibration
# data actually supports it. This script measures whether two elimination
# ideas are viable PER MODEL, BEFORE any GPU/kernel spend:
#
#   (B) PREDICTED XMIN  — drop k_xmin_ext + v_xmin_ext (~1.30 GB at mml=32K).
#       Hypothesis: per (layer, head, channel/group) the stored xmin is a
#       linear function of scale, xmin ≈ α·scale + β. If so, store only scale
#       + a tiny per-unit (α, β) and reconstruct xmin in-kernel.
#       Decision metric: regression R² and the residual expressed in LSBs of
#       the quant step (resid_rms / mean_scale). A residual well under 1 LSB
#       means predicted-xmin adds error below the existing int4 quant floor.
#
#   (A) SYMMETRIC V    — drop v_xmin_ext (~0.65 GB), quantize V symmetrically.
#       Hypothesis: per V group the distribution is ~centered, so a signed
#       symmetric grid wastes little range vs the asymmetric (xmin, scale) one.
#       Decision metric: the error-inflation factor of symmetric vs asymmetric
#       quant, which is closed-form = 2·absmax / (xmax − xmin). =1 when centered
#       (free), >1 when offset (symmetric clips / coarsens). (Predicted-xmin (B)
#       subsumes symmetric-V (A) for xmin; A is the cheaper no-regression route.)
#
# Both decision metrics are CLOSED FORM over per-group (min, max, absmax) +
# (scale, xmin) regression sufficient statistics — accumulable online in the
# capture hook, no raw-activation dump. The quant convention matches the writer
# (phase5b_4c_paged_writer.py): asymmetric, scale=(max−min)/15, xmin=min;
# K per-channel over a 32-token block, V per-token over a 32-channel group.
#
# This is a SCREEN, not the final quality verdict: GREEN here means "worth
# implementing + running the real A/B quality bench"; RED means "don't bother
# on this model." The downstream GPU A/B (token-agreement + hard-needle) is
# the actual acceptance gate.
#
# Modes:
#   --selftest               CPU; proves the regression + verdict math.   <-- runs here
#   --capture --model M ...  GPU; hooks attention over the calib corpus,
#                            accumulates sufficient stats -> writes JSON.
#   --analyze STATS.json     CPU; loads stats, prints the per-model verdict.
#
# Usage:
#   python CTM_plus/Bench/scripts/phase6g2_sidecar_diet_derisk.py --selftest
#   python CTM_plus/Bench/scripts/phase6g2_sidecar_diet_derisk.py \
#       --capture --model Qwen/Qwen2.5-7B-Instruct \
#       --out /tmp/diet_stats_qwen7b.json
#   python CTM_plus/Bench/scripts/phase6g2_sidecar_diet_derisk.py \
#       --analyze /tmp/diet_stats_qwen7b.json

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

# Sidecar GB recovered if an elimination is GREEN (from PHASE_6G_SIDECAR_DIET_
# FINDINGS.md per-tensor inventory at mml=32K; absolute GB scale up at smaller
# mml but the relative picture is fixed at 16.4% of KV cache).
SAVE_GB = {
    "predicted_xmin": 1.30,   # k_xmin_ext (0.65) + v_xmin_ext (0.65)
    "symmetric_v": 0.65,      # v_xmin_ext only
}

# Quant convention (must match phase5b_4c_paged_writer.py).
ASYM_LEVELS = 15.0            # scale = (max - min) / 15  (unsigned 4-bit, 16 levels)
SYM_LEVELS = 7.5             # symmetric signed 4-bit: scale = absmax / 7.5

# Per-unit verdict thresholds (documented; the raw numbers are always printed
# so a reviewer can re-judge). norm_resid is in LSBs of the quant step: error
# adds in quadrature with the ~0.5-LSB uniform-quant floor, so 0.25 LSB ≈ +3%,
# 0.5 LSB ≈ +12% error.
PX_GREEN = {"r2": 0.98, "norm_resid": 0.25}
PX_YELLOW = {"r2": 0.90, "norm_resid": 0.50}
SV_GREEN = {"mean": 1.05, "max": 1.15}   # error-inflation factor
SV_YELLOW = {"mean": 1.30, "max": 1.60}

# Model-level rollup: an idea is GREEN only if nearly all units are GREEN AND
# the worst unit is no worse than YELLOW (one RED channel can dominate quality).
MODEL_GREEN_FRAC = 0.95
_EPS = 1e-12


# ----------------------------------------------------------------------
# Pure-Python decision core (no numpy/torch — runs anywhere, fully tested).
# ----------------------------------------------------------------------

def linreg_from_sums(n, sx, sy, sxx, sxy, syy):
    """Simple linear regression y ≈ α·x + β from sufficient statistics.

    Returns (alpha, beta, r2, resid_rms, mean_x). Handles the degenerate
    cases that matter for this data:
      * n < 2                      -> not enough samples (r2=None).
      * Var(x) ≈ 0 (scale const)   -> predict y = mean_y; r2 = 1 if y also
                                      const else 0; resid_rms = std(y).
      * Var(y) ≈ 0 (xmin const)    -> perfectly predictable; r2 = 1,
                                      resid_rms = 0 (a constant β suffices).
    """
    if n < 2:
        return (0.0, sy / n if n else 0.0, None, 0.0, sx / n if n else 0.0)
    mean_x = sx / n
    mean_y = sy / n
    var_x = max(sxx / n - mean_x * mean_x, 0.0)
    var_y = max(syy / n - mean_y * mean_y, 0.0)
    cov = sxy / n - mean_x * mean_y
    if var_x <= _EPS:
        # scale ~ constant -> xmin can only be predicted by its own mean.
        r2 = 1.0 if var_y <= _EPS else 0.0
        return (0.0, mean_y, r2, math.sqrt(var_y), mean_x)
    alpha = cov / var_x
    beta = mean_y - alpha * mean_x
    if var_y <= _EPS:
        return (alpha, beta, 1.0, 0.0, mean_x)   # xmin const -> trivially predicted
    r2 = max(0.0, min(1.0, (cov * cov) / (var_x * var_y)))
    resid_rms = math.sqrt(max(var_y * (1.0 - r2), 0.0))
    return (alpha, beta, r2, resid_rms, mean_x)


def predicted_xmin_unit(stats):
    """Per-unit (layer,head,channel|group) verdict for the predicted-xmin idea.
    stats = [n, Sx, Sy, Sxx, Sxy, Syy] with x=scale, y=xmin."""
    n, sx, sy, sxx, sxy, syy = stats
    alpha, beta, r2, resid_rms, mean_x = linreg_from_sums(n, sx, sy, sxx, sxy, syy)
    # Dead channel (≈no signal): scale ≈ 0 -> xmin error is irrelevant.
    if mean_x <= _EPS:
        return {"r2": 1.0, "norm_resid": 0.0, "verdict": "GREEN",
                "alpha": alpha, "beta": beta, "dead": True}
    norm_resid = resid_rms / mean_x
    if r2 is None:
        v = "RED"
    elif r2 >= PX_GREEN["r2"] and norm_resid <= PX_GREEN["norm_resid"]:
        v = "GREEN"
    elif r2 >= PX_YELLOW["r2"] and norm_resid <= PX_YELLOW["norm_resid"]:
        v = "YELLOW"
    else:
        v = "RED"
    return {"r2": r2, "norm_resid": norm_resid, "verdict": v,
            "alpha": alpha, "beta": beta, "dead": False}


def symmetric_v_unit(infl_sum, infl_sq, infl_max, n):
    """Per-group verdict for symmetric-V. infl = 2·absmax/(xmax−xmin), the
    closed-form symmetric/asymmetric quant-step ratio (>=1)."""
    if n <= 0:
        return {"mean": None, "max": None, "verdict": "RED"}
    mean = infl_sum / n
    if mean <= SV_GREEN["mean"] and infl_max <= SV_GREEN["max"]:
        v = "GREEN"
    elif mean <= SV_YELLOW["mean"] and infl_max <= SV_YELLOW["max"]:
        v = "YELLOW"
    else:
        v = "RED"
    return {"mean": mean, "max": infl_max, "verdict": v}


def _pct(sorted_vals, q):
    """Linear-interpolated percentile q in [0,1] of an already-sorted list."""
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = q * (len(sorted_vals) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_vals[lo]
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


def _rollup(unit_verdicts):
    """Aggregate per-unit verdicts -> model-level decision for one idea."""
    n = len(unit_verdicts)
    if n == 0:
        return {"verdict": "NO_DATA", "n_units": 0}
    counts = {"GREEN": 0, "YELLOW": 0, "RED": 0}
    for u in unit_verdicts:
        counts[u["verdict"]] = counts.get(u["verdict"], 0) + 1
    green_frac = counts["GREEN"] / n
    any_red = counts["RED"] > 0
    if green_frac >= MODEL_GREEN_FRAC and not any_red:
        verdict = "GREEN"
    elif counts["RED"] / n <= 0.02 and (counts["GREEN"] + counts["YELLOW"]) / n >= 0.90:
        verdict = "YELLOW"
    else:
        verdict = "RED"
    return {"verdict": verdict, "n_units": n, "counts": counts,
            "green_frac": round(green_frac, 4)}


def analyze_model(stats):
    """stats: the JSON dict written by capture(). Returns a verdict report.

    Layout (per layer, JSON-friendly nested lists):
      stats["layers"][name]["k"]  -> list over (h,d) of [n,Sx,Sy,Sxx,Sxy,Syy]
      stats["layers"][name]["v"]  -> list over (h,g) of
                                     [n,Sx,Sy,Sxx,Sxy,Syy, infl_sum,infl_sq,infl_max]
    """
    layers = stats.get("layers", {})
    px_units, sv_units = [], []          # predicted-xmin (K∪V), symmetric-V (V)
    px_r2, px_nr = [], []
    sv_mean = []
    per_layer = {}

    for name, ld in layers.items():
        lpx, lsv = [], []
        for row in ld.get("k", []):
            u = predicted_xmin_unit(row[:6])
            px_units.append(u); lpx.append(u)
            if not u["dead"]:
                px_r2.append(u["r2"]); px_nr.append(u["norm_resid"])
        for row in ld.get("v", []):
            u = predicted_xmin_unit(row[:6])
            px_units.append(u); lpx.append(u)
            if not u["dead"]:
                px_r2.append(u["r2"]); px_nr.append(u["norm_resid"])
            # symmetric-V uses the same V groups + the inflation accumulators.
            n_v = row[0]
            sv = symmetric_v_unit(row[6], row[7], row[8], n_v)
            sv_units.append(sv); lsv.append(sv)
            if sv["mean"] is not None:
                sv_mean.append(sv["mean"])
        per_layer[name] = {
            "predicted_xmin": _rollup(lpx),
            "symmetric_v": _rollup(lsv),
        }

    px_r2.sort(); px_nr.sort(); sv_mean.sort()
    report = {
        "model": stats.get("model"),
        "n_prompts": stats.get("n_prompts"),
        "block_size": stats.get("block_size"),
        "v_group_size": stats.get("v_group_size"),
        "predicted_xmin": {
            **_rollup(px_units),
            "median_r2": round(_pct(px_r2, 0.5), 4) if px_r2 else None,
            "p10_r2": round(_pct(px_r2, 0.10), 4) if px_r2 else None,
            "median_norm_resid": round(_pct(px_nr, 0.5), 4) if px_nr else None,
            "p90_norm_resid": round(_pct(px_nr, 0.90), 4) if px_nr else None,
            "save_gb": SAVE_GB["predicted_xmin"],
        },
        "symmetric_v": {
            **_rollup(sv_units),
            "median_inflation": round(_pct(sv_mean, 0.5), 4) if sv_mean else None,
            "p90_inflation": round(_pct(sv_mean, 0.90), 4) if sv_mean else None,
            "save_gb": SAVE_GB["symmetric_v"],
        },
        "per_layer": per_layer,
    }
    return report


def format_report(report):
    L = []
    L.append("=" * 78)
    L.append(f"PHASE 6G.2 — sidecar-diet de-risk: {report.get('model')}")
    L.append(f"  calib prompts={report.get('n_prompts')} "
             f"block_size={report.get('block_size')} "
             f"v_group_size={report.get('v_group_size')}")
    L.append("=" * 78)

    px = report["predicted_xmin"]
    L.append("\n(B) PREDICTED XMIN  — drop k_xmin_ext + v_xmin_ext "
             f"(~{px['save_gb']} GB)")
    L.append(f"    verdict: {px['verdict']}   units={px['n_units']} "
             f"green_frac={px.get('green_frac')}  counts={px.get('counts')}")
    L.append(f"    R²: median={px['median_r2']} p10(worst)={px['p10_r2']}   "
             f"norm_resid[LSB]: median={px['median_norm_resid']} "
             f"p90(worst)={px['p90_norm_resid']}")

    sv = report["symmetric_v"]
    L.append(f"\n(A) SYMMETRIC V     — drop v_xmin_ext (~{sv['save_gb']} GB)")
    L.append(f"    verdict: {sv['verdict']}   units={sv['n_units']} "
             f"green_frac={sv.get('green_frac')}  counts={sv.get('counts')}")
    L.append(f"    inflation factor: median={sv['median_inflation']} "
             f"p90(worst)={sv['p90_inflation']}  (1.0 = free, >1 = quality cost)")

    # Stacked saving estimate (B subsumes A's xmin, so they don't add).
    best = px['save_gb'] if px['verdict'] in ("GREEN", "YELLOW") else (
        sv['save_gb'] if sv['verdict'] in ("GREEN", "YELLOW") else 0.0)
    L.append("\n" + "-" * 78)
    L.append(f"  Screen result: up to ~{best:.2f} GB of the ~4.7 GB delta is "
             "plausibly recoverable on this model")
    L.append("  (GREEN/YELLOW => worth the real A/B quality bench; "
             "RED => skip on this model).")
    worst_layers = sorted(
        report["per_layer"].items(),
        key=lambda kv: (kv[1]["predicted_xmin"].get("green_frac", 1.0)))[:3]
    if worst_layers:
        L.append("  weakest layers (predicted-xmin green_frac): " + ", ".join(
            f"{n}={d['predicted_xmin'].get('green_frac')}" for n, d in worst_layers))
    L.append("=" * 78)
    return "\n".join(L)


# ----------------------------------------------------------------------
# GPU capture path (lazy torch/vllm import — needs the model + a GPU).
# ----------------------------------------------------------------------

def capture(model, out_path, protect_irrelevant=True, max_model_len=2048,
            corpus_multiplier=1, block_size=32, v_group_size=32):
    """Hook every leaf attention module over the calibration corpus and
    accumulate the per-unit sufficient statistics the analyzer needs. Mirrors
    calibrate_phase5b_protect_mask.py's hook mechanism (same corpus + the same
    leaf-attention heuristic), but captures BOTH K and V and accumulates quant
    sufficient stats instead of just max-abs."""
    import torch  # noqa: F401  (lazy: GPU-only)
    from vllm import LLM, SamplingParams

    # Reuse the calibration corpus + helpers so the stats match the mask calib.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import calibrate_phase5b_protect_mask as calib

    corpus = calib.CALIBRATION_CORPUS * max(1, corpus_multiplier)
    llm = LLM(model=model, max_model_len=max_model_len,
              gpu_memory_utilization=0.5, enforce_eager=True)
    inner = calib._find_inner_model(llm)
    num_kv_heads = calib._detect_num_kv_heads(inner)
    if not num_kv_heads:
        raise RuntimeError("could not detect num_kv_heads")

    # Per-layer accumulators (built lazily on first prefill once D is known).
    # k_acc[name]: (H, D, 6)  sums [n,Sx,Sy,Sxx,Sxy,Syy], x=scale y=xmin
    # v_acc[name]: (H, ng, 9) sums [...6..., infl_sum, infl_sq, infl_max]
    k_acc, v_acc = {}, {}
    order = []

    def _accum_block_stats(x_blocks):
        # x_blocks: (nblk, BS, H, D) -> per (block,h,d) min/max over BS.
        mn = x_blocks.amin(dim=1)                  # (nblk,H,D)
        mx = x_blocks.amax(dim=1)
        scale = (mx - mn).clamp(min=1e-8) / ASYM_LEVELS
        xmin = mn
        return scale, xmin                          # each (nblk,H,D)

    def _accum_into(acc, name, scale, xmin, shape_hd):
        # Sum sufficient stats over the leading (sample) axis -> (H,D,6).
        s = scale.float(); y = xmin.float()
        n = torch.full(shape_hd, scale.shape[0], dtype=torch.float64,
                       device=scale.device)
        block = torch.stack([
            n,
            s.sum(0).double(), y.sum(0).double(),
            (s * s).sum(0).double(), (s * y).sum(0).double(),
            (y * y).sum(0).double(),
        ], dim=-1)                                  # (H,D,6)
        if name not in acc:
            acc[name] = block
        else:
            acc[name] = acc[name] + block

    def make_hook(lname, kidx=1, vidx=2):
        def wrapped(orig):
            def inner_fwd(*args, **kwargs):
                try:
                    _maybe_capture(lname, args, kidx, vidx)
                except Exception:
                    pass
                return orig(*args, **kwargs)
            return inner_fwd
        return wrapped

    def _to_3d(t):
        if t.ndim == 3:
            return t
        if t.ndim == 2:
            return calib._reshape_kv_2d_to_3d(t, num_kv_heads)
        return None

    def _maybe_capture(lname, args, kidx, vidx):
        if kidx >= len(args) or vidx >= len(args):
            return
        K, V = args[kidx], args[vidx]
        import torch as _t
        if not (isinstance(K, _t.Tensor) and isinstance(V, _t.Tensor)):
            return
        K3, V3 = _to_3d(K), _to_3d(V)
        if K3 is None or V3 is None or K3.shape[0] <= 1:
            return                                  # decode step — skip
        T, H, D = K3.shape
        if lname not in order:
            order.append(lname)
        # --- K: per-channel over 32-token blocks ---
        nblk = T // block_size
        if nblk >= 1:
            kb = K3[:nblk * block_size].reshape(nblk, block_size, H, D)
            ks, kx = _accum_block_stats(kb)
            _accum_into(k_acc, lname, ks, kx, (H, D))
        # --- V: per-token over 32-channel groups ---
        ng = D // v_group_size
        if ng >= 1:
            vg = V3.reshape(T, H, ng, v_group_size)
            vmn = vg.amin(dim=-1); vmx = vg.amax(dim=-1)   # (T,H,ng)
            vscale = (vmx - vmn).clamp(min=1e-8) / ASYM_LEVELS
            vxmin = vmn
            absmax = torch.maximum(vmx.abs(), vmn.abs())
            infl = 2.0 * absmax / (vmx - vmn).clamp(min=1e-8)
            s = vscale.float(); y = vxmin.float(); f = infl.float()
            n = torch.full((H, ng), float(T), dtype=torch.float64, device=s.device)
            block = torch.stack([
                n,
                s.sum(0).double(), y.sum(0).double(),
                (s * s).sum(0).double(), (s * y).sum(0).double(),
                (y * y).sum(0).double(),
                f.sum(0).double(), (f * f).sum(0).double(),
            ], dim=-1)                              # (H,ng,8)
            fmax = f.amax(0).double().unsqueeze(-1)  # (H,ng,1)
            block = torch.cat([block, fmax], dim=-1)  # (H,ng,9)
            if lname not in v_acc:
                v_acc[lname] = block
            else:
                prev = v_acc[lname]
                summed = prev[..., :8] + block[..., :8]
                newmax = torch.maximum(prev[..., 8:], block[..., 8:])
                v_acc[lname] = torch.cat([summed, newmax], dim=-1)

    teardowns = []
    for name, sub in inner.named_modules():
        if not calib._looks_like_attention(sub):
            continue
        orig = sub.forward
        sub.forward = make_hook(name)(orig)
        teardowns.append((sub, orig))

    sp = SamplingParams(temperature=0.0, max_tokens=1)
    llm.generate(corpus, sp)
    for sub, orig in teardowns:
        sub.forward = orig

    layers = {}
    for name in order:
        entry = {}
        if name in k_acc:
            entry["k"] = k_acc[name].reshape(-1, 6).cpu().tolist()
        if name in v_acc:
            entry["v"] = v_acc[name].reshape(-1, 9).cpu().tolist()
        layers[name] = entry

    stats = {"model": model, "n_prompts": len(corpus),
             "block_size": block_size, "v_group_size": v_group_size,
             "num_kv_heads": num_kv_heads, "layers": layers}
    Path(out_path).write_text(json.dumps(stats))
    print(f"[6g2 capture] wrote {out_path}: {len(layers)} layers, "
          f"{len(corpus)} prompts", flush=True)
    print(format_report(analyze_model(stats)))
    return 0


# ----------------------------------------------------------------------
# Selftest (CPU, pure-Python).
# ----------------------------------------------------------------------

def _sums(xs, ys):
    n = len(xs)
    return [n, sum(xs), sum(ys), sum(x * x for x in xs),
            sum(x * y for x, y in zip(xs, ys)), sum(y * y for y in ys)]


def _selftest():
    # 1. Regression core: exact linear data -> R²=1, zero residual.
    xs = [1.0, 2.0, 3.0, 4.0, 5.0]
    ys = [2.0 * x - 0.5 for x in xs]
    a, b, r2, rr, mx = linreg_from_sums(*_sums(xs, ys))
    assert abs(a - 2.0) < 1e-9 and abs(b + 0.5) < 1e-9, (a, b)
    assert abs(r2 - 1.0) < 1e-9 and rr < 1e-9, (r2, rr)
    print("  linreg exact-fit: PASS")

    # 2. Degenerate cases.
    a, b, r2, rr, mx = linreg_from_sums(*_sums([3.0] * 6, [1.0, 2.0, 1.5, 2.5, 1.0, 2.0]))
    assert r2 == 0.0 and rr > 0.0, (r2, rr)             # const scale, varying xmin
    a, b, r2, rr, mx = linreg_from_sums(*_sums([1.0, 2.0, 3.0], [4.0, 4.0, 4.0]))
    assert r2 == 1.0 and rr == 0.0, (r2, rr)            # const xmin -> predictable
    print("  linreg degenerate (const-x / const-y): PASS")

    # 3. predicted-xmin unit verdicts. xmin = -9·scale (centered-ish dist) is a
    #    tight linear law -> GREEN; pure noise -> RED.
    scales = [0.1 * i for i in range(1, 41)]
    xmins_tight = [-9.0 * s + 1e-4 * ((i % 5) - 2) for i, s in enumerate(scales)]
    u = predicted_xmin_unit(_sums(scales, xmins_tight))
    assert u["verdict"] == "GREEN", u
    xmins_noise = [(-9.0 * s) + 3.0 * ((i * 7) % 11 - 5) for i, s in enumerate(scales)]
    u2 = predicted_xmin_unit(_sums(scales, xmins_noise))
    assert u2["verdict"] == "RED", u2
    # dead channel: scale ≈ 0 -> GREEN regardless.
    u3 = predicted_xmin_unit(_sums([0.0] * 8, [0.0] * 8))
    assert u3["verdict"] == "GREEN" and u3["dead"], u3
    print("  predicted_xmin unit (tight/noisy/dead): PASS")

    # 4. symmetric-V inflation. Centered group (absmax≈range/2 -> infl≈1) GREEN;
    #    offset group (absmax≈range -> infl≈2) RED.
    sv_centered = symmetric_v_unit(infl_sum=1.0 * 100, infl_sq=1.0 * 100,
                                   infl_max=1.02, n=100)
    assert sv_centered["verdict"] == "GREEN", sv_centered
    sv_offset = symmetric_v_unit(infl_sum=1.9 * 100, infl_sq=3.7 * 100,
                                 infl_max=2.0, n=100)
    assert sv_offset["verdict"] == "RED", sv_offset
    print("  symmetric_v unit (centered/offset): PASS")

    # 5. Closed-form inflation identity: infl = 2·absmax/(max−min).
    lo, hi = -1.0, 3.0                                   # offset; absmax=3, range=4
    infl = 2.0 * max(abs(lo), abs(hi)) / (hi - lo)
    assert abs(infl - 1.5) < 1e-12, infl
    lo2, hi2 = -2.0, 2.0                                 # centered; absmax=2 range=4
    assert abs(2.0 * 2.0 / 4.0 - 1.0) < 1e-12
    print("  inflation closed-form identity: PASS")

    # 6. Model rollup + full analyze on a synthetic 2-layer model.
    def k_row_green():
        return _sums(scales, xmins_tight)
    def v_row_green():
        return _sums(scales, xmins_tight) + [1.0 * 40, 1.0 * 40, 1.03]
    def v_row_red():
        return _sums(scales, xmins_noise) + [1.9 * 40, 3.7 * 40, 2.1]
    stats = {
        "model": "synthetic-test", "n_prompts": 10,
        "block_size": 32, "v_group_size": 32,
        "layers": {
            "layer0": {"k": [k_row_green() for _ in range(8)],
                       "v": [v_row_green() for _ in range(4)]},
            "layer1": {"k": [k_row_green() for _ in range(8)],
                       "v": [v_row_red() for _ in range(4)]},
        },
    }
    rep = analyze_model(stats)
    # predicted-xmin: layer0 all green; layer1 K green but V noisy -> some RED.
    assert rep["predicted_xmin"]["verdict"] in ("GREEN", "YELLOW", "RED")
    assert rep["per_layer"]["layer0"]["predicted_xmin"]["verdict"] == "GREEN"
    assert rep["per_layer"]["layer0"]["symmetric_v"]["verdict"] == "GREEN"
    assert rep["per_layer"]["layer1"]["symmetric_v"]["verdict"] == "RED"
    assert rep["predicted_xmin"]["save_gb"] == 1.30
    assert rep["symmetric_v"]["save_gb"] == 0.65
    # Mixed V (half green, half red) -> model symmetric_v not GREEN.
    assert rep["symmetric_v"]["verdict"] in ("YELLOW", "RED")
    print("  analyze_model rollup (2-layer synthetic): PASS")
    print(format_report(rep))
    print("\nSELFTEST PASS")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Phase 6G.2 sidecar-diet de-risk")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--capture", action="store_true", help="GPU: hook + accumulate stats")
    ap.add_argument("--analyze", metavar="STATS.json", help="CPU: verdict from captured stats")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--out", default="/tmp/phase6g2_diet_stats.json")
    ap.add_argument("--max-model-len", type=int, default=2048)
    ap.add_argument("--corpus-multiplier", type=int, default=1)
    args = ap.parse_args()

    if args.selftest:
        return _selftest()
    if args.analyze:
        stats = json.loads(Path(args.analyze).read_text())
        print(format_report(analyze_model(stats)))
        return 0
    if args.capture:
        return capture(args.model, args.out, max_model_len=args.max_model_len,
                       corpus_multiplier=args.corpus_multiplier)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
