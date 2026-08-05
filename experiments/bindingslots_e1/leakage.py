#!/usr/bin/env python3
"""Mechanical leakage / exact-symbol / memorization shortcut suite (torch-free).

Runs on constructed data (no trained model needed). If any check fails, the experiment must terminate
with EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED regardless of accuracy.
"""
from __future__ import annotations

import task as T


def _key_token_set(kt):
    return {t for t in kt if t not in (T.PAD, T.SEP)}


def _query_token_set(qt):
    return {t for t in qt if t != T.PAD}


def check_no_exact_overlap(eps):
    """For every valid (query, correct key), query and key share NO surface token (matched primitives
    use different synonym indices; key uses SEP/canonical, query uses non-zero synonyms + filler)."""
    worst = 0
    for e in eps:
        if e["target_index"] < 0:
            continue
        ks = _key_token_set(e["key_tokens"][e["target_index"]])
        qs = _query_token_set(e["query_tokens"])
        worst = max(worst, len(ks & qs))
    return {"pass": worst == 0, "max_shared_tokens": worst}


def check_pools_disjoint(salt="e1_pool_v1"):
    p = T.identity_pools(salt)
    tr, dv, fn = set(p["train"]), set(p["dev"]), set(p["final"])
    return {"pass": not (tr & dv) and not (tr & fn) and not (dv & fn),
            "train": len(tr), "dev": len(dv), "final": len(fn)}


def check_eval_ids_unseen(eval_eps, salt="e1_pool_v1"):
    """No entity-identity in eval episodes belongs to the train pool (checks G5 recombination too:
    any (id,attr,val) with an eval id is automatically an unseen combination)."""
    train = set(T.identity_pools(salt)["train"])
    leaked = 0
    for e in eval_eps:
        for kt in e["key_tokens"]:
            # decode identity primitives from canonical key tokens [E(a,0),E(b,0),SEP,A(attr,0)]
            a = (kt[0] - T._E_BASE) // T.SYN
            b = (kt[1] - T._E_BASE) // T.SYN
            if tuple(sorted((a, b))) in train:
                # a key drawn from train pool inside an eval episode is allowed as a NEGATIVE;
                # only the TARGET identity must be unseen. Check the target below instead.
                pass
    # check only the target identity of each valid episode
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
    """No value token appears in any stored key (keys carry identity/attribute surface only)."""
    bad = 0
    for e in eps:
        for kt in e["key_tokens"]:
            if any(T._V_BASE <= t < T._V_BASE + T.N_VALUES for t in kt):
                bad += 1
    return {"pass": bad == 0, "keys_with_value_token": bad}


def check_lexical_overlap_uninformative(eps):
    """A surface-token-overlap matcher (shared-token count query-vs-key) must be ~chance, proving the
    task cannot be solved by symbolic hashing. Reports overlap-matcher accuracy vs 1/K."""
    import random
    correct = 0
    n = 0
    for e in eps:
        if e["target_index"] < 0:
            continue
        qs = _query_token_set(e["query_tokens"])
        scores = [len(qs & _key_token_set(kt)) for kt in e["key_tokens"]]
        best = max(scores)
        winners = [i for i, s in enumerate(scores) if s == best]
        # deterministic tie-break by index (still uninformative since overlap is ~0 everywhere)
        pred = winners[0]
        correct += int(pred == e["target_index"])
        n += 1
    acc = correct / n if n else 0.0
    K = T.KEYS_PER_EPISODE
    # pass if the lexical matcher is no better than ~2x chance (surface overlap carries no signal)
    return {"pass": acc <= 2.0 / K, "lexical_overlap_accuracy": acc, "chance": 1.0 / K}


def check_no_table_import():
    """E1/B0 ordinary inference imports no external ephemeral table. Scans source text by path (no
    import) so it runs in a torch-free environment."""
    import pathlib
    here = pathlib.Path(__file__).resolve().parent
    banned = ("ephemeral_table", "EphemeralTable", "v100_table", "external_fallback")
    hit = []
    for fn in ("models.py", "engine.py"):
        p = here / fn
        if p.exists():
            s = p.read_text()
            hit += [f"{fn}:{b}" for b in banned if b in s]
    return {"pass": not hit, "banned_hits": hit}


def run_all(dev_eval_splits):
    """dev_eval_splits: dict split_name -> episodes (built from the DEV pool for calibration)."""
    all_eps = [e for eps in dev_eval_splits.values() for e in eps]
    valid_eps = [e for e in all_eps if e["target_index"] >= 0]
    r = {
        "no_exact_overlap": check_no_exact_overlap(valid_eps),
        "pools_disjoint": check_pools_disjoint(),
        "eval_ids_unseen": check_eval_ids_unseen(all_eps),
        "no_answer_in_key": check_no_answer_in_key(all_eps),
        "lexical_overlap_uninformative": check_lexical_overlap_uninformative(valid_eps),
        "no_table_import": check_no_table_import(),
    }
    r["all_pass"] = all(v["pass"] for v in r.values() if isinstance(v, dict) and "pass" in v)
    return r
