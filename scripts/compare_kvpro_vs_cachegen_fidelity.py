#!/usr/bin/env python3
"""KVPro vs CacheGen — KV-codec FIDELITY at matched bits, on a real model's KV.

Runs on this pod's WORKING env (HF transformers + torch cu121) — NO lmcache, NO vLLM
0.23.0, NO driver wall. It captures real K/V from Qwen2.5-7B (HF, use_cache) and applies
a faithful MODEL of each codec's quantization:

  * CacheGen   = per-channel quantization to `bins` levels (the shipped config: K 16-32,
                 V 16-32 bins) + arithmetic coding. AC is LOSSLESS, so CacheGen's quality
                 loss == the bins-quantization error (computed exactly here); its bytes ≈
                 the entropy of the quantized codes (what AC achieves — reported as bits/elem).
                 NO channel protection.
  * KVPro      = per-channel 4-bit + top-`protect_frac` channels kept at bf16 (protected).
  * naive int4 = per-channel 4-bit, no protection (reference).
  * bf16       = reference (zero error, 16 b).

HEADLINE METRIC: relative reconstruction error on the HIGH-MAGNITUDE K channels (the
attention-critical ones). KVPro protects them (≈0 error); CacheGen quantizes them like any
other (full error) — this is the mechanism behind every hard-tail collapse we measured
(naive int4 / SAW / KVarN). Honest scope: this measures CODEC FIDELITY (a model of bytes +
exact quant error), NOT end-to-end needle accuracy — that needs the live server (Option A).
"""
from __future__ import annotations

import argparse
import math
import sys


def _entropy_bits(codes, bins):
    import torch
    hist = torch.bincount(codes.flatten().to(torch.int64), minlength=bins).float()
    p = hist / hist.sum().clamp(min=1)
    nz = p > 0
    return float(-(p[nz] * torch.log2(p[nz])).sum())   # bits/elem the AC approaches


def _per_channel_quant(x, bins):
    """x: [H, S, D]; quantize per (H, D) channel over S to `bins` levels; return (deq, codes)."""
    import torch
    xmin = x.amin(dim=1, keepdim=True)
    xmax = x.amax(dim=1, keepdim=True)
    scale = (xmax - xmin).clamp(min=1e-8) / (bins - 1)
    codes = torch.round((x - xmin) / scale).clamp(0, bins - 1)
    deq = codes * scale + xmin
    return deq, codes.to(torch.int32)


