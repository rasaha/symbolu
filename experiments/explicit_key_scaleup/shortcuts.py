"""Structure-blind baselines for E1-S (draft §5 rule 4; BTRR F13 margin rule). Torch-free.

Each baseline is a REAL predictor fitted on the cohort's gold (an optimistic bound, i.e. the conservative
direction for a shortcut detector). Compared against the model's G1 end-to-end accuracy; any baseline
within `structure_blind_margin` => SHORTCUT_OR_LEAKAGE_DETECTED.
"""
from __future__ import annotations

from collections import Counter

from . import keyspace as KS

SUITE = ("query_only_majority_value", "most_frequent_value", "random_valid_key", "lexical_overlap_key")


def _query_signature(e):
    """(subject_type, relation_type, object_type) primitives of the query, synonym-collapsed; ids excluded."""
    sig = []
    for t in e["query_tokens"]:
        c = KS.token_class(t)
        if c == "subject_type": sig.append(("st", (t - KS._ST_BASE) // KS.SYN))
        elif c == "relation_type": sig.append(("rel", (t - KS._REL_BASE) // KS.SYN))
        elif c == "object_type": sig.append(("ot", (t - KS._OT_BASE) // KS.SYN))
    return tuple(sorted(sig))


def _qset(e):
    return {t for t in e["query_tokens"] if t != KS.PAD}


def lexical_overlap_prediction(e) -> int:
    """Key with the most shared surface tokens (ties -> lowest index). With verbatim ids this resolves the
    same-subject group only; type/relation tokens never overlap (synonyms)."""
    qs = _qset(e)
    scores = [len(qs & {t for t in kt if t not in (KS.PAD, KS.SEP)}) for kt in e["key_tokens"]]
    best = max(scores)
    return scores.index(best)


def baseline_e2e(kind: str, eps: list) -> float:
    """End-to-end value accuracy of a structure-blind predictor on VALID episodes of `eps`."""
    import random
    valid = [e for e in eps if e["target_index"] >= 0]
    if not valid:
        return 0.0
    if kind == "query_only_majority_value":
        # leave-one-out: majority gold value among OTHER episodes with the same query signature (falls back
        # to the LOO global majority), so a near-unique signature cannot memorize its own gold.
        by, glob = {}, Counter()
        for e in valid:
            by.setdefault(_query_signature(e), Counter())[e["target_value"]] += 1
            glob[e["target_value"]] += 1
        ok = 0
        for e in valid:
            c = by[_query_signature(e)].copy(); c[e["target_value"]] -= 1
            g = glob.copy(); g[e["target_value"]] -= 1
            pool = c if sum(c.values()) > 0 else g
            pred = pool.most_common(1)[0][0] if sum(pool.values()) > 0 else None
            ok += pred == e["target_value"]
        return ok / len(valid)
    if kind == "most_frequent_value":
        glob = Counter(e["target_value"] for e in valid)
        ok = 0
        for e in valid:                      # leave-one-out global majority
            g = glob.copy(); g[e["target_value"]] -= 1
            ok += (g.most_common(1)[0][0] == e["target_value"]) if sum(g.values()) > 0 else 0
        return ok / len(valid)
    if kind == "random_valid_key":
        rng = random.Random(0)
        return sum(e["key_values"][rng.randrange(len(e["key_values"]))] == e["target_value"] for e in valid) / len(valid)
    if kind == "lexical_overlap_key":
        return sum(e["key_values"][lexical_overlap_prediction(e)] == e["target_value"] for e in valid) / len(valid)
    raise ValueError(kind)


def run_suite(eps: list, model_e2e: float, margin: float) -> dict:
    baselines = {k: baseline_e2e(k, eps) for k in SUITE}
    within = {k: (model_e2e - v) < margin for k, v in baselines.items()}
    return {"baselines": baselines, "within_margin": within, "shortcut_detected": any(within.values()),
            "margin": margin, "model": model_e2e}
