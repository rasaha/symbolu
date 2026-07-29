"""
evaluate.py — §11 metrics, §13 capacity study, §15 acceptance criteria.

Everything is computed from real model outputs on the held-out (unseen entity/template/wording)
split. Structural invariants (evidence-ID preservation, unauthorized inclusion) are measured, not
assumed. Attention diagnostics come from the recorded K×K event-attention matrices.
"""
from __future__ import annotations

import statistics as st
from collections import defaultdict
from typing import Dict, List, Optional

from .datasets import (Instance, RELATIONAL_FAMILIES, FAMILIES, ABSTAIN, CONFLICT, N_CLASS)
from .event_schema import Slot
from .normalization_bridge import build_working_set, schema_valid, evidence_id_preservation
from .event_attention import attention_entropy, mass_on
from .model_arms import EventArm, DeterministicArm, IntegratedArm, TokenArm


def _argmax(logits) -> int:
    row = logits.data[0]
    return max(range(len(row)), key=lambda k: row[k])


def predict(arm, inst, source: str, K: Optional[int] = None) -> int:
    if isinstance(arm, DeterministicArm):
        ans, _ = arm.predict(inst, source, K=K)
        return ans
    logits, _, _ = arm.logits(inst, source, K=K)
    return _argmax(logits)


# ---------------- core accuracy tables ----------------
def per_family_accuracy(arm, data: List[Instance], source: str, K: Optional[int] = None) -> Dict[str, float]:
    d = defaultdict(lambda: [0, 0])
    for inst in data:
        ok = predict(arm, inst, source, K) == inst.gold_answer
        d[inst.query.task_family][0] += ok
        d[inst.query.task_family][1] += 1
    return {f: c / n for f, (c, n) in d.items()}


def macro(acc: Dict[str, float], subset=None) -> float:
    keys = [f for f in acc if (subset is None or f in subset)]
    return st.mean(acc[f] for f in keys) if keys else 0.0


def arm_scores(arm, data: List[Instance], source: str, K: Optional[int] = None) -> Dict:
    acc = per_family_accuracy(arm, data, source, K)
    return {
        "per_family": acc,
        "macro_all": macro(acc),
        "macro_relational": macro(acc, RELATIONAL_FAMILIES),
        "overall": sum(predict(arm, i, source, K) == i.gold_answer for i in data) / len(data),
    }


# ---------------- diagnostic metrics (§11) ----------------
def conflict_f1(arm, data: List[Instance], source: str) -> float:
    tp = fp = fn = 0
    for inst in data:
        pred = predict(arm, inst, source)
        gold_c = inst.gold_answer == CONFLICT
        pred_c = pred == CONFLICT
        tp += gold_c and pred_c
        fp += (not gold_c) and pred_c
        fn += gold_c and (not pred_c)
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    return 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0


def abstention_pr(arm, data: List[Instance], source: str) -> Dict[str, float]:
    tp = fp = fn = 0
    for inst in data:
        pred = predict(arm, inst, source)
        gold_a = inst.gold_answer == ABSTAIN
        pred_a = pred == ABSTAIN
        tp += gold_a and pred_a
        fp += (not gold_a) and pred_a
        fn += gold_a and (not pred_a)
    return {"precision": tp / (tp + fp) if (tp + fp) else 1.0,
            "recall": tp / (tp + fn) if (tp + fn) else 1.0}


def family_accuracy(arm, data, source, families) -> float:
    sub = [i for i in data if i.query.task_family in families]
    if not sub:
        return 0.0
    return sum(predict(arm, i, source) == i.gold_answer for i in sub) / len(sub)


