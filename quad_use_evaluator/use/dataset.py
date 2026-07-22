"""Build per-query prediction datasets across model seeds and evaluation conditions.

The "model" is the frozen bounded task-only Quad transformer (BD-A) — the prior program's best
generalizer, on which Quad retrieval is causally necessary. It is trained once per seed by the
UNMODIFIED prior package and then frozen; USE only observes completed inferences.

Per query we record: the correctness label (failure = predicted != target), the confidence
baselines, and the USE signal vector for every (channel set x phase mapping). Ground truth is
used only to form the label; USE and the baselines never see it.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import torch

from . import _qgr_path  # noqa: F401
from qgr.experiment import FrozenConfig
from qgr.train import train_arm
from qgr.mqar import MQARConfig, generate_batch, split_seed, IGNORE_INDEX

from .capture import run_inference
from .phases import PhaseExtractor, MAPPINGS
from .channels import CHANNEL_SETS
from .use_signals import use_signals_for_batch, SIGNAL_NAMES
from .baselines import baseline_signals, BASELINE_NAMES


def bounded_fc(alpha: float = 4.0) -> FrozenConfig:
    fc = FrozenConfig(); fc.bounded = True; fc.bound_alpha = alpha
    return fc


def train_model(fc: FrozenConfig, seed: int):
    """Train and freeze BD-A (bounded, task-only) via the unmodified prior package."""
    r = train_arm(fc.model_cfg(), fc.base_mqar(), fc.train_cfg("A", seed))
    m = r["model"]; m.eval()
    for p in m.parameters():
        p.requires_grad_(False)
    return m, r["final_val"]["acc"]


def conditions(fc: FrozenConfig) -> Dict[str, MQARConfig]:
    """The required evaluation suite (MQAR-scoped analogs of the prompt's dataset families)."""
    v = fc.vocab_size
    return {
        "in_distribution": MQARConfig(fc.num_kv, fc.num_queries, 0, v, 1),
        "long_context": MQARConfig(fc.num_kv, fc.num_queries, 32, v, 1),
        "distractor_robust": MQARConfig(8, fc.num_queries, 0, v, 1),
        "multi_relation": MQARConfig(fc.num_kv, fc.num_queries, 0, v, 2),
        "long_and_hard": MQARConfig(8, fc.num_queries, 24, v, 1),   # stress: confident-error / hallucination-style
    }


def _combos() -> List[Tuple[str, str]]:
    return [(cs, m) for cs in CHANNEL_SETS for m in MAPPINGS]


@torch.no_grad()
def build_condition(model, mq: MQARConfig, seed: int, n_batches: int, batch_size: int,
                    extractor: PhaseExtractor, W: int = 6) -> Dict[str, np.ndarray]:
    """Return per-query arrays for one condition: label, baselines, and all USE signal features."""
    combos = _combos()
    acc: Dict[str, List[np.ndarray]] = {}
    labels: List[np.ndarray] = []
    corrects: List[np.ndarray] = []
    for i in range(n_batches):
        batch = generate_batch(mq, split_seed(seed, "test", 10_000 + i), batch_size)
        rec = run_inference(model, batch.tokens)
        qmask = batch.targets != IGNORE_INDEX
        b_idx, q_idx = qmask.nonzero(as_tuple=True)
        if b_idx.numel() == 0:
            continue
        pred = rec["pred"][b_idx, q_idx]
        tgt = batch.targets[b_idx, q_idx]
        correct = (pred == tgt)
        corrects.append(correct.numpy().astype(int))
        labels.append((~correct).numpy().astype(int))            # failure = 1
        # baselines
        bl = baseline_signals(rec, (b_idx, q_idx))
        for k, v in bl.items():
            acc.setdefault(f"BASE::{k}", []).append(v.numpy())
        # USE signals for every (channel set, mapping)
        for cs, mp in combos:
            sig = use_signals_for_batch(rec, model, (b_idx, q_idx), cs, mp, extractor, W=W)
            for sname, v in sig.items():
                acc.setdefault(f"USE::{cs}::{mp}::{sname}", []).append(v.numpy())
    out = {k: np.concatenate(v) for k, v in acc.items()}
    out["label_failure"] = np.concatenate(labels) if labels else np.zeros(0, dtype=int)
    out["correct"] = np.concatenate(corrects) if corrects else np.zeros(0, dtype=int)
    return out


def build_all(seeds: List[int], n_batches: int = 24, batch_size: int = 32,
              alpha: float = 4.0, W: int = 6, verbose=True) -> Dict:
    """Build the full dataset: {seed: {condition: arrays}} plus the frozen model accuracies."""
    fc = bounded_fc(alpha)
    extractor = PhaseExtractor()
    data = {}
    model_acc = {}
    for s in seeds:
        model, acc = train_model(fc, s)
        model_acc[s] = acc
        if verbose:
            print(f"[seed {s}] BD-A in-dist acc={acc:.3f}")
        conds = conditions(fc)
        data[s] = {}
        for cname, mq in conds.items():
            d = build_condition(model, mq, s, n_batches, batch_size, extractor, W=W)
            data[s][cname] = d
            if verbose:
                n = len(d["label_failure"]); fr = float(d["label_failure"].mean()) if n else float("nan")
                print(f"  {cname:18s}: queries={n} failure_rate={fr:.3f}")
    return {"data": data, "model_acc": model_acc, "seeds": seeds,
            "conditions": list(conditions(fc).keys()), "W": W, "alpha": alpha,
            "n_batches": n_batches, "batch_size": batch_size}
