"""Capacity-/FLOP-matched controls: does each active Symbol-U mechanism learn
something a plain Transformer cannot reproduce with the same compute budget?

Each Symbol-U mechanism is trained in its earned-best config (combined mode) and
compared to a control with ~equal params AND FLOPs:
  - Recursive refinement  vs  RecurrentPlainRefine (shared plain block × steps)
  - Deferred-Insight memory vs PointwiseMemoryControl (pointwise FFN ≈ d^2)
  - Full Symbol-U          vs  both controls together

Identical dataset / optimizer / lr / batch / seed / steps. Adversarial: if a
mechanism doesn't beat its equal-compute control, it's "equivalent to extra
capacity".

CPU:  python -m symbolu_neural.clean_softmax.run_capacity_study --steps 300 --block 96
"""
from __future__ import annotations

import argparse
import json
import os

import torch

from .config import get_ablation, with_mode, approx_flops_per_token
from .data import CharTokenizer, load_corpus, split_ids
from .trainer import train_and_eval
from .generate import generate

PROMPTS = ["The ", "Symbol-U "]
RUNS = [  # (label, ablation, mode)
    ("baseline",        "baseline",      "normal"),
    ("refine_symbolu",  "entropy_refine","combined"),
    ("refine_control",  "recur_plain",   "normal"),
    ("memory_symbolu",  "mem_only",      "combined"),
    ("memory_control",  "mem_control",   "normal"),
    ("full_symbolu",    "full",          "combined"),
    ("full_control",    "full_control",  "normal"),
]
PAIRS = [  # (mechanism, symbolu_label, control_label)
    ("Recursive refinement", "refine_symbolu", "refine_control"),
    ("Deferred-Insight memory", "memory_symbolu", "memory_control"),
    ("Full Symbol-U", "full_symbolu", "full_control"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--block", type=int, default=96)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-every", type=int, default=100)
    ap.add_argument("--margin", type=float, default=0.01)
    ap.add_argument("--out", default="runs/capacity")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    text = load_corpus(args.corpus)
    tok = CharTokenizer(text)
    ids = tok.encode(text); tr, va = split_ids(ids, 0.1)
    print(f"device={device} vocab={tok.vocab_size} train_tok={len(tr)} val_tok={len(va)}")

    res = {}
    for label, abl, mode in RUNS:
        cfg = with_mode(get_ablation(abl), mode)
        cfg.backbone.vocab_size = tok.vocab_size
        cfg.backbone.d_model = args.d_model
        cfg.backbone.n_layers = args.layers
        cfg.backbone.n_heads = args.heads
        cfg.backbone.max_seq = args.block
        print(f"\n==== {label} (ablation={abl}, mode={mode}) ====")
        m, model, hist = train_and_eval(
            cfg, tr, va, args.block, args.batch, args.steps, args.lr, args.seed,
            log_every=max(1, args.steps // 3), device=device,
            val_every=args.val_every, collect=True)
        m["mflops_per_tok"] = round(approx_flops_per_token(cfg, args.block) / 1e6, 2)
        model.eval()
        samples = {p: generate(model, tok, p, 90, 0.8, 40, 0.0, args.seed)[len(p):]
                   for p in PROMPTS}
        res[label] = {"metrics": m, "history": hist, "samples": samples}
        d = os.path.join(args.out, label); os.makedirs(d, exist_ok=True)
        json.dump({"metrics": m, "history": hist, "samples": samples},
                  open(os.path.join(d, "log.json"), "w"), indent=2)
        print(f"  val_loss={m['val_loss']:.4f} ppl={m['ppl']:.2f} ece={m['ece']:.3f} "
              f"params={m['params']/1e3:.0f}k MFLOPs/tok={m['mflops_per_tok']} "
              f"ms/step={m['ms_per_step']}")

    # -------- summary table --------
    print("\n================ CAPACITY-MATCHED SUMMARY ================")
    print(f"{'run':18s}{'val_loss':>9s}{'ppl':>8s}{'ece':>7s}{'params':>9s}"
          f"{'MFLOP/t':>9s}{'ms/st':>7s}")
    for label, _, _ in RUNS:
        m = res[label]["metrics"]
        print(f"{label:18s}{m['val_loss']:9.4f}{m['ppl']:8.2f}{m['ece']:7.3f}"
              f"{m['params']/1e3:8.0f}k{m['mflops_per_tok']:9.2f}{m['ms_per_step']:7.1f}")

    # -------- per-mechanism verdicts --------
    print("\n================ PER-MECHANISM VERDICT ================")
    print(f"{'mechanism':24s}{'S_val':>8s}{'C_val':>8s}{'Δ(S-C)':>9s}"
          f"{'S_par':>8s}{'C_par':>8s}{'S_FLOP':>8s}{'C_FLOP':>8s}  verdict")
    verdicts = {}
    for mech, sl, cl in PAIRS:
        s, c = res[sl]["metrics"], res[cl]["metrics"]
        d = s["val_loss"] - c["val_loss"]
        if d <= -args.margin:
            v = "Novel computation observed"
        elif d >= args.margin:
            v = "Worse than control (not useful)"
        else:
            v = "Equivalent to extra capacity"
        verdicts[mech] = (v, d, s, c)
        print(f"{mech:24s}{s['val_loss']:8.4f}{c['val_loss']:8.4f}{d:+9.4f}"
              f"{s['params']/1e3:7.0f}k{c['params']/1e3:7.0f}k"
              f"{s['mflops_per_tok']:8.2f}{c['mflops_per_tok']:8.2f}  {v}")

    print("\n================ FINAL ANSWER (single seed — run >=2 seeds!) ================")
    novel = [m for m, (v, *_ ) in verdicts.items() if v == "Novel computation observed"]
    if novel:
        print("Single-seed: some mechanism beats its equal-compute control:",
              ", ".join(novel))
        print("=> NOT robust on one seed; re-run with --seed 1/2. (In our 2-seed run "
              "the only 'win' flipped sign — it was noise. See "
              "CAPACITY_MATCHED_CONTROL_REPORT.md.)")
    else:
        print("NO mechanism beats its capacity-/FLOP-matched control by the margin.")
        print("=> the active Symbol-U mechanisms are NOT distinguishable from simply "
              "adding equivalent Transformer capacity at this scale; their gains over "
              "the plain baseline are reproduced by plain recurrent depth / pointwise "
              "capacity of the same size.")
    os.makedirs(args.out, exist_ok=True)
    json.dump({l: res[l]["metrics"] for l, _, _ in RUNS},
              open(os.path.join(args.out, "summary.json"), "w"), indent=2)
    print(f"\nsaved under {args.out}/  (device={device})")


if __name__ == "__main__":
    main()
