"""
Structural validator for an assembled EvidencePacket.

Checks the invariants an EvidencePacket must satisfy to be safe for downstream claim
validation: no dangling references, every relationship grounded in evidence, every
governance decision supported (or an explicit no-support terminal), no provenance loss, a
connected acyclic dependency graph, no duplicate object ids, and minimality. Returns
``(ok, problems)``; it never mutates the packet.
"""

from __future__ import annotations

import json
from typing import List, Tuple

from truth_assurance_pipeline.tap_e5_evidence_assembly import dependency_graph as dg
from truth_assurance_pipeline.tap_e5_evidence_assembly.schema import EvidencePacket

# governance statuses that legitimately carry no supporting relationship
_NO_SUPPORT_OK = {"CONFLICTED", "NO_GOVERNING_AUTHORITY", "GOVERNING_WITH_EXCEPTION",
                  "INSUFFICIENT_BASIS", "UNRESOLVED"}


def validate_packet(packet: EvidencePacket) -> Tuple[bool, Tuple[str, ...]]:
    problems: List[str] = []
    ev_ids = [e.unit_id for e in packet.evidence_units]
    rel_ids = [r.assertion_id for r in packet.relationships]
    gov_ids = [g.decision_id for g in packet.governance_decisions]
    ev_set, rel_set = set(ev_ids), set(rel_ids)
    known = ev_set | rel_set | set(gov_ids) | {packet.intent.request_id}

    # duplicate object ids
    for label, ids in (("evidence", ev_ids), ("relationship", rel_ids),
                       ("governance", gov_ids)):
        if len(ids) != len(set(ids)):
            problems.append(f"duplicate {label} ids")

    # every relationship grounded in evidence that is present
    for r in packet.relationships:
        if not r.evidence_unit_ids:
            problems.append(f"relationship {r.assertion_id} has no evidence")
        for uid in r.evidence_unit_ids:
            if uid not in ev_set:
                problems.append(f"relationship {r.assertion_id} references absent evidence {uid}")

    # every governance decision supported (or an explicit no-support terminal)
    for g in packet.governance_decisions:
        present = [a for a in g.supporting_relationships if a in rel_set]
        if not present and g.status not in _NO_SUPPORT_OK:
            problems.append(f"governance {g.decision_id} has no supporting relationship")
        for a in g.supporting_relationships:
            if a not in rel_set:
                problems.append(f"governance {g.decision_id} references absent relationship {a}")

    # conflicts must not reference absent members
    for c in packet.conflicts:
        for m in c.member_ids:
            if m not in known:
                problems.append(f"conflict {c.conflict_id} references absent member {m}")

    # dependency-edge integrity + acyclicity
    for e in dg.dangling_edges(packet.dependency_edges, known):
        problems.append(f"dangling edge {e.src_id}->{e.dst_id}")
    if dg.has_cycle(packet.dependency_edges):
        problems.append("dependency graph has a cycle")

    # no orphans (objects touching no edge; intent is a valid sink)
    for o in dg.orphans(ev_ids + rel_ids + gov_ids, packet.dependency_edges,
                        packet.intent.request_id):
        problems.append(f"orphan object {o}")

    # provenance completeness (no provenance loss)
    for oid in ev_ids + rel_ids + gov_ids:
        if oid not in packet.provenance_index:
            problems.append(f"provenance missing for {oid}")

    # minimality: no unreferenced evidence, no downstream-unused raw metadata
    referenced = {uid for r in packet.relationships for uid in r.evidence_unit_ids}
    for uid in ev_ids:
        if uid not in referenced:
            problems.append(f"non-minimal: evidence {uid} referenced by no relationship")
    if "raw_upstream_signals" in packet.confidence_summary:
        problems.append("non-minimal: downstream-unused raw_upstream_signals present")

    # schema round-trip
    try:
        if json.loads(packet.to_json())["packet_id"] != packet.packet_id:
            problems.append("schema round-trip mismatch")
    except Exception as exc:  # pragma: no cover
        problems.append(f"schema round-trip raised {exc!r}")

    return (not problems, tuple(problems))
