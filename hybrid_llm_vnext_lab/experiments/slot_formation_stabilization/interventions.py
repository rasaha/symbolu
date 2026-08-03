"""Intervention families for slot-formation stabilization — applied WITHOUT modifying the
frozen S architecture, BindingSlots equations, tasks, tokenizer, corpus, or parameter count.

Family 1 (optimizer): explicit slot-routing vs non-slot AdamW parameter groups + per-group warmup.
Family 2 (init):      deterministic orthogonal, unit-normalized, trainable slot-key re-init.
Family 3 (scaffold):  curriculum batch schedule + a temporary, label-free write-read alignment loss.

All slot-routing distributions used by diagnostics/alignment are recomputed by a non-invasive
forward-pre-hook that calls the module's OWN projections and `_route` — the incubated BindingSlots
class is never edited. The alignment loss uses only fact-time/query-time slot-address vectors
(length M), never an N x N tensor, and adds no inference-time parameter or operation.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F

# ------------------------------------------------------------------ Family 1: optimizer groups

SLOT_MARKER = ".mix.slots."


def split_param_groups(model):
    """Return (slot_named, nonslot_named) as lists of (name, param). A parameter is 'slot-routing'
    iff its qualified name lies inside a BindingSlots module (…mix.slots.…): slot_keys, W_wk, W_rq,
    W_wv, gate, W_o, norm. Everything else (embeddings, window attention, block norms, FFN, final
    norm, tied head) is non-slot. Tied head.weight is de-duplicated by named_parameters()."""
    slot_named, nonslot_named = [], []
    for name, p in model.named_parameters():
        (slot_named if SLOT_MARKER in name else nonslot_named).append((name, p))
    return slot_named, nonslot_named


def param_group_audit(model):
    """Structured audit proving every param appears exactly once, no omissions/duplicates."""
    slot_named, nonslot_named = split_param_groups(model)
    total = sum(p.numel() for p in model.parameters())
    slot_ids = [id(p) for _, p in slot_named]
    nonslot_ids = [id(p) for _, p in nonslot_named]
    all_ids = slot_ids + nonslot_ids
    return {
        "slot_group_params": len(slot_named),
        "nonslot_group_params": len(nonslot_named),
        "slot_group_numel": sum(p.numel() for _, p in slot_named),
        "nonslot_group_numel": sum(p.numel() for _, p in nonslot_named),
        "total_numel": total,
        "numel_reconciles": sum(p.numel() for _, p in slot_named) + sum(p.numel() for _, p in nonslot_named) == total,
        "no_duplicates": len(all_ids) == len(set(all_ids)),
        "no_omissions": len(set(all_ids)) == len({id(p) for p in model.parameters()}),
        "slot_param_names": [n for n, _ in slot_named],
        "nonslot_param_count": len(nonslot_named),
    }


def build_optimizer_and_scheduler(model, *, nonslot_lr, nonslot_warmup, slot_lr, slot_warmup,
                                  weight_decay, steps, grouped):
    """grouped=False -> single group (identical to the frozen harness: AdamW(model.parameters(),
    lr=nonslot_lr, wd) + LambdaLR min(1, s/nonslot_warmup)). grouped=True -> two groups with
    per-group LR and per-group warmup lambdas. Returns (opt, sched, warmups_by_group)."""
    if not grouped:
        opt = torch.optim.AdamW(model.parameters(), lr=nonslot_lr, weight_decay=weight_decay)
        warm = nonslot_warmup
        sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, s / warm))
        return opt, sched, [nonslot_warmup]
    slot_named, nonslot_named = split_param_groups(model)
    groups = [
        {"params": [p for _, p in nonslot_named], "lr": nonslot_lr, "weight_decay": weight_decay},
        {"params": [p for _, p in slot_named], "lr": slot_lr, "weight_decay": weight_decay},
    ]
    opt = torch.optim.AdamW(groups)
    lambdas = [
        (lambda s, w=nonslot_warmup: min(1.0, s / w)),
        (lambda s, w=slot_warmup: min(1.0, s / w)),
    ]
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambdas)
    return opt, sched, [nonslot_warmup, slot_warmup]


# --------------------------------------------------------------------- Family 2: orthogonal init

def orthogonal_slot_key_init(model, seed):
    """In-place deterministic orthogonal, unit-normalized re-init of every slot_keys tensor.
    Shape/dtype/param-count preserved; keys stay a trainable nn.Parameter. Uses a private
    Generator so the rest of the model's initialization RNG stream is untouched."""
    audit = {"per_layer": []}
    for li, sm in enumerate(model.slot_mixers()):
        M, kd = sm.slot_keys.shape
        g = torch.Generator().manual_seed(seed * 7919 + li + 1)
        raw = torch.randn(kd, M, generator=g)          # [kd, M]
        q, _ = torch.linalg.qr(raw)                     # q: [kd, M] orthonormal columns (kd>=M)
        keys = q.t()[:M]                                # [M, kd] orthonormal rows
        keys = F.normalize(keys, dim=-1)                # unit rows (matches baseline normalization)
        with torch.no_grad():
            sm.slot_keys.copy_(keys.to(sm.slot_keys.dtype))
        audit["per_layer"].append({
            "layer": li, "shape": list(sm.slot_keys.shape), "dtype": str(sm.slot_keys.dtype),
            "requires_grad": bool(sm.slot_keys.requires_grad),
        })
    return audit


