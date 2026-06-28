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


# --------------------------------------------------------------------------- #
# Pairwise A/B preference judge (the ceiling-effect fix).
#
# Absolute 1-5 rubric scoring saturates (every answer ~4.8/5), so it cannot detect
# small quality differences between arms. A FORCED CHOICE between two answers is far
# more sensitive. Two failure modes are controlled:
#   * POSITION BIAS — judges favor whichever answer is shown first/second. We evaluate
#     BOTH orders and average, so a constant position bias cancels exactly.
#   * INVALID JUDGE — if the judge can't tell good from bad at all, no verdict is
#     trustworthy. `judge_discriminates` is a validity gate that must pass first.
# --------------------------------------------------------------------------- #
_PAIR_SYSTEM = ("You are a careful, impartial judge comparing two answers to the SAME "
                "prompt. Choose the better one on correctness, usefulness, clarity, and "
                "appropriate caution. Do NOT reward length or verbosity. If they are "
                "genuinely equivalent, answer tie. Reply ONLY with JSON.")


def pairwise_prompt(user_prompt: str, ans_a: str, ans_b: str) -> str:
    return (f"USER PROMPT:\n{user_prompt}\n\nANSWER A:\n{ans_a}\n\nANSWER B:\n{ans_b}\n\n"
            "Which answer is better overall? "
            'Reply ONLY as JSON: {"winner":"A"|"B"|"tie"}.')


def _pick(llm, user_prompt: str, a: str, b: str) -> int:
    """+1 if the judge prefers A, -1 if B, 0 if tie/unparseable."""
    raw = llm.chat(_PAIR_SYSTEM, pairwise_prompt(user_prompt, a, b))
    try:
        obj = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        w = str(obj.get("winner", "tie")).strip().upper()
    except Exception:
        return 0
    return 1 if w.startswith("A") else -1 if w.startswith("B") else 0


def judge_pairwise(llm, user_prompt: str, ans_sym: str, ans_ctrl: str) -> float:
    """Position-debiased pairwise preference, symbolu vs control. Evaluates BOTH
    orders and averages so a constant position bias cancels. Returns a margin in
    [-1, 1]: >0 symbolu preferred, <0 control preferred, 0 net tie."""
    s1 = _pick(llm, user_prompt, ans_sym, ans_ctrl)        # sym is A -> +1 means sym better
    s2 = -_pick(llm, user_prompt, ans_ctrl, ans_sym)       # sym is B -> flip sign
    return (s1 + s2) / 2.0


def judge_discriminates(llm) -> float:
    """Validity gate: the judge must prefer a clearly-correct answer over a clearly
    evasive one. Returns the same [-1,1] margin; ~+1 = healthy, ~0 = the judge cannot
    tell good from bad and EVERY verdict from it is meaningless."""
    q = "What is the capital of France?"
    good = "The capital of France is Paris."
    bad = "That's a tricky one and could depend on many factors; it's hard to say."
    return judge_pairwise(llm, q, good, bad)
