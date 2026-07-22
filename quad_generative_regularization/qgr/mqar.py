"""Deterministic Multi-Query Associative Recall (MQAR) generation.

Sequence layout (causal, left-to-right):

    [ k1 v1 k2 v2 ... kM vM  (distractor filler...)  q1 q2 ... qQ ]

Each key token k appears once in the "context" region; its immediately following token
is the corresponding value v.  Each query token q repeats one of the earlier keys; the
model must predict the matching value at the query position.  Targets are -100
(ignore) everywhere except query positions, where the target is the correct value token.

The generator is fully deterministic given (config, seed) and supports disjoint
train/val/test splits via disjoint seed streams.  It also emits, per query position, the
auxiliary supervision needed by Arms C and D WITHOUT leaking anything about the future:

    * key_pos[b, t]      : position of the correct earlier key for the query at t (or -1)
    * cand_mask[b, t, :] : boolean mask of candidate KEY positions for query t
                           (correct key + earlier distractor keys), all strictly < t.

Vocabulary partition (ids, pad=0 reserved):
    keys   : [key_lo, key_hi)
    values : [val_lo, val_hi)
    query tokens reuse the key ids (a query is literally the key token repeated).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch


IGNORE_INDEX = -100


@dataclass
class MQARConfig:
    num_kv: int = 8               # number of key-value associations in the context
    num_queries: int = 4          # number of queries appended after the context
    num_distractors: int = 0      # extra filler distractor tokens between context and queries
    vocab_size: int = 64          # total vocab incl. pad(0)
    n_relation_systems: int = 1   # independent relation systems packed in one sequence
    seq_len: Optional[int] = None # if None, computed from the layout; else padded/validated
    key_frac: float = 0.5         # fraction of usable vocab allocated to key ids

    # Derived id ranges (filled by _partition_vocab)
    def id_ranges(self) -> Tuple[int, int, int, int]:
        usable = self.vocab_size - 1  # exclude pad=0
        n_keys = max(self.num_kv * max(self.n_relation_systems, 1) + 4,
                     int(usable * self.key_frac))
        key_lo = 1
        key_hi = 1 + n_keys
        val_lo = key_hi
        val_hi = self.vocab_size
        if val_hi - val_lo < self.num_kv * max(self.n_relation_systems, 1) + 1:
            raise ValueError("vocab_size too small for requested num_kv / relation systems")
        return key_lo, key_hi, val_lo, val_hi

    def base_seq_len(self) -> int:
        ctx = 2 * self.num_kv * max(self.n_relation_systems, 1)
        return ctx + self.num_distractors + self.num_queries * max(self.n_relation_systems, 1)


@dataclass
class MQARBatch:
    tokens: torch.Tensor       # [B, N] long
    targets: torch.Tensor      # [B, N] long (IGNORE_INDEX except at query positions)
    query_pos: torch.Tensor    # [B, Q_total] long, positions of query tokens
    key_pos: torch.Tensor      # [B, N] long, correct-key position per position (-1 if n/a)
    cand_mask: torch.Tensor    # [B, N, N] bool, candidate KEY positions per query position

    def to(self, device) -> "MQARBatch":
        return MQARBatch(
            self.tokens.to(device), self.targets.to(device), self.query_pos.to(device),
            self.key_pos.to(device), self.cand_mask.to(device),
        )


def _gen_one(cfg: MQARConfig, g: torch.Generator) -> Dict[str, List[int]]:
    """Generate one sequence's token list + per-query metadata (deterministic via g)."""
    key_lo, key_hi, val_lo, val_hi = cfg.id_ranges()
    R = max(cfg.n_relation_systems, 1)

    tokens: List[int] = []
    # position -> ("key", relation_system, key_token) for candidate/pos bookkeeping
    key_positions: List[int] = []          # positions holding a key in the context
    key_token_at_pos: Dict[int, int] = {}  # position -> key token
    val_for_key_pos: Dict[int, int] = {}   # key position -> value token
    system_of_key_pos: Dict[int, int] = {} # key position -> relation system id

    # Build context: R independent relation systems, each with num_kv distinct keys.
    for sys_id in range(R):
        # distinct keys for this system (sampled without replacement)
        key_ids = _sample_distinct(key_lo, key_hi, cfg.num_kv, g)
        val_ids = _sample_distinct(val_lo, val_hi, cfg.num_kv, g)
        for k, v in zip(key_ids, val_ids):
            kp = len(tokens)
            tokens.append(k)
            key_positions.append(kp)
            key_token_at_pos[kp] = k
            system_of_key_pos[kp] = sys_id
            val_for_key_pos[kp] = v
            tokens.append(v)  # value immediately follows its key

    # Distractor filler tokens (random KEYS not used as queries; still causal-visible,
    # act as negative candidates by identity but carry no query later).
    for _ in range(cfg.num_distractors):
        tokens.append(_sample_distinct(key_lo, key_hi, 1, g)[0])

    # Queries: for each relation system, pick num_queries keys to query.
    query_pos: List[int] = []
    correct_key_pos_per_query: Dict[int, int] = {}
    for sys_id in range(R):
        sys_key_positions = [kp for kp in key_positions if system_of_key_pos[kp] == sys_id]
        chosen = _choice(sys_key_positions, cfg.num_queries, g)
        for kp in chosen:
            qp = len(tokens)
            tokens.append(key_token_at_pos[kp])  # query == the key token
            query_pos.append(qp)
            correct_key_pos_per_query[qp] = kp

    return {
        "tokens": tokens,
        "query_pos": query_pos,
        "correct_key_pos_per_query": correct_key_pos_per_query,
        "val_for_key_pos": val_for_key_pos,
        "key_positions": key_positions,
        "system_of_key_pos": system_of_key_pos,
    }


