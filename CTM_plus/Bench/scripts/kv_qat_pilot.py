#!/usr/bin/env python3
"""KV-aware fine-tune PILOT — does training for int4 KV recover quality without
the protect sidecar? (KV_AWARE_TRAINING_EXPERIMENT_DESIGN.md, pilot stage.)

Trains Qwen2.5-7B with LoRA while its attention sees the EXACT inference int4
distortion (INT4CacheKVRouteA.round_trip_kv) via a straight-through estimator.

Arms (the headline effect is B1 - B0, which isolates KV-awareness from FT drift):
  A0  base model, NO training — an EVAL baseline (no run here; eval the base model).
  --arm b0   CONTROL: vanilla LoRA FT, NO fake-quant.
  --arm b1   KV-QAT: fake-quant K (POST-RoPE) + V every layer, every step.
             round_trip_kv (dequant_fallback) is naive int4 (0% protect), so b1 is
             the design's 0%-protect arm; --group-size 128 = the coarse-group (B3).

Modes:
  --smoke    2 steps on the REAL 7B; prints hook location, #layers hooked, K/V
             shapes, dtype before/after, fired counts, mean |perturbation|; FAILS
             on zero perturbation or too few layers hooked.
  --overfit  ~40 steps on 16 fixed synthetic examples; FAILS unless loss decreases,
             LoRA weights move, and the hook fires every step. Proves learning.

Eval (token-agreement vs bf16, + the sidecar-reduction sweep) is a separate step on
the merged model — see KV_QAT_PILOT_RUNBOOK.md.
"""
from __future__ import annotations

import argparse
import sys


# --------------------------------------------------------------------------- stats
def new_stats() -> dict:
    s = {"hook_loc": None, "n_v_hooks": 0, "n_layers": 0}
    for w in ("k", "v"):
        s[f"{w}_fired"] = 0
        s[f"{w}_shape"] = None
        s[f"{w}_dtype"] = None          # (in, out)
        s[f"{w}_pert_sum"] = 0.0
        s[f"{w}_pert_n"] = 0
    return s


def _record(stats, which, flat_in, fake_out):
    stats[f"{which}_fired"] += 1
    stats[f"{which}_shape"] = tuple(flat_in.shape)
    stats[f"{which}_dtype"] = (str(flat_in.dtype), str(fake_out.dtype))
    stats[f"{which}_pert_sum"] += float((fake_out.detach() - flat_in.detach()).abs().float().mean())
    stats[f"{which}_pert_n"] += 1


def mean_pert(stats, which) -> float:
    return stats[f"{which}_pert_sum"] / max(1, stats[f"{which}_pert_n"])


# --------------------------------------------------------------------------- hooks
def install_post_rope_hooks(torch, model, mgr, ste_fake_quant, stats):
    """POST-RoPE K (wrap qwen2 apply_rotary_pos_emb — rotated K is what the int4
    cache stores at inference) + V via v_proj forward-hook. Returns restore()."""
    import transformers.models.qwen2.modeling_qwen2 as qm
    if not hasattr(qm, "apply_rotary_pos_emb"):
        raise RuntimeError("transformers qwen2 has no apply_rotary_pos_emb; "
                           "use --pre-rope or adapt the hook to this version")
    stats["hook_loc"] = "post-RoPE"
    orig_rope = qm.apply_rotary_pos_emb

    def fq_k(k_embed):
        b, h, s, d = k_embed.shape
        flat = k_embed.permute(0, 2, 1, 3).reshape(b * s, h, d)
        with torch.no_grad():
            k_lossy, _ = mgr.round_trip_kv(flat, flat)
        fake = ste_fake_quant(flat, k_lossy)
        _record(stats, "k", flat, fake)
        return fake.reshape(b, s, h, d).permute(0, 2, 1, 3).contiguous()

    def rope_kqat(q, k, cos, sin, *a, **kw):
        q_emb, k_emb = orig_rope(q, k, cos, sin, *a, **kw)
        return q_emb, fq_k(k_emb)
    qm.apply_rotary_pos_emb = rope_kqat

    handles = _install_v_proj_hooks(torch, model, mgr, ste_fake_quant, stats)

    def restore():
        qm.apply_rotary_pos_emb = orig_rope
        for hh in handles:
            hh.remove()
    return restore


