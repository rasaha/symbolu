"""
run_verify.py — post-rescue verification (held-out + causal), required before declaring the rescue
validated.

  #2 dev vs HELD-OUT (fresh seeds + unseen entities/templates) for P2–P5, reported separately.
  #3 separate active-version survival from active+stale CO-survival and conditional version accuracy
     (if only the active survives, credit the deterministic policy, not quadratic conflict handling).
  #4 rerun the failed causal gate after rescue: normal / force-evict-required / force-evict-irrelevant.
  #5 full metric report.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .schema import DomainCfg, ACTIVE, SUPERSEDED
from .dataset import generate
from .models import SlotQuadModel, working_set
from .train import train_model, collate_arm
from .evaluate import evaluate
from .diagnosis import conditional_metrics
from .causal_controls import control_accuracy, integrity_report

HERE = Path(__file__).resolve().parent
STEPS = 600
SEED = 0
N = 256
MODE = "streaming"
# splits: TRAIN pools used for training + dev eval; HELD pools + fresh seeds for held-out eval
TRAIN_SUBJ = list(range(32)); HELD_SUBJ = list(range(32, 48))
TRAIN_TMPL = list(range(8)); HELD_TMPL = list(range(8, 12))


def _train(cfg, policy, K=8):
    torch.manual_seed(SEED)
    m = SlotQuadModel(cfg, arm="S3", K=K)
    train_model(m, lambda bs, s: generate(cfg, N, MODE, bs, s, TRAIN_SUBJ, TRAIN_TMPL), cfg, "S3", K,
                policy=policy, steps=STEPS, seed=SEED)
    return m


def _tag_ids(ex, tags):
    return [e.evidence_id for e in ex["events"] if e.tag in tags]


@torch.no_grad()
def version_separation(model, data, cfg, K, policy, device="cpu"):
    """#3: active survival vs active+stale co-survival vs version accuracy | both survived."""
    model.eval()
    act_surv = [0, 0]; co_surv = [0, 0]; ver_both = [0, 0]; ver_all = [0, 0]
    for i in range(0, len(data), 64):
        b = data[i:i + 64]
        inp, labels, meta = collate_arm(b, cfg, "S3", K, policy, device)
        vpred = model(*inp)["version"].argmax(-1)
        for j, (ex, mm) in enumerate(zip(b, meta)):
            if ex["scenario"] == "missing":
                continue
            ids = set(mm["ids"])
            act = ex["active_policy_id"]
            act_in = act in ids
            stale = _tag_ids(ex, ("policy_superseded",))
            stale_in = any(s in ids for s in stale)
            act_surv[0] += int(act_in); act_surv[1] += 1
            if act_in:
                co_surv[0] += int(stale_in); co_surv[1] += 1
            ok = int(vpred[j].item() == ex["active_version"])
            ver_all[0] += ok; ver_all[1] += 1
            if act_in and stale_in:
                ver_both[0] += ok; ver_both[1] += 1
    r = lambda a: a[0] / max(1, a[1])
    return {"active_version_survival": r(act_surv),
            "active_plus_stale_cosurvival": r(co_surv),
            "version_acc_overall": r(ver_all),
            "version_acc_given_active_and_stale_survived": r(ver_both),
            "n_both": ver_both[1]}


def _metrics(model, data, cfg, K, policy):
    r = evaluate(model, data, cfg, "S3", K, policy)
    c = conditional_metrics(model, data, cfg, "S3", K, policy)
    return {"accuracy": r["accuracy"], "acc_given_required_survived": c["acc_given_required_survived"],
            "conflict_f1": r["conflict"]["f1"],
            "conflict_recall_given_both_survived": c["conflict_recall_given_both_survived"],
            "required_survival": r["required_survival_rate"],
            "evidence_id_preservation": r["evidence_id_preservation"],
            "unauthorized_inclusion": r["unauthorized_inclusion_rate"]}


def run():
    cfg = DomainCfg(); t0 = time.time(); res = {"steps": STEPS, "splits": {
        "train_subjects": len(TRAIN_SUBJ), "held_subjects": len(HELD_SUBJ),
        "train_templates": len(TRAIN_TMPL), "held_templates": len(HELD_TMPL)}}
    dev = generate(cfg, N, MODE, 300, 810000, TRAIN_SUBJ, TRAIN_TMPL)         # fresh dev seed
    ho = generate(cfg, N, MODE, 300, 820000, HELD_SUBJ, HELD_TMPL)            # held-out seed + entities/templates

    res["policies"] = {}
    p2model = None
    for policy in ("P2", "P3", "P4", "P5"):
        m = _train(cfg, policy)
        if policy == "P2":
            p2model = m
        res["policies"][policy] = {"dev": _metrics(m, dev, cfg, 8, policy),
                                   "heldout": _metrics(m, ho, cfg, 8, policy),
                                   "version_sep_heldout": version_separation(m, ho, cfg, 8, policy)}
        x = res["policies"][policy]
        print(f"{policy}: dev_acc={x['dev']['accuracy']:.3f} ho_acc={x['heldout']['accuracy']:.3f} "
              f"ho_acc|surv={x['heldout']['acc_given_required_survived']:.3f} "
              f"act_surv={x['version_sep_heldout']['active_version_survival']:.2f} "
              f"co_surv={x['version_sep_heldout']['active_plus_stale_cosurvival']:.2f} "
              f"({time.time()-t0:.0f}s)", flush=True)
        (HERE / "results" / "verify.json").write_text(json.dumps(res, indent=2, default=float))

    # #4 causal gate rerun on the rescued S3(P2), held-out
    res["causal_rerun_heldout"] = {c: control_accuracy(p2model, ho, cfg, "S3", 8, control=c, policy="P2")
                                   for c in ("none", "evict_required", "evict_irrelevant")}
    res["integrity_heldout"] = integrity_report(ho, cfg, "S3", 8, "P2")
    cc = res["causal_rerun_heldout"]
    res["checks"] = {
        "leak_free_reachability": True,      # verified in the audit (labels-invariant, runtime anchor)
        "heldout_survival_ok": all(res["policies"][p]["heldout"]["required_survival"] > 0.5 for p in ("P2","P3","P4","P5")),
        "causal_required_gt_irrelevant": cc["evict_required"] < cc["evict_irrelevant"] - 0.02,
        "id_preservation": res["integrity_heldout"]["evidence_id_preservation"] == 1.0,
        "no_unauthorized": res["integrity_heldout"]["unauthorized_inclusion_rate"] == 0.0,
        "version_gain_from_slots_not_quad": res["policies"]["P2"]["version_sep_heldout"]["active_plus_stale_cosurvival"] < 0.1,
    }
    res["checks"]["RESCUE_VALIDATED"] = (res["checks"]["heldout_survival_ok"] and
                                         res["checks"]["causal_required_gt_irrelevant"] and
                                         res["checks"]["id_preservation"] and res["checks"]["no_unauthorized"])
    (HERE / "results" / "verify.json").write_text(json.dumps(res, indent=2, default=float))
    print("causal_rerun:", json.dumps(cc, default=float), flush=True)
    print("CHECKS:", json.dumps(res["checks"], default=float), flush=True)
    print("VERIFY DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
