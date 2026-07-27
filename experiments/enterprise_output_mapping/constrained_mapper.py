"""
constrained_mapper.py — O2 (constrained rule mapper + hard gates) and O5 (oracle).

O2 = the deterministic contract PLUS confidence/abstention thresholds: when the model's confidence
in a mandatory field (budget / active policy) is below `tau`, it abstains rather than guessing.
Hard gates (§7) fire before any learned mapping and cannot be overridden. O5 applies the contract to
the TRUE typed fields — the mapping ceiling given correct reasoning.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .outcome_contract import (StructuredFinding, decide, ABSTAIN_INCOMPLETE_EVIDENCE,
                               ABSTAIN_MATERIAL_CONFLICT, REVIEW_REQUIRED, INVALID_RUN,
                               POLICY_MISSING, BUDGET_MISSING)
from .policy_mapper import fields_argmax, finding_at
from .structured_reasoning import FIELD_DIMS


def hard_gate(fields, i, meta) -> int:
    """Non-negotiable gates (§7). Returns an outcome index, or None if no gate fires."""
    if meta["unauthorized_included"]:
        return INVALID_RUN
    if int(fields["material_conflict"][i]) == 1 or int(fields["policy_status"][i]) == 2:
        return ABSTAIN_MATERIAL_CONFLICT
    if int(fields["evidence_complete"][i]) == 0 or int(fields["policy_status"][i]) == POLICY_MISSING \
            or int(fields["budget_status"][i]) == BUDGET_MISSING:
        return ABSTAIN_INCOMPLETE_EVIDENCE
    return None


def o2_constrained_map(reasoner_out, meta, tau=0.55, device="cpu"):
    fl = reasoner_out["field_logits"]
    fields = fields_argmax(fl)
    probs = {k: F.softmax(fl[k], -1).max(-1).values for k in FIELD_DIMS}
    B = fields["budget_status"].shape[0]
    out = torch.zeros(B, dtype=torch.long, device=device)
    for i in range(B):
        g = hard_gate(fields, i, meta[i])
        if g is not None:
            out[i] = max(g, 0); continue
        # low confidence in a mandatory field ⇒ abstain rather than guess
        if float(probs["budget_status"][i]) < tau or float(probs["policy_status"][i]) < tau:
            out[i] = ABSTAIN_INCOMPLETE_EVIDENCE; continue
        out[i] = max(decide(finding_at(fields, i, meta[i]["unauthorized_included"])), 0)
    return out


def o5_oracle_map(true_fields, meta, device="cpu"):
    """Contract over the TRUE typed fields (reasoning ceiling)."""
    B = true_fields["budget_status"].shape[0]
    out = torch.zeros(B, dtype=torch.long, device=device)
    for i in range(B):
        out[i] = max(decide(finding_at(true_fields, i, meta[i]["unauthorized_included"])), 0)
    return out
