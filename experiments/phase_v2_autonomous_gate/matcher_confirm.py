"""
matcher_confirm.py — 3-seed paired confirmation of the selected matcher under HARD negatives.

The 2-seed matcher_study selects the candidate matcher (best AUROC). This module reruns exactly
three arms — token baseline, frozen COND-MLP baseline, and the best matcher — with THREE paired
seeds on the hard-negative dataset, and reports the full metric set per arm:

  relevant-vs-distractor AUROC, paired score margin, hard-negative accuracy (relevant vs the
  frequency-matched hard distractor only), relevant/distractor/filler write rates, write-budget
  calibration (top 5/10/20), focus-state decode across distance (stability), focus-summary
  removed, focus-summary shuffled, random-summary control.

Promotion rule: the matcher is promoted only if it beats COND-MLP on BOTH AUROC and decode AND
the AUROC/margin gain disappears when the focus summary is removed or shuffled (not overfitting).
Recurrence, γ, ω, banks, readout are unchanged.
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
from .train import train_arm
from .matcher_train import train_matcher
from .distance_eval import probe_at
from .hard_dataset import generate_hard
from .matcher_study import _auroc, _score, ARMS as STUDY_ARMS

HERE = Path(__file__).resolve().parent
SEEDS = (0, 1, 2)
DISTS = (256, 512, 1024, 2048, 4096)


def _cfg(seed):
    return TrainCfg(seed=seed, stages=[(64, 120), (128, 150), (256, 200)], post_anneal_steps=150)


@torch.no_grad()
def full_metrics(model, mode, vocab, dcfg, seed, summary_mode=None, mutate=None, n=400, distance=2048):
    data = generate_hard(vocab, dcfg, distance, n, 9700 + seed)
    rel, distr, hard, paired = [], [], [], []
    tok_scores, tok_lab = [], []
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
            hd = [s[j, p].item() for k, p in enumerate(e["event_pos"])
                  if (not e["event_relevant"][k]) and e["event_entity"][k] == e.get("hard_distractor")]
            rel += r; distr += d; hard += hd
            if r and d:
                paired.append(sum(r) / len(r) - sum(d) / len(d))
            for k, p in enumerate(e["event_pos"]):
                tok_scores.append(s[j, p].item()); tok_lab.append(1 if e["event_relevant"][k] else 0)
    rt, dt, ht = torch.tensor(rel), torch.tensor(distr), torch.tensor(hard)
    sc = torch.cat([rt, dt]); lb = torch.cat([torch.ones_like(rt), torch.zeros_like(dt)])
    hsc = torch.cat([rt, ht]); hlb = torch.cat([torch.ones_like(rt), torch.zeros_like(ht)])
    ts, tl = torch.tensor(tok_scores), torch.tensor(tok_lab).float()
    calib = {}
    for frac in (0.05, 0.10, 0.20):
        k = max(1, int(frac * len(ts)))
        thr = torch.topk(ts, k).values[-1]; w = ts >= thr
        calib[f"top{int(frac*100)}"] = {"precision": (tl[w].sum() / w.sum()).item() if w.sum() else 0.0,
                                        "recall": (tl[w].sum() / tl.sum()).item() if tl.sum() else 0.0}
    return {"auroc": _auroc(sc, lb), "hard_auroc": _auroc(hsc, hlb),
            "paired_margin": st.mean(paired) if paired else 0.0,
            "relevant_score_mean": rt.mean().item() if len(rt) else 0.0,
            "distractor_score_mean": dt.mean().item() if len(dt) else 0.0,
            "hard_distractor_score_mean": ht.mean().item() if len(ht) else 0.0,
            "calibration": calib}


def train_arm_confirm(arm, best_matcher, seed, vocab, dcfg):
    if arm == "token":
        torch.manual_seed(seed); m = AutoGateModel(vocab.size, gate_mode="token")
        train_arm(m, "A_supervised_teacher", vocab, _cfg(seed), dcfg=dcfg); return m, "token"
    if arm == "cond_mlp":
        torch.manual_seed(seed); m = AutoGateModel(vocab.size, gate_mode="conditioned")
        train_arm(m, "A_supervised_teacher", vocab, _cfg(seed), dcfg=dcfg); return m, "conditioned"
    mode = STUDY_ARMS[best_matcher][0]                     # 'cosine' or 'bilinear'
    hard = STUDY_ARMS[best_matcher][2]
    torch.manual_seed(seed); m = AutoGateModel(vocab.size, gate_mode=mode)
    train_matcher(m, vocab, _cfg(seed), dcfg=dcfg, hard=hard); return m, mode


def run(best_matcher=None):
    vocab = D.build_vocab(); dcfg = DataCfg()
    if best_matcher is None:
        agg = json.loads((HERE / "results" / "matcher_study.json").read_text())["aggregate"]
        cand = {k: agg[k]["auroc"]["mean"] for k in ("cosine", "bilinear", "bilinear_hard")}
        best_matcher = max(cand, key=cand.get)
    print(f"selected best matcher: {best_matcher}", flush=True)
    arms = {"token": "token", "cond_mlp": "cond_mlp", best_matcher: best_matcher}
    res = {}
    for arm in arms:
        per = []
        for seed in SEEDS:
            m, mode = train_arm_confirm(arm, best_matcher, seed, vocab, dcfg)
            base = full_metrics(m, mode, vocab, dcfg, seed)
            decode = {str(d): probe_at(m, vocab, dcfg, d, seed=seed)["state"]["top1"] for d in DISTS}
            wc = probe_at(m, vocab, dcfg, 2048, seed=seed)["write_by_category"]
            fr = full_metrics(m, mode, vocab, dcfg, seed,
                              mutate=lambda e: {**e, "tokens": [vocab.PAD] + list(e["tokens"])[1:]})
            ctrl = {"focus_removed_auroc": fr["auroc"], "focus_removed_margin": fr["paired_margin"]}
            if mode in ("cosine", "bilinear", "conditioned"):
                sh = full_metrics(m, mode, vocab, dcfg, seed, summary_mode="shuffle")
                rn = full_metrics(m, mode, vocab, dcfg, seed, summary_mode="random")
                ctrl.update({"summary_shuffled_auroc": sh["auroc"], "summary_shuffled_margin": sh["paired_margin"],
                             "random_summary_auroc": rn["auroc"], "random_summary_margin": rn["paired_margin"]})
            rec = {"arm": arm, "seed": seed, **base, "decode": decode, "write_by_category": wc, "controls": ctrl}
            per.append(rec)
            (HERE / "results" / "raw" / f"confirm_{arm}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
            print(f"[{arm} s{seed}] auroc={base['auroc']:.3f} hard_auroc={base['hard_auroc']:.3f} "
                  f"margin={base['paired_margin']:+.3f} d2048={decode['2048']:.3f} d4096={decode['4096']:.3f} "
                  f"wr(rel/distr/fill)={wc['relevant']:.2f}/{wc['distractor']:.2f}/{wc['filler']:.2f}", flush=True)
        res[arm] = per
    agg = aggregate(res, best_matcher)
    (HERE / "results" / "matcher_confirm.json").write_text(json.dumps({"per": res, "aggregate": agg, "best_matcher": best_matcher}, indent=2, default=float))
    write_tables(agg, best_matcher)
    print("CONFIRM VERDICT:", json.dumps(agg["promotion"], indent=1, default=float), flush=True)
    print("CONFIRM DONE", flush=True)
    return agg


def _m(xs): return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}


def aggregate(res, best_matcher):
    out = {"by_arm": {}}
    for arm, per in res.items():
        out["by_arm"][arm] = {
            "auroc": _m([r["auroc"] for r in per]), "hard_auroc": _m([r["hard_auroc"] for r in per]),
            "margin": _m([r["paired_margin"] for r in per]),
            "d2048": _m([r["decode"]["2048"] for r in per]), "d4096": _m([r["decode"]["4096"] for r in per]),
            "write_rel": _m([r["write_by_category"]["relevant"] for r in per]),
            "write_distr": _m([r["write_by_category"]["distractor"] for r in per]),
            "write_fill": _m([r["write_by_category"]["filler"] for r in per]),
            "top10_precision": _m([r["calibration"]["top10"]["precision"] for r in per]),
            "top10_recall": _m([r["calibration"]["top10"]["recall"] for r in per]),
            "focus_removed_auroc": _m([r["controls"]["focus_removed_auroc"] for r in per]),
        }
    b = out["by_arm"].get(best_matcher, {}); c = out["by_arm"]["cond_mlp"]
    improves_disc = b.get("auroc", {}).get("mean", 0) > c["auroc"]["mean"] + 0.02
    improves_decode = b.get("d2048", {}).get("mean", 0) >= c["d2048"]["mean"] - 0.01 and \
        b.get("d4096", {}).get("mean", 0) >= c["d4096"]["mean"] - 0.01
    controls_kill = b.get("focus_removed_auroc", {}).get("mean", 0.5) < b.get("auroc", {}).get("mean", 0) - 0.05
    promote = improves_disc and improves_decode and controls_kill
    if promote:
        interp = "explicit focus-event matching validated"
    elif improves_disc and not improves_decode:
        interp = "matcher improves discrimination but not decode — gate calibration/write coupling unresolved"
    elif not improves_disc:
        interp = "no matcher materially exceeds COND-MLP — stop matcher-form sweeps; move to contrastive focus-event representation learning"
    else:
        interp = "mixed"
    if improves_disc and not controls_kill:
        interp = "hard-negative gain fails controls — reject as dataset overfitting"
    out["promotion"] = {"best_matcher": best_matcher, "improves_discrimination": improves_disc,
                        "improves_decode": improves_decode, "controls_eliminate_gain": controls_kill,
                        "promote": promote, "interpretation": interp}
    return out


def write_tables(agg, best):
    a = agg["by_arm"]
    L = ["# Matcher confirmation (3 seeds, hard negatives)", "",
         "| arm | AUROC | hard AUROC | margin | d2048 | d4096 | wr rel/distr/fill | top10 prec/rec | focus-removed AUROC |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in a:
        x = a[arm]
        L.append(f"| {arm} | {x['auroc']['mean']:.3f} | {x['hard_auroc']['mean']:.3f} | {x['margin']['mean']:+.3f} | "
                 f"{x['d2048']['mean']:.3f} | {x['d4096']['mean']:.3f} | "
                 f"{x['write_rel']['mean']:.2f}/{x['write_distr']['mean']:.2f}/{x['write_fill']['mean']:.2f} | "
                 f"{x['top10_precision']['mean']:.2f}/{x['top10_recall']['mean']:.2f} | {x['focus_removed_auroc']['mean']:.3f} |")
    p = agg["promotion"]
    L += ["", f"**Promotion:** {p['promote']} — {p['interpretation']}",
          f"- improves discrimination: {p['improves_discrimination']}; improves decode: {p['improves_decode']}; "
          f"controls eliminate gain: {p['controls_eliminate_gain']}"]
    (HERE / "results" / "matcher_confirm_tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
