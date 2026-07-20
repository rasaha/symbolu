#!/usr/bin/env python3
"""
Curation data model — three logically independent role artifacts plus an explicit
candidate lifecycle. Roles remain artifact-wise separate; blinding is enforced by
the *shape* of the annotator record (it simply has no author-only fields), checked
by `blinding.py`.

Roles:
  A Case Author         — question, documents, intended capability, proposed
                          difficulty, private rationale (+ private intended graph).
  B Independent Annotator — a graph/governance/expectation produced from the
                          documents alone, WITHOUT the author rationale or intended
                          graph.
  C Adjudicator         — compares A and B and produces the accepted gold.

No separate human identities are assumed; the guarantee is that the artifacts are
separate and the annotator artifact carries none of the author-only fields.
"""

from __future__ import annotations

from typing import ClassVar, Optional

from pydantic import BaseModel, Field

# ---- lifecycle ------------------------------------------------------------- #
STATES = [
    "DRAFT", "AUTHOR_COMPLETE", "READY_FOR_BLIND_ANNOTATION", "ANNOTATED",
    "READY_FOR_ADJUDICATION", "ACCEPTED", "REJECTED", "QUARANTINED",
]

ALLOWED_TRANSITIONS = {
    "DRAFT": {"AUTHOR_COMPLETE"},
    "AUTHOR_COMPLETE": {"READY_FOR_BLIND_ANNOTATION"},
    "READY_FOR_BLIND_ANNOTATION": {"ANNOTATED"},
    "ANNOTATED": {"READY_FOR_ADJUDICATION"},
    "READY_FOR_ADJUDICATION": {"ACCEPTED", "REJECTED", "QUARANTINED"},
    "ACCEPTED": set(), "REJECTED": set(), "QUARANTINED": set(),
}


def canonical_path(final_state: str) -> list[str]:
    """The unique non-skipping path from DRAFT to a terminal state."""
    base = ["DRAFT", "AUTHOR_COMPLETE", "READY_FOR_BLIND_ANNOTATION",
            "ANNOTATED", "READY_FOR_ADJUDICATION"]
    return base + [final_state]


def validate_path(path: list[str]) -> bool:
    if not path or path[0] != "DRAFT":
        return False
    for a, b in zip(path, path[1:]):
        if b not in ALLOWED_TRANSITIONS.get(a, set()):
            return False
    return True


# ---- artifacts ------------------------------------------------------------- #
class Doc(BaseModel):
    doc_id: str
    citation: str
    order: int
    text: str


class Graph(BaseModel):
    nodes: dict[str, str] = Field(default_factory=dict)   # citation -> type
    edges: list[tuple[str, str, str]] = Field(default_factory=list)  # (src,type,dst)
    governing: list[str] = Field(default_factory=list)
    abstain: bool = False


class AuthorRecord(BaseModel):
    """Role A. Includes the private intended graph + rationale (author-only)."""
    cand_id: str
    question: str
    documents: list[Doc]
    intended_capability: list[str]
    proposed_difficulty: int
    author_rationale: str                 # PRIVATE
    intended_graph: Graph                 # PRIVATE (author's mental model)
    variation: list[str] = Field(default_factory=list)
    negative_control: Optional[str] = None


class AnnotatorRecord(BaseModel):
    """Role B. Produced from documents alone. Carries NO author-only field."""
    cand_id: str
    graph: Graph
    governing: list[str] = Field(default_factory=list)
    defeated: list[str] = Field(default_factory=list)
    abstain: bool = False
    packet_expectation: dict = Field(default_factory=dict)
    ambiguity_status: str = "none"
    confidence: float = 0.9
    evidence_provenance: dict[str, str] = Field(default_factory=dict)  # "src|type|dst" -> needle

    # blinding: these author-only keys must NEVER appear on this record
    BANNED_FIELDS: ClassVar[tuple] = (
        "author_rationale", "intended_graph", "proposed_difficulty",
        "intended_capability", "expected_answer", "template_id",
        "target_weakness", "dev_case_ref")


class AdjudicationRecord(BaseModel):
    """Role C. Reconciles A and B; produces the accepted gold."""
    cand_id: str
    decision: str                          # ACCEPTED | REJECTED | QUARANTINED
    accepted_graph: Optional[Graph] = None
    accepted_packet: dict = Field(default_factory=dict)
    final_difficulty: Optional[int] = None
    final_difficulty_justification: str = ""
    ambiguity_status: str = "none"
    confidence: float = 0.9
    rationale: str = ""
    override_notes: str = ""
