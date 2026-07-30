"""
extraction.py — token-to-evidence extraction with bounded retries (RM1 §6, §7).

The real model returns a JSON array of provisional evidence proposals. This module parses that
generation deterministically and enforces the invariants the model is NOT trusted to guarantee:

    * JSON parseability;
    * required fields present;
    * relation in the bounded vocabulary;
    * **source_span is an exact substring of the permitted source document** (the model may not
      invent a span).

At most two attempts by default. The second attempt receives ONLY deterministic validator feedback
(parser errors, missing fields, invalid spans) — never the gold answer. Proposals that still fail
are handed on as REJECTED/QUARANTINED, never silently repaired.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..event_schema import RELATION_TYPES
from .prompts import build_extraction_prompt

_REL_SET = set(RELATION_TYPES)


@dataclass
class ExtractionAttempt:
    attempt: int
    prompt_hash: str
    raw_generation: str
    parse_ok: bool
    parse_error: str = ""
    n_items: int = 0
    n_valid_shape: int = 0
    feedback: str = ""


@dataclass
class ExtractionResult:
    provisional: List[Dict]                    # shape-valid proposals (spans verified as substrings)
    attempts: List[ExtractionAttempt] = field(default_factory=list)
    ok: bool = False


def _prompt_hash(p: str) -> str:
    import hashlib
    return hashlib.sha1(p.encode()).hexdigest()[:16]


def _extract_json_array(text: str) -> Tuple[Optional[list], str]:
    # tolerate prose around the JSON: take the first '[' to the matching last ']'
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        # maybe a single object
        s2, e2 = text.find("{"), text.rfind("}")
        if s2 != -1 and e2 > s2:
            try:
                return [json.loads(text[s2:e2 + 1])], ""
            except Exception as e:
                return None, f"json_object_parse_error: {e}"
        return None, "no_json_array_found"
    try:
        return json.loads(text[start:end + 1]), ""
    except Exception as e:
        return None, f"json_array_parse_error: {e}"


_REQUIRED_KEYS = ("subject", "relation", "object", "source_span", "source_document_id")


def _validate_shape(items: list, doc_by_id: Dict[str, str]) -> Tuple[List[Dict], List[str]]:
    good: List[Dict] = []
    errs: List[str] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(f"item {i}: not an object")
            continue
        missing = [k for k in _REQUIRED_KEYS if k not in it or it[k] in (None, "")]
        if missing:
            errs.append(f"item {i}: missing fields {missing}")
            continue
        if it["relation"] not in _REL_SET:
            errs.append(f"item {i}: relation '{it['relation']}' not in vocabulary")
            continue
        doc = doc_by_id.get(str(it["source_document_id"]))
        if doc is None:
            errs.append(f"item {i}: unknown source_document_id '{it['source_document_id']}'")
            continue
        if _normalize(it["source_span"]) not in _normalize(doc):
            errs.append(f"item {i}: source_span not an exact substring of the cited document")
            continue
        good.append(it)
    return good, errs


def _normalize(s: str) -> str:
    """Documented span normalization: collapse whitespace, casefold. (Nothing else.)"""
    return re.sub(r"\s+", " ", str(s)).strip().casefold()


def extract_records(backend, source_documents: List[Dict], task_hint: Optional[str],
                    max_attempts: int = 2, max_new_tokens: int = 512,
                    max_input_tokens: int = 2048) -> ExtractionResult:
    doc_by_id = {str(d["document_id"]): d["text"] for d in source_documents}
    res = ExtractionResult(provisional=[])
    feedback = None
    for attempt in range(1, max_attempts + 1):
        prompt = build_extraction_prompt(source_documents, task_hint, feedback)
        gen = backend.generate(prompt, max_new_tokens=max_new_tokens,
                               max_input_tokens=max_input_tokens)
        items, perr = _extract_json_array(gen.text)
        rec = ExtractionAttempt(attempt=attempt, prompt_hash=_prompt_hash(prompt),
                                raw_generation=gen.text, parse_ok=items is not None,
                                parse_error=perr)
        if items is None:
            rec.feedback = perr
            res.attempts.append(rec)
            feedback = f"Your output did not parse as JSON: {perr}. Return ONLY a JSON array."
            continue
        good, errs = _validate_shape(items, doc_by_id)
        rec.n_items = len(items)
        rec.n_valid_shape = len(good)
        res.attempts.append(rec)
        if good and not errs:
            res.provisional = good
            res.ok = True
            return res
        # keep the good ones but retry for the rejected ones (bounded)
        res.provisional = good
        res.ok = bool(good)
        feedback = "; ".join(errs[:8])
        rec.feedback = feedback
        if not errs:
            return res
    return res
