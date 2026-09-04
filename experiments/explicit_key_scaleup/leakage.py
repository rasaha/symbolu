"""Mechanical leakage / shortcut suite for E1-S (torch-free; runs on constructed data, no model).

Adapts experiments/bindingslots_e1/leakage.py to the enterprise key shape: paraphrased type/relation tokens
must never overlap verbatim; subject-id tokens DO appear verbatim by design (draft §4) and are a reserved
token class (F16); pools are disjoint and marker-free (F14); held-out (ST, REL) pairs never enter training.
Any failure => SHORTCUT_OR_LEAKAGE_DETECTED regardless of accuracy.
"""
from __future__ import annotations

from . import config as C
from . import keyspace as KS
from .shortcuts import lexical_overlap_prediction


def _nonid(tokens):
    return {t for t in tokens if t not in (KS.PAD, KS.SEP) and KS.token_class(t) != "id"}


def check_no_exact_overlap_on_paraphrased_tokens(eps):
    worst = 0
    for e in eps:
        if e["target_index"] < 0:
            continue
        worst = max(worst, len(_nonid(e["key_tokens"][e["target_index"]]) & _nonid(e["query_tokens"])))
    return {"pass": worst == 0, "max_shared_nonid_tokens": worst}


def check_id_token_class_reserved(eps):
    """Id tokens appear only as ids (F16): no id token in a type/relation/value/filler position and no
    non-id token in an id position of a canonical key."""
    bad = 0
    for e in eps:
        for kt in e["key_tokens"]:
            classes = [KS.token_class(t) for t in kt]
            if classes != ["subject_type", "id", "id", "sep", "relation_type", "object_type"]:
                bad += 1
    return {"pass": bad == 0, "malformed_keys": bad}


def check_pools_disjoint_and_markerless(salt="e1s_pool_v1"):
    p = KS.identity_pools(salt)
    tr, dv, fn = set(p["train"]), set(p["dev"]), set(p["final"])
    disjoint = not (tr & dv) and not (tr & fn) and not (dv & fn)
    # marker-free: every id primitive occurs at both positions in every pool
    prims_ok = all({a for a, _ in pool} == set(range(KS.ID_PRIMS)) and {b for _, b in pool} == set(range(KS.ID_PRIMS))
                   for pool in (tr, dv, fn))
    return {"pass": disjoint and prims_ok, "train": len(tr), "dev": len(dv), "final": len(fn), "markerless": prims_ok}


def check_eval_targets_unseen(eval_eps, salt="e1s_pool_v1"):
    train = set(KS.identity_pools(salt)["train"])
    leaked = 0
    for e in eval_eps:
        if e["target_index"] < 0:
            continue
        kt = e["key_tokens"][e["target_index"]]
        if (kt[1] - KS._ID_BASE, kt[2] - KS._ID_BASE) in train:
            leaked += 1
    return {"pass": leaked == 0, "leaked_targets": leaked}


def check_no_answer_in_key(eps):
    bad = sum(1 for e in eps for kt in e["key_tokens"] if any(KS.token_class(t) == "value" for t in kt))
    return {"pass": bad == 0, "keys_with_value_token": bad}


def check_heldout_pairs_absent_from_training(train_eps, salt="e1s_pool_v1"):
    held = set(KS.st_rel_pairs(salt)["held_out"])
    hits = 0
    for e in train_eps:
        for kt in e["key_tokens"]:
            if ((kt[0] - KS._ST_BASE) // KS.SYN, (kt[4] - KS._REL_BASE) // KS.SYN) in held:
                hits += 1
    return {"pass": hits == 0, "heldout_pair_keys_in_training": hits, "n_heldout_pairs": len(held)}


def check_lexical_overlap_bounded(eps, max_acc=None):
    max_acc = C.GATES["lexical_overlap_max_accuracy"] if max_acc is None else max_acc
    valid = [e for e in eps if e["target_index"] >= 0]
    acc = sum(lexical_overlap_prediction(e) == e["target_index"] for e in valid) / len(valid) if valid else 0.0
    return {"pass": acc <= max_acc, "lexical_overlap_addressing": acc, "max": max_acc}


def check_no_table_import():
    import pathlib
    here = pathlib.Path(__file__).resolve().parent
    banned = ("ephemeral_table", "EphemeralTable", "v100_table", "external_fallback")
    hit = [f"{fn}:{b}" for fn in ("run.py", "e1_import.py") for b in banned
           if (here / fn).exists() and b in (here / fn).read_text()]
    return {"pass": not hit, "banned_hits": hit}


def run_all(eval_splits: dict, train_eps: list) -> dict:
    all_eps = [e for eps in eval_splits.values() for e in eps]
    r = {
        "no_exact_overlap_on_paraphrased_tokens": check_no_exact_overlap_on_paraphrased_tokens(all_eps),
        "id_token_class_reserved": check_id_token_class_reserved(all_eps + train_eps),
        "pools_disjoint_and_markerless": check_pools_disjoint_and_markerless(),
        "eval_targets_unseen": check_eval_targets_unseen(all_eps),
        "no_answer_in_key": check_no_answer_in_key(all_eps),
        "heldout_pairs_absent_from_training": check_heldout_pairs_absent_from_training(train_eps),
        "lexical_overlap_bounded": check_lexical_overlap_bounded(all_eps),
        "no_table_import": check_no_table_import(),
    }
    r["all_pass"] = all(v["pass"] for v in r.values() if isinstance(v, dict))
    return r
