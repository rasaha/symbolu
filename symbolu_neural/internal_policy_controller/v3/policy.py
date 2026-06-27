"""v3 policy translation — every POLICY-DRIVING Symbol-U variable -> a DISTINCT axis.

Wiring (each state variable influences at least one policy axis; enforced by the
field-influence self-test in tests/):
  guna           -> tone
  vritti         -> directness
  kosha          -> reasoning_style
  aspect_balance -> caution
  guna_resonance -> uncertainty_handling
  valence        -> speculation_reduction
  (clarity is a fixed good-practice default, explicitly NOT claimed state-driven.)

Controls: relabeled permutes the LABELS of guna, kosha AND valence (every consumed
ontology category — fixing v2's guna-only relabel). shuffled uses a different
draft's state. random/sentiment/nl as before.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List
import copy

import numpy as np

from symbolu_core.formulas.guna_kosha_resonance import GUNA_NAMES, KOSHA_ORDER_5
from .symbolu_state import SymbolUState

ARMS = ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
        "random_policy", "shuffled_symbolu", "relabeled_symbolu", "symbolu"]
AXES = ["tone", "directness", "reasoning_style", "caution",
        "uncertainty_handling", "speculation_reduction", "clarity"]

_TONE = {"sattva": "calm and clear", "rajas": "direct and energetic",
         "tamas": "grounded and measured"}
_REASONING = {"annamaya": "concrete and practical", "pranamaya": "energetic and brisk",
              "manomaya": "balanced and reflective", "vijnanamaya": "analytical and rigorous",
              "anandamaya": "holistic and integrative"}
_VALENCE_SPEC = {"binding": "high", "mixed": "medium", "liberating": "low"}


@dataclass
class PolicySpec:
    tone: str
    directness: str
    reasoning_style: str
    caution: str
    uncertainty_handling: str
    speculation_reduction: str
    clarity: str = "high"
    source: str = ""

    def render(self) -> str:
        return ("Revise your draft to follow this response policy, preserving all "
                "factual content and meaning:\n"
                f"- Tone: {self.tone}.\n- Directness: {self.directness}.\n"
                f"- Reasoning style: {self.reasoning_style}.\n"
                f"- Caution / hedging: {self.caution} (only where genuinely warranted).\n"
                f"- Uncertainty: {self.uncertainty_handling}.\n"
                f"- Speculation: {self.speculation_reduction} reduction of unfounded speculation.\n"
                f"- Clarity: {self.clarity}.\nReturn only the revised answer.")

    def as_dict(self) -> Dict:
        return asdict(self)


def translate(state: SymbolUState) -> PolicySpec:
    guna_top = max(state.guna, key=state.guna.get)
    kosha_top = max(state.kosha, key=state.kosha.get)
    active = state.vritti.get("ACTIVATION", 0) + state.vritti.get("OSCILLATION", 0)
    inert = state.vritti.get("INERTIA", 0) + state.vritti.get("TENSION", 0)
    directness = "high" if active > 0.55 else ("low" if inert > 0.55 else "medium")
    # aspect_balance is weakly discriminative (empirical range ~0.79-1.0, sublimate-
    # leaning); thresholds calibrated to that range so caution actually varies.
    caution = ("high" if state.aspect_balance < 0.90 else
               ("medium" if state.aspect_balance < 0.97 else "low"))
    uncertainty = ("acknowledge uncertainty explicitly" if state.guna_resonance < 0.85
                   else "state conclusions plainly")
    return PolicySpec(
        tone=_TONE[guna_top], directness=directness,
        reasoning_style=_REASONING[kosha_top], caution=caution,
        uncertainty_handling=uncertainty,
        speculation_reduction=_VALENCE_SPEC.get(state.valence, "medium"),
        source="symbolu")


def _relabel_state(state: SymbolUState, seed: int = 0) -> SymbolUState:
    """Permute the LABELS of every consumed ontology category (guna, kosha, valence)."""
    rng = np.random.default_rng(seed + 7)
    s = copy.copy(state)
    gp = list(GUNA_NAMES); rng.shuffle(gp)
    s.guna = {gp[i]: list(state.guna.values())[i] for i in range(len(GUNA_NAMES))}
    kp = list(KOSHA_ORDER_5); rng.shuffle(kp)
    s.kosha = {kp[i]: list(state.kosha.values())[i] for i in range(len(KOSHA_ORDER_5))}
    vmap = {"binding": "liberating", "liberating": "binding", "mixed": "mixed"}
    s.valence = vmap.get(state.valence, state.valence)
    return s


def _sentiment_policy(state: SymbolUState) -> PolicySpec:
    binding = state.valence == "binding"
    return PolicySpec(
        tone="calm and clear" if binding else "direct and energetic",
        directness="medium", reasoning_style="balanced and reflective",
        caution="high" if binding else "medium",
        uncertainty_handling="acknowledge uncertainty explicitly" if binding else "state conclusions plainly",
        speculation_reduction="high" if binding else "medium", source="sentiment")


def _random_policy(seed: int) -> PolicySpec:
    rng = np.random.default_rng(seed + 99)
    lv = ["low", "medium", "high"]
    return PolicySpec(
        tone=rng.choice(list(_TONE.values())),
        directness=rng.choice(lv), reasoning_style=rng.choice(list(_REASONING.values())),
        caution=rng.choice(lv),
        uncertainty_handling=rng.choice(["acknowledge uncertainty explicitly",
                                         "state conclusions plainly"]),
        speculation_reduction=rng.choice(lv), source="random")


_FIXED_NL_POLICY = PolicySpec(
    tone="calm and clear", directness="high", reasoning_style="balanced and reflective",
    caution="medium", uncertainty_handling="acknowledge uncertainty where warranted",
    speculation_reduction="high", source="fixed_nl")


def policy_for_arm(arm, state, other_state, seed=0):
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
        return translate(other_state), "policy"
    if arm == "relabeled_symbolu":
        return translate(_relabel_state(state, seed)), "policy"
    if arm == "symbolu":
        return translate(state), "policy"
    raise ValueError(arm)


def policy_divergence(a: PolicySpec, b: PolicySpec) -> float:
    da, db = a.as_dict(), b.as_dict()
    return float(np.mean([da[k] != db[k] for k in AXES]))
