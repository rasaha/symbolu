"""
run_oracle_stageA.py — Stage A validity, oracle-addressed memory.

Trains A (no slots) and C (oracle slots, local retention) across seeds at candidate
pressure configs, reads capacity metrics straight off the OracleSlotState, and
checks the validity gate. Oracle addressing isolates capacity: because a query for an
evicted identity returns nothing, acc|evicted ≈ chance is a structural proof of
bounded-memory dependence (no query-token shortcut is possible). Phase (Stage B) is
gated on a PASS here.
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
RAW = HERE / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

CONFIGS = [dict(n_live=12, M=8), dict(n_live=16, M=8), dict(n_live=24, M=8)]
SEEDS = (0, 1, 2)
CHANCE = 1.0 / 50  # value vocabulary = 50 tokens


def gate(ev: dict) -> dict:
    early = ev["survival_by_target_position"]["early"]
    conds = {
        "capacity_saturation (occ>=M)": ev["mean_occupancy"] >= ev["_M"] - 0.05,
        "evictions>1": ev["evictions"] > 1.0,
        "early_target_eviction>0.20": (early is not None and (1 - early) > 0.20),
        "target_survival_in_0.30_0.80": 0.30 <= ev["target_survival_rate"] <= 0.80,
        "C_acc_in_0.30_0.70": 0.30 <= ev["answer_acc"] <= 0.70,
        "acc|evicted~chance (<0.10)": ev["acc_given_evicted"] < 0.10,
        "acc|survived_high (>0.60)": ev["acc_given_survived"] > 0.60,
        "acc_tracks_survival (|acc-surv|<0.20)": abs(ev["answer_acc"] - ev["target_survival_rate"]) < 0.20,
    }
    return {"conditions": conds, "PASS": all(conds.values())}


def run(configs=None, seeds=SEEDS):
    configs = configs or CONFIGS
    vocab = build_vocab()
    def gen_fn(n_live, n): return D.generate(vocab, "train", 0, n, n_live, 8)
    summary = {"chance": CHANCE, "configs": []}
    for c in configs:
        cell = {"config": c, "pressure": c["n_live"] / c["M"], "seeds": {}}
        for seed in seeds:
            # A baseline
            cfgA = OCfg(vocab_size=vocab.size, num_slots=c["M"])
            mA = build_oracle(cfgA, "A", seed)
            def gfn(nl, n, s=seed): return D.generate(vocab, "train", s, n, nl, c["M"])
            train_oracle_curriculum(mA, gfn, vocab.pad_id, [(c["n_live"], 400)],
                                    OTCfg(lambda_write=0.5, seed=seed))
            teA = D.generate(vocab, "test", 1000 + seed, 150, c["n_live"], c["M"])
            accA = evaluate_oracle(mA, teA, vocab.pad_id)["answer_acc"]
            # C: curriculum up to pressure
            cfgC = OCfg(vocab_size=vocab.size, num_slots=c["M"])
            mC = build_oracle(cfgC, "C", seed)
            stages = [(2, 150), (4, 150), (min(8, c["n_live"]), 200), (c["n_live"], 250)]
            train_oracle_curriculum(mC, gfn, vocab.pad_id, stages, OTCfg(lambda_write=0.5, seed=seed))
            te = D.generate(vocab, "test", 1000 + seed, 200, c["n_live"], c["M"])
            ev = evaluate_oracle(mC, te, vocab.pad_id); ev["_M"] = c["M"]
            g = gate(ev)
            rec = {"A_acc": accA, "C_eval": ev, "gate": g}
            (RAW / f"oracle_stageA_L{c['n_live']}_M{c['M']}_s{seed}.json").write_text(
                json.dumps(rec, indent=2, default=float))
            cell["seeds"][seed] = rec
            print(f"[L{c['n_live']} M{c['M']} s{seed}] A={accA:.2f} C={ev['answer_acc']:.3f} "
                  f"surv={ev['target_survival_rate']:.2f} acc|surv={ev['acc_given_survived']:.2f} "
                  f"acc|evict={ev['acc_given_evicted']:.3f} PASS={g['PASS']}", flush=True)
        def agg(f):
            xs = [f(cell["seeds"][s]) for s in seeds if s in cell["seeds"]]
            return {"mean": st.mean(xs), "std": st.pstdev(xs) if len(xs) > 1 else 0.0, "raw": xs}
        cell["agg"] = {
            "C_acc": agg(lambda r: r["C_eval"]["answer_acc"]),
            "target_survival": agg(lambda r: r["C_eval"]["target_survival_rate"]),
            "acc_given_evicted": agg(lambda r: r["C_eval"]["acc_given_evicted"]),
            "acc_given_survived": agg(lambda r: r["C_eval"]["acc_given_survived"]),
            "evictions": agg(lambda r: r["C_eval"]["evictions"]),
        }
        cell["PASS_all_seeds"] = all(cell["seeds"][s]["gate"]["PASS"] for s in seeds if s in cell["seeds"])
        summary["configs"].append(cell)
    (HERE / "results" / "oracle_stageA_summary.json").write_text(json.dumps(summary, indent=2, default=float))
    print("wrote results/oracle_stageA_summary.json")
    return summary


if __name__ == "__main__":
    run()
