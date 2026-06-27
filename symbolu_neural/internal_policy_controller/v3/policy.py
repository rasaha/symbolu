"""v3 policy translation — sentence-level classical Vritti (cognitive) vs phoneme/PSE
dynamic state (delivery). Each POLICY-DRIVING signal -> a DISTINCT axis (enforced by
the field-influence self-test).

  COGNITIVE / epistemic (from the sentence-level cognitive evaluator + ontology):
    classical_vritti.primary -> epistemic_stance      (pramana/viparyaya/vikalpa)
    classical_vritti.nidra   -> clarification_policy   (low-info / ask vs answer)
    classical_vritti.smrti   -> memory_policy          (memory provenance)
    kosha                    -> reasoning_style
    aspect_balance           -> caution
    guna_resonance           -> uncertainty_handling
    valence                  -> speculation_reduction
  DELIVERY / energy (phoneme/PSE):
    guna                     -> tone
    dynamic_state            -> delivery_pace
    (clarity is a fixed default, not claimed state-driven)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict
import copy

import numpy as np

from symbolu_core.formulas.guna_kosha_resonance import GUNA_NAMES, KOSHA_ORDER_5
from .symbolu_state import SymbolUState, DYNAMIC_STATES
from .cognitive_evaluator import PRIMARY_VRITTI

ARMS = ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
        "random_policy", "shuffled_symbolu", "relabeled_symbolu", "symbolu"]
AXES = ["tone", "delivery_pace", "epistemic_stance", "clarification_policy",
        "memory_policy", "reasoning_style", "caution", "uncertainty_handling",
        "speculation_reduction", "clarity"]
COGNITIVE_AXES = ["epistemic_stance", "clarification_policy", "memory_policy",
                  "reasoning_style", "caution", "uncertainty_handling", "speculation_reduction"]
DELIVERY_AXES = ["tone", "delivery_pace", "clarity"]

_TONE = {"sattva": "calm and clear", "rajas": "direct and energetic",
         "tamas": "grounded and measured"}
_PACE = {"INERTIA": "slow, minimal, stabilizing", "ACTIVATION": "elaborative and explanatory",
         "OSCILLATION": "iterative and self-checking", "TENSION": "concise and focused",
         "RELEASE": "closing and integrative"}
_STANCE = {"pramana": "grounded and direct: assert only verifiable, evidence-based conclusions",
           "viparyaya": "corrective: flag contradictions/false certainty and avoid overclaiming",
           "vikalpa": "clearly label speculation as speculation; do not present it as fact"}
_CLARIFY = {True: "the draft is low-information/evasive — ask a clarifying question instead of pretending to answer",
            False: "answer directly; no clarification needed"}
_MEMORY = {True: "the draft relies on remembered/prior context — state that provenance and flag recall uncertainty",
           False: "no memory reliance; do not invent prior context"}
_REASONING = {"annamaya": "concrete and practical", "pranamaya": "energetic and brisk",
              "manomaya": "balanced and reflective", "vijnanamaya": "analytical and rigorous",
              "anandamaya": "holistic and integrative"}
_VALENCE_SPEC = {"binding": "high", "mixed": "medium", "liberating": "low"}


@dataclass
class PolicySpec:
    tone: str
    delivery_pace: str
    epistemic_stance: str
    clarification_policy: str
    memory_policy: str
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
                f"- Clarification: {self.clarification_policy}.\n"
                f"- Memory: {self.memory_policy}.\n"
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
    cv = state.classical_vritti
    guna_top = max(state.guna, key=state.guna.get)
    dyn_top = max(state.dynamic_state, key=state.dynamic_state.get)
    kosha_top = max(state.kosha, key=state.kosha.get)
    caution = ("high" if state.aspect_balance < 0.90 else
               ("medium" if state.aspect_balance < 0.97 else "low"))
    uncertainty = ("acknowledge uncertainty explicitly" if state.guna_resonance < 0.85
                   else "state conclusions plainly")
    return PolicySpec(
        tone=_TONE[guna_top],
        delivery_pace=_PACE[dyn_top],
        epistemic_stance=_STANCE[cv["primary"]],
        clarification_policy=_CLARIFY[bool(cv["nidra"])],
        memory_policy=_MEMORY[bool(cv["smrti"])],
        reasoning_style=_REASONING[kosha_top],
        caution=caution,
        uncertainty_handling=uncertainty,
        speculation_reduction=_VALENCE_SPEC.get(state.valence, "medium"),
        source="symbolu")


def _relabel_state(state: SymbolUState, seed: int = 0) -> SymbolUState:
    """Independently permute every consumed categorical signal: classical_vritti
    primary (3-way), the nidra & smrti flags (swap their effects), dynamic_state,
    guna, kosha, valence."""
    s = copy.copy(state)

    def permute(d, keys, salt):
        r = np.random.default_rng(seed + salt)
        p = list(keys); r.shuffle(p)
        vals = list(d.values())
        return {p[i]: vals[i] for i in range(len(keys))}

    # classical primary: map the real primary to a permuted label
    r = np.random.default_rng(seed + 1)
    perm = list(PRIMARY_VRITTI); r.shuffle(perm)
    primary_map = {PRIMARY_VRITTI[i]: perm[i] for i in range(len(PRIMARY_VRITTI))}
    cv = dict(state.classical_vritti)
    cv = {"primary": primary_map[cv["primary"]],
          "nidra": cv["smrti"], "smrti": cv["nidra"],   # swap the two flags' effects
          **{k: v for k, v in cv.items() if k not in ("primary", "nidra", "smrti")}}
    s.classical_vritti = cv
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
        delivery_pace="concise and focused",
        epistemic_stance=_STANCE["pramana"],
        clarification_policy=_CLARIFY[False], memory_policy=_MEMORY[False],
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
        clarification_policy=rng.choice(list(_CLARIFY.values())),
        memory_policy=rng.choice(list(_MEMORY.values())),
        reasoning_style=rng.choice(list(_REASONING.values())),
        caution=rng.choice(lv),
        uncertainty_handling=rng.choice(["acknowledge uncertainty explicitly",
                                         "state conclusions plainly"]),
        speculation_reduction=rng.choice(lv), source="random")


_FIXED_NL_POLICY = PolicySpec(
    tone="calm and clear", delivery_pace="concise and focused",
    epistemic_stance=_STANCE["pramana"], clarification_policy=_CLARIFY[False],
    memory_policy=_MEMORY[False], reasoning_style="balanced and reflective",
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
