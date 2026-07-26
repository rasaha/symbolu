"""
decision_trace.py — §12 causal signal check: for each eviction, does the Phase
retention term change the decision, and does the change preserve the target?

We re-run the oracle write stream with instrumentation, comparing the eviction victim
chosen by r_local alone vs r_final = r_local + λ·r_phase. Reports:
  frac decisions changed by Phase, frac of changes that HELP (preserve target) vs
  HURT (evict target), and mean |Phase|/|local| retention-score ratio.
Read-only; identity allocation and query lookup are unchanged.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

from .train_eval import collate


@torch.no_grad()
def trace(model, exs, pad_id, device="cpu"):
    ids, ent, anchor, fa, da, gt, apos, aid, qent = collate(exs, pad_id, device)
    B, N = ids.shape
    h, g = model.encode(ids)
    r_final, r_local, r_phase = model.retention(h, g)
    gate = torch.sigmoid(model.g_write(h)).squeeze(-1)
    M = model.slots.M
    lam = float(model.lam()) if not torch.is_tensor(model.lam()) else float(model.lam().item())

    changed = help = hurt = 0
    n_evict = 0
    ratios = []
    # Per-example simulation of the oracle write under local-only retention vs r_final,
    # comparing the eviction victim at each full-memory allocation.
    for b in range(B):
        slot_ent_L = torch.full((M,), -1, dtype=torch.long)
        slot_ret_L = torch.full((M,), -1e4)
        act_L = torch.zeros(M)
        slot_ent_F = torch.full((M,), -1, dtype=torch.long)
        slot_ret_F = torch.full((M,), -1e4)
        act_F = torch.zeros(M)
        tgt = qent[b].item()
        for t in range(N):
            e = ent[b, t].item()
            if not (gate[b, t].item() > 0.5 and e >= 0):
                continue
            rl = r_local[b, t].item()
            rf = r_final[b, t].item()
            ratios.append(abs(lam * r_phase[b, t].item()) / (abs(rl) + 1e-6))
            for slot_ent, slot_ret, act, rv in ((slot_ent_L, slot_ret_L, act_L, rl),
                                                (slot_ent_F, slot_ret_F, act_F, rf)):
                m = (slot_ent == e) & (act > 0.5)
                if m.any():
                    s = int(m.nonzero()[0]); slot_ret[s] = rv
                elif (act < 0.5).any():
                    s = int((act < 0.5).nonzero()[0]); slot_ent[s] = e; slot_ret[s] = rv; act[s] = 1
                else:
                    s = int(torch.argmin(slot_ret).item())  # evict lowest retention
                    if slot_ent is slot_ent_F:
                        n_evict += 1
                    slot_ent[s] = e; slot_ret[s] = rv; act[s] = 1
        # after the stream, did local vs final differ on target survival?
        surv_L = bool(((slot_ent_L == tgt) & (act_L > 0.5)).any())
        surv_F = bool(((slot_ent_F == tgt) & (act_F > 0.5)).any())
        if surv_L != surv_F:
            changed += 1
            if surv_F and not surv_L:
                help += 1
            elif surv_L and not surv_F:
                hurt += 1
    tot = B
    return {
        "frac_examples_target_survival_changed_by_phase": changed / max(1, tot),
        "frac_changes_that_help": help / max(1, changed) if changed else 0.0,
        "frac_changes_that_hurt": hurt / max(1, changed) if changed else 0.0,
        "help_minus_hurt": (help - hurt) / max(1, tot),
        "mean_phase_over_local_ratio": sum(ratios) / max(1, len(ratios)),
        "lambda": lam,
    }
