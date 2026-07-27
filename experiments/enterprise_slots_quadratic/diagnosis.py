"""
diagnosis.py — §3 conditional metrics + §4 slot failure taxonomy + §5 audit trace.

The decisive question: is the S3→S4 gap caused by missing/evicted evidence, or by reasoning/output
after the correct evidence is already present? Conditional metrics (accuracy | required evidence
survived) and a per-error taxonomy answer it directly, reconstructed from the slot audit trace.
"""
from __future__ import annotations

import torch

from .train import collate_arm
from .models import working_set
from .binding_slots import simulate_slots
from .dataset import ABSTAIN

TAXONOMY = ("MISSING_ADMISSION", "PREMATURE_EVICTION", "DUPLICATE_WASTE", "STALE_DOMINANCE",
            "CONFLICT_PAIR_INCOMPLETE", "CHAIN_LINK_MISSING", "REASONING_FAILURE",
            "OUTPUT_MAPPING_FAILURE")


def _tag_ids(ex, tags):
    return [e.evidence_id for e in ex["events"] if e.tag in tags]


@torch.no_grad()
def conditional_metrics(model, data, cfg, arm, K, policy="P2", device="cpu", bs=64):
    model.eval()
    acc_all = [0, 0]; acc_surv = [0, 0]; ver_surv = [0, 0]; conf_surv = [0, 0]; abst_inc = [0, 0]
    for i in range(0, len(data), bs):
        b = data[i:i + bs]
        inp, labels, meta = collate_arm(b, cfg, arm, K, policy, device)
        out = model(*inp)
        pred = out["answer"].argmax(-1); vpred = out["version"].argmax(-1); cpred = out["conflict"] >= 0
        for j, (ex, mm) in enumerate(zip(b, meta)):
            ok = pred[j].item() == ex["answer_role"]
            acc_all[0] += ok; acc_all[1] += 1
            surv = mm["required_survived"]
            if surv:
                acc_surv[0] += ok; acc_surv[1] += 1
                if ex["scenario"] != "missing":
                    ver_surv[0] += int(vpred[j].item() == ex["active_version"]); ver_surv[1] += 1
            # conflict F1 conditioned on both sides surviving
            if ex["conflict"]:
                sides = _tag_ids(ex, ("policy_active", "policy_conflict"))
                both = all(s in mm["ids"] for s in sides) if sides else False
                if both:
                    conf_surv[0] += int(cpred[j].item()); conf_surv[1] += 1
            # abstention accuracy conditioned on incomplete evidence
            if not surv:
                abst_inc[0] += int(pred[j].item() == ABSTAIN and ex["abstain"]); abst_inc[1] += 1
    r = lambda a: a[0] / max(1, a[1])
    return {"accuracy": r(acc_all), "acc_given_required_survived": r(acc_surv),
            "version_acc_given_survived": r(ver_surv),
            "conflict_recall_given_both_survived": r(conf_surv),
            "abstain_acc_given_incomplete": r(abst_inc),
            "n_survived": acc_surv[1], "n": acc_all[1]}


@torch.no_grad()
def classify_errors(model, data, cfg, arm, K, policy="P2", device="cpu", bs=64):
    """Assign each S3 error to exactly one primary taxonomy category (reconstructed from audit)."""
    model.eval()
    counts = {t: 0 for t in TAXONOMY}; n_err = 0; n = 0
    for i in range(0, len(data), bs):
        b = data[i:i + bs]
        inp, labels, meta = collate_arm(b, cfg, arm, K, policy, device)
        out = model(*inp)
        pred = out["answer"].argmax(-1); vpred = out["version"].argmax(-1); cpred = out["conflict"] >= 0
        for j, (ex, mm) in enumerate(zip(b, meta)):
            n += 1
            if pred[j].item() == ex["answer_role"]:
                continue
            n_err += 1
            counts[_classify_one(ex, mm, K, policy, vpred[j].item(), cpred[j].item())] += 1
    pct = {t: counts[t] / max(1, n_err) for t in TAXONOMY}
    return {"counts": counts, "pct": pct, "n_errors": n_err, "n": n}


def _classify_one(ex, mm, K, policy, vpred, cpred):
    sim = simulate_slots(ex, K, policy=policy)
    audit = sim["audit"]; final = set(mm["ids"])
    admitted = set()
    evicted = set()
    for a in audit:
        if a["event"] == "admit":
            admitted.add(a["evidence_id"])
        elif a["event"] == "replace":
            admitted.add(a["admit"]); evicted.add(a["evict"])
    req = [r for r in ex["required_ids"] if r >= 0]
    # 1/2 missing vs premature eviction of a required record
    for r in req:
        if r not in final:
            if r not in admitted:
                return "MISSING_ADMISSION"
            if r in evicted:
                return "PREMATURE_EVICTION"
            return "PREMATURE_EVICTION"
    # 4 conflict pair incomplete
    if ex["conflict"]:
        sides = _tag_ids(ex, ("policy_active", "policy_conflict"))
        if sides and not all(s in final for s in sides):
            return "CONFLICT_PAIR_INCOMPLETE"
    # 5 chain link missing (vendor/contract link needed to reach the policy)
    links = _tag_ids(ex, ("vendor_link", "contract_link"))
    if links and not all(l in final for l in links):
        return "CHAIN_LINK_MISSING"
    # 6 duplicate waste: >1 record of the same exact key occupies slots
    id_of = {e.evidence_id: e for e in ex["events"]}
    keys = [id_of[i].key_tuple() for i in final if i in id_of]
    if len(keys) != len(set(keys)):
        return "DUPLICATE_WASTE"
    # 7 stale dominance: a superseded version survived while its active counterpart did not
    from .schema import ACTIVE, SUPERSEDED
    act_id = ex["active_policy_id"]
    stale_in = any(id_of[i].status == SUPERSEDED and id_of[i].key_tuple()[:3] ==
                   (id_of[act_id].key_tuple()[:3] if act_id in id_of else None) for i in final if i in id_of)
    if act_id not in final and stale_in:
        return "STALE_DOMINANCE"
    # 8 evidence complete but wrong: mapping vs reasoning
    if ex["scenario"] != "missing" and vpred == ex["active_version"] and (cpred == bool(ex["conflict"])):
        return "OUTPUT_MAPPING_FAILURE"      # picked right version/conflict, wrong final class
    return "REASONING_FAILURE"


def audit_trace(ex, K, policy="P2"):
    """§5 full reconstructable trace for one workflow."""
    sim = simulate_slots(ex, K, policy=policy)
    return {"arrival": [(e.evidence_id, e.tag, e.section_id) for e in ex["events"]],
            "audit": sim["audit"], "final_slots": sim["ids"], "required_ids": ex["required_ids"],
            "answer_role": ex["answer_role"], "scenario": ex["scenario"]}
