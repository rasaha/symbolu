"""
run_pilot.py — §17 validity pilot: one seed, N=64 & 256, K=4/8/16, arms S0–S4, policy P2.

Proceed to the full matrix only if: S1 beats S0 on ≥1 relational task; S2 beats S0 on evidence
survival under streaming pressure; S4 (oracle) shows the combined architecture can solve the task;
provenance & access-control pass; no leakage; no N×N. Emits results/pilot.json + a validity verdict.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .schema import DomainCfg
from .dataset import generate
from .models import SlotQuadModel, working_set
from .train import train_model
from .evaluate import evaluate
from .causal_controls import integrity_report, control_accuracy

HERE = Path(__file__).resolve().parent
STEPS = 700
SEED = 0
ARMS = ("S0", "S1", "S2", "S3", "S4")


def _train_eval(cfg, arm, mode, N, K, te):
    torch.manual_seed(SEED)
    m = SlotQuadModel(cfg, arm=arm, K=K)
    train_model(m, lambda bs, s: generate(cfg, N, mode, bs, s), cfg, arm, K, steps=STEPS, seed=SEED)
    return m, evaluate(m, te, cfg, arm, K)


def run():
    cfg = DomainCfg(); t0 = time.time(); res = {"seed": SEED, "steps": STEPS}

    # ---- deterministic required-survival grid ----
    surv = {}
    for mode in ("one_shot", "streaming"):
        surv[mode] = {}
        for N in (64, 256):
            te = generate(cfg, N, mode, 200, 55000)
            for K in (4, 8, 16):
                surv[mode][f"N{N}_K{K}"] = {a: sum(working_set(ex, a, K).get("required_survived", False)
                                                    for ex in te) / len(te) for a in ARMS}
    res["required_survival"] = surv
    print("survival streaming N256:", json.dumps(surv["streaming"]["N256_K8"]), flush=True)

    # ---- accuracy: streaming (K=4/8/16) + one_shot (K=8 control), N=256 ----
    acc = {"streaming": {}, "one_shot": {}}
    detail = {}
    te_s = generate(cfg, 256, "streaming", 300, 56000)
    for K in (4, 8, 16):
        acc["streaming"][f"K{K}"] = {}
        for a in ARMS:
            m, r = _train_eval(cfg, a, "streaming", 256, K, te_s)
            acc["streaming"][f"K{K}"][a] = r["accuracy"]
            if K == 16:
                detail[a] = {k: r[k] for k in ("accuracy", "conflict", "active_version_acc",
                             "abstention", "required_survival_rate", "unauthorized_inclusion_rate",
                             "evidence_id_preservation", "records_encoded_per_query")}
            print(f"stream K={K} {a}: acc={r['accuracy']:.3f} conf_f1={r['conflict']['f1']:.2f} "
                  f"ver={r['active_version_acc']:.2f} ({time.time()-t0:.0f}s)", flush=True)
    te_o = generate(cfg, 256, "one_shot", 300, 57000)
    for a in ARMS:
        m, r = _train_eval(cfg, a, "one_shot", 256, 8, te_o)
        acc["one_shot"][a] = {"accuracy": r["accuracy"], "conflict_f1": r["conflict"]["f1"],
                              "version_acc": r["active_version_acc"]}
        print(f"oneshot K=8 {a}: acc={r['accuracy']:.3f} conf_f1={r['conflict']['f1']:.2f}", flush=True)
    res["accuracy"] = acc; res["detail_streaming_K16"] = detail

    # ---- integrity + causal controls on S3 (streaming K=16) ----
    res["integrity_S3"] = integrity_report(te_s, cfg, "S3", 16)
    torch.manual_seed(SEED)
    m3 = SlotQuadModel(cfg, arm="S3", K=16)
    train_model(m3, lambda bs, s: generate(cfg, 256, "streaming", bs, s), cfg, "S3", 16, steps=STEPS, seed=SEED)
    res["causal_S3"] = {c: control_accuracy(m3, te_s, cfg, "S3", 16, control=c)
                        for c in ("none", "evict_required", "evict_irrelevant", "shuffle_slots", "zero_slot_repr")}
    print("integrity:", json.dumps(res["integrity_S3"]), flush=True)
    print("causal:", json.dumps(res["causal_S3"]), flush=True)

    # ---- validity gates ----
    s0o, s1o = acc["one_shot"]["S0"], acc["one_shot"]["S1"]
    s4 = max(acc["streaming"][f"K{K}"]["S4"] for K in (4, 8, 16))
    gate = {
        "S1_beats_S0_relational": (s1o["conflict_f1"] - s0o["conflict_f1"] >= 0.03) or
                                  (s1o["version_acc"] - s0o["version_acc"] >= 0.03),
        "S2_beats_S0_survival_streaming": surv["streaming"]["N256_K8"]["S2"] >
                                          surv["streaming"]["N256_K8"]["S0"] + 0.05,
        "S4_can_solve": s4 >= 0.70,
        "provenance_access_pass": res["integrity_S3"]["unauthorized_inclusion_rate"] == 0.0 and
                                  res["integrity_S3"]["evidence_id_preservation"] == 1.0 and
                                  res["integrity_S3"]["injected_unauthorized_leak_rate"] == 0.0,
        "causal_required_gt_irrelevant": res["causal_S3"]["evict_required"] <
                                         res["causal_S3"]["evict_irrelevant"] - 0.02,
    }
    gate["PILOT_VALID"] = all(gate.values())
    res["validity_gate"] = gate
    (HERE / "results" / "pilot.json").write_text(json.dumps(res, indent=2, default=float))
    print("VALIDITY_GATE:", json.dumps(gate, default=float), flush=True)
    print("PILOT_VALID" if gate["PILOT_VALID"] else "PILOT_INVALID", flush=True)
    print("PILOT DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
