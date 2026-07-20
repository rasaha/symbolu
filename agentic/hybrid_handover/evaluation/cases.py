#!/usr/bin/env python3
"""
Evaluation case format.

A case declares not just the question and corpus but the full ground truth an
enterprise cares about: which spans are *decisive*, which are *defeaters*
(exceptions / conflicts / overrides), which *precedence* relationships and
*definitions* must be present, when the system *should abstain*, and the correct
routing decision. The framework scores retrieval completeness against this
ground truth — not merely the final answer.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from agentic.hybrid_handover.schema import Corpus, ResolvedAnswer

SpanKind = Literal["decisive", "defeater", "definition"]
Routing = Literal["SERVE_IN_HOUSE", "ESCALATE", "REFUSE"]


class RequiredSpan(BaseModel):
    """A span that MUST appear in the packet, identified by source doc and a
    verbatim substring ("needle") that must be present in a retrieved quote."""

    doc_id: str
    needle: str
    kind: SpanKind = "decisive"
    note: str = ""


class PrecedenceReq(BaseModel):
    """A governing relationship the packet must record (superseded_by governs
    superseded)."""

    superseded: str  # citation of overridden clause/doc
    superseded_by: str  # citation of governing clause/doc


class EvalCase(BaseModel):
    case_id: str
    failure_mode: str
    question: str
    corpus: Corpus

    expected_answer: ResolvedAnswer
    required_decisive: list[RequiredSpan] = Field(default_factory=list)
    required_defeaters: list[RequiredSpan] = Field(default_factory=list)
    required_precedence: list[PrecedenceReq] = Field(default_factory=list)
    required_definitions: list[RequiredSpan] = Field(default_factory=list)

    # Coverage ground truth
    expected_doc_ids: list[str] = Field(default_factory=list)
    referenced_docs: list[str] = Field(default_factory=list)  # named external refs that must resolve

    # Decisions
    expected_abstention: bool = False  # should the system refuse on this (clean) case?
    expected_routing: Routing = "ESCALATE"

    # Provenance / honesty
    is_synthetic: bool = True

    def all_required(self) -> list[RequiredSpan]:
        return (
            self.required_decisive
            + self.required_defeaters
            + self.required_definitions
        )
