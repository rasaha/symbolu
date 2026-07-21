"""
Evidence Assembly engine + the A-F baseline configuration.

Consumes four frozen upstream records (IntentRecord/RetrievalRecord/RelationshipRecord/
GovernanceRecord) through their public interfaces and emits exactly one deterministic
EvidencePacket. E5 is a *linker*: it packages what upstream discovered into the smallest
complete, dependency-preserving, provenance-preserving object needed downstream. It performs
no retrieval, no reasoning, no claim validation, no conflict resolution, and no gap filling.

Deterministic 14-stage pipeline (Section: assembly pipeline). Every sort carries a stable id
tiebreak; there is no reliance on set/dict iteration order for any output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import RetrievalRecord
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import RelationshipRecord
from truth_assurance_pipeline.tap_e4_governance_truth.schema import GovernanceRecord
from truth_assurance_pipeline.tap_e5_evidence_assembly import dependency_graph as dg
from truth_assurance_pipeline.tap_e5_evidence_assembly.schema import (
    DependencyEdge, EdgeType, EvidencePacket, ObjectKind, PacketConflict, PacketEvidence,
    PacketGap, PacketGovernance, PacketIntent, PacketRejectedAuthority, PacketRelationship,
    SCHEMA_VERSION,
)
from truth_assurance_pipeline.tap_e5_evidence_assembly.validator import require_valid


def _v(x) -> str:
    return x.value if hasattr(x, "value") else ("" if x is None else str(x))


@dataclass(frozen=True)
class AssemblyConfig:
    name: str
    dedup: bool
    prune: bool
    full_closure: bool
    preserve_provenance: bool
    minimize: bool
    validate_freeze: bool
    description: str


BASELINES: Tuple[AssemblyConfig, ...] = (
    AssemblyConfig("A", False, False, True, False, False, False, "naive union"),
    AssemblyConfig("B", True, False, True, False, False, False, "deduplicate"),
    AssemblyConfig("C", True, True, False, False, False, False,
                   "dependency-aware (winner closure only)"),
    AssemblyConfig("D", True, True, True, False, False, False,
                   "dependency + full closure"),
    AssemblyConfig("E", True, True, True, True, False, False,
                   "dependency + provenance"),
    AssemblyConfig("F", True, True, True, True, True, True,
                   "full: dependency + provenance + minimization + validation"),
)


def config(name: str) -> AssemblyConfig:
    for c in BASELINES:
        if c.name == name:
            return c
    raise KeyError(name)


class EvidenceAssemblyLayer:
    def __init__(self, cfg: AssemblyConfig):
        self.cfg = cfg

    def assemble(self, intent: IntentRecord, retrieval: RetrievalRecord,
                 relationship: RelationshipRecord,
                 governance: GovernanceRecord) -> EvidencePacket:
        cfg = self.cfg
        trace: List[str] = ["validate_upstream"]
        require_valid(intent, retrieval, relationship, governance)

        # -- stage 2: import upstream records ---------------------------------
        trace.append("import_records")
        all_evidence = self._import_evidence(retrieval)            # unit_id -> PacketEvidence
        rel_objs, rel_by_subject = self._import_relationships(relationship)
        gov_objs, gov_supporting, gov_rejected_names = self._import_governance(
            governance, rel_by_subject)
        conflicts = self._import_conflicts(relationship, governance, rel_by_subject)
        gaps = self._import_gaps(retrieval, relationship, governance)

        # -- stage 3-6: dependency graph + reachable objects ------------------
        trace.append("build_dependency_graph")
        included_rel = set()
        for did, sup in gov_supporting.items():
            included_rel |= set(sup)
        if cfg.full_closure:
            for names in gov_rejected_names.values():
                for n in names:
                    aid = rel_by_subject.get(n)
                    if aid:
                        included_rel.add(aid)
            for c in conflicts:
                for m in c.member_ids:
                    if m in rel_objs:
                        included_rel.add(m)
                    aid = rel_by_subject.get(m)
                    if aid:
                        included_rel.add(aid)
        included_rel &= set(rel_objs)
        trace.append("collect_reachable_relationships")

        # evidence referenced by the included relationships
        ref_units: List[str] = []
        for aid in sorted(included_rel):
            ref_units.extend(rel_objs[aid].evidence_unit_ids)
        trace.append("collect_reachable_evidence")
        trace.append("collect_reachable_governance")
        trace.append("collect_conflicts")
        trace.append("collect_gaps")

        # -- stage 9: which evidence objects to carry -------------------------
        if cfg.prune:
            evidence_ids = [u for u in ref_units if u in all_evidence]
        else:
            # naive union: every retrieved unit + one per relationship use
            evidence_ids = list(all_evidence.keys()) + [u for u in ref_units
                                                        if u in all_evidence]
        if cfg.dedup:
            trace.append("deduplicate_references")
            evidence_ids = _dedupe_keep_order(evidence_ids)

        evidence_objs = tuple(all_evidence[u] for u in evidence_ids)
        rel_tuple = tuple(rel_objs[a] for a in sorted(included_rel))
        gov_tuple = tuple(gov_objs)

        # -- edges ------------------------------------------------------------
        edges = self._edges(intent.request_id, rel_tuple, gov_tuple,
                            {e.unit_id for e in evidence_objs})
        if cfg.dedup or cfg.minimize:
            edges = _dedupe_edges(edges)
        trace.append("dependency_integrity_verification")

        # -- stage 11: provenance ---------------------------------------------
        trace.append("provenance_verification")
        prov_index = (self._provenance_index(intent, evidence_objs, rel_tuple, gov_tuple)
                      if cfg.preserve_provenance else {})

        # -- stage 12: minimization (confidence summary) ----------------------
        conf_summary = self._confidence_summary(retrieval, relationship, governance,
                                                gov_tuple, minimal=cfg.minimize)
        if cfg.minimize:
            trace.append("packet_minimization")

        if cfg.validate_freeze:
            trace.append("packet_validation")
            trace.append("packet_freeze")

        return EvidencePacket(
            schema_version=SCHEMA_VERSION,
            packet_id=f"packet::{intent.request_id}::{cfg.name}",
            intent=PacketIntent(intent.request_id, intent.primary_objective,
                                _v(intent.task_type)),
            intent_record_id=intent.request_id,
            retrieval_record_id=retrieval.retrieval_id,
            relationship_record_id=relationship.relationship_record_id,
            governance_record_id=governance.governance_record_id,
            evidence_units=evidence_objs, relationships=rel_tuple,
            governance_decisions=gov_tuple, conflicts=conflicts, gaps=gaps,
            dependency_edges=edges, confidence_summary=conf_summary,
            provenance_index=prov_index, processing_trace=tuple(trace))

    # -- importers -----------------------------------------------------------
    def _import_evidence(self, retrieval: RetrievalRecord) -> Dict[str, PacketEvidence]:
        out: Dict[str, PacketEvidence] = {}
        for rank, cand in enumerate(retrieval.candidates):
            u = cand.unit
            p = cand.provenance
            out[u.unit_id] = PacketEvidence(
                unit_id=u.unit_id, source_id=_v(getattr(p, "source_id", u.doc_id)),
                source_location=_v(getattr(p, "source_location", u.location)),
                doc_type=_v(u.doc_type), authority_level=_v(u.authority),
                retrieval_rank=rank, retrieval_method=_v(p.retrieval_method),
                retrieval_score=float(cand.score),
                extraction_method=_v(p.extraction_method), confidence=float(cand.score))
        return out

    def _import_relationships(self, relationship: RelationshipRecord):
        rel: Dict[str, PacketRelationship] = {}
        by_subject: Dict[str, str] = {}
        for a in relationship.relationship_assertions:
            rel[a.assertion_id] = PacketRelationship(
                assertion_id=a.assertion_id, relationship_type=_v(a.relationship_type),
                direction=_v(a.direction), polarity=_v(a.polarity), modality=_v(a.modality),
                temporality=_v(a.temporality), valid_from=a.valid_from,
                valid_until=a.valid_until, scope=dict(a.scope),
                evidence_unit_ids=tuple(a.evidence_unit_ids),
                confidence_band=a.confidence_vector.band(), status=_v(a.status))
            by_subject.setdefault(a.normalized_subject, a.assertion_id)
        return rel, by_subject

    def _import_governance(self, governance: GovernanceRecord, rel_by_subject):
        objs: List[PacketGovernance] = []
        supporting: Dict[str, Tuple[str, ...]] = {}
        rejected_names: Dict[str, Tuple[str, ...]] = {}
        for d in governance.governing_authorities:
            rej = tuple(PacketRejectedAuthority(
                r.authority_name, _v(r.tier), r.reason,
                rel_by_subject.get(r.authority_name)) for r in d.rejected_relationships)
            objs.append(PacketGovernance(
                decision_id=d.decision_id, selected_authority=d.selected_authority,
                tier=_v(d.tier), status=_v(d.status),
                precedence_chain=tuple(d.precedence_chain), rejected_authorities=rej,
                exception_basis=tuple(d.exception_basis),
                temporal_basis=dict(d.temporal_basis), jurisdiction=dict(d.jurisdiction),
                scope=dict(d.scope),
                supporting_relationships=tuple(d.supporting_relationships),
                confidence=d.confidence.to_dict(),
                governance_record_id=governance.governance_record_id))
            supporting[d.decision_id] = tuple(d.supporting_relationships)
            rejected_names[d.decision_id] = tuple(r.authority_name
                                                  for r in d.rejected_relationships)
        return objs, supporting, rejected_names

    def _import_conflicts(self, relationship: RelationshipRecord,
                          governance: GovernanceRecord,
                          rel_by_subject) -> Tuple[PacketConflict, ...]:
        out: List[PacketConflict] = []
        for c in relationship.relationship_conflicts:
            out.append(PacketConflict(c.conflict_id, "E3", _v(c.conflict_type),
                                      tuple(c.assertion_ids), c.explanation, _v(c.status)))
        for c in governance.governance_conflicts:
            # translate E4 conflict authority names -> relationship ids (object ids), so a
            # packet conflict always references in-packet objects, not free-text names
            members = tuple(rel_by_subject.get(n, n) for n in c.authority_names)
            out.append(PacketConflict(c.conflict_id, "E4", _v(c.conflict_type),
                                      members, c.explanation, _v(c.status)))
        return tuple(out)

    def _import_gaps(self, retrieval, relationship,
                     governance) -> Tuple[PacketGap, ...]:
        out: List[PacketGap] = []
        for i, g in enumerate(retrieval.gaps):
            out.append(PacketGap(f"E2G{i}", "E2", _v(getattr(g, "gap_type", "")),
                                 getattr(g, "description", ""), {}))
        for i, g in enumerate(relationship.unresolved_relationship_gaps):
            out.append(PacketGap(f"E3G{i}", "E3", _v(g.gap_code), g.description,
                                 dict(g.detail)))
        for i, g in enumerate(governance.governance_gaps):
            out.append(PacketGap(f"E4G{i}", "E4", _v(g.gap_code), g.description,
                                 dict(g.detail)))
        return tuple(out)

    # -- edges / provenance / confidence -------------------------------------
    def _edges(self, intent_id, rels, govs, evidence_ids) -> Tuple[DependencyEdge, ...]:
        edges: List[DependencyEdge] = []
        for r in rels:
            for uid in r.evidence_unit_ids:
                if uid in evidence_ids:
                    edges.append(DependencyEdge(r.assertion_id, ObjectKind.RELATIONSHIP,
                                                uid, ObjectKind.EVIDENCE,
                                                EdgeType.SUPPORTED_BY_EVIDENCE))
        rel_ids = {r.assertion_id for r in rels}
        for g in govs:
            for aid in g.supporting_relationships:
                if aid in rel_ids:
                    edges.append(DependencyEdge(g.decision_id, ObjectKind.GOVERNANCE,
                                                aid, ObjectKind.RELATIONSHIP,
                                                EdgeType.SUPPORTED_BY_RELATIONSHIP))
            for rej in g.rejected_authorities:
                if rej.relationship_id and rej.relationship_id in rel_ids:
                    edges.append(DependencyEdge(g.decision_id, ObjectKind.GOVERNANCE,
                                                rej.relationship_id, ObjectKind.RELATIONSHIP,
                                                EdgeType.SUPPORTED_BY_RELATIONSHIP))
            edges.append(DependencyEdge(g.decision_id, ObjectKind.GOVERNANCE,
                                        intent_id, ObjectKind.INTENT,
                                        EdgeType.ANSWERS_INTENT))
        return tuple(edges)

    def _provenance_index(self, intent, evidence, rels, govs):
        idx: Dict[str, Dict[str, object]] = {
            intent.request_id: {"kind": "intent", "request_id": intent.request_id}}
        for e in evidence:
            idx[e.unit_id] = {"kind": "evidence", "source_id": e.source_id,
                              "source_location": e.source_location,
                              "retrieval_method": e.retrieval_method}
        for r in rels:
            idx[r.assertion_id] = {"kind": "relationship",
                                   "evidence_unit_ids": list(r.evidence_unit_ids)}
        for g in govs:
            idx[g.decision_id] = {"kind": "governance",
                                  "governance_record_id": g.governance_record_id,
                                  "supporting_relationships": list(g.supporting_relationships)}
        return idx

    def _confidence_summary(self, retrieval, relationship, governance, govs, minimal):
        summary: Dict[str, object] = {
            "governance_bands": {g.decision_id: g.confidence.get("provenance_completeness", 0.0)
                                 for g in govs},
            "governance_status": {g.decision_id: g.status for g in govs},
        }
        if not minimal:
            # downstream-unused raw upstream signals (removed by minimization)
            summary["raw_upstream_signals"] = {
                "retrieval_latency_ms": getattr(retrieval, "latency_ms", 0.0),
                "n_candidates": len(retrieval.candidates),
                "n_assertions": len(relationship.relationship_assertions),
                "governance_trace": list(governance.processing_trace),
            }
        return summary


def _dedupe_keep_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _dedupe_edges(edges: Tuple[DependencyEdge, ...]) -> Tuple[DependencyEdge, ...]:
    seen = set()
    out = []
    for e in edges:
        if e.key() not in seen:
            seen.add(e.key())
            out.append(e)
    return tuple(out)
