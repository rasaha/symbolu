#!/usr/bin/env python3
"""Zero-training counterfactual diagnostics D0-D5 for the T4 latest-state shortfall. Frozen E1 replay
(byte-identical), committed T4 episodes, oracle-only counterfactual selections. No optimizer step, no
weight change, no prior-evidence change. Applies the frozen attribution rules in cf_spec."""
from __future__ import annotations

import json
import pathlib

import torch

import temporal_task as T
import temporal_config as C
import temporal_train as TR
import cf_spec as SPEC

RES = pathlib.Path(__file__).resolve().parent / "results"


def _write(name, obj):
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def decode(kt):
    return {"ent": tuple(sorted(((kt[0] - T._E) // T.SYN, (kt[1] - T._E) // T.SYN))),
            "step": (kt[3] - T._P) // T.SYN}


def d0_category(pred, ti, records, K):
    if pred == ti:
        return "CORRECT_LATEST"
    if pred == K:
        return "NULL_OR_ABSTAIN"
    if records[pred]["ent"] == records[ti]["ent"]:
        return "RIGHT_ENTITY_WRONG_OLDER"
    return "WRONG_ENTITY"


def outcome(pred, ti, records, K):
    if pred == ti:
        return "correct_latest"
    if pred == K:
        return "null"
    if records[pred]["ent"] == records[ti]["ent"]:
        return "right_entity_older"
    return "wrong_entity"


@torch.no_grad()
def run_seed(model, seed):
    eps = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], C.EVAL_N_PER_SPLIT, seed_base=seed)["T4_latest"]
    kt = torch.tensor([e["key_tokens"] for e in eps], dtype=torch.long)
    qt = torch.tensor([e["query_tokens"] for e in eps], dtype=torch.long)
    scores = model.scores(kt, qt, C.TAU)
    K = kt.size(1)
    rows = []
    for i, e in enumerate(eps):
        recs = [decode(k) for k in e["key_tokens"]]
        ti = e["target_index"]
        tgt_status = T.status_of(e["key_values"][ti])
        sc = scores[i]
        ent_idx = [j for j, r in enumerate(recs) if r["ent"] == recs[ti]["ent"]]
        # arm selections
        d0 = int(sc.argmax().item())
        d1 = int(sc[:K].argmax().item())
        # D2: correct-entity records + null
        cand2 = ent_idx + [K]
        d2 = cand2[int(torch.tensor([sc[j] for j in cand2]).argmax().item())]
        # D3: correct-entity records only
        d3 = ent_idx[int(torch.tensor([sc[j] for j in ent_idx]).argmax().item())]
        d4 = ti                                  # oracle latest record
        d5 = max(ent_idx, key=lambda j: recs[j]["step"])   # metadata max position (== ti by construction)

        def val_ok(pred):
            return pred != K and T.status_of(e["key_values"][pred]) == tgt_status
        rank = int((sc[:K] > sc[ti]).sum().item()) + 1
        rows.append({"seed": seed, "ti": ti,
                     "d0": d0, "d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5,
                     "d0_cat": d0_category(d0, ti, recs, K),
                     "d0_correct": d0 == ti, "d1_correct": d1 == ti, "d2_correct": d2 == ti,
                     "d3_correct": d3 == ti, "d4_value_ok": val_ok(d4), "d5_correct": d5 == ti,
                     "d1_out": outcome(d1, ti, recs, K), "d3_out": outcome(d3, ti, recs, K),
                     "d0_value_ok": val_ok(d0), "d1_value_ok": val_ok(d1), "d3_value_ok": val_ok(d3),
                     "d5_value_ok": val_ok(d5),
                     "correct_latest_rank": rank, "n_ent_records": len(ent_idx),
                     "d0_entity_ok": d0 != K and recs[d0]["ent"] == recs[ti]["ent"]})
    return rows


def main():
    committed = {s["seed"]: s["e1_param_sha256"] for s in json.loads((RES / "per_seed.json").read_text())["per_seed"]}
    train_eps = C.build_train_episodes()
    all_rows = []
    byte_identical = True
    hash_report = {}
    for seed in C.FINAL_SEEDS:
        m = TR.train_e1(train_eps, seed)
        h = TR.param_hash(m)
        ok = (h == committed.get(seed))
        hash_report[seed] = {"replayed": h, "committed": committed.get(seed), "byte_identical": ok}
        byte_identical = byte_identical and ok
        if ok:
            all_rows += run_seed(m, seed)

    n = len(all_rows)
    fails = [r for r in all_rows if not r["d0_correct"]]
    F = len(fails)
    # D0 byte-identical addressing check vs committed T4 (per-seed addressing_top1)
    committed_T4 = {s["seed"]: s["metrics"]["T4"] for s in json.loads((RES / "per_seed.json").read_text())["per_seed"]}
    d0_addr_by_seed = {}
    for seed in C.FINAL_SEEDS:
        srows = [r for r in all_rows if r["seed"] == seed]
        # addressing (null-excluded) = D1 correct rate (argmax over keys)
        d0_addr_by_seed[seed] = sum(1 for r in srows if r["d1_correct"]) / len(srows) if srows else None
    d0_reproduces = all(abs(d0_addr_by_seed[s] - committed_T4[s]) < 1e-9 for s in C.FINAL_SEEDS) if byte_identical else False

    def rec(arm):
        return (sum(1 for r in fails if r[f"{arm}_correct"]) / F) if F else 0.0
    d1_rec, d2_rec, d3_rec = rec("d1"), rec("d2"), rec("d3")
    d4_fail_rate = sum(1 for r in all_rows if not r["d4_value_ok"]) / n if n else 0.0
    within_entity_latest_d3 = sum(1 for r in all_rows if r["d3_correct"]) / n if n else 0.0
    abstention_component = d1_rec
    entity_component = max(0.0, d3_rec - d1_rec)
    latest_component = max(0.0, 1.0 - d3_rec)
    # entity recovered from wrong-entity majority
    entity_recovered = [r for r in fails if r["d3_correct"] and not r["d1_correct"]]
    er_from_wrong = sum(1 for r in entity_recovered
                        if r["d0_cat"] == "WRONG_ENTITY" or (r["d0_cat"] == "NULL_OR_ABSTAIN" and r["d1_out"] == "wrong_entity"))
    entity_wrongentity_majority = bool(entity_recovered) and (er_from_wrong > len(entity_recovered) / 2)
    residual = [r for r in fails if not r["d3_correct"]]
    latest_older_majority = bool(residual) and (sum(1 for r in residual if r["d3_out"] == "right_entity_older") > len(residual) / 2)

    scalars = {"byte_identical": byte_identical and d0_reproduces, "oracle_valid": True,
               "d1_rec": d1_rec, "d2_rec": d2_rec, "d3_rec": d3_rec, "d4_fail_rate": d4_fail_rate,
               "abstention_component": abstention_component, "entity_component": entity_component,
               "latest_component": latest_component, "within_entity_latest_d3": within_entity_latest_d3,
               "entity_recovered_from_wrongentity_majority": entity_wrongentity_majority,
               "latest_older_majority_in_residual": latest_older_majority}
    conclusion, value_secondary = SPEC.conclude(scalars)

    # per-arm aggregate
    def agg(arm):
        return {"correct_latest_rate": sum(1 for r in all_rows if r[f"{arm}_correct"]) / n,
                "value_rate": sum(1 for r in all_rows if r[f"{arm}_value_ok"]) / n,
                "null_rate": sum(1 for r in all_rows if r[arm] == T.KEYS_PER_EPISODE) / n,
                "recovery_of_d0_failures": rec(arm)}
    arms = {a: agg(a) for a in ("d0", "d1", "d2", "d3")}
    arms["d4"] = {"value_rate": 1 - d4_fail_rate, "correct_latest_rate": 1.0, "recovery_of_d0_failures": rec_d4(fails)}
    arms["d5"] = {"correct_latest_rate": sum(1 for r in all_rows if r["d5_correct"]) / n,
                  "value_rate": sum(1 for r in all_rows if r["d5_value_ok"]) / n,
                  "recovery_of_d0_failures": sum(1 for r in fails if r["d5_correct"]) / F if F else 0.0}

    # transition table: D0 failure category -> outcome under D1 and D3
    def transitions(arm_out):
        tab = {}
        for r in fails:
            tab.setdefault(r["d0_cat"], {}).setdefault(r[arm_out], 0)
            tab[r["d0_cat"]][r[arm_out]] += 1
        return tab

    out = {"schema": "bindingslots_e1_temporal/t4_counterfactual/v1",
           "method": "zero-training frozen-E1 replay (byte-identical) + oracle counterfactual selections",
           "byte_identical_param_hashes": byte_identical, "param_hash_report": hash_report,
           "d0_reproduces_committed_T4_addressing": d0_reproduces,
           "n_T4_queries": n, "d0_failures": F,
           "arms": arms,
           "d1_recovery": d1_rec, "d2_recovery": d2_rec, "d3_recovery": d3_rec,
           "d4_value_fail_rate": d4_fail_rate, "within_entity_latest_d3": within_entity_latest_d3,
           "components_of_d0_failures": {"abstention": abstention_component, "entity": entity_component, "latest_ranking": latest_component},
           "transitions_D0_to_D1": transitions("d1_out"),
           "transitions_D0_to_D3": transitions("d3_out"),
           "attribution_scalars": scalars,
           "conclusion": conclusion, "value_path_secondary_invariant": value_secondary,
           "recommendation": SPEC.RECOMMENDATION[conclusion],
           "preserved": SPEC.PRESERVE,
           "t5_note": "T5 predecessor/successor remains OUTSIDE this conclusion and recommendation"}
    _write("t4_counterfactual.json", out)
    print(f"byte_identical={scalars['byte_identical']} F={F} d1_rec={d1_rec:.3f} d2_rec={d2_rec:.3f} d3_rec={d3_rec:.3f} d4_fail={d4_fail_rate:.3f}", flush=True)
    print(f"components abstention={abstention_component:.3f} entity={entity_component:.3f} latest={latest_component:.3f}", flush=True)
    print(f"CONCLUSION: {conclusion} | value_path_secondary={value_secondary}", flush=True)


def rec_d4(fails):
    return sum(1 for r in fails if r["d4_value_ok"]) / len(fails) if fails else 0.0


if __name__ == "__main__":
    main()
