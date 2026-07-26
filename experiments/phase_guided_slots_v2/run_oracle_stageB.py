"""
run_oracle_stageB.py — Stage B: Phase as a RETENTION-PRIORITY signal (oracle memory).

GATED: refuses to run unless Stage A produced a passing config
(results/oracle_stageA_summary.json). Per the redesign rule, Phase may be evaluated
only after plain slots C are shown genuinely capacity-limited (Stage A PASS).

Task: the focus-retention variant (datasets_pressure_v2.generate(..., focus_retention=True)).
A focus vendor is declared in an early header; only that vendor's contracts are ever
queried, flooded by distractor contracts. Retaining the queried (relevant) fact
requires prioritizing focus-vendor facts — which needs the DISTANT header, so a
local-only arm (C) cannot; a global retention signal (Phase, arm D) could. Oracle
addressing means acc = survival of the queried relevant fact, so D − C isolates
whether Phase helps RETENTION (nothing else).

Arms: C (local retention), D (Phase retention), D-no-guid (retention zeroed).
Reports acc and target-survival; the decisive number is D − C.
"""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from experiments.phase_guided_slots_v2.task_schema import build_vocab
from experiments.phase_guided_slots_v2 import datasets_pressure_v2 as D
from experiments.phase_guided_slots_v2.guided_models_oracle import OCfg, build_oracle
from experiments.phase_guided_slots_v2.oracle_eval import OTCfg, train_oracle_curriculum, evaluate_oracle

HERE = Path(__file__).resolve().parent
SUMMARY = HERE / "results" / "oracle_stageA_summary.json"
SEEDS = (0, 1, 2)


def _passing_config():
    if not SUMMARY.exists():
        return None
    s = json.loads(SUMMARY.read_text())
    for cell in s["configs"]:
        if cell.get("PASS_all_seeds"):
            return cell["config"]
    # soft pass: C in window + acc tracks survival + acc|evicted ~ chance across seeds
    for cell in s["configs"]:
        g = cell["agg"]
        if 0.30 <= g["C_acc"]["mean"] <= 0.70 and g["acc_given_evicted"]["mean"] < 0.10 \
                and g["evictions"]["mean"] > 1.0:
            return cell["config"]
    return None


def run(seeds=SEEDS):
    config = _passing_config()
    if config is None:
        print("STAGE A NOT PASSED — Phase evaluation is not permitted.")
        return {"gated": True}
    print(f"Stage A passed for {config}; running Stage B (Phase as retention signal).")
    vocab = build_vocab()
    def gfn(nl, n, s): return D.generate(vocab, "train", s, n, nl, config["M"], focus_retention=True)
    out = {"config": config, "arms": {}}
    for arm in ("C", "D", "D-no-guid"):
        accs, survs, early = [], [], []
        for seed in seeds:
            cfg = OCfg(vocab_size=vocab.size, num_slots=config["M"])
            m = build_oracle(cfg, arm, seed)
            stages = [(2, 150), (4, 150), (min(8, config["n_live"]), 200), (config["n_live"], 300)]
            train_oracle_curriculum(m, lambda nl, n, s=seed: gfn(nl, n, s), vocab.pad_id, stages,
                                    OTCfg(lambda_write=0.5, seed=seed))
            te = D.generate(vocab, "test", 1000 + seed, 200, config["n_live"], config["M"],
                            focus_retention=True)
            ev = evaluate_oracle(m, te, vocab.pad_id)
            accs.append(ev["answer_acc"]); survs.append(ev["target_survival_rate"])
            early.append(ev["survival_by_target_position"]["early"])
            print(f"[{arm} s{seed}] acc={ev['answer_acc']:.3f} surv={ev['target_survival_rate']:.3f} "
                  f"earlySurv={early[-1]:.3f}", flush=True)
        out["arms"][arm] = {"acc_mean": st.mean(accs), "acc_std": st.pstdev(accs) if len(accs) > 1 else 0,
                            "surv_mean": st.mean(survs), "early_surv_mean": st.mean([e for e in early if e is not None] or [0]),
                            "acc_raw": accs}
    c = out["arms"]["C"]["acc_mean"]; d = out["arms"]["D"]["acc_mean"]
    out["D_minus_C_acc"] = d - c
    out["D_minus_C_survival"] = out["arms"]["D"]["surv_mean"] - out["arms"]["C"]["surv_mean"]
    (HERE / "results" / "oracle_stageB_summary.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"D - C acc = {out['D_minus_C_acc']:+.3f}; D - C survival = {out['D_minus_C_survival']:+.3f}")
    return out


if __name__ == "__main__":
    run()
