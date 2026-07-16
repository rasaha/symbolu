#!/usr/bin/env python3
"""KVPro V3 Step-0 — Part E: cost accounting + two ceilings, from the ACTUAL stored layout.

Layout is derived from PagedKVWriter._lazy_alloc / get_packed_view_batched (CTM_plus/KVPolicy/kv_policy/
phase5b_4c_paged_writer.py). Qwen2.5-7B: D=128, BS=32, n_protect=5 (round(0.04*128)), v_n_groups=4,
bf16 sidecars. Per token / KV-head / layer:

  packed K  64 | packed V  64 | K scale 8 (per-block ÷BS) | K xmin 8 (per-block ÷BS)
  K protect 10 (=n_protect*2 bf16, per-token, SCATTERED) | V scale 8 | V xmin 8   => 170 B

Two ceilings, kept strictly separate:
  * IMPLEMENTATION-REMOVAL ceiling — max TIME gain from removing redundant gather / temp buffers /
    splice / extra launches, format UNCHANGED. This is a MEASURED quantity: it cannot exceed the
    profiled (gather+staging+splice) share of decode time. Returns UNAVAILABLE with no profile.
  * FORMAT-CHANGE ceiling — additional MODELED read-BYTE reduction from dropping xmin / prot bf16->int8 /
    densifying. Bytes, not time; NEVER a measured TPS claim.

The S-study's accounting.py used n_protect=6 (172 B, 9.30%); the accurate writer geometry is n_protect=5
(170 B, 9.41%). ~1% difference, immaterial to any verdict; Step-0 uses the accurate 170 B.
"""
from __future__ import annotations

import argparse
import json
import sys

_UNAVAIL = "UNAVAILABLE"

N_PROTECT = 5                           # DEFAULT only; Part F reads the real value from the mask
PROT_B_BF16, PROT_B_INT8 = 2, 1


def layout_for(n_protect: int):
    """Per token / KV-head / layer bytes (matches writer _lazy_alloc), parameterized by n_protect."""
    lay = {"packed_K": 64, "packed_V": 64, "K_scale": 8, "K_xmin": 8,
           "K_protect_bf16": n_protect * PROT_B_BF16, "V_scale": 8, "V_xmin": 8}
    return lay, sum(lay.values())


# n_protect=5 defaults (Qwen2.5-7B), kept for back-compat + the layout smoke test.
LAYOUT, TOTAL = layout_for(N_PROTECT)   # 170


def read_mask_accounting(mask_path):
    """Part F: read the ACTUAL calibration mask and report n_protect + sidecar bytes — DO NOT assume 5.
    n_protect is uniform per (layer,h_kv) by construction (topk), so min==max==mean; the value still comes
    from the real artifact and adapts to a different protect_fraction (e.g. the Llama mask)."""
    import torch
    blob = torch.load(mask_path, map_location="cpu", weights_only=False)
    m = blob.get("mask", blob.get("protect_mask"))
    if m is None:
        return {"label": "UNAVAILABLE", "error": f"no mask in {mask_path}"}
    m = m.to(torch.int64)                                      # (L, H_kv, D)
    per_head = m.sum(-1)                                       # (L, H_kv) count per head
    n_min, n_max, n_mean = int(per_head.min()), int(per_head.max()), float(per_head.float().mean())
    L, H_kv, D = m.shape
    _, tot = layout_for(n_max)
    return {
        "label": "MEASURED", "mask_path": mask_path,
        "n_protect": {"min": n_min, "max": n_max, "mean": round(n_mean, 3), "uniform_by_construction": n_min == n_max},
        "geom": {"num_layers": L, "H_kv": H_kv, "D": D},
        "protect_fraction": blob.get("protect_fraction"), "minmax_margin": blob.get("minmax_margin"),
        "has_calibrated_minmax": bool(blob.get("k_min") is not None and blob.get("k_max") is not None),
        "protected_bytes_per_tok_head_layer_bf16": n_max * PROT_B_BF16,
        "protected_bytes_per_tok_head_layer_int8": n_max * PROT_B_INT8,
        "total_bytes_bf16": tot,
        "matches_step0_default_n5": n_max == N_PROTECT,
    }


def format_change_ceiling(n_protect: int = N_PROTECT):
    """MODELED read-byte reductions vs the affine + bf16-protected baseline, for the ACTUAL n_protect."""
    lay, tot = layout_for(n_protect)
    xmin = lay["K_xmin"] + lay["V_xmin"]                       # 16
    prot_int8_saving = n_protect * (PROT_B_BF16 - PROT_B_INT8)
    return {
        "baseline_bytes_per_tok_head_layer": tot, "n_protect": n_protect,
        "drop_both_xmin_pct": round(100.0 * xmin / tot, 2),
        "protected_bf16_to_int8_pct": round(100.0 * prot_int8_saving / tot, 2),
        "xmin_plus_prot_int8_pct": round(100.0 * (xmin + prot_int8_saving) / tot, 2),
        "note": "MODELED read-byte reduction, NOT measured TPS. Decode recovery is bounded ~0.27-0.30x; "
                "these bytes map to a fraction of that, and the scattered protect stream + packed nibbles "
                "remain the larger costs.",
    }


