#!/usr/bin/env python3
"""Mechanical configuration selection under the committed DEV_CALIBRATION_PLAN. Trains each bounded
candidate on dev seed 500, evaluates dev-pool splits, applies the frozen selection rule, and asserts the
winner equals config.SELECTED. Non-reserved only."""
from __future__ import annotations

import json
import pathlib

import task as T
import config as C
import engine as E

RES = pathlib.Path(__file__).resolve().parent / "results"
GEN_SPLITS = ["G1_unseen_identity", "G2_paraphrase", "G3_hard_names",
              "G4_same_entity_diff_attr", "G5_recombined", "G7_stable"]


def _write(name, obj):
    RES.mkdir(parents=True, exist_ok=True)
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def score_candidate(name, steps, tau, nmf, dev_splits):
    train = T.build_split(T.identity_pools(C.POOL_SALT)["train"], C.TRAIN_EPISODES,
                          seed=C.TRAIN_SEED_FOR_EPISODES, no_match_frac=nmf)
    e1, _ = E.train_e1(train, steps, C.BATCH, C.LR, tau, seed=C.DEV_SEED_BASE)
    ev = {s: E.eval_e1(e1, dev_splits[s], tau) for s in set(GEN_SPLITS + ["G6_no_match"])}
    mean_addr = sum(ev[s]["addressing_top1"] for s in GEN_SPLITS) / len(GEN_SPLITS)
    nmfa = ev["G6_no_match"]["false_accept_rate"]
    score = mean_addr - max(0.0, nmfa - 0.30)
    return {"candidate": name, "steps": steps, "tau": tau, "nmf": nmf,
            "mean_addressing": mean_addr, "nomatch_false_accept": nmfa, "score": score}


def main():
    dev_splits = C.build_dev_eval(C.DEV_SEED_BASE)
    rows = [score_candidate(n, *cfg, dev_splits) for n, cfg in C.CANDIDATES.items()]
    # selection rule: argmax score; tie-break lower nomatch_false_accept, then fewer steps
    rows_sorted = sorted(rows, key=lambda r: (-r["score"], r["nomatch_false_accept"], r["steps"]))
    winner = rows_sorted[0]["candidate"]
    ok = (winner == C.SELECTED)
    out = {"schema": "bindingslots_e1/selection/v1", "dev_seed": C.DEV_SEED_BASE,
           "candidates": rows, "ranked": [r["candidate"] for r in rows_sorted],
           "mechanical_winner": winner, "frozen_SELECTED": C.SELECTED,
           "winner_matches_frozen": ok}
    _write("selection_result.json", out)
    for r in rows_sorted:
        print(f"  {r['candidate']} steps={r['steps']} tau={r['tau']} nmf={r['nmf']} "
              f"mean_addr={r['mean_addressing']:.3f} nm_fa={r['nomatch_false_accept']:.3f} score={r['score']:.3f}", flush=True)
    print(f"mechanical winner={winner} | frozen SELECTED={C.SELECTED} | match={ok}", flush=True)
    assert ok, f"selection rule winner {winner} != frozen SELECTED {C.SELECTED}"


if __name__ == "__main__":
    main()
