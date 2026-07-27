"""
hard_dataset.py — hard-negative variant of the distant-focus task (§4 Add hard negatives).

Same schema as experiments.phase_v3_selective_ssm.dataset, but injects a frequency-matched
REPEATED DISTRACTOR entity d* (≠ focus) that recurs about as often as the focus entity. This
removes frequency/recency shortcuts: relevant events (entity == focus) and the hard-distractor
events share format, position statistics, and frequency — the ONLY distinguishing feature is
identity-match to the distant cue. Distractors are otherwise the same EVENT type as relevant
events (structurally matched). Reuses the v3 Vocab so probes/collate are unchanged.
"""
from __future__ import annotations

from typing import List

import torch

from experiments.phase_v3_selective_ssm.dataset import Vocab, build_vocab  # noqa: F401
from experiments.phase_v3_selective_ssm.config import DataCfg


def _make_one_hard(vocab: Vocab, cfg: DataCfg, distance: int, g: torch.Generator) -> dict:
    E = cfg.num_entities

    def ri(n): return int(torch.randint(0, n, (1,), generator=g).item())
    def rf(): return float(torch.rand(1, generator=g).item())

    focus = ri(E)
    hard = focus
    while hard == focus:
        hard = ri(E)                                   # a single frequency-matched hard distractor

    tokens = [vocab.cue(focus)]
    event_pos, event_entity, event_relevant, write_target = [], [], [], [1.0]
    for _ in range(distance):
        if rf() < cfg.event_rate:
            u = rf()
            if u < cfg.relevant_event_rate:
                e, rel = focus, True                    # relevant (matches cue)
            elif u < cfg.relevant_event_rate + cfg.relevant_event_rate:
                e, rel = hard, False                    # hard distractor (matched frequency)
            else:
                e = ri(E); rel = (e == focus)           # random distractor
            tokens.append(vocab.evt(e))
            event_pos.append(len(tokens) - 1)
            event_entity.append(e); event_relevant.append(rel)
            write_target.append(1.0 if rel else 0.0)
        else:
            tokens.append(vocab.filler_base + ri(cfg.num_filler))
            write_target.append(0.0)
    tokens.append(vocab.PROBE)
    write_target.append(-1.0)
    return {"tokens": tokens, "focus_id": focus, "hard_distractor": hard,
            "cue_pos": 0, "probe_pos": len(tokens) - 1,
            "event_pos": event_pos, "event_entity": event_entity,
            "event_relevant": event_relevant, "write_target": write_target, "distance": distance}


def generate_hard(vocab: Vocab, cfg: DataCfg, distance: int, n: int, seed: int) -> List[dict]:
    g = torch.Generator().manual_seed(seed)
    return [_make_one_hard(vocab, cfg, distance, g) for _ in range(n)]
