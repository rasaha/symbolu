#!/usr/bin/env python3
"""Paired intervention arms on the corrected-H2 base: A+ (reference), B0 (frozen H2), A1 (read-address
generalization), G1 (routing-gradient isolation), AG (A1+G1).

run_ag_arm copies the FROZEN persistence_arms.run_h2 loop and adds ONLY two guarded levers:
  * use_a1: add lam_a1(step)*A1_loss (contrastive read-address on hard-negative diverse-template real
    task queries, drawn from a DEDICATED rng so the main data stream is byte-identical to B0);
  * use_g1: split the LM (main) and auxiliary (alignment+teacher[+A1]) gradients and PCGrad-project
    the auxiliary away from the LM inside write_addr_proj ONLY.
With use_a1=use_g1=False the TRAINING path is byte-identical to run_h2 (verified by the B0-equivalence
test); the only additions are measurement-only gradient-behaviour fields.

A+ uses the frozen persistence_arms.run_aplus. Requires torch.
"""
from __future__ import annotations

import copy
import hashlib
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
NEURAL = REPO / "hybrid_llm_vnext_lab" / "experiments" / "neural_slots_only"
FR = REPO / "experiments" / "bindingslots_functional_routing"
PERS = REPO / "experiments" / "bindingslots_persistence"
VPD = REPO / "experiments" / "bindingslots_value_path_diagnosis"
for p in (str(HERE), str(SBS), str(NEURAL), str(FR), str(PERS), str(VPD)):
    if p not in sys.path:
        sys.path.insert(0, p)

FULL_CKPTS = [0, 60, 120, 300, 600, 700, 900]  # record(1200) added at loop end
PRIMARY_CKPTS = {300, 600, 700, 900, 1200}      # heavy eval-time routing + wak probes only here
A1_PARTITION = "train"
A1_RNG_BASE = 8675309   # dedicated A1 batch rng base (independent of the training rng)
EVAL_SEED, EVAL_N, EVAL_DIST = 123, 120, 96      # the frozen held-out needle eval (base template)


def _eval_time_routing(model, vocab, T):
    """PRIMARY endpoint: correct-slot routing on the actual HELD-OUT eval queries (base needle
    template, seed 123) — correct-slot prob/top1/rank/margin/entropy + ordinary-vs-oracle gap.
    Measurement-only (no grad, no rng, no optimizer step). Reuses the value-path harness."""
    import torch
    import diagnosis_lib as DL
    X, fp, qp, tgt = DL.needle_examples(vocab, T, EVAL_SEED, EVAL_N, EVAL_DIST)
    probs, top1, ranks, margins, ents = [], [], [], [], []
    bs = 60
    for i in range(0, len(X), bs):
        fb, qb = fp[i:i + bs], qp[i:i + bs]
        with DL.instrumented_model(model, mode=None, capture=True, fact_pos=fb, query_pos=qb) as slots:
            with torch.no_grad():
                _ = model(X[i:i + bs])
            # aggregate correct-slot routing over slot layers from the per-layer captures
            r_prob = torch.zeros(len(fb)); r_top1 = torch.zeros(len(fb)); r_rank = torch.zeros(len(fb))
            r_marg = torch.zeros(len(fb)); r_ent = torch.zeros(len(fb))
            L = len(slots)
            for sm in slots:
                cap = sm._cap
                # need full read distribution at query: recompute from raddr — cap has raddr_query
                rq = cap["raddr_query"]              # [b, M]
                sstar = cap["sstar"]                 # [b]
                jj = torch.arange(len(fb))
                p_star = rq[jj, sstar]
                r_prob += p_star
                r_top1 += (rq.argmax(-1) == sstar).float()
                order = rq.argsort(-1, descending=True)
                r_rank += (order == sstar.unsqueeze(-1)).float().argmax(-1).float()
                rq2 = rq.clone(); rq2[jj, sstar] = -1.0
                r_marg += (p_star - rq2.max(-1).values)
                r_ent += -(rq * (rq + 1e-9).log()).sum(-1)
            probs.append(r_prob / L); top1.append(r_top1 / L); ranks.append(r_rank / L)
            margins.append(r_marg / L); ents.append(r_ent / L)
    ord_m = _needle_acc_base(model, X, qp, tgt)
    orc = _oracle_addr_acc(model, X, fp, qp, tgt)
    cat = lambda xs: torch.cat(xs)
    return {"correct_slot_prob": cat(probs).mean().item(),
            "correct_slot_top1": cat(top1).mean().item(),
            "correct_slot_rank_mean": cat(ranks).mean().item(),
            "correct_vs_best_competitor_margin": cat(margins).mean().item(),
            "read_entropy": cat(ents).mean().item(),
            "ordinary_needle": ord_m, "oracle_address_needle": orc,
            "ordinary_vs_oracle_gap": orc - ord_m}


