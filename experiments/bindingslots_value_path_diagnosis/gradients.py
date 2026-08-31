#!/usr/bin/env python3
"""B2 (no-update gradient norms) and B3 (gradient alignment) for the BindingSlots quality-
interference question.

On a FROZEN reproduced checkpoint and FIXED diagnostic batches, we compute the gradient of each of
three losses without ever taking an optimizer step:
  * grad_LM        : language-model cross-entropy on a fixed corpus batch;
  * grad_persist   : the arm's standing persistence auxiliary (O1R -> correct-slot-prob loss);
  * grad_teacher   : the H2 teacher/distillation KL to the frozen step-600 read distributions.

Discipline (§12/§15): optimizer-step count is zero; grads are cleared after every measurement;
the snapshot's state hash is asserted unchanged; parameter groups are bound from the actual
implementation and are complete + non-overlapping; cosine is zero-gradient-safe.
"""
from __future__ import annotations

import math
import random

import torch
import torch.nn.functional as F

import diagnosis_lib as DL

# fixed diagnostic batches
LM_SEED = 314159
LM_B, LM_N = 16, 160
AUX_SEED = 271828
AUX_B, AUX_N = 16, 160
SLOT_MARKER = ".mix.slots."


def param_groups(model):
    """Bind parameter groups to the ACTUAL implementation. Complete and non-overlapping:
    every named parameter falls in exactly one group. head.weight is tied to tok.weight and is
    de-duplicated by named_parameters()."""
    groups = {
        "embeddings": [],          # tok / pos embeddings (tied head shares tok.weight)
        "backbone": [],            # windowed attention + FFN + block/final norms (non-slot)
        "slot_keys": [],           # slots.slot_keys  (address key memory)
        "write_addr_proj": [],     # slots.W_wk
        "read_addr_proj": [],      # slots.W_rq
        "write_value_proj": [],    # slots.W_wv
        "write_gate": [],          # slots.gate
        "memory_readout_Wo": [],   # slots.W_o
        "slot_norm": [],           # slots.norm
    }

    def which(name):
        if SLOT_MARKER in name:
            if name.endswith("slot_keys"):
                return "slot_keys"
            if ".W_wk." in name:
                return "write_addr_proj"
            if ".W_rq." in name:
                return "read_addr_proj"
            if ".W_wv." in name:
                return "write_value_proj"
            if ".gate." in name:
                return "write_gate"
            if ".W_o." in name:
                return "memory_readout_Wo"
            if ".norm." in name:
                return "slot_norm"
            raise AssertionError(f"unclassified slot param {name}")
        if name.startswith("tok.") or name.startswith("pos."):
            return "embeddings"
        return "backbone"

    seen = set()
    for name, p in model.named_parameters():
        g = which(name)
        groups[g].append((name, p))
        assert id(p) not in seen, f"duplicate param {name}"
        seen.add(id(p))
    return groups


def audit_param_groups(model):
    groups = param_groups(model)
    total = sum(p.numel() for p in model.parameters())
    covered = sum(p.numel() for gs in groups.values() for _, p in gs)
    ids = [id(p) for gs in groups.values() for _, p in gs]
    return {
        "group_numel": {k: sum(p.numel() for _, p in v) for k, v in groups.items()},
        "group_param_count": {k: len(v) for k, v in groups.items()},
        "total_numel": total,
        "covered_numel": covered,
        "complete": covered == total,
        "non_overlapping": len(ids) == len(set(ids)),
    }


def _flat_grads(model, groups):
    """Read current .grad into a flat vector per group (zeros where grad is None)."""
    out = {}
    for g, params in groups.items():
        chunks = []
        for _, p in params:
            if p.grad is None:
                chunks.append(torch.zeros(p.numel()))
            else:
                chunks.append(p.grad.detach().reshape(-1).clone())
        out[g] = torch.cat(chunks) if chunks else torch.zeros(0)
    return out


def _grad_of(model, loss_fn):
    """Zero grads, backward one loss, return per-group flat grads, then zero grads again."""
    groups = param_groups(model)
    model.zero_grad(set_to_none=True)
    loss = loss_fn()
    loss.backward()
    g = _flat_grads(model, groups)
    model.zero_grad(set_to_none=True)
    return g, loss.detach().item()


