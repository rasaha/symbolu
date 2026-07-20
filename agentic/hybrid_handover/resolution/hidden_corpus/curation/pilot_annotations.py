#!/usr/bin/env python3
"""Evaluation-facing annotations for the ACCEPTED pilot cases (adjudicated gold +
metadata + evidence provenance). Never imported by resolver-facing code."""

from __future__ import annotations

from .records import accepted_candidates, adjudication_record, opaque_id

_BY_ID = {opaque_id(c): c for c in accepted_candidates()}


def annotation(cid: str) -> dict:
    c = _BY_ID[cid]
    adj = adjudication_record(c)
    g = adj["accepted_graph"]
    return {
        "gold_nodes": dict(g["nodes"]),
        "gold_edges": [tuple(e) for e in g["edges"]],
        "governing": list(g["governing"]),
        "abstain": g["abstain"],
        "packet_expectation": dict(adj["accepted_packet"]),
        "final_difficulty": adj["final_difficulty"],
        "capability": list(c["intended_capability"]),
        "variation": list(c["variation"]),
        "negative_control": c["negative_control"],
        "ambiguity": c["ann_ambiguity"],
        "confidence": c["ann_confidence"],
        "evidence_provenance": dict(c["provenance"]),
    }


def all_annotations() -> dict[str, dict]:
    return {cid: annotation(cid) for cid in _BY_ID}
