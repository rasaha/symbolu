#!/usr/bin/env python3
"""llm_judge_rubric.py — fixed-rubric judge PROMPT + strict-JSON PARSER for the weak LLM-judge eval.
Doc: docs/CG_TRAINING_LLM_JUDGE_EVAL.md.

LLM-judge labels are a WEAK SCREENING signal, NOT human labels. This module only builds the judge prompt
and parses/validates strict JSON. It imports nothing from the C×R×S runtime, Kosha/Guna/Vritti, or the
Phase-3 audit, and changes none of them.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

RUBRIC_VERSION = "v1"

# 8 binary rubric fields (also the agreement fields) + 2 numeric + optional reason
BINARY_FIELDS = ("primary_frame_correct", "rejected_domain_leak", "secondary_overpromotion",
                 "factuality_preserved", "generic_low_signal", "overconfident_or_overstated",
                 "answer_acceptable", "rewrite_needed")
NUMERIC_FIELDS = ("must_include_recall_score", "clarity_usefulness_score")
REQUIRED_FIELDS = BINARY_FIELDS + NUMERIC_FIELDS
ALL_FIELDS = REQUIRED_FIELDS + ("short_reason",)

# fields that must NEVER appear in the judge prompt (arm/model identity must be hidden)
_IDENTITY_KEYS = ("arm", "model", "lora", "metadata", "split", "judge", "source")

_RUBRIC_INSTRUCTIONS = """\
Return STRICT JSON ONLY — no prose, no markdown fences, no leading/trailing text. Exactly these fields:
{
  "primary_frame_correct": true|false,   // answer mainly stays inside the expected PRIMARY frame
  "rejected_domain_leak": true|false,    // answer introduces/promotes ANY rejected frame (MAJOR failure)
  "secondary_overpromotion": true|false, // a secondary frame dominates over the primary frame
  "factuality_preserved": true|false,    // factually plausible, no unsupported claims
  "must_include_recall_score": 0.0..1.0, // fraction of required concepts actually included
  "clarity_usefulness_score": 1..5,      // 1=useless, 5=clear and useful
  "generic_low_signal": true|false,      // vague/generic/dodges the question
  "overconfident_or_overstated": true|false, // claims beyond the evidence/context
  "answer_acceptable": true|false,       // good enough WITHOUT a rewrite
  "rewrite_needed": true|false,          // rewrite due to frame failure, rejected-domain leak,
                                         // factuality issue, severe incompleteness, or low usefulness
  "short_reason": "one sentence"
}
Rules:
- Judge SEMANTIC-FRAME correctness, not fluency. Do NOT reward fluent prose that violates the frame.
- Do NOT punish a concise answer unless it OMITS required must-include content.
- Rejected-domain leakage is a MAJOR failure: if present, rejected_domain_leak=true and usually
  rewrite_needed=true.
- If must-include concepts are not provided, set must_include_recall_score to 1.0.
"""


def _fmt_list(items: Optional[List[str]]) -> str:
    items = [str(x) for x in (items or []) if str(x).strip()]
    return ", ".join(items) if items else "(none provided)"


def build_judge_prompt(record: Dict, *, allow_missing_optional: bool = False) -> str:
    """Build the fixed judge prompt for ONE answer record. Arm/model identity is NEVER included.
    `record` must carry query/answer/primary_domain (validated upstream)."""
    q = record.get("query")
    ans = record.get("answer")
    primary = record.get("primary_domain")
    if not q or not ans or not primary:
        raise ValueError("build_judge_prompt requires non-empty query, answer, and primary_domain")
    return (
        "You are evaluating an answer for SEMANTIC-FRAME correctness. The model that produced the answer "
        "is unknown to you; judge only the answer.\n\n"
        f"User question:\n{q}\n\n"
        f"Expected primary semantic frame:\n{primary}\n\n"
        f"Allowed secondary frames:\n{_fmt_list(record.get('secondary_domains'))}\n\n"
        f"Rejected frames:\n{_fmt_list(record.get('rejected_domains'))}\n\n"
        f"Must-include concepts:\n{_fmt_list(record.get('must_include'))}\n\n"
        f"Answer to evaluate:\n{ans}\n\n"
        + _RUBRIC_INSTRUCTIONS
    )


def prompt_hides_identity(prompt: str, record: Dict) -> bool:
    """True iff no arm/model-identity value from the record leaked into the prompt."""
    low = prompt.lower()

    def _leaks(val) -> bool:
        # single/two-char arm codes (A/B/C/D) are not a meaningful substring-leak vector; only flag
        # identity-bearing tokens of length >= 3 (model names, "mistral_lora", split names, etc.)
        return isinstance(val, str) and len(val.strip()) >= 3 and val.strip().lower() in low

    for k in _IDENTITY_KEYS:
        v = record.get(k)
        if _leaks(v):
            return False
        if isinstance(v, dict) and any(_leaks(vv) for vv in v.values()):
            return False
    return True


# ---- strict JSON parsing -------------------------------------------------------------------------
def _coerce_bool(v) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)) and v in (0, 1):
        return bool(v)
    if isinstance(v, str) and v.strip().lower() in ("true", "false"):
        return v.strip().lower() == "true"
    return None


def _extract_json_block(raw: str) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if s.startswith("```"):                                   # tolerate ```json fences
        s = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", s).strip()
    try:
        json.loads(s)
        return s
    except Exception:                                         # noqa: BLE001
        pass
    i, j = s.find("{"), s.rfind("}")
    return s[i:j + 1] if (i != -1 and j != -1 and j > i) else None


def parse_judge_json(raw: str) -> Tuple[Optional[Dict], bool]:
    """Return (labels, valid). valid iff parseable AND all REQUIRED fields present with coercible types.
    Numeric scores are clamped; booleans coerced; short_reason passed through if present."""
    block = _extract_json_block(raw)
    if block is None:
        return None, False
    try:
        obj = json.loads(block)
    except Exception:                                         # noqa: BLE001
        return None, False
    if not isinstance(obj, dict):
        return None, False
    out: Dict = {}
    for f in BINARY_FIELDS:
        if f not in obj:
            return None, False
        b = _coerce_bool(obj[f])
        if b is None:
            return None, False
        out[f] = b
    # numeric
    try:
        mir = float(obj["must_include_recall_score"])
        clar = float(obj["clarity_usefulness_score"])
    except (KeyError, TypeError, ValueError):
        return None, False
    out["must_include_recall_score"] = round(min(1.0, max(0.0, mir)), 4)
    out["clarity_usefulness_score"] = int(min(5, max(1, round(clar))))
    out["short_reason"] = str(obj.get("short_reason", ""))[:300]
    return out, True
