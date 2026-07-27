"""
dataset.py — self-contained distant-focus retention task (§10).

A focus cue names one entity early, as a DISTINCTLY-TYPED token (CUE_e) so a per-token
gate can in principle learn to grab it. Then a flood of filler tokens and entity EVENTS
(EVENT_e, some relevant = the focus entity, most distractors) pushes the cue far out of
any local window. At the final PROBE position the Phase state is read to recover the focus
identity; at each event position the readout is probed for relevance (is this the focus
entity?). This reproduces the v1 dilution problem: dense no-decay accumulation buries the
single rare cue under the distractor flood.

Vocabulary layout (ids):
    0            : PAD
    1            : PROBE  (query marker at the end)
    2 .. 2+F-1   : FILLER token types (noise)
    base_cue+e   : CUE_e    (focus cue for entity e; only ever at the cue position)
    base_evt+e   : EVENT_e  (an event mentioning entity e)

Each example dict:
    tokens        : list[int]                 (length = distance + 2: cue, body, probe)
    focus_id      : int in [0, E)
    cue_pos       : 0
    probe_pos     : len-1
    event_pos     : list[int]                 positions of EVENT tokens
    event_entity  : list[int]                 entity per event
    event_relevant: list[bool]                entity == focus
    write_target  : list[float] length N in {1 (cue/relevant event), 0 (filler/distractor), -1 ignore}
    distance      : int
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import torch

from .config import DataCfg


@dataclass
class Vocab:
    num_entities: int
    num_filler: int

    @property
    def PAD(self): return 0

    @property
    def PROBE(self): return 1

    @property
    def filler_base(self): return 2

    @property
    def cue_base(self): return 2 + self.num_filler

    @property
    def evt_base(self): return 2 + self.num_filler + self.num_entities

    @property
    def size(self): return 2 + self.num_filler + 2 * self.num_entities

    def cue(self, e): return self.cue_base + e

    def evt(self, e): return self.evt_base + e


def build_vocab(cfg: DataCfg = DataCfg()) -> Vocab:
    return Vocab(cfg.num_entities, cfg.num_filler)


def _make_one(vocab: Vocab, cfg: DataCfg, distance: int, g: torch.Generator) -> dict:
    E = cfg.num_entities

    def randint(n):
        return int(torch.randint(0, n, (1,), generator=g).item())

    def rand():
        return float(torch.rand(1, generator=g).item())

    focus = randint(E)
    tokens = [vocab.cue(focus)]                       # position 0: the focus cue
    event_pos, event_entity, event_relevant = [], [], []
    write_target = [1.0]                               # cue is a write target
    body_len = distance                                # tokens between cue and probe
    for _ in range(body_len):
        if rand() < cfg.event_rate:
            if rand() < cfg.relevant_event_rate:
                e = focus; rel = True
            else:
                e = randint(E)
                rel = (e == focus)
            tokens.append(vocab.evt(e))
            event_pos.append(len(tokens) - 1)
            event_entity.append(e); event_relevant.append(rel)
            write_target.append(1.0 if rel else 0.0)
        else:
            tokens.append(vocab.filler_base + randint(cfg.num_filler))
            write_target.append(0.0)
    tokens.append(vocab.PROBE)
    write_target.append(-1.0)                          # probe position: ignore for write loss
    return {
        "tokens": tokens, "focus_id": focus, "cue_pos": 0, "probe_pos": len(tokens) - 1,
        "event_pos": event_pos, "event_entity": event_entity, "event_relevant": event_relevant,
        "write_target": write_target, "distance": distance,
    }


def generate(vocab: Vocab, cfg: DataCfg, distance: int, n: int, seed: int) -> List[dict]:
    g = torch.Generator().manual_seed(seed)
    return [_make_one(vocab, cfg, distance, g) for _ in range(n)]


def collate(batch, pad_id, device="cpu"):
    """Right-pad to max length. Returns tensors + per-example metadata lists."""
    maxlen = max(len(e["tokens"]) for e in batch)
    B = len(batch)
    ids = torch.full((B, maxlen), pad_id, dtype=torch.long)
    wtgt = torch.full((B, maxlen), -1.0)
    probe_pos = torch.zeros(B, dtype=torch.long)
    focus = torch.zeros(B, dtype=torch.long)
    for i, e in enumerate(batch):
        n = len(e["tokens"])
        ids[i, :n] = torch.tensor(e["tokens"])
        wtgt[i, :n] = torch.tensor(e["write_target"])
        probe_pos[i] = e["probe_pos"]; focus[i] = e["focus_id"]
    return (ids.to(device), wtgt.to(device), probe_pos.to(device), focus.to(device))
