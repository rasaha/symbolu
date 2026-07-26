"""
datasets_pressure.py — topic-conditioned slot-pressure tasks (natural language).

Design rationale (the fair test of Phase-as-guidance):
  * A TOPIC entity is declared once, early, in a header sentence.
  * The body contains many "vendor X valued $V (recorded in DOC)" facts. Facts
    about the topic entity are WRITE-WORTHY (gold label 1); facts about other
    entities are distractors (label 0).
  * The query asks about the TOPIC entity. Under SLOT PRESSURE (candidate facts
    > slots), the model must have prioritized writing/retaining topic facts.
  * Crucially, "is this fact write-worthy?" depends on the DISTANT header (global
    context), which the small local window cannot see when a far fact appears.
    This is exactly where a global relevance signal (Phase) could help — and where
    plain local-only slots cannot know what to keep.

Each example provides:
    tokens, answer_pos, answer_id (queried topic value)
    write_labels : per-token {1 at topic-fact value positions, 0 elsewhere, -100 ignore}
    source answer, meta (n_candidates, n_slots_hint, pressure, topic)

Leakage control: entity names partitioned train/val/test (held-out topic identities);
values/sources shared and emittable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from experiments.lightweight_phase_natural_language.datasets import (
    BASE_NAMES, VALUE_TOKENS, SOURCE_TOKENS, FILLER, build_tokenizer, Tokenizer, make_pools,
)

TOPIC_MARK = "TOPIC"
EXTRA_SPECIAL = [TOPIC_MARK, "about", "regarding", "note", "concerning"]


def build_pressure_tokenizer() -> Tokenizer:
    tok = build_tokenizer()
    # extend with a few structural words if missing
    nxt = len(tok.itos)
    for w in EXTRA_SPECIAL:
        if w not in tok.stoi:
            tok.stoi[w] = nxt; tok.itos.append(w); nxt += 1
    return tok


@dataclass
class PExample:
    tokens: List[int]
    answer_pos: int
    answer_id: int
    write_labels: List[int]       # per-token: 1 write-worthy, 0 not, -100 ignore
    task: str
    meta: Dict = field(default_factory=dict)
    source_id: Optional[int] = None
    source_answer_pos: Optional[int] = None


class PressureGenerator:
    def __init__(self, tok: Tokenizer, split: str, seed: int):
        self.tok = tok
        self.pools = make_pools(split)
        self.rng = random.Random(hash((split, "pressure", seed)) & 0xFFFFFFFF)

    def _name(self, exclude=()):
        opts = [e.split("|")[0] for e in self.pools.entities]
        opts = [o for o in opts if o not in exclude]
        return self.rng.choice(opts)

    def _filler(self, n_sent):
        out = []
        for _ in range(n_sent):
            out += self.rng.choice(FILLER).split()
        return out

    def make(self, n_candidates: int, target_len: int = 128,
             topic_facts: int = 1) -> PExample:
        """Topic header + n_candidates facts (topic + distractors) + query."""
        tok = self.tok
        topic = self._name()
        # distractor entity names distinct from topic
        others = [self._name(exclude=(topic,)) for _ in range(max(1, n_candidates))]
        topic_val = self.rng.choice(self.pools.values)
        topic_src = self.rng.choice(self.pools.sources)

        words: List[str] = []
        wlabels: List[int] = []

        def emit(ws: List[str], value_word: str = None, value_label: int = -100):
            # only value-token positions carry a write-worthiness label (1 topic /
            # 0 distractor); everything else is ignored (-100) so write-F1 is
            # measured over fact-value decisions, not trivially over filler.
            for w in ws:
                words.append(w)
                wlabels.append(value_label if (value_word is not None and w == value_word) else -100)

        # header declaring the topic (global cue, placed early)
        emit(["TOPIC", "vendor", topic, "<sep>"])  # no value labels
        # interleave candidate facts with filler
        facts = []
        # topic fact(s)
        for _ in range(topic_facts):
            facts.append(("topic", topic, topic_val, topic_src))
        # distractor facts
        for o in others:
            dv = self.rng.choice(self.pools.values)
            ds = self.rng.choice(self.pools.sources)
            facts.append(("distractor", o, dv, ds))
        self.rng.shuffle(facts)

        # place facts spread across the body with filler between
        gap_each = max(1, (target_len // max(1, len(facts))) // 8)
        for kind, name, val, src in facts:
            emit(self._filler(gap_each))
            emit(["vendor", name, "valued", val, "recorded", "in", src, "<sep>"],
                 value_word=val, value_label=(1 if kind == "topic" else 0))
        emit(self._filler(2))

        # query about the topic entity
        q = ["what", "value", "for", "vendor", topic]
        toks = tok.encode(words) + [tok.id("<Q>")] + tok.encode(q) + [tok.id("<A>")]
        wl = wlabels + [-100] * (len(toks) - len(wlabels))  # ignore non-body positions
        ans_pos = len(toks) - 1
        ans_id = tok.id(topic_val)
        toks.append(ans_id)
        wl.append(-100)
        return PExample(tokens=toks, answer_pos=ans_pos, answer_id=ans_id,
                        write_labels=wl, task="pressure_topic",
                        meta={"n_candidates": len(facts), "topic": topic,
                              "len": len(words), "pressure_items": len(facts)},
                        source_id=tok.id(topic_src))


def generate_pressure(tok: Tokenizer, split: str, seed: int, n: int,
                      n_candidates: int, target_len: int = 128) -> List[PExample]:
    gen = PressureGenerator(tok, split, seed)
    return [gen.make(n_candidates=n_candidates, target_len=target_len) for _ in range(n)]
