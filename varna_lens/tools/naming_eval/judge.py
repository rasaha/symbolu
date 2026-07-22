#!/usr/bin/env python3
"""Pluggable generation + judging adapter for the naming evaluation.

LLM-backed when an API key is available; otherwise every LLM-dependent call returns an explicit
UNAVAILABLE sentinel so the runner records "not measured" instead of fabricating data. Blind
randomization utilities live here so arm labels are hidden from any judge.

This module NEVER fabricates candidate names or scores. If no model is reachable, the outcome metrics
(candidate quality, explanation quality, portfolio consistency of generated names) are simply not
produced — consistent with the task's evidence discipline.
"""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

_VL = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_VL))

UNAVAILABLE = {"status": "LLM_UNAVAILABLE",
               "reason": "no API key / model reachable in this environment; outcome metrics require a "
                         "live LLM for generation and blinded judging and were not run (not fabricated)."}


def llm_available() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import reflect
        return reflect.call_llm("Reply with the single token: OK") is not None
    except Exception:
        return False


def generate(prompt: str, model: str = "claude-opus-4-8"):
    """Generate candidate names for an arm prompt. Returns a list[str] or UNAVAILABLE."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return UNAVAILABLE
    try:
        import reflect
        out = reflect.call_llm(prompt)
        if not out:
            return UNAVAILABLE
        return [ln.strip(" -•\t") for ln in out.splitlines() if ln.strip()]
    except Exception as e:  # noqa: BLE001
        return {"status": "LLM_ERROR", "reason": str(e)[:200]}


JUDGE_RUBRIC = ["memorability", "pronounceability", "distinctiveness", "perceived_professionalism",
                "verbal_identity", "fit_to_brief"]


def judge(brief: str, candidates, models=("claude-opus-4-8",)):
    """Blind-score a candidate set on JUDGE_RUBRIC (1-5) with one or more models. Returns per-model
    scores or UNAVAILABLE. The caller passes candidates with arm labels already stripped/shuffled."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return UNAVAILABLE
    import json
    import reflect
    results = {}
    for m in models:
        prompt = ("Score each naming option 1-5 on: " + ", ".join(JUDGE_RUBRIC) +
                  ". Return JSON {option: {metric: score}}. You are blind to how each option was made.\n\n"
                  f"BRIEF: {brief}\nOPTIONS:\n" + "\n".join(f"- {c}" for c in candidates))
        try:
            out = reflect.call_llm(prompt)
            results[m] = json.loads(out) if out else UNAVAILABLE
        except Exception as e:  # noqa: BLE001
            results[m] = {"status": "LLM_ERROR", "reason": str(e)[:200]}
    return results


def blind_shuffle(arm_outputs: dict, salt: str):
    """Deterministically hide arm identity: map each arm's output to an opaque label, in a
    salt-derived order. Returns (labelled:list[(label, output)], label_to_arm:dict)."""
    arms = sorted(arm_outputs)
    order = sorted(arms, key=lambda a: hashlib.sha256((salt + a).encode()).hexdigest())
    labels = [f"opt_{i+1}" for i in range(len(order))]
    labelled = [(labels[i], arm_outputs[order[i]]) for i in range(len(order))]
    label_to_arm = {labels[i]: order[i] for i in range(len(order))}
    return labelled, label_to_arm
