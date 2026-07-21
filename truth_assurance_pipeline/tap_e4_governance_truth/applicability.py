"""
Governance resolution engine + the A-F baseline configuration.

Consumes an IntentRecord (TAP-E1), a RetrievalRecord (TAP-E2), and a RelationshipRecord
(TAP-E3) through their frozen public interfaces, plus an explicit ``Situation`` (governance
context passed as application metadata). It resolves WHICH documented authority governs —
nothing beyond that. It does not retrieve, infer missing relationships, or repair upstream
gaps (upstream gaps are preserved).

Typed stages (Section 7): input validation → authority identification → authority
normalization → jurisdiction → scope → temporal → exceptions → version → precedence →
conflict detection → confidence → gaps → GovernanceRecord generation. Every stage is a
pure function of the records + situation; the pipeline emits an append-only trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import IntentRecord
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import RetrievalRecord
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    RelationshipRecord, RelationshipAssertion,
)
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import RelationshipType
from truth_assurance_pipeline.tap_e4_governance_truth import (
    authority as auth, conflict_resolution, confidence as conf_mod, exceptions as exc_mod,
    jurisdiction as juris_mod, precedence as prec_mod, scope as scope_mod, temporal as temp_mod,
)
from truth_assurance_pipeline.tap_e4_governance_truth.authority import (
    AUTHORITY_MODEL_VERSION, AuthorityTier,
)
from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    SCHEMA_VERSION, GovGapCode, GovProvenance, GovStatus, GovernanceConfidence,
    GovernanceGap, GovernanceRecord, GoverningDecision, RejectedAuthority,
)

CREATED_AT = "N/A (deterministic run)"

_GOVERNANCE_PREDICATES = {
    RelationshipType.APPLIES_TO, RelationshipType.GOVERNS, RelationshipType.REQUIRES,
    RelationshipType.PROHIBITS, RelationshipType.PROHIBITED_FROM,
    RelationshipType.OVERRIDES, RelationshipType.SUBORDINATE_TO,
    RelationshipType.OBLIGATED_TO,
}


@dataclass(frozen=True)
class Situation:
    jurisdiction: str = ""
    user_role: str = ""
    environment: str = ""
    date_year: Optional[int] = None
    contract: str = ""
    product: str = ""
    business_unit: str = ""

    def as_map(self) -> Dict[str, str]:
        return {"jurisdiction": self.jurisdiction, "user_role": self.user_role,
                "environment": self.environment, "contract": self.contract,
                "product": self.product, "business_unit": self.business_unit}

    @staticmethod
    def from_metadata(md: Mapping[str, str]) -> "Situation":
        y = md.get("date_year")
        return Situation(
            jurisdiction=md.get("jurisdiction", ""), user_role=md.get("user_role", ""),
            environment=md.get("environment", ""),
            date_year=int(y) if y not in (None, "") else None,
            contract=md.get("contract", ""), product=md.get("product", ""),
            business_unit=md.get("business_unit", ""))


@dataclass(frozen=True)
class Candidate:
    name: str
    predicate: RelationshipType
    target: str
    obligation_value: str
    tier: AuthorityTier
    jurisdiction: str
    role: str
    environment: str
    version: int
    is_contract: bool
    is_emergency_override: bool
    superseded: bool
    temporality: str
    valid_from: Optional[str]
    valid_until: Optional[str]
    assertion_id: str
    evidence_unit_id: str
    source_id: str
    source_location: str
    record_id: str

    @property
    def specificity(self) -> int:
        return scope_mod.specificity(self.role, self.environment)


@dataclass(frozen=True)
class GovernanceConfig:
    name: str
    first_match: bool
    highest_authority: bool
    jurisdiction: bool
    temporal_version: bool
    exceptions_precedence: bool
    full: bool
    description: str


BASELINES: Tuple[GovernanceConfig, ...] = (
    GovernanceConfig("A", True, False, False, False, False, False,
                     "first matching policy"),
    GovernanceConfig("B", False, True, False, False, False, False,
                     "highest authority only"),
    GovernanceConfig("C", False, True, True, False, False, False,
                     "authority + jurisdiction (+ scope)"),
    GovernanceConfig("D", False, True, True, True, False, False,
                     "C + temporal + version/supersession"),
    GovernanceConfig("E", False, True, True, True, True, False,
                     "D + exceptions + precedence (customer/emergency override)"),
    GovernanceConfig("F", False, True, True, True, True, True,
                     "full Governance Truth (+ conflict, confidence, gaps, provenance, trace)"),
)


def config(name: str) -> GovernanceConfig:
    for c in BASELINES:
        if c.name == name:
            return c
    raise KeyError(name)


def _ver(s: str) -> int:
    m = re.search(r"\d+", s or "")
    return int(m.group(0)) if m else 0


class GovernanceTruthLayer:
    def __init__(self, cfg: GovernanceConfig):
        self.cfg = cfg

    # -- candidate extraction (stages 2-3) -----------------------------------
    def _candidates(self, retrieval: RetrievalRecord, relationship: RelationshipRecord):
        units = {c.unit.unit_id: c.unit for c in retrieval.candidates}
        superseded: set = set()
        exemptions: List[str] = []
        for a in relationship.relationship_assertions:
            if a.relationship_type is RelationshipType.SUPERSEDES:
                superseded.add(a.normalized_object)     # object is superseded
            elif a.relationship_type in (RelationshipType.EXEMPTS,
                                         RelationshipType.PROHIBITED_FROM):
                if a.relationship_type is RelationshipType.EXEMPTS:
                    exemptions.append(a.normalized_object)

        cands: List[Candidate] = []
        for a in relationship.relationship_assertions:
            if a.relationship_type not in _GOVERNANCE_PREDICATES:
                continue
            eu = a.evidence_unit_ids[0] if a.evidence_unit_ids else ""
            unit = units.get(eu)
            authority_level = unit.authority.value if unit else ""
            doc_type = unit.doc_type.value if unit else ""
            tier = auth.tier_from_evidence(authority_level, doc_type,
                                           a.scope.get("tier", ""))
            sp = a.source_provenance[0] if a.source_provenance else None
            cands.append(Candidate(
                name=a.normalized_subject, predicate=a.relationship_type,
                target=a.normalized_object, obligation_value=a.scope.get("value", ""),
                tier=tier, jurisdiction=a.scope.get("jurisdiction",
                                                    a.scope.get("geography", "")),
                role=a.scope.get("user_role", ""), environment=a.scope.get("environment", ""),
                version=_ver(a.scope.get("version", "")),
                is_contract=(doc_type == "contract"),
                is_emergency_override=(a.scope.get("emergency") == "true"
                                       or "emergency" in a.normalized_subject),
                superseded=(a.normalized_subject in superseded),
                temporality=a.temporality.value, valid_from=a.valid_from,
                valid_until=a.valid_until, assertion_id=a.assertion_id,
                evidence_unit_id=eu, source_id=sp.source_id if sp else "",
                source_location=sp.source_location if sp else "",
                record_id=relationship.relationship_record_id))
        return cands, exemptions

    # -- resolution ----------------------------------------------------------
    def resolve(self, intent: IntentRecord, retrieval: RetrievalRecord,
                relationship: RelationshipRecord, situation: Situation) -> GovernanceRecord:
        cfg = self.cfg
        trace = ["input_validation", "authority_identification", "authority_normalization"]
        cands, exemptions = self._candidates(retrieval, relationship)
        sit = situation.as_map()

        rejected: List[RejectedAuthority] = []
        gaps: List[GovernanceGap] = []
        jur_conf = scope_conf = temp_conf = exc_conf = 1.0

        # stage 4-5: jurisdiction + scope (C and above; A first-match and B highest-authority
        # deliberately skip applicability filtering — that is what makes them unsafe)
        pool = list(cands)
        if cfg.jurisdiction:
            trace.append("jurisdiction_resolution")
            trace.append("scope_matching")
            kept = []
            for c in pool:
                jok, jc = juris_mod.matches(c.jurisdiction, sit)
                sok, sc = scope_mod.matches(c.role, c.environment, sit)
                if not jok:
                    rejected.append(RejectedAuthority(c.name, c.tier, "jurisdiction mismatch"))
                    continue
                if not sok:
                    rejected.append(RejectedAuthority(c.name, c.tier, "scope mismatch"))
                    continue
                jur_conf = min(jur_conf, jc); scope_conf = min(scope_conf, sc)
                kept.append(c)
            pool = kept

        # stage 6-8: temporal + version/supersession
        if cfg.temporal_version:
            trace.extend(["temporal_applicability", "version_resolution"])
            kept = []
            for c in pool:
                st, tc = temp_mod.status(c.temporality, c.valid_from, c.valid_until,
                                         c.superseded, situation.date_year)
                if st != "EFFECTIVE":
                    rejected.append(RejectedAuthority(c.name, c.tier, f"temporal:{st}"))
                    continue
                temp_conf = min(temp_conf, tc)
                kept.append(c)
            pool = kept

        # stage 7/9: exceptions + precedence
        exception_basis: List[str] = []
        if cfg.exceptions_precedence:
            trace.append("exception_evaluation")
            exempt, basis = exc_mod.evaluate(exemptions, sit)
            if exempt:
                exception_basis.append(basis)
                # the situation is exempted from the general obligation; the exempting
                # (emergency) rule governs if present, else no obligation applies
                pool = [c for c in pool if c.is_emergency_override] or []
            trace.append("precedence_resolution")

        # selection
        if cfg.first_match:
            # baseline A: first candidate in evidence order, no selectability guard
            winner = pool[0] if pool else None
            ordered = pool
            tied: List[Candidate] = []
        elif cfg.exceptions_precedence:
            # E/F: full documented precedence (contract/emergency override, specificity, version)
            winner, ordered, tied = prec_mod.select(pool)
        else:
            # B/C: highest authority; D also resolves version. Drafts never selectable.
            selectable = [c for c in pool if auth.is_selectable(c.tier)]
            if cfg.temporal_version:                     # D: version-aware
                key = lambda c: (auth.rank(c.tier), c.version, c.name)
            else:                                        # B, C: tier + name only
                key = lambda c: (auth.rank(c.tier), c.name)
            ordered = sorted(selectable, key=key, reverse=True)
            winner = ordered[0] if ordered else None
            tied = [c for c in ordered
                    if winner is not None and auth.rank(c.tier) == auth.rank(winner.tier)]

        # stage 10: conflict detection (F only)
        conflicts = ()
        conflicted = False
        if cfg.full and cfg.exceptions_precedence:
            trace.append("conflict_detection")
            conflicts = conflict_resolution.detect(tied)
            conflicted = bool(conflicts)

        # stage 12: gaps
        if cfg.full:
            trace.append("governance_gaps")
            if not cands:
                gaps.append(GovernanceGap(GovGapCode.INSUFFICIENT_UPSTREAM_RELATIONSHIPS,
                                          "no governance relationships upstream"))
            if winner is None and not conflicted and not exception_basis:
                gaps.append(GovernanceGap(GovGapCode.NO_GOVERNING_POLICY,
                                          "no candidate governs the situation"))
            if conflicted:
                gaps.append(GovernanceGap(GovGapCode.CONFLICTING_AUTHORITIES,
                                          "authorities tie with no deterministic resolver",
                                          {"authorities": list(conflicts[0].authority_names)}))
            for g in relationship.unresolved_relationship_gaps:
                gaps.append(GovernanceGap(GovGapCode.INSUFFICIENT_UPSTREAM_RELATIONSHIPS,
                                          f"upstream relationship gap preserved: {g.gap_code.value}",
                                          {"upstream_gap": g.gap_code.value}))

        # stage 11: confidence
        trace.append("governance_confidence")
        prov_ok = winner is not None and bool(winner.source_id)
        confidence = conf_mod.assess(cfg, jur_conf, scope_conf, temp_conf,
                                     1.0 if exception_basis else 0.9,
                                     len(pool), prov_ok, conflicted)

        # stage 13: record
        trace.append("governance_record_generation")
        decision = self._decision(cfg, winner, ordered, tied, rejected, sit, situation,
                                  exception_basis, confidence, conflicted)
        return GovernanceRecord(
            schema_version=SCHEMA_VERSION, authority_model_version=AUTHORITY_MODEL_VERSION,
            governance_record_id=f"gov::{intent.request_id}::{cfg.name}",
            intent_record_id=intent.request_id, retrieval_record_id=retrieval.retrieval_id,
            relationship_record_id=relationship.relationship_record_id, created_at=CREATED_AT,
            governing_authorities=(decision,) if decision else (),
            governing_relationships=tuple(c.assertion_id for c in ([winner] if winner else [])),
            governance_conflicts=tuple(conflicts), governance_gaps=tuple(_dedupe(gaps)),
            confidence_vector=confidence, processing_trace=tuple(trace))

    def _decision(self, cfg, winner, ordered, tied, rejected, sit, situation,
                  exception_basis, confidence, conflicted) -> Optional[GoverningDecision]:
        if conflicted:
            names = tied
            prov = tuple(GovProvenance(c.name, c.assertion_id, c.evidence_unit_id,
                                       c.source_id, c.source_location, c.record_id)
                         for c in names)
            return GoverningDecision(
                decision_id="D1", selected_authority=None,
                tier=AuthorityTier.UNKNOWN,
                selection_reason="multiple authorities tie at top precedence; not resolved",
                supporting_relationships=(), rejected_relationships=tuple(rejected),
                precedence_chain=tuple(c.name for c in ordered), jurisdiction={},
                scope={}, temporal_basis={}, exception_basis=tuple(exception_basis),
                provenance=prov, confidence=confidence, status=GovStatus.CONFLICTED)
        if winner is None:
            status = (GovStatus.GOVERNING_WITH_EXCEPTION if exception_basis
                      else GovStatus.NO_GOVERNING_AUTHORITY)
            return GoverningDecision(
                decision_id="D1", selected_authority=None, tier=AuthorityTier.UNKNOWN,
                selection_reason=("situation exempted; no residual obligation"
                                  if exception_basis else "no candidate governs"),
                supporting_relationships=(), rejected_relationships=tuple(rejected),
                precedence_chain=(), jurisdiction={}, scope={}, temporal_basis={},
                exception_basis=tuple(exception_basis), provenance=(),
                confidence=confidence, status=status)
        prov = (GovProvenance(winner.name, winner.assertion_id, winner.evidence_unit_id,
                              winner.source_id, winner.source_location, winner.record_id),)
        status = (GovStatus.GOVERNING_WITH_EXCEPTION if exception_basis
                  else GovStatus.GOVERNING)
        reason = self._reason(cfg, winner, ordered)
        return GoverningDecision(
            decision_id="D1", selected_authority=winner.name, tier=winner.tier,
            selection_reason=reason,
            supporting_relationships=(winner.assertion_id,),
            rejected_relationships=tuple(rejected),
            precedence_chain=tuple(c.name for c in ordered),
            jurisdiction={"jurisdiction": winner.jurisdiction or "global"},
            scope={"user_role": winner.role or "all", "environment": winner.environment or "all"},
            temporal_basis={"temporality": winner.temporality,
                            "valid_from": winner.valid_from or "",
                            "valid_until": winner.valid_until or ""},
            exception_basis=tuple(exception_basis), provenance=prov,
            confidence=confidence, status=status)

    @staticmethod
    def _reason(cfg, winner, ordered) -> str:
        bits = [f"tier={winner.tier.value}"]
        if winner.is_contract:
            bits.append("customer-contract override")
        if winner.is_emergency_override:
            bits.append("emergency override")
        if len(ordered) > 1:
            bits.append(f"selected over {len(ordered) - 1} lower-precedence candidate(s)")
        return "; ".join(bits)


def _dedupe(gaps: List[GovernanceGap]) -> List[GovernanceGap]:
    seen = set()
    out = []
    for g in gaps:
        k = (g.gap_code.value, str(sorted(g.detail.items())))
        if k not in seen:
            seen.add(k)
            out.append(g)
    return out
