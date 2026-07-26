"""
run_all.py — run every diagnostic probe on the cached arm checkpoints and collect
results into results/aggregate.json and results/tables.md.

Assumes checkpoints exist (experiments.phase_guidance_diagnostics.train_ckpts).
Each probe writes its own results/raw/*.json; this runner also copies the arm
train/eval metrics into the aggregate for the headline reproduction.
"""
from __future__ import annotations
import json
from pathlib import Path

from experiments.phase_guidance_diagnostics import _common as C
from experiments.phase_guidance_diagnostics import (
    topic_probe, distance_probe, dilution_probe, decay_probe, head_analysis,
    guidance_probe, score_decomposition, slot_chain_trace, shortcut_checks,
    multitask_interference,
)

HERE = Path(__file__).resolve().parent
RES = HERE / "results"


def arm_metrics():
    out = {}
    for p in sorted((RES / "ckpt").glob("*.json")):
        d = json.loads(p.read_text())
        out[f"{d['arm']}_p{d['pressure']}"] = d.get("metrics", {})
    return out


def main():
    agg = {"arm_metrics": arm_metrics(), "probes": {}}

    print("\n===== Question A/F: topic decodability =====")
    agg["probes"]["topic_probe"] = {a: topic_probe.run(a, "3x") for a in ("D", "C")}

    print("\n===== Question B: distance/decay-over-distance =====")
    agg["probes"]["distance_probe"] = {"D": distance_probe.run("D", "3x")}

    print("\n===== Question C: cumulative-normalization dilution =====")
    agg["probes"]["dilution_probe"] = {"D": dilution_probe.run("D", "3x")}

    print("\n===== Question D: decay interventions =====")
    agg["probes"]["decay_probe"] = {"D": decay_probe.run("D", "3x")}

    print("\n===== Question E: per-head analysis =====")
    agg["probes"]["head_analysis"] = {"D": head_analysis.run("D", "3x")}

    print("\n===== Question F: guidance-head extraction =====")
    agg["probes"]["guidance_probe"] = {"D": guidance_probe.run("D", "3x")}

    print("\n===== Question H: content-vs-Phase score decomposition + beta sweep =====")
    agg["probes"]["score_decomposition"] = {"D": score_decomposition.run("D", "3x")}

    print("\n===== Questions I/J: slot-chain trace + pressure validity =====")
    sc = {}
    for a in ("C", "D"):
        for p in ("1x", "3x"):
            sc[f"{a}_{p}"] = slot_chain_trace.run(a, p)
    agg["probes"]["slot_chain_trace"] = sc

    print("\n===== Question K: shortcut checks =====")
    agg["probes"]["shortcut_checks"] = {a: shortcut_checks.run(a, "3x") for a in ("C", "D")}

    print("\n===== Question L: multitask interference =====")
    agg["probes"]["multitask_interference"] = {"D": multitask_interference.run("D", "3x")}

    (RES / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))
    print("\nwrote results/aggregate.json")
    write_tables(agg)


def write_tables(agg):
    L = ["# Phase-guidance diagnostics — result tables\n"]
    am = agg["arm_metrics"]
    L.append("## Headline: answer accuracy & write-F1 by arm/pressure (seed 0)\n")
    L.append("| arm/pressure | answer_acc | write_f1 | write_prec | write_rec |")
    L.append("|---|---:|---:|---:|---:|")
    for k in sorted(am):
        m = am[k]
        L.append(f"| {k} | {m.get('answer_acc'):.3f} | {m.get('write_f1'):.3f} | "
                 f"{m.get('write_precision'):.3f} | {m.get('write_recall'):.3f} |")
    (RES / "tables.md").write_text("\n".join(L) + "\n")
    print("wrote results/tables.md")


if __name__ == "__main__":
    main()
