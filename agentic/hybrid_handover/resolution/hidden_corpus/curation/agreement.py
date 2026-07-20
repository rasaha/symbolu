#!/usr/bin/env python3
"""
Independent-graph agreement metrics. The author's private intended graph and the
blind annotator's graph are compared on SEPARATE dimensions — never collapsed
into a single score.

Cohen's kappa is reported only for the binary abstention decision (categorically
appropriate). It is NOT used for edge agreement, because the edge universe is
sparse and open-ended, which makes chance-correction ill-defined — documented in
ANNOTATOR_AGREEMENT.md.
"""

from __future__ import annotations


def _prf(pred: set, ref: set) -> dict:
    tp = len(pred & ref)
    p = tp / len(pred) if pred else (1.0 if not ref else 0.0)
    r = tp / len(ref) if ref else (1.0 if not pred else 0.0)
    f = (2 * p * r / (p + r)) if (p + r) else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4),
            "exact": pred == ref}


def _defeated(graph: dict) -> set:
    disc = set()
    for (s, t, d) in graph.get("edges", []):
        if t in ("supersedes", "overrides", "governs_over"):
            disc.add(d)
    return disc


def compare(author: dict, annot: dict) -> dict:
    a_nodes = set(author.get("nodes", {}))
    b_nodes = set(annot.get("nodes", {}))
    a_pairs = {(s, d) for (s, _t, d) in author.get("edges", [])}
    b_pairs = {(s, d) for (s, _t, d) in annot.get("edges", [])}
    a_type = {(s, d): t for (s, t, d) in author.get("edges", [])}
    b_type = {(s, d): t for (s, t, d) in annot.get("edges", [])}
    a_undir = {frozenset((s, d)) for (s, d) in a_pairs}
    b_undir = {frozenset((s, d)) for (s, d) in b_pairs}

    shared_undir = a_undir & b_undir
    # direction agreement: of shared unordered pairs, same ordered direction
    dir_ok = sum(1 for u in shared_undir
                 if any((s, d) in a_pairs and (s, d) in b_pairs
                        for (s, d) in [tuple(u), tuple(u)[::-1]]))
    # type agreement: over shared ordered pairs
    shared_ord = a_pairs & b_pairs
    type_ok = sum(1 for p in shared_ord if a_type[p] == b_type[p])

    return {
        "node": _prf(b_nodes, a_nodes),
        "edge_presence": _prf(b_pairs, a_pairs),
        "edge_direction": {"agree": dir_ok, "shared_unordered": len(shared_undir),
                           "rate": round(dir_ok / len(shared_undir), 4) if shared_undir else None},
        "edge_type": {"agree": type_ok, "shared_ordered": len(shared_ord),
                      "rate": round(type_ok / len(shared_ord), 4) if shared_ord else None},
        "governing": _prf(set(annot.get("governing", [])), set(author.get("governing", []))),
        "defeated": _prf(_defeated(annot), _defeated(author)),
        "abstention_match": bool(author.get("abstain")) == bool(annot.get("abstain")),
        "packet_membership": _prf(set(annot.get("governing", [])), set(author.get("governing", []))),
    }


def cohens_kappa_binary(pairs: list[tuple[bool, bool]]) -> float | None:
    """Kappa for a binary categorical decision (used only for abstention)."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    pa1 = sum(1 for a, _ in pairs if a) / n
    pb1 = sum(1 for _, b in pairs if b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe == 1.0:
        return 1.0 if po == 1.0 else None  # undefined; report None
    return round((po - pe) / (1 - pe), 4)
