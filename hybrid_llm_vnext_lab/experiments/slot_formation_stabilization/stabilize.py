#!/usr/bin/env python3
"""Slot-formation stabilization arm runner.

Reuses the FROZEN S architecture (neural_slots_only/models.py), the FROZEN eval suite +
ablations (neural_slots_only/evaluate.py), and the FROZEN tasks/tokenizer/corpus
(experiments/phase_lc/tasks.py via tasks_adapter). The ONLY per-arm differences are the
pre-registered intervention surfaces: optimizer parameter groups + warmup (Family 1), orthogonal
slot-key init (Family 2), curriculum + temporary write-read alignment (Family 3), plus
diagnostic instrumentation. Requires torch.

B0 (no intervention) is designed to reproduce the frozen five-seed S numbers exactly: its training
path is byte-for-byte the frozen loop (single AdamW group, warmup 60, ABC_MIX batches, identical
clip/step order); diagnostics never advance the torch RNG or touch optimizer state.

CLI:  python stabilize.py --arm O1 --seeds 3,6,7 --run-id stageA_O1 [--steps 1200]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
LAB = HERE.parents[1]
NEURAL = LAB / "experiments" / "neural_slots_only"
for p in (str(HERE), str(NEURAL)):
    if p not in sys.path:
        sys.path.insert(0, p)

CKPTS = [0, 60, 120, 300, 600, 900]
B_ALIGN = 8


def _load_arm(arm_id):
    mx = json.loads((HERE / "EXPERIMENT_MATRIX.json").read_text())
    for a in mx["stage_a"]["arms"]:
        if a["id"] == arm_id:
            return a
    if arm_id == "A+":
        return {"id": "A+", "family": "control", "window_only": True}
    raise SystemExit(f"unknown arm {arm_id}")


def run_arm(arm_id, seed, steps=1200, N=160, B=16, target_params=2000000, num_slots=32,
            threads=4, wd=0.01, base_lr=2e-3):
    import torch
    import torch.nn.functional as F
    import _nso
    MDL = _nso.models
    TA = _nso.tasks_adapter
    EV = _nso.evaluate
    import interventions as IV
    import diagnostics as DIAG
    T = _nso.tasks  # frozen phase_lc tasks module

    torch.set_num_threads(threads)
    try:
        torch.set_num_interop_threads(threads)
    except Exception:
        pass

    spec = _load_arm(arm_id)
    window_only = spec.get("window_only", False)
    grouped = spec.get("family") == "1_optimizer"
    orthogonal = bool(spec.get("orthogonal_keys", False))
    curriculum = bool(spec.get("curriculum", False))
    alignment = bool(spec.get("alignment", False))
    slot_lr = spec.get("slot_lr", base_lr)
    slot_warmup = spec.get("slot_warmup", 60)
    nonslot_lr = spec.get("nonslot_lr", base_lr)
    nonslot_warmup = spec.get("nonslot_warmup", 60)

    words, vocab, stream = TA.build_corpus()

    def set_seed(s):
        random.seed(s); torch.manual_seed(s)

    set_seed(seed)
    if window_only:
        # A+ : window-only, parameter-matched to S's exact param count (mirror frozen protocol)
        s_probe, s_params, _ = MDL.build_matched("S", len(vocab), target_params, d=128, h=4,
                                                 layers=4, max_len=1200, window=TA.WINDOW, num_slots=num_slots)
        set_seed(seed)
        model, nparams, ff = MDL.build_matched("A", len(vocab), s_params, d=128, h=4, layers=4,
                                               max_len=1200, window=TA.WINDOW, num_slots=num_slots)
    else:
        model, nparams, ff = MDL.build_matched("S", len(vocab), target_params, d=128, h=4, layers=4,
                                               max_len=1200, window=TA.WINDOW, num_slots=num_slots)

    init_audit = None
    if orthogonal:
        base_keys = [sm.slot_keys.detach().clone() for sm in model.slot_mixers()]
        ortho_audit = IV.orthogonal_slot_key_init(model, seed)
        new_keys = [sm.slot_keys.detach().clone() for sm in model.slot_mixers()]
        init_audit = {
            "method": "deterministic QR-orthonormal + row-normalize, per (seed, layer)",
            "baseline": [IV.key_cosine_stats(k) for k in base_keys],
            "K1": [IV.key_cosine_stats(k) for k in new_keys],
            "shape_dtype_count": ortho_audit["per_layer"],
            "deterministic_hash_per_seed": _keys_hash(new_keys),
        }

    group_audit = IV.param_group_audit(model)
    hooks = IV.install_capture_hooks(model)

    opt, sched, warmups = IV.build_optimizer_and_scheduler(
        model, nonslot_lr=nonslot_lr, nonslot_warmup=nonslot_warmup, slot_lr=slot_lr,
        slot_warmup=slot_warmup, weight_decay=wd, steps=steps, grouped=grouped)

    rng = random.Random(seed * 991 + 7)
    model.train()
    traj = []
    loss_log = []

    def record(step):
        rec = {"step": step}
        if not window_only:
            rec["routing"] = DIAG.routing_diagnostics(model, vocab, T, distance=96, n=64)
            rec["routing_d16"] = DIAG.routing_diagnostics(model, vocab, T, distance=16, n=64)
            rec["grad_norms"] = DIAG.grad_norm_probe(model, vocab, T)
            opt.zero_grad(set_to_none=True)
        rec["needle_d96"] = _needle_at(model, vocab, TA, dist=96)
        model.train()
        traj.append(rec)

    t0 = time.time()
    for step in range(steps):
        if step in CKPTS:
            record(step)
        if curriculum:
            x, y, mask, _phase = IV.curriculum_batch(step, stream, vocab, B, N, rng, T)
        else:
            x, y, mask = TA.train_batch(stream, B, N, vocab, rng)
        lo = model(x)
        if mask is None:
            main = F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1))
        else:
            sel = mask.reshape(-1)
            main = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
        total = main
        lam = IV.lambda_align(step) if alignment else 0.0
        aux_val = None
        if alignment and lam > 0.0:
            xa, fp, qp = IV.aux_needle_batch(vocab, B_ALIGN, N, rng, T)
            la, ov = IV.alignment_loss(model, xa, fp, qp)
            total = main + lam * la
            aux_val = {"lambda": lam, "L_align": la.item(), "overlap": ov}
        opt.zero_grad(); total.backward()
        import torch as _t
        _t.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step()
        if step in CKPTS or (alignment and step % 100 == 0):
            loss_log.append({"step": step, "main_loss": main.item(),
                             "aux": aux_val, "lr": [g["lr"] for g in opt.param_groups]})
    # final checkpoint (step 1200) diagnostics
    record(steps)

    ev = EV.eval_suite(model, vocab, stream)
    rec = {"arm": arm_id, "seed": seed, "params": nparams, "ff": ff,
           "needle_by_dist": ev["needle_by_dist"], "ppl": ev["ppl"],
           "binding_by_k": ev["binding_by_k"], "supersession": ev["supersession"],
           "source": ev["source"], "multihop": ev["multihop"],
           "warmups_by_group": warmups, "grouped_optimizer": grouped,
           "param_group_audit": group_audit, "init_audit": init_audit,
           "trajectory": traj, "loss_log": loss_log,
           "train_s": round(time.time() - t0, 1)}
    if not window_only:
        rec["ablation"] = EV.s_ablations(model, vocab)
    for h in hooks:
        h.remove()
    return rec


def _needle_at(model, vocab, TA, dist=96):
    import torch
    import _nso
    EV = _nso.evaluate
    X, P, Tg, _ = TA.make_eval_set('needle', 256, vocab, 123, n=120, distance=dist)
    with torch.no_grad():
        return EV._acc(model, X, P, Tg)


def _keys_hash(keys):
    import hashlib
    h = hashlib.sha256()
    for k in keys:
        h.update(k.cpu().numpy().tobytes())
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--seeds", default="3,6,7")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--steps", type=int, default=1200)
    ap.add_argument("--out-root", default=str(HERE / "artifacts"))
    args = ap.parse_args()

    try:
        import torch  # noqa: F401
    except Exception:
        print("RESOURCE_BLOCKED: torch not installed; stabilization arm cannot run.")
        return 3

    run_id = args.run_id or f"{args.arm}_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    out_dir = pathlib.Path(args.out_root) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(s) for s in args.seeds.split(",")]
    records = []
    for seed in seeds:
        print(f"[stabilize] arm={args.arm} seed={seed} steps={args.steps}", flush=True)
        rec = run_arm(args.arm, seed, steps=args.steps)
        d96 = rec["needle_by_dist"]["96"]
        print(f"[stabilize] arm={args.arm} seed={seed} needle@d96={d96:.3f} "
              f"ppl256={rec['ppl']['256']:.1f} ({rec['train_s']}s)", flush=True)
        records.append(rec)
        (out_dir / f"{args.arm}_seed{seed}.json").write_text(json.dumps(rec, indent=2))
        (out_dir / "partial.json").write_text(json.dumps({"arm": args.arm, "records": records}, indent=2))
    (out_dir / f"{args.arm}_results.json").write_text(json.dumps({"arm": args.arm, "records": records}, indent=2))
    print(f"[stabilize] wrote {out_dir}/{args.arm}_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
