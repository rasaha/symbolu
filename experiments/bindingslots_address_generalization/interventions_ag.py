#!/usr/bin/env python3
"""Intervention levers for the read-address generalization (A1) and routing-gradient isolation (G1)
phase. Built ON the frozen S architecture / BindingSlots / tasks / corpus without editing them.

A1 lever: a contrastive read-address objective of the SAME FORM as the prior correct-slot-probability
objective (objectives.correct_slot_prob_loss, L = -log r[q, s*]), differing ONLY in
  (a) the query distribution — real task-query positions across diverse query templates, and
  (b) hard-negative construction — competitor slots carrying content-similar / related / shuffled
      facts in the same example.
Its coefficient/schedule is the closest prior objective's schedule (objectives_persistence.o1r_lambda);
no coefficient sweep. The A1 batch is drawn from a DEDICATED rng so the main training data stream is
byte-identical to B0 (only the added loss term differs).

G1 lever: PCGrad-style projection of the auxiliary (persistence + teacher) gradient away from the LM
gradient, applied ONLY to the write_addr_proj (W_wk) parameter group, at the group level.

Requires torch.
"""
from __future__ import annotations

import pathlib
import random
import sys

import torch

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
FR = REPO / "experiments" / "bindingslots_functional_routing"
PERS = REPO / "experiments" / "bindingslots_persistence"
for p in (str(SBS), str(FR), str(PERS)):
    if p not in sys.path:
        sys.path.insert(0, p)

SLOT_MARKER = ".mix.slots."
WRITE_ADDR_MARKER = ".W_wk."   # write-address projection inside a slot module

# ------------------------------------------------------------------ query-template partitions
# Templates live in ag_meta.py (torch-free) so leakage/separation is verifiable without torch. All
# tokens are existing struct vocabulary (no new tokens, no NL expansion). The TEST template equals the
# frozen needle eval query and is HELD OUT — never used for A1 training or coefficient selection.
from ag_meta import QUERY_TEMPLATES  # noqa: E402


def _tpl_ids(tpl, ent, vocab):
    S = vocab.stoi
    return [S[t] if t != "ENT" else ent for t in tpl]


def a1_hard_negative_batch(vocab, B, N, a1_rng, T, partition="train", n_hard=3):
    """Build a hard-negative diverse-template routing batch from a DEDICATED rng (does not perturb the
    main training stream). Each example: one target write fact + n_hard content-similar distractor
    facts (hard negatives writing to competitor slots) + a query using a template from `partition`.
    Returns (x[B,N], fact_pos[B], query_pos[B]). The target slot s* is derived at loss time from the
    write address at fact_pos (as in the prior correct-slot objective)."""
    S = vocab.stoi
    templates = QUERY_TEMPLATES[partition]
    xs, fps, qps = [], [], []
    for _ in range(B):
        ents = a1_rng.sample(vocab.ent, n_hard + 1)
        vals = a1_rng.sample(vocab.val, n_hard + 1)
        e_t, v_t = ents[0], vals[0]
        # target write fact (standard needle write framing) — establishes s*
        target_fact = [S['the'], S['code'], S['for'], e_t, S['is'], v_t, S['.']]
        # hard-negative distractor facts (same framing, other entity->value) -> competitor slots
        distractors = [[S['the'], S['code'], S['for'], ents[i + 1], S['is'], vals[i + 1], S['.']]
                       for i in range(n_hard)]
        tpl = templates[a1_rng.randrange(len(templates))]
        query = _tpl_ids(tpl, e_t, vocab)
        tail = query + [v_t]                       # predict v_t at the final position
        body_facts = [target_fact] + distractors
        a1_rng.shuffle(body_facts)
        flat = [t for f in body_facts for t in f]
        # layout: fillers + facts + fillers + tail, left-padded to N
        room = N - len(tail) - len(flat)
        if room < 0:
            flat = flat[:max(0, N - len(tail))]
            room = 0
        pre = room // 2
        post = room - pre
        ids = ([vocab.filler[a1_rng.randrange(len(vocab.filler))] for _ in range(pre)]
               + flat
               + [vocab.filler[a1_rng.randrange(len(vocab.filler))] for _ in range(post)]
               + tail)
        ids = ids[:N]
        while len(ids) < N:
            ids = [vocab.pad] + ids
        # locate the target value token (v_t within the target fact): find target_fact's 'is' then v_t
        # after layout+padding; recompute by scanning for the exact target_fact subsequence.
        fp = _find_target_value_pos(ids, target_fact, v_t)
        xs.append(torch.tensor(ids, dtype=torch.long))
        fps.append(fp)
        qps.append(N - 2)                          # position predicting the value at N-1
    return torch.stack(xs), torch.tensor(fps), torch.tensor(qps)


