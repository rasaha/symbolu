#!/usr/bin/env python3
"""QuaRot/SpinQuant-style rotation test for int4 K — training-free.

Does rotating K (post-RoPE) by an orthogonal matrix BEFORE int4 quantization make it
more quantizable — i.e. reduce the need for the protected-channel sidecar — WITHOUT
any fine-tuning? This is the higher-EV lever flagged by KV_QAT_PILOT_RESULT.md after
the (negative) KV-QAT pilot.

Mechanism (computational invariance): rotate Q and K (post-RoPE) by the same
orthogonal R, so attention scores Q·K are unchanged (R Rᵀ = I); then quantize the
ROTATED K. A Hadamard R spreads the outlier channels — the exact thing protect-K
babysits — across all dims, so plain int4 holds up better. V is left bf16 to ISOLATE
the K effect (K is the dominant failure / the channel protect exists for).

Primary signal = **K quant error** (raw vs rotated) — NOT argmax-ceiling-bound.
Secondary = int4-vs-bf16 token-agreement (raw-K-int4 vs rotated-K-int4).

    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_rotation_test.py --model Qwen/Qwen2.5-7B-Instruct --group-size 128
"""
from __future__ import annotations

import argparse
import sys


def hadamard(torch, n, device, dtype):
    """Normalized Sylvester-Hadamard (orthonormal). n must be a power of 2."""
    H = torch.ones(1, 1, device=device, dtype=torch.float32)
    while H.shape[0] < n:
        H = torch.cat([torch.cat([H, H], 1), torch.cat([H, -H], 1)], 0)
    return (H / (n ** 0.5)).to(dtype)


def rand_orth(torch, n, device, dtype):
    q, _ = torch.linalg.qr(torch.randn(n, n))
    return q.to(device=device, dtype=dtype)


def install_k_quant_hook(torch, mgr, R, err):
    """Wrap qwen2 apply_rotary_pos_emb: optionally rotate (q,k) by R, then quantize K.
    Accumulates relative K quant error into err=[num,den]. R=None -> raw (no rotation)."""
    import transformers.models.qwen2.modeling_qwen2 as qm
    orig = qm.apply_rotary_pos_emb

    def wrap(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig(q, k, cos, sin, *a, **kw)
        if R is not None:
            q_emb = torch.matmul(q_emb, R)
            k_emb = torch.matmul(k_emb, R)
        b, h, s, d = k_emb.shape
        flat = k_emb.permute(0, 2, 1, 3).reshape(b * s, h, d)
        k_lossy, _ = mgr.round_trip_kv(flat, flat)
        err[0] += float((k_lossy - flat).norm())
        err[1] += float(flat.norm())
        return q_emb, k_lossy.reshape(b, s, h, d).permute(0, 2, 1, 3).contiguous()
    qm.apply_rotary_pos_emb = wrap
    return lambda: setattr(qm, "apply_rotary_pos_emb", orig)


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
    ap.add_argument("--group-size", type=int, default=128)
    ap.add_argument("--rotation", choices=["hadamard", "random"], default="hadamard")
    ap.add_argument("--n-seqs", type=int, default=32)
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
    if args.rotation == "hadamard" and (D & (D - 1)) == 0:
        R = hadamard(torch, D, dev, torch.bfloat16)
        rot_name = f"hadamard({D})"
    else:
        R = rand_orth(torch, D, dev, torch.bfloat16)
        rot_name = f"random-orthogonal({D})" + ("" if (D & (D - 1)) == 0 else " [D not pow2]")
    print(f"[rot-test] model={args.model} group_size={args.group_size} rotation={rot_name} "
          f"dev={dev} (K-only quant, V bf16)", flush=True)

    seqs = build_seqs(torch, tok, args.n_seqs, args.seq_len, args.dataset, args.dataset_config)

    @torch.no_grad()
    def preds(ids):
        return model(input_ids=ids).logits[0, :-1].argmax(-1)

    err_raw, err_rot = [0.0, 0.0], [0.0, 0.0]
    m_raw = m_rot = total = 0
    for i, ids in enumerate(seqs):
        ids = ids.to(dev)
        p_bf16 = preds(ids)
        r = install_k_quant_hook(torch, mgr, None, err_raw)
        try:
            p_raw = preds(ids)
        finally:
            r()
        r = install_k_quant_hook(torch, mgr, R, err_rot)
        try:
            p_rot = preds(ids)
        finally:
            r()
        m_raw += int((p_bf16 == p_raw).sum())
        m_rot += int((p_bf16 == p_rot).sum())
        total += int(p_bf16.numel())
        if i < 2 or (i + 1) % 8 == 0:
            print(f"[seq {i}] Kerr raw={err_raw[0]/max(1e-9,err_raw[1]):.4f} "
                  f"rot={err_rot[0]/max(1e-9,err_rot[1]):.4f}  "
                  f"agree raw={m_raw/max(1,total):.4f} rot={m_rot/max(1,total):.4f}", flush=True)

    kerr_raw = err_raw[0] / max(1e-9, err_raw[1])
    kerr_rot = err_rot[0] / max(1e-9, err_rot[1])
    a_raw, a_rot = m_raw / max(1, total), m_rot / max(1, total)
    print(f"\n[rot-test] {args.model}  (group_size={args.group_size}, {rot_name})")
    print(f"  K quant rel-error : raw={kerr_raw:.4f}  rotated={kerr_rot:.4f}  "
          f"-> rotation {'REDUCES' if kerr_rot < kerr_raw else 'does NOT reduce'} it "
          f"by {100*(kerr_raw-kerr_rot)/max(1e-9,kerr_raw):+.1f}%")
    print(f"  token-agreement   : raw-K-int4={a_raw:.4f}  rotated-K-int4={a_rot:.4f}  "
          f"(Δ {a_rot-a_raw:+.4f})")
    print("  [primary = K quant error; lower with rotation => QuaRot mechanism works => "
          "protect-K may be reducible WITHOUT training]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
