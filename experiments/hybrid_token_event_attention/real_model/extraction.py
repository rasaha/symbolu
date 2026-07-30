"""
extraction.py — schema-guided provisional extraction with bounded retries and a bounded, append-only
ClarificationRequest contract (§6, §7).

The real model proposes *provisional* evidence (semantic fields + an EXACT source span). This module
performs only the provisional-level deterministic checks that gate a proposal onto the next stage:

    JSON parseability -> schema validity -> source-span exact-substring existence in the cited,
    permitted source document.

It does NOT resolve identity, authority, version, provenance, tenancy or admission — those are the
deterministic evidence pipeline's job (`evidence_pipeline.py`). Malformed or low-confidence proposals
are NOT silently repaired; they are surfaced (and quarantined downstream).

Bounded retries: at most two extraction attempts by default. The retry receives parser/schema/span
feedback ONLY — never the expected gold answer. Clarification: a bounded, append-only, replayable
request that re-validates against the SOURCE, not against the hypothesis that triggered it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

from .prompts import (build_extraction_prompt, build_clarification_prompt, EXTRACTION_SCHEMA)


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha1((system + "\x00" + user).encode()).hexdigest()[:16]


@dataclass
class ProvisionalEvent:
    """A single provisional proposal (pre-validation). Semantic fields are strings as proposed; the
    deterministic pipeline resolves them into an exact EventRecord."""
    relation: str
    source_document_id: int
    source_span: str
    subject: str = ""
    object: str = ""
    value: str = ""
    version: str = ""
    status: str = ""
    authority: str = ""
    confidence: float = 0.0
    ambiguous: bool = False
    conditions: List[str] = field(default_factory=list)
    temporal: List[str] = field(default_factory=list)
    span_verified: bool = False       # exact-substring check against permitted doc


@dataclass
class AttemptLog:
    attempt: int
    prompt_hash: str
    raw_generation: str
    parse_ok: bool
    schema_ok: bool
    n_events: int
    errors: List[str] = field(default_factory=list)


@dataclass
class ClarificationResponse:
    attempt: int
    interpretation: str
    validation_outcome: str           # "RESOLVED" | "REJECTED"
    at: str = ""                       # logical timestamp (append order); no wall-clock


@dataclass
class ClarificationRequest:
    """Bounded, append-only, replayable clarification contract (§7)."""
    request_id: str
    triggering_evidence_ids: List[int]
    unresolved_question: str
    permitted_document_ids: List[int]
    permitted_source_spans: List[str]
    max_attempts: int
    requesting_component: str
    created_order: int                # logical timestamp (append order), not wall-clock
    responses: List[ClarificationResponse] = field(default_factory=list)
    final_outcome: str = "OPEN"       # OPEN | RESOLVED | QUARANTINE | HUMAN_REVIEW_REQUIRED

    def append_response(self, resp: ClarificationResponse) -> None:
        # append-only: never mutate a prior response
        self.responses.append(resp)


@dataclass
class ExtractionResult:
    proposals: List[ProvisionalEvent]
    attempts: List[AttemptLog]
    clarifications: List[ClarificationRequest]
    parse_ok: bool
    schema_ok: bool
    prompt_hashes: List[str]
    raw_generations: List[str]


# --------------------------------------------------------------------------- #
# deterministic provisional-level checks                                       #
# --------------------------------------------------------------------------- #
def _parse_json_object(text: str) -> Tuple[Optional[dict], Optional[str]]:
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        return None, "no_json_object"
    try:
        return json.loads(text[start:end + 1]), None
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error:{exc.msg}"


def _schema_check(obj: dict) -> Tuple[bool, List[str]]:
    errs: List[str] = []
    if not isinstance(obj, dict) or "events" not in obj:
        return False, ["missing_events"]
    if not isinstance(obj["events"], list):
        return False, ["events_not_array"]
    for i, ev in enumerate(obj["events"]):
        if not isinstance(ev, dict):
            errs.append(f"event[{i}]_not_object")
            continue
        for req in ("relation", "source_document_id", "source_span"):
            if req not in ev:
                errs.append(f"event[{i}]_missing_{req}")
    return (len(errs) == 0), errs


def _verify_span(ev: dict, docs: Dict[int, str]) -> bool:
    doc_id = ev.get("source_document_id")
    span = ev.get("source_span", "")
    if doc_id not in docs or not isinstance(span, str) or not span:
        return False
    # exact substring after documented whitespace normalization (collapse runs of spaces)
    def norm(s: str) -> str:
        return " ".join(s.split())
    return norm(span) in norm(docs[doc_id])


def _to_provisional(ev: dict, span_ok: bool) -> ProvisionalEvent:
    return ProvisionalEvent(
        relation=str(ev.get("relation", "")),
        source_document_id=int(ev.get("source_document_id", -1))
        if str(ev.get("source_document_id", "")).lstrip("-").isdigit() else -1,
        source_span=str(ev.get("source_span", "")),
        subject=str(ev.get("subject", "")),
        object=str(ev.get("object", "")),
        value=str(ev.get("value", "")),
        version=str(ev.get("version", "")),
        status=str(ev.get("status", "")),
        authority=str(ev.get("authority", "")),
        confidence=float(ev.get("confidence", 0.0) or 0.0),
        ambiguous=bool(ev.get("ambiguous", False)),
        conditions=list(ev.get("conditions", []) or []),
        temporal=list(ev.get("temporal", []) or []),
        span_verified=span_ok,
    )


# --------------------------------------------------------------------------- #
# main extraction routine                                                      #
# --------------------------------------------------------------------------- #
def extract_events(backend, task_family: str, subject_ref: str, docs: Dict[int, str],
                   permitted_doc_ids: Optional[List[int]] = None, max_attempts: int = 2,
                   clarification_limit: int = 1, order_base: int = 0) -> ExtractionResult:
    permitted = {d: docs[d] for d in (permitted_doc_ids or list(docs))}
    attempts: List[AttemptLog] = []
    clar: List[ClarificationRequest] = []
    prompt_hashes: List[str] = []
    raw_generations: List[str] = []
    feedback: Optional[str] = None
    proposals: List[ProvisionalEvent] = []
    parse_ok = schema_ok = False

    for attempt in range(1, max_attempts + 1):
        system, user = build_extraction_prompt(task_family, subject_ref, permitted, feedback)
        ph = prompt_hash(system, user)
        gen = backend.generate(system, user)
        prompt_hashes.append(ph)
        raw_generations.append(gen.text)

        obj, perr = _parse_json_object(gen.text)
        if obj is None:
            attempts.append(AttemptLog(attempt, ph, gen.text, False, False, 0, [perr or "parse"]))
            feedback = f"Attempt {attempt} was not valid JSON ({perr}). Return one JSON object."
            continue
        parse_ok = True
        sok, serrs = _schema_check(obj)
        if not sok:
            attempts.append(AttemptLog(attempt, ph, gen.text, True, False, 0, serrs))
            feedback = "Schema errors: " + "; ".join(serrs) + ". Every event needs relation, " \
                       "source_document_id and an exact source_span."
            continue
        schema_ok = True

        cand: List[ProvisionalEvent] = []
        span_errs: List[str] = []
        for i, ev in enumerate(obj["events"]):
            span_ok = _verify_span(ev, permitted)
            if not span_ok:
                span_errs.append(f"event[{i}]_span_not_in_source")
            cand.append(_to_provisional(ev, span_ok))
        attempts.append(AttemptLog(attempt, ph, gen.text, True, True, len(cand), span_errs))

        if span_errs and attempt < max_attempts:
            feedback = ("Some source_span values were not exact substrings of the cited document: "
                        + "; ".join(span_errs) + ". Copy spans verbatim from the source.")
            proposals = cand   # keep best-so-far in case retry does not improve
            continue
        proposals = cand
        break

    return ExtractionResult(proposals=proposals, attempts=attempts, clarifications=clar,
                            parse_ok=parse_ok, schema_ok=schema_ok, prompt_hashes=prompt_hashes,
                            raw_generations=raw_generations)


def run_clarification(backend, req: ClarificationRequest, docs: Dict[int, str],
                      validate_against_source) -> ClarificationRequest:
    """Execute a bounded clarification. ``validate_against_source(provisional) -> bool`` compares the
    new interpretation with the SOURCE (never with the triggering hypothesis). Append-only; after the
    attempt limit the request is quarantined or escalated to human review."""
    for attempt in range(1, req.max_attempts + 1):
        system, user = build_clarification_prompt(
            req.unresolved_question, req.permitted_document_ids, docs)
        gen = backend.generate(system, user)
        obj, _ = _parse_json_object(gen.text)
        interp = json.dumps(obj) if obj is not None else gen.text
        ok = False
        if obj is not None:
            evs = obj.get("events", []) if isinstance(obj, dict) else []
            ok = any(validate_against_source(_to_provisional(e, _verify_span(e, docs))) for e in evs)
        req.append_response(ClarificationResponse(
            attempt=attempt, interpretation=interp,
            validation_outcome="RESOLVED" if ok else "REJECTED",
            at=f"order:{req.created_order}.{attempt}"))
        if ok:
            req.final_outcome = "RESOLVED"
            return req
    req.final_outcome = "HUMAN_REVIEW_REQUIRED"
    return req


def clarification_to_record(req: ClarificationRequest) -> Dict:
    d = asdict(req)
    return d