def _find_target_value_pos(ids, target_fact, v_t):
    """Position of the target value token v_t inside the (unique) target write fact occurrence."""
    L = len(target_fact)
    for i in range(len(ids) - L + 1):
        if ids[i:i + L] == target_fact:
            return i + 5      # index of v_t within [the,code,for,ENT,is,v_t,.]
    # fallback: last standalone v_t before the tail (should not happen given unique vals)
    return max(j for j, t in enumerate(ids) if t == v_t)


def a1_loss(model, x_a1, fact_pos, query_pos):
    """A1 routing loss = the prior correct-slot-probability objective on the hard-negative diverse-
    template batch. Reuses the FROZEN objectives.correct_slot_prob_loss (L = -log r[q, s*])."""
    import objectives as O1
    loss, overlap = O1.correct_slot_prob_loss(model, x_a1, fact_pos, query_pos)
    return loss, overlap


# ------------------------------------------------------------------ G1 gradient projection
def write_addr_params(model):
    """The write_addr_proj (W_wk) parameters across slot layers — the ONLY group G1 touches."""
    return [(n, p) for n, p in model.named_parameters()
            if SLOT_MARKER in n and WRITE_ADDR_MARKER in n]


def project_write_addr_grad(model, g_lm_wak, lm_norm_sq, eps=1e-12):
    """Group-level PCGrad projection on write_addr_proj ONLY.

    On entry each write_addr_proj param's .grad holds g_lm + g_aux (LM backward then aux backward).
    g_lm_wak maps param-name -> the saved g_lm for that param. We reconstruct g_aux = grad - g_lm,
    flatten the group, and if cosine(g_aux, g_lm) < 0 project:
        g_aux_corrected = g_aux - min(0, <g_aux,g_lm>/||g_lm||^2) * g_lm
    then rewrite each param's .grad = g_lm + g_aux_corrected. Zero LM-gradient norm is handled
    deterministically: if ||g_lm||^2 < eps, NO projection is applied (g_aux left unchanged).
    Returns a metrics dict. Parameters outside write_addr_proj are never touched here.
    """
    params = write_addr_params(model)
    gl, ga = [], []
    for n, p in params:
        assert p.grad is not None, f"missing grad for {n}"
        glp = g_lm_wak[n]
        gap = p.grad.detach() - glp
        gl.append(glp.reshape(-1))
        ga.append(gap.reshape(-1))
    gl = torch.cat(gl)
    ga = torch.cat(ga)
    dot = torch.dot(ga, gl).item()
    ln2 = float(lm_norm_sq)
    aux_norm = ga.norm().item()
    lm_norm = gl.norm().item()
    cos_before = (dot / (aux_norm * lm_norm)) if aux_norm > eps and lm_norm > eps else 0.0
    projected = False
    removed_frac = 0.0
    if ln2 >= eps and dot < 0.0:
        coeff = dot / ln2                     # = min(0, dot/||g_lm||^2) since dot<0
        ga_corr = ga - coeff * gl
        projected = True
        removed_frac = (ga - ga_corr).norm().item() / (aux_norm + eps)
    else:
        ga_corr = ga
    # cosine after
    ac_norm = ga_corr.norm().item()
    dot_after = torch.dot(ga_corr, gl).item()
    cos_after = (dot_after / (ac_norm * lm_norm)) if ac_norm > eps and lm_norm > eps else 0.0
    # redistribute ga_corr back and set .grad = g_lm + ga_corr
    off = 0
    for n, p in params:
        numel = p.numel()
        chunk = ga_corr[off:off + numel].reshape(p.shape)
        off += numel
        p.grad = (g_lm_wak[n] + chunk).clone()
    return {"lm_norm_wak": lm_norm, "aux_norm_wak": aux_norm, "projected_norm_wak": ac_norm,
            "cosine_before": cos_before, "cosine_after": cos_after, "projected": projected,
            "fraction_aux_removed": removed_frac, "dot_before": dot,
            "zero_lm_gradient": ln2 < eps}
