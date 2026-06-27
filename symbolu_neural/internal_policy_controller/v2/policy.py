"""Explicit policy-translation layer + the 8 arms' policy generators.

This is the core v1 fix. v1 had a learned 5-label classifier and a hard-coded
dict. Here the controller is an EXPLICIT, label-semantic translation from the full
Symbol-U state to a structured policy with six axes (tone, caution, directness,
clarity, uncertainty_handling, speculation_reduction). Because the translation
reads the ontology LABELS (guna_top, valence, ...), the `relabeled` control — which
permutes those labels — actually changes the policy (v1's relabel was a linear
no-op tautology).

A policy renders to a natural-language instruction the rewrite-LLM follows.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List

import numpy as np

from symbolu_core.formulas.guna_kosha_resonance import GUNA_NAMES
from .symbolu_state import SymbolUState

ARMS = ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
        "random_policy", "shuffled_symbolu", "relabeled_symbolu", "symbolu"]

AXES = ["tone", "caution", "directness", "clarity",
        "uncertainty_handling", "speculation_reduction"]
LEVELS = ["low", "medium", "high"]
TONES = ["calm and clear", "direct and energetic", "grounded and measured"]


@dataclass
class PolicySpec:
    tone: str
    caution: str
    directness: str
    clarity: str
    uncertainty_handling: str
    speculation_reduction: str
    source: str = ""

    def render(self) -> str:
        return (
            "Revise your draft to follow this response policy, preserving all factual "
            "content and meaning:\n"
            f"- Tone: {self.tone}.\n"
            f"- Caution / hedging: {self.caution} (only where genuinely warranted).\n"
            f"- Directness: {self.directness}.\n"
            f"- Clarity: {self.clarity}.\n"
            f"- Uncertainty: {self.uncertainty_handling}.\n"
            f"- Speculation: {self.speculation_reduction} reduction of unfounded speculation.\n"
            "Return only the revised answer."
        )

    def as_dict(self) -> Dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# The real translation: Symbol-U state -> policy (label-semantic)
# --------------------------------------------------------------------------- #
def translate(state: SymbolUState) -> PolicySpec:
    guna_top = max(state.guna, key=state.guna.get)
    binding = state.valence == "binding"
    low_res = state.guna_resonance < 0.5
    tone = {"sattva": TONES[0], "rajas": TONES[1], "tamas": TONES[2]}[guna_top]
    caution = "high" if (guna_top == "tamas" or low_res or binding) else "medium"
    directness = "high" if guna_top == "rajas" else ("low" if guna_top == "tamas" else "medium")
    uncertainty = ("acknowledge uncertainty explicitly" if (binding or low_res)
                   else "state conclusions plainly")
    speculation = "high" if (guna_top == "tamas" or binding) else "medium"
    return PolicySpec(tone, caution, directness, "high", uncertainty, speculation,
                      source="symbolu")


def _relabel_state(state: SymbolUState, seed: int = 0) -> SymbolUState:
    """Permute guna labels (sattva<->rajas<->tamas) so the SAME magnitudes map to
    DIFFERENT ontology categories -> a genuine 'does the specific ontology matter?'
    control (unlike v1's basis-permutation no-op)."""
    import copy
    rng = np.random.default_rng(seed + 7)
    perm = list(GUNA_NAMES)
    rng.shuffle(perm)
    s = copy.copy(state)
    s.guna = {perm[i]: list(state.guna.values())[i] for i in range(len(GUNA_NAMES))}
    return s


def _sentiment_policy(state: SymbolUState) -> PolicySpec:
    """Policy from valence/sentiment ONLY (no guna/kosha ontology)."""
    binding = state.valence == "binding"
    return PolicySpec(
        tone="calm and clear" if binding else "direct and energetic",
        caution="high" if binding else "medium",
        directness="medium", clarity="high",
        uncertainty_handling="acknowledge uncertainty explicitly" if binding else "state conclusions plainly",
        speculation_reduction="high" if binding else "medium", source="sentiment")


def _random_policy(seed: int) -> PolicySpec:
    rng = np.random.default_rng(seed + 99)
    return PolicySpec(
        tone=TONES[rng.integers(0, 3)],
        caution=LEVELS[rng.integers(0, 3)],
        directness=LEVELS[rng.integers(0, 3)],
        clarity=LEVELS[rng.integers(0, 3)],
        uncertainty_handling=rng.choice(["acknowledge uncertainty explicitly",
                                         "state conclusions plainly"]),
        speculation_reduction=LEVELS[rng.integers(0, 3)], source="random")


_FIXED_NL_POLICY = PolicySpec(
    tone="calm and clear", caution="medium", directness="high", clarity="high",
    uncertainty_handling="acknowledge uncertainty where warranted",
    speculation_reduction="high", source="fixed_nl")


def policy_for_arm(arm: str, state: SymbolUState, other_state: SymbolUState,
                   seed: int = 0):
    """Return (policy_or_None, mode). mode in {none, self_refine, policy}."""
    if arm == "draft_only":
        return None, "none"
    if arm == "generic_refine":
        return None, "self_refine"
    if arm == "nl_policy":
        return _FIXED_NL_POLICY, "policy"
    if arm == "sentiment_critic":
        return _sentiment_policy(state), "policy"
    if arm == "random_policy":
        return _random_policy(seed), "policy"
    if arm == "shuffled_symbolu":
        return translate(other_state), "policy"      # state of a DIFFERENT draft
    if arm == "relabeled_symbolu":
        return translate(_relabel_state(state, seed)), "policy"
    if arm == "symbolu":
        return translate(state), "policy"
    raise ValueError(arm)


def policy_divergence(p_a: PolicySpec, p_b: PolicySpec) -> float:
    """Fraction of the 6 policy axes that differ (0=identical, 1=all differ)."""
    da, db = p_a.as_dict(), p_b.as_dict()
    return float(np.mean([da[k] != db[k] for k in AXES]))
