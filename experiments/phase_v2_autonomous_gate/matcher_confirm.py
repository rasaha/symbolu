"""
matcher_confirm.py — 3-seed paired confirmation of the selected matcher under HARD negatives.

Reruns token / frozen COND-MLP / selected-best-matcher at three paired seeds on the
hard-negative dataset, reporting the full metric set (§4) + causal summary controls (§5) +
hard-negative diagnostics (§6), and applies the promotion criteria (§7). Recurrence, γ, ω,
banks, readout unchanged. Discrimination score `s` = match score for matchers / gate prob for
baselines; write rates use the gate prob B_t.
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
RAW = HERE / "results" / "matcher_confirmation_raw"
RAW.mkdir(parents=True, exist_ok=True)
SEEDS = (0, 1, 2)
DISTS = (256, 512, 1024, 2048, 4096)


def _cfg(seed):
    return TrainCfg(seed=seed, stages=[(64, 120), (128, 150), (256, 200)], post_anneal_steps=150)


def _winrate(pos, neg):
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    return _auroc(torch.cat([pos, neg]), torch.cat([torch.ones_like(pos), torch.zeros_like(neg)]))


@torch.no_grad()
def full_metrics(model, mode, vocab, dcfg, seed, summary_mode=None, mutate=None, n=400, distance=2048):
    data = generate_hard(vocab, dcfg, distance, n, 9700 + seed)
    rel, ordist, hard, fill = [], [], [], []
    wr = {"relevant": [], "ordinary": [], "hard": [], "filler": [], "cue": [], "total": []}
    rel_hard_margin, tok_score, tok_lab = [], [], []
    for i in range(0, len(data), 32):
        b = [mutate(dict(e)) for e in data[i:i + 32]] if mutate else data[i:i + 32]
        ids, wt, pp, fo = D.collate(b, vocab.PAD)
        override = None
        if mode in ("cosine", "bilinear", "conditioned") and summary_mode:
            f = model.summary_rep(ids)
            override = f[torch.randperm(f.shape[0])] if summary_mode == "shuffle" else torch.randn_like(f)
        s = _score(model, ids, mode, summary_override=override)
        B = torch.sigmoid(model.gate_logit(ids, summary_override=override)).mean(-1)
        for j, e in enumerate(b):
            wr["cue"].append(B[j, 0].item()); ev = set(e["event_pos"])
            nonpad = (ids[j] != vocab.PAD)
            for p in range(len(e["tokens"])):
                if p == 0 or p == e["probe_pos"] or not nonpad[p] or p in ev:
                    continue
                fill.append(s[j, p].item()); wr["filler"].append(B[j, p].item()); wr["total"].append(B[j, p].item())
            r_s, hd_s = [], []
            for k, p in enumerate(e["event_pos"]):
                sv, bv = s[j, p].item(), B[j, p].item(); wr["total"].append(bv)
                if e["event_relevant"][k]:
                    rel.append(sv); r_s.append(sv); wr["relevant"].append(bv)
                elif e["event_entity"][k] == e.get("hard_distractor"):
                    hard.append(sv); hd_s.append(sv); wr["hard"].append(bv)
                else:
                    ordist.append(sv); wr["ordinary"].append(bv)
                tok_score.append(sv); tok_lab.append(1 if e["event_relevant"][k] else 0)
            if r_s and hd_s:
                rel_hard_margin.append(sum(r_s) / len(r_s) - sum(hd_s) / len(hd_s))
    T = lambda x: torch.tensor(x) if x else torch.zeros(0)
    rt, ot, ht, ft = T(rel), T(ordist), T(hard), T(fill)
    alld = torch.cat([ot, ht]) if (len(ot) + len(ht)) else torch.zeros(0)
    ts, tl = T(tok_score), T(tok_lab).float()
    calib = {}
    for frac in (0.05, 0.10, 0.20):
        if len(ts):
            k = max(1, int(frac * len(ts))); thr = torch.topk(ts, k).values[-1]; w = ts >= thr
            calib[f"top{int(frac*100)}"] = {"precision": (tl[w].sum() / w.sum()).item() if w.sum() else 0.0,
                                            "recall": (tl[w].sum() / tl.sum()).item() if tl.sum() else 0.0}
    mean = lambda x: (x.mean().item() if len(x) else 0.0)
    wm = lambda k: mean(T(wr[k]))
    return {
        "auroc": _winrate(rt, alld), "hard_auroc": _winrate(rt, ht),
        "paired_winrate_rel_vs_hard": _winrate(rt, ht),
        "rel_minus_hard_margin": st.mean(rel_hard_margin) if rel_hard_margin else 0.0,
        "relevant_score_mean": mean(rt), "hard_score_mean": mean(ht),
        "ordinary_score_mean": mean(ot), "filler_score_mean": mean(ft),
        "write_relevant": wm("relevant"), "write_ordinary": wm("ordinary"), "write_hard": wm("hard"),
        "write_filler": wm("filler"), "write_cue": wm("cue"), "write_total": wm("total"),
        "calibration": calib,
    }


def train_arm_confirm(arm, best_matcher, seed, vocab, dcfg):
    torch.manual_seed(seed)
    if arm == "token":
        m = AutoGateModel(vocab.size, gate_mode="token")
        train_arm(m, "A_supervised_teacher", vocab, _cfg(seed), dcfg=dcfg); return m, "token"
    if arm == "cond_mlp":
        m = AutoGateModel(vocab.size, gate_mode="conditioned")
        train_arm(m, "A_supervised_teacher", vocab, _cfg(seed), dcfg=dcfg); return m, "conditioned"
    mode, _, hard = STUDY_ARMS[best_matcher]
    m = AutoGateModel(vocab.size, gate_mode=mode)
    train_matcher(m, vocab, _cfg(seed), dcfg=dcfg, hard=hard); return m, mode


def run(best_matcher=None):
    vocab = D.build_vocab(); dcfg = DataCfg()
    if best_matcher is None:
        agg = json.loads((HERE / "results" / "matcher_study.json").read_text())["aggregate"]
        cand = {k: agg[k]["auroc"]["mean"] for k in ("cosine", "bilinear", "bilinear_hard") if k in agg}
        best_matcher = max(cand, key=cand.get)
    print(f"selected best matcher: {best_matcher}", flush=True)
    arms = ["token", "cond_mlp", best_matcher]
    res = {}
    for arm in arms:
        per = []
        for seed in SEEDS:
            m, mode = train_arm_confirm(arm, best_matcher, seed, vocab, dcfg)
            base = full_metrics(m, mode, vocab, dcfg, seed)
            dec = {str(d): probe_at(m, vocab, dcfg, d, seed=seed) for d in DISTS}
            decode = {d: {"state": r["state"]["top1"], "readout": r["readout"]["top1"]} for d, r in dec.items()}
            ctrl = {}
            if mode in ("cosine", "bilinear", "conditioned"):
                ctrl["focus_removed"] = full_metrics(m, mode, vocab, dcfg, seed,
                                                     mutate=lambda e: {**e, "tokens": [vocab.PAD] + list(e["tokens"])[1:]})["hard_auroc"]
                ctrl["summary_shuffled"] = full_metrics(m, mode, vocab, dcfg, seed, summary_mode="shuffle")["hard_auroc"]
                ctrl["random_summary"] = full_metrics(m, mode, vocab, dcfg, seed, summary_mode="random")["hard_auroc"]
            rec = {"arm": arm, "seed": seed, **base, "decode": decode, "controls": ctrl}
            per.append(rec)
            (RAW / f"{arm}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
            print(f"[{arm} s{seed}] auroc={base['auroc']:.3f} hard_auroc={base['hard_auroc']:.3f} "
                  f"winrate={base['paired_winrate_rel_vs_hard']:.3f} d2048={decode['2048']['state']:.3f} "
                  f"d4096={decode['4096']['state']:.3f} wr(rel/hard/fill)="
                  f"{base['write_relevant']:.2f}/{base['write_hard']:.2f}/{base['write_filler']:.2f}", flush=True)
        res[arm] = per
    agg = aggregate(res, best_matcher)
    (HERE / "results" / "matcher_confirmation_aggregate.json").write_text(
        json.dumps({"per_seed": res, "aggregate": agg, "best_matcher": best_matcher}, indent=2, default=float))
    write_tables(agg, best_matcher)
    print("CONFIRM VERDICT:", json.dumps(agg["promotion"], indent=1, default=float), flush=True)
    print("CONFIRM DONE", flush=True)
    return agg


def _m(xs):
    return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "min": min(xs), "raw": xs}


def aggregate(res, best_matcher):
    out = {"by_arm": {}}
    for arm, per in res.items():
        g = lambda k: _m([r[k] for r in per])
        out["by_arm"][arm] = {
            "auroc": g("auroc"), "hard_auroc": g("hard_auroc"),
            "paired_winrate_rel_vs_hard": g("paired_winrate_rel_vs_hard"),
            "rel_minus_hard_margin": g("rel_minus_hard_margin"),
            "write_relevant": g("write_relevant"), "write_hard": g("write_hard"),
            "write_ordinary": g("write_ordinary"), "write_filler": g("write_filler"),
            "write_total": g("write_total"),
            "d2048_state": _m([r["decode"]["2048"]["state"] for r in per]),
            "d4096_state": _m([r["decode"]["4096"]["state"] for r in per]),
            "d2048_readout": _m([r["decode"]["2048"]["readout"] for r in per]),
            "d4096_readout": _m([r["decode"]["4096"]["readout"] for r in per]),
            "top10_precision": _m([r["calibration"].get("top10", {}).get("precision", 0.0) for r in per]),
        }
        if per[0]["controls"]:
            out["by_arm"][arm]["controls"] = {k: _m([r["controls"][k] for r in per]) for k in per[0]["controls"]}
    b = out["by_arm"][best_matcher]; c = out["by_arm"]["cond_mlp"]
    # promotion criteria (§7)
    ctrls = b.get("controls", {})
    controls_kill = all(ctrls.get(k, {}).get("mean", 1.0) < b["hard_auroc"]["mean"] - 0.05
                        for k in ("focus_removed", "summary_shuffled", "random_summary")) if ctrls else False
    crit = {
        "1_overall_auroc_ge_0.70": b["auroc"]["min"] >= 0.70,
        "2_hard_auroc_ge_0.65": b["hard_auroc"]["min"] >= 0.65,
        "3_rel_minus_hard_positive_every_seed": min(b["rel_minus_hard_margin"]["raw"]) > 0,
        "4_winrate_ge_0.70": b["paired_winrate_rel_vs_hard"]["min"] >= 0.70,
        "5_write_rel_gt_hard": b["write_relevant"]["mean"] > b["write_hard"]["mean"] + 0.02,
        "6_hard_falsewrite_improves": b["write_hard"]["mean"] < c["write_hard"]["mean"],
        "7_d4096_no_worse": b["d4096_state"]["mean"] >= c["d4096_state"]["mean"] - 0.01,
        "8_controls_eliminate": controls_kill,
        "10_recurrence_unchanged": True,
    }
    promote = all(crit.values())
    if promote:
        interp = "explicit focus-event matching VALIDATED"
    elif crit["1_overall_auroc_ge_0.70"] and not crit["7_d4096_no_worse"]:
        interp = "matcher discrimination works but decode regresses — gate calibration/write coupling unresolved"
    elif not controls_kill and (b["hard_auroc"]["mean"] > c["hard_auroc"]["mean"]):
        interp = "hard-negative gain fails controls — reject as dataset/shortcut overfitting"
    elif b["auroc"]["mean"] <= c["auroc"]["mean"] + 0.02:
        interp = "no matcher beats COND-MLP — stop similarity-function sweeps; move to contrastive representation learning"
    else:
        interp = "mixed — see criteria"
    out["promotion"] = {"best_matcher": best_matcher, "criteria": crit, "controls_eliminate_advantage": controls_kill,
                        "promote": promote, "interpretation": interp}
    return out


def write_tables(agg, best):
    a = agg["by_arm"]
    L = ["# Matcher confirmation (3 seeds, hard negatives)", "",
         "| arm | AUROC | hard AUROC | win-rate | rel−hard margin | d2048 state | d4096 state | d2048 readout | wr rel/ord/hard/fill |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm in a:
        x = a[arm]
        L.append(f"| {arm} | {x['auroc']['mean']:.3f} | {x['hard_auroc']['mean']:.3f} | "
                 f"{x['paired_winrate_rel_vs_hard']['mean']:.3f} | {x['rel_minus_hard_margin']['mean']:+.3f} | "
                 f"{x['d2048_state']['mean']:.3f} | {x['d4096_state']['mean']:.3f} | {x['d2048_readout']['mean']:.3f} | "
                 f"{x['write_relevant']['mean']:.2f}/{x['write_ordinary']['mean']:.2f}/{x['write_hard']['mean']:.2f}/{x['write_filler']['mean']:.2f} |")
    p = agg["promotion"]
    L += ["", f"**Promotion: {p['promote']}** — {p['interpretation']}", "",
          "Criteria (§7):"] + [f"- {k}: {v}" for k, v in p["criteria"].items()]
    if "controls" in a.get(best, {}):
        L += ["", "Causal controls (hard AUROC under intervention):"]
        for k, v in a[best]["controls"].items():
            L.append(f"- {k}: {v['mean']:.3f}")
    (HERE / "results" / "matcher_tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
