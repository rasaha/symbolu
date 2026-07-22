"""
TAP-E3 relationship corpus (NEW, independently authored).

Each case owns one or more evidence units (built as TAP-E2 ``EvidenceUnit`` objects — a
frozen upstream structure used for interface compatibility, not modified) assembled into
a TAP-E2 ``RetrievalRecord`` that feeds TAP-E3. The relationship gold is newly authored
for this study; TAP-E2 query annotations are NOT reused as relationship gold.

Ground truth allows multiple acceptable normalized predicate forms
(``acceptable_predicates``) so ontology-equivalent representations are not penalized.

Splits: dev (development) and eval (locked development evaluation — see LEAKAGE_AUDIT).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

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
    Direction, Explicitness, GapCode, Modality, Polarity, Temporality,
)

SPLITS = ("dev", "eval")
RT = RelationshipType


@dataclass(frozen=True)
class GoldRel:
    subject: str                       # normalized (lower, no articles)
    predicate: RelationshipType
    object: str
    acceptable_predicates: Tuple[RelationshipType, ...] = ()
    direction: Direction = Direction.SUBJECT_TO_OBJECT
    polarity: Polarity = Polarity.POSITIVE
    modality: Modality = Modality.ASSERTED
    temporality: Temporality = Temporality.CURRENT
    scope: Mapping[str, str] = field(default_factory=dict)
    conditions: Tuple[str, ...] = ()
    exceptions: Tuple[str, ...] = ()
    explicitness: Explicitness = Explicitness.EXPLICIT
    evidence_unit_ids: Tuple[str, ...] = ()
    prohibited_predicates: Tuple[RelationshipType, ...] = ()

    def acceptable(self) -> Tuple[RelationshipType, ...]:
        return (self.predicate,) + self.acceptable_predicates


@dataclass(frozen=True)
class Case:
    case_id: str
    split: str
    request_text: str
    units: Tuple[EvidenceUnit, ...]
    upstream_gaps: Tuple[RetrievalGap, ...]
    gold: Tuple[GoldRel, ...]
    expected_conflicts: int
    expected_gaps: Tuple[GapCode, ...]
    family: str

    def public_dict(self) -> Dict[str, object]:
        return {"case_id": self.case_id, "split": self.split,
                "request_text": self.request_text,
                "units": [u.to_public_dict() for u in self.units]}


_CASES: List[Case] = []
_ALL_UNITS: List[EvidenceUnit] = []


def _u(uid, text, entities, dtype=DocumentType.POLICY, authority=AuthorityLevel.OFFICIAL_POLICY,
       year=2025):
    u = EvidenceUnit(unit_id=uid, doc_id=uid.split("#")[0], text=text,
                     location=uid.split("#")[1] if "#" in uid else "s1",
                     doc_type=dtype, authority=authority, effective_year=year,
                     entities=tuple(entities))
    _ALL_UNITS.append(u)
    return u


def build_retrieval_record(case: Case) -> RetrievalRecord:
    cands = []
    for rank, u in enumerate(case.units):
        prov = EvidenceProvenance(
            source_id=u.doc_id, source_location=u.location,
            retrieval_path=("candidate_retrieval", "provenance_attachment"),
            retrieval_method=RetrievalMethod.HYBRID, retrieval_score=1.0 - rank * 0.01,
            extraction_method=ExtractionMethod.SENTENCE_SPLIT)
        sig = RankingSignals(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0)
        cands.append(RankedCandidate(u, prov, sig, 1.0 - rank * 0.01))
    conf = RetrievalConfidence(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
    q = RetrievalQuery((), (), (), None, True)
    return RetrievalRecord(
        schema_version="tap-e2-retrieval/1.0.0",
        retrieval_id=f"ret::{case.case_id}", intent_ref=case.case_id,
        intent_objective=case.request_text, query=q, candidates=tuple(cands),
        confidence=conf, gaps=case.upstream_gaps, latency_ms=0.0)


def _c(cid, split, request_text, family, units, gold, *, upstream_gaps=(),
       expected_conflicts=0, expected_gaps=()):
    _CASES.append(Case(cid, split, request_text, tuple(units), tuple(upstream_gaps),
                       tuple(gold), expected_conflicts, tuple(expected_gaps), family))


# =========================================================================== #
# DEV                                                                         #
# =========================================================================== #

_c("E3D01", "dev", "What relationship does Acme have to System B?", "direct",
   [_u("DOC-OWN#s1", "Acme Corporation owns System B.", ["Acme Corporation", "System B"])],
   [GoldRel("acme corporation", RT.OWNS, "system b", evidence_unit_ids=("DOC-OWN#s1",))])

_c("E3D02", "dev", "Who operates System B?", "passive",
   [_u("DOC-OP#s1", "System B is operated by Acme Corporation.",
       ["System B", "Acme Corporation"])],
   [GoldRel("acme corporation", RT.OPERATES, "system b",
            evidence_unit_ids=("DOC-OP#s1",))])

_c("E3D03", "dev", "Can contractors access production?", "negation",
   [_u("DOC-NEG#s1", "Contractors are not authorized to access production systems.",
       ["Contractors", "production systems"], dtype=DocumentType.SOP)],
   [GoldRel("contractors", RT.PERMITTED_TO, "production systems",
            acceptable_predicates=(RT.PROHIBITED_FROM,), polarity=Polarity.NEGATED,
            modality=Modality.PERMITTED, scope={"environment": "production", "user_role": "contractors"},
            evidence_unit_ids=("DOC-NEG#s1",),
            prohibited_predicates=())])

_c("E3D04", "dev", "May vendors access the portal?", "modality_may",
   [_u("DOC-MAY#s1", "Vendors may access the partner portal.",
       ["Vendors", "partner portal"])],
   [GoldRel("vendors", RT.PERMITTED_TO, "partner portal", modality=Modality.PERMITTED,
            evidence_unit_ids=("DOC-MAY#s1",))])

_c("E3D05", "dev", "Must vendors access the portal?", "modality_must",
   [_u("DOC-MUST#s1", "Vendors must access the partner portal.",
       ["Vendors", "partner portal"])],
   [GoldRel("vendors", RT.PERMITTED_TO, "partner portal", modality=Modality.REQUIRED,
            acceptable_predicates=(RT.OBLIGATED_TO,), evidence_unit_ids=("DOC-MUST#s1",))])

_c("E3D06", "dev", "When must support escalate?", "conditional",
   [_u("DOC-COND#s1", "Support must escalate the incident if severity is critical.",
       ["Support", "incident"], dtype=DocumentType.SOP)],
   [GoldRel("support", RT.OBLIGATED_TO, "incident", modality=Modality.REQUIRED,
            conditions=("severity is critical",), evidence_unit_ids=("DOC-COND#s1",))])

_c("E3D07", "dev", "Who is exempt from MFA?", "exception",
   [_u("DOC-EXC#s1", "All staff must use MFA except break-glass administrators.",
       ["staff", "MFA"], dtype=DocumentType.SOP)],
   [GoldRel("staff", RT.USES, "mfa", modality=Modality.REQUIRED,
            exceptions=("break-glass administrators",), evidence_unit_ids=("DOC-EXC#s1",))])

_c("E3D08", "dev", "Which policy is current?", "supersession",
   [_u("DOC-SUP#s1", "Policy B supersedes Policy A from June 1 2025.",
       ["Policy B", "Policy A"], dtype=DocumentType.POLICY)],
   [GoldRel("policy b", RT.SUPERSEDES, "policy a", acceptable_predicates=(RT.REPLACES,),
            evidence_unit_ids=("DOC-SUP#s1",))])

_c("E3D09", "dev", "How fast must the vendor notify us?", "conflict_value",
   [_u("DOC-N1#s1", "The vendor must notify the customer within 24 hours.",
       ["vendor", "customer"], dtype=DocumentType.CONTRACT),
    _u("DOC-N2#s1", "The vendor must notify the customer within 72 hours.",
       ["vendor", "customer"], dtype=DocumentType.CONTRACT)],
   [GoldRel("vendor", RT.REPORTS, "customer", acceptable_predicates=(RT.OBLIGATED_TO,),
            modality=Modality.REQUIRED, scope={"value": "24 hours"},
            evidence_unit_ids=("DOC-N1#s1",)),
    GoldRel("vendor", RT.REPORTS, "customer", acceptable_predicates=(RT.OBLIGATED_TO,),
            modality=Modality.REQUIRED, scope={"value": "72 hours"},
            evidence_unit_ids=("DOC-N2#s1",))],
   expected_conflicts=1)

_c("E3D10", "dev", "Are Acme and Product X related?", "cooccurrence",
   [_u("DOC-CO#s1", "Acme Corporation and Product X are both discussed in the quarterly report.",
       ["Acme Corporation", "Product X"], dtype=DocumentType.MANUAL)],
   [],  # NO relationship is established
   expected_gaps=(GapCode.NO_RELATIONSHIP_ESTABLISHED,))

_c("E3D11", "dev", "Did Vendor A cause the outage?", "attribution",
   [_u("DOC-ALL#s1", "The audit report alleges that Vendor A caused the outage.",
       ["Vendor A", "outage"], dtype=DocumentType.MANUAL)],
   [GoldRel("vendor a", RT.CAUSES, "outage", modality=Modality.ALLEGED,
            evidence_unit_ids=("DOC-ALL#s1",))])

_c("E3D12", "dev", "What does Acme own and license?", "coordinated",
   [_u("DOC-COORD#s1", "Acme owns Platform B and licenses Module C to Vendor D.",
       ["Acme", "Platform B", "Module C", "Vendor D"])],
   [GoldRel("acme", RT.OWNS, "platform b", evidence_unit_ids=("DOC-COORD#s1",)),
    GoldRel("acme", RT.LICENSES, "module c", evidence_unit_ids=("DOC-COORD#s1",))])

_c("E3D13", "dev", "What is the dependency history?", "historical",
   [_u("DOC-HIST#s1", "System A previously depended on Library B but now uses Library C.",
       ["System A", "Library B", "Library C"], dtype=DocumentType.DESIGN_DOC)],
   [GoldRel("system a", RT.DEPENDS_ON, "library b", temporality=Temporality.HISTORICAL,
            evidence_unit_ids=("DOC-HIST#s1",)),
    GoldRel("system a", RT.USES, "library c", temporality=Temporality.CURRENT,
            evidence_unit_ids=("DOC-HIST#s1",))])

_c("E3D14", "dev", "Does Acme own Product X?", "distributes_not_owns",
   [_u("DOC-DIST#s1", "Acme distributes Product X in Europe.",
       ["Acme", "Product X"], dtype=DocumentType.CONTRACT)],
   [GoldRel("acme", RT.DISTRIBUTES, "product x", scope={"geography": "europe"},
            prohibited_predicates=(RT.OWNS,), evidence_unit_ids=("DOC-DIST#s1",))])

_c("E3D15", "dev", "Where is Service X hosted?", "hosted",
   [_u("DOC-HOST#s1", "Service X is hosted on Cluster Z.",
       ["Service X", "Cluster Z"], dtype=DocumentType.TECH_SPEC)],
   [GoldRel("service x", RT.HOSTED_ON, "cluster z", evidence_unit_ids=("DOC-HOST#s1",))])

_c("E3D16", "dev", "What is the scope of Policy A?", "scope",
   [_u("DOC-SCOPE#s1", "Policy A applies to European employees only.",
       ["Policy A", "European employees"], dtype=DocumentType.POLICY)],
   [GoldRel("policy a", RT.APPLIES_TO, "european employees",
            scope={"geography": "european"}, evidence_unit_ids=("DOC-SCOPE#s1",))])

_c("E3D17", "dev", "Who owns System B (duplicated across sources)?", "duplicate",
   [_u("DOC-DUP1#s1", "Acme Corporation owns System B.", ["Acme Corporation", "System B"]),
    _u("DOC-DUP2#s1", "Acme Corporation owns System B.", ["Acme Corporation", "System B"])],
   [GoldRel("acme corporation", RT.OWNS, "system b",
            evidence_unit_ids=("DOC-DUP1#s1", "DOC-DUP2#s1"))])

# =========================================================================== #
# EVAL (locked development evaluation)                                        #
# =========================================================================== #

_c("E3E01", "eval", "What does Globex own?", "direct",
   [_u("DOC-OWN2#s1", "Globex Industries owns the Helios Platform.",
       ["Globex Industries", "Helios Platform"])],
   [GoldRel("globex industries", RT.OWNS, "helios platform",
            evidence_unit_ids=("DOC-OWN2#s1",))])

_c("E3E02", "eval", "Who manages the Helios Platform?", "passive",
   [_u("DOC-OP2#s1", "The Helios Platform is managed by Globex Industries.",
       ["Helios Platform", "Globex Industries"])],
   [GoldRel("globex industries", RT.MANAGES, "helios platform",
            evidence_unit_ids=("DOC-OP2#s1",))])

_c("E3E03", "eval", "Can interns reach customer data?", "negation",
   [_u("DOC-NEG2#s1", "Interns are prohibited from accessing customer data.",
       ["Interns", "customer data"], dtype=DocumentType.SOP)],
   [GoldRel("interns", RT.PROHIBITED_FROM, "customer data", polarity=Polarity.POSITIVE,
            acceptable_predicates=(RT.PROHIBITS,), evidence_unit_ids=("DOC-NEG2#s1",))])

_c("E3E04", "eval", "Should engineers review the design?", "modality_should",
   [_u("DOC-SHOULD#s1", "Engineers should review the design document.",
       ["Engineers", "design document"], dtype=DocumentType.SOP)],
   [GoldRel("engineers", RT.USES, "design document", modality=Modality.RECOMMENDED,
            acceptable_predicates=(RT.REFERENCES, RT.DESCRIBES),
            evidence_unit_ids=("DOC-SHOULD#s1",))])

_c("E3E05", "eval", "What authorization conflict exists for administrators?", "conflict_ontology",
   [_u("DOC-AUTH1#s1", "Policy A authorizes administrators.",
       ["Policy A", "administrators"], dtype=DocumentType.POLICY),
    _u("DOC-AUTH2#s1", "Policy B prohibits administrators.",
       ["Policy B", "administrators"], dtype=DocumentType.POLICY)],
   [GoldRel("policy a", RT.AUTHORIZED_BY, "administrators",
            acceptable_predicates=(RT.PERMITTED_TO,), evidence_unit_ids=("DOC-AUTH1#s1",)),
    GoldRel("policy b", RT.PROHIBITS, "administrators",
            acceptable_predicates=(RT.PROHIBITED_FROM,), evidence_unit_ids=("DOC-AUTH2#s1",))],
   expected_conflicts=1)

_c("E3E06", "eval", "What does Service X depend on?", "direct",
   [_u("DOC-DEP#s1", "Service X depends on Database Y.",
       ["Service X", "Database Y"], dtype=DocumentType.TECH_SPEC)],
   [GoldRel("service x", RT.DEPENDS_ON, "database y", evidence_unit_ids=("DOC-DEP#s1",))])

_c("E3E07", "eval", "Is Module C part of Platform B?", "structural",
   [_u("DOC-PART#s1", "Module C is part of Platform B.",
       ["Module C", "Platform B"], dtype=DocumentType.TECH_SPEC)],
   [GoldRel("module c", RT.PART_OF, "platform b", evidence_unit_ids=("DOC-PART#s1",))])

_c("E3E08", "eval", "What does the standard require?", "governance",
   [_u("DOC-REQ#s1", "The security standard requires multi-factor authentication.",
       ["security standard", "multi-factor authentication"], dtype=DocumentType.REGULATORY,
       authority=AuthorityLevel.REGULATORY)],
   [GoldRel("security standard", RT.REQUIRES, "multi-factor authentication",
            evidence_unit_ids=("DOC-REQ#s1",))])

_c("E3E09", "eval", "What relationship is stated between Acme and the outage?", "cooccurrence",
   [_u("DOC-CO2#s1", "Acme and the outage are mentioned together in the same paragraph.",
       ["Acme", "outage"], dtype=DocumentType.MANUAL)],
   [], expected_gaps=(GapCode.NO_RELATIONSHIP_ESTABLISHED,))

_c("E3E10", "eval", "Does the vendor license or distribute Product Q?", "distributes_not_owns",
   [_u("DOC-DIST2#s1", "The reseller distributes Product Q under a regional agreement.",
       ["reseller", "Product Q"], dtype=DocumentType.CONTRACT)],
   [GoldRel("reseller", RT.DISTRIBUTES, "product q", prohibited_predicates=(RT.OWNS,),
            evidence_unit_ids=("DOC-DIST2#s1",))])

_c("E3E11", "eval", "What can we establish about Widget Z given weak retrieval?", "upstream_gap",
   [_u("DOC-WEAK#s1", "Widget Z is referenced in a marketing brief.",
       ["Widget Z"], dtype=DocumentType.MANUAL, authority=AuthorityLevel.DRAFT)],
   [],
   upstream_gaps=(RetrievalGap(E2GapType.INSUFFICIENT_EVIDENCE, "insufficient upstream evidence"),),
   expected_gaps=(GapCode.INSUFFICIENT_RETRIEVAL_EVIDENCE,))

_c("E3E12", "eval", "What is the future applicability of Policy C?", "future",
   [_u("DOC-FUT#s1", "Policy C will apply to all vendors from January 2027.",
       ["Policy C", "vendors"], dtype=DocumentType.POLICY, year=2026)],
   [GoldRel("policy c", RT.APPLIES_TO, "vendors", temporality=Temporality.FUTURE,
            evidence_unit_ids=("DOC-FUT#s1",))])


ALL_CASES: Tuple[Case, ...] = tuple(_CASES)
ALL_UNITS: Tuple[EvidenceUnit, ...] = tuple(_ALL_UNITS)


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
    return {"n_cases": len(ALL_CASES), "n_evidence_units": len(ALL_UNITS),
            "split_distribution": dist, "family_distribution": fam,
            "units_hash": stable_hash([u.to_public_dict() for u in ALL_UNITS]),
            "eval_lock": eval_lock()}