def _cos(a, b, eps=1e-12):
    na, nb = a.norm().item(), b.norm().item()
    if na < eps or nb < eps:
        return {"cosine": None, "zero_gradient": True, "norm_a": na, "norm_b": nb}
    return {"cosine": float(torch.dot(a, b).item() / (na * nb)), "zero_gradient": False,
            "norm_a": na, "norm_b": nb}


def _lm_loss_fn(model, vocab, TA):
    rng = random.Random(LM_SEED)
    x, y, _ = TA.lm_batch(TA.build_corpus()[2], LM_B, LM_N, rng)

    def fn():
        lo = model(x)
        return F.cross_entropy(lo.reshape(-1, lo.size(-1)), y.reshape(-1))
    return fn


def _persist_loss_fn(model, vocab, T):
    """O1R standing persistence auxiliary = correct-slot-probability loss on a fixed aux batch."""
    import interventions as IV
    import objectives as O1
    rng = random.Random(AUX_SEED)
    xa, fp, qp = IV.aux_needle_batch(vocab, AUX_B, AUX_N, rng, T)

    def fn():
        loss, _ = O1.correct_slot_prob_loss(model, xa, fp, qp)
        return loss
    return fn


def _teacher_loss_fn(model, teacher_model, vocab, T):
    """H2 teacher distillation KL to the frozen step-600 teacher read distributions."""
    import interventions as IV
    import objectives_persistence as OP
    rng = random.Random(AUX_SEED)
    xa, fp, qp = IV.aux_needle_batch(vocab, AUX_B, AUX_N, rng, T)
    tdists = OP.h2_teacher_read_distributions(teacher_model, xa, qp)

    def fn():
        return OP.h2_loss(model, xa, qp, tdists)
    return fn


def run_gradient_diagnostics(model, arm, vocab, T, TA, teacher_model=None):
    """Full B2 + B3 for one snapshot. teacher_model (step-600 snapshot) required for H2."""
    h0 = DL.model_state_hash(model)
    groups = param_groups(model)
    lm_g, lm_loss = _grad_of(model, _lm_loss_fn(model, vocab, TA))

    result = {
        "arm": arm,
        "param_group_audit": audit_param_groups(model),
        "losses": {"lm": lm_loss},
        "grad_norms_by_group": {"lm": {g: v.norm().item() for g, v in lm_g.items()}},
        "alignment_lm_vs_persist": None,
        "alignment_lm_vs_teacher": None,
        "persist_to_lm_norm_ratio": None,
        "teacher_to_lm_norm_ratio": None,
        "zero_gradient_groups": {"lm": [g for g, v in lm_g.items() if v.norm().item() < 1e-12]},
    }

    lm_total = math.sqrt(sum(v.norm().item() ** 2 for v in lm_g.values()))

    has_slots = len(model.slot_mixers()) > 0
    if arm in ("O1R",) and has_slots:
        pg, ploss = _grad_of(model, _persist_loss_fn(model, vocab, T))
        result["losses"]["persist"] = ploss
        result["grad_norms_by_group"]["persist"] = {g: v.norm().item() for g, v in pg.items()}
        result["alignment_lm_vs_persist"] = {g: _cos(lm_g[g], pg[g]) for g in groups}
        p_total = math.sqrt(sum(v.norm().item() ** 2 for v in pg.values()))
        result["persist_to_lm_norm_ratio"] = (p_total / lm_total) if lm_total > 0 else None
        result["global_alignment_lm_vs_persist"] = _cos(
            torch.cat([lm_g[g] for g in groups]), torch.cat([pg[g] for g in groups]))

    if arm == "H2" and has_slots and teacher_model is not None:
        tg, tloss = _grad_of(model, _teacher_loss_fn(model, teacher_model, vocab, T))
        result["losses"]["teacher"] = tloss
        result["grad_norms_by_group"]["teacher"] = {g: v.norm().item() for g, v in tg.items()}
        result["alignment_lm_vs_teacher"] = {g: _cos(lm_g[g], tg[g]) for g in groups}
        t_total = math.sqrt(sum(v.norm().item() ** 2 for v in tg.values()))
        result["teacher_to_lm_norm_ratio"] = (t_total / lm_total) if lm_total > 0 else None
        result["global_alignment_lm_vs_teacher"] = _cos(
            torch.cat([lm_g[g] for g in groups]), torch.cat([tg[g] for g in groups]))

    # integrity: no optimizer step happened, grads cleared, state unchanged
    model.zero_grad(set_to_none=True)
    result["state_hash_unchanged"] = (DL.model_state_hash(model) == h0)
    result["state_hash"] = h0
    return result
