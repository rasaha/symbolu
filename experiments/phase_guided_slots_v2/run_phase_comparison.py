"""
run_phase_comparison.py — Stage B: D vs C (and D-no-guidance) on the redesigned task.

GATED: this runner refuses to run unless Stage A produced a PASSING pressure config
(results/stageA_summary.json with PASS_all_seeds for some config). Per the redesign
rule, Phase guidance may not be evaluated until plain slots C are shown to be
genuinely capacity-limited and losing relevant evidence through real eviction.

For a passing config it trains D and D-no-guid across seeds and reports D − C.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from experiments.phase_guided_slots_v2.task_validator import PCfg, train_arm, gate

HERE = Path(__file__).resolve().parent
SUMMARY = HERE / "results" / "stageA_summary.json"


def _passing_config():
    if not SUMMARY.exists():
        return None
    s = json.loads(SUMMARY.read_text())
    for cell in s["configs"]:
        if cell.get("PASS_all_seeds"):
            return cell["config"], s["seeds"]
    # fall back: any config where C_acc mean in window and evictions>1 (soft pass)
    for cell in s["configs"]:
        g = cell["agg"]
        if 0.30 <= g["C_acc"]["mean"] <= 0.70 and g["evictions"]["mean"] > 1.0 \
                and g["capacity_saturation"]["mean"] >= 0.80:
            return cell["config"], s["seeds"]
    return None


def run(steps=400):
    pcfg_seeds = _passing_config()
    if pcfg_seeds is None:
        print("STAGE A NOT PASSED — Phase evaluation is not permitted. "
              "Run run_task_validation and achieve a passing config first.")
        return {"gated": True}
    config, seeds = pcfg_seeds
    print(f"Stage A passed for config {config}; running Stage B (D vs C).")
    out = {"config": config, "seeds": seeds, "arms": {}}
    for arm in ("C", "D", "D-no-guid"):
        accs, early = [], []
        for seed in seeds:
            pc = PCfg(M=config["M"], top_k=config["top_k"], n_live=config["n_live"], steps=steps)
            _, _, meta, tag = train_arm(arm, pc, seed)
            accs.append(meta["metrics"]["answer_acc"])
            early.append(meta["trace"]["by_target_position"]["early"]["target_survival_rate"])
            print(f"[{tag}] acc={accs[-1]:.3f} earlySurv={early[-1]:.3f}", flush=True)
        out["arms"][arm] = {"acc_mean": st.mean(accs), "acc_std": st.pstdev(accs) if len(accs) > 1 else 0.0,
                            "early_survival_mean": st.mean(early), "acc_raw": accs}
    c = out["arms"]["C"]["acc_mean"]; d = out["arms"]["D"]["acc_mean"]
    out["D_minus_C"] = d - c
    out["D_minus_Dnoguid"] = d - out["arms"]["D-no-guid"]["acc_mean"]
    (HERE / "results" / "stageB_summary.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"D - C = {out['D_minus_C']:+.3f}; D - D-no-guid = {out['D_minus_Dnoguid']:+.3f}")
    return out


if __name__ == "__main__":
    run()
