#!/usr/bin/env python3
"""KV-aware fine-tune PILOT — does training for int4 KV recover quality without
the protect sidecar? (KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md, pilot stage.)

Trains Qwen2.5-7B with LoRA while its attention sees the EXACT inference int4
distortion (INT4CacheKVRouteA.round_trip_kv) via a straight-through estimator.
Two arms:

  --arm b0   CONTROL: vanilla LoRA FT, NO fake-quant. Isolates "did the fine-tune
             itself move quality?" from KV-awareness.
  --arm b1   KV-QAT: fake-quant K (POST-RoPE) + V on every layer, every step.
             round_trip_kv on the dequant_fallback path is naive int4 (0% protect),
             so b1 IS the design's "0%-protect" arm. --group-size 128 makes it the
             coarse-group (B3) arm; both via the same path.

The hook is the crux. The CPU smoke test (kv_qat_hook_smoketest.py) proved the
mechanism with a PRE-RoPE hook (wiring only). Here K is quantized POST-RoPE — by
wrapping the module-level ``apply_rotary_pos_emb`` (the rotated K is exactly what
the int4 cache stores at inference) — and V via a v_proj forward-hook (V is not
rotated). ``--pre-rope`` falls back to the proven (but serving-INVALID) pre-RoPE
hook if the rotary wrap fails on your transformers version; a real result requires
post-RoPE.

Validate wiring on the real 7B in ~1 min before a real run:
    PYTHONPATH=KVPolicy python Bench/scripts/kv_qat_pilot.py --arm b1 --smoke

Then B0 then B1 (see KV_QAT_PILOT_RUNBOOK.md). Eval (token-agreement vs bf16) is a
separate step on the merged model — reuses phase6j_quality_comparison.py.
"""
from __future__ import annotations

import argparse
import sys
from typing import List


# --------------------------------------------------------------------------- hooks
def _make_fake_quant_k(torch, mgr, ste_fake_quant, counter):
    """POST-RoPE K fake-quant. k_embed is (B, H_kv, S, D); reshape to the
    quantizer's (num_tokens, H_kv, D) 3-D layout, round-trip + STE, reshape back."""
    def fq_k(k_embed):
        b, h, s, d = k_embed.shape
        flat = k_embed.permute(0, 2, 1, 3).reshape(b * s, h, d)   # (tokens, H, D)
        with torch.no_grad():
            k_lossy, _ = mgr.round_trip_kv(flat, flat)
        fake = ste_fake_quant(flat, k_lossy)
        counter["k"] += 1
        return fake.reshape(b, s, h, d).permute(0, 2, 1, 3).contiguous()
    return fq_k


