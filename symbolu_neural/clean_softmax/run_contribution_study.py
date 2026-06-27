"""Can the active Symbol-U modules EARN their contribution during training?

Trains: baseline, capacity control (+1 plain block), full (normal), full
(contribution-aware), full (combined), and reports per-module helps/hurts,
halt-probability trend (normal vs contribution), residual norms, val loss/ppl,
and generation samples. Then applies the interpretation logic and answers whether
the mechanisms become naturally useful or only work when forced on.

CPU:  python -m symbolu_neural.clean_softmax.run_contribution_study --steps 400 --block 96
"""
from __future__ import annotations

import argparse
import json
import os

import torch

from .config import get_ablation, with_mode
from .data import CharTokenizer, load_corpus, split_ids
from .trainer import train_and_eval
from .generate import generate

PROMPTS = ["The ", "Symbol-U ", "The model "]
RUNS = [  # (label, ablation, mode)
    ("baseline", "baseline", "normal"),
    ("capacity_control", "baseline_plus_block", "normal"),
    ("full_normal", "full", "normal"),
    ("full_contribution", "full", "contribution"),
    ("full_combined", "full", "combined"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--block", type=int, default=96)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-every", type=int, default=100)
    ap.add_argument("--out", default="runs/contrib")
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
            log_every=max(1, args.steps // 4), device=device,
            val_every=args.val_every, collect=True)
        model.eval()
        samples = {p: generate(model, tok, p, 100, 0.8, 40, 0.0, args.seed)[len(p):]
                   for p in PROMPTS}
        res[label] = {"metrics": m, "history": hist, "samples": samples,
                      "mode": mode}
        d = os.path.join(args.out, label); os.makedirs(d, exist_ok=True)
        json.dump({"metrics": m, "history": hist, "samples": samples},
                  open(os.path.join(d, "log.json"), "w"), indent=2)
        print(f"  val_loss={m['val_loss']:.4f} ppl={m['ppl']:.2f} "
              f"final_halt_p={m.get('final_halt_p')} "
              f"refine_help={m.get('refine_help_frac')} mem_help={m.get('memory_help_frac')} "
              f"ms/step={m['ms_per_step']}")

    # -------- summary --------
    print("\n================ CONTRIBUTION SUMMARY ================")
    print(f"{'run':20s}{'val_loss':>9s}{'ppl':>8s}{'halt_p':>8s}{'refHelp':>8s}"
          f"{'memHelp':>8s}{'refR':>7s}{'memR':>7s}{'ms/st':>7s}")
    for label, _, _ in RUNS:
        m = res[label]["metrics"]
        def g(k, f="{:.3f}"):
            v = m.get(k); return (f.format(v) if isinstance(v, (int, float)) else "-")
        print(f"{label:20s}{m['val_loss']:9.4f}{m['ppl']:8.2f}"
              f"{g('final_halt_p'):>8}{g('refine_help_frac'):>8}{g('memory_help_frac'):>8}"
              f"{g('refine_residual_final','{:.0f}'):>7}{g('mem_residual_final','{:.0f}'):>7}"
              f"{m['ms_per_step']:7.1f}")

    # -------- interpretation --------
    print("\n================ INTERPRETATION ================")
    norm = res["full_normal"]["metrics"]
    con = res["full_contribution"]["metrics"]
    comb = res["full_combined"]["metrics"]
    cap = res["capacity_control"]["metrics"]
    base = res["baseline"]["metrics"]
    hp_norm = norm.get("final_halt_p") or 0.0
    hp_con = con.get("final_halt_p") or 0.0
    print(f"halt_p: normal={hp_norm:.4f} -> contribution={hp_con:.4f} "
          f"(rose by {hp_con - hp_norm:+.4f})")
    rose = hp_con > hp_norm + 0.02
    print("• " + ("Contribution loss made halt probability RISE — positive signal "
                  "that refinement can be earned." if rose else
                  "Contribution loss did NOT raise halt probability — refinement is "
                  "not useful in its current form (optimizer still rejects it)."))
    rh = con.get("refine_help_frac"); mh = con.get("memory_help_frac")
    if rh is not None and mh is not None:
        print(f"• helps-fraction (contribution run): refine={rh:.2f}, memory={mh:.2f}")
        if mh > rh + 0.1:
            print("  -> memory helps more often than refinement: keep memory, simplify refinement.")
        elif rh > mh + 0.1:
            print("  -> refinement helps more often than memory.")
        else:
            print("  -> refinement and memory help about equally often.")
    best_full = min(norm["val_loss"], con["val_loss"], comb["val_loss"])
    print(f"• best full val_loss={best_full:.4f} vs capacity_control={cap['val_loss']:.4f} "
          f"vs baseline={base['val_loss']:.4f}")
    if best_full >= cap["val_loss"] - 0.002:
        print("  -> full Symbol-U does NOT beat the equal-capacity control: usefulness "
              "INCONCLUSIVE/NEGATIVE (gains are capacity, not the formula).")
    else:
        print("  -> full Symbol-U beats the equal-capacity control: tentative usefulness.")

    print("\nFINAL ANSWER:")
    earned = rose and (best_full < cap["val_loss"] - 0.002)
    if earned:
        print("Active Symbol-U mechanisms CAN become naturally useful: the gate rises "
              "when they help and they beat the capacity control.")
    elif rose:
        print("PARTIAL: the contribution objective makes the gate respond to usefulness "
              "(halt rises when it helps), but the modules still do not beat the "
              "capacity control — useful as control, not yet as net quality.")
    else:
        print("NO (so far): even with a contribution objective the gate is not earned and "
              "the modules match only the capacity control — they work only when forced on.")
    os.makedirs(args.out, exist_ok=True)
    json.dump({l: res[l]["metrics"] for l, _, _ in RUNS},
              open(os.path.join(args.out, "summary.json"), "w"), indent=2)
    print(f"\nsaved under {args.out}/  (device={device})")


if __name__ == "__main__":
    main()
