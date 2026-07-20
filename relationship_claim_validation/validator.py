"""
The Relationship Claim Validation Layer + ablation configuration.

Pipeline position (intended, in a resolver-connected system):
    Documents -> Proposal -> [Frozen Proposal Validation] -> THIS LAYER -> Governance

In THIS repository there is no frozen proposal/governance/packet pipeline, so the
layer runs stand-alone over a synthetic corpus. When ``config.enabled is False``
the layer is an identity pass-through: every proposed claim is retained as
SUPPORTED (the pre-experiment assumption "proposal-validated relationships are
true"). That reproduces frozen/baseline behavior for the V0 ablation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from relationship_claim_validation.deterministic import run_deterministic
from relationship_claim_validation.judges import (
    JudgeATrace, JudgeBTrace, UNKNOWN_VERDICT, judge_a, judge_b, judge_c,
    judges_disagree,
)
from relationship_claim_validation.model import (
    CORE_PREDICATES, NARROWING_PREDICATES, ClaimStatus, ConfidenceVector,
    Document, EvidenceRecord, PredicateName as P, PredicateVerdict as V,
    RecommendedAction, RelationshipClaim, STATUS_ACTION,
)


@dataclass(frozen=True)
class AblationConfig:
    name: str
    enabled: bool               # False => identity pass-through (V0)
    deterministic: bool         # run deterministic pre-checks
    judge_a: bool
    judge_b: bool
    judge_c: bool
    description: str


# The five preregistered ablations (ABLATION_RESULTS.md).
ABLATIONS: Tuple[AblationConfig, ...] = (
    AblationConfig("V0", False, False, False, False, False,
                   "no claim validation (identity pass-through; baseline)"),
    AblationConfig("V1", True, True, False, False, False,
                   "deterministic validation only"),
    AblationConfig("V2", True, True, True, False, False,
                   "deterministic + Judge A (advocate) only"),
    AblationConfig("V3", True, True, True, True, False,
                   "deterministic + Judge A + Judge B (no adjudicator)"),
    AblationConfig("V4", True, True, True, True, True,
                   "full system: deterministic + A + B + C"),
)


def _confidence(verdicts: Mapping[str, str]) -> ConfidenceVector:
    score = {V.SUPPORTED.value: 1.0, V.NOT_APPLICABLE.value: 0.75,
             V.NOT_SUPPORTED.value: 0.25, V.CONTRADICTED.value: 0.0}
    return ConfidenceVector({k: score.get(v, 0.5) for k, v in verdicts.items()})


class ClaimValidationLayer:
    def __init__(self, config: AblationConfig, documents: Mapping[str, Document]):
        self.config = config
        self.documents = dict(documents)

    # -- single claim ---------------------------------------------------------
    def validate(self, claim: RelationshipClaim,
                 retained_keys: Tuple[Tuple[str, str, str], ...] = ()
                 ) -> EvidenceRecord:
        c = self.config
        if not c.enabled:
            return self._identity(claim)

        # deterministic pre-judge checks
        det = run_deterministic(claim, self.documents, retained_keys) \
            if c.deterministic else None
        if det is not None and not det.passed:
            return self._terminal(claim, det.terminal_status, deterministic=True)

        # judges
        a = judge_a(claim, self.documents) if c.judge_a else None
        b = judge_b(claim, self.documents) if c.judge_b else None

        disagreements: Tuple[str, ...] = ()
        adjudicated = False
        c_resolved: Dict[str, str] = {}
        if a is not None and b is not None:
            disagreements = judges_disagree(a, b)
            if c.judge_c and disagreements:
                cres = judge_c(claim, self.documents, a, b, disagreements)
                c_resolved = dict(cres.resolved)
                adjudicated = cres.ran

        return self._decide(claim, a, b, c_resolved, adjudicated)

    # -- ablation-aware batch -------------------------------------------------
    def validate_corpus(self, claims: Tuple[RelationshipClaim, ...]
                        ) -> Tuple[EvidenceRecord, ...]:
        out: List[EvidenceRecord] = []
        retained_keys: List[Tuple[str, str, str]] = []
        for claim in claims:
            rec = self.validate(claim, tuple(retained_keys))
            out.append(rec)
            if rec.recommended_action in (RecommendedAction.RETAIN,
                                          RecommendedAction.NARROW):
                retained_keys.append(
                    (claim.source_node, claim.relationship_type, claim.target_node))
        return tuple(out)

    # -- helpers --------------------------------------------------------------
    def _identity(self, claim: RelationshipClaim) -> EvidenceRecord:
        verdicts = {p.value: V.NOT_APPLICABLE.value for p in P}
        return EvidenceRecord(
            claim.relationship_id, claim.relationship_type, claim.source_node,
            claim.target_node, tuple(claim.cited_document_ids),
            tuple(claim.cited_span_ids), (), (), _confidence(verdicts),
            ClaimStatus.SUPPORTED, RecommendedAction.RETAIN, verdicts)

    def _terminal(self, claim: RelationshipClaim, status: ClaimStatus,
                  deterministic: bool) -> EvidenceRecord:
        verdicts = {p.value: V.NOT_SUPPORTED.value for p in P}
        return EvidenceRecord(
            claim.relationship_id, claim.relationship_type, claim.source_node,
            claim.target_node, (), (), (), tuple(p.value for p in CORE_PREDICATES),
            _confidence(verdicts), status, STATUS_ACTION[status], verdicts,
            adjudicated=False, deterministic_removed=deterministic)

    def _decide(self, claim: RelationshipClaim,
                a: JudgeATrace | None, b: JudgeBTrace | None,
                c_resolved: Mapping[str, str], adjudicated: bool
                ) -> EvidenceRecord:
        # Build final per-predicate verdicts.
        verdicts: Dict[str, str] = {}
        for p in P:
            key = p.value
            if key in c_resolved:                     # adjudicated wins
                verdicts[key] = c_resolved[key]
                continue
            a_sup = a.supported.get(key, False) if a else False
            b_con = b.contradicted.get(key, False) if b else False
            if b_con and not a_sup:
                verdicts[key] = V.CONTRADICTED.value
            elif a_sup:
                verdicts[key] = V.SUPPORTED.value
            elif b_con and a_sup:                     # unresolved (no C) -> conservative
                verdicts[key] = V.CONTRADICTED.value
            else:
                verdicts[key] = V.NOT_SUPPORTED.value

        contradicting = tuple(b.contradicting_spans) if b else ()
        missing = tuple(
            p.value for p in CORE_PREDICATES
            if verdicts.get(p.value) == V.NOT_SUPPORTED.value)
        sup_spans = tuple(a.supporting_spans) if a else ()
        sup_docs = tuple(a.supporting_document_ids) if a else ()

        status = self._status_from_verdicts(verdicts)
        return EvidenceRecord(
            claim.relationship_id, claim.relationship_type, claim.source_node,
            claim.target_node, sup_docs, sup_spans, contradicting, missing,
            _confidence(verdicts), status, STATUS_ACTION[status], verdicts,
            adjudicated=adjudicated, deterministic_removed=False)

    @staticmethod
    def _status_from_verdicts(verdicts: Mapping[str, str]) -> ClaimStatus:
        """Frozen decision function (CLAIM_STATUS_SPEC.md)."""
        def val(p: P) -> str:
            return verdicts.get(p.value, V.NOT_SUPPORTED.value)

        # 0) an unresolvable equally-explicit conflict -> UNKNOWN (manual review)
        if any(v == UNKNOWN_VERDICT for v in verdicts.values()):
            return ClaimStatus.UNKNOWN

        # 1) explicit contradiction anywhere -> CONTRADICTED
        if any(v == V.CONTRADICTED.value for v in verdicts.values()):
            return ClaimStatus.CONTRADICTED

        # 2) the relationship itself affirmatively supported (wording+direction+
        #    provenance) -> SUPPORTED or narrowed
        relation_supported = (
            val(P.RELATIONSHIP_WORDING) == V.SUPPORTED.value
            and val(P.DIRECTION) == V.SUPPORTED.value
            and val(P.DOCUMENT_PROVENANCE) == V.SUPPORTED.value)
        if relation_supported:
            narrowing = [val(p) == V.SUPPORTED.value for p in NARROWING_PREDICATES]
            return ClaimStatus.SUPPORTED if all(narrowing) \
                else ClaimStatus.PARTIALLY_SUPPORTED

        # 3) entities established but the relation between them is not asserted
        #    -> evidence is present yet does not support the claim -> UNSUPPORTED
        if val(P.ENTITY_CORRECTNESS) == V.SUPPORTED.value:
            return ClaimStatus.UNSUPPORTED

        # 4) evidence does not even establish the entities -> INSUFFICIENT
        return ClaimStatus.INSUFFICIENT_EVIDENCE
