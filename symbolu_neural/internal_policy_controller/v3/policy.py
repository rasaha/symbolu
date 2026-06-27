"""v3 policy translation — classical_vritti (cognitive) vs dynamic_state (delivery).

Each POLICY-DRIVING Symbol-U variable -> a DISTINCT policy axis (enforced by the
field-influence self-test). The two vritti senses now drive SEPARATE axis families:

  COGNITIVE / epistemic:
    classical_vritti -> epistemic_stance   (pramana/viparyaya/vikalpa/smrti/nidra)
    kosha            -> reasoning_style
    aspect_balance   -> caution
    guna_resonance   -> uncertainty_handling
    valence          -> speculation_reduction
  DELIVERY / energy:
    guna             -> tone
    dynamic_state    -> delivery_pace       (inertia/activation/oscillation/tension/release)
    (clarity is a fixed default, not claimed state-driven)

Controls: relabeled independently permutes the LABELS of classical_vritti,
dynamic_state, guna, kosha AND valence; shuffled uses a different draft's state.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict
import copy

import numpy as np

from symbolu_core.formulas.guna_kosha_resonance import GUNA_NAMES, KOSHA_ORDER_5
from .symbolu_state import SymbolUState, CLASSICAL_VRITTI, DYNAMIC_STATES

ARMS = ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
        "random_policy", "shuffled_symbolu", "relabeled_symbolu", "symbolu"]
AXES = ["tone", "delivery_pace", "epistemic_stance", "reasoning_style", "caution",
        "uncertainty_handling", "speculation_reduction", "clarity"]
COGNITIVE_AXES = ["epistemic_stance", "reasoning_style", "caution",
                  "uncertainty_handling", "speculation_reduction"]
DELIVERY_AXES = ["tone", "delivery_pace", "clarity"]

_TONE = {"sattva": "calm and clear", "rajas": "direct and energetic",
         "tamas": "grounded and measured"}
_PACE = {"INERTIA": "slow, minimal, stabilizing", "ACTIVATION": "elaborative and explanatory",
         "OSCILLATION": "iterative and self-checking", "TENSION": "concise and focused",
         "RELEASE": "closing and integrative"}
_STANCE = {"pramana": "grounded and direct (assert valid conclusions)",
           "viparyaya": "corrective and careful (flag likely misperceptions, verify claims)",
           "vikalpa": "imaginative but clearly labeled as speculation",
           "smrti": "recall and contextualize prior/known information",
           "nidra": "low-confidence: keep minimal and ask to clarify"}
_REASONING = {"annamaya": "concrete and practical", "pranamaya": "energetic and brisk",
              "manomaya": "balanced and reflective", "vijnanamaya": "analytical and rigorous",
              "anandamaya": "holistic and integrative"}
_VALENCE_SPEC = {"binding": "high", "mixed": "medium", "liberating": "low"}


@dataclass
class PolicySpec:
    tone: str
    delivery_pace: str
    epistemic_stance: str
    reasoning_style: str
    caution: str
    uncertainty_handling: str
    speculation_reduction: str
    clarity: str = "high"
    source: str = ""

    def render(self) -> str:
        return ("Revise your draft to follow this response policy, preserving all "
                "factual content and meaning.\n"
                "Cognitive policy:\n"
                f"- Epistemic stance: {self.epistemic_stance}.\n"
                f"- Reasoning style: {self.reasoning_style}.\n"
                f"- Caution / hedging: {self.caution} (only where genuinely warranted).\n"
                f"- Uncertainty: {self.uncertainty_handling}.\n"
                f"- Speculation: {self.speculation_reduction} reduction of unfounded speculation.\n"
                "Delivery policy:\n"
                f"- Tone: {self.tone}.\n- Pace/elaboration: {self.delivery_pace}.\n"
                f"- Clarity: {self.clarity}.\nReturn only the revised answer.")

    def as_dict(self) -> Dict:
        return asdict(self)


def translate(state: SymbolUState) -> PolicySpec:
    guna_top = max(state.guna, key=state.guna.get)
    dyn_top = max(state.dynamic_state, key=state.dynamic_state.get)
    cv_top = max(state.classical_vritti, key=state.classical_vritti.get)
    kosha_top = max(state.kosha, key=state.kosha.get)
    caution = ("high" if state.aspect_balance < 0.90 else
               ("medium" if state.aspect_balance < 0.97 else "low"))
    uncertainty = ("acknowledge uncertainty explicitly" if state.guna_resonance < 0.85
                   else "state conclusions plainly")
    return PolicySpec(
        tone=_TONE[guna_top],
        delivery_pace=_PACE[dyn_top],
        epistemic_stance=_STANCE[cv_top],
        reasoning_style=_REASONING[kosha_top],
        caution=caution,
        uncertainty_handling=uncertainty,
        speculation_reduction=_VALENCE_SPEC.get(state.valence, "medium"),
        source="symbolu")


def _relabel_state(state: SymbolUState, seed: int = 0) -> SymbolUState:
    """Independently permute the LABELS of every consumed categorical ontology:
    classical_vritti, dynamic_state, guna, kosha, valence."""
    rng = np.random.default_rng(seed + 7)
    s = copy.copy(state)

    def permute(d, keys, salt):
        r = np.random.default_rng(seed + salt)
        p = list(keys); r.shuffle(p)
        vals = list(d.values())
        return {p[i]: vals[i] for i in range(len(keys))}

    s.classical_vritti = permute(state.classical_vritti, CLASSICAL_VRITTI, 1)
    s.dynamic_state = permute(state.dynamic_state, DYNAMIC_STATES, 2)
    s.guna = permute(state.guna, list(GUNA_NAMES), 3)
    s.kosha = permute(state.kosha, list(KOSHA_ORDER_5), 4)
    vmap = {"binding": "liberating", "liberating": "binding", "mixed": "mixed"}
    s.valence = vmap.get(state.valence, state.valence)
    return s


def _sentiment_policy(state: SymbolUState) -> PolicySpec:
    binding = state.valence == "binding"
    return PolicySpec(
        tone="calm and clear" if binding else "direct and energetic",
        delivery_pace="concise and focused", epistemic_stance="grounded and direct",
        reasoning_style="balanced and reflective",
        caution="high" if binding else "medium",
        uncertainty_handling="acknowledge uncertainty explicitly" if binding else "state conclusions plainly",
        speculation_reduction="high" if binding else "medium", source="sentiment")


def _random_policy(seed: int) -> PolicySpec:
    rng = np.random.default_rng(seed + 99)
    lv = ["low", "medium", "high"]
    return PolicySpec(
        tone=rng.choice(list(_TONE.values())),
        delivery_pace=rng.choice(list(_PACE.values())),
        epistemic_stance=rng.choice(list(_STANCE.values())),
        reasoning_style=rng.choice(list(_REASONING.values())),
        caution=rng.choice(lv),
        uncertainty_handling=rng.choice(["acknowledge uncertainty explicitly",
                                         "state conclusions plainly"]),
        speculation_reduction=rng.choice(lv), source="random")


_FIXED_NL_POLICY = PolicySpec(
    tone="calm and clear", delivery_pace="concise and focused",
    epistemic_stance="grounded and direct", reasoning_style="balanced and reflective",
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