def _install_v_proj_hooks(torch, model, mgr, ste_fake_quant, stats):
    def hook(module, inputs, out):
        shape = out.shape
        flat = out.reshape(-1, shape[-1])
        with torch.no_grad():
            _, v_lossy = mgr.round_trip_kv(flat, flat)
        fake = ste_fake_quant(flat, v_lossy)
        _record(stats, "v", flat, fake)
        return fake.reshape(shape)
    handles = []
    for name, module in model.named_modules():
        if name.rsplit(".", 1)[-1] == "v_proj":
            handles.append(module.register_forward_hook(hook))
    stats["n_v_hooks"] = len(handles)
    return handles


def install_pre_rope_hooks(torch, model, mgr, ste_fake_quant, stats):
    """Fallback: hook k_proj + v_proj OUTPUT (pre-RoPE for K). Proven to RUN (smoke
    test) but NOT serving-valid — K quantized before rotation. Unblock only."""
    stats["hook_loc"] = "pre-RoPE (NOT serving-valid)"

    def make(which):
        def hook(module, inputs, out):
            shape = out.shape
            flat = out.reshape(-1, shape[-1])
            with torch.no_grad():
                k_l, v_l = mgr.round_trip_kv(flat, flat)
            fake = ste_fake_quant(flat, k_l if which == "k" else v_l)
            _record(stats, which, flat, fake)
            return fake.reshape(shape)
        return hook
    handles, nv = [], 0
    for name, module in model.named_modules():
        leaf = name.rsplit(".", 1)[-1]
        if leaf == "k_proj":
            handles.append(module.register_forward_hook(make("k")))
        elif leaf == "v_proj":
            handles.append(module.register_forward_hook(make("v")))
            nv += 1
    stats["n_v_hooks"] = nv

    def restore():
        for hh in handles:
            hh.remove()
    return restore


# ---------------------------------------------------------------------------- data
def _synthetic(torch, tokenizer, n, seqlen, seed=0):
    g = torch.Generator().manual_seed(seed)
    return [torch.randint(0, tokenizer.vocab_size, (1, seqlen), generator=g) for _ in range(n)]


def build_batches(torch, tokenizer, args):
    """List of (1, seq_len) int64 tensors. --smoke/--overfit use synthetic (no
    dataset). Otherwise stream a HF dataset and PACK to max_seq_len (long-context-
    inclusive — the int4 distortion compounds with length)."""
    if args.smoke:
        return _synthetic(torch, tokenizer, max(args.steps, 2), 256)
    if args.overfit:
        return _synthetic(torch, tokenizer, 16, 128)      # 16 FIXED examples to memorize
    from datasets import load_dataset
    ds = load_dataset(args.dataset, args.dataset_config, split="train", streaming=True)
    buf, blocks, need = [], [], args.steps * args.grad_accum
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


# --------------------------------------------------------------------------- report
def _print_hook_report(stats):
    print("\n--- hook report ---", flush=True)
    print(f"  location           : {stats['hook_loc']}", flush=True)
    print(f"  layers (cfg)       : {stats['n_layers']}", flush=True)
    print(f"  V hooks installed  : {stats['n_v_hooks']}", flush=True)
    print(f"  fired              : K={stats['k_fired']}  V={stats['v_fired']}", flush=True)
    print(f"  K shape/dtype      : {stats['k_shape']}  {stats['k_dtype']}", flush=True)
    print(f"  V shape/dtype      : {stats['v_shape']}  {stats['v_dtype']}", flush=True)
    print(f"  mean |perturbation|: K={mean_pert(stats,'k'):.5f}  V={mean_pert(stats,'v'):.5f}", flush=True)


