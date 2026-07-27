"""evaluate.py — per-field + final-mapped metrics (§5/§14) for a field-prediction arm."""
from __future__ import annotations

import torch

from experiments.enterprise_output_mapping.outcome_contract import (decide, N_OUTCOME, OUTCOMES,
    ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT, APPROVAL_PRESENT)
from experiments.enterprise_slots_quadratic.models import working_set
from .field_predictors import predict, POLICY

FIELD_KEYS = ("budget_status", "policy_status", "approval_status", "material_conflict", "evidence_complete")
ABSTAIN_SET = {ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT}


def _finding_fields(f):
    return {"budget_status": f.budget_status, "policy_status": f.policy_status,
            "approval_status": 0 if f.approval_status == APPROVAL_PRESENT else 1,
            "material_conflict": int(f.material_conflict), "evidence_complete": int(f.evidence_complete)}


@torch.no_grad()
def evaluate(arm, data, cfg, K, table, reasoner=None, bs=64):
    field_ok = {k: [0, 0] for k in FIELD_KEYS}
    field_ok_surv = {k: [0, 0] for k in FIELD_KEYS}
    out_ok = macro = 0; n = 0
    conf = {"tp": 0, "fp": 0, "fn": 0}; abst = {"tp": 0, "fp": 0, "fn": 0}
    per = {o: [0, 0, 0] for o in range(N_OUTCOME)}
    ids_ok = unauth = 0
    for i in range(0, len(data), bs):
        b = data[i:i + bs]
        findings = predict(arm, b, cfg, K, table, reasoner)
        for ex, f in zip(b, findings):
            pf = _finding_fields(f); n += 1
            id_of = {e.evidence_id: e for e in ex["events"]}
            ws = working_set(ex, "S3", K, POLICY)
            surv = ex.get("required_ids") and all((r < 0) or (r in ws["ids"]) for r in ex["required_ids"])
            ids_ok += all(eid in id_of for eid in ws["ids"])
            unauth += any(not (id_of[e].tenant_id == ex["tenant"] and id_of[e].readable_by(ex["role_idx"]))
                          for e in ws["ids"] if e in id_of)
            for k in FIELD_KEYS:
                ok = int(pf[k] == ex["finding"][k]); field_ok[k][0] += ok; field_ok[k][1] += 1
                if surv:
                    field_ok_surv[k][0] += ok; field_ok_surv[k][1] += 1
            p = max(decide(f), 0); y = ex["outcome"]
            out_ok += int(p == y); per[y][2] += 1; per[p][1] += 1; per[p][0] += int(p == y)
            yc = ex["finding"]["material_conflict"] == 1; pc = (p == ABSTAIN_MATERIAL_CONFLICT)
            conf["tp"] += int(pc and yc); conf["fp"] += int(pc and not yc); conf["fn"] += int((not pc) and yc)
            ya = y in ABSTAIN_SET; pa = p in ABSTAIN_SET
            abst["tp"] += int(pa and ya); abst["fp"] += int(pa and not ya); abst["fn"] += int((not pa) and ya)
    def prf(d):
        pr = d["tp"] / max(1, d["tp"] + d["fp"]); r = d["tp"] / max(1, d["tp"] + d["fn"])
        return {"precision": pr, "recall": r, "f1": 2 * pr * r / max(1e-9, pr + r)}
    fa = {k: field_ok[k][0] / max(1, field_ok[k][1]) for k in FIELD_KEYS}
    fas = {k: field_ok_surv[k][0] / max(1, field_ok_surv[k][1]) for k in FIELD_KEYS}
    return {"outcome_accuracy": out_ok / max(1, n),
            "field_macro_accuracy": sum(fa.values()) / len(fa),
            "field_accuracy": fa, "field_accuracy_given_survived": fas,
            "conflict": prf(conf), "abstention": prf(abst),
            "evidence_id_preservation": ids_ok / max(1, n), "unauthorized_inclusion": unauth / max(1, n),
            "n": n}
