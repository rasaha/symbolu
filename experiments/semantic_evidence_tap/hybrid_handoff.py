"""
hybrid_handoff.py — bounded local ↔ frontier-LLM handoff packet (§10).

Constructs the minimal packet sent to an external model: only the relevant source spans, structured
evidence context, the unresolved semantic question, the allowed output schema, and prohibited
conclusions — with tenant-safe identifiers (no raw tenant/entity leakage). Reports what is retained
locally vs sent externally and any sensitive-field exposure. The external model returns structured
interpretations only, never a final decision.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import List, Dict

from .document_schema import Document, Workflow

SENSITIVE = ("tenant_id", "subject_id")
PROHIBITED_CONCLUSIONS = ("final_outcome", "compliance_status", "execution_authorization",
                          "decision_authority")
ALLOWED_OUTPUT = ("interpretation_type", "proposition", "confidence", "supporting_span",
                  "alternatives")


def _safe_id(raw) -> str:
    return "ent:" + hashlib.sha256(str(raw).encode()).hexdigest()[:8]


@dataclass
class HandoffPacket:
    spans: List[str]
    question: str
    tenant_safe_context: Dict
    allowed_output_schema: tuple
    prohibited_conclusions: tuple
    tokens_local: int
    tokens_external: int
    sensitive_field_exposure: int


def build_packet(wf: Workflow, unresolved_field: str) -> HandoffPacket:
    # only the spans for the unresolved semantic field are sent
    spans = [f.span for d in wf.documents for f in d.truth if f.field == unresolved_field]
    full_text = " ".join(d.body for d in wf.documents)
    external_text = " ".join(spans) + " " + unresolved_field
    context = {"subject": _safe_id(wf.documents[0].subject_id), "workflow": _safe_id(wf.workflow_id)}
    exposure = sum(1 for s in spans for bad in ("request:", "tenant") if bad in s)
    return HandoffPacket(spans=spans, question=f"What is {unresolved_field}?",
                         tenant_safe_context=context, allowed_output_schema=ALLOWED_OUTPUT,
                         prohibited_conclusions=PROHIBITED_CONCLUSIONS,
                         tokens_local=len(full_text.split()),
                         tokens_external=len(external_text.split()),
                         sensitive_field_exposure=exposure)
