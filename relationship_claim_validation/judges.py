"""
Three specialized judges (JUDGE_PROTOCOL.md).

  Judge A — evidence advocate:   finds spans that SUPPORT each predicate.
  Judge B — evidence challenger: independently tries to FALSIFY the claim
                                 (contradiction spans, missing predicates).
  Judge C — adjudicator:         runs ONLY when A and B disagree on a predicate;
                                 resolves predicate-by-predicate (no majority vote).

HONESTY: these judges are DETERMINISTIC, span-grounded rule engines — deliberately
NOT LLMs — so the whole experiment is reproducible and the calibration/determinism
gates are meaningful. They are stand-ins for what would be LLM judges in a
resolver-connected deployment; see FINAL_VERDICT.md. Judge independence is
structural: Judge B never receives Judge A's output; Judge C receives both traces
plus the deterministic result and resolves each disputed predicate on the evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Tuple

from relationship_claim_validation.model import (
    Document, PredicateName as P, PredicateVerdict as V, RelationshipClaim,
)

# Sentinel verdict for a genuinely unresolvable, equally-explicit conflict.
UNKNOWN_VERDICT = "unknown"


def _cited_spans(claim: RelationshipClaim, documents: Mapping[str, Document]):
    out = []
    for d in claim.cited_document_ids:
        doc = documents.get(d)
        if doc is None:
            continue
        for s in doc.spans:
            if s.span_id in claim.cited_span_ids:
                out.append((d, s))
    return out


def _temporal_ok(span_t, claim_t) -> bool:
    if span_t is None or claim_t is None:
        return True
    sf, st = span_t.get("from"), span_t.get("to")
    cf, ct = claim_t
    los = [x for x in (sf, cf) if x is not None]
    his = [x for x in (st, ct) if x is not None]
    lo = max(los) if los else None
    hi = min(his) if his else None
    if lo is None or hi is None:
        return True
    return lo <= hi


# --- Judge A -----------------------------------------------------------------

@dataclass(frozen=True)
class JudgeATrace:
    supported: Mapping[str, bool]
    explicit: Mapping[str, bool]            # support came from an explicit relation span
    supporting_spans: Tuple[str, ...]
    supporting_document_ids: Tuple[str, ...]


def judge_a(claim: RelationshipClaim,
            documents: Mapping[str, Document]) -> JudgeATrace:
    supported: Dict[str, bool] = {p.value: False for p in P}
    explicit: Dict[str, bool] = {p.value: False for p in P}
    sup_spans: List[str] = []
    sup_docs: List[str] = []

    for doc_id, s in _cited_spans(claim, documents):
        a = s.assertions
        touches = a.get("source") == claim.source_node and \
            a.get("target") == claim.target_node
        rel_ok = a.get("relation") == claim.relationship_type and not a.get("negates")
        used = False
        if touches:
            supported[P.ENTITY_CORRECTNESS.value] = True
            used = True
        if touches and rel_ok:
            for pr in (P.RELATIONSHIP_WORDING, P.DIRECTION, P.DOCUMENT_PROVENANCE,
                       P.SUPPORT_COMPLETENESS):
                supported[pr.value] = True
                explicit[pr.value] = True
            sc = a.get("scope", "__unset__")
            if sc == "__unset__" or sc == claim.claimed_scope:
                supported[P.SCOPE.value] = True
            if _temporal_ok(a.get("temporal"), claim.claimed_temporal):
                supported[P.TEMPORAL_APPLICABILITY.value] = True
            au = a.get("authority")
            if au is None or au == claim.claimed_authority:
                supported[P.AUTHORITY_APPLICABILITY.value] = True
            used = True
        if used:
            sup_spans.append(s.span_id)
            if doc_id not in sup_docs:
                sup_docs.append(doc_id)
    return JudgeATrace(dict(supported), dict(explicit),
                       tuple(sup_spans), tuple(sup_docs))


# --- Judge B -----------------------------------------------------------------

@dataclass(frozen=True)
class JudgeBTrace:
    contradicted: Mapping[str, bool]
    explicit: Mapping[str, bool]            # contradiction from an explicit negation span
    missing: Tuple[str, ...]
    contradicting_spans: Tuple[str, ...]


def judge_b(claim: RelationshipClaim,
            documents: Mapping[str, Document]) -> JudgeBTrace:
    contradicted: Dict[str, bool] = {p.value: False for p in P}
    explicit: Dict[str, bool] = {p.value: False for p in P}
    contra_spans: List[str] = []

    for doc in documents.values():
        for s in doc.spans:
            a = s.assertions
            same_pair = a.get("source") == claim.source_node and \
                a.get("target") == claim.target_node
            if same_pair and a.get("relation") == claim.relationship_type and a.get("negates"):
                contradicted[P.CONTRADICTION.value] = True
                explicit[P.CONTRADICTION.value] = True
                contra_spans.append(s.span_id)
            if same_pair and a.get("contradicts") == claim.relationship_type:
                contradicted[P.CONTRADICTION.value] = True
                explicit[P.CONTRADICTION.value] = True
                contra_spans.append(s.span_id)
            if a.get("source") == claim.target_node and \
               a.get("target") == claim.source_node and \
               a.get("relation") == claim.relationship_type and \
               a.get("exclusive_direction"):
                contradicted[P.DIRECTION.value] = True
                explicit[P.DIRECTION.value] = True
                contra_spans.append(s.span_id)

    a_indep = judge_a(claim, documents)     # recomputed; A's result is not shared in
    missing = tuple(
        p.value for p in P
        if not a_indep.supported.get(p.value, False)
        and not contradicted.get(p.value, False))
    return JudgeBTrace(dict(contradicted), dict(explicit), missing,
                       tuple(sorted(set(contra_spans))))


# --- Judge C -----------------------------------------------------------------

@dataclass(frozen=True)
class JudgeCResult:
    resolved: Mapping[str, str]
    ran: bool


def judges_disagree(a: JudgeATrace, b: JudgeBTrace) -> Tuple[str, ...]:
    """Predicates where A found support but B found contradiction — the only
    genuine semantic disagreements that need adjudication."""
    return tuple(p.value for p in P
                 if a.supported.get(p.value, False)
                 and b.contradicted.get(p.value, False))


def judge_c(claim: RelationshipClaim, documents: Mapping[str, Document],
            a: JudgeATrace, b: JudgeBTrace,
            disagreements: Tuple[str, ...]) -> JudgeCResult:
    """Resolve each disputed predicate on evidence explicitness (deterministic):
      - both sides explicit  -> UNKNOWN (manual review)
      - only B explicit      -> CONTRADICTED
      - only A explicit      -> SUPPORTED
      - neither explicit      -> CONTRADICTED (conservative default)
    """
    resolved: Dict[str, str] = {}
    for pred in disagreements:
        a_exp = a.explicit.get(pred, False)
        b_exp = b.explicit.get(pred, False)
        if a_exp and b_exp:
            resolved[pred] = UNKNOWN_VERDICT
        elif b_exp:
            resolved[pred] = V.CONTRADICTED.value
        elif a_exp:
            resolved[pred] = V.SUPPORTED.value
        else:
            resolved[pred] = V.CONTRADICTED.value
    return JudgeCResult(resolved, ran=bool(disagreements))
