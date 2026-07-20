#!/usr/bin/env python3
"""
Corpus statistics + blind-spot detection (evaluation-side; no resolver run)."""

from __future__ import annotations

from collections import Counter

from .annotations import all_annotations
from .validate import CAPABILITIES, VARIATIONS

_GOV_TYPES = ("supersedes", "overrides", "governs_over", "references",
              "exception_to", "conflicts_with", "same_as", "amends", "effective_after")


def statistics():
    ann = all_annotations()
    n = len(ann)
    cap = Counter()
    diff = Counter()
    var = Counter()
    edge = Counter()
    gov = Counter()
    ambiguous = 0
    abstain = 0
    negctl = Counter()
    for a in ann.values():
        for c in a["capability"]:
            cap[c] += 1
        diff[a["difficulty"]] += 1
        for v in a["variation"]:
            var[v] += 1
        for (_s, t, _d) in a["gold_edges"]:
            edge[t] += 1
        # governance type of the case
        etypes = {t for (_s, t, _d) in a["gold_edges"]}
        if a["abstain"]:
            gov["abstain"] += 1
        elif "governs_over" in etypes or "overrides" in etypes:
            gov["precedence_override"] += 1
        elif "supersedes" in etypes or "effective_after" in etypes:
            gov["supersession"] += 1
        elif "references" in etypes:
            gov["reference_resolution"] += 1
        elif "exception_to" in etypes:
            gov["exception"] += 1
        elif not etypes:
            gov["single_or_none"] += 1
        else:
            gov["other"] += 1
        if a["ambiguity"] != "none":
            ambiguous += 1
        if a["abstain"]:
            abstain += 1
        if a["negative_control"]:
            negctl[a["negative_control"]] += 1

    blind = {
        "capabilities_zero": [c for c in CAPABILITIES if cap.get(c, 0) == 0],
        "capabilities_single": [c for c in CAPABILITIES if cap.get(c, 0) == 1],
        "variations_zero": [v for v in VARIATIONS if var.get(v, 0) == 0],
        "edge_types_zero": [t for t in _GOV_TYPES if edge.get(t, 0) == 0],
        "difficulty_levels_thin": [lvl for lvl in range(1, 6) if diff.get(lvl, 0) <= 1],
    }
    return {
        "n_cases": n,
        "coverage_by_capability": dict(cap),
        "coverage_by_difficulty": {lvl: diff.get(lvl, 0) for lvl in range(1, 6)},
        "coverage_by_variation": dict(var),
        "coverage_by_relationship_type": dict(edge),
        "coverage_by_governance_type": dict(gov),
        "coverage_by_ambiguity": {"ambiguous": ambiguous, "unambiguous": n - ambiguous},
        "coverage_by_abstention": {"abstain": abstain, "answer": n - abstain},
        "negative_controls": dict(negctl),
        "blind_spots": blind,
    }
