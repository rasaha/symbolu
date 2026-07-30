"""
prompts.py — schema-guided extraction and explanation prompts (RM1 §5, §6).

The real model is confined to two jobs: (A) propose provisional evidence from source language, and
(B) explain an already-computed typed result. Neither prompt ever contains the gold answer, the gold
EvidenceRecords, or the expected outcome — that would leak the label the extraction is meant to
produce. Retry prompts add only *deterministic validator feedback* (parser/schema/span errors),
never the target.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from ..event_schema import RELATION_TYPES, STATUSES

_EXTRACTION_SYSTEM = (
    "You are an enterprise evidence extractor. From the SOURCE DOCUMENT(S) you output a JSON array "
    "of PROVISIONAL evidence proposals. You do NOT decide authority, versions, access, or outcomes; "
    "a deterministic governance layer validates everything you propose. Output ONLY valid JSON."
)

_EXTRACTION_SCHEMA = {
    "type": "array",
    "items": {
        "subject": "string entity id or type, e.g. ent_12 or purchase_request",
        "relation": f"one of {list(RELATION_TYPES)}",
        "object": "string entity id, role, or numeric value",
        "normalized_value": "integer if the object is a value/amount/tier/role, else null",
        "version": "integer version if stated, else null",
        "status": f"one of {list(STATUSES)} if stated, else null",
        "source_document_id": "id of the document the span is quoted from",
        "source_span": "EXACT substring copied verbatim from the source document",
        "confidence": "float 0..1",
        "ambiguous": "true if the language is materially ambiguous",
    },
}


def build_extraction_prompt(source_documents: List[Dict], task_hint: Optional[str] = None,
                            feedback: Optional[str] = None) -> str:
    """`source_documents`: [{"document_id":..., "text":...}]. `task_hint` names the contract only
    (never the answer). `feedback` is deterministic validator error text for a bounded retry."""
    docs = "\n".join(f"[{d['document_id']}]\n{d['text']}" for d in source_documents)
    parts = [
        _EXTRACTION_SYSTEM,
        "\nJSON item schema (propose 0..N items):",
        json.dumps(_EXTRACTION_SCHEMA, indent=2),
        "\nRules:",
        "- Every source_span MUST be an exact substring of the cited source document.",
        "- Never invent a span. If unsure, set \"ambiguous\": true and lower confidence.",
        "- Do not output authority, provenance, evidence ids, or the final decision.",
    ]
    if task_hint:
        parts.append(f"\nContract under consideration (for extraction focus only, NOT the answer): "
                     f"{task_hint}")
    if feedback:
        parts.append(f"\nYour previous attempt was rejected by the deterministic validator for these "
                     f"reasons (fix them; the correct answer is NOT provided):\n{feedback}")
    parts.append("\nSOURCE DOCUMENT(S):")
    parts.append(docs)
    parts.append("\nJSON array:")
    return "\n".join(parts)


_EXPLANATION_SYSTEM = (
    "You explain an ALREADY-DECIDED governed result in plain enterprise English. You must not change "
    "the decision, invent evidence, or cite any evidence id not in the provided list. Every factual "
    "claim must be traceable to the cited EvidenceRecords."
)


def build_explanation_prompt(typed_findings: Dict, cited_records: List[Dict]) -> str:
    """Explanation prompt from typed findings + the exact cited records. No gold, no free evidence."""
    return "\n".join([
        _EXPLANATION_SYSTEM,
        "\nTYPED FINDINGS (authoritative, do not alter):",
        json.dumps(typed_findings, indent=2, default=str),
        "\nCITED EVIDENCE RECORDS (the only evidence you may reference):",
        json.dumps(cited_records, indent=2, default=str),
        "\nWrite 2-4 sentences explaining the decision, referencing evidence ids in brackets like "
        "[EV-1042]. Do not state any number, authority, or version not present above.",
        "\nExplanation:",
    ])
