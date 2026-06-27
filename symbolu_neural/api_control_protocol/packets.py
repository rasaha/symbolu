"""Control-message builders for each pilot arm.

Each arm turns (target_axis) into a control message that is prepended to the user
prompt when calling the LLM. The arms isolate *what kind of control structure*
carries the steering:

  none             — no control (baseline)
  nl_instruction   — plain-English instruction only (ordinary prompting)
  symbolu_json     — JSON with symbolu_state ONLY (the ontology, no NL policy)
  hybrid           — JSON with symbolu_state + response_policy (state + NL translation)
  sentiment_json   — JSON with response_policy ONLY (actionable NL fields, no ontology)
  random_json      — structurally-valid JSON, random ontology + random policy
  shuffled_symbolu — symbolu_state values shuffled/mismatched, response_policy KEPT
                     correct (isolates: does the ontology's CONTENT matter, given a
                     correct policy?)

Key designed contrasts:
  symbolu_json vs nl_instruction   -> does the ontology beat plain prompting?
  hybrid vs sentiment_json         -> does adding the ontology help over policy-only?
  shuffled_symbolu vs hybrid       -> does the ontology's actual content matter?
  random_json vs everything        -> does any JSON structure help at all?
"""
from __future__ import annotations

import json
import random
from typing import Dict, List

from .ontology import (AXES, SYMBOLU_STATE, RESPONSE_POLICY, RANDOM_VOCAB)

ARMS = ["none", "nl_instruction", "symbolu_json", "hybrid",
        "sentiment_json", "random_json", "shuffled_symbolu"]


def _nl_from_policy(policy: dict) -> str:
    return (f"Respond in a {policy['tone']}, {policy['style']} tone. "
            f"Prefer {', '.join(policy['prefer'])}. "
            f"Avoid {', '.join(policy['avoid'])}.")


def _json_block(obj: dict) -> str:
    return "```json\n" + json.dumps(obj, indent=2) + "\n```"


def _shuffled_state(axis: str, rng: random.Random) -> dict:
    """Symbol-U state with values pulled from the WRONG axes (content corrupted)."""
    others = [a for a in AXES if a != axis]
    src = {k: SYMBOLU_STATE[rng.choice(others)][k] for k in SYMBOLU_STATE[axis]}
    return src


def _random_state(rng: random.Random) -> dict:
    return {
        "guna": rng.choice(RANDOM_VOCAB["guna"]),
        "vritti": rng.choice(RANDOM_VOCAB["vritti"]),
        "kosha": rng.choice(RANDOM_VOCAB["kosha"]),
        "aspect": rng.choice(RANDOM_VOCAB["aspect"]),
        "resonance": round(rng.random(), 2),
    }


def _random_policy(rng: random.Random) -> dict:
    a = rng.choice(AXES)
    return RESPONSE_POLICY[a]


def build(arm: str, axis: str, seed: int = 0) -> str:
    """Return the control message (prepended to the user prompt) for an arm/axis."""
    rng = random.Random(hash((arm, axis, seed)) & 0xFFFFFFFF)
    if arm == "none":
        return ""
    if arm == "nl_instruction":
        return _nl_from_policy(RESPONSE_POLICY[axis])
    if arm == "symbolu_json":
        return ("Use this Symbol-U cognitive state as your response policy:\n"
                + _json_block({"symbolu_state": SYMBOLU_STATE[axis]}))
    if arm == "hybrid":
        return ("Use this Symbol-U control packet as your response policy:\n"
                + _json_block({"symbolu_state": SYMBOLU_STATE[axis],
                               "response_policy": RESPONSE_POLICY[axis]}))
    if arm == "sentiment_json":
        return ("Use this response policy:\n"
                + _json_block({"response_policy": RESPONSE_POLICY[axis]}))
    if arm == "random_json":
        return ("Use this control packet as your response policy:\n"
                + _json_block({"symbolu_state": _random_state(rng),
                               "response_policy": _random_policy(rng)}))
    if arm == "shuffled_symbolu":
        return ("Use this Symbol-U control packet as your response policy:\n"
                + _json_block({"symbolu_state": _shuffled_state(axis, rng),
                               "response_policy": RESPONSE_POLICY[axis]}))
    raise ValueError(f"unknown arm {arm!r}")


def approx_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Marked approximate; no tokenizer here."""
    return max(1, round(len(text) / 4))
