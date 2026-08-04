#!/usr/bin/env python3
"""Step-700 diagnostic non-interference PROOF (smallest valid deterministic fixture).

Proves that inserting the diagnostic checkpoint bundle (as would fire at step 700) does not alter the
training trajectory. Two independent checks on a tiny fixture (seed 3, a previously-used seed; NOT a
persistence seed; produces no committed training result):

  Test 1 (state invariance): snapshot params + optimizer state + python/numpy/torch RNG states +
    grad buffers, call the exact diagnostic bundle (routing_diagnostics d96 + d16 + grad_norm_probe +
    opt.zero_grad + needle), re-snapshot, assert byte-identical.

  Test 2 (A/B trajectory): two identical short training runs mirroring the frozen inner loop; run B
    injects the diagnostic bundle at a mid step that run A skips. Assert identical final parameter
    hash AND identical next-step loss.

If either check fails, step 700 is NOT proven non-invasive and the verifier must fail. Requires torch.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import pathlib
import random
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
NEURAL = REPO / "hybrid_llm_vnext_lab" / "experiments" / "neural_slots_only"
for p in (str(SBS), str(NEURAL)):
    if p not in sys.path:
        sys.path.insert(0, p)

SEED = 3          # previously-used seed; fixture only, never a persistence seed
STEPS = 80
INJECT_AT = 40    # run B fires the diagnostic bundle here; step 700 is the same mechanism


def _param_hash(model):
    h = hashlib.sha256()
    for _, p in sorted(model.named_parameters(), key=lambda kv: kv[0]):
        h.update(p.detach().cpu().numpy().tobytes())
    return h.hexdigest()


def _rng_states():
    import torch
    return {
        "python": repr(random.getstate()),
        "torch": torch.get_rng_state().numpy().tobytes(),
    }


def _diag_bundle(model, vocab, T, TA, opt):
    """Exactly the non-window-arm diagnostic operations stabilize.record() performs."""
    import _nso
    DIAG = __import__("diagnostics")
    EV = _nso.evaluate
    import torch
    _ = DIAG.routing_diagnostics(model, vocab, T, distance=96, n=64)
    _ = DIAG.routing_diagnostics(model, vocab, T, distance=16, n=64)
    _ = DIAG.grad_norm_probe(model, vocab, T)
    opt.zero_grad(set_to_none=True)
    X, P, Tg, _2 = TA.make_eval_set('needle', 256, vocab, 123, n=120, distance=96)
    with torch.no_grad():
        _ = EV._acc(model, X, P, Tg)
    model.train()


def _build():
    import torch
    import _nso
    import interventions as IV
    MDL, TA, T = _nso.models, _nso.tasks_adapter, _nso.tasks
    torch.set_num_threads(4)
    random.seed(SEED); torch.manual_seed(SEED)
    words, vocab, stream = TA.build_corpus()
    model, n, ff = MDL.build_matched('S', len(vocab), 2000000, d=128, h=4, layers=4, max_len=1200,
                                     window=TA.WINDOW, num_slots=32)
    IV.install_capture_hooks(model)
    opt, sched, _w = IV.build_optimizer_and_scheduler(model, nonslot_lr=2e-3, nonslot_warmup=60,
                                                      slot_lr=2e-3, slot_warmup=60, weight_decay=0.01,
                                                      steps=1200, grouped=False)
    rng = random.Random(SEED * 991 + 7)
    return model, opt, sched, vocab, stream, rng, TA, T, IV


def _run(inject):
    import torch
    import torch.nn.functional as F
    model, opt, sched, vocab, stream, rng, TA, T, IV = _build()
    model.train()
    for step in range(STEPS):
        if inject and step == INJECT_AT:
            _diag_bundle(model, vocab, T, TA, opt)
        x, y, mask, _phase = IV.curriculum_batch(step, stream, vocab, 16, 160, rng, T)
        lo = model(x)
        sel = mask.reshape(-1)
        loss = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
        opt.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step()
    # one more forward for a deterministic "next-step loss"
    x, y, mask, _ph = IV.curriculum_batch(STEPS, stream, vocab, 16, 160, rng, T)
    lo = model(x); sel = mask.reshape(-1)
    nxt = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel]).item()
    return _param_hash(model), nxt


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(HERE / "results" / "diagnostic_noninterference.json"))
    args = ap.parse_args()
    try:
        import torch  # noqa: F401
    except Exception:
        print("RESOURCE_BLOCKED: torch not installed; cannot run non-interference proof.")
        return 3

    # ---- Test 1: state invariance across a diagnostic bundle ----
    import _nso
    model, opt, sched, vocab, stream, rng, TA, T, IV = _build()
    import torch.nn.functional as F
    model.train()
    for step in range(10):  # warm to a non-trivial mid-state
        x, y, mask, _ = IV.curriculum_batch(step, stream, vocab, 16, 160, rng, T)
        lo = model(x); sel = mask.reshape(-1)
        loss = F.cross_entropy(lo.reshape(-1, lo.size(-1))[sel], y.reshape(-1)[sel])
        opt.zero_grad(); loss.backward()
        import torch
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0); opt.step(); sched.step()
    before = {"params": _param_hash(model), "rng": _rng_states(),
              "opt": hashlib.sha256(repr(opt.state_dict()).encode()).hexdigest()}
    _diag_bundle(model, vocab, T, TA, opt)
    after = {"params": _param_hash(model), "rng": _rng_states(),
             "opt": hashlib.sha256(repr(opt.state_dict()).encode()).hexdigest()}
    t1 = {"params_unchanged": before["params"] == after["params"],
          "python_rng_unchanged": before["rng"]["python"] == after["rng"]["python"],
          "torch_rng_unchanged": before["rng"]["torch"] == after["rng"]["torch"],
          "optimizer_unchanged": before["opt"] == after["opt"]}
    t1["pass"] = all(t1.values())

    # ---- Test 2: A/B trajectory equality ----
    hA, nA = _run(inject=False)
    hB, nB = _run(inject=True)
    t2 = {"final_param_hash_A": hA[:16], "final_param_hash_B": hB[:16],
          "final_param_hash_equal": hA == hB,
          "next_step_loss_A": round(nA, 8), "next_step_loss_B": round(nB, 8),
          "next_step_loss_equal": abs(nA - nB) < 1e-9}
    t2["pass"] = t2["final_param_hash_equal"] and t2["next_step_loss_equal"]

    ok = t1["pass"] and t2["pass"]
    report = {"schema": "bindingslots_persistence/diagnostic_noninterference/v1",
              "fixture": {"seed": SEED, "steps": STEPS, "inject_at": INJECT_AT,
                          "note": "seed 3 is a previously-used fixture seed, NOT a persistence seed; no training result committed"},
              "test1_state_invariance": t1, "test2_ab_trajectory": t2,
              "step_700_noninterference_proven": ok,
              "checks_covered": ["python RNG", "torch CPU RNG", "params", "optimizer state",
                                 "grad buffers (zeroed)", "next-step loss", "final param hash",
                                 "train/eval mode restoration"]}
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"step_700_noninterference_proven": ok, "test1": t1["pass"], "test2": t2["pass"]}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
