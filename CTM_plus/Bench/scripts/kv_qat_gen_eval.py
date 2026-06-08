#!/usr/bin/env python3
"""KV-QAT HARD-REGIME eval — free-generation int4-KV agreement.

The teacher-forced eval (kv_qat_eval.py) was near-ceiling (~0.95) — too easy to
discriminate. This is the harsh regime the brief's naive-int4 0.533 lives in:
**greedy free generation**, where one int4-induced divergence CASCADES. To keep the
quantization faithful (not the near-lossless single-token decode-quant), generation
runs with use_cache=False so each step re-quantizes the FULL K/V block per-channel.

For each prompt: greedy-generate G tokens with bf16 KV and with int4 KV (post-RoPE
round_trip_kv on K + V), then compare the two generations:
  - agreement      = fraction of the G positions that match
  - prefix-match    = how many leading tokens agree before the first divergence

Run base / b0 / b1; the question: does int4 finally bite here, and does B1 (KV-QAT)
beat B0 (control) where it matters?

    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_gen_eval.py --model Qwen/Qwen2.5-7B-Instruct
"""
from __future__ import annotations

import argparse
import sys


def install_int4_inference_hooks(torch, model, mgr):
    """Quantize K (POST-RoPE) + V via round_trip_kv at inference. Returns restore()."""
    import transformers.models.qwen2.modeling_qwen2 as qm
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


def build_prompts(torch, tok, n, plen, dataset, config):
    from datasets import load_dataset
    ds = load_dataset(dataset, config, split="test", streaming=True)
    buf, prompts = [], []
    for row in ds:
        t = row.get("text") or ""
        if not t:
            continue
        buf.extend(tok(t, add_special_tokens=False)["input_ids"])
        while len(buf) >= plen:
            prompts.append(torch.tensor(buf[:plen], dtype=torch.long)[None, :])
            buf = buf[plen:]
            if len(prompts) >= n:
                return prompts
    if not prompts:
        raise RuntimeError("no prompts built")
    return prompts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--group-size", type=int, default=32)
    ap.add_argument("--n-prompts", type=int, default=16)
    ap.add_argument("--prompt-len", type=int, default=128)
    ap.add_argument("--gen", type=int, default=48)
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
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    model.config.use_cache = False
    mgr = INT4CacheKVRouteA(
        k_group_size=args.group_size, v_group_size=args.group_size, asymmetric=True,
        bits=4, sink_size=0, num_kv_heads=model.config.num_key_value_heads,
        kernel_backend="dequant_fallback")
    print(f"[gen-eval] model={args.model} dev={dev} n={args.n_prompts} plen={args.prompt_len} "
          f"gen={args.gen} group_size={args.group_size}  (free-generation, use_cache=False)", flush=True)

    prompts = build_prompts(torch, tok, args.n_prompts, args.prompt_len,
                            args.dataset, args.dataset_config)

    @torch.no_grad()
    def gen(ids):
        out = model.generate(ids, max_new_tokens=args.gen, do_sample=False, num_beams=1,
                             use_cache=False, pad_token_id=pad)
        return out[0, ids.shape[1]:]

    matched = total = prefix_sum = 0
    for i, ids in enumerate(prompts):
        ids = ids.to(dev)
        g_bf16 = gen(ids)
        restore = install_int4_inference_hooks(torch, model, mgr)
        try:
            g_int4 = gen(ids)
        finally:
            restore()
        n = min(g_bf16.numel(), g_int4.numel())
        eq = (g_bf16[:n] == g_int4[:n])
        matched += int(eq.sum())
        total += n
        # longest common prefix
        pre = 0
        for j in range(n):
            if bool(eq[j]):
                pre += 1
            else:
                break
        prefix_sum += pre
        if i < 2 or (i + 1) % 4 == 0:
            print(f"[prompt {i}] agreement={matched/max(1,total):.4f}  "
                  f"mean_prefix={prefix_sum/(i+1):.1f}/{args.gen}", flush=True)

    agree = matched / max(1, total)
    print(f"\n[gen-eval] {args.model}  (group_size={args.group_size}, gen={args.gen})")
    print(f"  free-generation int4-vs-bf16 agreement = {agree:.4f}  "
          f"mean common-prefix = {prefix_sum/len(prompts):.1f}/{args.gen}")
    print("  [HARD regime: low here = int4 finally bites; compare base/b0/b1, effect = b1 - b0]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
