"""Run the ablation ladder and print a comparison table + verdict.

    python -m symbolu_neural.clean_softmax.prepare_data --out data/clean_lm/corpus.txt
    python -m symbolu_neural.clean_softmax.run_ablations --corpus data/clean_lm/corpus.txt \
        --steps 300 --ablations baseline,baseline_plus_block,random_aug,entropy_refine,full
"""
from __future__ import annotations

import argparse

import torch

from .config import ABLATIONS, get_ablation
from .data import CharTokenizer, load_corpus, split_ids
from .trainer import train_and_eval, head_grounding_control
from .metrics import sample


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default="data/clean_lm/corpus.txt")
    ap.add_argument("--ablations", default="baseline,baseline_plus_block,random_aug,"
                                           "typed_heads_probe,entropy_refine,memory,full")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--d-model", type=int, default=128)
    ap.add_argument("--layers", type=int, default=2)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--lr", type=float, default=3e-3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--grounding-control", action="store_true")
    args = ap.parse_args()

    text = load_corpus(args.corpus)
    tok = CharTokenizer(text)
    ids = tok.encode(text)
    tr, va = split_ids(ids, 0.1)
    print(f"corpus chars={len(text)} vocab={tok.vocab_size} "
          f"train_tok={len(tr)} val_tok={len(va)}")

    names = [n.strip() for n in args.ablations.split(",") if n.strip()]
    rows = {}
    base_loss = None
    for name in names:
        cfg = get_ablation(name)
        cfg.backbone.vocab_size = tok.vocab_size
        cfg.backbone.d_model = args.d_model
        cfg.backbone.n_layers = args.layers
        cfg.backbone.n_heads = args.heads
        cfg.backbone.max_seq = args.block
        m, model = train_and_eval(cfg, tr, va, args.block, args.batch,
                                  args.steps, args.lr, args.seed)
        rows[name] = m
        if name == "baseline":
            base_loss = m["val_loss"]
        print(f"[{name:20s}] val_loss={m['val_loss']:.4f} ppl={m['ppl']:.2f} "
              f"ece={m['ece']:.4f} H~err={m['lm_entropy_error_corr']:.3f} "
              f"params={m['params']/1e3:.0f}k ms/step={m['ms_per_step']}")
        if args.sample and name in ("baseline", "full"):
            print("    sample:", repr(sample(lambda x: model(x)["logits"], tok,
                                             prompt="The ", n=120, block=args.block)[:120]))

    print("\n================ COMPARISON (Δ vs baseline) ================")
    print(f"{'ablation':22s}{'val_loss':>10s}{'Δloss':>9s}{'ppl':>8s}"
          f"{'ece':>8s}{'H~err':>8s}{'params':>9s}{'ms/st':>7s}")
    for name in names:
        m = rows[name]
        d = (m["val_loss"] - base_loss) if base_loss is not None else float("nan")
        flag = ""
        if base_loss is not None and name != "baseline":
            flag = "  WORSE" if d > 0.002 else ("  better" if d < -0.002 else "  ~tie")
        print(f"{name:22s}{m['val_loss']:10.4f}{d:+9.4f}{m['ppl']:8.2f}"
              f"{m['ece']:8.4f}{m['lm_entropy_error_corr']:8.3f}"
              f"{m['params']/1e3:8.0f}k{m['ms_per_step']:7.1f}{flag}")

    if args.grounding_control:
        print("\n========== typed-head grounding (synthetic labels) ==========")
        cfg = get_ablation("typed_heads_probe")
        cfg.backbone.vocab_size = tok.vocab_size
        cfg.backbone.d_model = args.d_model
        cfg.backbone.n_layers = args.layers
        cfg.backbone.n_heads = args.heads
        cfg.backbone.max_seq = args.block
        real = head_grounding_control(tr, va, cfg, args.block, args.batch,
                                      steps=max(120, args.steps // 2), shuffle=False)
        ctrl = head_grounding_control(tr, va, cfg, args.block, args.batch,
                                      steps=max(120, args.steps // 2), shuffle=True)
        print(f"  real labels : vritti_acc={real['vritti_acc']:.3f} (chance 0.20) "
              f"aspect_acc={real['aspect_acc']:.3f} (chance 0.10)")
        print(f"  shuffled    : vritti_acc={ctrl['vritti_acc']:.3f} "
              f"aspect_acc={ctrl['aspect_acc']:.3f}  <- should collapse to chance")

    # ---- adversarial verdict ----
    # Controls are NOT the formula: they exist to attribute any gain to capacity/
    # compute rather than to Symbol-U. The formula only "works" if a TRAINED
    # Symbol-U ablation beats the equal-capacity controls, not merely the baseline.
    print("\n================ VERDICT ================")
    if base_loss is None:
        print("baseline not in run; cannot judge the formula."); return
    CONTROLS = {"baseline", "baseline_plus_block", "random_aug"}
    formula = [n for n in names if n not in CONTROLS]            # trained Symbol-U paths
    control_losses = {n: rows[n]["val_loss"] for n in names
                      if n in ("baseline_plus_block", "random_aug")}
    best_control = min(control_losses, key=control_losses.get) if control_losses else None
    if not formula:
        print("no trained-formula ablation in run; cannot judge."); return
    best_f = min(formula, key=lambda n: rows[n]["val_loss"])
    df_base = rows[best_f]["val_loss"] - base_loss
    print(f"best TRAINED formula = '{best_f}': Δloss={df_base:+.4f} vs plain baseline.")
    if best_control is not None:
        dctrl = rows[best_f]["val_loss"] - rows[best_control]["val_loss"]
        print(f"vs equal-capacity control '{best_control}' "
              f"({rows[best_control]['val_loss']:.4f}): Δ={dctrl:+.4f}.")
    if df_base >= -0.002:
        print("VERDICT: FAIL — the trained Symbol-U formula does NOT beat even the "
              "plain softmax baseline on val loss.")
    elif best_control is not None and rows[best_f]["val_loss"] >= rows[best_control]["val_loss"] - 0.002:
        print("VERDICT: FAIL — any gain is fully explained by added capacity/compute: "
              "an equal-size plain extra block and/or a FROZEN-RANDOM augmentation match "
              "or beat the trained formula. The Symbol-U mechanism adds nothing here.")
    else:
        print("VERDICT: TENTATIVE PASS — a trained Symbol-U ablation beats both the "
              "baseline and the equal-capacity controls (smoke-scale only; not a scaled claim).")
    print("NOTE: refinement re-applies its block up to refine_steps times, so its FLOPs/"
          "latency exceed a single extra block — see ms/step. Judge accordingly.")


if __name__ == "__main__":
    main()
