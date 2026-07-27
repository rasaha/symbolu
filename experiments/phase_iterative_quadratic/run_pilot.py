"""
run_pilot.py — §7 two-hop pilot: does iterative query-update create headroom over static routing?

Gate (must pass to authorize the full 9P:3Q study):
    static learned-router accuracy ≤ 0.25
    iterative oracle accuracy ≥ 0.85
    random routing near chance
    at least one learned iterative arm in [0.35, 0.75]
Decisive Phase question (secondary): iterative Phase − iterative COND, with phase-zero/shuffle
controls. Uses the validated non-saturated multi-hop task.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch

from .multihop_dataset import build_vocab, generate
from .config import TrainCfg, PILOT_ARMS, GATE_STATIC_MAX, GATE_ORACLE_MIN, GATE_ITER_LO, GATE_ITER_HI
from .hybrid_model import IterativeHybrid
from .train import train_hybrid
from .evaluate import evaluate

HERE = Path(__file__).resolve().parent
N_EVENTS, K, W = 48, 8, 32

# arm -> (router_kind, use_phase, iterative, routing_mode, hops)
ARMS = {
    "P0-static-cond": ("cond", False, False, "learned", 1),
    "P1-static-phase": ("cond", True, False, "learned", 1),
    "I0-iter-cond": ("cond", False, True, "learned", 2),
    "I1-iter-cosine": ("cosine", False, True, "learned", 2),
    "I2-iter-bilinear": ("bilinear", False, True, "learned", 2),
    "I3-iter-phase": ("cond", True, True, "learned", 2),
    "I4-phase-zero": ("cond", True, True, "phase_zero", 2),
    "I5-phase-shuffled": ("cond", True, True, "phase_shuffle", 2),
    "I6-random": ("cond", False, True, "random", 2),
    "I7-oracle": ("cond", False, True, "oracle", 2),
    "Q-local": ("cond", False, True, "local", 2),
}


def build(arm, vocab, n_id, seed):
    kind, use_phase, iterative, mode, hops = ARMS[arm]
    torch.manual_seed(seed)
    return IterativeHybrid(vocab.size, n_id, hops=hops, router_kind=kind, use_phase=use_phase,
                           iterative=iterative, routing_mode=mode, W=W, K=(0 if mode == "local" else K))


def run(seed=0, depth=2):
    vocab = build_vocab(); n_id = vocab.n_id
    def gen(bs, s): return generate(vocab, N_EVENTS, depth, bs, s)
    te = generate(vocab, N_EVENTS, depth, 400, 77000)
    t0 = time.time(); res = {}
    for arm in PILOT_ARMS:
        m = build(arm, vocab, n_id, seed)
        train_hybrid(m, gen, vocab, TrainCfg(seed=seed, steps=800))
        ev = evaluate(m, te, vocab)
        res[arm] = {"accuracy": ev["accuracy"], "complete_chain": ev["complete_chain_retrieval"],
                    "hop_recall": ev["hop_recall"]}
        print(f"[{arm}] acc={ev['accuracy']:.3f} chain={ev['complete_chain_retrieval']:.3f} "
              f"hops={ {h: round(v,2) for h,v in ev['hop_recall'].items()} } ({time.time()-t0:.0f}s)", flush=True)
    gate = decide(res, n_id)
    out = {"arms": res, "gate": gate, "chance": 1.0 / n_id}
    (HERE / "results" / "pilot.json").write_text(json.dumps(out, indent=2, default=float))
    print("GATE:", json.dumps(gate, indent=1, default=float), flush=True)
    print("PILOT DONE", flush=True)
    return out


def decide(res, n_id):
    static = min(res["P0-static-cond"]["accuracy"], res["P1-static-phase"]["accuracy"])
    static_max = max(res["P0-static-cond"]["accuracy"], res["P1-static-phase"]["accuracy"])
    oracle = res["I7-oracle"]["accuracy"]; rnd = res["I6-random"]["accuracy"]
    iters = {a: res[a]["accuracy"] for a in ("I0-iter-cond", "I1-iter-cosine", "I2-iter-bilinear", "I3-iter-phase")}
    in_window = {a: (GATE_ITER_LO <= v <= GATE_ITER_HI) for a, v in iters.items()}
    phase_gain = res["I3-iter-phase"]["accuracy"] - res["I0-iter-cond"]["accuracy"]
    passed = (static_max <= GATE_STATIC_MAX and oracle >= GATE_ORACLE_MIN
              and rnd <= 3.0 / n_id + 0.05 and any(in_window.values()))
    return {"static_max": static_max, "oracle": oracle, "random": rnd, "chance": 1.0 / n_id,
            "iter_accuracies": iters, "any_iter_in_window": any(in_window.values()),
            "iter_in_window": in_window,
            "iter_best": max(iters, key=iters.get), "iter_best_acc": max(iters.values()),
            "phase_minus_itercond": phase_gain,
            "gate_passed": passed,
            "decision": "launch full 9P:3Q study" if passed else "iterative headroom not demonstrated — do not launch"}


if __name__ == "__main__":
    run()