def key_cosine_stats(keys):
    """Off-diagonal pairwise cosine stats + norms + singular values for an [M,kd] key tensor."""
    k = keys.detach()
    kn = F.normalize(k, dim=-1)
    cos = kn @ kn.t()
    M = k.shape[0]
    off = cos[~torch.eye(M, dtype=torch.bool)]
    sv = torch.linalg.svdvals(k)
    return {
        "off_diag_cos_mean_abs": off.abs().mean().item(),
        "off_diag_cos_max_abs": off.abs().max().item(),
        "off_diag_cos_rms": (off.pow(2).mean().sqrt()).item(),
        "row_norm_mean": k.norm(dim=-1).mean().item(),
        "row_norm_std": k.norm(dim=-1).std().item(),
        "elem_var": k.var(unbiased=False).item(),
        "singular_values": [round(x, 5) for x in sv.tolist()],
    }


# ------------------------------------------------------------------ Family 3a: curriculum

def _task_batch(kind, vocab, B, N, rng, T, **kw):
    """(x, y, mask) for a single-kind task batch, mirroring the frozen train_batch construction."""
    xs, ys, ms = [], [], []
    for _ in range(B):
        if kind == "needle":
            x, pos, tgt = T.needle(N, vocab, rng, **kw)
        elif kind == "binding":
            x, pos, tgt = T.binding(N, vocab, rng, **kw)
        else:
            raise ValueError(kind)
        y = x.clone(); y[:-1] = x[1:]; y[-1] = vocab.pad
        m = torch.zeros(N, dtype=torch.bool); m[pos - 1] = True
        xs.append(x); ys.append(y); ms.append(m)
    return torch.stack(xs), torch.stack(ys), torch.stack(ms)


def curriculum_batch(step, stream, vocab, B, N, rng, T):
    """Curriculum schedule (boundaries 300 / 700 / 1200). Returns (x, y, mask, phase_label).
    Phase 3 (>=700) delegates to the ORIGINAL frozen train_batch (ABC_MIX)."""
    if step < 300:
        x, y, m = _task_batch("needle", vocab, B, N, rng, T, distance=16)
        return x, y, m, 1
    if step < 700:
        if rng.random() < 0.7:
            d = 16 if rng.random() < 0.5 else 96
            x, y, m = _task_batch("needle", vocab, B, N, rng, T, distance=d)
        else:
            x, y, m = _task_batch("binding", vocab, B, N, rng, T, k=2)
        return x, y, m, 2
    x, y, m = T.train_batch(stream, B, N, vocab, rng)
    return x, y, m, 3


# ------------------------------------------------------------------ Family 3b: write-read alignment

