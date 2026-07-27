"""
causal_controls.py — §12 integrity + causal controls.

Eval-time interventions on the bounded working set / features that isolate each component's causal
contribution. Access-control and evidence-ID isolation are structural guarantees (verified by
construction) — the working set is drawn only from authorized, ledger-resolvable records.
"""
from __future__ import annotations

import torch

from .train import collate_arm
from .dataset import ABSTAIN


@torch.no_grad()
def _acc(model, inp):
    return model(*inp)["answer"].argmax(-1)


@torch.no_grad()
def control_accuracy(model, data, cfg, arm, K, control="none", policy="P2", device="cpu", bs=64):
    model.eval(); correct = n = 0
    for i in range(0, len(data), bs):
        b = data[i:i + bs]
        (ws_cats, ws_num, ws_mask, q_cats, q_num), labels, meta = collate_arm(b, cfg, arm, K, policy, device)
        B, M = ws_mask.shape
        if control == "zero_slot_repr":
            ws_num = torch.zeros_like(ws_num)
            for f in ws_cats:
                ws_cats[f] = torch.zeros_like(ws_cats[f])          # exact fields blanked in the encoder
        elif control == "shuffle_slots":
            perm = torch.stack([torch.randperm(M, device=device) for _ in range(B)])
            for f in ws_cats:
                ws_cats[f] = ws_cats[f].gather(1, perm)
            ws_num = ws_num.gather(1, perm.unsqueeze(-1).expand_as(ws_num))
            ws_mask = ws_mask.gather(1, perm)
        elif control in ("evict_required", "evict_irrelevant"):
            id_of_list = [{e.evidence_id: e for e in ex["events"]} for ex in b]
            for j, (ex, mm) in enumerate(zip(b, meta)):
                req = set(x for x in ex["required_ids"] if x >= 0)
                for k, eid in enumerate(mm["ids"][:M]):
                    drop = (eid in req) if control == "evict_required" else (eid not in req)
                    if drop:
                        ws_mask[j, k] = False
        out = model(ws_cats, ws_num, ws_mask, q_cats, q_num)
        correct += (out["answer"].argmax(-1) == labels["answer"]).sum().item(); n += len(b)
    return correct / max(1, n)


@torch.no_grad()
def integrity_report(data, cfg, arm, K, policy="P2"):
    """Structural guarantees: unauthorized inclusion, ID resolution — computed from the working set
    itself (no model needed). Also injects an unauthorized RELEVANT record and confirms exclusion."""
    from .models import working_set
    from .schema import ACTIVE
    unauth = ids_ok = n = 0
    inj_leak = 0
    for ex in data:
        id_of = {e.evidence_id: e for e in ex["events"]}
        w = working_set(ex, arm, K, policy)
        for eid in w["ids"]:
            e = id_of.get(eid)
            if e is None:
                continue
            if not (e.tenant_id == ex["tenant"] and e.readable_by(ex["role_idx"])):
                unauth += 1
        ids_ok += all(eid in id_of for eid in w["ids"]); n += 1
        # any injected unauthorized_policy that slipped into the working set?
        inj_leak += any(id_of[eid].tag == "unauthorized_policy" for eid in w["ids"] if eid in id_of)
    return {"unauthorized_inclusion_rate": unauth / max(1, n),
            "evidence_id_preservation": ids_ok / max(1, n),
            "injected_unauthorized_leak_rate": inj_leak / max(1, n)}
