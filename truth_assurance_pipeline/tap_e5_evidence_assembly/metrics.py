"""
TAP-E5 packet metrics + independent critical-failure detection.

Every metric is reported separately (never one aggregate score). Assembly failures — losing
a conflict/gap/provenance, orphaning an object, breaking a dependency, duplicating ids,
shipping an incomplete-but-smaller packet, or an unjustifiably larger one — are counted
INDEPENDENTLY of the pass/fail metrics, so a high average can never mask a packet defect.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Set, Tuple

from truth_assurance_pipeline.tap_e5_evidence_assembly import dependency_graph as dg
from truth_assurance_pipeline.tap_e5_evidence_assembly.packet_validator import validate_packet
from truth_assurance_pipeline.tap_e5_evidence_assembly.schema import EvidencePacket

CRITICAL_CLASSES = (
    "ORPHAN_EVIDENCE", "ORPHAN_RELATIONSHIP", "ORPHAN_GOVERNANCE_DECISION", "LOST_CONFLICT",
    "LOST_GAP", "LOST_PROVENANCE", "BROKEN_DEPENDENCY", "DUPLICATE_IDENTIFIERS",
    "PACKET_SMALLER_BUT_INCOMPLETE", "PACKET_LARGER_WITHOUT_JUSTIFICATION",
    "SCHEMA_CORRUPTION", "NON_DETERMINISTIC_PACKET",
)

_TERMINAL_NO_SUPPORT = {"CONFLICTED", "NO_GOVERNING_AUTHORITY", "GOVERNING_WITH_EXCEPTION",
                        "INSUFFICIENT_BASIS", "UNRESOLVED"}


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    family: str
    completeness: float
    minimality: float
    dependency_preservation: float
    provenance_preservation: float
    reference_integrity: float
    conflict_preservation: float
    gap_preservation: float
    duplicate_elimination: float
    unsupported_reference_rate: float
    orphan_rate: float
    validation_success: float
    object_count: int
    criticals: Tuple[str, ...]


def _frac(present: int, total: int) -> float:
    return 1.0 if total == 0 else present / total


def score_case(case, packet: EvidencePacket, did_validate: bool) -> CaseScore:
    gold = case.gold()
    ev_ids = [e.unit_id for e in packet.evidence_units]
    rel_ids = [r.assertion_id for r in packet.relationships]
    gov_ids = [g.decision_id for g in packet.governance_decisions]
    ev_set, rel_set, gov_set = set(ev_ids), set(rel_ids), set(gov_ids)
    conf_ids = {c.conflict_id for c in packet.conflicts}
    gap_ids = {g.gap_id for g in packet.gaps}
    all_obj = ev_ids + rel_ids + gov_ids

    # completeness (over all required objects)
    req = [("ev", gold["evidence"], ev_set), ("rel", gold["relationships"], rel_set),
           ("gov", gold["governance"], gov_set), ("conf", gold["conflicts"], conf_ids),
           ("gap", gold["gaps"], gap_ids)]
    req_total = sum(len(r) for _, r, _ in req)
    req_present = sum(len(r & have) for _, r, have in req)
    completeness = _frac(req_present, req_total)

    # minimality (no removable object retained)
    referenced = {uid for r in packet.relationships for uid in r.evidence_unit_ids}
    unused_ev = [u for u in ev_ids if u not in referenced]
    dup_ids = len(all_obj) != len(set(all_obj))
    raw_meta = "raw_upstream_signals" in packet.confidence_summary
    dup_edges = len(packet.dependency_edges) != len({e.key() for e in packet.dependency_edges})
    minimality = 0.0 if (unused_ev or dup_ids or raw_meta or dup_edges) else 1.0

    # dependency preservation (required edges reconstructible)
    edge_keys = {e.key() for e in packet.dependency_edges}
    need = 0
    have = 0
    for r in packet.relationships:
        if r.assertion_id in gold["relationships"]:
            for uid in r.evidence_unit_ids:
                if uid in gold["evidence"]:
                    need += 1
                    have += 1 if (r.assertion_id, uid, "supported_by_evidence") in edge_keys else 0
    for g in packet.governance_decisions:
        for a in g.supporting_relationships:
            if a in gold["relationships"]:
                need += 1
                have += 1 if (g.decision_id, a, "supported_by_relationship") in edge_keys else 0
    dependency_preservation = _frac(have, need)

    # provenance preservation
    prov_present = sum(1 for o in all_obj if o in packet.provenance_index)
    prov_present += 1 if packet.intent.request_id in packet.provenance_index else 0
    provenance_preservation = _frac(prov_present, len(all_obj) + 1)

    # reference integrity
    dangling = list(dg.dangling_edges(packet.dependency_edges,
                                      set(all_obj) | {packet.intent.request_id}))
    for r in packet.relationships:
        dangling += [uid for uid in r.evidence_unit_ids if uid not in ev_set]
    for g in packet.governance_decisions:
        dangling += [a for a in g.supporting_relationships if a not in rel_set]
    for c in packet.conflicts:
        dangling += [m for m in c.member_ids
                     if m not in (ev_set | rel_set | gov_set | {packet.intent.request_id})]
    reference_integrity = 0.0 if dangling else 1.0

    conflict_preservation = _frac(len(gold["conflicts"] & conf_ids), len(gold["conflicts"]))
    gap_preservation = _frac(len(gold["gaps"] & gap_ids), len(gold["gaps"]))
    duplicate_elimination = 0.0 if dup_ids else 1.0

    # unsupported references
    n_units = len(packet.relationships) + len(packet.governance_decisions)
    unsupported = 0
    for r in packet.relationships:
        if not [u for u in r.evidence_unit_ids if u in ev_set]:
            unsupported += 1
    for g in packet.governance_decisions:
        present = [a for a in g.supporting_relationships if a in rel_set]
        if not present and g.status not in _TERMINAL_NO_SUPPORT:
            unsupported += 1
    unsupported_reference_rate = (unsupported / n_units) if n_units else 0.0

    orphan_ids = dg.orphans(all_obj, packet.dependency_edges, packet.intent.request_id)
    orphan_rate = _frac(len(orphan_ids), len(all_obj))

    ok, _ = validate_packet(packet)
    validation_success = 1.0 if (did_validate and ok) else 0.0

    # -- critical failures ---------------------------------------------------
    crit: List[str] = []
    if unused_ev:
        crit.append("ORPHAN_EVIDENCE")
    if any(not r.evidence_unit_ids for r in packet.relationships):
        crit.append("ORPHAN_RELATIONSHIP")
    for g in packet.governance_decisions:
        if (not [a for a in g.supporting_relationships if a in rel_set]
                and g.status not in _TERMINAL_NO_SUPPORT):
            crit.append("ORPHAN_GOVERNANCE_DECISION")
            break
    if gold["conflicts"] - conf_ids:
        crit.append("LOST_CONFLICT")
    if gold["gaps"] - gap_ids:
        crit.append("LOST_GAP")
    if prov_present < len(all_obj) + 1:
        crit.append("LOST_PROVENANCE")
    if dangling:
        crit.append("BROKEN_DEPENDENCY")
    if dup_ids:
        crit.append("DUPLICATE_IDENTIFIERS")
    if completeness < 1.0:
        crit.append("PACKET_SMALLER_BUT_INCOMPLETE")
    if unused_ev or raw_meta or dup_edges:
        crit.append("PACKET_LARGER_WITHOUT_JUSTIFICATION")
    try:
        import json
        if json.loads(packet.to_json())["packet_id"] != packet.packet_id:
            crit.append("SCHEMA_CORRUPTION")
    except Exception:
        crit.append("SCHEMA_CORRUPTION")

    return CaseScore(
        case_id=case.case_id, family=case.family, completeness=completeness,
        minimality=minimality, dependency_preservation=dependency_preservation,
        provenance_preservation=provenance_preservation,
        reference_integrity=reference_integrity, conflict_preservation=conflict_preservation,
        gap_preservation=gap_preservation, duplicate_elimination=duplicate_elimination,
        unsupported_reference_rate=unsupported_reference_rate, orphan_rate=orphan_rate,
        validation_success=validation_success, object_count=len(all_obj),
        criticals=tuple(crit))


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 1.0


def aggregate(scores: Sequence[CaseScore]) -> Dict[str, object]:
    n = len(scores) or 1
    crit_counts: Dict[str, int] = {c: 0 for c in CRITICAL_CLASSES}
    for s in scores:
        for c in s.criticals:
            crit_counts[c] = crit_counts.get(c, 0) + 1
    severe = sum(crit_counts.values())
    return {
        "n_cases": len(scores),
        "packet_completeness": _mean([s.completeness for s in scores]),
        "packet_minimality": _mean([s.minimality for s in scores]),
        "dependency_preservation": _mean([s.dependency_preservation for s in scores]),
        "provenance_preservation": _mean([s.provenance_preservation for s in scores]),
        "reference_integrity": _mean([s.reference_integrity for s in scores]),
        "conflict_preservation": _mean([s.conflict_preservation for s in scores]),
        "gap_preservation": _mean([s.gap_preservation for s in scores]),
        "duplicate_elimination": _mean([s.duplicate_elimination for s in scores]),
        "unsupported_reference_rate": _mean([s.unsupported_reference_rate for s in scores]),
        "orphan_rate": _mean([s.orphan_rate for s in scores]),
        "validation_success": _mean([s.validation_success for s in scores]),
        "mean_object_count": _mean([float(s.object_count) for s in scores]),
        "critical_failures": crit_counts,
        "severe_critical_failure_count": float(severe),
    }