def _needle_acc_base(model, X, qp, tgt, bs=60):
    import torch
    c = 0
    with torch.no_grad():
        for i in range(0, len(X), bs):
            lo = model(X[i:i + bs]); j = torch.arange(len(X[i:i + bs]))
            c += (lo[j, qp[i:i + bs]].argmax(-1) == tgt[i:i + bs]).sum().item()
    return c / len(X)


def _oracle_addr_acc(model, X, fp, qp, tgt, bs=60):
    import torch
    import diagnosis_lib as DL
    c = 0
    for i in range(0, len(X), bs):
        fb, qb, tb = fp[i:i + bs], qp[i:i + bs], tgt[i:i + bs]
        with DL.instrumented_model(model, mode="oracle_address", fact_pos=fb, query_pos=qb):
            with torch.no_grad():
                lo = model(X[i:i + bs])
        j = torch.arange(len(fb))
        c += (lo[j, qb].argmax(-1) == tb).sum().item()
    return c / len(X)


def _wak_gradient_probe(model, teacher, vocab, T, IV, OP, O1, step, seed=5551):
    """Measurement-only: separate LM vs auxiliary (alignment+teacher) gradient PER PARAMETER GROUP and
    their cosine (for the wak conflict AND the §12.4 'no new conflict in another group' check). Does
    NOT step the optimizer, clears grads afterwards, uses a fixed local rng, consumes no training RNG."""
    import torch
    import torch.nn.functional as F
    import gradients as GR   # value-path phase: complete non-overlapping parameter groups
    was_training = model.training
    model.train()
    groups = GR.param_groups(model)
    rng = random.Random(seed)
    _, _, stream = TA_cache(vocab)
    x, y, _ = T.lm_batch(stream, 8, 160, rng)
    model.zero_grad(set_to_none=True)
    lo = model(x)
    F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1)).backward()
    g_lm = {g: [(p.grad.detach().clone() if p.grad is not None else torch.zeros_like(p)) for _, p in ps]
            for g, ps in groups.items()}
    model.zero_grad(set_to_none=True)
    aux_terms = 0.0
    lam = IV.lambda_align(step)
    if lam > 0.0:
        xa, fp, qp = IV.aux_needle_batch(vocab, 8, 160, rng, T)
        la, _ = IV.alignment_loss(model, xa, fp, qp)
        aux_terms = aux_terms + lam * la
    h2c = OP.h2_coefficient(step)
    if h2c > 0.0 and teacher is not None:
        xa2, fp2, qp2 = IV.aux_needle_batch(vocab, 8, 160, rng, T)
        tdists = OP.h2_teacher_read_distributions(teacher, xa2, qp2)
        aux_terms = aux_terms + h2c * OP.h2_loss(model, xa2, qp2, tdists)
    out = {"step": step, "has_aux": not isinstance(aux_terms, float)}
    if not isinstance(aux_terms, float):
        aux_terms.backward()
        eps = 1e-12
        cos_by_group = {}
        for g, ps in groups.items():
            gl = torch.cat([g_lm[g][i].reshape(-1) for i in range(len(ps))])
            ga = torch.cat([(p.grad.detach() if p.grad is not None else torch.zeros_like(p)).reshape(-1)
                            for _, p in ps])
            c = (torch.dot(gl, ga).item() / (gl.norm().item() * ga.norm().item())) \
                if gl.norm() > eps and ga.norm() > eps else 0.0
            cos_by_group[g] = c
        out["lm_vs_aux_cosine_by_group"] = cos_by_group
        out["lm_vs_aux_cosine_wak"] = cos_by_group.get("write_addr_proj", 0.0)
    model.zero_grad(set_to_none=True)
    if not was_training:
        model.eval()
    return out


_TA_STREAM = {}
def TA_cache(vocab):
    import _nso
    if "s" not in _TA_STREAM:
        _TA_STREAM["s"] = _nso.tasks_adapter.build_corpus()
    return _TA_STREAM["s"]


