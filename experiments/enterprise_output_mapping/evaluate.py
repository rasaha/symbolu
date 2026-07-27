"""evaluate.py — §14 metrics + §8 error decomposition for the output-mapping arms."""
from __future__ import annotations

import torch

from .structured_reasoning import collate, FIELD_DIMS
from .outcome_contract import N_OUTCOME, OUTCOMES, ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT
from .policy_mapper import o1_policy_map, fields_argmax
from .constrained_mapper import o2_constrained_map, o5_oracle_map
from .learned_mapper import o0_latent_map


ABSTAIN_SET = {ABSTAIN_INCOMPLETE_EVIDENCE, ABSTAIN_MATERIAL_CONFLICT}


def _predict(mapper_name, reasoner, ro, true_fields, meta):
    if mapper_name == "O0":
        return o0_latent_map(ro, meta)
    if mapper_name == "O1":
        return o1_policy_map(ro, meta)
    if mapper_name == "O2":
        return o2_constrained_map(ro, meta)
    if mapper_name == "O5":
        return o5_oracle_map(true_fields, meta)
    raise ValueError(mapper_name)


@torch.no_grad()
def evaluate(reasoner, data, cfg, K, mapper_name, learned=None, device="cpu", bs=64):
    reasoner.eval()
    correct = n = 0
    conf = {"tp": 0, "fp": 0, "fn": 0}
    abst = {"tp": 0, "fp": 0, "fn": 0}
    per = {o: [0, 0, 0] for o in range(N_OUTCOME)}      # tp, pred, actual
    field_correct = field_tot = 0
    map_err = map_den = 0                                # output-mapping error | complete & fields correct
    unauth = ids_ok = dup_occ = 0
    for i in range(0, len(data), bs):
        b = data[i:i + bs]
        inp, fields, outcome, meta = collate(b, cfg, K, device)
        ro = reasoner(*inp)
        if learned is not None:
            pred = learned.predict(ro, meta) if hasattr(learned, "predict") else learned(ro).argmax(-1)
        else:
            pred = _predict(mapper_name, reasoner, ro, fields, meta)
        correct += (pred == outcome).sum().item(); n += len(b)
        fa = fields_argmax(ro["field_logits"])
        for j, ex in enumerate(b):
            y = int(outcome[j]); p = int(pred[j])
            per[y][2] += 1; per[p][1] += 1; per[p][0] += int(p == y)
            yc = ex["finding"]["material_conflict"] == 1; pc = (p == ABSTAIN_MATERIAL_CONFLICT)
            conf["tp"] += int(pc and yc); conf["fp"] += int(pc and not yc); conf["fn"] += int((not pc) and yc)
            ya = y in ABSTAIN_SET; pa = p in ABSTAIN_SET
            abst["tp"] += int(pa and ya); abst["fp"] += int(pa and not ya); abst["fn"] += int((not pa) and ya)
            fok = all(int(fa[k][j]) == ex["finding"][k] for k in FIELD_DIMS)
            field_correct += int(fok); field_tot += 1
            # §8 key metric: mapping error given complete evidence AND correct structured fields
            if ex["finding"]["evidence_complete"] == 1 and fok:
                map_den += 1; map_err += int(p != y)
            unauth += meta[j]["unauthorized_included"]; ids_ok += meta[j]["ids_resolve"]
            dup_occ += meta[j]["dup_occupancy"]
    def prf(d):
        p = d["tp"] / max(1, d["tp"] + d["fp"]); r = d["tp"] / max(1, d["tp"] + d["fn"])
        return {"precision": p, "recall": r, "f1": 2 * p * r / max(1e-9, p + r)}
    bal = sum((per[o][0] / max(1, per[o][2])) for o in range(N_OUTCOME)) / N_OUTCOME
    return {"accuracy": correct / max(1, n), "balanced_accuracy": bal,
            "conflict": prf(conf), "abstention": prf(abst),
            "structured_field_accuracy": field_correct / max(1, field_tot),
            "output_mapping_error_rate": map_err / max(1, map_den), "map_den": map_den,
            "unauthorized_inclusion_rate": unauth / max(1, n),
            "evidence_id_preservation": ids_ok / max(1, n),
            "duplicate_occupancy": dup_occ / max(1, n),
            "per_outcome": {OUTCOMES[o]: {"precision": per[o][0] / max(1, per[o][1]),
                                          "recall": per[o][0] / max(1, per[o][2])} for o in range(N_OUTCOME)},
            "n": n}
