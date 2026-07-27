"""
capacity_dataset.py — capacity-bound admission task (§3-4), with (entity, relation) identities.

Relevance requires matching the focus on BOTH entity and relation, so a simple entity-matcher
cannot solve admission by identity alone. Hard negatives (§4E) share nuisance structure with
the relevant event and differ only in the focus relationship:
  same-entity / wrong-relation, same-relation / wrong-entity, and a frequency-matched repeated
distractor. `num_relations=1` recovers the entity-only task.

Each example: focus cue (e,r) + N candidate events, an exact final query, capacity K.
Token sequence [CUE_(e,r), EVENT_(e,r)…, PROBE] is what the router scores; event metadata
(identity, value, category, position, required) drives the exact store and grading.

Families: single (query one relevant event) / multihop (chain, both links required) /
update (later fact supersedes) / hardneg (heavy same-entity-wrong-relation flood).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import torch

from .config import DataCfg


@dataclass
class Vocab:
    num_entities: int
    num_relations: int = 1

    @property
    def n_id(self): return self.num_entities * self.num_relations
    @property
    def PAD(self): return 0
    @property
    def PROBE(self): return 1
    @property
    def cue_base(self): return 2
    @property
    def evt_base(self): return 2 + self.n_id
    @property
    def size(self): return 2 + 2 * self.n_id

    def idx(self, e, r): return e * self.num_relations + r
    def cue(self, e, r): return self.cue_base + self.idx(e, r)
    def evt(self, e, r): return self.evt_base + self.idx(e, r)


def build_vocab(cfg: DataCfg = DataCfg()) -> Vocab:
    return Vocab(cfg.num_entities, getattr(cfg, "num_relations", 1))


def _ri(n, g): return int(torch.randint(0, n, (1,), generator=g).item())


def _make(vocab, cfg, N, K, g) -> dict:
    E, R, V = cfg.num_entities, vocab.num_relations, cfg.num_values
    fe, fr = _ri(E, g), _ri(R, g)
    events = []                       # dicts: entity, relation, value, category, required

    def other_rel(r):
        r2 = _ri(R, g)
        return r2 if R == 1 else ((r + 1 + _ri(R - 1, g)) % R)

    def other_ent(e):
        return (e + 1 + _ri(E - 1, g)) % E if E > 1 else e

    if cfg.family == "multihop":
        chain = [(fe, fr)]
        for _ in range(cfg.multihop_depth):
            chain.append((_ri(E, g), _ri(R, g)))
        for h in range(cfg.multihop_depth):
            e, r = chain[h]
            events.append({"entity": e, "relation": r, "value": vocab.idx(*chain[h + 1]),
                           "category": "relevant", "required": True})
        query_id, answer = vocab.idx(fe, fr), vocab.idx(*chain[-1])
        n_req = cfg.multihop_depth
    elif cfg.family == "update":
        events.append({"entity": fe, "relation": fr, "value": _ri(V, g), "category": "relevant_stale", "required": False})
        v_new = _ri(V, g)
        events.append({"entity": fe, "relation": fr, "value": v_new, "category": "relevant", "required": True})
        query_id, answer, n_req = vocab.idx(fe, fr), v_new, 1
    else:   # single / hardneg
        ans = _ri(V, g)
        events.append({"entity": fe, "relation": fr, "value": ans, "category": "relevant", "required": True})
        query_id, answer, n_req = vocab.idx(fe, fr), ans, 1

    # hard negatives (§4E): same-entity/wrong-relation, same-relation/wrong-entity, repeated distractor
    n_hard = cfg.n_hard if cfg.family != "hardneg" else max(cfg.n_hard, N // 2)
    rep_e, rep_r = other_ent(fe), fr           # frequency-matched repeated distractor
    for k in range(min(n_hard, N)):
        u = _ri(3, g)
        if u == 0 and R > 1:
            e, r = fe, other_rel(fr)           # same entity, wrong relation (hardest)
        elif u == 1:
            e, r = other_ent(fe), fr           # same relation, wrong entity
        else:
            e, r = rep_e, rep_r                # repeated distractor
        events.append({"entity": e, "relation": r, "value": _ri(V, g), "category": "hard", "required": False})
    # ordinary distractors fill to N
    while len(events) < N:
        e, r = _ri(E, g), _ri(R, g)
        if (e, r) == (fe, fr):
            e = other_ent(fe)
        events.append({"entity": e, "relation": r, "value": _ri(V, g), "category": "ordinary", "required": False})
    events = events[:N]
    perm = torch.randperm(N, generator=g).tolist()
    events = [events[i] for i in perm]
    for i, ev in enumerate(events):
        ev["position"] = i
        ev["ident"] = vocab.idx(ev["entity"], ev["relation"])   # composite identity for the exact store

    tokens = [vocab.cue(fe, fr)] + [vocab.evt(ev["entity"], ev["relation"]) for ev in events] + [vocab.PROBE]
    return {"tokens": tokens, "focus": (fe, fr), "events": events, "N": N, "K": K,
            "query_entity": query_id, "answer": answer, "family": cfg.family,
            "n_required": n_req, "event_pos": list(range(1, N + 1))}


def generate(vocab, cfg, N, K, n, seed) -> List[dict]:
    g = torch.Generator().manual_seed(seed)
    return [_make(vocab, cfg, N, K, g) for _ in range(n)]


def collate(batch, pad_id, device="cpu"):
    maxlen = max(len(e["tokens"]) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    for i, e in enumerate(batch):
        ids[i, :len(e["tokens"])] = torch.tensor(e["tokens"])
    return ids.to(device)
