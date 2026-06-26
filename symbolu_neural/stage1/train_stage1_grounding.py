"""Stage-1 grounding trainer: FROZEN backbone + Symbol-U typed heads only.

Trains ONLY the head parameters (Vritti, Aspect, optional Guna/Kosha) with NLL,
plus an optional entropy-calibration term. Saves head weights + run config.
Does NOT train the backbone or any other Symbol-U module.

Example (toy):
    python -m symbolu_neural.stage1.make_toy_grounding_dataset --out-dir data/toy_grounding
    python -m symbolu_neural.stage1.train_stage1_grounding \
        --train data/toy_grounding/train.jsonl --val data/toy_grounding/val.jsonl \
        --backbone dummy --heads vritti,aspect --epochs 8 --out runs/toy
"""
from __future__ import annotations

import argparse
import json
import os

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .common import build_model, detect_meta, synthetic_banner
from .data import GroundingDataset, make_collate
from .labels import IGNORE, CARDINALITY
from .metrics import head_report
from ..losses import entropy_calibration_loss


def nll(logp, labels):
    B, U, C = logp.shape
    return F.nll_loss(logp.reshape(-1, C), labels.reshape(-1), ignore_index=IGNORE)


def evaluate(model, loader, heads):
    model.eval()
    cat = {h: ([], []) for h in heads}
    with torch.no_grad():
        for b in loader:
            out = model(b["input_ids"], b["attention_mask"], b["pool"])
            for h in heads:
                C = out[h].shape[-1]
                cat[h][0].append(out[h].reshape(-1, C))      # flatten variable U
                cat[h][1].append(b["labels"][h].reshape(-1))
    rep = {}
    for h in heads:
        lp = torch.cat(cat[h][0], 0).unsqueeze(1)            # [N,1,C]
        ys = torch.cat(cat[h][1], 0).unsqueeze(1)            # [N,1]
        rep[h] = head_report(h, lp, ys, CARDINALITY[h])
    return rep


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--backbone", default="dummy", help="'dummy' or 'hf:<name>'")
    ap.add_argument("--heads", default="vritti,aspect")
    ap.add_argument("--d-model", type=int, default=32, help="dummy backbone width")
    ap.add_argument("--pool", default="sum", choices=["sum", "mean"],
                    help="unit pooling; 'sum' for dummy (recovers length/vowel-count)")
    ap.add_argument("--epochs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-2)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--entropy-cal", action="store_true",
                    help="add entropy-calibration aux loss (self-uncertainty)")
    ap.add_argument("--shuffle-labels", action="store_true",
                    help="CONTROL: randomize labels; val should stay ~chance")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="runs/stage1")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    heads = [h.strip() for h in args.heads.split(",") if h.strip()]
    meta = detect_meta(args.train)
    print(synthetic_banner(meta))
    if args.shuffle_labels:
        print(">> SHUFFLE-LABEL CONTROL: expecting val ~ chance.\n")

    model, tok, d_eff = build_model(args.backbone, args.d_model, heads, args.seed)
    collate = make_collate(args.pool)
    tr = GroundingDataset(load(args.train), tok, args.shuffle_labels, args.seed)
    va = GroundingDataset(load(args.val), tok, False, args.seed)
    tl = DataLoader(tr, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    vl = DataLoader(va, batch_size=args.batch_size, shuffle=False, collate_fn=collate)

    opt = torch.optim.Adam(model.head_parameters(), lr=args.lr)
    for ep in range(args.epochs):
        model.train()
        tot = 0.0
        for b in tl:
            out = model(b["input_ids"], b["attention_mask"], b["pool"])
            loss = sum(nll(out[h], b["labels"][h]) for h in heads)
            if args.entropy_cal:
                for h in heads:
                    lp, y = out[h], b["labels"][h]
                    keep = (y != IGNORE).reshape(-1)
                    if keep.any():
                        ent = model.entropy(lp).reshape(-1)[keep]
                        C = lp.shape[-1]
                        ent_n = ent / torch.log(torch.tensor(float(C)))
                        per = F.nll_loss(lp.reshape(-1, C)[keep],
                                         y.reshape(-1)[keep], reduction="none").detach()
                        loss = loss + 0.1 * entropy_calibration_loss(ent_n, per)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item()
        rep = evaluate(model, vl, heads)
        msg = " | ".join(f"{h}: acc={rep[h]['accuracy']:.3f} "
                         f"(chance {rep[h]['chance']:.3f}, maj {rep[h]['majority']:.3f})"
                         for h in heads)
        print(f"epoch {ep+1:2d}  loss={tot/len(tl):.3f}  {msg}")

    os.makedirs(args.out, exist_ok=True)
    torch.save({"heads": {h: model.heads[h].state_dict() for h in heads},
                "config": vars(args), "d_eff": d_eff},
               os.path.join(args.out, "stage1_heads.pt"))
    with open(os.path.join(args.out, "run_config.json"), "w") as f:
        json.dump(vars(args), f, indent=2)
    print(f"\nsaved heads -> {os.path.join(args.out, 'stage1_heads.pt')}")
    print("Run eval_stage1_grounding.py for the kill-criteria verdict.")


def load(path):
    from .data import load_jsonl
    return load_jsonl(path)


if __name__ == "__main__":
    main()
