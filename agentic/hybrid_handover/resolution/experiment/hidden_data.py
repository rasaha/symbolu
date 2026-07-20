#!/usr/bin/env python3
"""
Unified read-only view of the Hidden Relationship Corpus Pilot v0.2 (22 seed + 38
pilot) for evaluation. Merges evidence (resolver-facing) with gold annotations
(evaluation-facing). Nothing frozen is modified.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.hidden_corpus import corpus as seed_corpus
from agentic.hybrid_handover.resolution.hidden_corpus.annotations import annotation as seed_ann
from agentic.hybrid_handover.resolution.hidden_corpus.curation import pilot_corpus
from agentic.hybrid_handover.resolution.hidden_corpus.curation.pilot_annotations import annotation as pilot_ann


def _pkt(ann):
    return ann.get("expectation") or ann.get("packet_expectation") or {}


def hidden_cases() -> list[dict]:
    out = []
    for c in seed_corpus.executable_cases():
        a = seed_ann(c["id"])
        out.append({"cid": c["id"], "source": "seed", "question": c["question"],
                    "evidence": seed_corpus.evidence_for(c["id"]), "gold": _gold(a)})
    for c in pilot_corpus.executable_cases():
        a = pilot_ann(c["id"])
        out.append({"cid": c["id"], "source": "pilot", "question": c["question"],
                    "evidence": pilot_corpus.evidence_for(c["id"]), "gold": _gold(a)})
    return out


def _gold(a: dict) -> dict:
    return {
        "nodes": dict(a["gold_nodes"]), "edges": [tuple(e) for e in a["gold_edges"]],
        "governing": list(a["governing"]), "abstain": a["abstain"],
        "packet": _pkt(a),
        "capability": list(a.get("capability", [])),
        "difficulty": a.get("difficulty") or a.get("final_difficulty"),
        "variation": list(a.get("variation", [])),
        "negative_control": a.get("negative_control"),
        "ambiguity": a.get("ambiguity", "none"),
    }


def governance_owned(gold: dict) -> bool:
    # pure-coverage (OCR/scan) cases are SafetyGate-owned, not the resolver's
    caps = gold.get("capability", [])
    return not (caps == ["coverage"])
