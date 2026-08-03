#!/usr/bin/env python3
"""Slots-only (S) neural attribution experiment. Phase-free A / S / A+ arms, 3 seeds.

Answers: can bounded slots learn the beyond-window retrieval capability with NO Phase present
during initialization, forward, backprop, or evaluation? The decisive comparison is S - A at
needle@d96, with a parameter-matched A+ control.

Requires torch. With torch absent this exits NON-ZERO (an explicitly requested neural run that
cannot execute is a failure); `--check-environment` reports availability and exits 0.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _torch_ok():
    try:
        import torch  # noqa: F401
        return True
    except Exception:
        return False


def _run(args) -> int:
    import torch
    import torch.nn.functional as F
    import models as MDL
    import tasks_adapter as TA
    import evaluate as EV

    # reproducible CPU environment
    torch.set_num_threads(args.threads)
    try:
        torch.set_num_interop_threads(args.threads)
    except Exception:
        pass

    words, vocab, stream = TA.build_corpus()
    target = args.target_params
    steps, N, B = args.steps, args.N, args.batch

    def set_seed(s):
        random.seed(s); torch.manual_seed(s)

    def train_arm(arm, seed, tp):
        set_seed(seed)
        model, nparams, ff = MDL.build_matched(arm, len(vocab), tp, d=128, h=4, layers=4,
                                               max_len=1200, window=TA.WINDOW, num_slots=args.num_slots)
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=0.01)
        warm = max(20, steps // 20)
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, s / warm))
        rng = random.Random(seed * 991 + 7)
        model.train()
        for step in range(steps):
            x, y, mask = TA.train_batch(stream, B, N, vocab, rng)
            lo = model(x)
            if mask is None:
                loss = F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1))
            else:
                sel = mask.reshape(-1)
                loss = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step()
        return model, nparams, ff

    run_id = args.run_id or time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = HERE / "artifacts" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {"config": vars(args), "vocab": len(vocab), "corpus_tokens": len(stream),
               "corpus_hashes": TA.corpus_hashes(), "run_id": run_id,
               "torch": torch.__version__, "threads": torch.get_num_threads(),
               "deterministic": torch.are_deterministic_algorithms_enabled(),
               "arms": {}}

    seeds = [int(s) for s in args.seeds.split(",")]
    # build S first to get its exact param count for the A+ match
    s_params = None
    for arm in ["A", "S", "A+"]:
        results["arms"][arm] = []
        # A+ is window-only (arm 'A') matched to S's exact param count; A/A+ use build target
        build_arm = "A" if arm == "A+" else arm
        tp = target if arm != "A+" else (s_params or target)
        for seed in seeds:
            t0 = time.time()
            model, nparams, ff = train_arm(build_arm, seed, tp)
            ev = EV.eval_suite(model, vocab, stream)
            rec = {"seed": seed, "params": nparams, "ff": ff,
                   "needle_by_dist": ev["needle_by_dist"], "ppl": ev["ppl"],
                   "binding_by_k": ev["binding_by_k"], "supersession": ev["supersession"],
                   "source": ev["source"], "multihop": ev["multihop"],
                   "train_s": round(time.time() - t0, 1)}
            if arm == "S":
                rec["ablation"] = EV.s_ablations(model, vocab)
            results["arms"][arm].append(rec)
            if arm == "S" and s_params is None:
                s_params = nparams
            print(f"[S-exp] {arm} seed{seed} params={nparams} ff={ff} "
                  f"ndl96={ev['needle_by_dist']['96']:.3f} ppl256={ev['ppl']['256']:.1f} "
                  f"({rec['train_s']}s)", flush=True)
            (out_dir / "partial.json").write_text(json.dumps(results, indent=2))
    (out_dir / "slots_only_results.json").write_text(json.dumps(results, indent=2))
    print(f"[S-exp] wrote {out_dir/'slots_only_results.json'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-environment", action="store_true")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--seeds", default="0,1,2")
    ap.add_argument("--steps", type=int, default=1200)
    ap.add_argument("--N", type=int, default=160)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--num-slots", type=int, default=32)
    ap.add_argument("--target-params", type=int, default=2000000)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--threads", type=int, default=4)
    args = ap.parse_args()

    if args.check_environment:
        print(json.dumps({"torch_available": _torch_ok(),
                          "python": sys.version.split()[0]}, indent=2))
        return 0
    if not _torch_ok():
        print("RESOURCE_BLOCKED: PyTorch not installed; the slots-only neural experiment cannot run.")
        print("  python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu 'numpy<2' torch")
        return 3
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
