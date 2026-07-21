"""
TAP-E3 metrics + independent critical-failure reporting (Sections 18 & 19).

Each relationship dimension is measured separately (never hidden behind an aggregate
F1). Ground truth allows ontology-equivalent predicates and multiple normalized forms.
Critical failures are computed per case and reported independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e3_relationship_truth.corpus.cases import Case, GoldRel
from truth_assurance_pipeline.tap_e3_relationship_truth.ontology import RelationshipType
from truth_assurance_pipeline.tap_e3_relationship_truth.schema import (
    Explicitness, GapCode, Modality, Polarity, RelationshipAssertion,
    RelationshipRecord, Temporality,
)

_PERMIT = {RelationshipType.PERMITTED_TO, RelationshipType.AUTHORIZED_BY}
_PROHIBIT = {RelationshipType.PROHIBITS, RelationshipType.PROHIBITED_FROM}
_PAST = {Temporality.HISTORICAL, Temporality.SUPERSEDED}


def _pair(subj: str, obj: str) -> frozenset:
    return frozenset({subj, obj})


def _effect_negative(rtype: RelationshipType, polarity: Polarity) -> bool:
    """Does the assertion ultimately DENY (prohibit) the relationship?"""
    base_prohibit = rtype in _PROHIBIT
    neg = polarity is Polarity.NEGATED
    return base_prohibit ^ neg


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    n_gold: int
    n_pred: int
    tp: int                 # matched gold with acceptable predicate
    fp: int                 # predicted not matching any gold
    subj_ok: int
    obj_ok: int
    pred_ok: int
    dir_ok: int
    pol_ok: int
    pol_total: int
    mod_ok: int
    mod_total: int
    temp_ok: int
    temp_total: int
    scope_ok: int
    scope_total: int
    cond_ok: int
    cond_total: int
    exc_ok: int
    exc_total: int
    matched: int            # denominator for component accuracies
    exact_triple: int
    full_structure: int
    prov_complete: int
    prov_total: int
    conflict_expected: bool
    conflict_detected: bool
    gaps_expected_all: bool
    has_expected_gaps: bool
    cooccurrence_case: bool
    cooccurrence_fp: bool
    unsupported_assertions: int
    crit: Tuple[str, ...]


def _match(case: Case, record: RelationshipRecord
           ) -> List[Tuple[GoldRel, RelationshipAssertion]]:
    preds = list(record.relationship_assertions)
    used = set()
    pairs = []
    for g in case.gold:
        gp = _pair(g.subject, g.object)
        chosen = None
        for i, p in enumerate(preds):
            if i in used:
                continue
            if _pair(p.normalized_subject, p.normalized_object) != gp:
                continue
            if (g.scope.get("value") and p.scope.get("value")
                    and g.scope["value"] != p.scope["value"]):
                continue
            chosen = (i, p)
            break
        if chosen:
            used.add(chosen[0])
            pairs.append((g, chosen[1]))
    unmatched_pred = [p for i, p in enumerate(preds) if i not in used]
    return pairs, unmatched_pred


def score_case(case: Case, record: RelationshipRecord) -> CaseScore:
    matches, unmatched = _match(case, record)
    preds = list(record.relationship_assertions)
    crit: List[str] = []

    tp = sum(1 for g, p in matches if p.relationship_type in g.acceptable())
    fp = len(unmatched)

    subj_ok = obj_ok = pred_ok = dir_ok = 0
    pol_ok = pol_total = mod_ok = mod_total = 0
    temp_ok = temp_total = scope_ok = scope_total = 0
    cond_ok = cond_total = exc_ok = exc_total = 0
    exact = full = 0

    for g, p in matches:
        s_ok = p.normalized_subject == g.subject
        o_ok = p.normalized_object == g.object
        pr_ok = p.relationship_type in g.acceptable()
        d_ok = s_ok and o_ok
        subj_ok += s_ok; obj_ok += o_ok; pred_ok += pr_ok; dir_ok += d_ok
        if not d_ok and p.normalized_subject == g.object and p.normalized_object == g.subject:
            crit.append("DIRECTION_REVERSED")

        pol_total += 1
        p_ok = p.polarity == g.polarity
        pol_ok += p_ok
        # effect-based negation/prohibition/authorization criticals
        if _effect_negative(g.predicate, g.polarity) != _effect_negative(
                p.relationship_type, p.polarity):
            if g.predicate in _PERMIT | _PROHIBIT or g.polarity is Polarity.NEGATED:
                crit.append("AUTHORIZATION_INVERTED")
            if _effect_negative(g.predicate, g.polarity):
                crit.append("PROHIBITION_DROPPED")
            if g.polarity is Polarity.NEGATED:
                crit.append("NEGATION_LOST")

        mod_total += 1
        m_ok = p.modality == g.modality
        mod_ok += m_ok
        if {g.modality, p.modality} == {Modality.REQUIRED, Modality.PERMITTED}:
            crit.append("MUST_MAY_COLLAPSE")
        if g.modality is Modality.ALLEGED and p.modality is Modality.ASSERTED:
            crit.append("ALLEGATION_TREATED_AS_FACT")

        temp_total += 1
        t_ok = p.temporality == g.temporality
        temp_ok += t_ok
        if g.temporality in _PAST and p.temporality is Temporality.CURRENT:
            crit.append("SUPERSEDED_RELATION_TREATED_AS_CURRENT")

        if g.scope:
            scope_total += 1
            if all(p.scope.get(k) == v for k, v in g.scope.items()):
                scope_ok += 1
        if g.conditions:
            cond_total += 1
            if p.conditions and all(any(_tokovlp(gc, pc) for pc in p.conditions)
                                    for gc in g.conditions):
                cond_ok += 1
            else:
                crit.append("CONDITION_DROPPED")
        if g.exceptions:
            exc_total += 1
            if p.exceptions and all(any(_tokovlp(ge, pe) for pe in p.exceptions)
                                    for ge in g.exceptions):
                exc_ok += 1
            else:
                crit.append("EXCEPTION_DROPPED")

        # ownership invented
        if (RelationshipType.OWNS in g.prohibited_predicates
                and p.relationship_type is RelationshipType.OWNS):
            crit.append("OWNERSHIP_INVENTED")

        et = s_ok and o_ok and pr_ok
        exact += et
        fs = (et and d_ok and p_ok and m_ok and t_ok
              and (scope_total == 0 or all(p.scope.get(k) == v for k, v in g.scope.items()))
              and (not g.conditions or (p.conditions and cond_ok))
              and (not g.exceptions or (p.exceptions and exc_ok)))
        full += 1 if fs else 0

    # co-occurrence / unsupported
    cooccurrence_case = (len(case.gold) == 0 and case.family.startswith("cooccurrence"))
    cooccurrence_fp = cooccurrence_case and len(preds) > 0
    if cooccurrence_fp:
        crit.append("UNSUPPORTED_RELATIONSHIP_EMITTED")
        if any(p.relationship_type is RelationshipType.OWNS for p in preds):
            crit.append("OWNERSHIP_INVENTED")
    unsupported = sum(1 for p in preds
                      if p.explicitness is Explicitness.UNSUPPORTED_INFERENCE
                      or cooccurrence_case)

    # provenance
    prov_total = sum(len(p.source_provenance) for p in preds)
    prov_complete = sum(1 for p in preds for sp in p.source_provenance if sp.is_complete())
    if any(not sp.is_complete() for p in preds for sp in p.source_provenance):
        crit.append("PROVENANCE_MISSING")

    # conflict
    conflict_detected = len(record.relationship_conflicts) > 0
    if case.expected_conflicts > 0 and not conflict_detected:
        crit.append("CONFLICT_HIDDEN")

    # gaps
    detected_gaps = {g.gap_code for g in record.unresolved_relationship_gaps}
    has_expected = bool(case.expected_gaps)
    gaps_all = set(case.expected_gaps) <= detected_gaps if has_expected else True
    if case.upstream_gaps and GapCode.INSUFFICIENT_RETRIEVAL_EVIDENCE not in detected_gaps:
        crit.append("UPSTREAM_GAP_IGNORED")

    return CaseScore(
        case_id=case.case_id, n_gold=len(case.gold), n_pred=len(preds),
        tp=tp, fp=fp, subj_ok=subj_ok, obj_ok=obj_ok, pred_ok=pred_ok, dir_ok=dir_ok,
        pol_ok=pol_ok, pol_total=pol_total, mod_ok=mod_ok, mod_total=mod_total,
        temp_ok=temp_ok, temp_total=temp_total, scope_ok=scope_ok, scope_total=scope_total,
        cond_ok=cond_ok, cond_total=cond_total, exc_ok=exc_ok, exc_total=exc_total,
        matched=len(matches), exact_triple=exact, full_structure=full,
        prov_complete=prov_complete, prov_total=prov_total,
        conflict_expected=case.expected_conflicts > 0, conflict_detected=conflict_detected,
        gaps_expected_all=gaps_all, has_expected_gaps=has_expected,
        cooccurrence_case=cooccurrence_case, cooccurrence_fp=cooccurrence_fp,
        unsupported_assertions=unsupported, crit=tuple(sorted(set(crit))))


def _tokovlp(a: str, b: str) -> bool:
    ta = set(a.lower().split())
    tb = set(b.lower().split())
    return bool(ta & tb)


def aggregate(scores: Sequence[CaseScore]) -> Dict[str, object]:
    def s(f):
        return sum(f(x) for x in scores)

    tp, fp = s(lambda x: x.tp), s(lambda x: x.fp)
    n_gold = s(lambda x: x.n_gold)
    precision = round(tp / (tp + fp), 4) if (tp + fp) else 1.0
    recall = round(tp / n_gold, 4) if n_gold else 1.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) else 0.0

    matched = s(lambda x: x.matched) or 1

    def acc(ok, tot):
        t = s(tot)
        return round(s(ok) / t, 4) if t else 1.0

    # conflict detection
    conf_exp = [x for x in scores if x.conflict_expected]
    conf_pred = [x for x in scores if x.conflict_detected]
    c_recall = round(sum(1 for x in conf_exp if x.conflict_detected) / len(conf_exp), 4) if conf_exp else 1.0
    c_prec = round(sum(1 for x in conf_pred if x.conflict_expected) / len(conf_pred), 4) if conf_pred else 1.0
    c_f1 = round(2 * c_prec * c_recall / (c_prec + c_recall), 4) if (c_prec + c_recall) else 0.0

    gap_cases = [x for x in scores if x.has_expected_gaps]
    gap_acc = round(sum(1 for x in gap_cases if x.gaps_expected_all) / len(gap_cases), 4) if gap_cases else 1.0

    cooc = [x for x in scores if x.cooccurrence_case]
    cooc_fp = round(sum(1 for x in cooc if x.cooccurrence_fp) / len(cooc), 4) if cooc else 0.0

    total_pred = s(lambda x: x.n_pred) or 1
    unsupported_rate = round(s(lambda x: x.unsupported_assertions) / total_pred, 4)

    crit_counts: Dict[str, int] = {}
    for x in scores:
        for c in x.crit:
            crit_counts[c] = crit_counts.get(c, 0) + 1
    for k in ("OWNERSHIP_INVENTED", "AUTHORIZATION_INVERTED", "PROHIBITION_DROPPED",
              "NEGATION_LOST", "DIRECTION_REVERSED", "MUST_MAY_COLLAPSE",
              "ALLEGATION_TREATED_AS_FACT", "SUPERSEDED_RELATION_TREATED_AS_CURRENT",
              "CONDITION_DROPPED", "EXCEPTION_DROPPED", "CONFLICT_HIDDEN",
              "PROVENANCE_MISSING", "UNSUPPORTED_RELATIONSHIP_EMITTED", "UPSTREAM_GAP_IGNORED"):
        crit_counts.setdefault(k, 0)

    return {
        "n_cases": len(scores),
        "relationship_precision": precision,
        "relationship_recall": recall,
        "relationship_f1": f1,
        "subject_accuracy": acc(lambda x: x.subj_ok, lambda x: x.matched),
        "predicate_accuracy": acc(lambda x: x.pred_ok, lambda x: x.matched),
        "object_accuracy": acc(lambda x: x.obj_ok, lambda x: x.matched),
        "direction_accuracy": acc(lambda x: x.dir_ok, lambda x: x.matched),
        "polarity_accuracy": acc(lambda x: x.pol_ok, lambda x: x.pol_total),
        "modality_accuracy": acc(lambda x: x.mod_ok, lambda x: x.mod_total),
        "temporality_accuracy": acc(lambda x: x.temp_ok, lambda x: x.temp_total),
        "scope_accuracy": acc(lambda x: x.scope_ok, lambda x: x.scope_total),
        "condition_accuracy": acc(lambda x: x.cond_ok, lambda x: x.cond_total),
        "exception_accuracy": acc(lambda x: x.exc_ok, lambda x: x.exc_total),
        "ontology_normalization_accuracy": acc(lambda x: x.pred_ok, lambda x: x.matched),
        "exact_triple_accuracy": acc(lambda x: x.exact_triple, lambda x: x.matched),
        "full_structure_accuracy": acc(lambda x: x.full_structure, lambda x: x.matched),
        "provenance_completeness": round(s(lambda x: x.prov_complete) / (s(lambda x: x.prov_total) or 1), 4)
        if s(lambda x: x.prov_total) else 1.0,
        "conflict_detection_precision": c_prec,
        "conflict_detection_recall": c_recall,
        "conflict_detection_f1": c_f1,
        "gap_detection_accuracy": gap_acc,
        "cooccurrence_false_positive_rate": cooc_fp,
        "unsupported_relationship_rate": unsupported_rate,
        "critical_failures": crit_counts,
        "severe_critical_failure_count": sum(crit_counts.values()),
    }