def _rel_err(orig, recon, mask=None):
    import torch
    o, r = orig.float(), recon.float()
    if mask is not None:
        # mask: [H, D] over channels; broadcast over S
        m = mask.unsqueeze(1)                       # [H,1,D]
        o = o * m
        r = r * m
    num = torch.linalg.vector_norm(r - o)
    den = torch.linalg.vector_norm(o).clamp(min=1e-8)
    return float(num / den)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="KVPro vs CacheGen KV-codec fidelity (real KV, this pod)")
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--protect-frac", type=float, default=0.04)
    ap.add_argument("--cachegen-bins", default="16,32", help="CacheGen bins levels to test")
    ap.add_argument("--prompt-reps", type=int, default=40)
    ap.add_argument("--max-layers", type=int, default=0, help="limit layers (0=all) for speed")
    args = ap.parse_args(argv)

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] needs torch + transformers (working env): {e}", file=sys.stderr)
        return 2

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[1/3] loading {args.model} on {dev} ...")
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, torch_dtype=torch.bfloat16).to(dev).eval()

    # a hard-needle-style prompt: planted codes + distractors in a long context
    body = ("The field archive logged a checksum and a timestamp for the overnight batch. " * args.prompt_reps)
    prompt = (f"{body} The RED code is 48271. {body} The BLUE code is 91043. {body} "
              "Question: what is the RED code?")
    ids = tok(prompt, return_tensors="pt").to(dev)
    print(f"[2/3] forward (use_cache) — prompt tokens: {ids.input_ids.shape[1]}")
    with torch.inference_mode():
        out = model(**ids, use_cache=True)
    pkv = out.past_key_values
    layers = list(pkv) if not hasattr(pkv, "to_legacy_cache") else list(pkv.to_legacy_cache())
    n_layers = len(layers)
    if args.max_layers:
        layers = layers[: args.max_layers]
    print(f"      captured {n_layers} layers; analyzing {len(layers)}")

    bins_list = [int(b) for b in args.cachegen_bins.split(",")]
    pf = args.protect_frac

    # accumulators
    agg = {}  # method -> {"kbits":[], "kerr":[], "ktop":[], "verr":[]}
    def add(m, **kv):
        d = agg.setdefault(m, {})
        for k, v in kv.items():
            d.setdefault(k, []).append(v)

    print(f"[3/3] per-layer codec fidelity (protect_frac={pf}) ...")
    for li, (K, V) in enumerate(layers):
        K = K[0].float()          # [H, S, D]
        V = V[0].float()
        H, S, D = K.shape
        n_prot = max(1, round(D * pf))
        # protected channels = top-magnitude per head (max-abs over S)
        kmag = K.abs().amax(dim=1)                       # [H, D]
        topidx = kmag.topk(n_prot, dim=1).indices        # [H, n_prot]
        protect = torch.zeros(H, D, dtype=torch.bool, device=K.device)
        protect.scatter_(1, topidx, True)

        # --- CacheGen: per-channel quant to `bins` (lossy); AC -> entropy bits ---
        for bins in bins_list:
            kdeq, kcodes = _per_channel_quant(K, bins)
            vdeq, vcodes = _per_channel_quant(V, bins)
            add(f"CacheGen(bins={bins})",
                kbits=_entropy_bits(kcodes, bins), kerr=_rel_err(K, kdeq),
                ktop=_rel_err(K, kdeq, protect), verr=_rel_err(V, vdeq))

        # --- naive int4 (16 levels), no protection ---
        kdeq, _ = _per_channel_quant(K, 16)
        vdeq, _ = _per_channel_quant(V, 16)
        add("naive_int4", kbits=4.0, kerr=_rel_err(K, kdeq),
            ktop=_rel_err(K, kdeq, protect), verr=_rel_err(V, vdeq))

        # --- KVPro: int4 + protected channels at bf16 ---
        kdeq, _ = _per_channel_quant(K, 16)
        kdeq_prot = torch.where(protect.unsqueeze(1), K, kdeq)   # restore protected channels exactly
        # bits/elem: 4 for the (1-pf) quantized + 16 for the pf protected
        kvpro_bits = 4.0 * (1 - pf) + 16.0 * pf
        add("KVPro(int4+protect)", kbits=kvpro_bits, kerr=_rel_err(K, kdeq_prot),
            ktop=_rel_err(K, kdeq_prot, protect), verr=_rel_err(V, vdeq))

    def mean(xs):
        return sum(xs) / len(xs) if xs else float("nan")

    print("\n==================== KV-CODEC FIDELITY (real KV, mean over layers) ====================")
    print(f"{'method':<22}{'K bits/elem':>12}{'K rel-err':>11}{'K rel-err@TOP':>15}{'V rel-err':>11}")
    print("-" * 72)
    order = [m for m in agg if m.startswith("CacheGen")] + ["naive_int4", "KVPro(int4+protect)"]
    for m in order:
        d = agg[m]
        print(f"{m:<22}{mean(d['kbits']):>12.2f}{mean(d['kerr']):>11.4f}"
              f"{mean(d['ktop']):>15.4f}{mean(d['verr']):>11.4f}")
    print("-" * 72)
    print("HEADLINE = 'K rel-err@TOP' (error on the high-attention K channels).")
    print("KVPro protects them -> ~0; CacheGen/naive quantize them -> full error. That gap is the")
    print("mechanism behind the measured hard-tail collapses (naive int4 / SAW / KVarN).")
    print("Bytes: CacheGen 'K bits/elem' is the arithmetic-coding entropy (its real payload); KVPro's")
    print("is the int4+protect nominal. Compare error AT matched bits across rows.")
    print("\n⚠️ Scope: this is CODEC FIDELITY on real KV (exact quant error + AC-entropy bytes), NOT")
    print("end-to-end needle accuracy. The live needle run needs the server (Option A, newer driver).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
