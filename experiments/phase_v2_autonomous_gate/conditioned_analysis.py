"""
conditioned_analysis.py — CLAIM 2 (focus-conditioned event selection).

Tests whether a causal focus-conditioned gate B_t = σ(MLP([h_t, f_t, h_t⊙f_t, |h_t−f_t|]))
can distinguish a later focus-MATCHING event from otherwise-identical distractor events —
something a token-only gate structurally cannot do. f_t is the causal cue summary (rep at the
header position); no oracle match bit, no future query, no target label at inference.

Uses PAIRED within-example comparisons (relevant & distractor events are structurally matched).
Reports, for token vs conditioned gates (trained supervised = fair learnability test, 2 seeds):
    relevant-event gate mean, distractor-event gate mean
    paired relevant−distractor margin (raw + standardized effect size)
    AUROC of the gate score separating relevant vs distractor events
    state Top-1 @2048/4096, header−filler margin, write rate
    controls: focus-removed, focus-shuffled, summary-shuffled, random-summary
Acceptance (§ Acceptance for the conditioned gate).
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import torch

from experiments.phase_v3_selective_ssm.dataset import build_vocab
from experiments.phase_v3_selective_ssm.config import DataCfg
from .config import TrainCfg
from .train import build_model, train_arm
from .distance_eval import probe_at

HERE = Path(__file__).resolve().parent
SEEDS = (0, 1)


def _cfg(seed):
    return TrainCfg(seed=seed, stages=[(64, 120), (128, 150), (256, 200)], post_anneal_steps=150)


def _auroc(scores, labels):
    order = torch.argsort(scores)
    yr = labels[order]
    npos = yr.sum().item(); nneg = (1 - yr).sum().item()
    if npos == 0 or nneg == 0:
        return 0.5
    ranks = torch.arange(1, len(yr) + 1, dtype=torch.float)
    return ((ranks[yr == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg)).item()


@torch.no_grad()
def gate_event_stats(model, vocab, dcfg, distance, seed, summary_mode=None, mutate=None, n=400):
    from experiments.phase_v3_selective_ssm import dataset as D
    data = D.generate(vocab, dcfg, distance, n, 9100 + seed)
    rel_all, distr_all, paired = [], [], []
    for i in range(0, len(data), 32):
        b = data[i:i + 32]
        if mutate:
            b = [mutate(dict(e)) for e in b]
        ids, wt, pp, fo = D.collate(b, vocab.PAD)
        override = None
        if model.gate_mode == "conditioned" and summary_mode:
            f = model.summary_rep(ids)
            if summary_mode == "shuffle":
                override = f[torch.randperm(f.shape[0])]
            elif summary_mode == "random":
                override = torch.randn_like(f)
        logit = model.gate_logit(ids, summary_override=override)
        gm = torch.sigmoid(logit).mean(-1)                     # [B,N]
        for j, e in enumerate(b):
            r = [gm[j, p].item() for k, p in enumerate(e["event_pos"]) if e["event_relevant"][k]]
            d = [gm[j, p].item() for k, p in enumerate(e["event_pos"]) if not e["event_relevant"][k]]
            rel_all += r; distr_all += d
            if r and d:
                paired.append(sum(r) / len(r) - sum(d) / len(d))
    rel = torch.tensor(rel_all); distr = torch.tensor(distr_all)
    scores = torch.cat([rel, distr]); labels = torch.cat([torch.ones_like(rel), torch.zeros_like(distr)])
    pooled_std = scores.std().item() + 1e-6
    margin = st.mean(paired) if paired else 0.0
    return {
        "relevant_gate_mean": rel.mean().item() if len(rel) else 0.0,
        "distractor_gate_mean": distr.mean().item() if len(distr) else 0.0,
        "paired_margin": margin,
        "standardized_margin": margin / pooled_std,
        "auroc_relevant_vs_distractor": _auroc(scores, labels),
    }


def analyze_gate(mode, seed, vocab, dcfg):
    m = build_model(vocab, "sigmoid", seed, gate_mode=mode)
    train_arm(m, "A_supervised_teacher", vocab, _cfg(seed), dcfg=dcfg)     # supervised = fair learnability test
    base = gate_event_stats(m, vocab, dcfg, 2048, seed)
    p2048 = probe_at(m, vocab, dcfg, 2048, seed=seed)
    p4096 = probe_at(m, vocab, dcfg, 4096, seed=seed)
    wc = p2048["write_by_category"]
    out = {
        "mode": mode, "seed": seed,
        "relevant_gate_mean": base["relevant_gate_mean"],
        "distractor_gate_mean": base["distractor_gate_mean"],
        "paired_margin": base["paired_margin"],
        "standardized_margin": base["standardized_margin"],
        "auroc_relevant_vs_distractor": base["auroc_relevant_vs_distractor"],
        "state_top1_2048": p2048["state"]["top1"], "state_top1_4096": p4096["state"]["top1"],
        "control_top1_2048": max(p2048["shuffled_state"]["top1"], p2048["random_state"]["top1"]),
        "header_minus_filler": wc["cue"] - wc["filler"],
        "write_rate": 0.5 * (wc["relevant"] + wc["distractor"]),
    }
    # controls (margin should vanish when the true focus is removed/scrambled)
    def blank_header(e):
        e = dict(e); e["tokens"] = list(e["tokens"]); e["tokens"][0] = vocab.PAD; return e

    def shuffle_focus(e):
        e = dict(e); e["focus_id"] = int(torch.randint(0, dcfg.num_entities, (1,)).item()); return e
    out["margin_focus_removed"] = gate_event_stats(m, vocab, dcfg, 2048, seed, mutate=blank_header)["paired_margin"]
    out["margin_focus_shuffled"] = gate_event_stats(m, vocab, dcfg, 2048, seed, mutate=shuffle_focus)["paired_margin"]
    if mode == "conditioned":
        out["margin_summary_shuffled"] = gate_event_stats(m, vocab, dcfg, 2048, seed, summary_mode="shuffle")["paired_margin"]
        out["margin_random_summary"] = gate_event_stats(m, vocab, dcfg, 2048, seed, summary_mode="random")["paired_margin"]
    return out


def run():
    vocab = build_vocab(); dcfg = DataCfg()
    res = {"token": [], "conditioned": []}
    for mode in ("token", "conditioned"):
        for seed in SEEDS:
            r = analyze_gate(mode, seed, vocab, dcfg)
            res[mode].append(r)
            print(f"[{mode} s{seed}] margin={r['paired_margin']:+.3f} std={r['standardized_margin']:+.2f} "
                  f"auroc={r['auroc_relevant_vs_distractor']:.3f} d2048={r['state_top1_2048']:.3f} "
                  f"d4096={r['state_top1_4096']:.3f}", flush=True)
    res["acceptance"] = accept(res)
    (HERE / "results" / "conditioned_analysis.json").write_text(json.dumps(res, indent=2, default=float))
    print("COND ANALYSIS:", json.dumps(res["acceptance"], indent=1, default=float), flush=True)
    print("COND DONE", flush=True)
    return res


def accept(res):
    c = res["conditioned"]
    margins = [x["paired_margin"] for x in c]
    aurocs = [x["auroc_relevant_vs_distractor"] for x in c]
    std_margins = [x["standardized_margin"] for x in c]
    d2048 = [x["state_top1_2048"] for x in c]
    d4096 = [x["state_top1_4096"] for x in c]
    ctrl_ok = all((x["paired_margin"] - x.get("margin_focus_removed", 0) > 0.02) or
                  (x["paired_margin"] - x.get("margin_focus_shuffled", 0) > 0.02) for x in c)
    decode_above_ctrl = all(x["state_top1_2048"] - x["control_top1_2048"] > 0.2 for x in c)
    passed = (all(m > 0 for m in margins) and st.mean(aurocs) > 0.55
              and ctrl_ok and decode_above_ctrl)
    preferred = (st.mean(std_margins) >= 0.20 and st.mean(aurocs) >= 0.70
                 and st.mean(d2048) >= 0.80 and st.mean(d4096) >= 0.60)
    return {
        "conditioned_margin_mean": st.mean(margins), "conditioned_margin_all_positive": all(m > 0 for m in margins),
        "conditioned_auroc_mean": st.mean(aurocs), "conditioned_standardized_margin_mean": st.mean(std_margins),
        "token_margin_mean": st.mean([x["paired_margin"] for x in res["token"]]),
        "token_auroc_mean": st.mean([x["auroc_relevant_vs_distractor"] for x in res["token"]]),
        "controls_eliminate_margin": ctrl_ok, "decode_above_controls": decode_above_ctrl,
        "conditioned_gate_passes": passed, "preferred_success": preferred,
        "launch_full_study": passed,
    }


if __name__ == "__main__":
    run()