def install_post_rope_hooks(torch, model, mgr, ste_fake_quant, counter):
    """Wrap qwen2 ``apply_rotary_pos_emb`` (K, post-RoPE) + a v_proj forward-hook
    (V). Returns a restore() callable. Raises if the rotary symbol isn't found."""
    import transformers.models.qwen2.modeling_qwen2 as qm
    if not hasattr(qm, "apply_rotary_pos_emb"):
        raise RuntimeError("transformers qwen2 has no apply_rotary_pos_emb; "
                           "use --pre-rope or adapt the hook to this version")
    orig_rope = qm.apply_rotary_pos_emb
    fq_k = _make_fake_quant_k(torch, mgr, ste_fake_quant, counter)

    def rope_kqat(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig_rope(q, k, cos, sin, *a, **kw)
        return q_emb, fq_k(k_emb)
    qm.apply_rotary_pos_emb = rope_kqat

    handles = _install_v_proj_hooks(torch, model, mgr, ste_fake_quant, counter)

    def restore():
        qm.apply_rotary_pos_emb = orig_rope
        for h in handles:
            h.remove()
    return restore


def _install_v_proj_hooks(torch, model, mgr, ste_fake_quant, counter):
    def hook(module, inputs, out):
        shape = out.shape
        flat = out.reshape(-1, shape[-1])
        with torch.no_grad():
            _, v_lossy = mgr.round_trip_kv(flat, flat)
        fake = ste_fake_quant(flat, v_lossy)
        counter["v"] += 1
        return fake.reshape(shape)
    handles = []
    for name, module in model.named_modules():
        if name.rsplit(".", 1)[-1] == "v_proj":
            handles.append(module.register_forward_hook(hook))
    return handles


def install_pre_rope_hooks(torch, model, mgr, ste_fake_quant, counter):
    """Fallback: hook k_proj + v_proj OUTPUT (pre-RoPE for K). Proven to RUN
    (smoke test), but NOT serving-valid — K is quantized before rotation. Use only
    to unblock wiring; a real experiment result needs install_post_rope_hooks."""
    def make(which):
        def hook(module, inputs, out):
            shape = out.shape
            flat = out.reshape(-1, shape[-1])
            with torch.no_grad():
                k_l, v_l = mgr.round_trip_kv(flat, flat)
            fake = ste_fake_quant(flat, k_l if which == "k" else v_l)
            counter[which] += 1
            return fake.reshape(shape)
        return hook
    handles = []
    for name, module in model.named_modules():
        leaf = name.rsplit(".", 1)[-1]
        if leaf in ("k_proj", "v_proj"):
            handles.append(module.register_forward_hook(make("k" if leaf == "k_proj" else "v")))

    def restore():
        for h in handles:
            h.remove()
    return restore


# ---------------------------------------------------------------------------- data
def build_batches(torch, tokenizer, args) -> List["torch.Tensor"]:
    """Return a list of (1, seq_len) int64 input_id tensors. --smoke uses synthetic
    random ids (no dataset). Otherwise stream a HF dataset, tokenize, and PACK into
    max_seq_len blocks (long-context-inclusive — the int4 distortion compounds with
    length, so short-only data would miss the regime the quality story lives in)."""
    if args.smoke:
        g = torch.Generator().manual_seed(0)
        return [torch.randint(0, tokenizer.vocab_size, (1, 256), generator=g)
                for _ in range(args.steps)]
    from datasets import load_dataset
    ds = load_dataset(args.dataset, args.dataset_config, split="train", streaming=True)
    buf, blocks = [], []
    need = args.steps * args.grad_accum
    for row in ds:
        text = row.get(args.text_column) or ""
        if not text:
            continue
        buf.extend(tokenizer(text, add_special_tokens=False)["input_ids"])
        while len(buf) >= args.max_seq_len:
            blocks.append(torch.tensor(buf[:args.max_seq_len], dtype=torch.long)[None, :])
            buf = buf[args.max_seq_len:]
            if len(blocks) >= need:
                return blocks
    if not blocks:
        raise RuntimeError("no training blocks built — check --dataset/--text-column")
    return blocks


# --------------------------------------------------------------------------- train
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["b0", "b1"], required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--group-size", type=int, default=32, help="32=B1, 128=B3(coarse)")
    ap.add_argument("--dataset", default="wikitext")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    ap.add_argument("--text-column", default="text")
    ap.add_argument("--max-seq-len", type=int, default=4096)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--pre-rope", action="store_true", help="fallback pre-RoPE hook (NOT serving-valid)")
    ap.add_argument("--smoke", action="store_true", help="2-step synthetic wiring check on the real model")
    ap.add_argument("--merge", action="store_true", help="merge LoRA into base + save (for eval)")
    ap.add_argument("--output", default="kv_qat_out")
    args = ap.parse_args()
    if args.smoke:
        args.steps = 2

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig, get_peft_model
    except Exception as e:  # noqa: BLE001
        print(f"PILOT CANNOT RUN: need torch + transformers + peft + datasets ({e})")
        return 2
    from kv_policy.int4_cache_kv_route_a import INT4CacheKVRouteA
    from kv_policy.kv_aware_qat import ste_fake_quant

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[pilot] arm={args.arm} model={args.model} dev={dev} steps={args.steps} "
          f"group_size={args.group_size} hook={'pre' if args.pre_rope else 'post'}-RoPE "
          f"smoke={args.smoke}", flush=True)

    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, attn_implementation="sdpa")
    model.config.use_cache = False
    model.to(dev)

    lora = LoraConfig(r=args.lora_rank, lora_alpha=2 * args.lora_rank, lora_dropout=0.0,
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()
    model.train()

    counter = {"k": 0, "v": 0}
    restore = None
    if args.arm == "b1":
        mgr = INT4CacheKVRouteA(
            k_group_size=args.group_size, v_group_size=args.group_size,
            asymmetric=True, bits=4, sink_size=0,
            num_kv_heads=model.config.num_key_value_heads,
            kernel_backend="dequant_fallback")
        installer = install_pre_rope_hooks if args.pre_rope else install_post_rope_hooks
        restore = installer(torch, model, mgr, ste_fake_quant, counter)
        print(f"[pilot] KV-QAT hooks installed ({'pre' if args.pre_rope else 'post'}-RoPE)", flush=True)
    else:
        print("[pilot] arm b0: CONTROL, no fake-quant", flush=True)

    batches = build_batches(torch, tok, args)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)

    try:
        running = 0.0
        for step in range(args.steps):
            opt.zero_grad(set_to_none=True)
            ids = batches[step % len(batches)].to(dev)
            loss = model(input_ids=ids, labels=ids).loss
            loss.backward()
            opt.step()
            running += float(loss.detach())
            if step < 3 or (step + 1) % 20 == 0:
                print(f"[step {step}] loss={float(loss.detach()):.4f}  "
                      f"hook_fired k={counter['k']} v={counter['v']}", flush=True)
        avg = running / max(1, args.steps)
    finally:
        if restore is not None:
            restore()

    # wiring guard: b1 MUST have fired the fake-quant; a silent no-op invalidates it.
    if args.arm == "b1":
        assert counter["k"] > 0 and counter["v"] > 0, (
            f"KV-QAT hooks never fired (k={counter['k']} v={counter['v']}) — "
            "the int4 distortion was NOT applied; result is invalid. Check the hook.")

    print(f"[pilot] done  arm={args.arm}  avg_loss={avg:.4f}  "
          f"fired k={counter['k']} v={counter['v']}", flush=True)
    if args.smoke:
        print(f"kv_qat_pilot SMOKE ({args.arm}): "
              f"{'PASS' if (args.arm == 'b0' or (counter['k'] and counter['v'])) else 'FAIL'}")
        return 0

    out = args.output
    if args.merge:
        print("[pilot] merging LoRA -> base and saving (for int4 eval) ...", flush=True)
        merged = model.merge_and_unload()
        merged.save_pretrained(out)
    else:
        model.save_pretrained(out)
    tok.save_pretrained(out)
    print(f"[pilot] saved -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
