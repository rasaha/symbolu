"""Independent LLM-as-judge with a human-reviewable rubric (the v1-eval fix).

No keyword markers, no regex, no oracle lexicon. The judge LLM reads the user
prompt, the draft, and the final answer, and scores the FINAL on a 1-5 rubric plus
a draft-vs-final preference. A separate model/call from the generator is preferred.
Requires a real LLM; the mock judge returns neutral constants (NO verdict).
"""
from __future__ import annotations

import json
from typing import Dict

RUBRIC = ["clarity", "directness", "usefulness", "caution",
          "speculation_reduction", "escalation_reduction", "completeness",
          "meaning_preservation", "fluency"]

_SYSTEM = ("You are a careful, impartial evaluation judge. You score answers on a "
           "rubric. Be calibrated; do not reward verbosity. Reply ONLY with JSON.")


def judge_prompt(user_prompt: str, draft: str, final: str) -> str:
    keys = ", ".join(f'"{k}":N' for k in RUBRIC)
    return (
        f"USER PROMPT:\n{user_prompt}\n\nDRAFT ANSWER:\n{draft}\n\n"
        f"FINAL ANSWER:\n{final}\n\n"
        "Rate the FINAL answer 1-5 on each rubric axis (5=best). For "
        "'caution' rate APPROPRIATENESS of hedging (over- or under-hedging both "
        "score low). Also judge whether the FINAL is better than the DRAFT.\n"
        f"Reply ONLY as JSON: {{{keys}, \"prefer_final\":true|false}}."
    )


def judge(llm, user_prompt: str, draft: str, final: str) -> Dict:
    raw = llm.chat(_SYSTEM, judge_prompt(user_prompt, draft, final))
    try:
        obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except Exception:
        obj = {k: 0 for k in RUBRIC} | {"prefer_final": False}
    return obj
