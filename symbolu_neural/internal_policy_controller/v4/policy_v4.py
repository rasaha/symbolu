"""v4 high-fidelity translator: preserve the Symbol-U distributions + continuous values.

Contrast with v3 `policy.translate`, which read only argmaxes + 2 thresholds and emitted
canned phrases. v4 verbalizes:
  * dynamic_state / guna / kosha as their TOP-k components WITH probabilities (a blend,
    not a single winner) -> the distribution SHAPE survives;
  * aspect_balance / guna_resonance / kosha_resonance / valence_sign as the actual
    NUMBERS, graded continuously -> no 2-3 bucket collapse;
  * every component named by its Symbol-U concept -> permuting labels (relabel) rewrites
    most of the prompt, so the ontology-specificity test has real leverage.

Controls (draft_only/generic_refine/nl_policy/sentiment/random) are reused unchanged from
v3 — they are generic baselines whose fidelity is irrelevant. Only symbolu / shuffled /
relabeled use the v4 translator.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, List

import numpy as np

from ..v3.symbolu_state import SymbolUState, DYNAMIC_STATES
from ..v3.policy import (_sentiment_policy, _random_policy, _FIXED_NL_POLICY,
                         _relabel_state)
from ..v3.cognitive_evaluator import PRIMARY_VRITTI

ARMS = ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
        "random_policy", "shuffled_symbolu", "relabeled_symbolu", "symbolu"]

# Concept descriptions — what each ontology category MEANS for the response. Naming the
# concept (not just a generic phrase) is what makes relabel change the prompt.
_DYN_DESC = {"INERTIA": "steady, minimal, stabilizing delivery",
             "ACTIVATION": "expansive, elaborative delivery",
             "OSCILLATION": "iterative, self-checking delivery",
             "TENSION": "focused, concise, high-stakes delivery",
             "RELEASE": "resolving, integrative delivery"}
_GUNA_DESC = {"sattva": "calm, clear, balanced", "rajas": "active, direct, energetic",
              "tamas": "grounded, heavy, measured"}
_KOSHA_DESC = {"annamaya": "concrete/physical reasoning", "pranamaya": "energetic/process reasoning",
               "manomaya": "reflective/mental reasoning", "vijnanamaya": "analytical/discriminative reasoning",
               "anandamaya": "holistic/integrative reasoning"}
_STANCE = {"pramana": "grounded — assert only verifiable, evidence-based conclusions",
           "viparyaya": "corrective — flag contradictions/false certainty; do not overclaim",
           "vikalpa": "label speculation AS speculation; never present it as fact"}
_CLARIFY = {True: "draft is low-information/evasive — ask a clarifying question rather than pretend",
            False: "answer directly; no clarification needed"}
_MEMORY = {True: "draft leans on remembered/prior context — state that provenance and flag recall risk",
           False: "no memory reliance; do not invent prior context"}


def _blend(dist: Dict[str, float], desc: Dict[str, str], topk: int = 5,
           thresh: float = 0.05) -> str:
    """Verbalize a distribution as ALL non-trivial components, each as NAME (description)
    PROB. Including the raw ontology NAME (not just a generic description) and the full
    distribution is what makes a label scramble rewrite this text — every name and its
    description moves to a different probability."""
    items = [(k, v) for k, v in sorted(dist.items(), key=lambda kv: -kv[1]) if v >= thresh]
    if not items:
        items = [max(dist.items(), key=lambda kv: kv[1])]
    return "; ".join(f"{k} ({desc.get(k, k)}) {v:.0%}" for k, v in items[:topk])


def _graded(value: float, lo_txt: str, mid_txt: str, hi_txt: str,
            lo: float, hi: float, label: str, rng: str) -> str:
    """Carry the actual continuous NUMBER into the prompt, graded into nuance."""
    band = lo_txt if value < lo else (mid_txt if value < hi else hi_txt)
    return f"{label} {value:+.2f} on {rng} -> {band}"


@dataclass
class PolicySpecV4:
    pace: str
    tone: str
    reasoning: str
    epistemic: str
    clarification: str
    memory: str
    caution: str
    uncertainty: str
    coherence: str
    speculation: str
    source: str = "symbolu_v4"

    def render(self) -> str:
        return ("Revise the draft to follow this Symbol-U response policy, preserving "
                "all factual content and meaning.\n"
                f"- Delivery / motion (vritti mix): {self.pace}.\n"
                f"- Tone (guna mix): {self.tone}.\n"
                f"- Reasoning depth (kosha mix): {self.reasoning}.\n"
                f"- Epistemic stance: {self.epistemic}.\n"
                f"- Clarification: {self.clarification}.\n"
                f"- Memory: {self.memory}.\n"
                f"- Caution: {self.caution}.\n"
                f"- Uncertainty: {self.uncertainty}.\n"
                f"- Coherence: {self.coherence}.\n"
                f"- Speculation: {self.speculation}.\n"
                "Return only the revised answer.")

    def as_dict(self) -> Dict:
        return asdict(self)


def translate_v4(state: SymbolUState) -> PolicySpecV4:
    cv = state.classical_vritti
    sign = float(getattr(state, "valence_sign", 0.0))
    return PolicySpecV4(
        pace=_blend(state.dynamic_state, _DYN_DESC),
        tone=_blend(state.guna, _GUNA_DESC),
        reasoning=_blend(state.kosha, _KOSHA_DESC),
        epistemic=_STANCE[cv["primary"]],
        clarification=_CLARIFY[bool(cv["nidra"])],
        memory=_MEMORY[bool(cv["smrti"])],
        caution=_graded(state.aspect_balance,
                        "treat claims skeptically; hedge actively",
                        "hedge where evidence is thin",
                        "state conclusions with confidence",
                        0.85, 0.95, "sublimation balance", "[-1,+1]"),
        uncertainty=_graded(state.guna_resonance,
                            "acknowledge uncertainty explicitly and often",
                            "acknowledge uncertainty where it is real",
                            "state conclusions plainly",
                            0.70, 0.85, "guna resonance", "[0,1]"),
        coherence=_graded(float(state.kosha_resonance),
                          "structure carefully; the reasoning layers are not yet aligned",
                          "keep the through-line explicit",
                          "let the integrated structure carry the answer",
                          0.70, 0.85, "kosha resonance", "[0,1]"),
        speculation=(f"valence {state.valence} (sign {sign:+.2f}) -> "
                     + ("high reduction of unfounded speculation" if state.valence == "binding"
                        else "low reduction; openness is appropriate" if state.valence == "liberating"
                        else "medium reduction of unfounded speculation")),
        source="symbolu_v4")


def policy_for_arm_v4(arm, state, other_state, seed=0):
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
        return translate_v4(other_state), "policy"
    if arm == "relabeled_symbolu":
        return translate_v4(_relabel_state(state, seed)), "policy"
    if arm == "symbolu":
        return translate_v4(state), "policy"
    raise ValueError(arm)
