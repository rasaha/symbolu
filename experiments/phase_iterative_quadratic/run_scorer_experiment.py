"""
run_scorer_experiment.py — authorized next-hop pointer-discrimination experiment.

Bounded arms (identical dataset / seed / N=32 / candidate set / encoder / Q-blocks / optimizer
budget / eval examples):
    P0 — current structured-pointer baseline (o^T W ev)
    P1 — relation-aware bilinear candidate scorer   (backbone frozen, scorer-only)
    P2 — small candidate-conditioned MLP scorer      (backbone frozen, scorer-only)
    P3 — best scorer + one joint fine-tune + bounded beam-3

Listwise objective: cross_entropy over all 32 candidates vs the correct candidate index
(train.py pointer supervision). Primary metrics: top-1/top-3/MRR/correct-prob/entropy/grounded_D1/
beam-3 D1. Plus Part-1 held-out controls, causal/leakage controls, and the strict acceptance rule.
Autonomous eval uses only the predicted pointer distribution (no GT intermediate query / event id).
"""
from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path

import torch
import torch.nn.functional as F

from .multihop_dataset import build_vocab, generate
from .config import TrainCfg
from .hybrid_model import IterativeHybrid
from .train import train_hybrid, collate_iter
from .evaluate import evaluate
from .beam_search import decode
from .heldout_splits import (entity_pair_split, relation_compose_split,
                             generate_entity_pair, generate_relation_compose, rename_identities)

HERE = Path(__file__).resolve().parent
N = 32
STEPS = 3000
SEED = 0
RES = HERE / "results" / "scorer_experiment.json"


def base_kw(**extra):
    kw = dict(hops=2, routing_mode="oracle", pointer_query=True, W=N, K=8)
    kw.update(extra); return kw


def freeze_backbone(model):
    for name, p in model.named_parameters():
        p.requires_grad = name.startswith("scorer.")
    return model


def _params(m, trainable_only=False):
    return int(sum(p.numel() for p in m.parameters() if (p.requires_grad or not trainable_only)))


@torch.no_grad()
def rich_metrics(model, data, vocab, device="cpu"):
    model.eval()
    top1 = top3 = mrr = corr = ent = n = 0.0
    acc_all = acc_cp = n_cp = tot = 0
    for i in range(0, len(data), 64):
        b = data[i:i + 64]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        out = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)
        pred = out["answer_logits"].argmax(-1)
        acc_all += (pred == ans).sum().item(); tot += len(b)
        pl = out["pointer_logits"][0]
        tgt = reqe[:, 1] if reqe.shape[1] > 1 else torch.full((len(b),), -1)
        valid = tgt >= 0
        if valid.any():
            p = torch.softmax(pl[valid], dim=-1); t = tgt[valid]
            order = p.argsort(dim=-1, descending=True)
            rank = (order == t.unsqueeze(1)).float().argmax(-1) + 1        # 1-indexed rank
            top1 += (rank == 1).sum().item(); top3 += (rank <= 3).sum().item()
            mrr += (1.0 / rank.float()).sum().item()
            corr += p.gather(1, t.unsqueeze(1)).squeeze(1).sum().item()
            ent += (-(p.clamp_min(1e-9).log() * p).sum(-1)).sum().item()
            n += valid.sum().item()
            cp = rank == 1; idx = valid.nonzero(as_tuple=True)[0]
            acc_cp += ((pred[idx] == ans[idx]) & cp).sum().item(); n_cp += cp.sum().item()
    return {"grounded_D1": acc_all / max(1, tot),
            "next_entity_top1": top1 / max(1, n), "next_entity_top3": top3 / max(1, n),
            "mrr": mrr / max(1, n), "correct_entity_prob": corr / max(1, n),
            "pointer_entropy": ent / max(1, n),
            "acc_given_correct_pointer": acc_cp / max(1, n_cp)}


def train_arm(vocab, nid, gen, steps, backbone_src=None, freeze=False, **kw):
    torch.manual_seed(SEED)
    m = IterativeHybrid(vocab.size, nid, **kw)
    if backbone_src is not None:
        m.load_state_dict(backbone_src.state_dict(), strict=False)        # copy shared backbone
    if freeze:
        freeze_backbone(m)
    train_hybrid(m, gen, vocab, TrainCfg(seed=SEED, steps=steps))
    return m