def _sample_distinct(lo: int, hi: int, n: int, g: torch.Generator) -> List[int]:
    perm = torch.randperm(hi - lo, generator=g)[:n]
    return [lo + int(x) for x in perm]


def _choice(items: List[int], n: int, g: torch.Generator) -> List[int]:
    if n >= len(items):
        idx = torch.randperm(len(items), generator=g)
    else:
        idx = torch.randperm(len(items), generator=g)[:n]
    return [items[int(i)] for i in idx]


def generate_batch(cfg: MQARConfig, seed: int, batch_size: int, device="cpu") -> MQARBatch:
    """Deterministically generate a batch. Same (cfg, seed, batch_size) -> identical batch."""
    g = torch.Generator().manual_seed(seed)
    seqs = [_gen_one(cfg, g) for _ in range(batch_size)]
    N = cfg.seq_len or max(len(s["tokens"]) for s in seqs)
    if cfg.seq_len is not None:
        for s in seqs:
            if len(s["tokens"]) > N:
                raise ValueError(f"sequence length {len(s['tokens'])} exceeds seq_len {N}")

    B = batch_size
    tokens = torch.zeros(B, N, dtype=torch.long, device=device)  # pad=0
    targets = torch.full((B, N), IGNORE_INDEX, dtype=torch.long, device=device)
    key_pos = torch.full((B, N), -1, dtype=torch.long, device=device)
    cand_mask = torch.zeros(B, N, N, dtype=torch.bool, device=device)
    max_q = max(len(s["query_pos"]) for s in seqs)
    query_pos = torch.full((B, max_q), -1, dtype=torch.long, device=device)

    for b, s in enumerate(seqs):
        toks = s["tokens"]
        tokens[b, : len(toks)] = torch.tensor(toks, dtype=torch.long, device=device)
        for j, qp in enumerate(s["query_pos"]):
            kp = s["correct_key_pos_per_query"][qp]
            val = s["val_for_key_pos"][kp]
            targets[b, qp] = val
            key_pos[b, qp] = kp
            query_pos[b, j] = qp
            # Candidate KEY positions: all key positions strictly BEFORE the query.
            # (Correct key + earlier distractor keys; all causally visible.)
            for cand_kp in s["key_positions"]:
                if cand_kp < qp:
                    cand_mask[b, qp, cand_kp] = True

    return MQARBatch(tokens, targets, query_pos, key_pos, cand_mask)


# ---- Split helpers: disjoint deterministic seed streams --------------------------------

def split_seed(base_seed: int, split: str, index: int) -> int:
    """Map (base_seed, split, index) -> a disjoint deterministic seed.

    Splits get non-overlapping high-order offsets so train/val/test never coincide.
    """
    offset = {"train": 0, "val": 1_000_000, "test": 2_000_000}[split]
    return (base_seed * 7_919 + offset + index) % (2**31 - 1)


def iter_batches(cfg: MQARConfig, base_seed: int, split: str, n_batches: int,
                 batch_size: int, device="cpu"):
    """Yield n_batches deterministic batches from a split's disjoint seed stream."""
    for i in range(n_batches):
        yield generate_batch(cfg, split_seed(base_seed, split, i), batch_size, device)
