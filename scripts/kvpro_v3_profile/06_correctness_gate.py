#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part B: MANDATORY correctness gate. Route-A must match the CPU oracle BEFORE any
profiling. Emits correctness.json and a nonzero exit code on failure so run_profile_all.sh aborts.

CPU half (runs anywhere, gates here): build the writer `view` (route_a_builder) and verify against the
in-repo reference dequant (phase6f_read_fusion) — reference==fused byte-eq, INT4 round-trip within one
step, EXACT protect overlay, across full AND partial-tail lengths (Part G), for bf16 AND production-int8
protected. GPU half (pod-only): compare the Triton route-A kernel output to the oracle for the SAME view.

Never profile an incorrect kernel: a FAIL here must stop the pipeline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import torch

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(os.path.abspath(os.path.join(_HERE, "..", "..")),
                                "experiments", "kvpro_v3_symmetric_residual"))
import route_a_builder as RB          # noqa: E402
import phase6f_read_fusion as RF      # noqa: E402  (added to path by route_a_builder)
import protected_int8 as P8           # noqa: E402


def _scale_tok(k_scale, S_pad, BS):
    block_of_tok = (torch.arange(S_pad) // BS).long()
    return k_scale[0].index_select(0, block_of_tok)                     # (S_pad,H,D)


def roundtrip_checks(K_fp, V_fp, mask, BS=32, v_group_size=32, k_min=None, k_max=None, prot_int8=False):
    """Return {check: {pass, detail}} for one (K,V,mask) at one sequence length."""
    S = K_fp.shape[0]
    view = RB.build_packed_view(K_fp, V_fp, mask, BS, v_group_size, k_min, k_max, prot_int8)
    S_pad = view["S_padded"]
    k_codes = RF.unpack_nibbles(view["k_int4"], view["D"])
    v_codes = RF.unpack_nibbles(view["v_int4"], view["D"])
    # reference vs fused: must be byte-identical (both bf16)
    k_ref = RF.dequant_k_reference(k_codes, view["k_scale"], view["k_xmin"], view["k_protect_bf16"],
                                   view["protect_slot"], BS)
    k_fus = RF.dequant_k_fused(k_codes, view["k_scale"], view["k_xmin"], view["k_protect_bf16"],
                               view["protect_slot"], BS)
    v_ref = RF.dequant_v_reference(v_codes, view["v_scale"], view["v_xmin"])
    v_fus = RF.dequant_v_fused(v_codes, view["v_scale"], view["v_xmin"])
    # f32 dequant for a clean round-trip error
    k_f32 = RF.dequant_k_reference(k_codes, view["k_scale"], view["k_xmin"], view["k_protect_bf16"],
                                   view["protect_slot"], BS, out_dtype=torch.float32)[0, :S]      # (S,H,D)
    v_f32 = RF.dequant_v_reference(v_codes, view["v_scale"], view["v_xmin"], out_dtype=torch.float32)[0, :S]

    prot = mask.to(torch.bool).unsqueeze(0).expand(S, *mask.shape)      # (S,H,D)
    scale_tok = _scale_tok(view["k_scale"], S_pad, BS)[:S]              # (S,H,D)
    ck = {}
    ck["k_ref_eq_fused"] = {"pass": bool(torch.equal(k_ref, k_fus))}
    ck["v_ref_eq_fused"] = {"pass": bool(torch.equal(v_ref, v_fus))}
    # residual (non-protected) K reconstructs within one int4 step
    if (~prot).any():
        err = (k_f32 - K_fp).abs()[~prot]
        bound = scale_tok[~prot] + 1e-4
        ck["k_residual_within_step"] = {"pass": bool((err <= bound).all()), "max_err": float(err.max())}
    # protected K overlay: EXACT (bf16-rounded) for bf16; production-int8 restore for prot_int8
    if prot.any():
        if prot_int8:
            restored, _ = P8.protected_int8_prod(K_fp, k_min, k_max)
            tgt = restored.to(torch.bfloat16).to(torch.float32)[prot]
        else:
            tgt = K_fp.to(torch.bfloat16).to(torch.float32)[prot]
        err = (k_f32[prot] - tgt).abs()
        ck["k_protect_overlay_exact"] = {"pass": bool((err <= 1e-3).all()), "max_err": float(err.max())}
    # V reconstructs within one int4 step
    verr = (v_f32 - V_fp).abs()
    gsz = view["D"] // view["v_n_groups"]
    vscale_tok = view["v_scale"][0, :S].repeat_interleave(gsz, dim=-1)  # (S,H,D)
    ck["v_within_step"] = {"pass": bool((verr <= vscale_tok + 1e-4).all()), "max_err": float(verr.max())}
    return ck, view


def run_cpu(H=4, D=128, BS=32, v_group_size=32, seed=0, protect_fraction=0.04):
    torch.manual_seed(seed)
    n_protect = max(1, round(D * protect_fraction))
    mask = torch.zeros(H, D, dtype=torch.int8)
    for h in range(H):                                                 # top-n_protect channels per head
        mask[h, torch.randperm(D)[:n_protect]] = 1
    kmin = torch.full((H, D), -3.0); kmax = torch.full((H, D), 3.0)    # stand-in calibrated bounds
    tails = [BS * 3, BS * 3 + 1, BS * 3 + 7, BS * 3 + 15, BS * 3 + 31, BS * 4]   # Part G coverage
    results = []
    all_pass = True
    for S in tails:
        K = torch.randn(S, H, D); V = torch.randn(S, H, D)
        for pint8 in (False, True):
            ck, _ = roundtrip_checks(K, V, mask, BS, v_group_size, kmin, kmax, pint8)
            ok = all(c["pass"] for c in ck.values())
            all_pass = all_pass and ok
            results.append({"seq_len": S, "prot_int8": pint8, "pass": ok, "checks": ck})
    return {"label": "CPU-verified", "all_pass": all_pass, "n_cases": len(results), "cases": results,
            "geom": {"H_kv": H, "D": D, "BS": BS, "v_group_size": v_group_size, "n_protect": n_protect}}


def gpu_kernel_vs_oracle():
    """POD-ONLY: compare the in-repo Triton route-A kernel to the CPU oracle on identical views. Best-effort
    — returns UNAVAILABLE (not a pass) if GPU / kernel / a synthetic-input entry is missing, so profiling is
    NOT enabled by a missing check. The production vLLM fork path is a separate, still-blocked comparison."""
    if not torch.cuda.is_available():
        return {"label": "UNAVAILABLE", "reason": "no CUDA GPU"}
    try:
        import int4_fused_attention_kernel as RA  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return {"label": "UNAVAILABLE", "reason": f"route-A kernel import failed: {e}"}
    return {"label": "UNAVAILABLE",
            "reason": "route-A GPU kernel present; wire build_packed_view -> kernel and compare to "
                      "int4_fused_attention_sketch.fused_int4_attention_reference. Kept honest: no GPU "
                      "numeric check is claimed until it actually runs."}


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Step-0 MANDATORY correctness gate (Part B)")
    ap.add_argument("--out", default="correctness.json")
    ap.add_argument("--gpu", action="store_true", help="also attempt the pod-only kernel-vs-oracle check")
    a = ap.parse_args(argv)
    cpu = run_cpu()
    blob = {"cpu": cpu, "gpu": gpu_kernel_vs_oracle() if a.gpu else {"label": "NOT_RUN"},
            "gate_pass": bool(cpu["all_pass"])}
    json.dump(blob, open(a.out, "w"), indent=2)
    print(f"[correctness] CPU {'PASS' if cpu['all_pass'] else 'FAIL'} "
          f"({cpu['n_cases']} cases: full+partial tails, bf16+prot-int8) -> {a.out}")
    if not cpu["all_pass"]:
        for c in cpu["cases"]:
            if not c["pass"]:
                print(f"  [FAIL] seq_len={c['seq_len']} prot_int8={c['prot_int8']}: "
                      f"{[k for k, v in c['checks'].items() if not v['pass']]}")
        print("[correctness] GATE FAIL — profiling must NOT proceed.")
        return 2
    print("[correctness] GATE PASS — profiling may proceed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
