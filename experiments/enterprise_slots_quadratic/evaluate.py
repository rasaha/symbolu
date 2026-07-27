"""evaluate.py — enterprise metrics (§13) for the slots+quadratic arms."""
from __future__ import annotations

import torch

from .train import collate_arm
from .dataset import ABSTAIN


@torch.no_grad()
def evaluate(model, data, cfg, arm, K, policy="P2", device="cpu", batch_size=64):
    model.eval()
    n = 0; acc = 0; abst_tp = abst_fp = abst_fn = 0
    conf_tp = conf_fp = conf_fn = 0; ver_acc = ver_n = 0
    req_surv = unauth = ids_ok = 0
    retr = enc = 0.0
    acc_by_survived = [0, 0]                         # [correct, count] among required-survived
    for i in range(0, len(data), batch_size):
        b = data[i:i + batch_size]
        inp, labels, meta = collate_arm(b, cfg, arm, K, policy, device)
        out = model(*inp)
        pred = out["answer"].argmax(-1)
        acc += (pred == labels["answer"]).sum().item(); n += len(b)
        # abstention (predict ABSTAIN class)
        pa = (pred == ABSTAIN); ya = labels["abstain"].bool()
        abst_tp += (pa & ya).sum().item(); abst_fp += (pa & ~ya).sum().item(); abst_fn += (~pa & ya).sum().item()
        pc = out["conflict"] >= 0; yc = labels["conflict"].bool()
        conf_tp += (pc & yc).sum().item(); conf_fp += (pc & ~yc).sum().item(); conf_fn += (~pc & yc).sum().item()
        vpred = out["version"].argmax(-1)
        ver_acc += (vpred == labels["version"]).sum().item(); ver_n += len(b)
        for j, mm in enumerate(meta):
            req_surv += mm["required_survived"]; unauth += mm["unauthorized_included"]
            ids_ok += mm["ids_resolve"]; retr += mm["retrieval_calls"]; enc += mm["records_encoded"]
            if mm["required_survived"]:
                acc_by_survived[1] += 1
                acc_by_survived[0] += int(pred[j].item() == labels["answer"][j].item())
    def f1(tp, fp, fn):
        p = tp / max(1, tp + fp); r = tp / max(1, tp + fn)
        return {"precision": p, "recall": r, "f1": 2 * p * r / max(1e-9, p + r)}
    return {"accuracy": acc / max(1, n),
            "abstention": f1(abst_tp, abst_fp, abst_fn),
            "conflict": f1(conf_tp, conf_fp, conf_fn),
            "active_version_acc": ver_acc / max(1, ver_n),
            "required_survival_rate": req_surv / max(1, n),
            "unauthorized_inclusion_rate": unauth / max(1, n),
            "evidence_id_preservation": ids_ok / max(1, n),
            "retrieval_calls_per_wf": retr / max(1, n),
            "records_encoded_per_query": enc / max(1, n),
            "acc_given_required_survived": acc_by_survived[0] / max(1, acc_by_survived[1]),
            "n": n}