def staging_byte_model(context_len: int, H_kv: int = 4, n_layers: int = 28, n_protect: int = N_PROTECT):
    """Structural upper bound on REDUNDANT staging traffic if the gathered KV is materialized into a
    temp contiguous buffer then reread by the decode kernel: +1 write +1 read of the per-step KV, on top
    of the 1x irreducible read. Whether/how much staging actually happens is a PROFILE question."""
    _, tot = layout_for(n_protect)
    per_step_kv = tot * context_len * H_kv * n_layers            # bytes read per decode step (all prior KV)
    return {
        "per_step_kv_bytes": per_step_kv,
        "redundant_staging_bytes_if_full_temp": 2 * per_step_kv,  # write + reread
        "max_redundant_fraction_of_gather_path": round(2 / 3, 3),  # 2 redundant of 3 passes
        "note": "STRUCTURAL upper bound only. Confirm the real staging fraction from stage_summary "
                "(gather+staging+splice %). Do not treat as measured.",
    }


def implementation_removal_ceiling(stage_summary: dict | None):
    """MEASURED time ceiling = profiled (gather+staging+splice) share of decode kernel time. UNAVAILABLE
    without a GPU profile — this ceiling is a measurement, not a model."""
    if not stage_summary or stage_summary.get("label") != "GPU-measured":
        return {"max_time_gain_pct": _UNAVAIL,
                "note": "Requires a GPU stage_summary (Nsight/CUDA events). Not modeled; not fabricated."}
    st = stage_summary.get("stages", {})
    def p(n):
        v = st.get(n, {}).get("pct_of_kernel_time")
        return v if isinstance(v, (int, float)) else 0.0
    total = p("gather") + p("staging") + p("splice")
    return {"max_time_gain_pct": round(total, 2),
            "components": {"gather": p("gather"), "staging": p("staging"), "splice": p("splice")},
            "note": "Measured share of decode kernel time in removable stages; the realized gain is a "
                    "fraction of this and stays under the ~0.27-0.30x decode-recovery ceiling."}


def build(stage_summary=None, context_len=8192, H_kv=4, n_layers=28, mask_path=None):
    mask_acc = read_mask_accounting(mask_path) if mask_path else None
    measured = bool(mask_acc and mask_acc.get("label") == "MEASURED")
    n_protect = mask_acc["n_protect"]["max"] if measured else N_PROTECT
    if measured:                                             # adopt the real geometry from the mask
        H_kv = mask_acc["geom"]["H_kv"]
    lay, tot = layout_for(n_protect)
    return {
        "layout_bytes_per_tok_head_layer": lay,
        "total_bytes_per_tok_head_layer": tot,
        "n_protect_used": n_protect,
        "n_protect_source": "mask-file" if measured else "default(5)",
        "mask_accounting": mask_acc,
        "geom": {"D": 128, "BS": 32, "n_protect": n_protect, "v_n_groups": 4,
                 "H_kv": H_kv, "n_layers": n_layers, "context_len": context_len},
        "format_change_ceiling_modeled_bytes": format_change_ceiling(n_protect),
        "implementation_removal_ceiling_measured_time": implementation_removal_ceiling(stage_summary),
        "staging_byte_model_structural": staging_byte_model(context_len, H_kv, n_layers, n_protect),
        "block_table_bytes_per_token": round(4.0 / 32, 4),   # int32 block id per BS=32 tokens (amortized)
        "labels": {"format_change": "MODELED-bytes", "implementation_removal": "MEASURED-time-or-UNAVAILABLE"},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="KVPro V3 Step-0 cost accounting + two ceilings")
    ap.add_argument("--stages", help="stage_summary.json (for the implementation-removal ceiling)")
    ap.add_argument("--mask", help="protect mask .pt — read the REAL n_protect (Part F); default assumes 5")
    ap.add_argument("--context-len", type=int, default=8192)
    ap.add_argument("--out", default="cost_accounting.json")
    a = ap.parse_args(argv)
    ss = json.load(open(a.stages)) if a.stages else None
    blob = build(ss, a.context_len, mask_path=a.mask)
    json.dump(blob, open(a.out, "w"), indent=2)
    fc = blob["format_change_ceiling_modeled_bytes"]; ir = blob["implementation_removal_ceiling_measured_time"]
    print(f"[cost] total {blob['total_bytes_per_tok_head_layer']} B/tok/head/layer "
          f"(n_protect={blob['n_protect_used']} from {blob['n_protect_source']})")
    print(f"[cost] FORMAT-CHANGE ceiling (MODELED bytes): drop-both-xmin {fc['drop_both_xmin_pct']}% | "
          f"prot int8 {fc['protected_bf16_to_int8_pct']}% | combined {fc['xmin_plus_prot_int8_pct']}%")
    print(f"[cost] IMPL-REMOVAL ceiling (MEASURED time): {ir['max_time_gain_pct']}")
    print(f"[cost] -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
