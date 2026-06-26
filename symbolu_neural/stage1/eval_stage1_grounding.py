"""Stage-1 grounding evaluator + kill-criteria verdict.

Loads trained heads, reports per-head metrics with baselines, and applies the
kill criteria. Optionally takes --train to compute the train/val gap used by the
memorization criterion. Prints a clear PASS / FAIL and the synthetic-data banner.

Example:
    python -m symbolu_neural.stage1.eval_stage1_grounding \
        --val data/toy_grounding/val.jsonl --train data/toy_grounding/train.jsonl \
        --ckpt runs/toy/stage1_heads.pt --backbone dummy
"""
from __future__ import annotations

import argparse

import torch
from torch.utils.data import DataLoader

from .common import build_model, detect_meta, synthetic_banner
from .data import GroundingDataset, make_collate, load_jsonl
from .labels import CARDINALITY
from .metrics import head_report


def _collect(model, loader, heads):
    model.eval()
    cat = {h: ([], []) for h in heads}
    with torch.no_grad():
        for b in loader:
            out = model(b["input_ids"], b["attention_mask"], b["pool"])
            for h in heads:
                C = out[h].shape[-1]
                cat[h][0].append(out[h].reshape(-1, C))       # flatten variable U
                cat[h][1].append(b["labels"][h].reshape(-1))
    return {h: (torch.cat(cat[h][0], 0).unsqueeze(1),         # [N,1,C]
                torch.cat(cat[h][1], 0).unsqueeze(1)) for h in heads}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--val", required=True)
    ap.add_argument("--train", default=None, help="for memorization (train-val gap)")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--backbone", default="dummy")
    ap.add_argument("--pool", default="sum", choices=["sum", "mean"])
    ap.add_argument("--d-model", type=int, default=32)
    ap.add_argument("--margin", type=float, default=0.05,
                    help="required val accuracy margin over max(chance,majority)")
    ap.add_argument("--gap", type=float, default=0.25,
                    help="train-val acc gap above which memorization is flagged")
    ap.add_argument("--corr-min", type=float, default=0.0,
                    help="min entropy<->error correlation to pass calibration")
    args = ap.parse_args()

    ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
    heads = list(ckpt["heads"].keys())
    meta = detect_meta(args.val)
    print(synthetic_banner(meta))

    model, tok, d_eff = build_model(args.backbone, ckpt.get("d_eff", args.d_model),
                                    heads)
    for h in heads:
        model.heads[h].load_state_dict(ckpt["heads"][h])
    collate = make_collate(args.pool)

    va = GroundingDataset(load_jsonl(args.val), tok)
    vl = DataLoader(va, batch_size=32, shuffle=False, collate_fn=collate)
    val_out = _collect(model, vl, heads)

    train_acc = {}
    if args.train:
        tr = GroundingDataset(load_jsonl(args.train), tok)
        tld = DataLoader(tr, batch_size=32, shuffle=False, collate_fn=collate)
        tr_out = _collect(model, tld, heads)
        for h in heads:
            from .metrics import accuracy
            train_acc[h] = accuracy(*tr_out[h])

    print(f"{'head':10s} {'acc':>7s} {'mF1':>7s} {'chance':>7s} {'major':>7s} "
          f"{'ent~err':>8s} {'ece':>6s} {'train':>7s}")
    failures = []
    for h in heads:
        lp, ys = val_out[h]
        r = head_report(h, lp, ys, CARDINALITY[h])
        tacc = train_acc.get(h, float("nan"))
        print(f"{h:10s} {r['accuracy']:7.3f} {r['macro_f1']:7.3f} {r['chance']:7.3f} "
              f"{r['majority']:7.3f} {r['entropy_error_corr']:8.3f} {r['ece']:6.3f} "
              f"{tacc:7.3f}")

        floor = max(r["chance"], r["majority"]) + args.margin
        if h in ("vritti", "aspect") and not (r["accuracy"] > floor):
            failures.append(f"[{h}] acc {r['accuracy']:.3f} <= max(chance,majority)+margin "
                            f"{floor:.3f} -> grounding FAIL")
        corr = r["entropy_error_corr"]
        if h in ("vritti", "aspect") and not (corr != corr or corr > args.corr_min):
            # corr!=corr guards NaN (no errors); only fail on a real non-positive corr
            failures.append(f"[{h}] entropy<->error corr {corr:.3f} <= {args.corr_min} "
                            f"-> uncertainty FAIL")
        if args.train and h in ("vritti", "aspect"):
            if (tacc - r["accuracy"]) > args.gap and r["accuracy"] <= floor:
                failures.append(f"[{h}] train-val gap {tacc - r['accuracy']:.3f} > "
                                f"{args.gap} with val at chance -> MEMORIZATION")

    print()
    if failures:
        print("VERDICT: FAIL")
        for f in failures:
            print("  -", f)
    else:
        print("VERDICT: PASS (grounding signal above baselines; entropy tracks error)")
    if meta and meta.get("synthetic"):
        print("\nNOTE: dataset is SYNTHETIC — this PASS/FAIL concerns the harness and a\n"
              "      surface-feature signal only, not the real Vritti hypothesis.")


if __name__ == "__main__":
    main()
