"""kosha.py — OPTIONAL inference-time depth/readiness prompt-control layer for Conscious Generation.

C×R×S controls semantic-frame alignment (WHICH frame the answer stays in). Kosha controls inference-time
answer DEPTH/READINESS (at WHAT depth the answer is generated). Kosha is a DETERMINISTIC, rule-based
prompt-control layer — NOT a trained cognitive-state estimator, NOT hidden-state steering, NO model-weight
change, NOT wired into agent runtime. It is DISABLED by default and must not weaken C×R×S frame correctness
or rejected-domain avoidance. No Guna/Vritti/Bhava coupling.

Pipeline:  query → C×R×S frame selection → [Kosha depth selection] → prompt construction → LLM → audit
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class KoshaLevel(str, Enum):
    ANNAMAYA = "annamaya"        # surface / form / data
    PRANAMAYA = "pranamaya"      # action / urgency / practical next-step
    MANOMAYA = "manomaya"        # intent / emotion / context
    VIJNANAMAYA = "vijnanamaya"  # reasoning / discernment / tradeoff
    ANANDAMAYA = "anandamaya"    # synthesis / integration / coherence


@dataclass(frozen=True)
class KoshaSelection:
    level: KoshaLevel
    confidence: float
    reason: str
    prompt_modifier: str
    features: Dict[str, Any]
    secondary_level: Optional["KoshaLevel"] = None      # K1.1: blended-support level (or None)


# ---- prompt modifiers (always preserve the primary frame) ----------------------------------------
_MODIFIER = {
    KoshaLevel.ANNAMAYA: "Answer at a surface/data level: be concrete, concise, factual, and easy to "
                         "understand. Preserve the primary semantic frame.",
    KoshaLevel.PRANAMAYA: "Answer at an action/practical level: give clear steps, next actions, and "
                          "operational guidance while preserving the primary semantic frame.",
    KoshaLevel.MANOMAYA: "Answer at a context/intent level: address the user's concern, clarify "
                         "ambiguity, and keep the explanation grounded in the primary semantic frame.",
    KoshaLevel.VIJNANAMAYA: "Answer at a reasoning/discernment level: compare alternatives, state "
                            "assumptions, explain tradeoffs, and preserve the primary semantic frame.",
    KoshaLevel.ANANDAMAYA: "Answer at an integration/coherence level: synthesize the main principle, "
                           "connect the layers, and preserve the primary semantic frame without "
                           "becoming vague.",
}
_CAUTION = (" Be cautious, state limits, avoid unsupported certainty, and preserve factual grounding.")
# K1.1 blended-support phrases (appended after the primary modifier when a secondary level qualifies)
_SUPPORT = {
    KoshaLevel.ANNAMAYA: "keep it concrete and simple",
    KoshaLevel.PRANAMAYA: "give clear practical next steps",
    KoshaLevel.MANOMAYA: "acknowledge the user's concern",
    KoshaLevel.VIJNANAMAYA: "explain the reasoning and tradeoffs carefully",
    KoshaLevel.ANANDAMAYA: "connect it to the bigger picture",
}
# K1.1 pre-registered weights (frozen; NOT tuned against the eval set)
_W_BASE, _W_STRONG = 0.30, 0.45
_STRONG_CUES = frozenset({
    "i feel", "overwhelmed", "worried", "anxious", "scared", "panic",      # strong emotional distress
    "diagnos", "compare", "tradeoff", "trade-off", "should i",             # strong reasoning
    "step by step", "how do i", "how to",                                  # strong practical
    "synthesize", "big picture", "deeper meaning",                         # strong synthesis
})
_HIGH_STAKES_BONUS = 0.10            # added to VIJNANAMAYA (caution bias)
_SECONDARY_MIN = 0.35               # a second level must reach this to be a secondary
_PRIMARY_BLEND_MIN = 0.60           # primary this high + qualifying secondary -> blend
_BLEND_MARGIN = 0.30                # OR top-second closer than this (with second >= _SECONDARY_MIN)

# ---- deterministic cue lexicons (lowercased substring/word matches) ------------------------------
# explicit "dumb it down" requests FORCE ANNAMAYA (unless high-stakes)
_FORCE_ANNAMAYA = ("simple", "simply", "in simple terms", "5th grade", "fifth grade", "eli5",
                   "explain like i'm", "briefly", "keep it short", "short answer", "tl;dr")
_CUES = {
    KoshaLevel.ANNAMAYA: ("what is", "what's", "define", "definition", "meaning of the word",
                          "brief", "short", "summarize in one"),
    KoshaLevel.PRANAMAYA: ("steps", "step by step", "how do i", "how to", "how can i", "checklist",
                           "instructions", "what should i do", "guide me", "next step", "prepare for",
                           "set up", "configure", "perform", "implement"),
    KoshaLevel.MANOMAYA: ("worried", "worry", "anxious", "anxiety", "confused", "confusing", "scared",
                          "nervous", "overwhelmed", "stressed", "i feel", "what should i feel",
                          "reassure", "afraid", "panic"),
    KoshaLevel.VIJNANAMAYA: ("compare", "comparison", " vs ", "versus", "which is better", "should i",
                             "pros and cons", "tradeoff", "trade-off", "evaluate", "decide",
                             "diagnos", "which one", "better to", "review the", "architecture",
                             "design review", "analyze", "assess"),
    KoshaLevel.ANANDAMAYA: ("synthesize", "synthesis", "big picture", "deeper meaning", "principle",
                            "integrate", "unifying", "overall meaning", "essence", "philosoph",
                            "tie together", "connect the"),
}
# cue-conflict precedence (highest first)
_PRECEDENCE = (KoshaLevel.VIJNANAMAYA, KoshaLevel.PRANAMAYA, KoshaLevel.MANOMAYA,
               KoshaLevel.ANANDAMAYA, KoshaLevel.ANNAMAYA)
_HIGH_STAKES = ("medical", "medicine", "health", "diagnos", "symptom", "medication", "dose", "dosage",
                "legal", "lawsuit", "court", "contract", "liability", "tax", "invest", "financial",
                "loan", "mortgage", "insurance", "suicide", "emergency", "overdose", "prescription")


def _hint_to_level(hint: Optional[str]) -> Optional[KoshaLevel]:
    if not hint:
        return None
    h = hint.strip().lower()
    for lvl in KoshaLevel:
        if h == lvl.value or h == lvl.name.lower():
            return lvl
    alias = {"surface": KoshaLevel.ANNAMAYA, "data": KoshaLevel.ANNAMAYA,
             "action": KoshaLevel.PRANAMAYA, "practical": KoshaLevel.PRANAMAYA,
             "context": KoshaLevel.MANOMAYA, "intent": KoshaLevel.MANOMAYA,
             "reasoning": KoshaLevel.VIJNANAMAYA, "discernment": KoshaLevel.VIJNANAMAYA,
             "synthesis": KoshaLevel.ANANDAMAYA, "integration": KoshaLevel.ANANDAMAYA}
    return alias.get(h)


def _matches(q: str, needles) -> List[str]:
    return [n for n in needles if n in q]


def select_kosha_depth(
    query: str,
    *,
    primary_domain: Optional[str] = None,
    secondary_domains: Optional[List[str]] = None,
    rejected_domains: Optional[List[str]] = None,
    user_level_hint: Optional[str] = None,
    task_type_hint: Optional[str] = None,
) -> KoshaSelection:
    """Deterministic depth/readiness selection (K1.1: score-first, precedence-as-tiebreak). Precedence of
    *overrides*: explicit user_level_hint > task_type_hint > additive query-cue scores. Explicit
    'simple/5th grade' forces ANNAMAYA unless the query is high-stakes. Mixed cues yield a primary level
    plus an optional `secondary_level` and a blended modifier."""
    q = " " + (query or "").lower() + " "
    high_stakes = bool(_matches(q, _HIGH_STAKES))
    matched = {lvl: _matches(q, cues) for lvl, cues in _CUES.items()}
    force_hits = _matches(q, _FORCE_ANNAMAYA)
    hint_lvl = _hint_to_level(user_level_hint)
    task_lvl = _hint_to_level(task_type_hint)

    # ---- additive scores -------------------------------------------------------------------------
    def _cue_w(c):
        return _W_STRONG if c in _STRONG_CUES else _W_BASE
    scores = {lvl: round(sum(_cue_w(c) for c in matched[lvl]), 4) for lvl in KoshaLevel}
    if high_stakes:
        scores[KoshaLevel.VIJNANAMAYA] = round(scores[KoshaLevel.VIJNANAMAYA] + _HIGH_STAKES_BONUS, 4)

    secondary: Optional[KoshaLevel] = None
    blended = False

    if hint_lvl is not None:
        primary, source = hint_lvl, "user_level_hint"
        reason = f"Explicit user level hint: {hint_lvl.value}."
        scores = {lvl: (1.0 if lvl == hint_lvl else 0.0) for lvl in KoshaLevel}
    elif force_hits and not high_stakes:
        primary, source = KoshaLevel.ANNAMAYA, "force_simple"
        reason = f"Explicit simplicity request ({force_hits[0]!r}) → surface level."
        scores = {lvl: (1.0 if lvl == KoshaLevel.ANNAMAYA else 0.0) for lvl in KoshaLevel}
    else:
        if task_lvl is not None:
            scores[task_lvl] = round(scores[task_lvl] + 0.50, 4)
        # rank by score desc, precedence index as deterministic tie-breaker
        prec = {lvl: i for i, lvl in enumerate(_PRECEDENCE)}
        order = sorted(KoshaLevel, key=lambda l: (-scores[l], prec[l]))
        top, second = order[0], order[1]
        if scores[top] <= 0.0:
            primary, source = KoshaLevel.ANNAMAYA, "default"
            reason = "No strong depth cue; defaulting to surface level."
        else:
            primary = top
            source = "task_type_hint" if (task_lvl is not None and top == task_lvl
                                          and not matched[top]) else "additive_cue"
            reason = f"Top cue score {scores[top]} → {top.value}."
            if scores[second] >= _SECONDARY_MIN:
                secondary = second
                if (scores[top] >= _PRIMARY_BLEND_MIN and scores[second] >= _SECONDARY_MIN) \
                        or (scores[top] - scores[second] < _BLEND_MARGIN):
                    blended = True
                    reason = (f"{top.value} ({scores[top]}) outweighed {second.value} "
                              f"({scores[second]}); blended with {second.value} support.")

    # ---- prompt modifier (blend secondary if qualified; caution if high-stakes) -------------------
    modifier = _MODIFIER[primary]
    if blended and secondary is not None:
        modifier += f" Then also {_SUPPORT[secondary]}."
    if high_stakes:
        modifier += _CAUTION
        reason += " High-stakes terms detected → cautious framing added."

    # ---- confidence ------------------------------------------------------------------------------
    if source == "user_level_hint":
        conf = 0.95
    elif source in ("force_simple", "task_type_hint"):
        conf = 0.9
    elif source == "additive_cue":
        top_s = scores[primary]
        sec_s = scores[secondary] if secondary is not None else 0.0
        conf = min(0.95, max(0.5, 0.5 + 0.4 * (top_s - sec_s)))
    else:
        conf = 0.4

    features = {
        "scores": {lvl.value: scores[lvl] for lvl in KoshaLevel if scores[lvl] > 0},
        "matched_cues": {lvl.value: m for lvl, m in matched.items() if m},
        "force_simple_hits": force_hits, "high_stakes": high_stakes, "source": source,
        "blended": blended, "primary_domain": primary_domain,
    }
    return KoshaSelection(level=primary, confidence=round(conf, 3), reason=reason,
                          prompt_modifier=modifier, features=features, secondary_level=secondary)


# ---- prompt integration --------------------------------------------------------------------------
def depth_block(selection: KoshaSelection) -> str:
    """The text inserted AFTER the C×R×S frame instruction and BEFORE the user question."""
    return f"Depth/readiness instruction:\n{selection.prompt_modifier}\n\n"


def kosha_trace(selection: Optional[KoshaSelection], *, enabled: bool) -> Dict[str, Any]:
    """Generation-metadata trace. NO Guna/Vritti/Bhava fields."""
    if not enabled or selection is None:
        return {"enabled": False}
    return {"enabled": True, "level": selection.level.value,
            "secondary_level": selection.secondary_level.value if selection.secondary_level else None,
            "confidence": selection.confidence, "reason": selection.reason,
            "features": selection.features}
