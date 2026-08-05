#!/usr/bin/env python3
"""Zero-new-training T4 error-structure analysis. Recovers per-query T4 predictions by DETERMINISTIC
REPLAY of the frozen E1 (param hash verified byte-identical to the committed per-seed e1_param_sha256),
then classifies every T4 query per the frozen spec and applies the frozen conclusion rule. Does not
change any model, seed, gate, metric, or verdict."""
from __future__ import annotations

import json
import pathlib
import random

import torch

import temporal_task as T
import temporal_config as C
import temporal_train as TR
import t4_error_spec as SPEC

RES = pathlib.Path(__file__).resolve().parent / "results"


def _write(name, obj):
    p = RES / name
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(obj, indent=2)); tmp.replace(p)


def decode(kt):
    return {"ent": tuple(sorted(((kt[0] - T._E) // T.SYN, (kt[1] - T._E) // T.SYN))),
            "ev": (kt[2] - T._EV) // T.SYN, "step": (kt[3] - T._P) // T.SYN}


@torch.no_grad()
def at_step_control(model, ep, tgt_ent, tgt_index, records):
    """Within-episode control: pose an at-step (T3-style) query for the target entity at its latest step
    and check whether the frozen model retrieves the target record. Isolates 'is the record findable
    given the explicit step?' from 'can it infer latest?'. Deterministic (seeded)."""
    step = records[tgt_index]["step"]
    rng = random.Random(hash((tgt_ent, step, tgt_index)) & 0xFFFFFFFF)
    q = torch.tensor([T.render_query(rng, tgt_ent, "at_step", step=step)], dtype=torch.long)
    kt = torch.tensor([ep["key_tokens"]], dtype=torch.long)
    sc = model.scores(kt, q, C.TAU)[:, :len(ep["key_tokens"])]
    return int(sc.argmax(-1).item()) == tgt_index


def analyze_seed(model, seed):
    # identical episodes to run_seed's reserved cohort (build_eval_splits -> T4_latest)
    eps = T.build_eval_splits(T.identity_pools(C.POOL_SALT)["final"], C.EVAL_N_PER_SPLIT, seed_base=seed)["T4_latest"]
    kt = torch.tensor([e["key_tokens"] for e in eps], dtype=torch.long)
    qt = torch.tensor([e["query_tokens"] for e in eps], dtype=torch.long)
    with torch.no_grad():
        scores = model.scores(kt, qt, C.TAU)
    K = kt.size(1)
    key_scores = scores[:, :K]
    pred_all = scores.argmax(-1)
    rows = []
    for i, e in enumerate(eps):
        records = [decode(k) for k in e["key_tokens"]]
        ti = e["target_index"]
        tgt = records[ti]
        pred = int(pred_all[i].item())
        correct = (pred == ti)
        cs = float(key_scores[i, ti])
        rank = int((key_scores[i] > cs).sum().item()) + 1
        same_ent = [j for j, r in enumerate(records) if r["ent"] == tgt["ent"]]
        same_ent_steps = sorted(records[j]["step"] for j in same_ent)
        n_records = len(same_ent)
        temporal_dist = (same_ent_steps[-1] - same_ent_steps[-2]) if len(same_ent_steps) >= 2 else -1
        another_above = any(float(key_scores[i, j]) > cs for j in same_ent if j != ti)
        top2 = key_scores[i].topk(2).values
        margin = float(top2[0] - top2[1])

        if correct:
            cat = "RIGHT_ENTITY_RIGHT_LATEST_STEP"
        elif pred == K:
            cat = "NULL_OR_ABSTAIN"
        else:
            pr = records[pred]
            if pr["ent"] == tgt["ent"]:
                cat = "RIGHT_ENTITY_WRONG_OLDER_STEP" if pr["step"] < tgt["step"] else "INVALID_OR_OTHER"
            else:
                cat = "WRONG_ENTITY"
        control = at_step_control(model, e, tgt["ent"], ti, records) if not correct else None
        rows.append({"seed": seed, "category": cat, "correct": correct,
                     "pred_entity": None if pred == K else records[pred]["ent"], "correct_entity": tgt["ent"],
                     "pred_step": None if pred == K else records[pred]["step"], "correct_latest_step": tgt["step"],
                     "pred_status": None if pred == K else T.status_of(e["key_values"][pred]),
                     "correct_latest_status": T.status_of(e["key_values"][ti]),
                     "correct_rank": rank, "another_same_entity_ranked_above": bool(another_above),
                     "n_records_for_entity": n_records, "temporal_distance": temporal_dist,
                     "at_step_control_recovers_target": control, "top1_margin": margin})
    return rows


def main():
    committed = {s["seed"]: s["e1_param_sha256"] for s in json.loads((RES / "per_seed.json").read_text())["per_seed"]}
    train_eps = C.build_train_episodes()
    all_rows = []
    replay_ok = True
    hash_report = {}
    for seed in C.FINAL_SEEDS:
        m = TR.train_e1(train_eps, seed)
        h = TR.param_hash(m)
        match = (h == committed.get(seed))
        hash_report[seed] = {"replayed": h, "committed": committed.get(seed), "byte_identical": match}
        replay_ok = replay_ok and match
        if not match:
            continue
        all_rows += analyze_seed(m, seed)

    failures = [r for r in all_rows if not r["correct"]]
    fc = {}
    for r in failures:
        fc[r["category"]] = fc.get(r["category"], 0) + 1
    conclusion = SPEC.conclude(fc, replay_ok, len(failures))

    # aggregates
    def pct(cat):
        return (fc.get(cat, 0) / len(failures)) if failures else 0.0
    ranks = sorted(r["correct_rank"] for r in all_rows)
    import statistics
    per_seed = {}
    for s in C.FINAL_SEEDS:
        srows = [r for r in all_rows if r["seed"] == s]
        sf = [r for r in srows if not r["correct"]]
        per_seed[s] = {"total_T4": len(srows), "failures": len(sf),
                       "right_entity_wrong_older": sum(1 for r in sf if r["category"] == "RIGHT_ENTITY_WRONG_OLDER_STEP"),
                       "wrong_entity": sum(1 for r in sf if r["category"] == "WRONG_ENTITY"),
                       "null_abstain": sum(1 for r in sf if r["category"] == "NULL_OR_ABSTAIN"),
                       "invalid_other": sum(1 for r in sf if r["category"] == "INVALID_OR_OTHER")}
    # breakdown by events-per-entity and temporal distance (over failures)
    def breakdown(key):
        b = {}
        for r in failures:
            k = r[key]
            b.setdefault(k, {}).setdefault(r["category"], 0)
            b[k][r["category"]] = b[k].get(r["category"], 0) + 1
        return {str(k): v for k, v in sorted(b.items())}
    control_recovered = sum(1 for r in failures if r["at_step_control_recovers_target"])

    out = {
        "schema": "bindingslots_e1_temporal/t4_error_analysis/v1",
        "method": "deterministic replay (byte-identical verified) + committed episode records; zero new training",
        "replay_byte_identical": replay_ok, "param_hash_report": hash_report,
        "total_T4_queries": len(all_rows), "total_failures": len(failures),
        "failure_category_counts": fc,
        "pct_right_entity_wrong_older_step": pct("RIGHT_ENTITY_WRONG_OLDER_STEP"),
        "pct_wrong_entity": pct("WRONG_ENTITY"),
        "pct_null_abstain": pct("NULL_OR_ABSTAIN"),
        "pct_invalid_other": pct("INVALID_OR_OTHER"),
        "correct_latest_rank_mean": statistics.mean(ranks) if ranks else None,
        "correct_latest_rank_median": statistics.median(ranks) if ranks else None,
        "fraction_entity_ok_latest_misselected": (fc.get("RIGHT_ENTITY_WRONG_OLDER_STEP", 0) / len(failures)) if failures else 0.0,
        "fraction_entity_retrieval_failed": (fc.get("WRONG_ENTITY", 0) / len(failures)) if failures else 0.0,
        "at_step_control_recovers_target_among_failures": (control_recovered / len(failures)) if failures else 0.0,
        "another_same_entity_record_outranked_target_frac": (sum(1 for r in failures if r["another_same_entity_ranked_above"]) / len(failures)) if failures else 0.0,
        "breakdown_by_events_per_entity": breakdown("n_records_for_entity"),
        "breakdown_by_temporal_distance": breakdown("temporal_distance"),
        "per_seed": per_seed,
        "conclusion": conclusion, "co_emitted": SPEC.ALWAYS,
        "recommendation": SPEC.RECOMMENDATION.get(conclusion),
        "t5_note": "T5 predecessor/successor performance is explicitly OUTSIDE this conclusion",
        "existing_verdict_unchanged": "E1_TEMPORAL_TRANSFER_PARTIAL",
    }
    _write("t4_error_analysis.json", out)
    print(f"replay_byte_identical={replay_ok} failures={len(failures)}", flush=True)
    print(f"  right_entity/wrong_older={pct('RIGHT_ENTITY_WRONG_OLDER_STEP'):.3f} "
          f"wrong_entity={pct('WRONG_ENTITY'):.3f} null={pct('NULL_OR_ABSTAIN'):.3f} "
          f"invalid={pct('INVALID_OR_OTHER'):.3f}", flush=True)
    print(f"  at_step_control_recovers_target_among_failures={out['at_step_control_recovers_target_among_failures']:.3f}", flush=True)
    print(f"  CONCLUSION: {conclusion}", flush=True)


if __name__ == "__main__":
    main()
