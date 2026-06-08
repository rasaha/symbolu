#!/usr/bin/env python3
"""Head-wise mixed-precision probe (Option 1) — is int4_protected (channel-granular
selective precision) better than head-granular bit allocation, at MATCHED avg bits?

int4_protected keeps the top-p% of K *channels* at bf16 (fine-grained). Option 1
(rate-distortion / head-wise) instead gives whole *heads* more or fewer bits by
sensitivity. This probe captures post-RoPE K per (layer, head) and compares, at the
SAME average bit-budget:

  - uniform int4              (4.00 bits)            -- the floor
  - channel-protect p%        (~4 + 12p bits)        -- int4_protected
  - head-mixed (greedy alloc) (matched to above)     -- Option 1

Plus the gating diagnostic: per-head K quant sensitivity. If it concentrates in a
few heads, head-wise has headroom; if it's flat, it can't help.

Lower error at matched bits wins. (Grouping is per-seq per-channel here -- internally
consistent for the COMPARISON; absolute values differ from the group-32 round_trip.)

    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_headwise_probe.py --model Qwen/Qwen2.5-7B-Instruct
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--protect-frac", type=float, default=0.04)
    ap.add_argument("--n-seqs", type=int, default=8)
    ap.add_argument("--seq-len", type=int, default=256)
    ap.add_argument("--dataset", default="Salesforce/wikitext")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    args = ap.parse_args()

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as e:  # noqa: BLE001
        print(f"CANNOT RUN: need torch + transformers + datasets ({e})")
        return 2
    from kv_policy.kv_aware_qat import rotary_module

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    model.config.use_cache = False
    Hn = int(model.config.num_key_value_heads)
    print(f"[headwise] model={args.model} dev={dev} kv_heads={Hn} protect_frac={args.protect_frac}", flush=True)

    def q_per_channel(x, bits):
        levels = (1 << bits) - 1
        xmin = x.amin(0, keepdim=True)
        scale = ((x.amax(0, keepdim=True) - xmin) / levels).clamp_min(1e-8)
        return ((x - xmin) / scale).round().clamp(0, levels) * scale + xmin

    def relerr(a, b):
        return float((a - b).norm()), float(b.norm())

    def channel_protect(f, p, bits=4):
        T, H, D = f.shape
        q = q_per_channel(f, bits)
        k = max(1, int(round(p * D)))
        mag = f.abs().amax(0)                                  # (H, D)
        thr = mag.topk(k, dim=-1).values[..., -1:]            # (H, 1)
        mask = (mag >= thr).unsqueeze(0)                      # (1, H, D)
        avg_bits = bits * (1 - k / D) + 16 * (k / D)
        return torch.where(mask, f, q), avg_bits

    def alloc_head_bits(f, target_avg):
        H = f.shape[1]
        bits = [4] * H
        while sum(bits) / H < target_avg:
            errs = [float((q_per_channel(f[:, h:h + 1], bits[h]) - f[:, h:h + 1]).norm())
                    for h in range(H)]
            h = max(range(H), key=lambda i: errs[i] if bits[i] < 12 else -1.0)
            if bits[h] >= 12:
                break
            bits[h] += 1
        return bits

    def head_mixed(f, bits):
        return torch.cat([q_per_channel(f[:, h:h + 1], bits[h]) for h in range(f.shape[1])], dim=1)

    acc = {k: [0.0, 0.0] for k in ("uniform", "chan", "head")}
    hsens = [[0.0, 0.0] for _ in range(Hn)]
    headbits_sum, chanbits_sum, nlayers = 0.0, 0.0, 0

    qm = rotary_module(model)
    orig = qm.apply_rotary_pos_emb

    def wrap(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig(q, k, cos, sin, *a, **kw)
        b, h, s, d = k_emb.shape
        f = k_emb.permute(0, 2, 1, 3).reshape(b * s, h, d).float()
        nonlocal headbits_sum, chanbits_sum, nlayers
        for n, (a_, b_) in zip(("uniform",), ((q_per_channel(f, 4), f),)):
            e, nrm = relerr(*(a_, b_)); acc[n][0] += e; acc[n][1] += nrm
        for hh in range(h):
            e, nrm = relerr(q_per_channel(f[:, hh:hh + 1], 4), f[:, hh:hh + 1])
            hsens[hh][0] += e; hsens[hh][1] += nrm
        kp, ab = channel_protect(f, args.protect_frac)
        e, nrm = relerr(kp, f); acc["chan"][0] += e; acc["chan"][1] += nrm
        bits = alloc_head_bits(f, ab)
        km = head_mixed(f, bits)
        e, nrm = relerr(km, f); acc["head"][0] += e; acc["head"][1] += nrm
        chanbits_sum += ab; headbits_sum += sum(bits) / h; nlayers += 1
        return q_emb, k_emb
    qm.apply_rotary_pos_emb = wrap

    try:
        from datasets import load_dataset
        ds = load_dataset(args.dataset, args.dataset_config, split="test", streaming=True)
        buf, seqs = [], []
        for row in ds:
            t = row.get("text") or ""
            if not t:
                continue
            buf.extend(tok(t, add_special_tokens=False)["input_ids"])
            while len(buf) >= args.seq_len:
                seqs.append(torch.tensor(buf[:args.seq_len], dtype=torch.long)[None, :])
                buf = buf[args.seq_len:]
                if len(seqs) >= args.n_seqs:
                    break
            if len(seqs) >= args.n_seqs:
                break
        with torch.no_grad():
            for ids in seqs:
                model(input_ids=ids.to(dev))
    finally:
        qm.apply_rotary_pos_emb = orig

    e_u = acc["uniform"][0] / max(1e-9, acc["uniform"][1])
    e_c = acc["chan"][0] / max(1e-9, acc["chan"][1])
    e_h = acc["head"][0] / max(1e-9, acc["head"][1])
    sens = [hsens[i][0] / max(1e-9, hsens[i][1]) for i in range(Hn)]
    print(f"\n[headwise] {args.model}")
    print(f"  per-head K sensitivity (uniform int4 rel-err): "
          + " ".join(f"{s:.3f}" for s in sens))
    print(f"    spread max/min = {max(sens)/max(1e-9,min(sens)):.2f}x "
          f"({'concentrated -> head-wise has headroom' if max(sens)/max(1e-9,min(sens)) > 1.5 else 'flat -> head-wise cannot help much'})")
    print(f"  uniform int4         (4.00 bits) : err={e_u:.4f}")
    print(f"  channel-protect {args.protect_frac:.0%}  ({chanbits_sum/max(1,nlayers):.2f} bits) : err={e_c:.4f}   [int4_protected]")
    print(f"  head-mixed (greedy)  ({headbits_sum/max(1,nlayers):.2f} bits) : err={e_h:.4f}   [Option 1]")
    win = "int4_protected (channel) BETTER" if e_c < e_h else "head-mixed (Option 1) BETTER"
    print(f"  verdict @ matched bits: channel={e_c:.4f} vs head={e_h:.4f} -> {win} "
          f"({abs(e_c-e_h)/max(1e-9,min(e_c,e_h))*100:.0f}% gap)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
