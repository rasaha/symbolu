#!/usr/bin/env python3
"""Frozen training-only building blocks for the persistence phase (O1R / H1 / H2).

These are DEFINITIONS, frozen and hashed by the preregistration. They are NOT invoked in the
preregistration task — training requires a separate authorization (see runner_stub.py and
TRAINING_AUTHORIZATION_GATE.md). torch is imported lazily so this module is importable torch-free.

O1R uses the frozen Stage-1 O1 loss (imported) and differs ONLY in the coefficient schedule.
H1 selects the frozen addressing parameter group and its LR multiplier schedule.
H2 defines the step-600 functional teacher target (address-conditioned slot-read distribution) and
   the distillation loss — using only slot-address distributions, never the answer label.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
FR = REPO / "experiments" / "bindingslots_functional_routing"

H1_MANIFEST = json.loads((HERE / "h1_parameter_group_manifest.json").read_text())
H1_NAMES = set(H1_MANIFEST["ordered_names"])


# ----------------------------------------------------------------- O1R coefficient schedule
def o1r_lambda(step: int, start: float = 0.10, decay_start: int = 300, decay_end: int = 600,
               residual: float = 0.01) -> float:
    """O1 lambda for steps < 600, then a STANDING residual (default 0.01) for steps 601-1200."""
    if step < decay_start:
        return start
    if step < decay_end:
        frac = (step - decay_start) / (decay_end - decay_start)
        return start * (1.0 - frac)
    return residual  # steps >= 600 -> standing residual (evaluation uses 0.0, enforced by the runner)


def o1r_correct_slot_loss(model, x_aux, fact_pos, query_pos, eps=1e-6):
    """Identical to the frozen O1 loss; O1R differs only in the coefficient schedule above."""
    import sys
    if str(FR) not in sys.path:
        sys.path.insert(0, str(FR))
    import objectives as O1  # frozen Stage-1 objectives (sha256 pinned)
    return O1.correct_slot_prob_loss(model, x_aux, fact_pos, query_pos, eps=eps)


# ----------------------------------------------------------------- H1 addressing param group
def h1_address_param_group(model):
    """Return the ordered [(name, param)] list of the frozen H1 addressing group; assert it matches
    the frozen manifest exactly (no drift)."""
    sel = [(n, p) for n, p in model.named_parameters() if n in H1_NAMES]
    got = [n for n, _ in sel]
    assert set(got) == H1_NAMES, f"H1 group drift: {set(got) ^ H1_NAMES}"
    # preserve the manifest's canonical order
    order = {n: i for i, n in enumerate(H1_MANIFEST["ordered_names"])}
    sel.sort(key=lambda kv: order[kv[0]])
    return sel


def h1_lr_multiplier(step: int, lo: float = 0.1, start: int = 600, stop: int = 900) -> float:
    """0.1x during [600, 900); 1.0x otherwise."""
    return lo if (start <= step < stop) else 1.0


# ----------------------------------------------------------------- H2 functional teacher
def h2_teacher_read_distributions(teacher_model, x_aux, query_pos):
    """Per-layer DETACHED read-address softmax at the query position on the frozen teacher.
    Uses only slot-address distributions (no answer token)."""
    import torch  # noqa: F401
    import sys
    SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
    if str(SBS) not in sys.path:
        sys.path.insert(0, str(SBS))
    import interventions as IV
    IV.enable_capture(teacher_model, True)
    with __import__("torch").no_grad():
        _ = teacher_model(x_aux)
    import torch as _t
    B = x_aux.size(0); idx = _t.arange(B)
    out = [sm._sfs_raddr[idx, query_pos].detach().clone() for sm in teacher_model.slot_mixers()]
    IV.enable_capture(teacher_model, False)
    return out  # list of [B, M] detached distributions


def h2_loss(student_model, x_aux, query_pos, teacher_dists, eps=1e-8):
    """KL(teacher || student) over the read-address distributions, mean over layers and batch."""
    import torch
    import sys
    SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
    if str(SBS) not in sys.path:
        sys.path.insert(0, str(SBS))
    import interventions as IV
    IV.enable_capture(student_model, True)
    _ = student_model(x_aux)
    B = x_aux.size(0); idx = torch.arange(B)
    kls = []
    for sm, t in zip(student_model.slot_mixers(), teacher_dists):
        s = sm._sfs_raddr[idx, query_pos]
        kls.append((t * ((t + eps).log() - (s + eps).log())).sum(-1))
    IV.enable_capture(student_model, False)
    return torch.stack(kls).mean()


def h2_coefficient(step: int) -> float:
    """0 through 600; 0.02 during 601-900; linear 0.02->0 during 901-1000; 0 during 1001-1200."""
    if step <= 600:
        return 0.0
    if step <= 900:
        return 0.02
    if step <= 1000:
        return 0.02 * (1.0 - (step - 900) / 100.0)
    return 0.0
