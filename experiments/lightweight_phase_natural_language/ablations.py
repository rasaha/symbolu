"""
ablations.py — causal ablations for Phase and binding slots.

A component is load-bearing only if corrupting it causes a meaningful loss on the
capability it is meant to provide. Ablations are applied at EVAL time by toggling
the model's ablation state or by corrupting the frozen module's parameters/state
on a copy — training weights are never changed.
"""

from __future__ import annotations

import copy
from typing import Dict, List

import torch

from .datasets import Example, Tokenizer
from .evaluate import evaluate
from .models import ExperimentLM


def _clone_eval(model: ExperimentLM) -> ExperimentLM:
    m = copy.deepcopy(model)
    m.eval()
    return m


def phase_ablations(model: ExperimentLM, test: List[Example], tok: Tokenizer,
                    tasks: List[str]) -> Dict[str, Dict]:
    out = {}
    # baseline
    out["baseline"] = _subset(evaluate(model, test, tok), tasks)

    # 1. Phase disabled
    m = _clone_eval(model)
    m.abl.phase_disabled = True
    out["phase_disabled"] = _subset(evaluate(m, test, tok), tasks)

    # 2. Phase key/query weights randomized (destroys learned retrieval)
    m = _clone_eval(model)
    with torch.no_grad():
        for blk in m.blocks:
            if hasattr(blk, "phase"):
                for lin in (blk.phase.W_phi_q, blk.phase.W_phi_k):
                    lin.weight.normal_(0, 1.0)
    out["phase_weights_randomized"] = _subset(evaluate(m, test, tok), tasks)

    # 3. Phase capacity reduced (zero half the heads' value projection rows)
    m = _clone_eval(model)
    with torch.no_grad():
        for blk in m.blocks:
            if hasattr(blk, "phase"):
                w = blk.phase.W_v.weight
                w[: w.shape[0] // 2] = 0.0
    out["phase_capacity_reduced"] = _subset(evaluate(m, test, tok), tasks)
    return out


def slot_ablations(model: ExperimentLM, test: List[Example], tok: Tokenizer,
                   tasks: List[str]) -> Dict[str, Dict]:
    out = {}
    out["baseline"] = _subset(evaluate(model, test, tok), tasks)

    # 1. slots disabled
    m = _clone_eval(model)
    m.abl.slots_disabled = True
    out["slots_disabled"] = _subset(evaluate(m, test, tok), tasks)

    # 2. slot key projection randomized (destroys content addressing)
    m = _clone_eval(model)
    with torch.no_grad():
        for blk in m.blocks:
            if hasattr(blk, "slots"):
                blk.slots.to_wkey.weight.normal_(0, 1.0)
                blk.slots.to_query.weight.normal_(0, 1.0)
    out["slot_keys_randomized"] = _subset(evaluate(m, test, tok), tasks)

    # 3. slot values shuffled across positions at read
    m = _clone_eval(model)
    m.abl.slot_value_shuffle = True
    out["slot_values_shuffled"] = _subset(evaluate(m, test, tok), tasks)

    # 4. reduce Top-K to 1
    m = _clone_eval(model)
    with torch.no_grad():
        for blk in m.blocks:
            if hasattr(blk, "slots"):
                blk.slots.top_k = 1
    out["slot_top_k_1"] = _subset(evaluate(m, test, tok), tasks)
    return out


def _subset(results: Dict, tasks: List[str]) -> Dict:
    return {t: results.get(t, {}) for t in tasks}