def held_out_controls(vocab, nid, best_kind, te, best_model, t0):
    """Part-1/Part-6 held-out controls. Eval-time renaming/shuffle on the given model; unseen
    compositions require restricted training (train best kind jointly on the restricted split)."""
    out = {}
    out["clean"] = evaluate(best_model, te, vocab)["accuracy"]
    out["identity_renaming"] = evaluate(best_model, rename_identities(te, vocab, seed=7), vocab)["accuracy"]
    # shuffled evidence order: permute events per example (positions re-encoded); identity-defined
    # answer is unchanged, so a genuine retriever is invariant.
    g = torch.Generator().manual_seed(123)
    sh = []
    for ex in te:
        ex2 = {**ex}
        perm = torch.randperm(len(ex["events"]), generator=g).tolist()
        ex2["events"] = [ex["events"][i] for i in perm]
        toks = [ex["tokens"][0]]; kp = []
        for e in ex2["events"]:
            kp.append(len(toks)); toks += [vocab.key(e["entity"], e["relation"]), vocab.val(e["value"])]
        toks.append(vocab.PROBE)
        ex2["tokens"] = toks; ex2["key_pos"] = kp
        ex2["req_evidx"] = sorted([i for i, e in enumerate(ex2["events"]) if e["required"]],
                                  key=lambda i: ex2["events"][i]["hop"])
        sh.append(ex2)
    out["shuffled_order"] = evaluate(best_model, sh, vocab)["accuracy"]
    print(f"  controls: clean={out['clean']:.3f} rename={out['identity_renaming']:.3f} "
          f"shuffle={out['shuffled_order']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    # unseen entity pairings (retrain restricted, joint)
    tr_p, te_p = entity_pair_split(vocab, 0.3, seed=0)
    m_ep = train_arm(vocab, nid, lambda bs, s: generate_entity_pair(vocab, N, 2, bs, s, tr_p),
                     STEPS, **base_kw(scorer_kind=best_kind, n_rel=vocab.R))
    out["unseen_entity_pair"] = evaluate(m_ep, generate_entity_pair(vocab, N, 2, 300, 78000, te_p), vocab)["accuracy"]
    print(f"  unseen_entity_pair={out['unseen_entity_pair']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    # unseen relation compositions (retrain restricted, joint)
    tr_c, te_c = relation_compose_split(vocab, 0.3, seed=1)
    m_rc = train_arm(vocab, nid, lambda bs, s: generate_relation_compose(vocab, N, 2, bs, s, tr_c),
                     STEPS, **base_kw(scorer_kind=best_kind, n_rel=vocab.R))
    out["unseen_relation_compose"] = evaluate(m_rc, generate_relation_compose(vocab, N, 2, 300, 79000, te_c), vocab)["accuracy"]
    print(f"  unseen_relation_compose={out['unseen_relation_compose']:.3f} ({time.time()-t0:.0f}s)", flush=True)
    coll = min(out["unseen_entity_pair"], out["unseen_relation_compose"], out["identity_renaming"],
               out["shuffled_order"])
    out["no_material_collapse"] = coll >= 0.85 * out["clean"]
    return out


@torch.no_grad()
def causal_controls(model, te, vocab, best_kind, backbone_src, device="cpu"):
    """Oracle routing uses stochastic tie-breaking noise, so equality checks seed identically
    before both compared calls; any residual difference is then attributable to the tested factor."""
    out = {}
    b = te[:128]
    ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)

    def call(**kw):
        torch.manual_seed(1234)                             # identical routing noise across calls
        return model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, **kw)["answer_logits"]

    a = call()
    out["clean_acc"] = (a.argmax(-1) == ans).float().mean().item()
    # (1) leak-free: randomize the intermediate-query label (reqe) — the pointer must not read it
    reqe_rand = reqe.clone(); reqe_rand[:, 1:] = torch.randint(0, ep.shape[1], reqe_rand[:, 1:].shape)
    torch.manual_seed(1234)
    a2 = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe_rand)["answer_logits"]
    out["leakfree_reqe_invariant"] = bool(torch.allclose(a, a2, atol=1e-6))
    # (2) random pointer scores collapse accuracy
    ar = call(random_pointer=True)
    out["random_pointer_acc"] = (ar.argmax(-1) == ans).float().mean().item()
    # (3) required-event-removed collapse: corrupt the hop-1 required VALUE so the answer is unreachable
    ids_c = ids.clone(); r1 = reqf[:, 1].clamp(min=0)
    for j in range(len(b)):
        pos = r1[j].item()
        if pos > 0 and b[j]["n_required"] > 1:
            ids_c[j, pos + 1] = vocab.val((ans[j].item() + 1) % vocab.n_id)   # wrong retrievable value
    torch.manual_seed(1234)
    ac = model(ids_c, ep, pp, vl, required_hops=reqf, req_evidx=reqe)["answer_logits"]
    out["required_removed_acc"] = (ac.argmax(-1) == ans).float().mean().item()
    # (4) forced identical candidate -> identical non-scorer behavior across two scorer kinds.
    # The scorer-independent quantity given a forced hop-1 query is the hop-1 ATTENTION readout
    # (the answer decode additionally mixes in the post-last-hop pointer query, which is by design
    # scorer-dependent). We compare the last-hop attention output across two different scorers.
    other = "mlp" if best_kind == "bilinear" else "bilinear"
    m2 = IterativeHybrid(vocab.size, vocab.n_id, **base_kw(scorer_kind=other, n_rel=vocab.R))
    m2.load_state_dict(backbone_src.state_dict(), strict=False); m2.eval()
    q1 = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)["event_reps"][:, 0]
    torch.manual_seed(1234)
    fa = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, forced_query=q1)["hop_logits"][-1]
    torch.manual_seed(1234)
    fb = m2(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe, forced_query=q1)["hop_logits"][-1]
    out["forced_candidate_scorer_independent"] = bool(torch.allclose(fa, fb, atol=1e-6))
    return out


