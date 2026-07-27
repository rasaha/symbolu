"""
capacity_dataset.py — capacity-bound admission task (§3-4).

Each example: a focus cue + N candidate events (relevant / frequency-matched hard negatives /
ordinary distractors), an exact final query, and a bounded admission capacity K. Storing every
event is impossible (N > K). The token sequence [CUE_f, EVENT_e1, ..., EVENT_eN] is what the
router scores; event METADATA (entity, value, category, position, required-for-answer) drives
the exact store and grading. Relevant/hard/ordinary are the SAME EVENT token type; only focus
identity distinguishes relevant from hard negatives.

Families (§4):
  single   : query targets one specific relevant event → answer = its value.
  multihop : chain a→b, b→c; query asks c; BOTH link events must be admitted.
  update   : an entity's value is superseded later; query wants the latest.
  hardneg  : single-hop with a heavy frequency-matched hard-negative flood.

Vocab: 0 PAD, 1 PROBE, cue_base+e = CUE_e, evt_base+e = EVENT_e.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import torch

from .config import DataCfg


@dataclass
class Vocab:
    num_entities: int

    @property
    def PAD(self): return 0
    @property
    def PROBE(self): return 1
    @property
    def cue_base(self): return 2
    @property
    def evt_base(self): return 2 + self.num_entities
    @property
    def size(self): return 2 + 2 * self.num_entities

    def cue(self, e): return self.cue_base + e
    def evt(self, e): return self.evt_base + e


def build_vocab(cfg: DataCfg = DataCfg()) -> Vocab:
    return Vocab(cfg.num_entities)


def _ri(n, g): return int(torch.randint(0, n, (1,), generator=g).item())


def _make(vocab, cfg: DataCfg, N, K, g) -> dict:
    E, V = cfg.num_entities, cfg.num_values
    focus = _ri(E, g)
    events = []       # list of dict(entity, value, category, required)

    if cfg.family == "multihop":
        # chain focus=a -> b -> c ; query asks value reachable in `depth` hops from a
        chain = [focus]
        for _ in range(cfg.multihop_depth):
            chain.append(_ri(E, g))
        link_events = []
        for h in range(cfg.multihop_depth):
            link_events.append({"entity": chain[h], "value": chain[h + 1], "category": "relevant", "required": True})
        events += link_events
        query_entity, answer = chain[0], chain[-1]
        n_req = cfg.multihop_depth
    elif cfg.family == "update":
        a = focus
        v_old, v_new = _ri(V, g), _ri(V, g)
        events.append({"entity": a, "value": v_old, "category": "relevant_stale", "required": False})
        events.append({"entity": a, "value": v_new, "category": "relevant", "required": True})
        query_entity, answer = a, v_new
        n_req = 1
    else:   # single / hardneg
        rel = []
        for _ in range(cfg.n_relevant):
            rel.append({"entity": focus, "value": _ri(V, g), "category": "relevant", "required": False})
        # distinguish target relevant events by value; query targets one by picking its slot
        tgt = _ri(len(rel), g); rel[tgt]["required"] = True
        events += rel
        query_entity, answer = focus, rel[tgt]["value"]
        n_req = 1

    # hard negatives: one frequency-matched repeated distractor entity (≠ focus)
    hard = focus
    while hard == focus:
        hard = _ri(E, g)
    n_hard = cfg.n_hard if cfg.family != "hardneg" else max(cfg.n_hard, N // 2)
    for _ in range(min(n_hard, N)):
        events.append({"entity": hard, "value": _ri(V, g), "category": "hard", "required": False})
    # ordinary distractors fill up to N
    while len(events) < N:
        e = _ri(E, g)
        if e == focus:
            e = (e + 1) % E
        events.append({"entity": e, "value": _ri(V, g), "category": "ordinary", "required": False})
    events = events[:N]
    # shuffle event order (positions randomized)
    perm = torch.randperm(N, generator=g).tolist()
    events = [events[i] for i in perm]
    for i, ev in enumerate(events):
        ev["position"] = i

    tokens = [vocab.cue(focus)] + [vocab.evt(ev["entity"]) for ev in events] + [vocab.PROBE]
    return {"tokens": tokens, "focus": focus, "events": events, "N": N, "K": K,
            "query_entity": query_entity, "answer": answer, "family": cfg.family,
            "n_required": n_req, "hard_entity": hard,
            "event_pos": list(range(1, N + 1))}   # positions of EVENT tokens in the sequence


def generate(vocab, cfg: DataCfg, N, K, n, seed) -> List[dict]:
    g = torch.Generator().manual_seed(seed)
    return [_make(vocab, cfg, N, K, g) for _ in range(n)]


def collate(batch, pad_id, device="cpu"):
    maxlen = max(len(e["tokens"]) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    for i, e in enumerate(batch):
        ids[i, :len(e["tokens"])] = torch.tensor(e["tokens"])
    return ids.to(device)
