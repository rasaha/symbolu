#!/usr/bin/env python3
"""Curate committed summary artifacts from the raw Stage A / Stage B run outputs.

Reads artifacts/stageA/*_results.json and artifacts/stageB/*_results.json (raw, gitignored) and
writes compact, committed summaries under hybrid_llm_vnext_lab/artifacts/slot_formation_stabilization/.
Pure stdlib. Idempotent.
"""
from __future__ import annotations

import glob
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parents[1]
REPO = LAB.parent
OUT = LAB / "artifacts" / "slot_formation_stabilization"
OUT.mkdir(parents=True, exist_ok=True)
APLUS = json.loads((HERE / "frozen_aplus_seeds_367.json").read_text())


def load(run, arm):
    p = HERE / "artifacts" / run / f"{arm}_results.json"
    return {r["seed"]: r for r in json.loads(p.read_text())["records"]} if p.exists() else {}


def compact(rec):
    return {
        "seed": rec["seed"], "params": rec["params"], "ff": rec["ff"],
        "needle_by_dist": {k: round(v, 4) for k, v in rec["needle_by_dist"].items()},
        "ppl": {k: round(v, 2) for k, v in rec["ppl"].items()},
        "ablation": {k: (round(v, 4) if isinstance(v, (int, float)) else v)
                     for k, v in rec.get("ablation", {}).items() if k != "slot_diagnostics"},
        "train_s": rec.get("train_s"),
    }


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    stageA = {a: load("stageA", a) for a in ["B0", "O1", "O2", "K1", "C1", "R1", "CR1"]}
    stageB = {a: load("stageB", a) for a in ["A+", "B0", "CR1"]}

    # 1. diagnostic_results.json (Stage A compact, per arm/seed)
    diag = {"stage": "A", "diagnostic_seeds": [3, 6, 7],
            "development_set_disclaimer": "Seeds 3,6,7 are a DEVELOPMENT set; results select a candidate and are NOT a fresh holdout result.",
            "aplus_reused_frozen": {s: {"needle_by_dist": APLUS[s]["needle_by_dist"], "ppl": APLUS[s]["ppl"]} for s in APLUS},
            "arms": {a: {str(s): compact(r) for s, r in byseed.items()} for a, byseed in stageA.items()}}
    (OUT / "diagnostic_results.json").write_text(json.dumps(diag, indent=2) + "\n")

    # 2. routing_diagnostics.json (trajectories: does overlap rise before needle?)
    def traj(rec):
        rows = []
        for t in rec["trajectory"]:
            row = {"step": t["step"], "needle_d96": round(t["needle_d96"], 4)}
            if "routing" in t:
                r = t["routing"]
                row.update({"write_read_overlap": round(r["write_read_overlap"], 4),
                            "correct_slot_rank": round(r["rank_of_highest_write_slot_under_read"], 3),
                            "read_prob_on_top_write": round(r["read_prob_on_highest_write_slot"], 4),
                            "top1_agreement": round(r["top1_slot_agreement"], 4),
                            "write_entropy": round(r["write_entropy"], 3),
                            "read_entropy": round(r["read_entropy"], 3),
                            "addr_logit_margin": round(r["address_logit_margin"], 4),
                            "write_gate": round(r["write_gate_at_fact"], 4)})
            if "grad_norms" in t:
                g = t["grad_norms"]
                row.update({"grad_slot_keys": round(g["grad_norm_slot_keys"], 5),
                            "grad_read_proj": round(g["grad_norm_read_proj"], 5),
                            "grad_write_proj": round(g["grad_norm_write_proj"], 5)})
            rows.append(row)
        return rows
    routing = {"note": "Central question: does fact-write/query-read overlap rise BEFORE final needle@d96 rises? Argued from these trajectories, not aggregate utilization.",
               "checkpoints": [0, 60, 120, 300, 600, 900, 1200],
               "stageA": {a: {str(s): traj(r) for s, r in byseed.items()} for a, byseed in stageA.items()},
               "stageB": {a: {str(s): traj(r) for s, r in byseed.items()} for a, byseed in stageB.items() if a != "A+"},
               "seed9_retention_finding": "CR1 seed9 (fresh): needle peaked 1.000 at step300 (overlap ~1.0) then decayed 0.62->0.10->0.00 after alignment lambda->0 (step600) and curriculum handoff to original distribution (step700). Seeds 8/10/11 dipped at step900 but recovered by 1200; seed9 did not. Post-scaffold retention failure = architectural bistability, not incapacity."}
    (OUT / "routing_diagnostics.json").write_text(json.dumps(routing, indent=2) + "\n")

    # 3. optimizer_group_audit.json (from any arm; groups identical across arms)
    any_rec = next(iter(stageA["B0"].values()))
    (OUT / "optimizer_group_audit.json").write_text(json.dumps({
        "note": "Slot-routing vs non-slot AdamW parameter groups. O1/O2 use two groups with per-group warmup; other arms use a single group (identical to the frozen harness).",
        "param_group_audit": any_rec["param_group_audit"],
        "O1": {"slot_lr": 1e-3, "slot_warmup": 180, "nonslot_lr": 2e-3, "nonslot_warmup": 60,
               "warmups_by_group": stageA["O1"][3]["warmups_by_group"], "grouped": stageA["O1"][3]["grouped_optimizer"]},
        "O2": {"slot_lr": 3e-3, "slot_warmup": 180, "nonslot_lr": 2e-3, "nonslot_warmup": 60,
               "warmups_by_group": stageA["O2"][3]["warmups_by_group"], "grouped": stageA["O2"][3]["grouped_optimizer"]},
    }, indent=2) + "\n")

    # 4. initialization_audit.json (K1)
    k1 = stageA["K1"][3]
    (OUT / "initialization_audit.json").write_text(json.dumps({
        "note": "K1 orthogonal slot-key init vs baseline. The frozen BindingSlots ALREADY orthogonalizes (32<=64), so baseline off-diagonal cosine is ~0; K1 is a re-seeded orthogonalization with the same (near-zero) off-diagonal cosine -> Family 2 has ~no orthogonality headroom.",
        "K1_seed3_init_audit": k1.get("init_audit"),
    }, indent=2) + "\n")

    # 5. curriculum_audit.json
    (OUT / "curriculum_audit.json").write_text(json.dumps({
        "boundaries": [300, 700, 1200],
        "phase_1": "steps 1-300: needle-only at distance d16, single supervised position",
        "phase_2": "steps 301-700: 70% needle (d16/d96), 30% binding k=2 (interference)",
        "phase_3": "steps 701-1200: ORIGINAL ABC_MIX (frozen train_batch)",
        "final_500_steps_original": True,
        "example_count": "16 per step x 1200 steps = 19200, identical to baseline",
        "tokenizer_corpus_unchanged": {"vocab": 1291, "corpus_tokens": 55547},
        "leakage_control": "supervised target is always only the answer position (mask at pos-1); value never adjacent to query beyond the designed distance.",
        "C1_causal_finding": "C1 (curriculum alone) reaches 3/3 needle but FAILS the causal gate on seeds 6,7 (slots_off leaves 0.575/rand 0.90 on s6; rand 0.33 on s7) -> gain routed through the multi-layer local-window pathway, NOT slots. Adding alignment (CR1) restores clean causal collapse (slots_off ~0 on all seeds).",
    }, indent=2) + "\n")

    # 6. alignment_audit.json (loss logs)
    def align_log(rec):
        return [{"step": l["step"], "main_loss": round(l["main_loss"], 4),
                 "lambda": (l["aux"]["lambda"] if l.get("aux") else 0.0),
                 "L_align": (round(l["aux"]["L_align"], 4) if l.get("aux") else None),
                 "overlap": (round(l["aux"]["overlap"], 4) if l.get("aux") else None)}
                for l in rec.get("loss_log", [])]
    (OUT / "alignment_audit.json").write_text(json.dumps({
        "objective": "L_align = -log(mean_layers,batch sum_m w_m*r_m + 1e-6); w=write-addr at fact value-token, r=read-addr at query.",
        "lambda_schedule": {"steps_1_300": 0.10, "steps_301_600": "linear 0.10->0", "steps_601_1200": 0.0},
        "guarantees": ["label-free", "no fixed correct slot", "no answer-token leakage (verified by test)", "no N x N tensor", "zero after step 600 and during all eval"],
        "R1_seed6_loss_log": align_log(stageA["R1"][6]),
        "CR1_seed8_loss_log": align_log(stageB["CR1"][8]) if 8 in stageB.get("CR1", {}) else None,
    }, indent=2) + "\n")

    # 7. fresh_holdout_results.json (Stage B compact)
    (OUT / "fresh_holdout_results.json").write_text(json.dumps({
        "stage": "B", "fresh_seeds": [8, 9, 10, 11, 12],
        "seeds_uncontaminated": True,
        "arms": {a: {str(s): compact(r) for s, r in byseed.items()} for a, byseed in stageB.items()},
    }, indent=2) + "\n")

    # 8. complexity_report.json is regenerated by complexity_report.py (kept)

    # 9. frozen_artifact_verification.json
    (OUT / "frozen_artifact_verification.json").write_text(json.dumps({
        "frozen_abc_json": {"path": "experiments/phase_lc/results/abc.json",
                            "sha256_expected": "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482",
                            "sha256_actual": sha(REPO / "experiments/phase_lc/results/abc.json"),
                            "byte_identical": sha(REPO / "experiments/phase_lc/results/abc.json") == "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482"},
        "five_seed_results_unchanged": sha(LAB / "artifacts/five_seed_results_run1.json") == "87dd642b04e955a1057acea61feb0ab7e3f9efe8f1b26b3ca13da21312f52ae3",
        "five_seed_classification_unchanged": sha(LAB / "artifacts/five_seed_classification_run1.json") == "25aa469863e45de7b52bf1ebe7fb7bea729cf090f7f67bb60ce91b5d46fe354a",
        "platform_freeze_manifest": {"path": "platform/PLATFORM_FREEZE_V1.json",
                                     "sha256": sha(REPO / "platform/PLATFORM_FREEZE_V1.json")},
    }, indent=2) + "\n")

    print("curated artifacts written to", OUT)


if __name__ == "__main__":
    main()
