"""Deterministic, concise finding text (§9).

No dramatic "crime story" prose. The explanation states, factually, which
individually-admissible actions contributed which capability fragments, which are
still missing, and why the threat interpretation dominates / is neutralized /
remains ambiguous. Steps are ordered by their assembly position so the record
reads in the order the assembly happened.
"""

from __future__ import annotations

from .ledger import _LedgerInstance
from .matcher import MatchResult
from .model import Ontology


def _step(li: _LedgerInstance) -> dict:
    inst = li.inst
    return {
        "position": inst.position,
        "sequence_id": inst.sequence_id,
        "correlation_id": inst.correlation_id,
        "event_id": inst.event_id,
        "actor": inst.actor,
        "operation": inst.operation,
        "fragment_id": inst.fragment_id,
        "note": inst.note,
        "state": li.state,
    }


def present_fragments(ontology: Ontology, result: MatchResult) -> list[dict]:
    steps = []
    for fid, li in result.contributing.items():
        s = _step(li)
        s["fragment_title"] = ontology.fragments[fid].title
        steps.append(s)
    steps.sort(key=lambda s: (s["position"], s["sequence_id"], s["fragment_id"]))
    return steps


def explanation(result: MatchResult, benign_status: str) -> str:
    r = result.recipe
    base = r.explanation_template or (
        f"Linked actions have accumulated fragments of {r.name} ({r.ref}).")
    if result.missing_required:
        return (f"Partial assembly of {r.name} ({r.ref}): "
                f"{len(result.present_required)}/{len(r.required)} required "
                f"fragments present; missing {', '.join(result.missing_required)}.")
    tail = {
        "THREAT_DOMINATES": "No benign-context evidence neutralizes it.",
        "AMBIGUOUS": "A benign context was asserted but is not fully supported; "
                     "the threat interpretation is not neutralized.",
        "NEUTRALIZED": "A valid, scope-matched approval qualifies the escalation.",
    }.get(benign_status, "")
    return f"{base} {tail}".strip()