def run_ag_arm(seed, use_a1=False, use_g1=False, steps=1200):
    import torch
    import torch.nn.functional as F
    import _nso
    import interventions as IV
    import diagnostics as DIAG
    import interventions_ag as IAG
    import objectives as O1
    import objectives_persistence as OP
    MDL, TA, T, EV = _nso.models, _nso.tasks_adapter, _nso.tasks, _nso.evaluate
    arm = "AG" if (use_a1 and use_g1) else "A1" if use_a1 else "G1" if use_g1 else "B0"

    torch.set_num_threads(4)
    try:
        torch.set_num_interop_threads(4)
    except Exception:
        pass
    words, vocab, stream = TA.build_corpus()
    _TA_STREAM["s"] = (words, vocab, stream)

    def set_seed(s):
        random.seed(s); torch.manual_seed(s)

    set_seed(seed)
    model, nparams, ff = MDL.build_matched("S", len(vocab), 2000000, d=128, h=4, layers=4, max_len=1200,
                                           window=TA.WINDOW, num_slots=32)
    IV.install_capture_hooks(model)
    opt, sched, warmups = IV.build_optimizer_and_scheduler(
        model, nonslot_lr=2e-3, nonslot_warmup=60, slot_lr=2e-3, slot_warmup=60,
        weight_decay=0.01, steps=steps, grouped=False)
    rng = random.Random(seed * 991 + 7)
    a1_rng = random.Random(seed * 100003 + A1_RNG_BASE)   # DEDICATED — does not perturb main stream
    model.train()
    traj, loss_log, h2_log, a1_log, g1_log, grad_behav, eval_routing = [], [], [], [], [], [], []
    B, N, B_ALIGN = 16, 160, 8
    CKPTS = list(FULL_CKPTS)
    teacher = {"model": None, "hash": None}
    g1_neg_updates = [0]

    def record(step):
        rec = {"step": step}
        rec["routing"] = DIAG.routing_diagnostics(model, vocab, T, distance=96, n=64)
        rec["routing_d16"] = DIAG.routing_diagnostics(model, vocab, T, distance=16, n=64)
        rec["grad_norms"] = DIAG.grad_norm_probe(model, vocab, T)
        opt.zero_grad(set_to_none=True)
        X, P, Tg, _ = TA.make_eval_set('needle', 256, vocab, 123, n=120, distance=96)
        with torch.no_grad():
            rec["needle_d96"] = EV._acc(model, X, P, Tg)
        model.train()
        traj.append(rec)
        # heavy measurement-only probes only at PRIMARY checkpoints (training path unaffected)
        if step in PRIMARY_CKPTS:
            gb = _wak_gradient_probe(model, teacher["model"], vocab, T, IV, OP, O1, step)
            opt.zero_grad(set_to_none=True)
            model.train()
            grad_behav.append(gb)
            er = _eval_time_routing(model, vocab, T)
            er["step"] = step
            model.train()
            eval_routing.append(er)

    def teacher_read_dists(x_aux, qp):
        IV.enable_capture(teacher["model"], True)
        with torch.no_grad():
            _ = teacher["model"](x_aux)
        idx = torch.arange(x_aux.size(0))
        out = [sm._sfs_raddr[idx, qp].detach().clone() for sm in teacher["model"].slot_mixers()]
        IV.enable_capture(teacher["model"], False)
        return out

    t0 = time.time()
    for step in range(steps):
        if step in CKPTS:
            record(step)
        if step == 600 and teacher["model"] is None:
            tm = copy.deepcopy(model)
            for p in tm.parameters():
                p.requires_grad_(False)
            tm.eval()
            teacher["model"] = tm
            h = hashlib.sha256()
            for _, p in sorted(tm.named_parameters(), key=lambda kv: kv[0]):
                h.update(p.detach().cpu().numpy().tobytes())
            teacher["hash"] = h.hexdigest()

        x, y, mask, _phase = IV.curriculum_batch(step, stream, vocab, B, N, rng, T)
        lo = model(x)
        if mask is None:
            main = F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1))
        else:
            sel = mask.reshape(-1)
            main = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
        aux = None  # accumulates auxiliary terms (alignment + teacher [+ A1]) for G1 gradient split
        lam = IV.lambda_align(step)
        aux_val = None
        if lam > 0.0:
            xa, fp, qp = IV.aux_needle_batch(vocab, B_ALIGN, N, rng, T)
            la, ov = IV.alignment_loss(model, xa, fp, qp)
            aux = (la * lam) if aux is None else aux + lam * la
            aux_val = {"lambda": lam, "L_align": la.item(), "overlap": ov}
        h2c = OP.h2_coefficient(step)
        if h2c > 0.0 and teacher["model"] is not None:
            xa2, fp2, qp2 = IV.aux_needle_batch(vocab, B_ALIGN, N, rng, T)
            tdists = teacher_read_dists(xa2, qp2)
            kl = OP.h2_loss(model, xa2, qp2, tdists)
            aux = (h2c * kl) if aux is None else aux + h2c * kl
            if step % 100 == 0 or step in CKPTS:
                h2_log.append({"step": step, "h2_coef": h2c, "kl": kl.item(),
                               "teacher_hash": teacher["hash"]})
        # ---- A1 lever ----
        if use_a1:
            lam_a1 = OP.o1r_lambda(step)   # same schedule as the closest prior correct-slot objective
            if lam_a1 > 0.0:
                xa1, fp1, qp1 = IAG.a1_hard_negative_batch(vocab, B_ALIGN, N, a1_rng, T, A1_PARTITION)
                la1, ov1 = IAG.a1_loss(model, xa1, fp1, qp1)
                aux = (lam_a1 * la1) if aux is None else aux + lam_a1 * la1
                if step % 100 == 0 or step in CKPTS:
                    a1_log.append({"step": step, "lam_a1": lam_a1, "L_a1": la1.item(), "overlap": ov1})
        # ---- backward (+ G1 projection) ----
        opt.zero_grad()
        if use_g1 and aux is not None:
            main.backward()
            wak = IAG.write_addr_params(model)
            g_lm_wak = {n: (p.grad.detach().clone() if p.grad is not None else torch.zeros_like(p))
                        for n, p in wak}
            lm_norm_sq = sum((g_lm_wak[n] ** 2).sum().item() for n, _ in wak)
            aux.backward()
            m = IAG.project_write_addr_grad(model, g_lm_wak, lm_norm_sq)
            if m["projected"]:
                g1_neg_updates[0] += 1
            if step % 100 == 0 or step in CKPTS:
                g1_log.append({"step": step, **m})
        else:
            total = main if aux is None else (main + aux)
            total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step()
        if step in CKPTS or (aux is not None and step % 100 == 0):
            loss_log.append({"step": step, "main_loss": main.item(), "aux": aux_val,
                             "lr": [g["lr"] for g in opt.param_groups]})
    record(steps)
    ev = EV.eval_suite(model, vocab, stream)
    rec = {"arm": arm, "seed": seed, "use_a1": use_a1, "use_g1": use_g1,
           "params": nparams, "ff": ff,
           "needle_by_dist": ev["needle_by_dist"], "ppl": ev["ppl"],
           "binding_by_k": ev["binding_by_k"], "supersession": ev["supersession"],
           "source": ev["source"], "multihop": ev["multihop"],
           "trajectory": traj, "loss_log": loss_log, "h2_log": h2_log,
           "a1_log": a1_log, "g1_log": g1_log, "grad_behaviour": grad_behav,
           "eval_time_routing": eval_routing,
           "g1_negative_cosine_updates": g1_neg_updates[0],
           "h2_teacher_hash": teacher["hash"], "train_s": round(time.time() - t0, 1)}
    rec["ablation"] = EV.s_ablations(model, vocab)
    return rec


def run_aplus(seed, steps=1200):
    import persistence_arms as PA
    return PA.run_aplus(seed, steps=steps)


DISPATCH = {
    "A+": lambda s, steps=1200: run_aplus(s, steps),
    "B0": lambda s, steps=1200: run_ag_arm(s, use_a1=False, use_g1=False, steps=steps),
    "A1": lambda s, steps=1200: run_ag_arm(s, use_a1=True, use_g1=False, steps=steps),
    "G1": lambda s, steps=1200: run_ag_arm(s, use_a1=False, use_g1=True, steps=steps),
    "AG": lambda s, steps=1200: run_ag_arm(s, use_a1=True, use_g1=True, steps=steps),
}


def run_arm(arm, seed, steps=1200):
    if arm not in DISPATCH:
        raise SystemExit(f"unknown arm {arm}")
    return DISPATCH[arm](seed, steps=steps)
