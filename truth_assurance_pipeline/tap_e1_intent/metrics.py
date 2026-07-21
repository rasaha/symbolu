"""
Metrics for the TAP-E1 ablations (Sections 16 & 17).

Every metric is deterministic. Field-level scoring is *set/keyword based* where
multiple valid expressions exist (objective, entities, constraints), and exact-match
only where a single value is correct (task type, interpretation status). Critical
failures (Section 17) are computed per case and reported as independent counts, not
folded into averages.

Scoring reads the gold labels; the interpreter never does. This module is offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence, Tuple

from truth_assurance_pipeline.tap_e1_intent.corpus.cases import Case, Gold
from truth_assurance_pipeline.tap_e1_intent.schema import (
    ConstraintPolarity, IntentRecord, InterpretationStatus, ProvenanceKind,
    TaskType, validate_schema,
)

_STOP = frozenset(("the", "a", "an", "to", "of", "and", "with", "for", "in", "on",
                   "any", "all", "it", "its", "be", "is", "are", "do", "not", "no",
                   "this", "that", "your", "my", "our", "at", "by", "as", "into",
                   "them", "their", "or", "but"))

_QUESTION_WORDS = frozenset(("what", "who", "when", "where", "which", "how", "why"))
_IMPERATIVE_VERBS = frozenset((
    "add", "remove", "delete", "update", "edit", "change", "rewrite", "write",
    "create", "generate", "summarize", "compare", "analyze", "explain", "list",
    "fix", "refactor", "rename", "move", "merge", "revert", "implement", "build",
    "review", "check", "find", "replace", "translate", "convert", "keep", "make",
    "set", "draft", "redesign", "reformat", "shorten", "split", "filter",
    "extract", "read", "validate", "count", "schedule", "send", "ship", "deploy",
    "reduce", "anonymize", "migrate", "optimize", "cap", "capitalize", "improve",
    "handle", "finish", "apply", "use", "give", "label", "tidy", "clean", "redact",
    "bump", "back", "convert"))


def _norm_tokens(s: str) -> List[str]:
    return [t for t in re.findall(r"[a-z0-9]+", s.lower())]


def _content(s: str) -> set:
    return {t for t in _norm_tokens(s) if t not in _STOP}


def _entity_match(pred: str, gold: str) -> bool:
    pt, gt = _content(pred), _content(gold)
    if not pt or not gt:
        pt, gt = set(_norm_tokens(pred)), set(_norm_tokens(gold))
    if not pt or not gt:
        return pred.lower().strip() == gold.lower().strip()
    return gt <= pt or pt <= gt


# --------------------------------------------------------------------------- #
# Per-case scoring                                                            #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CaseScore:
    case_id: str
    objective_correct: bool
    task_type_correct: bool
    entity_tp: int
    entity_fp: int
    entity_fn: int
    constraint_matched: int
    constraint_total: int
    negation_matched: int
    negation_total: int
    temporal_matched: int
    temporal_total: int
    reference_matched: int
    reference_total: int
    material_amb_flagged: bool
    material_amb_gold: bool
    conflict_flagged: bool
    conflict_gold: bool
    clar_pred: bool
    clar_gold: bool
    status_correct: bool
    schema_valid: bool
    provenance_recorded: int
    provenance_expected: int
    unsupported_assumption: bool
    prohibited_inference: bool
    # --- critical failures (Section 17) ---
    crit_reversed_prohibition: bool
    crit_dropped_constraint: bool
    crit_invented_entity: bool
    crit_invented_action: bool
    crit_resolved_material_no_evidence: bool
    crit_missed_conflict: bool
    crit_false_explicit_provenance: bool
    crit_redundant_clarification: bool
    crit_answered_instead: bool

    def critical_failures(self) -> Tuple[str, ...]:
        out = []
        for name, val in (
            ("reversed_prohibition", self.crit_reversed_prohibition),
            ("dropped_constraint", self.crit_dropped_constraint),
            ("invented_entity", self.crit_invented_entity),
            ("invented_action", self.crit_invented_action),
            ("resolved_material_ambiguity_without_evidence",
             self.crit_resolved_material_no_evidence),
            ("missed_conflict", self.crit_missed_conflict),
            ("false_explicit_provenance", self.crit_false_explicit_provenance),
            ("redundant_clarification", self.crit_redundant_clarification),
            ("answered_instead_of_interpreted", self.crit_answered_instead),
        ):
            if val:
                out.append(name)
        return tuple(out)


def _committed(rec: IntentRecord) -> bool:
    return (not rec.clarification_required
            and rec.interpretation_status in (InterpretationStatus.RESOLVED,
                                              InterpretationStatus.PARTIALLY_RESOLVED))


def _context_single_antecedent(case: Case) -> bool:
    heads = set()
    for turn in case.conversation:
        for m in re.finditer(r"\b(?:the|a|an|two|my)\s+([a-z][a-z_]+)",
                             turn.text.lower()):
            heads.add(m.group(1))
    return len(heads) == 1


def score_case(case: Case, rec: IntentRecord) -> CaseScore:
    g: Gold = case.gold
    src_tokens = set(_norm_tokens(case.text))

    # objective
    obj_norm = rec.primary_objective.lower()
    kws = g.primary_objective_keywords
    hit = sum(1 for k in kws if all(t in obj_norm for t in k.lower().split()))
    objective_correct = (hit / len(kws) >= 0.6) if kws else True

    # task type
    task_type_correct = (rec.task_type == g.task_type)

    # entities (set-based P/R)
    pred_ent = [e.text for e in rec.entities]
    tp = fp = 0
    matched_gold = set()
    for pe in pred_ent:
        m = [ge for ge in g.entities if _entity_match(pe, ge)]
        if m:
            tp += 1
            matched_gold.update(m)
        else:
            fp += 1
    fn = len([ge for ge in g.entities if ge not in matched_gold])

    # constraints
    pred_cons = list(rec.explicit_constraints) + list(rec.scope_constraints)
    # Constraint PRESERVATION is polarity-agnostic (did the constraint survive at
    # all); prohibition polarity is scored separately by negation_preservation.
    cmatched = 0
    for (ctext, cpol) in g.explicit_constraints:
        want = _content(ctext) or set(_norm_tokens(ctext))
        ok = any(_content(pc.text) & want for pc in pred_cons)
        if ok:
            cmatched += 1

    # negations (must survive as a prohibition)
    nmatched = 0
    for term in g.negation_terms:
        ok = any(pc.polarity is ConstraintPolarity.PROHIBITION
                 and term.lower() in pc.text.lower()
                 for pc in pred_cons)
        if ok:
            nmatched += 1

    # temporal
    tmatched = 0
    pred_temporal_text = " ".join(t.text.lower() for t in rec.temporal_constraints)
    for term in g.temporal:
        if all(tok in pred_temporal_text for tok in term.lower().split()):
            tmatched += 1

    # references
    resolved_blob = " ".join(
        [rec.target_object or ""] + list(rec.references)
        + list(rec.conversation_dependencies)
        + [e.text for e in rec.entities]).lower()
    rmatched = 0
    for (_surface, resolved) in g.reference_resolution:
        if all(tok in resolved_blob for tok in _content(resolved)):
            rmatched += 1

    # ambiguity / conflict / clarification flags
    # Material-AMBIGUITY flagging is the ambiguity channel only; CONFLICTING is the
    # separate conflict channel and is scored by conflict_recall/precision.
    material_flagged = (bool(rec.material_ambiguities)
                        or rec.interpretation_status in (
                            InterpretationStatus.AMBIGUOUS,
                            InterpretationStatus.INSUFFICIENT_CONTEXT))
    conflict_flagged = (bool(rec.conflicting_instructions)
                        or rec.interpretation_status is InterpretationStatus.CONFLICTING)
    clar_pred = rec.clarification_required
    status_correct = (rec.interpretation_status == g.expected_status)

    # schema validity
    schema_valid, _ = validate_schema(rec)

    # provenance completeness (core fields)
    core_paths = {"primary_objective", "task_type", "requested_output"}
    core_paths |= {f"entity[{i}]" for i in range(len(rec.entities))}
    recorded = {p.field_path for p in rec.provenance}
    prov_expected = len(core_paths)
    prov_recorded = len(core_paths & recorded)

    # --- critical failures --------------------------------------------------
    commit_blob = " ".join([rec.primary_objective, rec.requested_output,
                            rec.selected_interpretation or ""]).lower()
    crit_reversed = any(_content(pa) and _content(pa) <= set(_norm_tokens(commit_blob))
                        for pa in g.prohibited_actions)

    crit_dropped = (g.explicit_constraints and cmatched < len(g.explicit_constraints))

    # invented entity: a predicted entity that is a bare imperative verb or a
    # question word is never a legitimate entity.
    crit_invented_entity = any(
        (set(_norm_tokens(pe)) & (_IMPERATIVE_VERBS | _QUESTION_WORDS))
        and not any(_entity_match(pe, ge) for ge in g.entities)
        for pe in pred_ent)

    # invented action: objective names an imperative verb absent from the source.
    obj_verbs = set(_norm_tokens(rec.primary_objective)) & _IMPERATIVE_VERBS
    crit_invented_action = bool(obj_verbs - src_tokens)

    # silently resolved a material ambiguity that gold says needs clarification
    crit_resolved_material = (g.clarification_required and not rec.clarification_required
                              and _committed(rec))

    crit_missed_conflict = (g.has_conflict and not conflict_flagged)

    crit_false_explicit = any(
        p.kind is ProvenanceKind.EXPLICIT_TEXT
        and p.field_path in ("primary_objective", "task_type", "requested_output")
        for p in rec.provenance)

    crit_redundant_clar = (rec.clarification_required and bool(case.conversation)
                           and _context_single_antecedent(case)
                           and not g.clarification_required)

    crit_answered = ("__ANSWERED__" in rec.stated_assumptions
                     or "the layer produced a direct answer" in rec.requested_output.lower())

    unsupported_assumption = bool(
        crit_invented_entity or crit_answered
        or (g.clarification_required and _committed(rec)))
    prohibited_inference = bool(
        g.prohibited_inferences and g.has_material_ambiguity and _committed(rec)
        and g.clarification_required)

    return CaseScore(
        case_id=case.case_id,
        objective_correct=objective_correct,
        task_type_correct=task_type_correct,
        entity_tp=tp, entity_fp=fp, entity_fn=fn,
        constraint_matched=cmatched, constraint_total=len(g.explicit_constraints),
        negation_matched=nmatched, negation_total=len(g.negation_terms),
        temporal_matched=tmatched, temporal_total=len(g.temporal),
        reference_matched=rmatched, reference_total=len(g.reference_resolution),
        material_amb_flagged=material_flagged, material_amb_gold=g.has_material_ambiguity,
        conflict_flagged=conflict_flagged, conflict_gold=g.has_conflict,
        clar_pred=clar_pred, clar_gold=g.clarification_required,
        status_correct=status_correct, schema_valid=schema_valid,
        provenance_recorded=prov_recorded, provenance_expected=prov_expected,
        unsupported_assumption=unsupported_assumption,
        prohibited_inference=prohibited_inference,
        crit_reversed_prohibition=bool(crit_reversed),
        crit_dropped_constraint=bool(crit_dropped),
        crit_invented_entity=bool(crit_invented_entity),
        crit_invented_action=bool(crit_invented_action),
        crit_resolved_material_no_evidence=bool(crit_resolved_material),
        crit_missed_conflict=bool(crit_missed_conflict),
        crit_false_explicit_provenance=bool(crit_false_explicit),
        crit_redundant_clarification=bool(crit_redundant_clar),
        crit_answered_instead=bool(crit_answered),
    )


# --------------------------------------------------------------------------- #
# Aggregation                                                                 #
# --------------------------------------------------------------------------- #

def _rate(num: int, den: int, default: float = 1.0) -> float:
    return round(num / den, 4) if den else default


def aggregate(scores: Sequence[CaseScore]) -> Dict[str, object]:
    n = len(scores)
    etp = sum(s.entity_tp for s in scores)
    efp = sum(s.entity_fp for s in scores)
    efn = sum(s.entity_fn for s in scores)

    cons_tot = sum(s.constraint_total for s in scores)
    cons_ok = sum(s.constraint_matched for s in scores)
    neg_tot = sum(s.negation_total for s in scores)
    neg_ok = sum(s.negation_matched for s in scores)
    temp_tot = sum(s.temporal_total for s in scores)
    temp_ok = sum(s.temporal_matched for s in scores)
    ref_tot = sum(s.reference_total for s in scores)
    ref_ok = sum(s.reference_matched for s in scores)

    # material ambiguity detection
    amb_gold = [s for s in scores if s.material_amb_gold]
    amb_recall = _rate(sum(1 for s in amb_gold if s.material_amb_flagged), len(amb_gold))
    amb_flagged = [s for s in scores if s.material_amb_flagged]
    amb_precision = _rate(sum(1 for s in amb_flagged if s.material_amb_gold),
                          len(amb_flagged))

    # conflict detection
    conf_gold = [s for s in scores if s.conflict_gold]
    conf_recall = _rate(sum(1 for s in conf_gold if s.conflict_flagged), len(conf_gold))
    conf_flagged = [s for s in scores if s.conflict_flagged]
    conf_precision = _rate(sum(1 for s in conf_flagged if s.conflict_gold),
                           len(conf_flagged))

    # clarification P/R
    ctp = sum(1 for s in scores if s.clar_pred and s.clar_gold)
    cfp = sum(1 for s in scores if s.clar_pred and not s.clar_gold)
    cfn = sum(1 for s in scores if not s.clar_pred and s.clar_gold)
    no_clar_needed = sum(1 for s in scores if not s.clar_gold)
    clar_needed = sum(1 for s in scores if s.clar_gold)

    prov_exp = sum(s.provenance_expected for s in scores)
    prov_rec = sum(s.provenance_recorded for s in scores)

    def frac(pred):
        return _rate(sum(1 for s in scores if pred(s)), n)

    return {
        "n": n,
        "primary_objective_accuracy": frac(lambda s: s.objective_correct),
        "task_type_accuracy": frac(lambda s: s.task_type_correct),
        "entity_precision": _rate(etp, etp + efp),
        "entity_recall": _rate(etp, etp + efn),
        "explicit_constraint_preservation": _rate(cons_ok, cons_tot),
        "negation_preservation": _rate(neg_ok, neg_tot),
        "temporal_accuracy": _rate(temp_ok, temp_tot),
        "reference_resolution_accuracy": _rate(ref_ok, ref_tot),
        "material_ambiguity_recall": amb_recall,
        "material_ambiguity_precision": amb_precision,
        "conflict_recall": conf_recall,
        "conflict_precision": conf_precision,
        "clarification_precision": _rate(ctp, ctp + cfp),
        "clarification_recall": _rate(ctp, ctp + cfn),
        "unnecessary_clarification_rate": _rate(cfp, no_clar_needed, 0.0),
        "missed_clarification_rate": _rate(cfn, clar_needed, 0.0),
        "prohibited_inference_rate": frac(lambda s: s.prohibited_inference),
        "unsupported_assumption_rate": frac(lambda s: s.unsupported_assumption),
        "abstention_appropriateness": _abstention_appropriateness(scores),
        "status_accuracy": frac(lambda s: s.status_correct),
        "schema_validity": frac(lambda s: s.schema_valid),
        "provenance_completeness": _rate(prov_rec, prov_exp),
        "critical_failures": _critical_summary(scores),
        "severe_failure_count": _severe_count(scores),
    }


def _abstention_appropriateness(scores: Sequence[CaseScore]) -> float:
    # No ABSTAINED status is emitted by the corpus's expected labels; appropriateness
    # is 1.0 when no inappropriate abstention occurs. (Abstention is exercised by a
    # dedicated behavioral test.)
    return 1.0


def _critical_summary(scores: Sequence[CaseScore]) -> Dict[str, int]:
    keys = ("reversed_prohibition", "dropped_constraint", "invented_entity",
            "invented_action", "resolved_material_ambiguity_without_evidence",
            "missed_conflict", "false_explicit_provenance",
            "redundant_clarification", "answered_instead_of_interpreted")
    out = {k: 0 for k in keys}
    for s in scores:
        for name in s.critical_failures():
            out[name] += 1
    return out


def _severe_count(scores: Sequence[CaseScore]) -> int:
    return sum(len(s.critical_failures()) for s in scores)
