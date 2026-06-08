#!/usr/bin/env python3
"""Downstream resolver — does head-wise bit allocation (Option 1) actually beat
int4_protected's channel-bf16-protect on MODEL QUALITY, or only on recon error?

The headwise probe showed head-mixed has ~20% lower K *reconstruction* error. But
int4_protected's protect was validated DOWNSTREAM, where it preserves the outlier
channels that catastrophically break attention. This resolves which matters by
applying each K scheme at inference (FIXED, calibrated-once per (layer,head) -- the
way int4_protected ships) and measuring real quality:

  schemes (K-only; V stays bf16 to isolate the K scheme):
    bf16        -- reference (no quant)
    uniform     -- int4 per-channel, 4 bits
    protect     -- int4 + top-p% channels per (layer,head) at bf16  [int4_protected]
    head-mixed  -- per-(layer,head) bit allocation by sensitivity   [Option 1]
  metrics:
    perplexity  -- mean NLL on held-out text (stable, sensitive, average-case)
    gen-agree   -- free-generation int4-vs-bf16 token agreement (harsh hard-tail)

Verdict logic:
  head-mixed wins BOTH  -> genuine upgrade to int4_protected's allocation.
  protect wins gen-agree (esp. if it loses ppl) -> protect's value IS the hard-tail
    outlier preservation that recon error / avg ppl miss -> affirms current design.

    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_downstream_resolver.py --model Qwen/Qwen2.5-7B-Instruct
"""
from __future__ import annotations

