"""
oracle_interventions.py — §6 one-field oracle replacement to rank fields by CAUSAL contribution to
final-outcome error (not correlation). Replaces one predicted field at a time with ground truth in
the F0 learned findings and measures the final-accuracy gain.
"""
from __future__ import annotations

import torch

from experiments.enterprise_output_mapping.outcome_contract import (decide, APPROVAL_PRESENT, APPROVAL_MISSING)
from experiments.enterprise_output_mapping.structured_reasoning import collate
from .field_predictors import _learned_finding

FIELDS = ("budget_status", "policy_status", "approval_status", "material_conflict", "evidence_complete")


def _override(f, field, ex):
    tv = ex["finding"][field]
    kw = dict(budget_status=f.budget_status, policy_status=f.policy_status,
              approval_status=f.approval_status, material_conflict=f.material_conflict,
              evidence_complete=f.evidence_complete)
    if field == "approval_status":
        kw["approval_status"] = APPROVAL_PRESENT if tv == 0 else APPROVAL_MISSING
    elif field in ("material_conflict", "evidence_complete"):
        kw[field] = bool(tv)
    else:
        kw[field] = tv
    from experiments.enterprise_output_mapping.outcome_contract import StructuredFinding
    return StructuredFinding(**kw)


@torch.no_grad()
def one_field_oracle(reasoner, data, cfg, K, bs=64):
    base = 0; gains = {f: 0 for f in FIELDS}; n = 0
    for i in range(0, len(data), bs):
        b = data[i:i + bs]
        inp, fields, outcome, meta = collate(b, cfg, K)
        fl = reasoner(*inp)["field_logits"]
        for j, ex in enumerate(b):
            f0 = _learned_finding(fl, j); n += 1
            base += int(max(decide(f0), 0) == ex["outcome"])
            for field in FIELDS:
                gains[field] += int(max(decide(_override(f0, field, ex)), 0) == ex["outcome"])
    base /= max(1, n)
    ranked = sorted(((f, gains[f] / max(1, n) - base) for f in FIELDS), key=lambda x: -x[1])
    return {"base_accuracy": base, "oracle_gain": {f: gains[f] / max(1, n) - base for f in FIELDS},
            "ranked_load_bearing": ranked}
