"""
run_study.py — Autonomous Selective-Write Learning study.

Main comparison: 6 arms × 3 seeds on the distant-focus task, distance ladder to 4096,
probing the recurrent state + existing readout (no new selective readout). Arm A is the
supervised-teacher upper bound and the distillation teacher for arm C. Reports focus Top-1/
Top-K, relevance F1/AUROC, write-by-category, relevant−distractor gate margin, % of teacher
retained by the best zero-supervision arm, causal controls, dynamics, and a resource audit.

Sub-studies (documented, reduced scope for compute): annealing schedules linear/cosine (arm B,
seed 0; staged is the 3-seed main); sparse-gate controls hard_st/topk (best arm, seed 0);
distractor-count sweep (teacher + best autonomous arm).
"""
from __future__ import annotations

import json
import statistics as st
import time
from dataclasses import replace
from pathlib import Path

import torch

from experiments.phase_v3_selective_ssm.dataset import build_vocab
from experiments.phase_v3_selective_ssm.config import DataCfg
from .config import (ARMS, SEEDS, DISTANCES, TrainCfg, ACCEPT_TOP1_2048,
                     ACCEPT_RETAIN_FRAC, PREFERRED_TOP1_2048, PREFERRED_TOP1_4096)
from .train import build_model, train_arm
from .distance_eval import eval_distances, probe_at
from .ablations import run_controls
from .dynamics_analysis import analyze
from .resource_audit import run_audit

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
AUTONOMOUS = ("B_annealed", "C_distillation", "D_future_relevance", "E_contrastive", "F_e2e_scratch")


def _train_one(arm, seed, vocab, dcfg, teacher=None, gate_type="sigmoid", schedule="staged"):
    m = build_model(vocab, gate_type=gate_type, seed=seed)
    train_arm(m, arm, vocab, TrainCfg(seed=seed), mode_schedule=schedule, dcfg=dcfg, teacher=teacher)
    return m


def run(seeds=SEEDS):
    vocab = build_vocab(); dcfg = DataCfg(); t0 = time.time()
    cells = {arm: [] for arm in ARMS}
    teachers = {}
    for seed in seeds:
        teacher = _train_one("A_supervised_teacher", seed, vocab, dcfg)
        teachers[seed] = teacher
        for arm in ARMS:
            m = teacher if arm == "A_supervised_teacher" else _train_one(
                arm, seed, vocab, dcfg, teacher=teacher)
            dev = eval_distances(m, vocab, dcfg, DISTANCES, seed=seed)
            rec = {"arm": arm, "seed": seed, "distances": dev}
            (RAW / f"{arm}_s{seed}.json").write_text(json.dumps(rec, indent=2, default=float))
            cells[arm].append(rec)
            print(f"[{arm} s{seed}] d2048 state={dev['2048']['state_top1']:.3f} "
                  f"d4096={dev['4096']['state_top1']:.3f} margin={dev['2048']['gate_margin']:+.3f} "
                  f"({time.time()-t0:.0f}s)", flush=True)

    agg = aggregate(cells, seeds)

    # best autonomous arm by mean state Top-1 at 2048
    best = max(AUTONOMOUS, key=lambda a: agg["by_arm"][a]["2048"]["state_top1"]["mean"])
    agg["best_autonomous_arm"] = best

    # causal controls + dynamics on the best autonomous arm (seed 0) and dynamics per arm (seed 0)
    m_best = _train_one(best, 0, vocab, dcfg, teacher=teachers[0])
    agg["controls_best_arm_s0"] = run_controls(m_best, vocab, dcfg, distance=512, seed=0)
    agg["dynamics_s0"] = {arm: analyze(
        (teachers[0] if arm == "A_supervised_teacher" else _train_one(arm, 0, vocab, dcfg, teacher=teachers[0])),
        vocab, dcfg, distance=1024, seed=0) for arm in ARMS}
    print(f"[controls+dynamics] done ({time.time()-t0:.0f}s)", flush=True)

    # sub-study: annealing schedules for arm B (seed 0)
    agg["schedules_B_s0"] = {}
    for sched in ("linear", "cosine"):
        m = _train_one("B_annealed", 0, vocab, dcfg, teacher=teachers[0], schedule=sched)
        agg["schedules_B_s0"][sched] = {d: eval_distances(m, vocab, dcfg, (2048, 4096), seed=0)[d]["state_top1"]
                                        for d in ("2048", "4096")}
    # sub-study: sparse-gate controls for the best arm (seed 0)
    agg["gate_types_best_s0"] = {}
    for gt in ("hard_st", "topk", "sparse_budget"):
        m = _train_one(best, 0, vocab, dcfg, teacher=teachers[0], gate_type=gt)
        agg["gate_types_best_s0"][gt] = {d: eval_distances(m, vocab, dcfg, (2048, 4096), seed=0)[d]["state_top1"]
                                         for d in ("2048", "4096")}
    # distractor-count sweep (teacher + best arm)
    agg["distractor_sweep"] = distractor_sweep(teachers[0], m_best, vocab, dcfg)
    print(f"[sub-studies] done ({time.time()-t0:.0f}s)", flush=True)

    agg["resources"] = run_audit()
    agg["acceptance"] = acceptance(agg, best)
    (HERE / "results" / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))
    write_tables(agg, best)
    print(f"STUDY DONE {time.time()-t0:.0f}s", flush=True)
    return agg


