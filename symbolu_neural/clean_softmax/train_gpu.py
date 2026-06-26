"""Single reproducible GPU training entrypoint for the clean-softmax Symbol-U model.

The model and all Symbol-U algorithms are FROZEN — this file only adds a GPU
training loop (mixed precision, gradient accumulation, periodic checkpoint/eval,
all existing diagnostics, automatic final generation). It imports the existing
modules unchanged.

Outputs under --out:
  config.json, vocab.json, train_log.jsonl, ckpt_step*.pt, ckpt.pt,
  metrics.json, samples.txt

Diagnostics preserved (nothing removed): val loss, perplexity, contribution stats
(per-module delta loss + helps-fraction), entropy mean/std, refinement halt prob /
gate / residual norm, memory readiness / residual norm, grad norm, activation norm,
throughput, and final generation samples. Token-change instrumentation is produced
by inspect_generation.py (run by scripts/run_gpu_training.sh on the final ckpt).
"""
from __future__ import annotations

import argparse
import json
import os
import time

import torch
import torch.nn.functional as F

from .config import get_ablation, with_mode, approx_flops_per_token
from .data import CharTokenizer, load_corpus, split_ids, make_batches
from .model import SymbolUSoftmaxModel
from .metrics import val_loss_ppl, ece_and_entropy_corr
from .generate import generate

PROMPTS = ["The ", "Symbol-U ", "The model ", "In this ", "A "]


