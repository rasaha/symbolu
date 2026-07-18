"""Train + diagnose the clean-softmax Symbol-U ablations.

Runs each ablation, logs training/validation curves and per-module diagnostics,
generates fixed-prompt samples, detects failure modes, and prints a mechanism
table. Saves per-ablation checkpoint + config + logs under runs/study/<name>/.

NOT a superiority test. The question: what happens when the active Symbol-U
mechanisms are trained longer, and what should be improved next?

CPU:  python -m symbolu_neural.clean_softmax.run_training_study --steps 600 --block 96
GPU:  python -m symbolu_neural.clean_softmax.run_training_study --steps 4000 --block 256 \
          --d-model 384 --layers 6 --batch 64   # auto-uses CUDA if available
"""
from __future__ import annotations

import argparse
import json
import os

import torch

from .config import get_ablation
from .data import CharTokenizer, load_corpus, split_ids
from .trainer import train_and_eval
from .generate import generate

PROMPTS = ["The ", "Symbol-U ", "The model ", "In this ", "A "]


def repetition_stats(text: str):
    if not text:
        return {"distinct_char_ratio": 0.0, "longest_run": 0}
    longest, cur = 1, 1
    for i in range(1, len(text)):
        cur = cur + 1 if text[i] == text[i - 1] else 1
        longest = max(longest, cur)
    return {"distinct_char_ratio": round(len(set(text)) / len(text), 3),
            "longest_run": longest}


def detect_failures(name, m, hist, base_val):
    f = []
    act = m.get("act_norm_final") or (hist[-1].get("act_norm") if hist else 0) or 1e-9
    rr = m.get("refine_residual_final")
    mr = m.get("mem_residual_final")
    if rr is not None and rr / act > 1.0:
        f.append(f"refinement residual ({rr:.1f}) > activation norm ({act:.1f}) — OVERPOWERING")
    if mr is not None and mr / act > 1.0:
        f.append(f"memory residual ({mr:.1f}) > activation norm ({act:.1f}) — OVERPOWERING")
    es = m.get("entropy_std_final")
    if es is not None and es < 0.02:
        f.append(f"entropy std {es:.3f} ~0 — typed heads collapsing")
    # loss instability: val rose from its mid to final
    vals = [r["val_loss"] for r in hist if "val_loss" in r]
    if len(vals) >= 3 and vals[-1] > min(vals) + 0.05:
        f.append(f"val loss rose from {min(vals):.3f} to {vals[-1]:.3f} — instability/overfit")
    gns = [r["grad_norm"] for r in hist]
    if gns and sum(g >= 0.99 for g in gns) / len(gns) > 0.8:
        f.append("grad norm pinned at clip (1.0) most steps — clipping-bound")
    if base_val is not None and name != "baseline" and abs(m["val_loss"] - base_val) < 0.01:
        f.append("no meaningful val-loss difference from baseline")
    if m["ece"] > 0.05:
        f.append(f"ECE {m['ece']:.3f} > 0.05 — poor calibration")
    return f


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--ablations",
                    default="baseline,typed_heads_probe,entropy_refine,memory,full")
    ap.add_argument("--steps", type=int, default=600)
    ap.add_argument("--block", type=int, default=96)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-every", type=int, default=100)
    ap.add_argument("--out", default="runs/study")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device}  torch={torch.__version__}")

    text = load_corpus(args.corpus)
    tok = CharTokenizer(text)
    ids = tok.encode(text)
    tr, va = split_ids(ids, 0.1)
    print(f"corpus chars={len(text)} vocab={tok.vocab_size} "
          f"train_tok={len(tr)} val_tok={len(va)}")

    names = [n.strip() for n in args.ablations.split(",") if n.strip()]
    results = {}
    base_val = None
    for name in names:
        print(f"\n==================== TRAIN [{name}] ====================")
        cfg = get_ablation(name)
        cfg.backbone.vocab_size = tok.vocab_size
        cfg.backbone.d_model = args.d_model
        cfg.backbone.n_layers = args.layers
        cfg.backbone.n_heads = args.heads
        cfg.backbone.max_seq = args.block
        m, model, hist = train_and_eval(
            cfg, tr, va, args.block, args.batch, args.steps, args.lr, args.seed,
            log_every=max(1, args.steps // 6), device=device,
            val_every=args.val_every, collect=True)
        last = hist[-1] if hist else {}
        m["act_norm_final"] = last.get("act_norm")
        m["refine_residual_final"] = last.get("refine_residual_norm")
        m["mem_residual_final"] = last.get("mem_residual_norm")
        m["entropy_std_final"] = last.get("entropy_std")
        m["refine_gate_final"] = last.get("refine_gate_mean")
        m["refine_halt_final"] = last.get("refine_halt_p")
        if name == "baseline":
            base_val = m["val_loss"]

        # generation samples (fixed seed/settings)
        model.eval()
        samples = {}
        for p in PROMPTS:
            txt = generate(model, tok, p, max_new_tokens=120, temperature=0.8,
                           top_k=40, top_p=0.0, seed=args.seed)
            gen = txt[len(p):]
            samples[p] = {"text": gen, **repetition_stats(gen)}

        fails = detect_failures(name, m, hist, base_val)
        results[name] = {"metrics": m, "history": hist, "samples": samples,
                         "failures": fails}

        # save
        d = os.path.join(args.out, name)
        os.makedirs(d, exist_ok=True)
        torch.save({"model": model.state_dict(), "cfg": cfg, "stoi": tok.stoi,
                    "ablation": name, "metrics": m}, os.path.join(d, "ckpt.pt"))
        with open(os.path.join(d, "log.json"), "w") as f:
            json.dump({"metrics": m, "history": hist, "samples": samples,
                       "failures": fails}, f, indent=2)

        print(f"[{name}] val_loss={m['val_loss']:.4f} ppl={m['ppl']:.2f} "
              f"ece={m['ece']:.4f} params={m['params']/1e3:.0f}k ms/step={m['ms_per_step']} "
              f"act={m.get('act_norm_final')} refineR={m.get('refine_residual_final')} "
              f"memR={m.get('mem_residual_final')}")
        for fl in fails:
            print("   FAILURE:", fl)
        print(f"   sample 'The ': {samples['The ']['text'][:80]!r}")

    # ---- summary tables ----
    print("\n================ TRAINING SUMMARY ================")
    print(f"{'ablation':20s}{'val_loss':>9s}{'ppl':>8s}{'ece':>7s}{'H~err':>7s}"
          f"{'params':>8s}{'ms/st':>7s}{'actN':>7s}{'refR':>7s}{'memR':>7s}")
    for name in names:
        m = results[name]["metrics"]
        def g(k):
            v = m.get(k); return f"{v:.1f}" if isinstance(v, (int, float)) and v is not None else "-"
        print(f"{name:20s}{m['val_loss']:9.4f}{m['ppl']:8.2f}{m['ece']:7.3f}"
              f"{m['lm_entropy_error_corr']:7.3f}{m['params']/1e3:7.0f}k"
              f"{m['ms_per_step']:7.1f}{g('act_norm_final'):>7}"
              f"{g('refine_residual_final'):>7}{g('mem_residual_final'):>7}")

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "summary.json"), "w") as f:
        json.dump({n: results[n]["metrics"] for n in names}, f, indent=2)
    print(f"\nsaved per-ablation logs + checkpoints under {args.out}/")
    print("device used:", device)


if __name__ == "__main__":
    main()
