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


# ---- deterministic source-document resolution methods (RM1-v1.1, §normalization) ----
RES_EXACT_ID = "EXACT_ID"
RES_REGISTERED_ALIAS = "REGISTERED_ALIAS"
RES_SINGLE_PERMITTED = "SINGLE_PERMITTED_DOCUMENT"
RES_UNIQUE_SPAN = "UNIQUE_SPAN_MATCH"
RES_AMBIGUOUS = "AMBIGUOUS"
RES_UNRESOLVED = "UNRESOLVED"
_RESOLVED_METHODS = (RES_EXACT_ID, RES_REGISTERED_ALIAS, RES_SINGLE_PERMITTED, RES_UNIQUE_SPAN)


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
    span_verified: bool = False       # exact-substring check against the RESOLVED permitted doc
    # deterministic document-binding audit (RM1-v1.1): the model's proposed id is NOT trusted; the
    # span is bound to an authorized document by exact-id / alias / single-permitted / unique-span.
    model_supplied_document_id: Optional[int] = None
    resolved_document_id: Optional[int] = None
    document_resolution_method: str = RES_UNRESOLVED


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


def _norm_text(s) -> str:
    # documented normalization: collapse runs of whitespace (nothing else)
    return " ".join(str(s).split())


def _coerce_doc_id(v):
    return int(v) if str(v).lstrip("-").isdigit() else v


def resolve_document(ev: dict, permitted: Dict[int, str],
                     aliases: Optional[Dict] = None) -> Tuple[Optional[int], str, bool]:
    """Deterministically bind a proposal's span to an AUTHORIZED permitted document (RM1-v1.1).

    The model's ``source_document_id`` is a hint, never trusted. Returns
    ``(resolved_document_id, method, span_verified)``. A span that exists in more than one permitted
    document is AMBIGUOUS (quarantined); a span found in none is UNRESOLVED. This is strictly safer
    than blindly coercing to a single document: it never binds a span to a document that does not
    contain it, and never silently disambiguates.
    """
    aliases = aliases or {}
    span = ev.get("source_span", "")
    if not isinstance(span, str) or not span:
        return None, RES_UNRESOLVED, False
    nspan = _norm_text(span)
    mid = _coerce_doc_id(ev.get("source_document_id"))

    # 1. exact model-supplied id, and the span is actually in it
    if mid in permitted and nspan in _norm_text(permitted[mid]):
        return mid, RES_EXACT_ID, True
    # 2. registered alias -> a permitted id containing the span
    if mid in aliases and aliases[mid] in permitted and nspan in _norm_text(permitted[aliases[mid]]):
        return aliases[mid], RES_REGISTERED_ALIAS, True
    # 3. exactly one permitted document: bind to it IF it contains the span
    if len(permitted) == 1:
        only = next(iter(permitted))
        if nspan in _norm_text(permitted[only]):
            return only, RES_SINGLE_PERMITTED, True
        return None, RES_UNRESOLVED, False          # invented id + span absent -> quarantine
    # 4/5. multiple documents: resolve by UNIQUE span membership; >1 match is ambiguous
    hits = [d for d, txt in permitted.items() if nspan in _norm_text(txt)]
    if len(hits) == 1:
        return hits[0], RES_UNIQUE_SPAN, True
    if len(hits) > 1:
        return None, RES_AMBIGUOUS, False
    return None, RES_UNRESOLVED, False


def _verify_span(ev: dict, docs: Dict[int, str]) -> bool:
    # kept for the clarification path; delegates to the deterministic resolver
    _, _, span_ok = resolve_document(ev, docs)
    return span_ok


def _to_provisional(ev: dict, resolved_doc: Optional[int], method: str,
                    span_ok: bool) -> ProvisionalEvent:
    model_doc = _coerce_doc_id(ev.get("source_document_id"))
    return ProvisionalEvent(
        relation=str(ev.get("relation", "")),
        # source_document_id is the RESOLVED authorized id (falls back to model's hint if unresolved)
        source_document_id=resolved_doc if resolved_doc is not None
        else (model_doc if isinstance(model_doc, int) else -1),
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
        model_supplied_document_id=model_doc if isinstance(model_doc, int) else None,
        resolved_document_id=resolved_doc,
        document_resolution_method=method,
    )


# --------------------------------------------------------------------------- #
# main extraction routine                                                      #
# --------------------------------------------------------------------------- #
def extract_events(backend, task_family: str, subject_ref: str, docs: Dict[int, str],
                   permitted_doc_ids: Optional[List[int]] = None, max_attempts: int = 2,
                   clarification_limit: int = 1, order_base: int = 0,
                   aliases: Optional[Dict] = None) -> ExtractionResult:
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
            rdoc, method, span_ok = resolve_document(ev, permitted, aliases)
            if not span_ok:
                span_errs.append(f"event[{i}]_span_{method.lower()}")
            cand.append(_to_provisional(ev, rdoc, method, span_ok))
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
            def _mk(e):
                rdoc, method, span_ok = resolve_document(e, docs)
                return _to_provisional(e, rdoc, method, span_ok)
            ok = any(validate_against_source(_mk(e)) for e in evs)
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
