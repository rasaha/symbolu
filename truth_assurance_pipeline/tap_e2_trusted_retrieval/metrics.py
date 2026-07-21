"""
TAP-E2 retrieval metrics + independent critical-failure reporting.

Ranked-list metrics (Recall@k, Precision@k, nDCG, MRR, coverage, redundancy,
diversity), retrieval-quality metrics (provenance completeness, authority coverage,
false-evidence inclusion), and gap-detection metrics are computed against the graded
gold. Critical failures are computed per query and reported independently of averages.

Ground truth supports multiple acceptable retrieval sets: a retrieved unit counts as
correct if it is `relevant` (grade 2) or `partial` (grade 1); only grade-0 units
(distractors / off-topic) are penalized.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e2_trusted_retrieval.corpus.queries import QueryCase
from truth_assurance_pipeline.tap_e2_trusted_retrieval.schema import (
    GapType, RetrievalRecord,
)


def _dcg(grades: Sequence[int]) -> float:
    return sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(grades))


@dataclass(frozen=True)
class QueryScore:
    query_id: str
    k: int
    recall_at_k: float
    precision_at_k: float
    ndcg_at_k: float
    mrr: float
    evidence_coverage: float
    provenance_completeness: float
    redundancy: float
    diversity: float
    false_evidence_inclusion: float
    has_authoritative_gold: bool
    authoritative_retrieved: bool
    conflict_expected: bool
    conflict_detected: bool
    no_authority_expected: bool
    no_authority_detected: bool
    missing_expected: bool
    missing_detected: bool
    expected_gaps_all_detected: bool
    spurious_conflict: bool
    # critical failures
    crit_authoritative_omitted: bool
    crit_unsupported_top1: bool
    crit_provenance_missing: bool
    crit_outdated_preferred: bool
    crit_conflict_hidden: bool
    crit_duplicate_overload: bool
    crit_hallucinated_id: bool

    def critical_failures(self) -> Tuple[str, ...]:
        out = []
        for name, v in (
            ("authoritative_evidence_omitted", self.crit_authoritative_omitted),
            ("unsupported_evidence_retrieved", self.crit_unsupported_top1),
            ("provenance_missing", self.crit_provenance_missing),
            ("outdated_evidence_preferred", self.crit_outdated_preferred),
            ("conflicting_evidence_hidden", self.crit_conflict_hidden),
            ("duplicate_evidence_overload", self.crit_duplicate_overload),
            ("hallucinated_evidence_identifiers", self.crit_hallucinated_id),
        ):
            if v:
                out.append(name)
        return tuple(out)


def score_query(q: QueryCase, rec: RetrievalRecord, index_ids: frozenset) -> QueryScore:
    k = len(rec.candidates)
    retrieved = list(rec.unit_ids)
    grades = [q.relevance(uid) for uid in retrieved]
    gold_relevant = set(q.relevant)                 # grade-2 must-find
    gold_any = set(q.relevant) | set(q.partial)     # acceptable

    hit2 = [uid for uid in retrieved if uid in gold_relevant]
    hit_any = [uid for uid in retrieved if uid in gold_any]

    recall = (len(set(hit2)) / len(gold_relevant)) if gold_relevant else 1.0
    precision = (len(hit_any) / len(retrieved)) if retrieved else (1.0 if not gold_any else 0.0)
    ideal = _dcg(sorted([q.relevance(u) for u in gold_any], reverse=True)[:max(1, k)])
    ndcg = (_dcg(grades) / ideal) if ideal > 0 else (1.0 if not gold_any else 0.0)
    mrr = 0.0
    for i, uid in enumerate(retrieved):
        if uid in gold_relevant:
            mrr = 1.0 / (i + 1)
            break
    coverage = (len(set(hit_any)) / len(gold_any)) if gold_any else 1.0

    prov_complete = (sum(1 for c in rec.candidates if c.provenance.is_complete())
                     / len(retrieved)) if retrieved else 1.0

    # redundancy: retrieved units duplicating an earlier claim_key+value
    seen_claims: set = set()
    dups = 0
    for c in rec.candidates:
        key = (c.unit.claim_key, c.unit.claim_value)
        if c.unit.claim_key and key in seen_claims:
            dups += 1
        elif c.unit.claim_key:
            seen_claims.add(key)
    redundancy = (dups / len(retrieved)) if retrieved else 0.0
    diversity = (len({c.unit.doc_id for c in rec.candidates}) / len(retrieved)) if retrieved else 1.0
    # false-evidence inclusion = fraction of retrieved that are ANNOTATED DISTRACTORS
    # (tempting-but-wrong planted units). Off-topic low-score filler is captured by
    # precision/nDCG; this metric targets the units a trusted layer must exclude.
    distractors = set(q.distractors)
    false_incl = (sum(1 for uid in retrieved if uid in distractors) / len(retrieved)) \
        if retrieved else 0.0

    # authority coverage: only meaningful when the gold set contains an authoritative unit
    auth_gold_ids = {uid for uid in gold_any if uid in index_ids}
    has_auth_gold = any(_is_authoritative(rec, uid) for uid in gold_any)
    auth_retrieved = any(c.unit.is_authoritative and c.unit.unit_id in gold_any
                         for c in rec.candidates)

    detected = {g.gap_type for g in rec.gaps}
    conflict_detected = GapType.CONFLICTING_SOURCES in detected
    no_auth_detected = GapType.NO_AUTHORITATIVE_SOURCE in detected
    missing_detected = (GapType.INSUFFICIENT_EVIDENCE in detected
                        or GapType.MISSING_ENTITY in detected
                        or GapType.NO_AUTHORITATIVE_SOURCE in detected)
    expected = set(q.expected_gaps)
    all_expected = expected <= detected if expected else True
    spurious_conflict = conflict_detected and not q.conflict_expected

    # --- critical failures ---
    crit_auth_omitted = bool(q.authoritative_required and has_auth_gold
                             and not auth_retrieved)
    crit_unsupported_top1 = bool(retrieved and retrieved[0] not in gold_any and gold_any)
    crit_prov_missing = any(not c.provenance.is_complete() for c in rec.candidates)
    crit_outdated_pref = _outdated_preferred(rec)
    crit_conflict_hidden = bool(q.conflict_expected and not conflict_detected)
    crit_dup_overload = redundancy > 0.4
    crit_halluc = any(uid not in index_ids for uid in retrieved)

    return QueryScore(
        query_id=q.query_id, k=k,
        recall_at_k=round(recall, 4), precision_at_k=round(precision, 4),
        ndcg_at_k=round(ndcg, 4), mrr=round(mrr, 4),
        evidence_coverage=round(coverage, 4),
        provenance_completeness=round(prov_complete, 4),
        redundancy=round(redundancy, 4), diversity=round(diversity, 4),
        false_evidence_inclusion=round(false_incl, 4),
        has_authoritative_gold=has_auth_gold, authoritative_retrieved=auth_retrieved,
        conflict_expected=q.conflict_expected, conflict_detected=conflict_detected,
        no_authority_expected=(GapType.NO_AUTHORITATIVE_SOURCE in expected),
        no_authority_detected=no_auth_detected,
        missing_expected=q.missing_evidence, missing_detected=missing_detected,
        expected_gaps_all_detected=all_expected, spurious_conflict=spurious_conflict,
        crit_authoritative_omitted=crit_auth_omitted,
        crit_unsupported_top1=crit_unsupported_top1,
        crit_provenance_missing=crit_prov_missing,
        crit_outdated_preferred=crit_outdated_pref,
        crit_conflict_hidden=crit_conflict_hidden,
        crit_duplicate_overload=crit_dup_overload,
        crit_hallucinated_id=crit_halluc)


def _is_authoritative(rec: RetrievalRecord, uid: str) -> bool:
    for c in rec.candidates:
        if c.unit.unit_id == uid:
            return c.unit.is_authoritative
    # unit not retrieved; consult gold-authority via a static lookup would need the index
    return False


def _outdated_preferred(rec: RetrievalRecord) -> bool:
    """A deprecated/superseded unit ranked above the fresher unit that supersedes it."""
    pos = {c.unit.unit_id: i for i, c in enumerate(rec.candidates)}
    for c in rec.candidates:
        u = c.unit
        if u.superseded_by and u.superseded_by in pos and pos[u.unit_id] < pos[u.superseded_by]:
            return True
    return False


def aggregate(scores: Sequence[QueryScore]) -> Dict[str, object]:
    n = len(scores)

    def mean(f):
        return round(sum(f(s) for s in scores) / n, 4) if n else 0.0

    auth_denom = [s for s in scores if s.has_authoritative_gold]
    conflict_denom = [s for s in scores if s.conflict_expected]
    conflict_pred = [s for s in scores if s.conflict_detected]
    missing_denom = [s for s in scores if s.missing_expected]
    gap_denom = [s for s in scores if s.conflict_expected or s.no_authority_expected
                 or s.missing_expected]
    clean = [s for s in scores if not (s.conflict_expected or s.no_authority_expected
                                       or s.missing_expected)]

    def rate(sub, f, default=1.0):
        return round(sum(1 for s in sub if f(s)) / len(sub), 4) if sub else default

    crit = {}
    for s in scores:
        for name in s.critical_failures():
            crit[name] = crit.get(name, 0) + 1
    for key in ("authoritative_evidence_omitted", "unsupported_evidence_retrieved",
                "provenance_missing", "outdated_evidence_preferred",
                "conflicting_evidence_hidden", "duplicate_evidence_overload",
                "hallucinated_evidence_identifiers"):
        crit.setdefault(key, 0)

    return {
        "n": n,
        "recall_at_k": mean(lambda s: s.recall_at_k),
        "precision_at_k": mean(lambda s: s.precision_at_k),
        "ndcg_at_k": mean(lambda s: s.ndcg_at_k),
        "mrr": mean(lambda s: s.mrr),
        "evidence_coverage": mean(lambda s: s.evidence_coverage),
        "provenance_completeness": mean(lambda s: s.provenance_completeness),
        "authority_coverage": rate(auth_denom, lambda s: s.authoritative_retrieved),
        "redundancy": mean(lambda s: s.redundancy),
        "retrieval_diversity": mean(lambda s: s.diversity),
        "false_evidence_inclusion": mean(lambda s: s.false_evidence_inclusion),
        "gap_detection_accuracy": rate(gap_denom, lambda s: s.expected_gaps_all_detected),
        "conflict_detection_recall": rate(conflict_denom, lambda s: s.conflict_detected),
        "conflict_detection_precision": rate(conflict_pred, lambda s: s.conflict_expected),
        "missing_evidence_detection": rate(missing_denom, lambda s: s.missing_detected),
        "false_conflict_rate": rate(clean, lambda s: s.spurious_conflict, 0.0),
        "critical_failures": crit,
        "severe_failure_count": sum(len(s.critical_failures()) for s in scores),
    }
