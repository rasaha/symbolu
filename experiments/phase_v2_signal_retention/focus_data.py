"""
focus_data.py — controlled focus-retention sequences for the Phase v2 signal study.

Layout: [focus header] [body: distractor records + filler, length-controlled] .
  header  : "focus vendor V*"  — declares the focus IDENTITY V* (one of N vendors)
  body    : distractor "record" facts (vendors != V*) interleaved with filler; a few
            RELEVANT facts (vendor == V*) are also placed.
Labels:
  focus_vendor_id : the identity to decode from Phase state at distance.
  anchor positions + per-anchor vendor  : for the relevance-F1 probe (is vendor==V*).
The focus cue leaves the local window quickly; only a global recurrent state can carry
it to distant positions. Controllable: n_distractors and target length (filler).
Vendor pool is split-partitioned train/val/test (disjoint focus identities).
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from experiments.phase_guided_slots_v2.task_schema import (
    build_vocab, VENDORS, CONTRACTS, REGIONS, PRODUCTS, VALUES, SOURCES, VERSIONS,
)

FILLER_WORDS = ["the", "record", "was", "amended", "after", "review", "and", "flagged",
                "for", "audit", "in", "the", "current", "status"]


def _part(items, split):
    n = len(items)
    return {"train": items[: int(n * 0.7)], "val": items[int(n * 0.7): int(n * 0.85)],
            "test": items[int(n * 0.85):]}[split]


@dataclass
class FocusExample:
    tokens: List[int]
    focus_vendor_id: int          # class label to decode (index into VENDORS)
    anchor_pos: List[int]         # positions of fact anchors (<sep>)
    anchor_vendor_id: List[int]   # vendor class at each anchor
    anchor_relevant: List[int]    # 1 if anchor vendor == focus vendor
    header_end: int               # position where the focus header ends
    length: int
    meta: Dict = field(default_factory=dict)


class FocusGen:
    def __init__(self, vocab, split, seed):
        self.v = vocab
        self.vendors = _part(VENDORS, split)
        self.contracts = _part(CONTRACTS, split)
        self.rng = random.Random(hash((split, "focusv2", seed)) & 0xFFFFFFFF)
        self.vidx = {vn: i for i, vn in enumerate(VENDORS)}

    def _record(self, vendor):
        r = self.rng
        return ["contract", r.choice(self.contracts), "vendor", vendor, "region",
                r.choice(REGIONS), "product", r.choice(PRODUCTS), "value",
                r.choice(VALUES), "source", r.choice(SOURCES), "<sep>"]

    def make(self, n_distractors: int, target_len: int, n_relevant: int = 3) -> FocusExample:
        r = self.rng
        v = self.v
        focus = r.choice(self.vendors)
        others = [x for x in self.vendors if x != focus] or self.vendors
        words = ["focus", "vendor", focus, "<sep>"]
        header_end = len(words) - 1
        anchor_pos, anchor_vendor, anchor_rel = [], [], []

        # build record units: n_relevant relevant + n_distractors distractor, shuffled
        units = [focus] * n_relevant + [r.choice(others) for _ in range(n_distractors)]
        r.shuffle(units)

        for u in units:
            # optional filler before the record to pad length
            if len(words) < target_len:
                nfill = r.randint(0, 3)
                words += [r.choice(FILLER_WORDS) for _ in range(nfill)]
            rec = self._record(u)
            words += rec
            anchor_pos.append(len(words) - 1)           # the <sep>
            anchor_vendor.append(self.vidx[u]); anchor_rel.append(int(u == focus))
        # pad with filler to reach target length
        while len(words) < target_len:
            words.append(r.choice(FILLER_WORDS))
        toks = v.encode(words)
        return FocusExample(tokens=toks, focus_vendor_id=self.vidx[focus],
                            anchor_pos=anchor_pos, anchor_vendor_id=anchor_vendor,
                            anchor_relevant=anchor_rel, header_end=header_end,
                            length=len(toks),
                            meta={"n_distractors": n_distractors, "focus": focus,
                                  "n_relevant": n_relevant})


def generate_focus(vocab, split, seed, n, n_distractors, target_len, n_relevant=3):
    g = FocusGen(vocab, split, seed)
    return [g.make(n_distractors, target_len, n_relevant) for _ in range(n)]
