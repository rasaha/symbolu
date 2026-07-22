"""
TAP-E4 governance corpus (NEW, independently authored).

Each case describes a governance SITUATION and one or more candidate authorities
(``PolicySpec``). From the specs the builders synthesize:

  * a TAP-E2 ``RetrievalRecord`` (frozen upstream structure) — one ``EvidenceUnit`` per
    spec, carrying the document type + authority level that fixes its governance tier;
  * a TAP-E3 ``RelationshipRecord`` (frozen upstream structure) — one governance
    ``RelationshipAssertion`` per spec (GOVERNS/REQUIRES/…), plus SUPERSEDES and EXEMPTS
    assertions, with every governance attribute placed in the assertion ``scope`` map.

The relationship inputs are authored to be already-perfect (upstream confidence 1.0): this
study evaluates the GOVERNANCE resolution layer, not upstream extraction. Ground truth
(``expected_authority``/``expected_status``/disqualifiers) is newly authored here; no
upstream gold is reused.

Splits: ``dev`` (development / configuration selection) and ``eval`` (locked development
evaluation — inspected during iteration; see LEAKAGE_AUDIT, not a blind holdout).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.evidence_unit import (
    AuthorityLevel, DocumentType, EvidenceProvenance, EvidenceUnit, ExtractionMethod,
    RetrievalMethod, stable_hash,
)
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    RankedCandidate, RankingSignals, RetrievalConfidence, RetrievalQuery, RetrievalRecord,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import RelationshipType
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    AssertionStatus, Direction, EvidenceRole, Explicitness, Modality, Polarity,
    RelationshipAssertion, RelationshipConfidence, RelationshipGap, RelationshipRecord,
    SourceProvenance, Temporality, GapCode as E3GapCode,
)
from truth_assurance_pipeline.tap_e4_governance_truth.applicability import Situation
from truth_assurance_pipeline.tap_e4_governance_truth.schema import GovGapCode, GovStatus

RT = RelationshipType
SPLITS = ("dev", "eval")

# authority-level / doc-type shorthands (values are the frozen upstream enum values)
LAW = ("official", "regulatory", "law")            # (authority_level, doc_type, explicit_tier)
REGULATION = ("regulatory", "regulatory", "")
CORPORATE = ("official", "policy", "corporate_policy")
DEPARTMENT = ("official", "policy", "department_policy")
SOP = ("official", "sop", "")
CONTRACT = ("official", "contract", "")
DRAFT = ("draft", "policy", "")


@dataclass(frozen=True)
class PolicySpec:
    name: str                              # normalized authority name (lower-case)
    governs: str                           # normalized object the authority governs
    kind: Tuple[str, str, str] = CORPORATE  # (authority_level, doc_type, explicit_tier)
    predicate: RelationshipType = RT.GOVERNS
    jurisdiction: str = ""
    user_role: str = ""
    environment: str = ""
    version: str = ""
    obligation_value: str = ""             # obligation content (drives conflict detection)
    temporality: Temporality = Temporality.CURRENT
    valid_from: str = ""
    valid_until: str = ""
    is_emergency: bool = False
    disqualifier: str = ""                 # "" selectable | expired|superseded|draft|
    #                                        wrong_jurisdiction|out_of_scope|future
    gold_winner: bool = False

    @property
    def unit_id(self) -> str:
        return f"U-{self.name.replace(' ', '_')}"


@dataclass(frozen=True)
class Case:
    case_id: str
    split: str
    family: str
    request_text: str
    situation: Situation
    policies: Tuple[PolicySpec, ...]
    supersessions: Tuple[Tuple[str, str], ...]   # (new_name, old_name)
    exemptions: Tuple[Tuple[str, str], ...]      # (rule_name, exempted_role)
    expected_authority: Optional[str]
    expected_status: GovStatus
    expected_conflicts: int
    expected_gaps: Tuple[GovGapCode, ...]
    upstream_gaps: Tuple[RelationshipGap, ...]

    # --- gold helpers ------------------------------------------------------
    def disqualified(self, kind: str) -> frozenset:
        return frozenset(p.name for p in self.policies if p.disqualifier == kind)

    def gold_spec(self) -> Optional[PolicySpec]:
        for p in self.policies:
            if p.gold_winner:
                return p
        return None

    def public_dict(self) -> Dict[str, object]:
        return {"case_id": self.case_id, "split": self.split, "family": self.family,
                "request_text": self.request_text,
                "situation": self.situation.as_map(),
                "policies": [p.name for p in self.policies]}


_CASES: List[Case] = []
_ALL_UNITS: List[EvidenceUnit] = []


# --------------------------------------------------------------------------- #
# builders                                                                     #
# --------------------------------------------------------------------------- #

_AUTH = {"regulatory": AuthorityLevel.REGULATORY, "official": AuthorityLevel.OFFICIAL_POLICY,
         "reference": AuthorityLevel.REFERENCE, "draft": AuthorityLevel.DRAFT,
         "deprecated": AuthorityLevel.DEPRECATED}
_DOC = {"policy": DocumentType.POLICY, "sop": DocumentType.SOP, "manual": DocumentType.MANUAL,
        "api_doc": DocumentType.API_DOC, "contract": DocumentType.CONTRACT,
        "tech_spec": DocumentType.TECH_SPEC, "design_doc": DocumentType.DESIGN_DOC,
        "regulatory": DocumentType.REGULATORY}


def _perfect_conf() -> RelationshipConfidence:
    return RelationshipConfidence(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0)


def _year(spec: PolicySpec) -> int:
    for s in (spec.valid_from, spec.valid_until):
        for tok in (s or "").split():
            if tok.isdigit() and len(tok) == 4:
                return int(tok)
    return 2025


def _units(case: Case) -> Dict[str, EvidenceUnit]:
    units: Dict[str, EvidenceUnit] = {}
    for p in case.policies:
        auth_level, doc_type, _ = p.kind
        u = EvidenceUnit(
            unit_id=p.unit_id, doc_id=p.unit_id, text=f"{p.name} governs {p.governs}.",
            location="s1", doc_type=_DOC[doc_type], authority=_AUTH[auth_level],
            effective_year=_year(p), entities=(p.name, p.governs))
        units[p.unit_id] = u
        if u not in _ALL_UNITS:
            _ALL_UNITS.append(u)
    return units


def build_retrieval_record(case: Case) -> RetrievalRecord:
    units = _units(case)
    cands = []
    for rank, p in enumerate(case.policies):
        u = units[p.unit_id]
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
        schema_version="tap-e2-retrieval/1.0.0", retrieval_id=f"ret::{case.case_id}",
        intent_ref=case.case_id, intent_objective=case.request_text, query=q,
        candidates=tuple(cands), confidence=conf, gaps=(), latency_ms=0.0)


def _assertion(aid: str, subj: str, pred: RelationshipType, obj: str,
               scope: Mapping[str, str], unit_id: str, retrieval_id: str,
               relationship_id: str, temporality: Temporality = Temporality.CURRENT,
               valid_from: Optional[str] = None, valid_until: Optional[str] = None,
               modality: Modality = Modality.REQUIRED) -> RelationshipAssertion:
    prov = SourceProvenance(
        evidence_unit_id=unit_id, source_id=unit_id, source_location="s1",
        retrieval_record_id=retrieval_id, retrieval_rank=0, retrieval_method="hybrid",
        extraction_span=(0, 1), extraction_method="corpus_authored",
        role=EvidenceRole.PRIMARY_SUPPORT)
    return RelationshipAssertion(
        assertion_id=aid, subject=subj, predicate=pred.value, object=obj,
        normalized_subject=subj, normalized_predicate=pred, normalized_object=obj,
        relationship_type=pred, direction=Direction.SUBJECT_TO_OBJECT,
        polarity=Polarity.POSITIVE, modality=modality, temporality=temporality,
        scope=dict(scope), conditions=(), exceptions=(), explicitness=Explicitness.EXPLICIT,
        evidence_unit_ids=(unit_id,), source_provenance=(prov,),
        extraction_method="corpus_authored", confidence_vector=_perfect_conf(),
        ambiguities=(), conflicts=(), status=AssertionStatus.SUPPORTED,
        valid_from=valid_from or None, valid_until=valid_until or None)


def build_relationship_record(case: Case) -> RelationshipRecord:
    rid = f"rel::{case.case_id}"
    ret_id = f"ret::{case.case_id}"
    asserts: List[RelationshipAssertion] = []
    for i, p in enumerate(case.policies):
        _, doc_type, explicit_tier = p.kind
        scope = {"jurisdiction": p.jurisdiction, "user_role": p.user_role,
                 "environment": p.environment, "version": p.version,
                 "value": p.obligation_value, "tier": explicit_tier,
                 "emergency": "true" if p.is_emergency else ""}
        asserts.append(_assertion(
            f"A{i}", p.name, p.predicate, p.governs, scope, p.unit_id, ret_id, rid,
            temporality=p.temporality, valid_from=p.valid_from, valid_until=p.valid_until))
    n = len(asserts)
    for j, (new, old) in enumerate(case.supersessions):
        asserts.append(_assertion(f"S{j}", new, RT.SUPERSEDES, old, {}, _uid(case, new),
                                  ret_id, rid, modality=Modality.ASSERTED))
    for k, (rule, role) in enumerate(case.exemptions):
        asserts.append(_assertion(f"E{k}", rule, RT.EXEMPTS, role, {}, _uid(case, rule),
                                  ret_id, rid, modality=Modality.ASSERTED))
    return RelationshipRecord(
        schema_version="tap-e3-relationship/1.0.0",
        ontology_version=_ontology_version(), relationship_record_id=rid,
        intent_record_id=case.case_id, retrieval_record_id=ret_id,
        created_at="N/A (deterministic run)", relationship_assertions=tuple(asserts),
        relationship_conflicts=(), unresolved_relationship_gaps=case.upstream_gaps,
        provenance_summary={"n_assertions": n}, confidence_summary={"band": "HIGH"},
        processing_trace=("corpus_authored",))


def _uid(case: Case, name: str) -> str:
    for p in case.policies:
        if p.name == name:
            return p.unit_id
    return f"U-{name.replace(' ', '_')}"


def _ontology_version() -> str:
    from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import ONTOLOGY_VERSION
    return ONTOLOGY_VERSION


def _sit(**kw) -> Situation:
    return Situation(**kw)


def _case(cid, split, family, request_text, situation, policies, expected_authority,
          expected_status, *, supersessions=(), exemptions=(), expected_conflicts=0,
          expected_gaps=(), upstream_gaps=()):
    _CASES.append(Case(cid, split, family, request_text, situation, tuple(policies),
                       tuple(supersessions), tuple(exemptions), expected_authority,
                       expected_status, expected_conflicts, tuple(expected_gaps),
                       tuple(upstream_gaps)))


def _build_split(prefix: str, split: str) -> None:
    # 1. basic — a single applicable authority governs.
    _case(f"{prefix}01", split, "basic", "Which policy governs refunds?",
          _sit(jurisdiction="us", user_role="agent"),
          [PolicySpec("acme refund policy", "refunds", CORPORATE, jurisdiction="us",
                      user_role="agent", gold_winner=True)],
          "acme refund policy", GovStatus.GOVERNING)

    # 2. jurisdiction — same tier; only the in-jurisdiction one governs.
    _case(f"{prefix}02", split, "jurisdiction", "Which privacy policy governs US data?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("zeta eu privacy policy", "data", CORPORATE, jurisdiction="eu",
                      disqualifier="wrong_jurisdiction"),
           PolicySpec("acme us privacy policy", "data", CORPORATE, jurisdiction="us",
                      gold_winner=True)],
          "acme us privacy policy", GovStatus.GOVERNING)

    # 3. scope — same tier; only the matching-role one governs.
    _case(f"{prefix}03", split, "scope", "Which access policy governs engineers?",
          _sit(jurisdiction="us", user_role="engineers"),
          [PolicySpec("zeta contractor policy", "access", CORPORATE, user_role="contractors",
                      disqualifier="out_of_scope"),
           PolicySpec("acme engineer policy", "access", CORPORATE, user_role="engineers",
                      gold_winner=True)],
          "acme engineer policy", GovStatus.GOVERNING)

    # 4. expired — an expired policy must never be selected.
    _case(f"{prefix}04", split, "expired", "Which retention policy governs now?",
          _sit(jurisdiction="us", user_role="staff", date_year=2026),
          [PolicySpec("zeta retention policy", "retention", CORPORATE, jurisdiction="us",
                      valid_from="2015", valid_until="2020", disqualifier="expired"),
           PolicySpec("acme retention policy", "retention", CORPORATE, jurisdiction="us",
                      valid_from="2021", valid_until="2030", gold_winner=True)],
          "acme retention policy", GovStatus.GOVERNING)

    # 5. superseded — the superseded policy must never be selected.
    _case(f"{prefix}05", split, "superseded", "Which data policy is controlling?",
          _sit(jurisdiction="us", user_role="staff", date_year=2026),
          [PolicySpec("yankee data policy", "data", CORPORATE, jurisdiction="us",
                      disqualifier="superseded"),
           PolicySpec("delta data policy", "data", CORPORATE, jurisdiction="us",
                      gold_winner=True)],
          "delta data policy", GovStatus.GOVERNING,
          supersessions=(("delta data policy", "yankee data policy"),))

    # 6. future — a not-yet-effective policy must never be selected today.
    _case(f"{prefix}06", split, "future", "Which vendor policy applies this year?",
          _sit(jurisdiction="us", user_role="staff", date_year=2026),
          [PolicySpec("zulu vendor policy", "vendors", CORPORATE, jurisdiction="us",
                      temporality=Temporality.FUTURE, valid_from="2030",
                      disqualifier="future"),
           PolicySpec("alpha vendor policy", "vendors", CORPORATE, jurisdiction="us",
                      valid_from="2020", gold_winner=True)],
          "alpha vendor policy", GovStatus.GOVERNING)

    # 7. version — the most recent version governs (same tier).
    _case(f"{prefix}07", split, "version", "Which metrics policy version governs?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("bravo metrics policy", "metrics", CORPORATE, jurisdiction="us",
                      version="v1", disqualifier="out_of_scope"),
           PolicySpec("alpha metrics policy", "metrics", CORPORATE, jurisdiction="us",
                      version="v2", gold_winner=True)],
          "alpha metrics policy", GovStatus.GOVERNING)

    # 8. draft — a draft is never selectable even if it appears first.
    _case(f"{prefix}08", split, "draft", "Which security policy governs?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("draft security policy", "security", DRAFT, jurisdiction="us",
                      disqualifier="draft"),
           PolicySpec("approved security policy", "security", CORPORATE, jurisdiction="us",
                      gold_winner=True)],
          "approved security policy", GovStatus.GOVERNING)

    # 9. customer_override — a customer contract overrides a corporate policy of equal tier.
    _case(f"{prefix}09", split, "customer_override", "What notification obligation governs?",
          _sit(jurisdiction="us", user_role="staff", contract="acme msa"),
          [PolicySpec("zeta internal policy", "notification", CORPORATE, jurisdiction="us",
                      obligation_value="72 hours"),
           PolicySpec("acme service agreement", "notification", CONTRACT, jurisdiction="us",
                      obligation_value="24 hours", gold_winner=True)],
          "acme service agreement", GovStatus.GOVERNING)

    # 10. emergency_override — an emergency procedure overrides the normal SOP in an emergency.
    _case(f"{prefix}10", split, "emergency_override", "Which procedure governs the incident?",
          _sit(jurisdiction="us", user_role="operator", environment="emergency"),
          [PolicySpec("zeta standard procedure", "incident", SOP, jurisdiction="us",
                      obligation_value="standard"),
           PolicySpec("alpha emergency procedure", "incident", SOP, jurisdiction="us",
                      obligation_value="expedited", is_emergency=True, gold_winner=True)],
          "alpha emergency procedure", GovStatus.GOVERNING)

    # 11. law_supremacy — a law governs; a contract may NOT override it.
    _case(f"{prefix}11", split, "law_supremacy", "What governs breach disclosure?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("acme vendor contract", "disclosure", CONTRACT, jurisdiction="us",
                      obligation_value="optional"),
           PolicySpec("federal breach law", "disclosure", LAW, jurisdiction="us",
                      obligation_value="mandatory", gold_winner=True)],
          "federal breach law", GovStatus.GOVERNING)

    # 12. exception — an exempted role is not governed by the general obligation.
    _case(f"{prefix}12", split, "exception", "Does MFA govern break-glass admins?",
          _sit(jurisdiction="us", user_role="break-glass-admin"),
          [PolicySpec("mfa requirement", "authentication", SOP, jurisdiction="us",
                      user_role="staff", predicate=RT.REQUIRES)],
          None, GovStatus.GOVERNING_WITH_EXCEPTION,
          exemptions=(("mfa requirement", "break-glass-admin"),))

    # 13. conflict — two equal-precedence authorities, incompatible obligations, no resolver.
    _case(f"{prefix}13", split, "conflict", "What retention period governs?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("policy blue", "retention", CORPORATE, jurisdiction="us",
                      obligation_value="30 days"),
           PolicySpec("policy red", "retention", CORPORATE, jurisdiction="us",
                      obligation_value="90 days")],
          None, GovStatus.CONFLICTED, expected_conflicts=1,
          expected_gaps=(GovGapCode.CONFLICTING_AUTHORITIES,))

    # 14. no_governing — the only candidate does not apply (wrong jurisdiction) -> a gap.
    _case(f"{prefix}14", split, "no_governing", "Which policy governs US operations?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("regional eu policy", "operations", CORPORATE, jurisdiction="eu",
                      disqualifier="wrong_jurisdiction")],
          None, GovStatus.NO_GOVERNING_AUTHORITY,
          expected_gaps=(GovGapCode.NO_GOVERNING_POLICY,))

    # 15. upstream_gap — a governing authority resolves, but an upstream gap is preserved.
    _case(f"{prefix}15", split, "upstream_gap", "Which ops policy governs (weak retrieval)?",
          _sit(jurisdiction="us", user_role="staff"),
          [PolicySpec("alpha ops policy", "operations", CORPORATE, jurisdiction="us",
                      gold_winner=True)],
          "alpha ops policy", GovStatus.GOVERNING,
          expected_gaps=(GovGapCode.INSUFFICIENT_UPSTREAM_RELATIONSHIPS,),
          upstream_gaps=(RelationshipGap(E3GapCode.INSUFFICIENT_RETRIEVAL_EVIDENCE,
                                         "upstream retrieval evidence was insufficient"),))


_build_split("E4D", "dev")
_build_split("E4E", "eval")

for _c in _CASES:              # eagerly realize evidence units for the manifest/hash
    _units(_c)

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
            "n_families": len(fam), "split_distribution": dist, "family_distribution": fam,
            "eval_lock": eval_lock()}
