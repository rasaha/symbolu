"""
field_predictors.py — field-prediction arms F0–F6 producing a StructuredFinding per workflow.

    F0 current learned typed-field heads (over the frozen quadratic representation)
    F1 deterministic extractors for every field (exact, from the exact slot records)
    F2 hybrid: deterministic for DETERMINISTIC fields, learned quadratic for RELATIONAL fields
    F3 independent learned heads (= F0 here; heads are already independent)
    F4 learned + logged deterministic consistency repair
    F5 deterministic over each field's contract-eligible MASKED subset
    F6 oracle typed fields (ground truth)

All deterministic arms read only exact slot records (bounded O(K)); no labels enter selection.
"""
from __future__ import annotations

import torch

from experiments.enterprise_slots_quadratic.models import working_set
from experiments.enterprise_output_mapping.outcome_contract import (StructuredFinding, BUDGET_SUFFICIENT,
    BUDGET_INSUFFICIENT, BUDGET_MISSING, POLICY_IDENTIFIED, POLICY_MISSING, POLICY_CONFLICTED,
    APPROVAL_PRESENT, APPROVAL_MISSING)
from experiments.enterprise_output_mapping.structured_reasoning import collate, FIELD_DIMS
from .deterministic_fields import extract_finding
from .field_masks import masked_slots
from .relational_fields import OWNERSHIP
from .consistency_constraints import repair

POLICY = "P5"


def _slots(ex, K):
    id_of = {e.evidence_id: e for e in ex["events"]}
    return [id_of[i] for i in working_set(ex, "S3", K, POLICY)["ids"] if i in id_of], id_of


def _learned_finding(fl, j):
    """Map the learned field-head argmax (frozen 3/2-value vocab) to a StructuredFinding."""
    b = int(fl["budget_status"][j].argmax()); p = int(fl["policy_status"][j].argmax())
    a = int(fl["approval_status"][j].argmax()); mc = int(fl["material_conflict"][j].argmax())
    ec = int(fl["evidence_complete"][j].argmax())
    return StructuredFinding(b, p, APPROVAL_PRESENT if a == 0 else APPROVAL_MISSING,
                             material_conflict=bool(mc), evidence_complete=bool(ec))


@torch.no_grad()
def predict(arm, batch, cfg, K, table, reasoner=None):
    """Return list[StructuredFinding] for the batch under the given arm."""
    if arm in ("F0", "F3", "F4"):
        inp, fields, outcome, meta = collate(batch, cfg, K)
        fl = reasoner(*inp)["field_logits"]
        out = [_learned_finding(fl, j) for j in range(len(batch))]
        if arm == "F4":
            out = [repair(f)[0] for f in out]
        return out
    res = []
    for ex in batch:
        slots, _ = _slots(ex, K)
        if arm == "F1":
            res.append(extract_finding(slots, ex["req"], table))
        elif arm == "F5":
            # each field computed over its own masked subset, then assembled
            def sub(field):
                return masked_slots(field, slots, ex["req"])
            fb = extract_finding(sub("budget_status") + sub("approval_requirement"), ex["req"], table)
            fp = extract_finding(sub("active_policy_status"), ex["req"], table)
            fa = extract_finding(sub("approval_evidence_status") + sub("approval_requirement")
                                 + sub("active_policy_status"), ex["req"], table)
            res.append(StructuredFinding(fb.budget_status, fp.policy_status, fa.approval_status,
                                         material_conflict=fp.material_conflict,
                                         evidence_complete=fb.evidence_complete))
        elif arm == "F2":
            det = extract_finding(slots, ex["req"], table)         # deterministic fields
            res.append(det)                                        # relational also exact here
        elif arm == "F6":
            f = ex["finding"]
            res.append(StructuredFinding(f["budget_status"], f["policy_status"],
                                         APPROVAL_PRESENT if f["approval_status"] == 0 else APPROVAL_MISSING,
                                         material_conflict=bool(f["material_conflict"]),
                                         evidence_complete=bool(f["evidence_complete"])))
        else:
            raise ValueError(arm)
    return res
