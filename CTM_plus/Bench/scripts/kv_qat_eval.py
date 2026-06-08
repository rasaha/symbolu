#!/usr/bin/env python3
"""KV-QAT eval — int4-KV token-agreement (the sensitive metric the experiment turns on).

For a given model, teacher-force a set of eval sequences and compare the argmax
next-token prediction with **bf16 KV** vs **int4 KV** (post-RoPE round_trip_kv — the
EXACT distortion the pilot trained against, so train==eval parity holds and there is
NO fused_v2 gap). Agreement = fraction of positions where the two predictions match.
Higher = more int4-robust.

Run for all three arms; the headline is B1 - B0 (A0 = base is the floor):
    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_eval.py --model Qwen/Qwen2.5-7B-Instruct
    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_eval.py --model ./kv_qat_b0
    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_eval.py --model ./kv_qat_b1

Decision (KV_QAT_PILOT_RUNBOOK.md): B1 - B0 <= 0 -> KILL (KV-QAT didn't help).
Pilot bar: B1 materially above B0, ideally toward base's protected-int4 0.737.
"""
from __future__ import annotations

import argparse
import sys


def install_int4_inference_hooks(torch, model, mgr):
    """Apply round_trip_kv to K (POST-RoPE) + V at inference. No STE (no backward).
    Returns restore()."""
    from kv_policy.kv_aware_qat import rotary_module
    qm = rotary_module(model)
    orig = qm.apply_rotary_pos_emb

    def fq_k(k):
        b, h, s, d = k.shape
        flat = k.permute(0, 2, 1, 3).reshape(b * s, h, d)
        k_lossy, _ = mgr.round_trip_kv(flat, flat)
        return k_lossy.reshape(b, s, h, d).permute(0, 2, 1, 3).contiguous()

    def rope(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig(q, k, cos, sin, *a, **kw)
        return q_emb, fq_k(k_emb)
    qm.apply_rotary_pos_emb = rope

    def vhook(module, inputs, out):
        shape = out.shape
        flat = out.reshape(-1, shape[-1])
        _, v_lossy = mgr.round_trip_kv(flat, flat)
        return v_lossy.reshape(shape)
    handles = [m.register_forward_hook(vhook)
               for n, m in model.named_modules() if n.rsplit(".", 1)[-1] == "v_proj"]

    def restore():
        qm.apply_rotary_pos_emb = orig
        for hh in handles:
            hh.remove()
    return restore


def build_eval_seqs(torch, tok, n, seqlen, dataset, config):
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
    ap.add_argument("--n-seqs", type=int, default=32)
    ap.add_argument("--seq-len", type=int, default=512)
    ap.add_argument("--dataset", default="Salesforce/wikitext")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    args = ap.parse_args()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:  # noqa: BLE001
        print(f"EVAL CANNOT RUN: need torch + transformers + datasets ({e})")
        return 2
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[eval] model={args.model} dev={dev} n_seqs={args.n_seqs} seq_len={args.seq_len} "
          f"group_size={args.group_size}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    model.config.use_cache = False
    mgr = INT4CacheKVRouteA(
        k_group_size=args.group_size, v_group_size=args.group_size, asymmetric=True,
        bits=4, sink_size=0, num_kv_heads=model.config.num_key_value_heads,
        kernel_backend="dequant_fallback")

    seqs = build_eval_seqs(torch, tok, args.n_seqs, args.seq_len,
                           args.dataset, args.dataset_config)

    @torch.no_grad()
    def preds(ids):
        return model(input_ids=ids).logits[0, :-1].argmax(-1)   # next-token argmax per pos

    matched = total = 0
    for i, ids in enumerate(seqs):
        ids = ids.to(dev)
        p_bf16 = preds(ids)
        restore = install_int4_inference_hooks(torch, model, mgr)
        try:
            p_int4 = preds(ids)
        finally:
            restore()
        matched += int((p_bf16 == p_int4).sum())
        total += int(p_bf16.numel())
        if i < 2 or (i + 1) % 8 == 0:
            print(f"[seq {i}] running agreement = {matched/max(1,total):.4f}", flush=True)

    agree = matched / max(1, total)
    print(f"\n[eval] {args.model}")
    print(f"[eval] int4-KV vs bf16-KV token-agreement = {agree:.4f}  "
          f"({matched}/{total} positions, group_size={args.group_size})")
    print("[eval] (compare base / b0 / b1; the effect is b1 - b0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