import argparse
import math
import sys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--protect-frac", type=float, default=0.04)
    ap.add_argument("--calib-seqs", type=int, default=4)
    ap.add_argument("--ppl-seqs", type=int, default=16)
    ap.add_argument("--seq-len", type=int, default=512)
    ap.add_argument("--gen-prompts", type=int, default=12)
    ap.add_argument("--gen", type=int, default=32)
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
    pad = tok.pad_token_id if tok.pad_token_id is not None else tok.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa").to(dev).eval()
    model.config.use_cache = False
    L = int(model.config.num_hidden_layers)
    Hn = int(model.config.num_key_value_heads)
    qm = rotary_module(model)
    orig = qm.apply_rotary_pos_emb
    print(f"[resolver] model={args.model} dev={dev} layers={L} kv_heads={Hn} "
          f"protect_frac={args.protect_frac}  (K-scheme only, V bf16)", flush=True)

    def q_per_channel(x, bits):
        levels = (1 << bits) - 1
        xmin = x.amin(0, keepdim=True)
        scale = ((x.amax(0, keepdim=True) - xmin) / levels).clamp_min(1e-8)
        return ((x - xmin) / scale).round().clamp(0, levels) * scale + xmin

    def seqs(n, split="test"):
        from datasets import load_dataset
        ds = load_dataset(args.dataset, args.dataset_config, split=split, streaming=True)
        buf, out = [], []
        for row in ds:
            t = row.get("text") or ""
            if not t:
                continue
            buf.extend(tok(t, add_special_tokens=False)["input_ids"])
            while len(buf) >= args.seq_len:
                out.append(torch.tensor(buf[:args.seq_len], dtype=torch.long)[None, :])
                buf = buf[args.seq_len:]
                if len(out) >= n:
                    return out
        return out

    # ---- calibrate fixed per-(layer,head) schemes ---------------------------------
    mag = [torch.zeros(Hn, model.config.head_dim if hasattr(model.config, "head_dim")
                       else model.config.hidden_size // model.config.num_attention_heads,
                       device=dev) for _ in range(L)]
    D = mag[0].shape[1]
    sens = [torch.zeros(Hn, device=dev) for _ in range(L)]
    snorm = [torch.zeros(Hn, device=dev) for _ in range(L)]
    cc = [0]

    def calib_hook(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig(q, k, cos, sin, *a, **kw)
        li = cc[0] % L; cc[0] += 1
        b, h, s, d = k_emb.shape
        f = k_emb.permute(0, 2, 1, 3).reshape(b * s, h, d).float()
        mag[li] = torch.maximum(mag[li], f.abs().amax(0))
        for hh in range(h):
            sens[li][hh] += (q_per_channel(f[:, hh:hh + 1], 4) - f[:, hh:hh + 1]).norm()
            snorm[li][hh] += f[:, hh:hh + 1].norm()
        return q_emb, k_emb
    qm.apply_rotary_pos_emb = calib_hook
    with torch.no_grad():
        for ids in seqs(args.calib_seqs):
            model(input_ids=ids.to(dev))
    qm.apply_rotary_pos_emb = orig

    kchan = max(1, int(round(args.protect_frac * D)))
    target_avg = 4 + (16 - 4) * args.protect_frac
    protect_mask, head_bits = [], []
    for li in range(L):
        thr = mag[li].topk(kchan, dim=-1).values[..., -1:]            # (H,1)
        protect_mask.append((mag[li] >= thr))                         # (H,D) bool
        s = (sens[li] / snorm[li].clamp_min(1e-9)).tolist()
        bits = [4] * Hn
        order = sorted(range(Hn), key=lambda h: -s[h])
        i = 0
        while sum(bits) / Hn < target_avg and min(bits) < 12:
            bits[order[i % Hn]] += 1; i += 1
        head_bits.append(bits)
    avg_protect = 4 * (1 - kchan / D) + 16 * (kchan / D)
    avg_head = sum(sum(b) / Hn for b in head_bits) / L
    print(f"[resolver] calibrated: protect {avg_protect:.2f} bits, head-mixed {avg_head:.2f} bits "
          f"(example head_bits[0]={head_bits[0]})", flush=True)

    # ---- scheme hooks --------------------------------------------------------------
    def make_hook(scheme):
        c = [0]

        def hook(q, k, cos, sin, *a, **kw):
            q_emb, k_emb = orig(q, k, cos, sin, *a, **kw)
            li = c[0] % L; c[0] += 1
            b, h, s, d = k_emb.shape
            f = k_emb.permute(0, 2, 1, 3).reshape(b * s, h, d).float()
            if scheme == "uniform":
                kq = q_per_channel(f, 4)
            elif scheme == "protect":
                q4 = q_per_channel(f, 4)
                kq = torch.where(protect_mask[li].unsqueeze(0), f, q4)
            else:  # head-mixed
                kq = torch.cat([q_per_channel(f[:, hh:hh + 1], head_bits[li][hh])
                                for hh in range(h)], dim=1)
            return q_emb, kq.to(k_emb.dtype).reshape(b, s, h, d).permute(0, 2, 1, 3).contiguous()
        return hook

    @torch.no_grad()
    def perplexity(scheme):
        if scheme != "bf16":
            qm.apply_rotary_pos_emb = make_hook(scheme)
        tot, ntok = 0.0, 0
        try:
            for ids in seqs(args.ppl_seqs):
                ids = ids.to(dev)
                loss = model(input_ids=ids, labels=ids).loss
                tot += float(loss) * (ids.numel() - 1); ntok += ids.numel() - 1
        finally:
            qm.apply_rotary_pos_emb = orig
        return math.exp(tot / max(1, ntok))

    @torch.no_grad()
    def gen_agree(scheme):
        prompts = seqs(args.gen_prompts)
        prompts = [p[:, :128] for p in prompts]

        def g(ids, hooked):
            if hooked:
                qm.apply_rotary_pos_emb = make_hook(scheme)
            try:
                out = model.generate(ids, max_new_tokens=args.gen, do_sample=False,
                                     num_beams=1, use_cache=False, pad_token_id=pad)
            finally:
                qm.apply_rotary_pos_emb = orig
            return out[0, ids.shape[1]:]
        m = t = 0
        for ids in prompts:
            ids = ids.to(dev)
            gb, gi = g(ids, False), g(ids, True)
            n = min(gb.numel(), gi.numel())
            m += int((gb[:n] == gi[:n]).sum()); t += n
        return m / max(1, t)

    ppl_bf16 = perplexity("bf16")
    print(f"\n[resolver] {args.model}   (bf16 ppl ref = {ppl_bf16:.3f})")
    print(f"  {'scheme':<12} {'ppl':>8} {'ppl-gap':>9} {'gen-agree':>10}")
    rows = {}
    for scheme, label in (("uniform", "uniform-4b"), ("protect", "protect[i4p]"),
                          ("head-mixed", "head-mixed")):
        p = perplexity(scheme); a = gen_agree(scheme)
        rows[scheme] = (p, a)
        print(f"  {label:<12} {p:>8.3f} {p-ppl_bf16:>+9.3f} {a:>10.4f}", flush=True)
    pc, hc = rows["protect"], rows["head-mixed"]
    print(f"\n  verdict: protect ppl={pc[0]:.3f}/agree={pc[1]:.4f}  vs  "
          f"head-mixed ppl={hc[0]:.3f}/agree={hc[1]:.4f}")
    ppl_win = "head-mixed" if hc[0] < pc[0] else "protect"
    agr_win = "head-mixed" if hc[1] > pc[1] else "protect"
    print(f"  -> perplexity favors {ppl_win}; gen-agreement favors {agr_win}")
    if ppl_win == agr_win == "head-mixed":
        print("  => HEAD-MIXED wins downstream too: real upgrade to int4_protected allocation")
    elif agr_win == "protect":
        print("  => PROTECT holds the hard tail: its value is outlier preservation recon-error missed")
    else:
        print("  => SPLIT: head-mixed better avg (ppl), protect better hard-tail (gen) -> nuanced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