@torch.no_grad()
def hard_negative_breakdown(model, te, vocab, device="cpu"):
    """Of the pointer's hop-1 top-1 errors, which candidate CATEGORY does it land on?"""
    model.eval(); cats = {"relevant": 0, "hard": 0, "ordinary": 0}; err = 0
    for i in range(0, len(te), 64):
        b = te[i:i + 64]
        ids, ep, pp, vl, ans, reqf, reqe, ht = collate_iter(b, vocab, device)
        pl = model(ids, ep, pp, vl, required_hops=reqf, req_evidx=reqe)["pointer_logits"][0]
        sel = pl.argmax(-1)
        for j, ex in enumerate(b):
            if ex["n_required"] < 2:
                continue
            correct = ex["req_evidx"][1]
            if sel[j].item() != correct:
                err += 1
                cats[ex["events"][sel[j].item()]["category"]] += 1
    return {"n_errors": err, **{f"err_on_{k}": v / max(1, err) for k, v in cats.items()}}


def run():
    vocab = build_vocab(); nid = vocab.n_id; t0 = time.time()
    g2 = lambda bs, s: generate(vocab, N, 2, bs, s)
    te = generate(vocab, N, 2, 300, 77000)
    res = {"N": N, "seed": SEED, "steps": STEPS, "arms": {}}

    # ---- P0 baseline (also the frozen backbone source) ----
    m0 = train_arm(vocab, nid, g2, STEPS, **base_kw())
    p0 = rich_metrics(m0, te, vocab)
    p0["beam3"] = decode(m0, te, vocab, "beam3"); p0["oracle_ptr"] = decode(m0, te, vocab, "oracle_ptr")
    p0["params"] = _params(m0)
    res["arms"]["P0_baseline"] = p0
    print(f"P0: gD1={p0['grounded_D1']:.3f} top1={p0['next_entity_top1']:.3f} "
          f"top3={p0['next_entity_top3']:.3f} mrr={p0['mrr']:.3f} beam3={p0['beam3']:.3f} "
          f"({time.time()-t0:.0f}s)", flush=True)
    RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- P0 Part-1 held-out / memorization diagnosis (on the current-style baseline) ----
    res["P0_heldout_controls"] = held_out_controls(vocab, nid, None, te, m0, t0)
    res["P0_hard_negatives"] = hard_negative_breakdown(m0, te, vocab)
    RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- P1 bilinear / P2 MLP: scorer-only, backbone frozen ----
    for tag, kind in [("P1_bilinear", "bilinear"), ("P2_mlp", "mlp")]:
        m = train_arm(vocab, nid, g2, STEPS, backbone_src=m0, freeze=True,
                      **base_kw(scorer_kind=kind, n_rel=vocab.R))
        met = rich_metrics(m, te, vocab)
        met["beam3"] = decode(m, te, vocab, "beam3"); met["oracle_ptr"] = decode(m, te, vocab, "oracle_ptr")
        met["scorer_params"] = _params(m, trainable_only=True); met["total_params"] = _params(m)
        res["arms"][tag] = met
        print(f"{tag}: gD1={met['grounded_D1']:.3f} top1={met['next_entity_top1']:.3f} "
              f"top3={met['next_entity_top3']:.3f} mrr={met['mrr']:.3f} beam3={met['beam3']:.3f} "
              f"scorer_params={met['scorer_params']} ({time.time()-t0:.0f}s)", flush=True)
        RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- pick best scorer (by grounded_D1) → P3 joint fine-tune + beam ----
    best_kind = "bilinear" if res["arms"]["P1_bilinear"]["grounded_D1"] >= res["arms"]["P2_mlp"]["grounded_D1"] else "mlp"
    tracemalloc.start()
    m3 = train_arm(vocab, nid, g2, STEPS, backbone_src=m0, freeze=False,
                   **base_kw(scorer_kind=best_kind, n_rel=vocab.R))               # joint fine-tune
    _c, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
    lat_b = te[:64]; lids, lep, lpp, lvl, *_ = collate_iter(lat_b, vocab)
    m3.eval(); m3(lids, lep, lpp, lvl)
    tL = time.time()
    for _ in range(5):
        with torch.no_grad():
            m3(lids, lep, lpp, lvl)
    latency = (time.time() - tL) / 5
    p3 = rich_metrics(m3, te, vocab)
    p3["beam3"] = decode(m3, te, vocab, "beam3"); p3["oracle_ptr"] = decode(m3, te, vocab, "oracle_ptr")
    p3["hard_top1"] = decode(m3, te, vocab, "hard_top1"); p3["soft"] = decode(m3, te, vocab, "soft")
    p3["best_kind"] = best_kind; p3["params"] = _params(m3)
    p3["latency_s_per_64"] = round(latency, 4); p3["peak_mem_mb"] = round(peak / 1e6, 1)
    res["arms"]["P3_best_joint_beam"] = p3
    print(f"P3({best_kind}+joint): gD1={p3['grounded_D1']:.3f} top1={p3['next_entity_top1']:.3f} "
          f"top3={p3['next_entity_top3']:.3f} beam3={p3['beam3']:.3f} acc|cp={p3['acc_given_correct_pointer']:.3f} "
          f"({time.time()-t0:.0f}s)", flush=True)
    RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- causal + held-out controls on the best (joint) model ----
    res["P3_causal_controls"] = causal_controls(m3, te, vocab, best_kind, m0)
    print(f"  causal: {json.dumps(res['P3_causal_controls'], default=float)}", flush=True)
    res["P3_heldout_controls"] = held_out_controls(vocab, nid, best_kind, te, m3, t0)
    res["P3_hard_negatives"] = hard_negative_breakdown(m3, te, vocab)
    RES.write_text(json.dumps(res, indent=2, default=float))

    # ---- strict acceptance rule ----
    cc = res["P3_causal_controls"]; ho = res["P3_heldout_controls"]
    accept = {
        "pointer_top1_ge_0.75": p3["next_entity_top1"] >= 0.75,
        "grounded_D1_ge_0.85": p3["grounded_D1"] >= 0.85,
        "beam3_ge_0.85": p3["beam3"] >= 0.85,
        "acc_given_correct_pointer_ge_0.90": p3["acc_given_correct_pointer"] >= 0.90,
        "heldout_no_material_collapse": ho["no_material_collapse"],
        "leakfree": cc["leakfree_reqe_invariant"],
    }
    accept["PASS"] = all(accept.values())
    res["acceptance"] = accept
    res["verdict"] = {
        "pointer_discrimination": ("validated" if accept["PASS"] else
                                   "improved_but_insufficient" if p3["grounded_D1"] > p0["grounded_D1"] + 0.02
                                   else "failed"),
        "iterative_3Q_pilot": "authorized" if accept["PASS"] else "blocked",
        "phase_comparison": "authorized" if accept["PASS"] else "blocked",
    }
    RES.write_text(json.dumps(res, indent=2, default=float))
    print("ACCEPTANCE:", json.dumps(accept, default=float), flush=True)
    print("VERDICT:", json.dumps(res["verdict"], default=float), flush=True)
    print("SCORER_EXPERIMENT DONE", flush=True)
    return res


if __name__ == "__main__":
    run()
