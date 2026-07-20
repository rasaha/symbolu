#!/usr/bin/env python3
"""
Evaluation-facing annotations for the hidden corpus — the private metadata that a
resolver must NEVER receive: gold graph, governance, packet expectation, author
justification, confidence, ambiguity, difficulty, capability.

Keyed by the same opaque id as the executable view, but this module is only
imported by evaluation/audit code, never by a resolver.
"""

from __future__ import annotations

from ._authored import AUTHORED
from .corpus import opaque_id

_ANN = {opaque_id(a): a for a in AUTHORED}


def annotation(cid: str) -> dict:
    a = _ANN[cid]
    return {
        "capability": list(a["capability"]),
        "difficulty": a["difficulty"],
        "variation": list(a["variation"]),
        "gold_nodes": dict(a["gold_nodes"]),
        "gold_edges": [tuple(e) for e in a["gold_edges"]],
        "governing": list(a["governing"]),
        "abstain": a["abstain"],
        "expectation": dict(a["expectation"]),
        "governance_explanation": a["governance_explanation"],
        "justification": a["justification"],
        "confidence": a["confidence"],
        "ambiguity": a["ambiguity"],
        "negative_control": a["negative_control"],
    }


def all_annotations() -> dict[str, dict]:
    return {cid: annotation(cid) for cid in _ANN}
