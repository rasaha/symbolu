#!/usr/bin/env python3
"""
Typed relationship-graph data model — the shared vocabulary of the resolution
layer.

Separation of concerns (this phase's central design principle):
  1. Evidence Extraction     → produces evidence spans (upstream; SEEB/baselines)
  2. Relationship Resolution → produces a typed graph over the spans   (here)
  3. Governance Resolution   → decides which nodes govern / abstain    (here)
  4. Packet Construction     → assembles the final answer/packet        (here)

These four stages are kept independent so a failure can be attributed to exactly
one of them (see attribution.py).
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

NodeType = Literal[
    "Clause", "Definition", "Exception", "Policy", "Table", "Version",
    "Document", "Section",
]

EdgeType = Literal[
    "defines", "references", "overrides", "supersedes", "governs_over",
    "exception_to", "conflicts_with", "same_as", "effective_after",
    "effective_before", "amends", "contains",
]

NODE_TYPES = (
    "Clause", "Definition", "Exception", "Policy", "Table", "Version",
    "Document", "Section",
)
EDGE_TYPES = (
    "defines", "references", "overrides", "supersedes", "governs_over",
    "exception_to", "conflicts_with", "same_as", "effective_after",
    "effective_before", "amends", "contains",
)


class Node(BaseModel):
    key: str                 # stable identity — the source citation
    type: NodeType
    doc_id: str = ""
    text: str = ""
    section: Optional[str] = None          # normalised section id, e.g. "7.1"
    attrs: dict = Field(default_factory=dict)  # notice_days, penalty_months, negation, version_label, ...


class Edge(BaseModel):
    src: str                 # Node.key
    type: EdgeType
    dst: str                 # Node.key
    attrs: dict = Field(default_factory=dict)

    def triple(self) -> tuple[str, str, str]:
        return (self.src, self.type, self.dst)


class ResolvedEvidenceGraph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def node(self, key: str) -> Optional[Node]:
        for n in self.nodes:
            if n.key == key:
                return n
        return None

    def edge_triples(self) -> set[tuple[str, str, str]]:
        return {e.triple() for e in self.edges}


class GovernanceResolution(BaseModel):
    governing: list[str] = Field(default_factory=list)   # Node.keys that govern
    discarded: dict[str, str] = Field(default_factory=dict)  # key -> reason
    abstain: bool = False
    abstain_reason: str = ""


class ResolutionResult(BaseModel):
    """Full output of a resolver for one case under one evidence mode."""
    graph: ResolvedEvidenceGraph
    governance: GovernanceResolution
    # Packet-construction stage output (derived answer):
    tfc: str = "unknown"                # allowed | prohibited | unknown
    notice_days: Optional[int] = None
    penalty: Optional[str] = None
