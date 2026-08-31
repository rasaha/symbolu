#!/usr/bin/env python3
"""Independent leakage / shortcut suite for the temporal transfer task (torch-free)."""
from __future__ import annotations

import pathlib

import temporal_task as T


def _kset(kt): return {t for t in kt if t not in (T.PAD, T.SEP)}
def _qset(qt): return {t for t in qt if t != T.PAD}


def check_no_answer_in_key(eps):
    bad = 0
    for e in eps:
        for kt in e["key_tokens"]:
            if any(T._ST <= t < T._ST + T.STATUS_VALUES for t in kt):
                bad += 1
    return {"pass": bad == 0, "keys_with_status_token": bad}


def check_no_status_in_query(eps):
    bad = sum(1 for e in eps if any(T._ST <= t < T._ST + T.STATUS_VALUES for t in e["query_tokens"]))
    return {"pass": bad == 0, "queries_with_status_token": bad}


def check_no_exact_overlap(eps):
    """Correct key and query share no surface token (entity/step use different synonyms; T4 has no step)."""
    worst = 0
    for e in eps:
        if e["target_index"] < 0:
            continue
        worst = max(worst, len(_kset(e["key_tokens"][e["target_index"]]) & _qset(e["query_tokens"])))
    return {"pass": worst == 0, "max_shared_tokens": worst}


def check_pools_disjoint(salt="e1_temporal_pool_v1"):
    p = T.identity_pools(salt)
    tr, dv, fn = set(p["train"]), set(p["dev"]), set(p["final"])
    return {"pass": not (tr & dv) and not (tr & fn) and not (dv & fn),
            "train": len(tr), "dev": len(dv), "final": len(fn)}


def check_eval_ids_unseen(eval_eps, salt="e1_temporal_pool_v1"):
    train = set(T.identity_pools(salt)["train"])
    leaked = 0
    for e in eval_eps:
        if e["target_index"] < 0:
            continue
        kt = e["key_tokens"][e["target_index"]]
        a = (kt[0] - T._E) // T.SYN
        b = (kt[1] - T._E) // T.SYN
        if tuple(sorted((a, b))) in train:
            leaked += 1
    return {"pass": leaked == 0, "leaked_targets": leaked}


def check_lexical_overlap_uninformative(eps):
    correct = n = 0
    for e in eps:
        if e["target_index"] < 0:
            continue
        qs = _qset(e["query_tokens"])
        sc = [len(qs & _kset(kt)) for kt in e["key_tokens"]]
        pred = max(range(len(sc)), key=lambda i: (sc[i], -i))
        correct += int(pred == e["target_index"]); n += 1
    acc = correct / n if n else 0.0
    return {"pass": acc <= 2.0 / T.KEYS_PER_EPISODE, "lexical_overlap_accuracy": acc, "chance": 1.0 / T.KEYS_PER_EPISODE}


def check_latest_heuristic_uninformative(latest_eps):
    """A 'always pick the globally-max-step record' heuristic must be near chance on T4 — proving
    latest-state needs entity+predicate, not just 'pick the newest record'."""
    correct = n = 0
    for e in latest_eps:
        if e["target_index"] < 0:
            continue
        # decode step token (syn 0) from each key's position slot (index 3)
        steps = [(kt[3] - T._P) // T.SYN for kt in e["key_tokens"]]
        pred = max(range(len(steps)), key=lambda i: (steps[i], -i))
        correct += int(pred == e["target_index"]); n += 1
    acc = correct / n if n else 0.0
    return {"pass": acc <= 3.0 / 9, "global_latest_heuristic_accuracy": acc}


def check_no_table_import():
    here = pathlib.Path(__file__).resolve().parent
    e1 = here.parents[0] / "bindingslots_e1"
    banned = ("ephemeral_table", "EphemeralTable", "v100_table", "external_fallback")
    hit = []
    for p in [here / "temporal_task.py", here / "temporal_eval.py", here / "temporal_run.py",
              here / "temporal_train.py", e1 / "models.py"]:
        if p.exists():
            s = p.read_text()
            hit += [f"{p.name}:{b}" for b in banned if b in s]
    return {"pass": not hit, "banned_hits": hit}


def run_all(eval_splits):
    all_eps = [e for v in eval_splits.values() for e in v]
    valid = [e for e in all_eps if e["target_index"] >= 0]
    r = {
        "no_answer_in_key": check_no_answer_in_key(all_eps),
        "no_status_in_query": check_no_status_in_query(all_eps),
        "no_exact_overlap": check_no_exact_overlap(valid),
        "pools_disjoint": check_pools_disjoint(),
        "eval_ids_unseen": check_eval_ids_unseen(all_eps),
        "lexical_overlap_uninformative": check_lexical_overlap_uninformative(valid),
        "latest_heuristic_uninformative": check_latest_heuristic_uninformative(eval_splits["T4_latest"]),
        "no_table_import": check_no_table_import(),
    }
    r["all_pass"] = all(v["pass"] for v in r.values() if isinstance(v, dict) and "pass" in v)
    return r
