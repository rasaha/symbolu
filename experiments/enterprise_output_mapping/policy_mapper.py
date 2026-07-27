"""
policy_mapper.py — O1: deterministic policy-table / contract mapper.

Applies the transparent outcome contract (`decide`) to the argmax of the predicted typed fields.
No learned parameters; fully auditable.
"""
from __future__ import annotations

import torch

from .outcome_contract import StructuredFinding, decide, ABSTAIN_INCOMPLETE_EVIDENCE
from .structured_reasoning import FIELD_DIMS


def fields_argmax(field_logits):
    return {k: field_logits[k].argmax(-1) for k in FIELD_DIMS}


def finding_at(fields, i, unauthorized=False):
    return StructuredFinding(
        budget_status=int(fields["budget_status"][i]),
        policy_status=int(fields["policy_status"][i]),
        approval_status=int(fields["approval_status"][i]),
        material_conflict=bool(int(fields["material_conflict"][i])),
        evidence_complete=bool(int(fields["evidence_complete"][i])),
        unauthorized_present=unauthorized)


def o1_policy_map(reasoner_out, meta, device="cpu"):
    fields = fields_argmax(reasoner_out["field_logits"])
    B = fields["budget_status"].shape[0]
    out = torch.zeros(B, dtype=torch.long, device=device)
    for i in range(B):
        o = decide(finding_at(fields, i, meta[i]["unauthorized_included"]))
        out[i] = max(o, 0)                       # INVALID_RUN(-1) surfaces as blocked; clamp for metric
    return out
