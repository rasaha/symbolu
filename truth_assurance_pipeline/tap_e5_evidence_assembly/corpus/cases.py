"""
TAP-E5 packet corpus (NEW, independently authored — not reused from any prior layer).

Each case is authored as a small governance scenario and compiled into the four frozen
upstream records (IntentRecord/RetrievalRecord/RelationshipRecord/GovernanceRecord) via
their public schemas. E5 then assembles those into an EvidencePacket. The upstream records
are authored fixtures (this study evaluates the *assembly/minimization* layer, not upstream
extraction — see LEAKAGE_AUDIT); the packet gold (the minimal complete set) is computed
independently of the assembler.

Families cover: single/multiple/shared/unused evidence, rejected authorities (minority
evidence), multiple governing authorities, E3 and E4 conflicts, multiple gaps, nested and
independent dependency trees, deep provenance, and minimal-packet edge cases.

Splits: dev (configuration selection) and eval (locked development evaluation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Set, Tuple

from truth_assurance_pipeline.tap_e1_intent import (
    IntentUnderstandingLayer, config as e1_config,
)
from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest
from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    AuthorityLevel, DocumentType, EvidenceProvenance, EvidenceUnit, ExtractionMethod,
    RetrievalMethod, stable_hash,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    GapType as E2GapType, RankedCandidate, RankingSignals, RetrievalConfidence,
    RetrievalGap, RetrievalQuery, RetrievalRecord,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import RelationshipType
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    AssertionStatus, Direction, EvidenceRole, Explicitness, Modality, Polarity,
    RelationshipAssertion, RelationshipConfidence, RelationshipConflict, RelationshipGap,
    SourceProvenance, Temporality, ConflictType as E3ConflictType, GapCode as E3GapCode,
)
from truth_assurance_pipeline.tap_e4_governance_truth.authority import AuthorityTier
from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    GovConflictType, GovGapCode, GovProvenance, GovStatus, GovernanceConfidence,
    GovernanceConflict, GovernanceGap, GovernanceRecord, GoverningDecision, RejectedAuthority,
)

SPLITS = ("dev", "eval")

_AUTH = {"regulatory": AuthorityLevel.REGULATORY, "official": AuthorityLevel.OFFICIAL_POLICY,
         "reference": AuthorityLevel.REFERENCE, "draft": AuthorityLevel.DRAFT,
         "deprecated": AuthorityLevel.DEPRECATED}
_DOC = {"policy": DocumentType.POLICY, "sop": DocumentType.SOP, "manual": DocumentType.MANUAL,
        "contract": DocumentType.CONTRACT, "regulatory": DocumentType.REGULATORY,
        "tech_spec": DocumentType.TECH_SPEC}
_TIER = {"law": AuthorityTier.LAW, "regulation": AuthorityTier.REGULATION,
         "corporate_policy": AuthorityTier.CORPORATE_POLICY, "sop": AuthorityTier.SOP,
         "unknown": AuthorityTier.UNKNOWN}


# ---- authoring spec --------------------------------------------------------

@dataclass(frozen=True)
class Ev:
    uid: str
    source: str
    doc_type: str = "policy"
    authority: str = "official"


@dataclass(frozen=True)
class Rel:
    rid: str
    subject: str
    obj: str
    evidence: Tuple[str, ...]


@dataclass(frozen=True)
class Gov:
    did: str
    authority: Optional[str]
    status: GovStatus
    tier: str
    supporting: Tuple[str, ...]
    rejected: Tuple[Tuple[str, str, str], ...] = ()   # (name, tier, reason)


@dataclass(frozen=True)
class Conf:
    cid: str
    origin: str                          # "E3" | "E4"
    members: Tuple[str, ...]             # E3: rids ; E4: authority names
    ctype: str
    explanation: str = "authored conflict"


@dataclass(frozen=True)
class Gap:
    origin: str                          # "E2" | "E3" | "E4"
    code: str
    description: str = "authored gap"


@dataclass(frozen=True)
class Case:
    case_id: str
    split: str
    family: str
    request_text: str
    evidences: Tuple[Ev, ...]
    relationships: Tuple[Rel, ...]
    governance: Tuple[Gov, ...]
    conflicts: Tuple[Conf, ...]
    gaps: Tuple[Gap, ...]

    # -- gold (independently computed minimal-complete set) -----------------
    def _rel_by_subject(self) -> Dict[str, str]:
        m: Dict[str, str] = {}
        for r in self.relationships:
            m.setdefault(r.subject, r.rid)
        return m

    def gold(self) -> Dict[str, object]:
        by_subj = self._rel_by_subject()
        req_rel: Set[str] = set()
        for g in self.governance:
            req_rel |= set(g.supporting)
            for (name, _t, _r) in g.rejected:
                if name in by_subj:
                    req_rel.add(by_subj[name])
        for c in self.conflicts:
            if c.origin == "E3":
                req_rel |= {m for m in c.members if m in {r.rid for r in self.relationships}}
            else:
                req_rel |= {by_subj[m] for m in c.members if m in by_subj}
        rel_ev = {r.rid: set(r.evidence) for r in self.relationships}
        req_ev: Set[str] = set()
        for rid in req_rel:
            req_ev |= rel_ev.get(rid, set())
        retrieved = {e.uid for e in self.evidences}
        removable_ev = retrieved - req_ev
        req_conf = {c.cid for c in self.conflicts}
        n_e2 = sum(1 for g in self.gaps if g.origin == "E2")
        n_e3 = sum(1 for g in self.gaps if g.origin == "E3")
        n_e4 = sum(1 for g in self.gaps if g.origin == "E4")
        req_gap = ({f"E2G{i}" for i in range(n_e2)} | {f"E3G{i}" for i in range(n_e3)}
                   | {f"E4G{i}" for i in range(n_e4)})
        return {"evidence": req_ev, "relationships": req_rel,
                "governance": {g.did for g in self.governance}, "conflicts": req_conf,
                "gaps": req_gap, "removable_evidence": removable_ev}

    def public_dict(self) -> Dict[str, object]:
        return {"case_id": self.case_id, "split": self.split, "family": self.family,
                "request_text": self.request_text,
                "n_evidence": len(self.evidences), "n_relationships": len(self.relationships),
                "n_governance": len(self.governance), "n_conflicts": len(self.conflicts),
                "n_gaps": len(self.gaps)}


_CASES: List[Case] = []


def _c(cid, split, family, text, evidences, relationships, governance,
       conflicts=(), gaps=()):
    _CASES.append(Case(cid, split, family, text, tuple(evidences), tuple(relationships),
                       tuple(governance), tuple(conflicts), tuple(gaps)))


# ---- record builders (compile a Case into the four upstream records) -------

_E1 = IntentUnderstandingLayer(e1_config("V4"))
_INTENT_CACHE: Dict[str, object] = {}


def build_intent(case: Case):
    if case.case_id not in _INTENT_CACHE:
        _INTENT_CACHE[case.case_id] = _E1.interpret(
            RawUserRequest(case.case_id, case.request_text))
    return _INTENT_CACHE[case.case_id]


def build_retrieval(case: Case) -> RetrievalRecord:
    cands = []
    for rank, e in enumerate(case.evidences):
        u = EvidenceUnit(unit_id=e.uid, doc_id=e.source, text=f"{e.uid} text",
                         location="s1", doc_type=_DOC[e.doc_type],
                         authority=_AUTH[e.authority], effective_year=2025,
                         entities=(e.uid,))
        prov = EvidenceProvenance(
            source_id=e.source, source_location="s1",
            retrieval_path=("candidate_retrieval", "provenance_attachment"),
            retrieval_method=RetrievalMethod.HYBRID, retrieval_score=1.0 - rank * 0.01,
            extraction_method=ExtractionMethod.SENTENCE_SPLIT)
        sig = RankingSignals(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0)
        cands.append(RankedCandidate(u, prov, sig, 1.0 - rank * 0.01))
    e2_gaps = tuple(RetrievalGap(getattr(E2GapType, g.code), g.description, {})
                    for g in case.gaps if g.origin == "E2")
    return RetrievalRecord(
        schema_version="tap-e2-retrieval/1.0.0", retrieval_id=f"ret::{case.case_id}",
        intent_ref=case.case_id, intent_objective=case.request_text,
        query=RetrievalQuery((), (), (), None, True), candidates=tuple(cands),
        confidence=RetrievalConfidence(1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
        gaps=e2_gaps, latency_ms=0.0)


def _rel_conf() -> RelationshipConfidence:
    return RelationshipConfidence(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


def build_relationship(case: Case):
    from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import ONTOLOGY_VERSION
    from truth_assurance_pipeline.tap_e3_relationship_truth.schema import RelationshipRecord
    rid = f"rel::{case.case_id}"
    ret_id = f"ret::{case.case_id}"
    asserts = []
    for r in case.relationships:
        prov = tuple(SourceProvenance(
            evidence_unit_id=u, source_id=u, source_location="s1",
            retrieval_record_id=ret_id, retrieval_rank=0, retrieval_method="hybrid",
            extraction_span=(0, 1), extraction_method="corpus_authored",
            role=EvidenceRole.PRIMARY_SUPPORT) for u in r.evidence)
        asserts.append(RelationshipAssertion(
            assertion_id=r.rid, subject=r.subject, predicate="governs", object=r.obj,
            normalized_subject=r.subject, normalized_predicate=RelationshipType.GOVERNS,
            normalized_object=r.obj, relationship_type=RelationshipType.GOVERNS,
            direction=Direction.SUBJECT_TO_OBJECT, polarity=Polarity.POSITIVE,
            modality=Modality.REQUIRED, temporality=Temporality.CURRENT, scope={},
            conditions=(), exceptions=(), explicitness=Explicitness.EXPLICIT,
            evidence_unit_ids=tuple(r.evidence), source_provenance=prov,
            extraction_method="corpus_authored", confidence_vector=_rel_conf(),
            ambiguities=(), conflicts=(), status=AssertionStatus.SUPPORTED))
    e3_conf = tuple(RelationshipConflict(
        conflict_id=c.cid, assertion_ids=tuple(c.members),
        conflict_type=getattr(E3ConflictType, c.ctype), scope_overlap=True,
        temporal_overlap=True, severity="HIGH", explanation=c.explanation)
        for c in case.conflicts if c.origin == "E3")
    e3_gaps = tuple(RelationshipGap(getattr(E3GapCode, g.code), g.description, {})
                    for g in case.gaps if g.origin == "E3")
    return RelationshipRecord(
        schema_version="tap-e3-relationship/1.0.0", ontology_version=ONTOLOGY_VERSION,
        relationship_record_id=rid, intent_record_id=case.case_id,
        retrieval_record_id=ret_id, created_at="N/A (deterministic run)",
        relationship_assertions=tuple(asserts), relationship_conflicts=e3_conf,
        unresolved_relationship_gaps=e3_gaps, provenance_summary={},
        confidence_summary={"band": "HIGH"}, processing_trace=("corpus_authored",))


def _gov_conf() -> GovernanceConfidence:
    return GovernanceConfidence(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


def build_governance(case: Case) -> GovernanceRecord:
    gid = f"gov::{case.case_id}"
    rel_id = f"rel::{case.case_id}"
    decisions = []
    for g in case.governance:
        rej = tuple(RejectedAuthority(name, _TIER.get(t, AuthorityTier.UNKNOWN), reason)
                    for (name, t, reason) in g.rejected)
        prov = tuple(GovProvenance(
            authority_name=g.authority or "", relationship_assertion_id=s,
            evidence_unit_id="", source_id=g.authority or "", source_location="s1",
            relationship_record_id=rel_id) for s in g.supporting)
        decisions.append(GoverningDecision(
            decision_id=g.did, selected_authority=g.authority,
            tier=_TIER.get(g.tier, AuthorityTier.UNKNOWN),
            selection_reason="authored", supporting_relationships=tuple(g.supporting),
            rejected_relationships=rej, precedence_chain=tuple(
                [g.authority] if g.authority else []) + tuple(n for (n, _t, _r) in g.rejected),
            jurisdiction={"jurisdiction": "us"}, scope={}, temporal_basis={},
            exception_basis=(), provenance=prov, confidence=_gov_conf(), status=g.status))
    e4_conf = tuple(GovernanceConflict(
        conflict_id=c.cid, conflict_type=getattr(GovConflictType, c.ctype),
        authority_names=tuple(c.members), explanation=c.explanation)
        for c in case.conflicts if c.origin == "E4")
    e4_gaps = tuple(GovernanceGap(getattr(GovGapCode, g.code), g.description, {})
                    for g in case.gaps if g.origin == "E4")
    return GovernanceRecord(
        schema_version="tap-e4-governance/1.0.0",
        authority_model_version="tap-e4-authority/1.0.0",
        governance_record_id=gid, intent_record_id=case.case_id,
        retrieval_record_id=f"ret::{case.case_id}", relationship_record_id=rel_id,
        created_at="N/A (deterministic run)",
        governing_authorities=tuple(decisions),
        governing_relationships=tuple(s for g in case.governance for s in g.supporting),
        governance_conflicts=e4_conf, governance_gaps=e4_gaps,
        confidence_vector=_gov_conf(), processing_trace=("authored",))


def build_records(case: Case):
    return (build_intent(case), build_retrieval(case), build_relationship(case),
            build_governance(case))


# =========================================================================== #
# cases                                                                       #
# =========================================================================== #

def _build_split(p: str, split: str) -> None:
    G = GovStatus

    _c(f"{p}01", split, "single", "Which policy governs refunds?",
       [Ev("u1", "doc-refund")],
       [Rel("r1", "refund policy", "refunds", ("u1",))],
       [Gov("d1", "refund policy", G.GOVERNING, "corporate_policy", ("r1",))])

    _c(f"{p}02", split, "multiple", "Which policies govern data handling?",
       [Ev("u1", "doc-a"), Ev("u2", "doc-b"), Ev("u3", "doc-c")],
       [Rel("r1", "data policy", "data", ("u1", "u2")),
        Rel("r2", "privacy policy", "pii", ("u3",))],
       [Gov("d1", "data policy", G.GOVERNING, "corporate_policy", ("r1", "r2"))])

    _c(f"{p}03", split, "shared_evidence", "Which rules cite the master standard?",
       [Ev("u1", "doc-standard")],
       [Rel("r1", "policy a", "x", ("u1",)), Rel("r2", "policy b", "y", ("u1",))],
       [Gov("d1", "policy a", G.GOVERNING, "corporate_policy", ("r1", "r2"))])

    _c(f"{p}04", split, "unused_evidence", "Which retention rule governs?",
       [Ev("u1", "doc-used"), Ev("u2", "doc-retrieved-unused")],
       [Rel("r1", "retention policy", "retention", ("u1",))],
       [Gov("d1", "retention policy", G.GOVERNING, "corporate_policy", ("r1",))])

    _c(f"{p}05", split, "rejected_authority", "Which authority governs disclosure?",
       [Ev("u1", "doc-law"), Ev("u2", "doc-contract")],
       [Rel("r1", "federal breach law", "disclosure", ("u1",)),
        Rel("r2", "vendor contract", "disclosure", ("u2",))],
       [Gov("d1", "federal breach law", G.GOVERNING, "law", ("r1",),
            (("vendor contract", "corporate_policy", "subordinate to law"),))])

    _c(f"{p}06", split, "multi_governing", "What governs access and logging?",
       [Ev("u1", "doc-access"), Ev("u2", "doc-logging")],
       [Rel("r1", "access policy", "access", ("u1",)),
        Rel("r2", "logging policy", "logging", ("u2",))],
       [Gov("d1", "access policy", G.GOVERNING, "corporate_policy", ("r1",)),
        Gov("d2", "logging policy", G.GOVERNING, "sop", ("r2",))])

    _c(f"{p}07", split, "e3_conflict", "How fast must the vendor notify?",
       [Ev("u1", "doc-24h"), Ev("u2", "doc-72h")],
       [Rel("r1", "contract a", "notify", ("u1",)),
        Rel("r2", "contract b", "notify", ("u2",))],
       [Gov("d1", "contract a", G.GOVERNING, "corporate_policy", ("r1",),
            (("contract b", "corporate_policy", "minority"),))],
       conflicts=[Conf("gc1", "E3", ("r1", "r2"), "VALUE_CONFLICT")])

    _c(f"{p}08", split, "e4_conflict", "Which retention period governs?",
       [Ev("u1", "doc-30"), Ev("u2", "doc-90")],
       [Rel("r1", "policy blue", "retention", ("u1",)),
        Rel("r2", "policy red", "retention", ("u2",))],
       [Gov("d1", None, G.CONFLICTED, "unknown", (),
            (("policy blue", "corporate_policy", "tie"),
             ("policy red", "corporate_policy", "tie")))],
       conflicts=[Conf("gc1", "E4", ("policy blue", "policy red"), "AUTHORITY_CONFLICT")])

    _c(f"{p}09", split, "multi_gap", "What governs cross-border transfer?",
       [Ev("u1", "doc-x")],
       [Rel("r1", "transfer policy", "transfer", ("u1",))],
       [Gov("d1", "transfer policy", G.GOVERNING, "corporate_policy", ("r1",))],
       gaps=[Gap("E2", "INSUFFICIENT_EVIDENCE"), Gap("E3", "AMBIGUOUS_PREDICATE"),
             Gap("E4", "AMBIGUOUS_JURISDICTION")])

    _c(f"{p}10", split, "nested", "What governs escalation and its exception?",
       [Ev("u1", "doc-esc"), Ev("u2", "doc-exc"), Ev("u3", "doc-orphan")],
       [Rel("r1", "escalation sop", "escalation", ("u1",)),
        Rel("r2", "exception memo", "escalation", ("u2",))],
       [Gov("d1", "escalation sop", G.GOVERNING_WITH_EXCEPTION, "sop", ("r1",),
            (("exception memo", "sop", "exception basis"),))])

    _c(f"{p}11", split, "deep_provenance", "Which regulation governs auditing?",
       [Ev("u1", "reg-src", "regulatory", "regulatory"),
        Ev("u2", "policy-src", "policy", "official")],
       [Rel("r1", "audit regulation", "audit", ("u1",)),
        Rel("r2", "audit policy", "audit", ("u2",))],
       [Gov("d1", "audit regulation", G.GOVERNING, "regulation", ("r1",),
            (("audit policy", "corporate_policy", "subordinate"),))])

    _c(f"{p}12", split, "minimal_edge", "Which single rule governs onboarding?",
       [Ev("u1", "doc-onboard")],
       [Rel("r1", "onboarding sop", "onboarding", ("u1",))],
       [Gov("d1", "onboarding sop", G.GOVERNING, "sop", ("r1",))])

    _c(f"{p}13", split, "unused_evidence", "Which security rule governs?",
       [Ev("u1", "doc-sec"), Ev("u2", "doc-unused-a"), Ev("u3", "doc-unused-b")],
       [Rel("r1", "security policy", "security", ("u1",))],
       [Gov("d1", "security policy", G.GOVERNING, "corporate_policy", ("r1",))])

    _c(f"{p}14", split, "rejected_authority", "Which rule governs vendor data?",
       [Ev("u1", "doc-reg"), Ev("u2", "doc-dept"), Ev("u3", "doc-draft", "policy", "draft")],
       [Rel("r1", "data regulation", "vendor data", ("u1",)),
        Rel("r2", "department policy", "vendor data", ("u2",)),
        Rel("r3", "draft policy", "vendor data", ("u3",))],
       [Gov("d1", "data regulation", G.GOVERNING, "regulation", ("r1",),
            (("department policy", "corporate_policy", "subordinate"),
             ("draft policy", "unknown", "draft not selectable")))])

    _c(f"{p}15", split, "e3_conflict", "What is the required backup interval?",
       [Ev("u1", "doc-daily"), Ev("u2", "doc-weekly"), Ev("u3", "doc-context")],
       [Rel("r1", "backup sop a", "backup", ("u1",)),
        Rel("r2", "backup sop b", "backup", ("u2",))],
       [Gov("d1", "backup sop a", G.GOVERNING, "sop", ("r1",),
            (("backup sop b", "sop", "minority"),))],
       conflicts=[Conf("gc1", "E3", ("r1", "r2"), "VALUE_CONFLICT")],
       gaps=[Gap("E3", "CONFLICTING_RELATIONSHIPS")])

    _c(f"{p}16", split, "independent_trees", "What governs billing and shipping?",
       [Ev("u1", "doc-bill"), Ev("u2", "doc-ship"), Ev("u3", "doc-ship-alt")],
       [Rel("r1", "billing policy", "billing", ("u1",)),
        Rel("r2", "shipping policy", "shipping", ("u2",)),
        Rel("r3", "shipping addendum", "shipping", ("u3",))],
       [Gov("d1", "billing policy", G.GOVERNING, "corporate_policy", ("r1",)),
        Gov("d2", "shipping policy", G.GOVERNING, "corporate_policy", ("r2",),
            (("shipping addendum", "corporate_policy", "minority"),))])


_build_split("E5D", "dev")
_build_split("E5E", "eval")

ALL_CASES: Tuple[Case, ...] = tuple(_CASES)


def cases_for_split(split: str) -> Tuple[Case, ...]:
    return tuple(c for c in ALL_CASES if c.split == split)


def eval_lock() -> Dict[str, object]:
    payload = [c.public_dict() for c in cases_for_split("eval")]
    return {"n_eval": len(payload), "eval_inputs_hash": stable_hash(payload)}


def manifest() -> Dict[str, object]:
    dist: Dict[str, int] = {}
    fam: Dict[str, int] = {}
    for c in ALL_CASES:
        dist[c.split] = dist.get(c.split, 0) + 1
        fam[c.family] = fam.get(c.family, 0) + 1
    return {"n_cases": len(ALL_CASES), "n_families": len(fam),
            "split_distribution": dist, "family_distribution": fam,
            "eval_lock": eval_lock()}
