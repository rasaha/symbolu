"""Structured output contract: deterministic serialize + strict parse. Torch-free.

Emitted/parsed form (fields frozen, order frozen):
  {"answer":"<outcome>"|null,"reasoning_path":["Type:id",...],"evidence_ids":["id",...],"status":"<STATUS>"}
The strict parser performs no silent repair and no constrained decoding; a malformed prediction is an
invalid structured output (counts against the structured-output-validity gate).
"""
from __future__ import annotations

import json

from .config import OUTPUT_FIELDS, STATUS_VALUES
from .schema_ext import ReasoningOutput, SchemaError


class OutputParseError(ValueError):
    """A model prediction that does not conform to the frozen output contract."""


def serialize_output(out: ReasoningOutput) -> str:
    payload = {
        "answer": out.answer,
        "reasoning_path": list(out.reasoning_path),
        "evidence_ids": list(out.evidence_ids),
        "status": out.status,
    }
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def parse_output(text: str) -> ReasoningOutput:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise OutputParseError("not valid JSON") from exc
    if not isinstance(payload, dict) or tuple(payload.keys()) != OUTPUT_FIELDS:
        raise OutputParseError("fields or field order do not match the frozen contract")
    answer = payload["answer"]
    if answer is not None and not isinstance(answer, str):
        raise OutputParseError("answer must be a string or null")
    rp = payload["reasoning_path"]
    ev = payload["evidence_ids"]
    if not isinstance(rp, list) or not all(isinstance(x, str) for x in rp):
        raise OutputParseError("reasoning_path must be a string array")
    if not isinstance(ev, list) or not all(isinstance(x, str) for x in ev):
        raise OutputParseError("evidence_ids must be a string array")
    status = payload["status"]
    if status not in STATUS_VALUES:
        raise OutputParseError("invalid status")
    return ReasoningOutput(answer=answer, reasoning_path=tuple(rp),
                           evidence_ids=tuple(ev), status=status)


def is_valid_output(text: str) -> bool:
    """True iff `text` parses under the frozen contract AND satisfies the schema caps (a syntactically
    well-formed output whose reasoning_path/evidence_ids exceed the caps is invalid, not an exception)."""
    try:
        parse_output(text)
        return True
    except (OutputParseError, SchemaError, ValueError, TypeError):
        return False
