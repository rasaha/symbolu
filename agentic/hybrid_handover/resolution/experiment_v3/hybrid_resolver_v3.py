#!/usr/bin/env python3
"""
HybridRelationshipResolver Experimental v0.3 — v0.2 proposal + validation UNCHANGED,
plus a deterministic Edge Prioritization layer, feeding the FROZEN GraphTraversal
governance + packet builder (reused by composition, never modified).

Pipeline:
    proposal (v0.1) -> validation (v0.2) -> Edge Prioritization -> frozen governance -> frozen packet

Boundary guarantees (structural, not merely intended):
- `resolve_relationships` delegates to v0.2 verbatim → discovery / classification are
  bit-identical to v0.2 (prioritization never touches the discovery graph).
- `resolve_governance` (used by the harness for Mode G with the gold graph) delegates
  straight to the frozen governance → Mode G is unchanged.
- `_derive` (used by the harness for Mode P with gold governance) delegates straight to
  the frozen packet builder → Mode P is unchanged.
- Prioritization runs ONLY inside the full `resolve()` pipeline, reordering the
  governance-input graph so the dominant competing governance source becomes the
  frozen packet's `primary`. With P0 (no prioritization) this reproduces v0.2 exactly.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import (
    GovernanceResolution, ResolutionResult, ResolvedEvidenceGraph,
)
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

from ..experiment_v2.hybrid_resolver_v2 import HybridRelationshipResolverV2
from ..experiment_v2.validator import ABLATIONS as V_ABLATIONS
from .prioritizer import ABLATIONS as P_ABLATIONS
from .prioritizer import PriorityConfig, prioritize


class HybridRelationshipResolverV3:
    name = "hybrid_relationship_v3"

    def __init__(self, priority_config: PriorityConfig | None = P_ABLATIONS["P4_full"]):
        self.pcfg = priority_config
        # v0.2 (proposal + validation) reused bit-for-bit
        self._v2 = HybridRelationshipResolverV2(V_ABLATIONS["V4_full"])
        self._gt = GraphTraversalResolver()   # frozen governance + packet
        self.TAU = self._v2.TAU
        self._records = []

    # ---------- discovery: delegated to v0.2, unchanged ---------- #
    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        return self._v2.resolve_relationships(question, evidence)

    # ---------- frozen governance / packet in isolation (Mode G / Mode P) ---------- #
    def resolve_governance(self, question, graph) -> GovernanceResolution:
        return self._gt.resolve_governance(question, graph)   # no prioritization → Mode G unchanged

    def _derive(self, graph, gov):
        return self._gt._derive(graph, gov)                    # no prioritization → Mode P unchanged

    # ---------- full pipeline: prioritization steers frozen governance ---------- #
    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self._v2.resolve_relationships(question, evidence)   # validated (v0.2)
        conf = dict(self._v2._conf)
        gov_graph, self._records = prioritize(graph, conf, self.pcfg)
        gov = self._gt.resolve_governance(question, gov_graph)       # frozen governance
        # v0.2/v0.1 confidence-gated abstention (unchanged), over the same edge set
        if not gov.abstain:
            supporting = [c for tr, c in conf.items() if tr in gov_graph.edge_triples()]
            if supporting and max(supporting) < self.TAU and gov.governing:
                gov = GovernanceResolution(abstain=True,
                                           abstain_reason="all supporting edges below confidence tau")
        tfc, notice, penalty = self._gt._derive(gov_graph, gov)      # frozen packet
        # the returned graph is the DISCOVERY graph (unchanged); prioritization only
        # affected the internal governance-input ordering
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)

    # ---------- reporting ---------- #
    def competition_records(self, question, evidence) -> list[dict]:
        graph = self._v2.resolve_relationships(question, evidence)
        _, records = prioritize(graph, dict(self._v2._conf), self.pcfg)
        return records

    def intermediate_artifacts(self, question, evidence) -> dict:
        res = self.resolve(question, evidence)
        return {
            "nodes": [{"key": n.key, "type": n.type} for n in res.graph.nodes],
            "edges": [{"src": e.src, "type": e.type, "dst": e.dst} for e in res.graph.edges],
            "competition_records": self._records,
            "governing": res.governance.governing, "abstain": res.governance.abstain,
            "packet": {"tfc": res.tfc, "notice_days": res.notice_days, "penalty": res.penalty},
        }