def amp_setup(device: str, want: bool):
    if device != "cuda" or not want:
        return None, False, torch.float32
    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    scaler = None
    if not bf16:
        try:
            scaler = torch.amp.GradScaler("cuda")
        except Exception:
            scaler = torch.cuda.amp.GradScaler()
    return scaler, True, dtype


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--ablation", default="full")
    ap.add_argument("--mode", default="combined")
    ap.add_argument("--steps", type=int, default=5000)
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--grad-accum", type=int, default=1)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--block", type=int, default=512)
    ap.add_argument("--d-model", type=int, default=512)
    ap.add_argument("--layers", type=int, default=8)
    ap.add_argument("--heads", type=int, default=8)
    ap.add_argument("--amp", action="store_true", default=True)
    ap.add_argument("--no-amp", dest="amp", action="store_false")
    ap.add_argument("--ckpt-every", type=int, default=1000)
    ap.add_argument("--eval-every", type=int, default=500)
    ap.add_argument("--log-every", type=int, default=50)
    ap.add_argument("--contrib-every", type=int, default=4)
    ap.add_argument("--gen-tokens", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="runs/symbolu_gpu")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    torch.manual_seed(args.seed)
    os.makedirs(args.out, exist_ok=True)

    text = load_corpus(args.corpus)
    tok = CharTokenizer(text)
    ids = tok.encode(text)
    tr, va = split_ids(ids, 0.1)

    cfg = with_mode(get_ablation(args.ablation), args.mode)
    cfg.backbone.vocab_size = tok.vocab_size
    cfg.backbone.d_model = args.d_model
    cfg.backbone.n_layers = args.layers
    cfg.backbone.n_heads = args.heads
    cfg.backbone.max_seq = args.block
    cfg.contrib_eval_every = args.contrib_every

    model = SymbolUSoftmaxModel(cfg).to(device)
    opt = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.01)
    scaler, use_amp, adtype = amp_setup(device, args.amp)

    json.dump({**vars(args), "device": device, "vocab_size": tok.vocab_size,
               "params": model.num_params(),
               "mflops_per_tok": round(approx_flops_per_token(cfg, args.block) / 1e6, 3),
               "amp": use_amp, "amp_dtype": str(adtype)},
              open(os.path.join(args.out, "config.json"), "w"), indent=2)
    json.dump(tok.stoi, open(os.path.join(args.out, "vocab.json"), "w"))
    print(f"device={device} amp={use_amp}({adtype}) params={model.num_params()/1e6:.1f}M "
          f"vocab={tok.vocab_size} block={args.block} batch={args.batch_size} "
          f"grad_accum={args.grad_accum} steps={args.steps}")

    gen = torch.Generator().manual_seed(args.seed)
    it = make_batches(tr, args.block, args.batch_size, generator=gen)
    logf = open(os.path.join(args.out, "train_log.jsonl"), "w")
    helps = {"refine": 0, "memory": 0}
    seen = {"refine": 0, "memory": 0}
    contrib_keys = {"refine": "refine_halt_p_grad", "memory": "mem_readiness_grad"}

    def ce(logits, y):
        return F.cross_entropy(logits.reshape(-1, logits.size(-1)), y.reshape(-1))

    def save_ckpt(path, step, metrics):
        torch.save({"model": model.state_dict(), "cfg": cfg, "stoi": tok.stoi,
                    "ablation": args.ablation, "step": step, "metrics": metrics}, path)

    model.train()
    t0 = time.time()
    tok_count = 0
    opt.zero_grad()
    for step in range(args.steps):
        contrib_rec = {}
        step_loss = 0.0
        for micro in range(args.grad_accum):
            x, y = next(it)
            x, y = x.to(device), y.to(device)
            tok_count += x.numel()
            with torch.autocast(device_type=device, dtype=adtype, enabled=use_amp):
                aux = model(x)
                logits = aux["logits"]
                lm = ce(logits, y)
                loss = lm
                if cfg.entropy_refine and "ponder_cost" in aux:
                    loss = loss + cfg.ponder_weight * aux["ponder_cost"]
                if cfg.entropy_cal_weight > 0 and "entropy_vec" in aux:
                    with torch.no_grad():
                        nll = F.cross_entropy(logits.reshape(-1, logits.size(-1)),
                                              y.reshape(-1), reduction="none").reshape(y.shape)
                    H = aux["entropy_vec"][..., 0]
                    Hn = H - H.mean(); en = nll - nll.mean()
                    corr = (Hn * en).mean() / (Hn.std().clamp_min(1e-6) * en.std().clamp_min(1e-6))
                    loss = loss + cfg.entropy_cal_weight * (1 - corr)
                if (cfg.contribution_weight > 0 and micro == 0
                        and step % max(1, cfg.contrib_eval_every) == 0):
                    contrib = loss.new_zeros(())
                    for mdl, gk in contrib_keys.items():
                        if gk not in aux:
                            continue
                        with torch.no_grad():
                            L_dis = ce(model(x, disabled={mdl})["logits"], y)
                        delta = (L_dis - lm).detach()
                        contrib_rec[f"{mdl}_delta_loss"] = float(delta)
                        seen[mdl] += 1
                        helped = delta.item() > 0
                        if helped:
                            helps[mdl] += 1
                        if abs(delta.item()) < 1e-3:
                            continue
                        p = aux[gk].clamp(1e-4, 1 - 1e-4)
                        target = p.new_tensor(1.0 if helped else 0.0)
                        contrib = contrib + F.binary_cross_entropy(p, target)
                    loss = loss + cfg.contribution_weight * contrib
                if cfg.residual_reg_weight > 0:
                    rr = loss.new_zeros(())
                    actg = aux["act_norm_grad"].detach()
                    for rk in ("refine_resid_grad", "mem_resid_grad"):
                        if rk in aux:
                            rr = rr + torch.relu(aux[rk] / actg - cfg.residual_target_ratio)
                    loss = loss + cfg.residual_reg_weight * rr
                loss = loss / args.grad_accum
            if scaler is not None:
                scaler.scale(loss).backward()
            else:
                loss.backward()
            step_loss += loss.item() * args.grad_accum
        if scaler is not None:
            scaler.unscale_(opt)
            gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0).item()
            scaler.step(opt); scaler.update()
        else:
            gnorm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0).item()
            opt.step()
        opt.zero_grad()

        if (step + 1) % args.log_every == 0 or step == 0:
            rec = {"step": step + 1, "train_loss": step_loss / args.grad_accum,
                   "grad_norm": gnorm, "lr": args.lr,
                   "act_norm": float(aux.get("act_norm", 0.0)),
                   "tokens": tok_count,
                   "tok_per_s": round(tok_count / (time.time() - t0), 1)}
            for k in ("entropy_mean", "entropy_std", "refine_residual_norm",
                      "refine_gate_mean", "refine_halt_p", "mem_residual_norm",
                      "mem_readiness"):
                if k in aux:
                    rec[k] = float(aux[k])
            rec.update(contrib_rec)
            for mod in ("refine", "memory"):
                if seen[mod]:
                    rec[f"{mod}_help_frac"] = round(helps[mod] / seen[mod], 3)
            logf.write(json.dumps(rec) + "\n"); logf.flush()
            print(f"  step {step+1}/{args.steps} loss={rec['train_loss']:.3f} "
                  f"gnorm={gnorm:.2f} tok/s={rec['tok_per_s']}")

        if (step + 1) % args.eval_every == 0 or step + 1 == args.steps:
            model.eval()
            v = val_loss_ppl(lambda z: model(z.to(device))["logits"],
                             va, args.block, args.batch_size)
            model.train()
            erec = {"step": step + 1, "eval": True, **v}
            logf.write(json.dumps(erec) + "\n"); logf.flush()
            print(f"  [eval] step {step+1} val_loss={v['val_loss']:.4f} ppl={v['ppl']:.2f}")

        if (step + 1) % args.ckpt_every == 0 or step + 1 == args.steps:
            save_ckpt(os.path.join(args.out, f"ckpt_step{step+1}.pt"), step + 1, None)
            save_ckpt(os.path.join(args.out, "ckpt.pt"), step + 1, None)

    # ---- final metrics + checkpoint ----
    model.eval()
    fwd = lambda z: model(z.to(device))["logits"]
    final = val_loss_ppl(fwd, va, args.block, args.batch_size)
    final.update(ece_and_entropy_corr(fwd, va, args.block, args.batch_size))
    final["params"] = model.num_params()
    final["train_time_s"] = round(time.time() - t0, 1)
    final["tok_per_s"] = round(tok_count / (time.time() - t0), 1)
    final["mflops_per_tok"] = round(approx_flops_per_token(cfg, args.block) / 1e6, 3)
    final["device"] = device
    for mod in ("refine", "memory"):
        if seen[mod]:
            final[f"{mod}_help_frac"] = round(helps[mod] / seen[mod], 3)
    json.dump(final, open(os.path.join(args.out, "metrics.json"), "w"), indent=2)
    save_ckpt(os.path.join(args.out, "ckpt.pt"), args.steps, final)
    logf.close()

    # ---- automatic final generation (generate.py code, on CPU for portability) ----
    model.to("cpu").eval()
    with open(os.path.join(args.out, "samples.txt"), "w") as sf:
        sf.write(f"# Symbol-U GPU run samples — {args.out}\n# final metrics: "
                 f"val_loss={final['val_loss']:.4f} ppl={final['ppl']:.2f}\n\n")
        for p in PROMPTS:
            samp = generate(model, tok, p, args.gen_tokens, 0.8, 40, 0.0, args.seed)
            greedy = generate(model, tok, p, 120, 0.0, 0, 0.0, args.seed)
            sf.write(f"=== prompt {p!r}  (temp 0.8, top-k 40) ===\n{samp}\n\n"
                     f"=== prompt {p!r}  (greedy) ===\n{greedy}\n\n")
    print(f"\nDONE. val_loss={final['val_loss']:.4f} ppl={final['ppl']:.2f} "
          f"-> {args.out}/  (ckpt.pt, metrics.json, samples.txt, train_log.jsonl)")


if __name__ == "__main__":
    main()
