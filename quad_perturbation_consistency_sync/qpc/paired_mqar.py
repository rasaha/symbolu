"""Paired MQAR generation for perturbation-consistency (read-only use of qgr).

For each base sample x we build a semantically-equivalent perturbation x_tilde that PRESERVES
the query->value relationships but changes irrelevant structure (pair order, distractor count,
absolute position). To compare per-head retrieval distributions across the two differently
shaped sequences, every candidate position is mapped to a canonical PAIR IDENTITY (by key
token) plus an "other" bucket for distractor keys. Pair index p = the p-th smallest key token;
queries are ordered canonically by query token; so x and x_tilde align bucket-for-bucket and
query-for-query with NO retrieval label (we never mark which pair is correct).

Perturbations (semantic-preserving): permute pair order, prepend positional filler (pad), and
insert extra distractor key tokens. The correct answer value for every query is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import torch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                                "quad_generative_regularization"))
from qgr.mqar import MQARConfig, IGNORE_INDEX  # noqa: E402

PAD = 0


@dataclass
class Paired:
    x_tokens: torch.Tensor       # [B,N]
    x_targets: torch.Tensor      # [B,N]  (IGNORE except query positions)
    x_qpos: torch.Tensor         # [B,Q]  canonical (sorted by query token)
    x_bucket: torch.Tensor       # [B,N]  pair idx (0..m-1), m=other(distractor key), -1=excluded
    xt_tokens: torch.Tensor      # [B,Nt]
    xt_qpos: torch.Tensor        # [B,Q]
    xt_bucket: torch.Tensor      # [B,Nt]
    num_buckets: int             # num_kv + 1
    num_kv: int
    # qgr-compatible labels for x (so the labelled-aux arm trains on identical base data)
    x_key_pos: Optional[torch.Tensor] = None    # [B,N] correct key pos at query positions, else -1
    x_cand_mask: Optional[torch.Tensor] = None  # [B,N,N] candidate key positions per query

    def to(self, device):
        for f in ("x_tokens", "x_targets", "x_qpos", "x_bucket",
                  "xt_tokens", "xt_qpos", "xt_bucket", "x_key_pos", "x_cand_mask"):
            v = getattr(self, f, None)
            if v is not None:
                setattr(self, f, v.to(device))
        return self


def _distinct(lo, hi, n, g):
    return [lo + int(v) for v in torch.randperm(hi - lo, generator=g)[:n]]


def _build_context(pair_order, key_of, val_of, lead_pad, distractors, g):
    """Return tokens, and pair_pos (position of each pair's key), distractor positions."""
    toks: List[int] = [PAD] * lead_pad
    pair_pos = {}
    # interleave optional distractor keys among the pairs (before queries)
    seq_items = []  # ("pair", pid) or ("dist", token)
    for pid in pair_order:
        seq_items.append(("pair", pid))
    for dt in distractors:
        # insert each distractor at a random slot
        pos = int(torch.randint(len(seq_items) + 1, (1,), generator=g))
        seq_items.insert(pos, ("dist", dt))
    dist_pos = []
    for kind, v in seq_items:
        if kind == "pair":
            pair_pos[v] = len(toks)
            toks.append(key_of[v]); toks.append(val_of[v])   # key then value
        else:
            dist_pos.append(len(toks)); toks.append(v)
    return toks, pair_pos, dist_pos


def _gen_one(cfg: MQARConfig, g: torch.Generator, perturb: bool):
    key_lo, key_hi, val_lo, val_hi = cfg.id_ranges()
    m = cfg.num_kv
    key_tokens = sorted(_distinct(key_lo, key_hi, m, g))          # canonical pair order by token
    val_tokens = _distinct(val_lo, val_hi, m, g)
    key_of = {p: key_tokens[p] for p in range(m)}
    val_of = {p: val_tokens[p] for p in range(m)}
    # choose queried pairs, canonical order by query token == key token
    q_pairs = sorted(_distinct(0, m, cfg.num_queries, g))

    def make(order, lead_pad, dists):
        toks, pair_pos, dist_pos = _build_context(order, key_of, val_of, lead_pad, dists, g)
        qpos = []
        for p in q_pairs:
            qpos.append(len(toks)); toks.append(key_of[p])       # query == key token
        bucket = [-1] * len(toks)
        for p, pos in pair_pos.items():
            bucket[pos] = p
        for dp in dist_pos:
            bucket[dp] = m                                        # 'other'
        # targets: answer value at each query position
        targets = [IGNORE_INDEX] * len(toks)
        correct_key = {}                      # query pos -> correct key position
        for p, qp in zip(q_pairs, qpos):
            targets[qp] = val_of[p]
            correct_key[qp] = pair_pos[p]
        return toks, targets, qpos, bucket, correct_key

    base = make(list(range(m)), 0, [])
    if not perturb:
        return base, base
    # perturbed: permute pairs, prepend positional filler, insert distractor keys
    order = list(range(m))
    order = [order[i] for i in torch.randperm(m, generator=g)]
    lead = int(torch.randint(0, 5, (1,), generator=g))
    n_dist = int(torch.randint(0, 4, (1,), generator=g))
    dists = _distinct(key_hi, val_hi, n_dist, g) if n_dist > 0 else []  # distractor "keys" from val range (unused as pairs)
    pert = make(order, lead, dists)
    return base, pert


def gen_paired_batch(cfg: MQARConfig, seed: int, batch_size: int, perturb: bool = True,
                     device="cpu") -> Paired:
    g = torch.Generator().manual_seed(seed)
    samples = [_gen_one(cfg, g, perturb) for _ in range(batch_size)]
    m = cfg.num_kv
    Q = cfg.num_queries
    B = batch_size
    N = max(len(s[0][0]) for s in samples)
    Nt = max(len(s[1][0]) for s in samples)

    def pack(which, L, with_labels=False):
        tok = torch.zeros(B, L, dtype=torch.long)
        tgt = torch.full((B, L), IGNORE_INDEX, dtype=torch.long)
        buc = torch.full((B, L), -1, dtype=torch.long)
        qp = torch.zeros(B, Q, dtype=torch.long)
        kp = torch.full((B, L), -1, dtype=torch.long)
        cm = torch.zeros(B, L, L, dtype=torch.bool)
        for b, s in enumerate(samples):
            toks, targets, qpos, bucket, correct_key = s[which]
            tok[b, :len(toks)] = torch.tensor(toks)
            tgt[b, :len(targets)] = torch.tensor(targets)
            buc[b, :len(bucket)] = torch.tensor(bucket)
            qp[b] = torch.tensor(qpos)
            if with_labels:
                cand = [j for j, bk in enumerate(bucket) if bk >= 0]
                for qpp, ckey in correct_key.items():
                    kp[b, qpp] = ckey
                    for j in cand:
                        if j < qpp:
                            cm[b, qpp, j] = True
        return tok, tgt, buc, qp, kp, cm

    xt_, xg_, xb_, xq_, xkp_, xcm_ = pack(0, N, with_labels=True)
    tt_, _tg, tb_, tq_, _kp, _cm = pack(1, Nt)
    return Paired(xt_, xg_, xq_, xb_, tt_, tq_, tb_, num_buckets=m + 1, num_kv=m,
                  x_key_pos=xkp_, x_cand_mask=xcm_).to(device)


# ---- progressive perturbation stages (for the degradation study) ---------------------

def staged_partner(cfg: MQARConfig, seed: int, batch_size: int, stage: int, device="cpu"
                   ) -> Paired:
    """Stage 0..5 of increasing perturbation, sharing the SAME base sample per seed so the
    base (x) is identical across stages and only x_tilde changes."""
    g = torch.Generator().manual_seed(seed)
    samples = []
    for _ in range(batch_size):
        key_lo, key_hi, val_lo, val_hi = cfg.id_ranges()
        m = cfg.num_kv
        key_tokens = sorted(_distinct(key_lo, key_hi, m, g))
        val_tokens = _distinct(val_lo, val_hi, m, g)
        key_of = {p: key_tokens[p] for p in range(m)}
        val_of = {p: val_tokens[p] for p in range(m)}
        q_pairs = sorted(_distinct(0, m, cfg.num_queries, g))

        def make(order, lead, dists):
            toks, pair_pos, dist_pos = _build_context(order, key_of, val_of, lead, dists, g)
            qpos = []
            for p in q_pairs:
                qpos.append(len(toks)); toks.append(key_of[p])
            bucket = [-1] * len(toks)
            for p, pos in pair_pos.items():
                bucket[pos] = p
            for dp in dist_pos:
                bucket[dp] = m
            targets = [IGNORE_INDEX] * len(toks)
            for p, qp in zip(q_pairs, qpos):
                targets[qp] = val_of[p]
            return toks, targets, qpos, bucket

        base = make(list(range(m)), 0, [])
        order = list(range(m))
        if stage == 0:
            pert = base
        elif stage == 1:                                  # minor irrelevant: lead pad 1
            pert = make(order, 1, [])
        elif stage == 2:                                  # distractor/pair permutation
            order = [order[i] for i in torch.randperm(m, generator=g)]
            pert = make(order, 0, [])
        elif stage == 3:                                  # additional distractors
            order = [order[i] for i in torch.randperm(m, generator=g)]
            dists = _distinct(key_hi, val_hi, 3, g)
            pert = make(order, 0, dists)
        elif stage == 4:                                  # longer context
            order = [order[i] for i in torch.randperm(m, generator=g)]
            pert = make(order, 20, [])
        else:                                             # stage 5: heavier (perm+dist+long)
            order = [order[i] for i in torch.randperm(m, generator=g)]
            dists = _distinct(key_hi, val_hi, 3, g)
            pert = make(order, 12, dists)
        samples.append((base, pert))

    m = cfg.num_kv; Q = cfg.num_queries; B = batch_size
    N = max(len(s[0][0]) for s in samples); Nt = max(len(s[1][0]) for s in samples)

    def pack(which, L):
        tok = torch.zeros(B, L, dtype=torch.long)
        buc = torch.full((B, L), -1, dtype=torch.long)
        qp = torch.zeros(B, Q, dtype=torch.long)
        for b, s in enumerate(samples):
            toks, _t, qpos, bucket = s[which]
            tok[b, :len(toks)] = torch.tensor(toks)
            buc[b, :len(bucket)] = torch.tensor(bucket)
            qp[b] = torch.tensor(qpos)
        return tok, buc, qp

    xt_, xb_, xq_ = pack(0, N)
    tt_, tb_, tq_ = pack(1, Nt)
    z = torch.zeros(B, 1, dtype=torch.long)
    return Paired(xt_, z, xq_, xb_, tt_, tq_, tb_, num_buckets=m + 1, num_kv=m).to(device)
