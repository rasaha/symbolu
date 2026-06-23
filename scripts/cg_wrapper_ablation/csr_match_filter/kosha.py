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
    """Deterministic depth/readiness selection. Precedence: explicit user_level_hint > task_type_hint >
    query cues. Explicit 'simple/5th grade' forces ANNAMAYA unless the query is high-stakes."""
    q = " " + (query or "").lower() + " "
    high_stakes = bool(_matches(q, _HIGH_STAKES))
    matched = {lvl: _matches(q, cues) for lvl, cues in _CUES.items()}
    force_hits = _matches(q, _FORCE_ANNAMAYA)

    source = "default"
    level: Optional[KoshaLevel] = None
    reason = ""

    hint_lvl = _hint_to_level(user_level_hint)
    task_lvl = _hint_to_level(task_type_hint)
    if hint_lvl is not None:
        level, source, reason = hint_lvl, "user_level_hint", f"Explicit user level hint: {hint_lvl.value}."
    elif force_hits and not high_stakes:
        level, source = KoshaLevel.ANNAMAYA, "force_simple"
        reason = f"Explicit simplicity request ({force_hits[0]!r}) → surface level."
    elif task_lvl is not None:
        level, source, reason = task_lvl, "task_type_hint", f"Task-type hint: {task_lvl.value}."
    else:
        for lvl in _PRECEDENCE:                          # highest-precedence matched cue wins
            if matched[lvl]:
                level, source = lvl, "query_cue"
                reason = f"Query cue(s) {matched[lvl]} → {lvl.value}."
                break
        if level is None:
            level = KoshaLevel.ANNAMAYA                  # safe minimal-intervention default
            reason = "No strong depth cue; defaulting to surface level."

    # confidence: hints are high; forced/cue scale with evidence; default is low
    if source in ("user_level_hint",):
        conf = 0.95
    elif source in ("force_simple", "task_type_hint"):
        conf = 0.9
    elif source == "query_cue":
        conf = min(0.95, 0.6 + 0.1 * len(matched[level]))
    else:
        conf = 0.4

    modifier = _MODIFIER[level] + (_CAUTION if high_stakes else "")
    features = {
        "matched_cues": {lvl.value: m for lvl, m in matched.items() if m},
        "force_simple_hits": force_hits, "high_stakes": high_stakes, "source": source,
        "primary_domain": primary_domain,
    }
    if high_stakes:
        reason += " High-stakes terms detected → cautious framing added."
    return KoshaSelection(level=level, confidence=round(conf, 3), reason=reason,
                          prompt_modifier=modifier, features=features)


# ---- prompt integration --------------------------------------------------------------------------
def depth_block(selection: KoshaSelection) -> str:
    """The text inserted AFTER the C×R×S frame instruction and BEFORE the user question."""
    return f"Depth/readiness instruction:\n{selection.prompt_modifier}\n\n"


def kosha_trace(selection: Optional[KoshaSelection], *, enabled: bool) -> Dict[str, Any]:
    """Generation-metadata trace. NO Guna/Vritti/Bhava fields."""
    if not enabled or selection is None:
        return {"enabled": False}
    return {"enabled": True, "level": selection.level.value, "confidence": selection.confidence,
            "reason": selection.reason, "features": selection.features}
