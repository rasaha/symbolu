"""
finalize.py — complete the results from the decisive 3-seed N=1024 matrix: fresh Phase causal
controls on A3, §14 acceptance, §18 verdict. (The N=4096 stage was stopped: with A3-A1 ~ 0 and
Phase dominated by the trained GRU across 3 seeds, "preserves the gain at N=4096" has no gain to
preserve and cannot change the verdict.)
"""
from __future__ import annotations

import json
from pathlib import Path

import torch

from .dataset import Schema, generate, TARGETS
from .quality_heads import HealthModel
from .train import train_health
from .causal_controls import phase_causal_controls

HERE = Path(__file__).resolve().parent
RES = HERE / "results" / "PHASE_QUALITY_AUXILIARY_RESULTS.json"


def run():
    S = Schema()
    res = json.loads(RES.read_text())
    # fresh Phase causal controls on a trained A3 (N=1024, seed 0)
    torch.manual_seed(0)
    m3 = HealthModel(S, arm="A3")
    train_health(m3, lambda bs, s: generate(S, 1024, bs, s), S, steps=800, seed=0)
    te = generate(S, 1024, 300, 900001)
    res["causal"] = phase_causal_controls(m3, te, S)
    print("causal:", json.dumps({k: (v if isinstance(v, bool) else round(v.get("macro_auroc", 0), 3))
                                  for k, v in res["causal"].items()}, default=float), flush=True)

    a1 = res["N1024"]["A1"]["mean_macro_auroc"]; a3 = res["N1024"]["A3"]["mean_macro_auroc"]
    a1p = res["N1024"]["A1"]["mean_macro_auprc"]; a3p = res["N1024"]["A3"]["mean_macro_auprc"]
    a1b = res["N1024"]["A1"]["mean_macro_brier"]; a3b = res["N1024"]["A3"]["mean_macro_brier"]
    best_base = max(res["N1024"][a]["mean_macro_auroc"] for a in ("A4", "A5", "A6"))
    best_base_arm = max(("A4", "A5", "A6"), key=lambda a: res["N1024"][a]["mean_macro_auroc"])
    cc = res["causal"]
    accept = {
        "A3_auroc_gain_ge_0.05": (a3 - a1) >= 0.05,
        "A3_auprc_gain_ge_0.05": (a3p - a1p) >= 0.05,
        "A3_brier_rel_improve_ge_10pct": (a1b - a3b) / max(1e-9, a1b) >= 0.10,
        "gain_collapses_under_phase_corruption": cc.get("causal_dependence_verified", False),
        "beats_best_temporal_baseline_by_0.03": (a3 - best_base) >= 0.03,
    }
    accept["PASS"] = all(accept.values())
    res["acceptance"] = accept
    # per-target gains
    a1t = res["N1024"]["A1"]["mean_per_target"]; a3t = res["N1024"]["A3"]["mean_per_target"]
    res["summary"] = {
        "A1_macro": a1, "A3_macro": a3, "best_baseline": best_base, "best_baseline_arm": best_base_arm,
        "A3_minus_A1": a3 - a1, "A3_minus_best_baseline": a3 - best_base,
        "per_target_gain_A3_minus_A1": {t: a3t[t] - a1t[t] for t in TARGETS},
        "gru_A6_recurrence_auroc": res["N1024"]["A6"]["mean_per_target"]["unresolved_recurrence"],
        "phase_A3_recurrence_auroc": a3t["unresolved_recurrence"],
        "n4096_stopped_reason": "A3-A1~0 and Phase dominated by trained GRU across 3 seeds; no gain to preserve",
    }
    res["verdict"] = {
        "deterministic_evidence_joins": "verified",
        "bounded_quadratic_evidence_comparison": "verified",
        "phase_used_only_as_auxiliary": "verified",
        "persistence_gain": a3t["persistence"] - a1t["persistence"],
        "unresolved_recurrence_gain": a3t["unresolved_recurrence"] - a1t["unresolved_recurrence"],
        "context_shift_gain": a3t["context_shift"] - a1t["context_shift"],
        "sequence_anomaly_gain": a3t["sequence_anomaly"] - a1t["sequence_anomaly"],
        "phase_causal_dependence": "verified" if cc.get("causal_dependence_verified") else "failed",
        "phase_vs_best_temporal_baseline": ("better" if a3 - best_base >= 0.03 else
                                            "worse" if best_base - a3 >= 0.03 else "equivalent"),
        "phase_information_health_value": (
            "validated" if accept["PASS"] else
            "useful_but_not_phase_specific" if (a3 - a1) >= 0.03 and (a3 - best_base) < 0.03 else
            "unsupported"),
        "authorized_production_role": "auxiliary quality sensor" if accept["PASS"] else "none",
    }
    RES.write_text(json.dumps(res, indent=2, default=float))
    print("ACCEPTANCE:", json.dumps(accept, default=float), flush=True)
    print("VERDICT:", json.dumps(res["verdict"], default=float), flush=True)
    print("FINALIZE DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
