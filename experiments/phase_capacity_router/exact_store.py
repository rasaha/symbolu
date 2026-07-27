"""
exact_store.py — bounded EXACT store of capacity K with oracle identity binding (§5).

Admits the top-K candidate events by router score, binds them by composite identity
(entity, with latest-position-wins for same-entity updates), and answers the exact query by
lookup / hop-chaining. Fully exact: no neural decode, no unbounded fallback. Answer accuracy
is therefore a direct function of admission — a required event that is not admitted cannot be
answered. The Phase state never answers directly.
"""
from __future__ import annotations

from typing import List


def admit_topk(scores: List[float], K: int) -> set:
    """Indices of the top-K scored candidate events (ties broken by index)."""
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    return set(order[:K])


def build_store(events, admitted: set) -> dict:
    """composite identity (entity,relation) -> value, latest admitted position wins."""
    store = {}
    for i in sorted(admitted, key=lambda i: events[i]["position"]):
        store[events[i]["ident"]] = events[i]["value"]
    return store


def answer_query(example, admitted: set):
    """Exact retrieval from the admitted store. Returns (predicted_answer, correct)."""
    events = example["events"]
    store = build_store(events, admitted)
    fam = example["family"]
    if fam == "multihop":
        cur = example["query_entity"]
        for _ in range(example["n_required"]):
            if cur not in store:
                return None, False
            cur = store[cur]
        return cur, cur == example["answer"]
    pred = store.get(example["query_entity"], None)
    return pred, pred == example["answer"]


def grade(example, admitted: set) -> dict:
    """Admission quality + exact correctness for one example."""
    events = example["events"]
    req = [i for i, ev in enumerate(events) if ev["required"]]
    req_admitted = sum(1 for i in req if i in admitted)
    cats = {"relevant": [0, 0], "hard": [0, 0], "ordinary": [0, 0], "relevant_stale": [0, 0]}
    for i, ev in enumerate(events):
        c = ev["category"]
        if c in cats:
            cats[c][1] += 1
            if i in admitted:
                cats[c][0] += 1
    pred, correct = answer_query(example, admitted)
    n_admit = len(admitted)
    rel_admit = cats["relevant"][0]; rel_tot = max(1, cats["relevant"][1])
    return {
        "correct": int(correct),
        "all_required_admitted": int(req_admitted == len(req)),
        "n_required": len(req), "req_admitted": req_admitted,
        "relevant_recall": rel_admit / rel_tot,
        "relevant_precision": rel_admit / max(1, n_admit),
        "hard_false_admit": cats["hard"][0] / max(1, cats["hard"][1]),
        "ordinary_false_admit": cats["ordinary"][0] / max(1, cats["ordinary"][1]),
        "topk_purity": rel_admit / max(1, n_admit),
        "capacity_util": n_admit,
    }
