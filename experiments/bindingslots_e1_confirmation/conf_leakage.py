#!/usr/bin/env python3
"""Independent leakage / shortcut suite for the confirmation task (torch-free)."""
from __future__ import annotations

import pathlib

import conf_task as T


def _kset(kt):
    return {t for t in kt if t not in (T.PAD, T.SEP)}


def _qset(qt):
    return {t for t in qt if t != T.PAD}


def check_no_exact_overlap(eps):
    worst = 0
    for e in eps:
        if e["target_index"] < 0:
            continue
        worst = max(worst, len(_kset(e["key_tokens"][e["target_index"]]) & _qset(e["query_tokens"])))
    return {"pass": worst == 0, "max_shared_tokens": worst}


def check_pools_disjoint(salt=T.identity_pools.__defaults__[0]):
    p = T.identity_pools(salt)
    tr, dv, fn = set(p["train"]), set(p["dev"]), set(p["final"])
    return {"pass": not (tr & dv) and not (tr & fn) and not (dv & fn),
            "train": len(tr), "dev": len(dv), "final": len(fn)}


def check_eval_ids_unseen(eval_eps, salt="e1_conf_pool_v1"):
    train = set(T.identity_pools(salt)["train"])
    leaked = 0
    for e in eval_eps:
        if e["target_index"] < 0:
            continue
        kt = e["key_tokens"][e["target_index"]]
        a = (kt[0] - T._E_BASE) // T.SYN
        b = (kt[1] - T._E_BASE) // T.SYN
        if tuple(sorted((a, b))) in train:
            leaked += 1
    return {"pass": leaked == 0, "leaked_targets": leaked}


def check_no_answer_in_key(eps):
    bad = 0
    for e in eps:
        for kt in e["key_tokens"]:
            if any(T._V_BASE <= t < T._V_BASE + T.N_VALUES for t in kt):
                bad += 1
    return {"pass": bad == 0, "keys_with_value_token": bad}


def check_no_opaque_identifier():
    """The task uses no shared opaque per-identity token: identity is encoded only via composed
    entity-primitive surface tokens (with synonyms), never a unique per-identity id. Vocab ranges are
    entity/attr/value/filler only."""
    ok = (T.VOCAB == T._F_BASE + T.N_FILLER) and T._E_BASE == 2
    return {"pass": bool(ok), "vocab": T.VOCAB, "note": "no per-identity opaque id token exists"}


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
    return {"pass": acc <= 2.0 / T.KEYS_PER_EPISODE, "lexical_overlap_accuracy": acc,
            "chance": 1.0 / T.KEYS_PER_EPISODE}


def check_no_table_import():
    here = pathlib.Path(__file__).resolve().parent
    e1 = here.parents[0] / "bindingslots_e1"
    banned = ("ephemeral_table", "EphemeralTable", "v100_table", "external_fallback")
    hit = []
    for p in [here / "conf_task.py", here / "conf_eval.py", here / "conf_run.py", e1 / "models.py"]:
        if p.exists():
            s = p.read_text()
            hit += [f"{p.name}:{b}" for b in banned if b in s]
    return {"pass": not hit, "banned_hits": hit}


def run_all(eval_splits):
    all_eps = [e for v in eval_splits.values() for e in v]
    valid = [e for e in all_eps if e["target_index"] >= 0]
    r = {
        "no_exact_overlap": check_no_exact_overlap(valid),
        "pools_disjoint": check_pools_disjoint(),
        "eval_ids_unseen": check_eval_ids_unseen(all_eps),
        "no_answer_in_key": check_no_answer_in_key(all_eps),
        "no_opaque_identifier": check_no_opaque_identifier(),
        "lexical_overlap_uninformative": check_lexical_overlap_uninformative(valid),
        "no_table_import": check_no_table_import(),
    }
    r["all_pass"] = all(v["pass"] for v in r.values() if isinstance(v, dict) and "pass" in v)
    return r
