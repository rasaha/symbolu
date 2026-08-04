#!/usr/bin/env python3
"""Exact frozen arm implementations for the authorized persistence execution.

A+, R0, O1, O1R, H1 run the FROZEN stabilize.run_arm loop with at most one interventions.py function
swapped in memory (files on disk unchanged, hashes verified elsewhere). H2 needs a mid-training teacher
snapshot + an added distillation term, which cannot be a single-function swap, so it uses a dedicated
loop that copies the frozen inner loop byte-for-byte through step 600 (data-paired with R0) and adds
the teacher term only in its window. Step 700 is added to the diagnostic cadence (proven non-invasive).

Requires torch. Contains NO decision-tree logic; the only execution-order authority is adaptive_plan.
"""
from __future__ import annotations

import contextlib
import copy
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
NEURAL = REPO / "hybrid_llm_vnext_lab" / "experiments" / "neural_slots_only"
FR = REPO / "experiments" / "bindingslots_functional_routing"
for p in (str(HERE), str(SBS), str(NEURAL), str(FR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import objectives_persistence as OP  # noqa: E402

FULL_CKPTS = [0, 60, 120, 300, 600, 700, 900]  # record(1200) added at loop end -> full cadence incl 700


def _patch_ckpts():
    """Add step 700 to the frozen diagnostic cadence (proven non-invasive). Returns a restorer."""
    import stabilize as SB
    saved = list(SB.CKPTS)
    SB.CKPTS = list(FULL_CKPTS)
    def restore():
        SB.CKPTS = saved
    return restore


@contextlib.contextmanager
def _swap(**attrs):
    """Swap interventions.<name> attributes for the duration; always restore."""
    import interventions as IV
    saved = {k: getattr(IV, k) for k in attrs}
    try:
        for k, v in attrs.items():
            setattr(IV, k, v)
        yield
    finally:
        for k, v in saved.items():
            setattr(IV, k, v)


# ------------------------------------------------------------------ A+ / R0 / O1 / O1R (frozen loop)
def run_aplus(seed, steps=1200):
    import stabilize as SB
    r = _patch_ckpts()
    try:
        rec = SB.run_arm("A+", seed, steps=steps)
    finally:
        r()
    rec["arm"] = "A+"
    return rec


def run_r0(seed, steps=1200):
    import stabilize as SB
    r = _patch_ckpts()
    try:
        rec = SB.run_arm("CR1", seed, steps=steps)
    finally:
        r()
    rec["arm"] = "R0"
    return rec


def run_o1(seed, steps=1200):
    import stabilize as SB
    import objectives as O1  # frozen Stage-1 correct-slot loss
    r = _patch_ckpts()
    try:
        with _swap(alignment_loss=O1.correct_slot_prob_loss):
            rec = SB.run_arm("CR1", seed, steps=steps)
    finally:
        r()
    rec["arm"] = "O1"
    return rec


def run_o1r(seed, steps=1200):
    """O1 correct-slot loss + standing residual lambda 0.01 for steps 601-1200 (swap alignment_loss
    AND lambda_align). Everything else is frozen CR1."""
    import stabilize as SB
    import objectives as O1
    r = _patch_ckpts()
    try:
        with _swap(alignment_loss=O1.correct_slot_prob_loss, lambda_align=OP.o1r_lambda):
            rec = SB.run_arm("CR1", seed, steps=steps)
    finally:
        r()
    rec["arm"] = "O1R"
    return rec


# ------------------------------------------------------------------ H1 (optimizer-group swap)
def _h1_build_optimizer_and_scheduler(model, *, nonslot_lr, nonslot_warmup, slot_lr, slot_warmup,
                                      weight_decay, steps, grouped):
    """Two AdamW groups (addressing group + rest), IDENTICAL base LR/warmup/wd to the frozen single
    group, with a 0.1x LR multiplier on the frozen addressing group during steps [600, 900)."""
    import torch
    names = set(OP.H1_NAMES)
    addr, rest = [], []
    for n, p in model.named_parameters():
        (addr if n in names else rest).append(p)
    assert len(addr) == len(names), "H1 addressing group drift"
    groups = [
        {"params": rest, "lr": nonslot_lr, "weight_decay": weight_decay},
        {"params": addr, "lr": nonslot_lr, "weight_decay": weight_decay},
    ]
    opt = torch.optim.AdamW(groups)
    warm = nonslot_warmup
    lambdas = [
        (lambda s: min(1.0, s / warm)),                                  # rest: base warmup
        (lambda s: min(1.0, s / warm) * OP.h1_lr_multiplier(s)),         # addressing: * 0.1 in 600-900
    ]
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambdas)
    return opt, sched, [nonslot_warmup, nonslot_warmup]


def run_h1(seed, steps=1200):
    import stabilize as SB
    # verify the addressing name-list hash before running
    import hashlib
    got = hashlib.sha256("\n".join(OP.H1_MANIFEST["ordered_names"]).encode()).hexdigest()
    assert got == OP.H1_MANIFEST["name_list_sha256"], "H1 name-list hash drift"
    r = _patch_ckpts()
    try:
        with _swap(build_optimizer_and_scheduler=_h1_build_optimizer_and_scheduler):
            rec = SB.run_arm("CR1", seed, steps=steps)
    finally:
        r()
    rec["arm"] = "H1"
    rec["h1_parameter_group_name_list_sha256"] = got
    return rec


# ------------------------------------------------------------------ H2 (dedicated faithful loop)
def run_h2(seed, steps=1200):
    """Frozen CR1 loop copied byte-for-byte through step 600 (data-paired with R0), plus a training-only
    distillation to a step-600 teacher of the address-conditioned slot-read distribution during the H2
    window. Teacher is frozen; absent at evaluation; uses only slot-address distributions (no labels)."""
    import torch
    import torch.nn.functional as F
    import _nso
    import interventions as IV
    import diagnostics as DIAG
    MDL, TA, T, EV = _nso.models, _nso.tasks_adapter, _nso.tasks, _nso.evaluate
    import hashlib
    import time

    torch.set_num_threads(4)
    try:
        torch.set_num_interop_threads(4)
    except Exception:
        pass
    words, vocab, stream = TA.build_corpus()

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
    model.train()
    traj, loss_log, h2_log = [], [], []
    B, N, B_ALIGN = 16, 160, 8
    CKPTS = list(FULL_CKPTS)
    teacher = {"model": None, "hash": None}

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
        # snapshot the step-600 teacher (frozen) BEFORE the step-600 update
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
        sel = mask.reshape(-1)
        main = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
        total = main
        # R0 alignment (steps < 600), byte-identical to CR1
        lam = IV.lambda_align(step)
        aux_val = None
        if lam > 0.0:
            xa, fp, qp = IV.aux_needle_batch(vocab, B_ALIGN, N, rng, T)
            la, ov = IV.alignment_loss(model, xa, fp, qp)
            total = total + lam * la
            aux_val = {"lambda": lam, "L_align": la.item(), "overlap": ov}
        # H2 teacher distillation (training-only), in its window and after the teacher exists
        h2c = OP.h2_coefficient(step)
        if h2c > 0.0 and teacher["model"] is not None:
            xa2, fp2, qp2 = IV.aux_needle_batch(vocab, B_ALIGN, N, rng, T)
            tdists = teacher_read_dists(xa2, qp2)
            kl = OP.h2_loss(model, xa2, qp2, tdists)
            total = total + h2c * kl
            if step % 100 == 0 or step in CKPTS:
                h2_log.append({"step": step, "h2_coef": h2c, "kl": kl.item(),
                               "teacher_hash": teacher["hash"]})
        opt.zero_grad(); total.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step()
        if step in CKPTS or (lam > 0 and step % 100 == 0):
            loss_log.append({"step": step, "main_loss": main.item(), "aux": aux_val,
                             "lr": [g["lr"] for g in opt.param_groups]})
    record(steps)
    ev = EV.eval_suite(model, vocab, stream)
    rec = {"arm": "H2", "seed": seed, "params": nparams, "ff": ff,
           "needle_by_dist": ev["needle_by_dist"], "ppl": ev["ppl"],
           "binding_by_k": ev["binding_by_k"], "supersession": ev["supersession"],
           "source": ev["source"], "multihop": ev["multihop"],
           "trajectory": traj, "loss_log": loss_log, "h2_log": h2_log,
           "h2_teacher_hash": teacher["hash"], "train_s": round(time.time() - t0, 1)}
    rec["ablation"] = EV.s_ablations(model, vocab)
    return rec


DISPATCH = {"A+": run_aplus, "R0": run_r0, "O1": run_o1, "O1R": run_o1r, "H1": run_h1, "H2": run_h2}


def run_arm(arm, seed, steps=1200):
    if arm not in DISPATCH:
        raise SystemExit(f"unknown arm {arm}")
    return DISPATCH[arm](seed, steps=steps)
