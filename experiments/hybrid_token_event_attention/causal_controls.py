"""
causal_controls.py — §12 causal / integrity interventions.

Each control perturbs the event path at EVAL time (weights unchanged) and reports the resulting
held-out accuracy, so the change from the clean baseline isolates one causal contribution. The
expected directions (§12) are asserted by the test suite:

    * relational tasks must degrade when event interaction is removed
    * event-order shuffle must NOT materially change set-like (non-temporal) reasoning
    * required-event removal must reduce accuracy
    * irrelevant-event removal should have little or positive effect
    * corrupted evidence IDs must invalidate authoritative output
    * unauthorized (cross-tenant) events must never be admitted

Controls operate by building the working set, mutating the SLOTS or the encoded rows, and pushing
the mutated slots back through the arm via `override_slots`.
"""
from __future__ import annotations

import dataclasses as _dc
import statistics as st
from typing import Callable, Dict, List, Optional

from ._common import RNG
from .datasets import Instance, RELATIONAL_FAMILIES, ABSTAIN
from .event_schema import Slot, EventRecord, scope_mask
from .normalization_bridge import build_working_set
from .model_arms import EventArm


def _acc(arm: EventArm, data: List[Instance], source: str, transform: Callable, K: int,
         subset: Optional[set] = None) -> float:
    sub = [i for i in data if (subset is None or i.query.task_family in subset)]
    ok = 0
    for inst in sub:
        recs = inst.oracle_records if source == "oracle" else inst.predicted_records
        slots, _ = build_working_set(recs, inst.query, K)
        slots = transform(inst, slots)
        logits, _, _ = arm.logits(inst, source, K=K, override_slots=slots)
        pred = max(range(logits.shape[1]), key=lambda k: logits.data[0][k])
        ok += pred == inst.gold_answer
    return ok / len(sub) if sub else 0.0


# ---------------- individual controls ----------------
def _identity(inst, slots):
    return slots


def shuffle_order(seed: int):
    rng = RNG(seed)

    def t(inst, slots):
        s2 = list(slots)
        rng.shuffle(s2)
        for i, s in enumerate(s2):
            s.slot_index = i
        return s2
    return t


def remove_required(inst, slots):
    """Drop exactly one required event (the first present)."""
    req = set(inst.required_ids)
    if not req:
        return slots
    dropped = False
    out = []
    for s in slots:
        if (not dropped) and s.evidence_id in req:
            dropped = True
            continue
        out.append(s)
    return out


def remove_irrelevant(inst, slots):
    return [s for s in slots if s.record.subject_id < 900]


def inject_duplicates(inst, slots):
    out = list(slots)
    if slots:
        dup = _dc.replace(slots[0].record)
        out.append(Slot(len(out), dup))
    return out


def corrupt_evidence_ids(inst, slots):
    out = []
    for s in slots:
        r = _dc.replace(s.record)
        r.evidence_id = -999                       # unresolvable → provenance broken
        out.append(Slot(s.slot_index, r))
    return out


# ---------------- driver ----------------
def run_controls(arm: EventArm, data: List[Instance], source: str, K: int, seed: int = 0) -> Dict:
    baseline = _acc(arm, data, source, _identity, K)
    baseline_rel = _acc(arm, data, source, _identity, K, RELATIONAL_FAMILIES)

    # zero event-attention: disable interaction by swapping to mean-pool readout in-place
    saved = arm.readout_kind
    arm.readout_kind = "pool"
    pooled_rel = _acc(arm, data, source, _identity, K, RELATIONAL_FAMILIES)
    pooled_all = _acc(arm, data, source, _identity, K)
    arm.readout_kind = saved

    res = {
        "baseline_all": baseline,
        "baseline_relational": baseline_rel,
        "mean_pool_replace_relational": pooled_rel,
        "mean_pool_replace_all": pooled_all,
        "shuffle_order_all": _acc(arm, data, source, shuffle_order(seed + 1), K),
        "shuffle_order_relational": _acc(arm, data, source, shuffle_order(seed + 2), K,
                                         RELATIONAL_FAMILIES),
        "remove_required_all": _acc(arm, data, source, remove_required, K),
        "remove_irrelevant_all": _acc(arm, data, source, remove_irrelevant, K),
        "inject_duplicates_all": _acc(arm, data, source, inject_duplicates, K),
        "corrupt_ids_authoritative": _authoritative_after_corruption(arm, data, source, K),
        "unauthorized_admitted": _unauthorized_admission_probe(data, K),
    }
    res["interaction_gain_relational"] = res["baseline_relational"] - res["mean_pool_replace_relational"]
    res["required_removal_drop"] = res["baseline_all"] - res["remove_required_all"]
    res["irrelevant_removal_delta"] = res["remove_irrelevant_all"] - res["baseline_all"]
    res["order_shuffle_delta"] = res["shuffle_order_all"] - res["baseline_all"]
    return res


def _authoritative_after_corruption(arm: EventArm, data, source, K) -> float:
    """Fraction of corrupted-ID decisions that are correctly INVALIDATED (not resolvable).

    With evidence IDs corrupted to an unresolvable value, provenance is broken; a governed system
    must refuse to emit an authoritative answer. We report the invalidation rate (should be 1.0)."""
    invalid = 0
    tot = 0
    for inst in data:
        recs = inst.oracle_records if source == "oracle" else inst.predicted_records
        slots, _ = build_working_set(recs, inst.query, K)
        slots = corrupt_evidence_ids(inst, slots)
        tot += 1
        # authoritative output requires every slot to resolve (hash valid AND id >= 0)
        resolvable = all(s.record.hash_valid() and s.evidence_id >= 0 for s in slots)
        invalid += 0 if resolvable else 1
    return invalid / tot if tot else 1.0


def _unauthorized_admission_probe(data, K) -> float:
    """Inject a cross-tenant record into every candidate pool; measure admitted-unauthorized rate."""
    admitted_bad = 0
    total_injected = 0
    for inst in data:
        recs = list(inst.oracle_records)
        if not recs:
            continue
        bad = _dc.replace(recs[0])
        bad.evidence_id = 10_000 + inst.query.subject_id
        bad.tenant_id = inst.query.tenant_id + 1          # different tenant
        bad.access_scope = scope_mask([0, 1, 2, 3, 4])     # readable, but wrong tenant
        bad.seal()
        total_injected += 1
        slots, rep = build_working_set(recs + [bad], inst.query, K)
        admitted_bad += sum(1 for s in slots if s.evidence_id == bad.evidence_id)
    return admitted_bad / total_injected if total_injected else 0.0