# --------------------------------------------------------------------------- train
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=["b0", "b1"], required=True)
    ap.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    ap.add_argument("--group-size", type=int, default=32, help="32=B1, 128=B3(coarse)")
    ap.add_argument("--dataset", default="Salesforce/wikitext",
                    help="HF dataset id (namespace/name; newer hub rejects bare ids)")
    ap.add_argument("--dataset-config", default="wikitext-103-raw-v1")
    ap.add_argument("--text-column", default="text")
    ap.add_argument("--max-seq-len", type=int, default=4096)
    ap.add_argument("--steps", type=int, default=200)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--pre-rope", action="store_true", help="fallback pre-RoPE hook (NOT serving-valid)")
    ap.add_argument("--smoke", action="store_true", help="2-step wiring report on the real model")
    ap.add_argument("--overfit", action="store_true", help="40-step learning sanity on 16 fixed examples")
    ap.add_argument("--merge", action="store_true", help="merge LoRA into base + save (for eval)")
    ap.add_argument("--output", default="kv_qat_out")
    args = ap.parse_args()
    if args.smoke:
        args.steps = 2
    if args.overfit:
        args.steps, args.lr = 40, max(args.lr, 5e-4)

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
          f"mode={'smoke' if args.smoke else 'overfit' if args.overfit else 'train'}", flush=True)

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

    stats = new_stats()
    stats["n_layers"] = int(model.config.num_hidden_layers)
    restore = None
    if args.arm == "b1":
        mgr = INT4CacheKVRouteA(
            k_group_size=args.group_size, v_group_size=args.group_size,
            asymmetric=True, bits=4, sink_size=0,
            num_kv_heads=model.config.num_key_value_heads, kernel_backend="dequant_fallback")
        installer = install_pre_rope_hooks if args.pre_rope else install_post_rope_hooks
        restore = installer(torch, model, mgr, ste_fake_quant, stats)
        print(f"[pilot] KV-QAT hooks installed ({stats['hook_loc']})", flush=True)
    else:
        print("[pilot] arm b0: CONTROL, no fake-quant", flush=True)

    batches = build_batches(torch, tok, args)

    # capture a LoRA weight to confirm it moves (overfit sanity)
    lparam = next((p for n, p in model.named_parameters()
                   if p.requires_grad and "lora" in n.lower()), None)
    w0 = lparam.detach().clone() if lparam is not None else None

    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    losses = []
    try:
        for step in range(args.steps):
            opt.zero_grad(set_to_none=True)
            ids = batches[step % len(batches)].to(dev)
            loss = model(input_ids=ids, labels=ids).loss
            loss.backward()
            opt.step()
            losses.append(float(loss.detach()))
            if step < 3 or (step + 1) % 20 == 0:
                print(f"[step {step}] loss={losses[-1]:.4f}  fired K={stats['k_fired']} V={stats['v_fired']}",
                      flush=True)
    finally:
        if restore is not None:
            restore()

    fired_every = (stats["k_fired"] == args.steps * stats["n_layers"]
                   and stats["v_fired"] == args.steps * stats["n_layers"])

    # ---- mode-specific verdicts ---------------------------------------------------
    if args.smoke:
        _print_hook_report(stats)
        if args.arm == "b1":
            checks = {
                "K fired every layer/step": stats["k_fired"] == args.steps * stats["n_layers"],
                "V fired every layer/step": stats["v_fired"] == args.steps * stats["n_layers"],
                "V hooks == n_layers": stats["n_v_hooks"] == stats["n_layers"],
                "K perturbation > 0": mean_pert(stats, "k") > 0.0,
                "V perturbation > 0": mean_pert(stats, "v") > 0.0,
                "K dtype preserved": stats["k_dtype"] and stats["k_dtype"][0] == stats["k_dtype"][1],
                "V dtype preserved": stats["v_dtype"] and stats["v_dtype"][0] == stats["v_dtype"][1],
            }
        else:
            checks = {"b0 ran (no hooks expected)": stats["k_fired"] == 0 and stats["v_fired"] == 0}
        print("\n--- smoke checks ---", flush=True)
        for k, v in checks.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}", flush=True)
        ok = all(checks.values())
        print(f"kv_qat_pilot SMOKE ({args.arm}): {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    if args.overfit:
        _print_hook_report(stats)
        moved = (w0 is not None) and float((lparam.detach() - w0).norm()) > 0.0
        checks = {
            "loss decreased": losses[-1] < losses[0],
            "LoRA weights updated": moved,
            "hook fired every step (b1) / none (b0)":
                fired_every if args.arm == "b1" else (stats["k_fired"] == 0),
        }
        print(f"\n--- overfit sanity ---  loss {losses[0]:.3f} -> {losses[-1]:.3f}", flush=True)
        for k, v in checks.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}", flush=True)
        ok = all(checks.values())
        print(f"kv_qat_pilot OVERFIT ({args.arm}): {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    # ---- real training: validity guard + save -------------------------------------
    if args.arm == "b1":
        assert fired_every, (
            f"KV-QAT hook fired {stats['k_fired']}K/{stats['v_fired']}V, expected "
            f"{args.steps * stats['n_layers']} each — distortion not applied on every "
            "layer/step; result is INVALID. Run --smoke to debug the hook.")
    print(f"[pilot] done  arm={args.arm}  loss {losses[0]:.3f}->{losses[-1]:.3f}  "
          f"fired K={stats['k_fired']} V={stats['v_fired']}", flush=True)
    out = args.output
    if args.merge:
        print("[pilot] merging LoRA -> base and saving (for int4 eval) ...", flush=True)
        model.merge_and_unload().save_pretrained(out)
    else:
        model.save_pretrained(out)
    tok.save_pretrained(out)
    print(f"[pilot] saved -> {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
