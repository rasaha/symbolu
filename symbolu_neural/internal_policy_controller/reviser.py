"""Shared deterministic reviser: apply a revision policy to a draft.

The SAME reviser is used for every arm, so any difference in final-answer quality
traces to the POLICY the critic emitted (i.e. to critic quality), not to the
revision machinery. The reviser is transparent rule-based text surgery — a smoke
stand-in for an LLM rewrite (no pretrained model / API available offline).

A real-LLM reviser (anthropic/mistral) is wired for the hardened run but cannot
execute in this sandbox (no key); see report §commands.
"""
from __future__ import annotations

import re
from typing import List

from .drafts import SPECULATIVE, ESCALATED, FILLER, VAGUE

_REPLACE = {
    "reduce_speculation": SPECULATIVE + ["but i could be wrong", "it might be that"],
    "de_escalate": ESCALATED + ["absolute", "total"],
    "be_concise": FILLER,
    "be_direct": VAGUE,
    "noop": [],
}


def revise(draft: str, policy: str) -> str:
    """Remove the phrases the policy targets; tidy whitespace/punctuation."""
    out = draft
    for phrase in _REPLACE.get(policy, []):
        out = re.sub(re.escape(phrase), "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,.])", r"\1", out)
    out = re.sub(r"(,\s*){2,}", ", ", out)
    out = re.sub(r"^[\s,.-]+", "", out)
    return out.strip()


# --- optional real-LLM reviser (wired, needs API key) ---------------------- #
class LLMReviser:
    def __init__(self, backend: str = "anthropic", model: str = None):
        from symbolu_neural.api_control_protocol.llm import get_llm
        self.llm = get_llm(backend, model)

    def revise(self, draft: str, nl_policy: str) -> str:
        prompt = (f"Revise the draft to follow this policy: {nl_policy}\n"
                  f"Keep the meaning. Return only the revised text.\n\nDRAFT:\n{draft}")
        return self.llm.generate("", prompt)