# ---------------- admission / survival / integrity ----------------
def admission_stats(data: List[Instance], source: str, K: int) -> Dict:
    surv, id_pres, irr_occ, dup_occ = [], [], [], []
    unauthorized = 0
    for inst in data:
        recs = inst.oracle_records if source == "oracle" else inst.predicted_records
        slots, rep = build_working_set(recs, inst.query, K)
        admitted = set(s.evidence_id for s in slots)
        req = set(inst.required_ids)
        surv.append(1.0 if req and req.issubset(admitted) else (1.0 if not req else 0.0))
        id_pres.append(evidence_id_preservation(slots))
        # irrelevant occupancy: admitted slots that are neither required nor chain-subject
        irr = sum(1 for s in slots if s.evidence_id not in req and s.record.subject_id >= 900)
        irr_occ.append(irr / max(1, len(slots)))
        seen = set()
        dup = 0
        for s in slots:
            k = s.record.identity_tuple()
            if k in seen:
                dup += 1
            seen.add(k)
        dup_occ.append(dup / max(1, len(slots)))
        # unauthorized inclusion: any ADMITTED slot violating access/tenant (0 by construction)
        unauthorized += sum(1 for s in slots if not s.record.readable_by(inst.query.reader_role)
                            or s.record.tenant_id != inst.query.tenant_id)
    return {
        "required_survival": st.mean(surv),
        "evidence_id_preservation": st.mean(id_pres),
        "irrelevant_occupancy": st.mean(irr_occ),
        "duplicate_occupancy": st.mean(dup_occ),
        "unauthorized_inclusion": unauthorized / max(1, sum(len(
            i.oracle_records if source == "oracle" else i.predicted_records) for i in data)),
    }


def conditional_accuracy(arm, data: List[Instance], source: str, K: int) -> float:
    """Final accuracy | all required events survived admission (§13 conditional accuracy)."""
    ok = tot = 0
    for inst in data:
        recs = inst.oracle_records if source == "oracle" else inst.predicted_records
        slots, _ = build_working_set(recs, inst.query, K)
        admitted = set(s.evidence_id for s in slots)
        req = set(inst.required_ids)
        if req and not req.issubset(admitted):
            continue
        tot += 1
        ok += predict(arm, inst, source, K) == inst.gold_answer
    return ok / tot if tot else 0.0


# ---------------- attention diagnostics (§11) ----------------
def attention_diagnostics(arm: EventArm, data: List[Instance], source: str, K: int) -> Dict:
    ent, req_mass, irr_mass, attrib = [], [], [], []
    for inst in data:
        recs = inst.oracle_records if source == "oracle" else inst.predicted_records
        slots, _ = build_working_set(recs, inst.query, K)
        logits, A, attribution = arm.logits(inst, source, K=K, override_slots=slots)
        ent.append(attention_entropy(A))
        req = set(inst.required_ids)
        req_idx = [i for i, s in enumerate(slots) if s.evidence_id in req]
        irr_idx = [i for i, s in enumerate(slots) if s.record.subject_id >= 900]
        req_mass.append(mass_on(A, req_idx))
        irr_mass.append(mass_on(A, irr_idx))
        # event-attribution: does the readout attend most to a required slot?
        w = getattr(arm.attn, "_last_readout", [])
        if req_idx and w:
            top = max(range(len(w)), key=lambda j: w[j] if j < len(w) else -1)
            attrib.append(1.0 if top in req_idx else 0.0)
    return {
        "event_attention_entropy": st.mean(ent) if ent else 0.0,
        "attention_to_required": st.mean(req_mass) if req_mass else 0.0,
        "attention_to_irrelevant": st.mean(irr_mass) if irr_mass else 0.0,
        "attribution_exact_match": st.mean(attrib) if attrib else 1.0,
    }


# ---------------- extraction-quality metrics (data level, §11) ----------------
def extraction_metrics(data: List[Instance]) -> Dict:
    exact = span = ent = schema = 0
    tot = 0
    for inst in data:
        oracle_by_id = {r.evidence_id: r for r in inst.oracle_records}
        for p in inst.predicted_records:
            tot += 1
            schema += 1 if schema_valid(p)[0] else 0
            o = oracle_by_id.get(p.evidence_id)
            if o is None:
                continue
            exact += 1 if (p.identity_tuple() == o.identity_tuple()
                           and p.normalized_value == o.normalized_value
                           and p.status == o.status and p.version == o.version) else 0
            span += 1 if p.source_span == o.source_span else 0
            ent += 1 if (p.subject_id == o.subject_id and p.object_id_or_value == o.object_id_or_value) else 0
    return {
        "event_extraction_exact_match": exact / tot if tot else 0.0,
        "event_schema_validity": schema / tot if tot else 0.0,
        "source_span_exact_match": span / tot if tot else 0.0,
        "entity_linking_accuracy": ent / tot if tot else 0.0,
    }
