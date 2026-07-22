"""Semantic-equivalence perturbations for the same-head consistency objective.

A *semantically-equivalent* view of an MQAR sequence keeps every key->value association and
every query->answer identical, changing only **irrelevant surface factors**:

    * distractor / key-value pair order,
    * distractor / key position,
    * additional irrelevant distractor fillers,
    * equivalent sequence ordering (query order),
    * equivalent positional variations (a leading positional shift).

None of these change *which key answers which query*.  The consistency objective (see
``consistency.py``) asks each attention head to behave the same across such views.  It uses
**no retrieval labels** — the only cross-view information is the augmentation correspondence
(which surface position holds which key/query *token*), exactly like an image-augmentation
consistency loss knows how it cropped the image.  Correctness of the retrieval is never used.

Alignment is by **token identity**.  In the base training configuration MQAR uses a single
relation system with distinct key tokens, so a key token appears at exactly one context
position per view; sorting candidate keys by token id yields a canonical, view-independent
axis along which two views' attention distributions are directly comparable.  Likewise the
queried key tokens are distinct, so sorting queries by token id aligns the query axis.

This module is pure data construction: it reconstructs the associations from a base
``MQARBatch`` and re-realises a perturbed view, returning both token tensors plus the
canonical query/key index tensors needed to align attention.  It does not touch the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch

from . import _qgr_path  # noqa: F401  (side-effect: put qgr on sys.path)
from qgr.mqar import IGNORE_INDEX, MQARConfig, MQARBatch, generate_batch, split_seed


@dataclass
class AugConfig:
    """Which irrelevant factors a perturbed view may vary (all preserve the answer)."""
    permute_pairs: bool = True        # reorder the key-value pairs in the context
    permute_queries: bool = True      # reorder the appended queries
    extra_distractors: int = 4        # number of irrelevant filler keys to insert
    max_pos_shift: int = 3            # leading positional shift (prepended pad tokens), 0..this
    context_length: int = 64          # hard cap on realised sequence length


@dataclass
class AlignedPair:
    """A base view O and a semantically-equivalent perturbed view P, plus canonical indices.

    tokens_o / tokens_p : [B, No] / [B, Np] long token tensors.
    targets_o           : [B, No] task targets for view O (identical answers to the base).
    q_idx_o / q_idx_p   : [B, Q] query positions, ordered by query-token id (aligned across views).
    k_idx_o / k_idx_p   : [B, K] candidate-key positions, ordered by key-token id (aligned).
    key_perm            : [B, K] a per-sample permutation of the key axis for the shuffled
                          control (identity for the real objective; a random derangement-ish
                          permutation for the control).  Applied to view P's key axis only.
    """
    tokens_o: torch.Tensor
    tokens_p: torch.Tensor
    targets_o: torch.Tensor
    q_idx_o: torch.Tensor
    q_idx_p: torch.Tensor
    k_idx_o: torch.Tensor
    k_idx_p: torch.Tensor
    key_perm: torch.Tensor

    def to(self, device) -> "AlignedPair":
        return AlignedPair(*[t.to(device) for t in (
            self.tokens_o, self.tokens_p, self.targets_o, self.q_idx_o, self.q_idx_p,
            self.k_idx_o, self.k_idx_p, self.key_perm)])


# --------------------------------------------------------------------------------------
# Reconstruct the semantic core (associations + queries) from a base MQARBatch.
# --------------------------------------------------------------------------------------

def decode_sample(batch: MQARBatch, b: int) -> Dict:
    """Recover, for sample b, the key->value associations and the queried keys.

    Uses only the batch's own metadata (cand_mask, key_pos, targets, tokens); relies on the
    MQAR construction invariant that a value immediately follows its key in the context.
    """
    tokens = batch.tokens[b]
    key_pos_row = batch.key_pos[b]
    cand = batch.cand_mask[b]
    # candidate key positions = any column marked as a candidate for some query
    key_positions = torch.nonzero(cand.any(dim=0), as_tuple=False).flatten().tolist()
    key_positions = sorted(key_positions)
    assoc = []  # (key_token, value_token)
    for kp in key_positions:
        ktok = int(tokens[kp])
        vtok = int(tokens[kp + 1])  # value immediately follows its key
        assoc.append((ktok, vtok))
    val_for_key = {k: v for k, v in assoc}
    queries = []  # (query_token, correct_key_token, answer_value)
    qpos = torch.nonzero(key_pos_row >= 0, as_tuple=False).flatten().tolist()
    for qp in qpos:
        qtok = int(tokens[qp])
        kp = int(key_pos_row[qp])
        ktok = int(tokens[kp])
        answer = int(batch.targets[b, qp])
        queries.append((qtok, ktok, answer))
    return {"assoc": assoc, "val_for_key": val_for_key, "queries": queries,
            "key_tokens": [k for k, _ in assoc]}


# --------------------------------------------------------------------------------------
# Realise a perturbed view of one sample.
# --------------------------------------------------------------------------------------

def _sample_extra_distractors(exclude: set, key_lo: int, key_hi: int, n: int,
                              g: torch.Generator) -> List[int]:
    """Sample n filler key-range tokens NOT equal to any real key (they are never candidates)."""
    pool = [t for t in range(key_lo, key_hi) if t not in exclude]
    if not pool or n <= 0:
        return []
    idx = torch.randint(len(pool), (n,), generator=g)
    return [pool[int(i)] for i in idx]


def realize_view(core: Dict, mq: MQARConfig, aug: AugConfig, g: torch.Generator,
                 perturb: bool) -> Dict:
    """Build one view's token list + query/key metadata.

    perturb=False -> canonical view O (pairs & queries in their reconstructed order, no extra
    distractors, no shift).  perturb=True -> a semantically-equivalent view varying only the
    irrelevant factors enabled in ``aug``.
    """
    key_lo, key_hi, _, _ = mq.id_ranges()
    assoc = list(core["assoc"])
    queries = list(core["queries"])
    real_keys = set(core["key_tokens"])

    if perturb and aug.permute_pairs and len(assoc) > 1:
        perm = torch.randperm(len(assoc), generator=g).tolist()
        assoc = [assoc[i] for i in perm]
    if perturb and aug.permute_queries and len(queries) > 1:
        perm = torch.randperm(len(queries), generator=g).tolist()
        queries = [queries[i] for i in perm]

    shift = 0
    if perturb and aug.max_pos_shift > 0:
        shift = int(torch.randint(aug.max_pos_shift + 1, (1,), generator=g))

    tokens: List[int] = [0] * shift  # leading positional shift via pad tokens (id 0)
    key_token_to_pos: Dict[int, int] = {}
    for ktok, vtok in assoc:
        kp = len(tokens)
        tokens.append(ktok)
        key_token_to_pos[ktok] = kp
        tokens.append(vtok)

    if perturb and aug.extra_distractors > 0:
        for d in _sample_extra_distractors(real_keys, key_lo, key_hi,
                                            aug.extra_distractors, g):
            tokens.append(d)

    query_token_to_pos: Dict[int, int] = {}
    query_answer: Dict[int, int] = {}
    for qtok, ktok, answer in queries:
        qp = len(tokens)
        tokens.append(qtok)
        query_token_to_pos[qtok] = qp
        query_answer[qtok] = answer

    if len(tokens) > aug.context_length:
        raise ValueError(f"realised length {len(tokens)} exceeds context_length "
                         f"{aug.context_length}")
    return {"tokens": tokens, "key_token_to_pos": key_token_to_pos,
            "query_token_to_pos": query_token_to_pos, "query_answer": query_answer}


# --------------------------------------------------------------------------------------
# Build an aligned pair for a whole batch.
# --------------------------------------------------------------------------------------

def make_aligned_pair(base: MQARBatch, mq: MQARConfig, aug: AugConfig, seed: int,
                      shuffled_control: bool = False, device="cpu") -> AlignedPair:
    """Given a base training batch, build (view O == the base associations in canonical order,
    view P == a semantically-equivalent perturbation) with canonical alignment indices.

    view O is realised from the SAME associations as ``base`` (identical answers); its task
    targets are used for the task loss so that a lambda=0 consistency run reduces to the
    task-only baseline.  ``shuffled_control`` fills ``key_perm`` with a random permutation of
    the key axis (semantic misalignment) instead of the identity.
    """
    B = base.tokens.shape[0]
    g = torch.Generator().manual_seed(seed)
    views_o, views_p, cores = [], [], []
    for b in range(B):
        core = decode_sample(base, b)
        cores.append(core)
        views_o.append(realize_view(core, mq, aug, g, perturb=False))
        views_p.append(realize_view(core, mq, aug, g, perturb=True))

    Q = len(cores[0]["queries"])
    K = len(cores[0]["key_tokens"])
    No = max(len(v["tokens"]) for v in views_o)
    Np = max(len(v["tokens"]) for v in views_p)

    tokens_o = torch.zeros(B, No, dtype=torch.long)
    tokens_p = torch.zeros(B, Np, dtype=torch.long)
    targets_o = torch.full((B, No), IGNORE_INDEX, dtype=torch.long)
    q_idx_o = torch.zeros(B, Q, dtype=torch.long)
    q_idx_p = torch.zeros(B, Q, dtype=torch.long)
    k_idx_o = torch.zeros(B, K, dtype=torch.long)
    k_idx_p = torch.zeros(B, K, dtype=torch.long)
    key_perm = torch.zeros(B, K, dtype=torch.long)

    cg = torch.Generator().manual_seed(seed + 5_000_011)  # control permutation stream
    for b in range(B):
        vo, vp, core = views_o[b], views_p[b], cores[b]
        to, tp = vo["tokens"], vp["tokens"]
        tokens_o[b, :len(to)] = torch.tensor(to, dtype=torch.long)
        tokens_p[b, :len(tp)] = torch.tensor(tp, dtype=torch.long)
        # task targets on view O (answers at each query position)
        for qtok, qp in vo["query_token_to_pos"].items():
            targets_o[b, qp] = vo["query_answer"][qtok]
        # canonical query axis: queries sorted by query-token id
        qtoks = sorted(vo["query_token_to_pos"].keys())
        for j, qt in enumerate(qtoks):
            q_idx_o[b, j] = vo["query_token_to_pos"][qt]
            q_idx_p[b, j] = vp["query_token_to_pos"][qt]
        # canonical key axis: candidate keys sorted by key-token id
        ktoks = sorted(core["key_tokens"])
        for j, kt in enumerate(ktoks):
            k_idx_o[b, j] = vo["key_token_to_pos"][kt]
            k_idx_p[b, j] = vp["key_token_to_pos"][kt]
        if shuffled_control and K > 1:
            key_perm[b] = torch.randperm(K, generator=cg)
        else:
            key_perm[b] = torch.arange(K)

    pair = AlignedPair(tokens_o, tokens_p, targets_o, q_idx_o, q_idx_p,
                       k_idx_o, k_idx_p, key_perm)
    return pair.to(device)
