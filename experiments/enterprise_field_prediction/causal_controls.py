"""
causal_controls.py — §12 controls + §9 leak audit for the deterministic field extractors.

Deterministic fields must (a) be label-invariant in their evidence routing, (b) degrade when their
required support is removed, and (c) be invariant to shuffling of non-supporting evidence.
"""
from __future__ import annotations

import copy
import torch

from experiments.enterprise_slots_quadratic.models import working_set
from experiments.enterprise_output_mapping.outcome_contract import decide
from .field_predictors import predict, _slots, POLICY
from .field_masks import field_mask


def leak_audit(data, cfg, K):
    """Field masks + deterministic extraction must be invariant to label perturbation."""
    ok = True
    for ex in data:
        slots, _ = _slots(ex, K)
        m1 = {f: field_mask(f, slots, ex["req"]) for f in ("budget_status", "active_policy_status",
                                                           "approval_evidence_status")}
        ex2 = {**ex, "outcome": (ex["outcome"] + 1) % 5,
               "finding": {k: 0 for k in ex["finding"]}, "required_role": -9}
        slots2, _ = _slots(ex2, K)
        m2 = {f: field_mask(f, slots2, ex2["req"]) for f in m1}
        ok = ok and (slots == slots2) and (m1 == m2)
    return {"label_invariant_routing": bool(ok)}


def _remove_support(ex, tag):
    ex2 = copy.deepcopy(ex)
    ex2["events"] = [e for e in ex2["events"] if e.tag != tag]
    return ex2


@torch.no_grad()
def support_removal(data, cfg, K, table):
    """Removing a field's required support must damage the corresponding field/outcome."""
    def acc(ds):
        f = predict("F1", ds, cfg, K, table)
        return sum(int(max(decide(fi), 0) == ex["outcome"]) for ex, fi in zip(ds, f)) / max(1, len(ds))
    base = acc(data)
    no_budget = acc([_remove_support(ex, "budget") for ex in data])
    no_policy = acc([_remove_support(ex, "policy_active") for ex in data])
    return {"base": base, "remove_budget": no_budget, "remove_active_policy": no_policy,
            "budget_is_causal": no_budget < base - 0.05, "policy_is_causal": no_policy < base - 0.05}
