#!/usr/bin/env python3
"""Scale-metadata probe — can rotation kill the per-block scale sidecar (~3.4 GB)?

The Hadamard test (kv_qat_rotation_test.py) targeted the PROTECT-channel sidecar
(~1 GB, outliers) and failed: round_trip_kv is already per-channel, so rotation is
redundant. This probes the DIFFERENT, BIGGER lever from PolarQuant/TurboQuant: the
per-block **scale/xmin metadata** (~3.4 GB).

Mechanism (PolarQuant/TurboQuant-MSE core): normalize K per-vector (÷‖k‖), then
random-rotate. For a unit vector rotated to the sphere, every coordinate follows the
SAME data-independent distribution (≈ N(0, 1/D)). So you can quantize with ONE FIXED
quantizer (range = ±3/√D, set by D alone — NO per-block data-dependent scale),
storing only the per-vector norm. If that matches per-channel int4's error, the
per-block scale grid is droppable -> most of the 3.4 GB sidecar goes.

Compares K quant rel-error (ceiling-free):
  - per-channel int4 (round_trip_kv): low error, but COSTS ~2D/G scale+xmin scalars
    per token·head (8 at G=32, D=128).
  - polar-core: norm + random-rotate + FIXED int4 quantizer -> 1 norm per token·head.

    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_scale_probe.py --model Qwen/Qwen2.5-7B-Instruct --group-size 32
"""
from __future__ import annotations

import argparse
import sys


def polar_core_roundtrip(torch, k, R, bits=4):
    """Normalize per-vector, random-rotate, quantize with a FIXED (data-independent)
    int4 quantizer, dequantize, un-rotate, un-normalize. Only metadata = ‖k‖."""
    D = k.shape[-1]
    kf = k.float()
    norm = kf.norm(dim=-1, keepdim=True).clamp_min(1e-8)        # the only stored scale
    u = kf / norm
    z = torch.matmul(u, R)                                      # (.,.,D)@(D,D) on sphere
    qmax = 2 ** (bits - 1) - 1                                  # 7 for int4
    scale = (3.0 / (D ** 0.5)) / qmax                           # FIXED: ±3·std(=1/√D)
    zq = (z / scale).round().clamp(-(qmax + 1), qmax)
    z_dq = zq * scale
    u_dq = torch.matmul(z_dq, R.transpose(-1, -2))             # un-rotate (Rᵀ = R⁻¹)
    return (u_dq * norm).to(k.dtype)


def build_seqs(torch, tok, n, seqlen, dataset, config):
    from datasets import load_dataset
    ds = load_dataset(dataset, config, split="test", streaming=True)
    buf, seqs = [], []
    for row in ds:
        t = row.get("text") or ""
        if not t:
            continue
        buf.extend(tok(t, add_special_tokens=False)["input_ids"])
        while len(buf) >= seqlen:
            seqs.append(torch.tensor(buf[:seqlen], dtype=torch.long)[None, :])
            buf = buf[seqlen:]
            if len(seqs) >= n:
                return seqs
    if not seqs:
        raise RuntimeError("no eval sequences built")
    return seqs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--group-size", type=int, default=32)
    ap.add_argument("--n-seqs", type=int, default=16)
    ap.add_argument("--seq-len", type=int, default=512)
    ap.add_argument("--dataset", default="Salesforce/wikitext")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    args = ap.parse_args()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:  # noqa: BLE001
        print(f"CANNOT RUN: need torch + transformers + datasets ({e})")
        return 2
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    model.config.use_cache = False
    mgr = INT4CacheKVRouteA(
        k_group_size=args.group_size, v_group_size=args.group_size, asymmetric=True,
        bits=4, sink_size=0, num_kv_heads=model.config.num_key_value_heads,
        kernel_backend="dequant_fallback")
    D = int(getattr(model.config, "head_dim", model.config.hidden_size // model.config.num_attention_heads))
    R = torch.linalg.qr(torch.randn(D, D))[0].to(dev, torch.float32)   # random orthogonal
    print(f"[scale-probe] model={args.model} dev={dev} D={D} group_size={args.group_size}  "
          f"(per-channel int4 vs polar-core fixed-quantizer)", flush=True)

    err_pc, err_pol = [0.0, 0.0], [0.0, 0.0]

    import transformers.models.qwen2.modeling_qwen2 as qm
    orig = qm.apply_rotary_pos_emb

    def wrap(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig(q, k, cos, sin, *a, **kw)
        b, h, s, d = k_emb.shape
        flat = k_emb.permute(0, 2, 1, 3).reshape(b * s, h, d)
        kl_pc, _ = mgr.round_trip_kv(flat, flat)
        kl_pol = polar_core_roundtrip(torch, flat, R)
        f = flat.float()
        err_pc[0] += float((kl_pc.float() - f).norm()); err_pc[1] += float(f.norm())
        err_pol[0] += float((kl_pol.float() - f).norm()); err_pol[1] += float(f.norm())
        return q_emb, k_emb
    qm.apply_rotary_pos_emb = wrap

    try:
        seqs = build_seqs(torch, tok, args.n_seqs, args.seq_len, args.dataset, args.dataset_config)
        with torch.no_grad():
            for i, ids in enumerate(seqs):
                model(input_ids=ids.to(dev))
                if i < 2 or (i + 1) % 4 == 0:
                    print(f"[seq {i}] err per-channel={err_pc[0]/max(1e-9,err_pc[1]):.4f}  "
                          f"polar-core={err_pol[0]/max(1e-9,err_pol[1]):.4f}", flush=True)
    finally:
        qm.apply_rotary_pos_emb = orig

    e_pc = err_pc[0] / max(1e-9, err_pc[1])
    e_pol = err_pol[0] / max(1e-9, err_pol[1])
    meta_pc = 2.0 * D / args.group_size                 # scale+xmin scalars / token·head
    print(f"\n[scale-probe] {args.model}  (D={D}, group_size={args.group_size})")
    print(f"  K quant rel-error : per-channel={e_pc:.4f}   polar-core(fixed)={e_pol:.4f}")
    print(f"  scale metadata    : per-channel={meta_pc:.1f}   polar-core=1.0  scalars/token·head "
          f"({meta_pc:.0f}x less)")
    verdict = ("MATCHES (<=1.25x) -> scale sidecar likely DROPPABLE" if e_pol <= 1.25 * e_pc
               else "WORSE -> fixed quantizer not yet competitive; needs Lloyd-Max/QJL")
    print(f"  verdict: polar-core error is {e_pol/max(1e-9,e_pc):.2f}x per-channel -> {verdict}")
    print("  [if comparable error at 1 scalar vs %.0f, rotation kills most of the ~3.4 GB "
          "scale/xmin sidecar WITHOUT training]" % meta_pc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
