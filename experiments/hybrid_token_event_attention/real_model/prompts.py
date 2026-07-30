"""
prompts.py — the two real-model prompts (interpret / explain) + the extraction JSON schema, plus a
deterministic *offline* mock responder that reads ONLY the prompt (exactly what a real model sees).

The real model is asked to do exactly two things (RM1 role boundary):
  A. interpret governed source text into *provisional* evidence proposals (never authoritative), and
  B. explain an already-computed typed result (never compute or authorize it).

The mock responder is not a model: it parses the machine-verbalised source grammar deterministically.
It is used only so the harness is exercisable offline; its outputs are always tagged MOCK.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

# ---- delimiters the prompt uses to fence the permitted source documents ----
SOURCE_OPEN = "<<<SOURCE"
SOURCE_CLOSE = "SOURCE>>>"
RESULT_OPEN = "<<<TYPED_RESULT"
RESULT_CLOSE = "TYPED_RESULT>>>"

# ---- provisional extraction schema (schema-guided generation) ----
EXTRACTION_SCHEMA: Dict = {
    "type": "object",
    "required": ["events"],
    "properties": {
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["relation", "source_document_id", "source_span"],
                "properties": {
                    "subject": {"type": "string"},
                    "relation": {"type": "string"},
                    "object": {"type": "string"},
                    "value": {"type": "string"},
                    "version": {"type": "string"},
                    "status": {"type": "string"},
                    "authority": {"type": "string"},
                    "conditions": {"type": "array", "items": {"type": "string"}},
                    "temporal": {"type": "array", "items": {"type": "string"}},
                    "source_document_id": {"type": "integer"},
                    "source_span": {"type": "string"},
                    "confidence": {"type": "number"},
                    "ambiguous": {"type": "boolean"},
                },
            },
        }
    },
}

EXTRACTION_SYSTEM = (
    "You are a governed evidence-extraction component. Read ONLY the permitted source documents "
    "fenced between the markers. For each governed statement, propose one provisional evidence "
    "record. You must NOT invent facts, ids, authority, or source spans. Every `source_span` MUST "
    "be an EXACT substring copied verbatim from the permitted source document it cites. You do not "
    "assign evidence ids, provenance, authority status, or admission decisions — a deterministic "
    "validator does that. Return ONLY a single JSON object matching the given schema. Do not answer "
    "the user's decision question."
)

EXPLANATION_SYSTEM = (
    "You are a governed explanation component. You are given an ALREADY-COMPUTED typed result and "
    "its cited evidence. Explain the result in plain language. You must ONLY state claims that are "
    "supported by the cited evidence; cite evidence ids in square brackets like [EV-12]. Preserve "
    "every qualifier (version, status, authority, exception) present in the evidence. Do not "
    "introduce numbers, roles, or authorities that are not in the cited evidence, and do not change "
    "or override the computed outcome."
)


def _fence_docs(docs: Dict[int, str]) -> str:
    lines = [SOURCE_OPEN]
    for doc_id in sorted(docs):
        lines.append(f"[doc:{doc_id}]")
        lines.append(docs[doc_id])
    lines.append(SOURCE_CLOSE)
    return "\n".join(lines)


def build_extraction_prompt(task_family: str, subject_ref: str, docs: Dict[int, str],
                            retry_feedback: Optional[str] = None) -> Tuple[str, str]:
    """(system, user). ``retry_feedback`` carries parser/schema/span errors ONLY — never the gold
    answer (bounded, source-anchored retry, never interpretation-shopping)."""
    parts = [
        f"Decision contract: {task_family}. Focal subject: {subject_ref}.",
        "Extract provisional evidence records from the permitted documents below.",
        _fence_docs(docs),
        "",
        "Schema (return one JSON object with an `events` array; each event copies an exact "
        "`source_span` substring and cites its `source_document_id`):",
        json.dumps(EXTRACTION_SCHEMA),
    ]
    if retry_feedback:
        parts += ["", "Your previous attempt was rejected by the deterministic validator for the "
                  "following reasons. Fix ONLY these issues by re-reading the source. Do not guess.",
                  retry_feedback]
    return EXTRACTION_SYSTEM, "\n".join(parts)


ANSWER_SYSTEM = (
    "You are answering an enterprise governance decision from the permitted source documents only. "
    "Respond with a single token: one of role:requester, role:finance, role:finance_director, "
    "role:auditor, role:admin, ABSTAIN, CONFLICT, YES, NO. If the documents do not determine the "
    "answer, respond ABSTAIN. Return only the token."
)

ANSWER_TOKENS = ["role:requester", "role:finance", "role:finance_director", "role:auditor",
                 "role:admin", "ABSTAIN", "CONFLICT", "YES", "NO"]


def build_answer_prompt(task_family: str, subject_ref: str, docs: Dict[int, str],
                        events_json: Optional[str] = None) -> Tuple[str, str]:
    """Direct-answer prompt used by RM0 (raw text), RM1 (retrieved packet), RM2 (validated events)."""
    parts = [f"Decision contract: {task_family}. Focal subject: {subject_ref}.", _fence_docs(docs)]
    if events_json is not None:
        parts += ["Validated structured events (authoritative):", events_json]
    parts.append("Answer with exactly one allowed token.")
    return ANSWER_SYSTEM, "\n".join(parts)


def parse_answer_token(text: str) -> str:
    low = (text or "").strip()
    for tok in ANSWER_TOKENS:
        if tok.lower() in low.lower():
            return tok
    return "ABSTAIN"


def build_clarification_prompt(unresolved_question: str, permitted_doc_ids: List[int],
                               docs: Dict[int, str]) -> Tuple[str, str]:
    permitted = {d: docs[d] for d in permitted_doc_ids if d in docs}
    user = "\n".join([
        "A bounded clarification is requested. Re-read ONLY the permitted source spans below and "
        "answer strictly from them.",
        f"Unresolved question: {unresolved_question}",
        _fence_docs(permitted),
        "Return one JSON object matching the extraction schema.",
    ])
    return EXTRACTION_SYSTEM, user


def build_explanation_prompt(typed_result: Dict, docs: Dict[int, str]) -> Tuple[str, str]:
    user = "\n".join([
        "Explain this already-computed typed result. Cite evidence ids in [EV-..] form and preserve "
        "all qualifiers. Do not change the outcome.",
        RESULT_OPEN,
        json.dumps(typed_result, sort_keys=True),
        RESULT_CLOSE,
        _fence_docs(docs),
    ])
    return EXPLANATION_SYSTEM, user


# --------------------------------------------------------------------------- #
# Prompt-only source extraction (used by the offline mock responder)          #
# --------------------------------------------------------------------------- #
def extract_source_block(user_prompt: str) -> Dict[int, str]:
    """Recover the fenced {doc_id: text} block from a prompt — reads ONLY the prompt text."""
    try:
        body = user_prompt.split(SOURCE_OPEN, 1)[1].split(SOURCE_CLOSE, 1)[0]
    except IndexError:
        return {}
    docs: Dict[int, str] = {}
    cur: Optional[int] = None
    buf: List[str] = []
    for line in body.splitlines():
        m = re.match(r"^\[doc:(\d+)\]\s*$", line.strip())
        if m:
            if cur is not None:
                docs[cur] = " ".join(buf).strip()
            cur = int(m.group(1))
            buf = []
        elif cur is not None:
            buf.append(line)
    if cur is not None:
        docs[cur] = " ".join(buf).strip()
    return docs


def _parse_verbalized_line(span: str) -> Optional[Dict]:
    """Parse one machine-verbalised governed line into semantic fields (see datasets._verbalize).

    Grammar: ``doc ent_<subj> <relation> ent_<obj> <verword> v<ver> <status> <authword> a<A> norm n<val>``
    """
    toks = span.split()
    if len(toks) < 11 or toks[0] != "doc":
        return None
    try:
        return {
            "subject": toks[1],
            "relation": toks[2],
            "object": toks[3],
            "version": toks[5],
            "status": toks[6],
            "authority": toks[8],
            "value": toks[10],
            "source_span": span,
        }
    except IndexError:
        return None


def mock_extraction_responder(system: str, user: str) -> str:
    """Deterministic OFFLINE extractor. NOT a model. Emits one proposal per governed source line.

    Reads only the prompt (the fenced source), so it obeys the same interface a real model does.
    """
    docs = extract_source_block(user)
    events: List[Dict] = []
    for doc_id in sorted(docs):
        # source text joins lines with " . " (see datasets); split back into governed statements
        for chunk in docs[doc_id].split(" . "):
            span = chunk.strip()
            parsed = _parse_verbalized_line(span)
            if not parsed:
                continue
            parsed.update({"source_document_id": doc_id, "confidence": 0.95, "ambiguous": False,
                           "conditions": [], "temporal": []})
            events.append(parsed)
    return json.dumps({"events": events})


def mock_explanation_responder(system: str, user: str) -> str:
    """Deterministic OFFLINE explainer. NOT a model. Produces a faithful, cited, qualifier-preserving
    sentence from the typed result embedded in the prompt."""
    try:
        block = user.split(RESULT_OPEN, 1)[1].split(RESULT_CLOSE, 1)[0].strip()
        result = json.loads(block)
    except (IndexError, json.JSONDecodeError):
        return "No typed result was provided; nothing can be explained."
    outcome = result.get("outcome_label", result.get("outcome", "UNKNOWN"))
    cites = result.get("cited_evidence_ids", [])
    quals = result.get("qualifiers", [])
    cite_str = " ".join(f"[{c}]" for c in cites)
    qual_str = (" Qualifiers: " + ", ".join(quals) + ".") if quals else ""
    return (f"The governed determination is {outcome}, computed deterministically from the cited "
            f"authoritative evidence {cite_str}.{qual_str}")


def composite_mock_responder(system: str, user: str) -> str:
    """Dispatch a mock response by prompt type. Offline, deterministic, NOT a model."""
    if RESULT_OPEN in user:
        return mock_explanation_responder(system, user)
    if "events" in user and SOURCE_OPEN in user and "schema" in user.lower():
        return mock_extraction_responder(system, user)
    if system == ANSWER_SYSTEM:
        # the mock cannot "reason"; it abstains rather than fabricate a governed answer
        return "ABSTAIN"
    return "{}"
