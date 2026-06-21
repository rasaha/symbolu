"""prompts.py — prompt builders for the three Phase 2 arms + post-check.

Arm A (base) gives the model nothing. Arm B (framed) injects the FROZEN Phase 1 C×R×S frame. Arm C
post-checks the framed answer and, if it drifts, builds a rewrite prompt. The frame is a prompt-level
constraint + audit only — no logits, no hidden states, no Phase 1 scoring changes.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from . import rubric


def _fmt(xs: List[str]) -> str:
    return ", ".join(xs) if xs else "(none)"


def build_base_prompt(query: str, ex_id: str = "") -> str:
    tag = f"[[id:{ex_id}]]\n" if ex_id else ""
    return (f"{tag}Answer the user's question clearly and accurately.\n\n"
            f"User question:\n{query}\n")


def build_framed_prompt(query: str, primary: List[str], secondary: List[str],
                        rejected: List[str], ex_id: str = "") -> str:
    tag = f"[[id:{ex_id}]]\n" if ex_id else ""
    return (
        f"{tag}CSR/C×R×S semantic-frame analysis:\n\n"
        f"Primary domains:\n  {_fmt(primary)}\n\n"
        f"Secondary domains:\n  {_fmt(secondary)}\n\n"
        f"Rejected domains:\n  {_fmt(rejected)}\n\n"
        "Instructions:\n"
        "1. Use primary domains as the main answer frame.\n"
        "2. Mention secondary domains only if useful.\n"
        "3. Do not introduce rejected domains unless the user explicitly asks.\n"
        "4. Do not claim phonemes alone prove meaning.\n"
        "5. Preserve factual correctness.\n\n"
        f"User question:\n{query}\n")


def build_rewrite_prompt(answer: str, query: str, primary: List[str], secondary: List[str],
                         rejected: List[str], reasons: List[str], ex_id: str = "") -> str:
    tag = f"[[id:{ex_id}]]\n" if ex_id else ""
    return (
        f"{tag}Rewrite the answer to stay within the C×R×S frame.\n"
        f"Primary: {_fmt(primary)}\n"
        f"Secondary: {_fmt(secondary)}\n"
        f"Rejected: {_fmt(rejected)}\n"
        f"Problems to fix: {_fmt(reasons)}\n"
        "Do not claim phonemes alone prove meaning. Preserve factual correctness.\n\n"
        f"User question:\n{query}\n\n"
        f"Original answer:\n{answer}\n")


def postcheck_answer(answer: str, primary: List[str], secondary: List[str],
                     rejected: List[str]) -> Tuple[bool, List[str]]:
    """Audit a framed answer. Returns (needed_rewrite, reasons)."""
    reasons = []
    if primary and not rubric.mentioned_domains(answer, primary):
        reasons.append("does not use the expected primary domain")
    men_rej = rubric.mentioned_domains(answer, rejected)
    if men_rej:
        reasons.append(f"mentions rejected domain(s): {', '.join(sorted(men_rej))}")
    if rubric.has_phoneme_overreach(answer):
        reasons.append("makes a phoneme-overreach claim")
    if len((answer or "").split()) < 5:
        reasons.append("answer is empty or too short")
    return (len(reasons) > 0, reasons)
