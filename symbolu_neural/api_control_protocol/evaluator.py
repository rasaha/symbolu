"""Offline + judge evaluators for the API control-protocol pilot.

Offline (assumption-light, runnable here):
- `tone_adherence` : does the output use target-axis tone words > other axes?
  (a transparent lexicon proxy; PROXY-ONLY, not a substitute for human/LLM judge)
- token cost        : control-message tokens per arm (real practical cost of JSON)
- consistency       : variance of adherence across prompts
- paraphrase stability : does adherence survive a paraphrased prompt?

LLM-judge (needs API): `JudgeAdapter` rates tone-match / clarity / fluency 1-5.
Wired but requires ANTHROPIC_API_KEY; not runnable in this sandbox.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .ontology import AXES, TONE_LEXICON


def tone_scores(text: str) -> Dict[str, float]:
    t = text.lower()
    raw = {a: sum(1 for w in TONE_LEXICON[a] if w in t) for a in AXES}
    s = sum(raw.values())
    if s == 0:
        return {a: 1.0 / len(AXES) for a in AXES}
    return {a: raw[a] / s for a in AXES}


def tone_adherence(text: str, target: str) -> float:
    sc = tone_scores(text)
    return sc[target] - np.mean([sc[a] for a in AXES if a != target])


def hit(text: str, target: str) -> int:
    sc = tone_scores(text)
    return int(max(sc, key=sc.get) == target and sc[target] > 1.0 / len(AXES))


class JudgeAdapter:
    """LLM-as-judge (needs API). Returns 1-5 ratings; not runnable offline here."""

    def __init__(self, llm):
        self.llm = llm

    def rate(self, output: str, target: str) -> Dict[str, int]:
        import json
        q = (f"Rate the following text for how well it matches a '{target}' tone, "
             f"its clarity, and its fluency, each 1-5. Reply ONLY as JSON "
             f'{{"tone_match":N,"clarity":N,"fluency":N}}.\n\nTEXT:\n{output}')
        resp = self.llm.generate("", q)
        try:
            return json.loads(resp[resp.index("{"): resp.rindex("}") + 1])
        except Exception:
            return {"tone_match": 0, "clarity": 0, "fluency": 0}
