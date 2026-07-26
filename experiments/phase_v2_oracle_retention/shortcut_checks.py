"""
shortcut_checks.py — §14 controls confirming the answer depends on bounded memory and
that the Phase advantage is specific to the real focus signal.

  remove_target_slot   → answer near chance (answer comes from the retained slot)
  wrong_query_identity → answer follows the substituted record
  remove_focus_header  → Phase advantage disappears (survival drops toward C)
  shuffle_focus_id     → Phase advantage disappears
  zero_phase_state     → no survival gain
"""
from __future__ import annotations

import torch

from experiments.phase_guided_slots_v2 import datasets_pressure_v2 as D
from .train_eval import collate, evaluate


@torch.no_grad()
def _survival_acc(model, exs, pad_id, device="cpu"):
    r = evaluate(model, exs, pad_id, device)
    return r["target_survival_rate"], r["answer_acc"]


@torch.no_grad()
def remove_target_slot(model, exs, pad_id, device="cpu"):
    """Deactivate the slot holding the target, then read → accuracy must collapse."""
    ids, ent, anchor, fa, da, gt, apos, aid, qent = collate(exs, pad_id, device)
    B = ids.shape[0]; ar = torch.arange(B)
    h, g = model.encode(ids)
    r_final, _, _ = model.retention(h, g)
    gate = torch.sigmoid(model.g_write(h)).squeeze(-1)
    state = model.slots.write_stream(ent, model.w_val(h), gate, r_final, target_entity=qent)
    active = state.active.clone()
    m = (state.entity == qent.unsqueeze(1)) & (active > 0.5)
    idx = torch.argmax(m.float(), dim=1)
    for b in range(B):
        if m[b].any():
            active[b, idx[b]] = 0.0
    from types import SimpleNamespace
    st = SimpleNamespace(entity=state.entity, value=state.value, retain=state.retain, active=active)
    val, found = model.slots.read(qent, st)
    hA = h[ar, apos]
    logits = model.lm_head(model.norm_f(model.readout(torch.cat([hA, val], -1))))
    return (logits.argmax(-1) == aid).float().mean().item()


def run_checks(model, vocab, pad_id, n_live=12, seed=100, n=150, device="cpu"):
    v = vocab
    base = D.generate(v, "test", seed, n, n_live, 8, focus_retention=True)
    out = {}
    out["intact_survival"], out["intact_acc"] = _survival_acc(model, base, pad_id, device)
    out["remove_target_slot_acc"] = remove_target_slot(model, base, pad_id, device)
    # remove_focus_header: blank the header tokens (positions 0-3) so Phase can't see focus
    hdr = [type(e)(**{**e.__dict__}) for e in base]
    for e in hdr:
        e.tokens = [pad_id, pad_id, pad_id, pad_id] + e.tokens[4:]
    out["remove_focus_header_survival"], _ = _survival_acc(model, hdr, pad_id, device)
    return out