def aux_needle_batch(vocab, B, N, rng, T, distances=(16, 96)):
    """Auxiliary needle probe batch with KNOWN spans for the label-free alignment objective.
    Returns (x[B,N], fact_pos[B], query_pos[B]). fact_pos = the value-token position (where the
    binding value enters the slot memory); query_pos = the position whose output predicts the
    value (N-2). The batch's cross-entropy is NEVER used — only slot-address vectors are read."""
    S = vocab.stoi
    xs, fps, qps = [], [], []
    body = N - 6  # len(tail) == 6
    for _ in range(B):
        e = rng.choice(vocab.ent); v = rng.choice(vocab.val)
        fact = [S['the'], S['code'], S['for'], e, S['is'], v, S['.']]      # value v at fact idx 5
        tail = [S['the'], S['code'], S['for'], e, S['is'], v]
        d = distances[0] if rng.random() < 0.5 else distances[1]
        gap = min(d, body - len(fact))
        before = body - len(fact) - gap
        ids = [vocab.filler[rng.randrange(len(vocab.filler))] for _ in range(before)] + fact \
            + [vocab.filler[rng.randrange(len(vocab.filler))] for _ in range(gap)] + tail
        ids = ids[:N]
        while len(ids) < N:
            ids = [vocab.pad] + ids
        xs.append(torch.tensor(ids, dtype=torch.long))
        fps.append(before + 5)   # value-token position
        qps.append(N - 2)        # predicts the value at N-1
    return torch.stack(xs), torch.tensor(fps), torch.tensor(qps)


def lambda_align(step, start=0.10, decay_start=300, decay_end=600):
    """λ schedule: constant `start` for steps < decay_start; linear decay to 0 across
    [decay_start, decay_end); exactly 0 for steps >= decay_end. Steps are 0-indexed."""
    if step < decay_start:
        return start
    if step < decay_end:
        frac = (step - decay_start) / (decay_end - decay_start)
        return start * (1.0 - frac)
    return 0.0


def enable_capture(model, on):
    for sm in model.slot_mixers():
        sm._sfs_capture = on
        if not on:
            sm._sfs_waddr = sm._sfs_raddr = sm._sfs_gate = None


def install_capture_hooks(model):
    """Forward-pre-hook that recomputes waddr/raddr/gate from the module's OWN params (exact,
    non-invasive). Enabled only when sm._sfs_capture is True. Returns the hook handles."""
    handles = []
    for sm in model.slot_mixers():
        sm._sfs_capture = False
        sm._sfs_waddr = sm._sfs_raddr = sm._sfs_gate = None

        def _hook(module, inputs):
            if not getattr(module, "_sfs_capture", False):
                return
            x = inputs[0]
            xn = module.norm(x)
            module._sfs_wlogit = (module.W_wk(xn) @ module.slot_keys.t()) * module.scale  # [B,N,M]
            module._sfs_rlogit = (module.W_rq(xn) @ module.slot_keys.t()) * module.scale  # [B,N,M]
            module._sfs_waddr = module._route(module.W_wk(xn))   # [B,N,M]
            module._sfs_raddr = module._route(module.W_rq(xn))   # [B,N,M]
            module._sfs_gate = torch.sigmoid(module.gate(xn))    # [B,N,1]
        handles.append(sm.register_forward_pre_hook(_hook))
    return handles


def alignment_loss(model, x_aux, fact_pos, query_pos, eps=1e-6):
    """Grad-enabled label-free overlap loss: L = -log(mean_layers,batch Σ_m w_m·r_m + eps).
    w = write-address at fact_pos; r = read-address at query_pos. No N x N tensor is formed."""
    slots = model.slot_mixers()
    enable_capture(model, True)
    _ = model(x_aux)   # grad-enabled forward; logits discarded (no output-token supervision)
    B = x_aux.size(0)
    idx = torch.arange(B)
    overlaps = []
    for sm in slots:
        w = sm._sfs_waddr[idx, fact_pos]    # [B, M]
        r = sm._sfs_raddr[idx, query_pos]   # [B, M]
        overlaps.append((w * r).sum(-1))    # [B]
    enable_capture(model, False)
    mean_overlap = torch.stack(overlaps).mean()
    return -(mean_overlap + eps).log(), mean_overlap.detach().item()
