#!/usr/bin/env python3
"""KVPro V3 6F-A measurement #1 — alpha: what share of the decode path does the store-as-consumed
(page-local) layout actually improve? Resolves the PROVISIONAL aggregate gate WITHOUT any 6F-C code.

Grounded in the REAL production decode path (int4_protected_k_cache.py:520-548): the standard
`kernel_inputs` does a permute-contiguous copy of the ENTIRE KV cache (k_packed + k_fp16 + v_packed)
from native (S,H,*) to head-major (H,S,*) EVERY decode step — an O(context) copy — and the decode
KERNEL then reads that coalesced. So page-local's win over the standard path is ELIMINATING THAT
PER-STEP PERMUTE-COPY, not the in-kernel read (which is already coalesced). alpha must capture the
copy, or it understates the case.

Times, on identical geometry, same A100, median + p95, per context:
  1. permute_copy_ms  — the standard-path native->head-major copy of the whole KV (what page-local removes)
  2. decode_kernel_ms — the full in-repo fused_protected_k_decode_attention (read+dequant+QK+softmax+PV+combine),
                        oracle-checked vs the fp reference (cosine)
  3. unzip_current/pagelocal_ms — the raw read-scatter (from the probe), for the gather-path framing

Then:
  alpha_copy = permute_copy_ms / (permute_copy_ms + decode_kernel_ms)   # standard-path win share
  page-local removes the copy, so the (copy+kernel) block shrinks by alpha_copy; with the step share
  beta and a conservative realizability r, aggregate ~= alpha_copy x beta x r. Reports the beta needed
  to clear the frozen 15% gate at r in {0.7, 0.8}, and a decision per the frozen alpha thresholds.

NO production integration, NO 6F-C code. Stops and reports after alpha. POD-ONLY; writes
label=UNAVAILABLE (never fabricated) if GPU/Triton/kernel is missing.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_ROOT, "CTM_plus", "KVPolicy", "kv_policy"))

# ---- FROZEN alpha decision thresholds (pre-registered; DECISION_THRESHOLDS.md Part 6F-A #1) ----
ALPHA_STOP = 0.50        # alpha < 0.50 -> improved path too small a share; likely stop
ALPHA_STRONG = 0.70      # alpha > 0.70 -> strong case; run the nsys beta trace
AGG_MIN = 0.15           # aggregate gate (shared with 6F-A)
REALIZABILITY = (0.70, 0.80)   # conservative range (NOT 1.0)

try:
    import torch
except Exception:  # pragma: no cover
    torch = None  # type: ignore


def alpha_decision(alpha, realizability=REALIZABILITY, agg_min=AGG_MIN):
    """Map measured alpha -> {LIKELY_STOP, AMBIGUOUS_NEED_BETA, STRONG_RUN_BETA} + the beta needed to
    clear the aggregate gate. Pure/CPU-testable. beta_needed = agg_min / (alpha * r); a value <= ~0.7
    is plausible for long-context decode, > 1 is impossible (stop)."""
    if not isinstance(alpha, (int, float)) or not (0.0 <= alpha <= 1.0):
        return {"verdict": "UNAVAILABLE", "reason": "alpha missing/out of range"}
    if alpha < ALPHA_STOP:
        v = "LIKELY_STOP"
    elif alpha > ALPHA_STRONG:
        v = "STRONG_RUN_BETA"
    else:
        v = "AMBIGUOUS_NEED_BETA"
    beta_needed = {f"r{int(r*100)}": (round(agg_min / (alpha * r), 4) if alpha > 0 else None)
                   for r in realizability}
    feasible = {k: (bn is not None and bn <= 1.0) for k, bn in beta_needed.items()}
    return {"verdict": v, "alpha": round(alpha, 4),
            "beta_needed_to_clear_15pct": beta_needed, "beta_feasible_le_1": feasible,
            "thresholds": {"stop_below": ALPHA_STOP, "strong_above": ALPHA_STRONG,
                           "realizability": list(realizability)},
            "note": "beta = decode-attention-block share of the whole step (needs an nsys trace). "
                    "aggregate ~= alpha x beta x realizability; beta_needed is what clears 15%."}


def _oracle_cosine(out, ref):
    a = out.reshape(-1).to(torch.float32); b = ref.reshape(-1).to(torch.float32)
    return float((a @ b) / (a.norm() * b.norm() + 1e-12))


def run(contexts, iters, H_kv, D, G, BS, v_group_size, n_protect, seed=0):
    import route_a_builder as RB
    import unzip_bound_probe as P
    import int4_fused_attention_kernel as RA
    if not getattr(RA, "_HAVE_TRITON", False):
        raise RuntimeError("Triton not available — decode kernel cannot launch")
    entry = RA.fused_protected_k_decode_attention

    def call_kernel(kw):
        return entry(kw["q"], kw["k_packed"], kw["k_scale"], kw["k_offset"], kw["k_fp16"],
                     kw["protect_mask"], kw["v_packed"], kw["v_scale"], kw["v_offset"],
                     group_size_k=kw["group_size_k"], group_size_v=kw["group_size_v"],
                     asymmetric=kw["asymmetric"])

    per_ctx = {}
    for ctx in contexts:
        # --- decode kernel (head-major inputs, the production standard read) ---
        kw, meta = RB.make_kernel_inputs(ctx, H_kv=H_kv, D=D, G=G, BS=BS,
                                         v_group_size=v_group_size, seed=seed, device="cuda")
        out = call_kernel(kw)
        ref = RB.reference_fp_attention(meta).to(out.device)          # fp attention on original K/V
        cos = _oracle_cosine(out, ref)
        kernel_med, kernel_p95 = P._time_dist(lambda: call_kernel(kw), iters)

        # --- standard-path permute-copy the layout ELIMINATES (native (S,H,*) -> head-major) ---
        ten, geom = P._build_inputs(ctx, H_kv, D, BS, v_group_size, n_protect, seed, "cuda")

        def copy_step():
            a = ten["k_packed"].permute(1, 0, 2).contiguous()
            b = ten["k_fp16"].permute(1, 0, 2).contiguous()
            c = ten["v_packed"].permute(1, 0, 2).contiguous()
            return a.numel() + b.numel() + c.numel()
        copy_med, copy_p95 = P._time_dist(copy_step, iters)

        # --- raw unzip read (both layouts) for the gather-path framing / continuity ---
        uc_med, uc_p95 = P._time_dist(lambda: P._launch(ten, geom, P.MODE_FULL, P.PROT_COMPACT, 0), iters)
        pl = P._to_pagelocal(ten, geom)
        up_med, up_p95 = P._time_dist(lambda: P._launch(pl, geom, P.MODE_FULL, P.PROT_COMPACT, 1), iters)

        alpha_copy = copy_med / (copy_med + kernel_med) if (copy_med + kernel_med) > 0 else float("nan")
        alpha_unzip = up_med / kernel_med if kernel_med > 0 else float("nan")
        per_ctx[str(ctx)] = {
            "permute_copy_ms": {"median": copy_med, "p95": copy_p95},
            "decode_kernel_ms": {"median": kernel_med, "p95": kernel_p95},
            "unzip_current_ms": {"median": uc_med, "p95": uc_p95},
            "unzip_pagelocal_ms": {"median": up_med, "p95": up_p95},
            "decode_kernel_oracle_cosine": round(cos, 5),
            "alpha_copy": round(alpha_copy, 4),          # standard-path: page-local removes the copy
            "alpha_unzip_of_kernel": round(alpha_unzip, 4),  # gather-path reference
            "S_kv": meta["S_kv"], "iters": iters,
        }
        print(f"  ctx={ctx:6} copy={copy_med:.4f} kernel={kernel_med:.4f} "
              f"alpha_copy={alpha_copy:.3f} | unzip cur={uc_med:.4f} pl={up_med:.4f} | oracle_cos={cos:.4f}")
    return per_ctx


def build_verdict(per_ctx, decision_ctx=None):
    ctxs = sorted((int(k) for k in per_ctx), key=int)
    dc = int(decision_ctx) if decision_ctx else ctxs[-1]
    row = per_ctx[str(dc)]
    dec = alpha_decision(row["alpha_copy"])
    return {"decision_context": dc, "alpha_copy": row["alpha_copy"],
            "alpha_by_context": {k: per_ctx[k]["alpha_copy"] for k in map(str, ctxs)},
            "decision": dec,
            "oracle_cosine": row["decode_kernel_oracle_cosine"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="6F-A measurement #1: alpha = decode-path share the layout improves")
    ap.add_argument("--contexts", default="4096 16384 32768")
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--h-kv", type=int, default=4)
    ap.add_argument("--head-dim", type=int, default=128)
    ap.add_argument("--gqa-g", type=int, default=7)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--v-group-size", type=int, default=32)
    ap.add_argument("--n-protect", type=int, default=5)
    ap.add_argument("--out", default=os.path.join(_HERE, "runs", "alpha_decode_share.json"))
    a = ap.parse_args(argv)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)

    def bail(msg):
        json.dump({"label": "UNAVAILABLE", "error": msg, "per_ctx": {}}, open(a.out, "w"), indent=2)
        print(f"[UNAVAILABLE] {msg} -> {a.out}")
        return 3

    if torch is None:
        return bail("torch import failed")
    if not torch.cuda.is_available():
        return bail("no CUDA GPU")
    try:
        import int4_fused_attention_kernel  # noqa: F401
    except Exception as e:  # noqa: BLE001
        return bail(f"decode kernel import failed: {e}")
    ctxs = [int(c) for c in a.contexts.split()]
    try:
        per_ctx = run(ctxs, a.iters, a.h_kv, a.head_dim, a.gqa_g, a.bs, a.v_group_size, a.n_protect)
    except Exception as e:  # noqa: BLE001
        return bail(f"measurement failed: {e}")
    verdict = build_verdict(per_ctx)
    p = torch.cuda.get_device_properties(0)
    blob = {"label": "GPU-measured", "measurement": "6fa_alpha_decode_share",
            "device": {"name": p.name, "sm_count": p.multi_processor_count},
            "geom": {"H_kv": a.h_kv, "D": a.head_dim, "G": a.gqa_g, "BS": a.bs, "n_protect": a.n_protect},
            "per_ctx": per_ctx, "verdict": verdict,
            "note": ("alpha_copy = permute_copy / (permute_copy + decode_kernel): the standard production "
                     "decode path (int4_protected_k_cache.py:520-548) permute-copies the WHOLE KV native->"
                     "head-major EVERY step; page-local (store-as-consumed) eliminates it. alpha is the "
                     "share of the (copy+kernel) block that page-local removes. Decode-kernel correctness "
                     "oracle-checked (cosine vs fp reference). MODELED step: beta (attn-block share of the "
                     "step) still needs an nsys trace; beta_needed reported. No 6F-C code.")}
    json.dump(blob, open(a.out, "w"), indent=2)
    d = verdict["decision"]
    print(f"\nALPHA (copy-share, ctx={verdict['decision_context']}) = {verdict['alpha_copy']} -> {d['verdict']}")
    print(f"  beta needed to clear 15%: {d['beta_needed_to_clear_15pct']} (feasible<=1: {d['beta_feasible_le_1']})")
    print(f"  decode-kernel oracle cosine = {verdict['oracle_cosine']} (want >= 0.99)")
    print(f"  -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
