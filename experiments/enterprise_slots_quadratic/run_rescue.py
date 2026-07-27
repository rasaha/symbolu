"""
run_rescue.py — §2–§13 slot-policy diagnosis + bounded deterministic rescue.

Decisive question: is the S3→S4 gap caused by missing/evicted evidence (selection) or by reasoning/
output after the correct evidence is present? Measured directly via conditional accuracy
(acc | required evidence survived) + the §4 failure taxonomy. Then compares deterministic policies
P2–P5, role-aware slots (S3R), and a FAIR global-retrieval control (S1G), across capacity K.
No Phase. Quadratic module unchanged.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .schema import DomainCfg
from .dataset import generate
from .models import SlotQuadModel
from .train import train_model
from .evaluate import evaluate
from .diagnosis import conditional_metrics, classify_errors
from .causal_controls import integrity_report, control_accuracy

HERE = Path(__file__).resolve().parent
STEPS = 600
SEED = 0
MODE = "streaming"
N = 256


def _train(cfg, arm, K, policy):
    torch.manual_seed(SEED)
    m = SlotQuadModel(cfg, arm=arm, K=K)
    train_model(m, lambda bs, s: generate(cfg, N, MODE, bs, s), cfg, arm, K, policy=policy,
                steps=STEPS, seed=SEED)
    return m


def _row(m, te, cfg, arm, K, policy):
    r = evaluate(m, te, cfg, arm, K, policy)
    c = conditional_metrics(m, te, cfg, arm, K, policy)
    return {"accuracy": r["accuracy"], "acc_given_required_survived": c["acc_given_required_survived"],
            "version_acc": r["active_version_acc"], "version_acc_given_survived": c["version_acc_given_survived"],
            "conflict_f1": r["conflict"]["f1"], "required_survival": r["required_survival_rate"],
            "unauthorized_inclusion": r["unauthorized_inclusion_rate"],
            "evidence_id_preservation": r["evidence_id_preservation"],
            "records_encoded_per_query": r["records_encoded_per_query"], "n_survived": c["n_survived"]}


def run():
    cfg = DomainCfg(); t0 = time.time(); res = {"steps": STEPS, "mode": MODE, "N": N}
    te = generate(cfg, N, MODE, 300, 56000)

    # ---- policy comparison @K=8 (S3 with P2..P5), plus S3R / S1G / S4 ----
    res["policies_K8"] = {}
    models = {}
    for arm, policy, tag in [("S3", "P2", "S3_P2"), ("S3", "P3", "S3_P3"), ("S3", "P4", "S3_P4"),
                             ("S3", "P5", "S3_P5"), ("S3R", "P2", "S3R_roles"),
                             ("S1G", "P2", "S1G_global"), ("S4", "P6", "S4_oracle")]:
        m = _train(cfg, arm, 8, policy); models[tag] = m
        res["policies_K8"][tag] = _row(m, te, cfg, arm, 8, policy)
        x = res["policies_K8"][tag]
        print(f"{tag}: acc={x['accuracy']:.3f} acc|surv={x['acc_given_required_survived']:.3f} "
              f"ver={x['version_acc']:.2f} conf={x['conflict_f1']:.2f} surv={x['required_survival']:.2f} "
              f"({time.time()-t0:.0f}s)", flush=True)
    (HERE / "results" / "rescue.json").write_text(json.dumps(res, indent=2, default=float))

    # ---- capacity sweep @P2 (S3) ----
    res["capacity_S3_P2"] = {}
    cap_models = {8: models["S3_P2"]}
    for K in (4, 8, 16, 32):
        m = cap_models.get(K) or _train(cfg, "S3", K, "P2")
        res["capacity_S3_P2"][f"K{K}"] = _row(m, te, cfg, "S3", K, "P2")
        cap_models[K] = m
        x = res["capacity_S3_P2"][f"K{K}"]
        print(f"K={K}: acc={x['accuracy']:.3f} acc|surv={x['acc_given_required_survived']:.3f} "
              f"surv={x['required_survival']:.2f} ({time.time()-t0:.0f}s)", flush=True)
    res["S4_ref"] = _row(_train(cfg, "S4", 16, "P6"), te, cfg, "S4", 16, "P6")
    (HERE / "results" / "rescue.json").write_text(json.dumps(res, indent=2, default=float))

    # ---- failure taxonomy on S3(P2, K=8) ----
    res["taxonomy_S3_P2_K8"] = classify_errors(models["S3_P2"], te, cfg, "S3", 8, "P2")
    print("taxonomy:", json.dumps(res["taxonomy_S3_P2_K8"]["pct"], default=float), flush=True)

    # ---- integrity + causal ablations on S3(P2, K=16) ----
    res["integrity"] = integrity_report(te, cfg, "S3", 16, "P2")
    m16 = cap_models[16]
    res["causal_S3_K16"] = {c: control_accuracy(m16, te, cfg, "S3", 16, control=c, policy="P2")
                            for c in ("none", "evict_required", "evict_irrelevant", "shuffle_slots", "zero_slot_repr")}
    print("integrity:", json.dumps(res["integrity"]), flush=True)
    print("causal:", json.dumps(res["causal_S3_K16"], default=float), flush=True)

    # ---- verdict ----
    best_pol = max(("S3_P2", "S3_P3", "S3_P4", "S3_P5"),
                   key=lambda t: res["policies_K8"][t]["accuracy"])
    s3 = res["policies_K8"]["S3_P2"]["accuracy"]; s4 = res["S4_ref"]["accuracy"]
    best_acc = res["policies_K8"][best_pol]["accuracy"]
    gap = s4 - s3
    tax = res["taxonomy_S3_P2_K8"]["pct"]
    missing = sum(tax[t] for t in ("MISSING_ADMISSION", "PREMATURE_EVICTION", "CONFLICT_PAIR_INCOMPLETE",
                                   "CHAIN_LINK_MISSING", "STALE_DOMINANCE", "DUPLICATE_WASTE"))
    reasoning = tax["REASONING_FAILURE"] + tax["OUTPUT_MAPPING_FAILURE"]
    acc_surv = res["policies_K8"]["S3_P2"]["acc_given_required_survived"]
    cc = res["causal_S3_K16"]
    # smallest K within 95% of best capacity accuracy
    cap = res["capacity_S3_P2"]; best_cap = max(cap[k]["accuracy"] for k in cap)
    best_K = min((int(k[1:]) for k in cap if cap[k]["accuracy"] >= 0.95 * best_cap), default=32)
    res["verdict"] = {
        "S3_to_S4_gap": gap,
        "gap_explained_by_missing_evidence_pct": missing,
        "gap_explained_by_reasoning_pct": reasoning,
        "acc_given_required_survived": acc_surv,
        "best_deterministic_policy": best_pol,
        "best_policy_closes_gap_pct": (best_acc - s3) / max(1e-9, gap),
        "S1G_vs_S3": ("better" if res["policies_K8"]["S1G_global"]["accuracy"] > best_acc + 0.02 else
                      "worse" if res["policies_K8"]["S1G_global"]["accuracy"] < best_acc - 0.02 else "equivalent"),
        "smallest_K_95pct": best_K,
        "causal_required_gt_irrelevant": cc["evict_required"] < cc["evict_irrelevant"] - 0.02,
        "primary_bottleneck": ("admission_eviction" if acc_surv >= 0.75 and s3 < s4 - 0.05 else
                               "reasoning_or_output" if acc_surv < 0.6 else "capacity"),
        "binding_slot_survival_value": "validated" if res["policies_K8"]["S3_P2"]["required_survival"] > 0.5 else "unsupported",
        "provenance_access_isolation": "verified" if res["integrity"]["unauthorized_inclusion_rate"] == 0
                                       and res["integrity"]["evidence_id_preservation"] == 1.0 else "failed",
    }
    (HERE / "results" / "rescue.json").write_text(json.dumps(res, indent=2, default=float))
    print("VERDICT:", json.dumps(res["verdict"], default=float), flush=True)
    print("RESCUE DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