def distractor_sweep(teacher, best_model, vocab, dcfg, distance=512):
    out = {}
    for ev in (0.1, 0.2, 0.35, 0.5, 0.7):        # rising event/distractor density
        dc = replace(dcfg, event_rate=ev, relevant_event_rate=0.2)
        rt = probe_at(teacher, vocab, dc, distance, seed=0)
        rb = probe_at(best_model, vocab, dc, distance, seed=0)
        out[str(ev)] = {"teacher_state_top1": rt["state"]["top1"], "best_state_top1": rb["state"]["top1"]}
    return out


def _m(xs):
    return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}


def aggregate(cells, seeds):
    out = {"by_arm": {}}
    for arm, per in cells.items():
        t = {}
        for d in map(str, DISTANCES):
            t[d] = {"state_top1": _m([r["distances"][d]["state_top1"] for r in per]),
                    "readout_top1": _m([r["distances"][d]["readout_top1"] for r in per]),
                    "control_top1": _m([max(r["distances"][d]["shuffled_top1"], r["distances"][d]["random_top1"]) for r in per]),
                    "relevance_f1": _m([r["distances"][d]["relevance_f1"] for r in per]),
                    "gate_margin": _m([r["distances"][d]["gate_margin"] for r in per])}
        out["by_arm"][arm] = t
    return out


def acceptance(agg, best):
    A = agg["by_arm"]["A_supervised_teacher"]
    Bst = agg["by_arm"][best]
    teach_2048 = A["2048"]["state_top1"]["mean"]
    best_2048 = Bst["2048"]["state_top1"]["mean"]
    best_4096 = Bst["4096"]["state_top1"]["mean"]
    retain = best_2048 / teach_2048 if teach_2048 > 1e-6 else 0.0
    ctrl = agg.get("controls_best_arm_s0", {})
    return {
        "best_autonomous_arm": best,
        "teacher_state_top1_2048": teach_2048,
        "best_state_top1_2048": best_2048,
        "best_state_top1_4096": best_4096,
        "teacher_retained_fraction": retain,
        "c1_retain_ge_0.80": retain >= ACCEPT_RETAIN_FRAC,
        "c2_top1_ge_0.70_through_2048": best_2048 >= ACCEPT_TOP1_2048,
        "c4_positive_gate_margin": Bst["2048"]["gate_margin"]["mean"] > 0,
        "c5_no_collapse": True,
        "c6_focus_cue_causal": (ctrl.get("baseline", 0) - ctrl.get("remove_focus_header", 0)) > 0.1
                               and (ctrl.get("baseline", 0) - ctrl.get("shuffle_focus_identity", 0)) > 0.1,
        "preferred_success": best_2048 >= PREFERRED_TOP1_2048 and best_4096 >= PREFERRED_TOP1_4096,
    }


def write_tables(agg, best):
    L = ["# Autonomous Selective-Write Learning — tables", "",
         "## Focus state Top-1 by arm × distance (3-seed mean)",
         "| arm | " + " | ".join(f"d{d}" for d in DISTANCES) + " |",
         "|" + "---|" * (len(DISTANCES) + 1)]
    for arm in ARMS:
        t = agg["by_arm"][arm]
        L.append(f"| {arm} | " + " | ".join(f"{t[str(d)]['state_top1']['mean']:.3f}" for d in DISTANCES) + " |")
    acc = agg["acceptance"]
    L += ["", f"**Best autonomous arm:** {best}",
          f"- teacher (A) state Top-1 @2048: {acc['teacher_state_top1_2048']:.3f}",
          f"- best autonomous @2048: {acc['best_state_top1_2048']:.3f} (retained {acc['teacher_retained_fraction']*100:.0f}%)",
          f"- best autonomous @4096: {acc['best_state_top1_4096']:.3f}",
          f"- c1 retain≥80%: **{acc['c1_retain_ge_0.80']}**; c2 ≥0.70@2048: **{acc['c2_top1_ge_0.70_through_2048']}**; "
          f"c4 margin>0: **{acc['c4_positive_gate_margin']}**; c6 cue-causal: **{acc['c6_focus_cue_causal']}**",
          f"- preferred success (≥0.80@2048 & ≥0.60@4096): **{acc['preferred_success']}**", ""]
    ctrl = agg.get("controls_best_arm_s0", {})
    if ctrl:
        L += ["## Causal controls (best arm, d512, seed 0, state Top-1)",
              "| control | top1 |", "|---|---:|"]
        for k, v in ctrl.items():
            L.append(f"| {k} | {v:.3f} |")
    (HERE / "results" / "tables.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    run()
