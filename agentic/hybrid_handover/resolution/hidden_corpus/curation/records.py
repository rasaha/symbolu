#!/usr/bin/env python3
"""
Projects authored candidates into the three separate role artifacts and computes
opaque content-hash ids. The annotator projection carries NO author-only field
(blinding). Only ACCEPTED candidates are exposed by the pilot corpus loaders.
"""

from __future__ import annotations

import hashlib

from .candidates import C


def opaque_id(cand: dict) -> str:
    blob = cand["question"] + "|" + "|".join(d["text"] for d in cand["documents"])
    return "HP" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


def author_record(cand: dict) -> dict:
    return {
        "cand_id": opaque_id(cand),
        "question": cand["question"],
        "documents": cand["documents"],
        "intended_capability": cand["intended_capability"],
        "proposed_difficulty": cand["proposed_difficulty"],
        "author_rationale": cand["author_rationale"],
        "intended_graph": cand["intended_graph"],
        "variation": cand["variation"],
        "negative_control": cand["negative_control"],
    }


def annotator_record(cand: dict) -> dict:
    """Blind projection — author-only fields are structurally absent."""
    return {
        "cand_id": opaque_id(cand),
        "graph": cand["ann_graph"],
        "governing": cand["ann_governing"],
        "defeated": cand["ann_defeated"],
        "abstain": cand["ann_abstain"],
        "packet_expectation": cand["ann_packet"],
        "ambiguity_status": cand["ann_ambiguity"],
        "confidence": cand["ann_confidence"],
        "evidence_provenance": cand["provenance"],
    }


def adjudication_record(cand: dict) -> dict:
    from .difficulty_rubric import rubric_level
    accepted = cand["decision"] == "ACCEPTED"
    return {
        "cand_id": opaque_id(cand),
        "decision": cand["decision"],
        "accepted_graph": (cand["ann_graph"] | {"governing": cand["ann_governing"],
                           "abstain": cand["ann_abstain"]}) if accepted else None,
        "accepted_packet": cand["ann_packet"] if accepted else {},
        "final_difficulty": rubric_level(cand["difficulty_factors"]) if accepted else None,
        "final_difficulty_justification": f"rubric over factors {cand['difficulty_factors']}",
        "ambiguity_status": cand["ann_ambiguity"],
        "confidence": cand["ann_confidence"],
        "rationale": cand["adj_rationale"],
    }


def all_candidates() -> list[dict]:
    return C


def accepted_candidates() -> list[dict]:
    return [c for c in C if c["decision"] == "ACCEPTED"]


def candidate_view(cand: dict) -> dict:
    """Flattened view for lifecycle checking."""
    adj = adjudication_record(cand)
    return {
        "cand_id": opaque_id(cand), "decision": cand["decision"],
        "has_author": True, "has_annotator": True, "has_adjudication": True,
        "accepted_graph": adj["accepted_graph"], "rationale": cand["adj_rationale"],
    }
