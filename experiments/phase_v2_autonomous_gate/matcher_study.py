"""
matcher_study.py — improved focus↔event matcher study (§ recommended next variant).

Preserves the pilot baselines (token-only, COND-MLP AUROC≈0.62) and adds explicit-similarity
matcher arms — cosine, bilinear, and bilinear+hard-negatives — trained with pairwise ranking +
event-vs-filler + write-budget (+ alignment). Reports, per arm × seed at d2048:
  relevant / distractor score mean, paired margin, AUROC (relevant vs distractor),
  state Top-1 @2048/4096, focus-removed & summary-shuffled margin controls,
  and calibration at fixed write budgets (top 5/10/20%): precision, recall (=1−missed),
  false-write rate.
Goal: move relevant-vs-distractor AUROC from ≈0.62 toward ≥0.70 WITHOUT changing the recurrence.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import torch

from experiments.phase_v3_selective_ssm import dataset as D
from experiments.phase_v3_selective_ssm.config import DataCfg
from .config import TrainCfg
from .teacher import AutoGateModel
from .train import train_arm, build_masks
from .matcher_train import train_matcher
from .distance_eval import probe_at
from .hard_dataset import generate_hard

HERE = Path(__file__).resolve().parent
SEEDS = (0, 1)
# arm -> (gate_mode, trainer, hard)
ARMS = {
    "token": ("token", "supervised", False),
    "cond_mlp": ("conditioned", "supervised", False),
    "cosine": ("cosine", "matcher", False),
    "bilinear": ("bilinear", "matcher", False),
    "bilinear_hard": ("bilinear", "matcher", True),
    "cosine_hard": ("cosine", "matcher", True),   # cosine fallback trained on hard negatives
}


def _cfg(seed):
    return TrainCfg(seed=seed, stages=[(64, 120), (128, 150), (256, 200)], post_anneal_steps=150)


def _auroc(scores, labels):
    order = torch.argsort(scores); yr = labels[order]
    npos, nneg = yr.sum().item(), (1 - yr).sum().item()
    if npos == 0 or nneg == 0:
        return 0.5
    ranks = torch.arange(1, len(yr) + 1, dtype=torch.float)
    return ((ranks[yr == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)).item()


@torch.no_grad()
def _score(model, ids, mode, summary_override=None):
    if mode in ("cosine", "bilinear"):
        return model.match_score(ids, summary_override=summary_override)          # [B,N]
    return torch.sigmoid(model.gate_logit(ids, summary_override=summary_override)).mean(-1)


@torch.no_grad()
def gate_metrics(model, mode, vocab, dcfg, distance, seed, hard=False, summary_mode=None, mutate=None, n=400):
    data = generate_hard(vocab, dcfg, distance, n, 9500 + seed) if hard else \
        D.generate(vocab, dcfg, distance, n, 9500 + seed)
    rel, distr, paired = [], [], []
    tok_scores, tok_pos, tok_isevent = [], [], []      # for write-budget calibration
    for i in range(0, len(data), 32):
        b = [mutate(dict(e)) for e in data[i:i + 32]] if mutate else data[i:i + 32]
        ids, wt, pp, fo = D.collate(b, vocab.PAD)
        override = None
        if mode in ("cosine", "bilinear", "conditioned") and summary_mode:
            f = model.summary_rep(ids)
            override = f[torch.randperm(f.shape[0])] if summary_mode == "shuffle" else torch.randn_like(f)
        s = _score(model, ids, mode, summary_override=override)
        for j, e in enumerate(b):
            r = [s[j, p].item() for k, p in enumerate(e["event_pos"]) if e["event_relevant"][k]]
            d = [s[j, p].item() for k, p in enumerate(e["event_pos"]) if not e["event_relevant"][k]]
            rel += r; distr += d
            if r and d:
                paired.append(sum(r) / len(r) - sum(d) / len(d))
            for k, p in enumerate(e["event_pos"]):
                tok_scores.append(s[j, p].item()); tok_pos.append(1 if e["event_relevant"][k] else 0); tok_isevent.append(1)
    rel_t, distr_t = torch.tensor(rel), torch.tensor(distr)
    scores = torch.cat([rel_t, distr_t]); labels = torch.cat([torch.ones_like(rel_t), torch.zeros_like(distr_t)])
    # write-budget calibration over events
    ts = torch.tensor(tok_scores); tp = torch.tensor(tok_pos).float()
    calib = {}
    for frac in (0.05, 0.10, 0.20):
        if len(ts):
            k = max(1, int(frac * len(ts)))
            thr = torch.topk(ts, k).values[-1]
            written = ts >= thr
            prec = (tp[written].sum() / written.sum()).item() if written.sum() else 0.0
            rec = (tp[written].sum() / tp.sum()).item() if tp.sum() else 0.0
            calib[f"top{int(frac*100)}"] = {"precision": prec, "recall": rec, "false_write_rate": 1 - prec}
    return {
        "relevant_score_mean": rel_t.mean().item() if len(rel_t) else 0.0,
        "distractor_score_mean": distr_t.mean().item() if len(distr_t) else 0.0,
        "paired_margin": st.mean(paired) if paired else 0.0,
        "auroc": _auroc(scores, labels),
        "calibration": calib,
    }


def train_arm_model(arm, seed, vocab, dcfg):
    mode, trainer, hard = ARMS[arm]
    torch.manual_seed(seed)
    m = AutoGateModel(vocab.size, gate_mode=mode)
    if trainer == "supervised":
        train_arm(m, "A_supervised_teacher", vocab, _cfg(seed), dcfg=dcfg)
    else:
        train_matcher(m, vocab, _cfg(seed), dcfg=dcfg, hard=hard)
    return m, mode, hard


def run(seeds=SEEDS):
    vocab = D.build_vocab(); dcfg = DataCfg()
    res = {}
    for arm in ARMS:
        per = []
        for seed in seeds:
            m, mode, hard = train_arm_model(arm, seed, vocab, dcfg)
            base = gate_metrics(m, mode, vocab, dcfg, 2048, seed, hard=hard)
            p2048 = probe_at(m, vocab, dcfg, 2048, seed=seed)
            p4096 = probe_at(m, vocab, dcfg, 4096, seed=seed)
            fr = gate_metrics(m, mode, vocab, dcfg, 2048, seed, hard=hard,
                              mutate=lambda e: {**e, "tokens": [vocab.PAD] + list(e["tokens"])[1:]})["paired_margin"]
            ss = (gate_metrics(m, mode, vocab, dcfg, 2048, seed, hard=hard, summary_mode="shuffle")["paired_margin"]
                  if mode in ("cosine", "bilinear", "conditioned") else None)
            rec = {"arm": arm, "seed": seed, "auroc": base["auroc"], "margin": base["paired_margin"],
                   "relevant_score_mean": base["relevant_score_mean"], "distractor_score_mean": base["distractor_score_mean"],
                   "state_top1_2048": p2048["state"]["top1"], "state_top1_4096": p4096["state"]["top1"],
                   "calibration": base["calibration"], "margin_focus_removed": fr, "margin_summary_shuffled": ss}
            per.append(rec)
            (HERE / "results" / "raw" / f"matcher_{arm}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
            print(f"[{arm} s{seed}] auroc={rec['auroc']:.3f} margin={rec['margin']:+.3f} "
                  f"d2048={rec['state_top1_2048']:.3f} d4096={rec['state_top1_4096']:.3f} "
                  f"top10={base['calibration'].get('top10')}", flush=True)
        res[arm] = per
    agg = aggregate(res)
    (HERE / "results" / "matcher_study.json").write_text(json.dumps({"per": res, "aggregate": agg}, indent=2, default=float))
    write_tables(agg)
    print("MATCHER STUDY DONE", flush=True)
    return agg


def aggregate(res):
    out = {}
    for arm, per in res.items():
        out[arm] = {
            "auroc": {"mean": st.mean([r["auroc"] for r in per]), "raw": [r["auroc"] for r in per]},
            "margin": {"mean": st.mean([r["margin"] for r in per]), "raw": [r["margin"] for r in per]},
            "state_top1_2048": st.mean([r["state_top1_2048"] for r in per]),
            "state_top1_4096": st.mean([r["state_top1_4096"] for r in per]),
            "margin_focus_removed": st.mean([r["margin_focus_removed"] for r in per]),
            "top10_precision": st.mean([r["calibration"].get("top10", {}).get("precision", 0.0) for r in per]),
            "top10_recall": st.mean([r["calibration"].get("top10", {}).get("recall", 0.0) for r in per]),
        }
    return out


def write_tables(agg):
    L = ["# Matcher study — focus↔event relevance (recurrence unchanged)", "",
         "| arm | AUROC | rel−distr margin | d2048 | d4096 | focus-removed margin | top10 prec | top10 recall |",
         "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in ARMS:
        a = agg[arm]
        L.append(f"| {arm} | {a['auroc']['mean']:.3f} | {a['margin']['mean']:+.3f} | "
                 f"{a['state_top1_2048']:.3f} | {a['state_top1_4096']:.3f} | {a['margin_focus_removed']:+.3f} | "
                 f"{a['top10_precision']:.3f} | {a['top10_recall']:.3f} |")
    best = max(ARMS, key=lambda a: agg[a]["auroc"]["mean"])
    L += ["", f"**Best AUROC arm:** {best} ({agg[best]['auroc']['mean']:.3f}); "
          f"COND-MLP baseline {agg['cond_mlp']['auroc']['mean']:.3f}; token {agg['token']['auroc']['mean']:.3f}"]
    (HERE / "results" / "matcher_tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
