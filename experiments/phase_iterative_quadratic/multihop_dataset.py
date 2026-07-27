"""
multihop_dataset.py — multi-hop chains tokenized as (key, value) pairs so an attention model can
actually RETRIEVE what a link points to (§10). Later-hop relevance is discoverable only after the
earlier hop is read: reading a link's VALUE token reveals the next hop's key.

Each event = (entity, relation, value=next identity), tokenized as adjacent [KEY_(e,r), VAL_value].
Sequence: [CUE_(A,r1)] + [KEY,VAL]×N + [PROBE]. Chain A-r1→B-r2→C(→D); answer = final identity.
Hard negatives: same-entity/wrong-relation, same-relation/wrong-entity, frequency-matched repeat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import torch


@dataclass
class Vocab:
    E: int = 8
    R: int = 4

    @property
    def n_id(self): return self.E * self.R
    @property
    def PAD(self): return 0
    @property
    def PROBE(self): return 1
    @property
    def cue_base(self): return 2
    @property
    def key_base(self): return 2 + self.n_id
    @property
    def val_base(self): return 2 + 2 * self.n_id
    @property
    def size(self): return 2 + 3 * self.n_id

    def idx(self, e, r): return e * self.R + r
    def cue(self, e, r): return self.cue_base + self.idx(e, r)
    def key(self, e, r): return self.key_base + self.idx(e, r)
    def val(self, ident): return self.val_base + ident


def build_vocab(E=8, R=4): return Vocab(E, R)


def _ri(n, g): return int(torch.randint(0, n, (1,), generator=g).item())


def make(vocab: Vocab, N, depth, g, n_hard=8) -> dict:
    E, R = vocab.E, vocab.R
    def oe(e): return (e + 1 + _ri(E - 1, g)) % E if E > 1 else e
    def orl(r): return (r + 1 + _ri(R - 1, g)) % R if R > 1 else r

    chain = [(_ri(E, g), _ri(R, g))]
    for _ in range(depth):
        chain.append((_ri(E, g), _ri(R, g)))
    events = []
    for h in range(depth):
        e, r = chain[h]
        events.append({"entity": e, "relation": r, "value": vocab.idx(*chain[h + 1]),
                       "ident": vocab.idx(e, r), "category": "relevant", "required": True, "hop": h})
    fe, fr = chain[0]
    rep_e = oe(fe)
    for _ in range(min(n_hard, N)):
        u = _ri(3, g)
        if u == 0:
            e, r = fe, orl(fr)
        elif u == 1:
            e, r = oe(fe), fr
        else:
            e, r = rep_e, fr
        events.append({"entity": e, "relation": r, "value": _ri(vocab.n_id, g),
                       "ident": vocab.idx(e, r), "category": "hard", "required": False, "hop": -1})
    while len(events) < N:
        e, r = _ri(E, g), _ri(R, g)
        events.append({"entity": e, "relation": r, "value": _ri(vocab.n_id, g),
                       "ident": vocab.idx(e, r), "category": "ordinary", "required": False, "hop": -1})
    events = events[:N]
    perm = torch.randperm(N, generator=g).tolist()
    events = [events[i] for i in perm]

    tokens = [vocab.cue(fe, fr)]
    key_pos = []
    for ev in events:
        key_pos.append(len(tokens))
        tokens.append(vocab.key(ev["entity"], ev["relation"]))
        tokens.append(vocab.val(ev["value"]))
    tokens.append(vocab.PROBE)
    answer = vocab.idx(*chain[-1])
    # ordered required event indices by hop
    req_evidx = [i for i, ev in enumerate(events) if ev["required"]]
    req_evidx.sort(key=lambda i: events[i]["hop"])
    return {"tokens": tokens, "events": events, "key_pos": key_pos, "N": N,
            "answer": answer, "n_required": depth, "req_evidx": req_evidx,
            "focus": (fe, fr)}


def generate(vocab, N, depth, n, seed, n_hard=8) -> List[dict]:
    g = torch.Generator().manual_seed(seed)
    return [make(vocab, N, depth, g, n_hard) for _ in range(n)]


def collate(batch, pad_id, device="cpu"):
    maxlen = max(len(e["tokens"]) for e in batch)
    ids = torch.full((len(batch), maxlen), pad_id, dtype=torch.long)
    for i, e in enumerate(batch):
        ids[i, :len(e["tokens"])] = torch.tensor(e["tokens"])
    return ids.to(device)
