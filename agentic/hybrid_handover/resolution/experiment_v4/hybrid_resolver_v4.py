#!/usr/bin/env python3
"""
HybridRelationshipResolver Experimental v0.4 — v0.2 proposal + validation UNCHANGED,
plus an experimental Governance Semantics Layer, feeding the FROZEN packet builder
through a documented adapter.

Pipeline:
    proposal (v0.1) -> validation (v0.2) -> Governance Semantics -> adapter -> frozen packet

Boundary guarantees (structural):
- `resolve_relationships` delegates to v0.2 verbatim → discovery / classification
  bit-identical to v0.2.
- `_derive` delegates to the frozen packet builder verbatim → packet Mode P
  bit-identical (the harness injects gold governance and calls `_derive`).
- `resolve_governance` runs the experimental semantic layer (its output IS the new
  governance under test) and is measured by Mode G against the non-inferiority margin.
- With G0 (no semantics) the resolver reproduces v0.2 exactly.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import (
    GovernanceResolution, ResolutionResult, ResolvedEvidenceGraph,
)
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

from ..experiment_v2.hybrid_resolver_v2 import HybridRelationshipResolverV2
from ..experiment_v2.validator import ABLATIONS as V_ABLATIONS
from . import governance_semantics as GS


class HybridRelationshipResolverV4:
    name = "hybrid_relationship_v4"

    def __init__(self, semantic_config=GS.ABLATIONS["G4_full"]):
        self.scfg = semantic_config                 # None => G0 control (frozen governance)
        self._v2 = HybridRelationshipResolverV2(V_ABLATIONS["V4_full"])
        self._gt = GraphTraversalResolver()         # frozen governance (control) + packet
        self.TAU = self._v2.TAU
        self._last_result = None

    # ---------- discovery: delegated to v0.2, unchanged ---------- #
    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        return self._v2.resolve_relationships(question, evidence)

    # ---------- governance (experimental semantics, or frozen control) ---------- #
    def resolve_governance(self, question, graph) -> GovernanceResolution:
        if self.scfg is None:
            return self._gt.resolve_governance(question, graph)   # G0 control
        result = GS.analyze(graph, question, {}, self.scfg)
        _, gov = GS.adapt(graph, result)
        return gov

    # ---------- packet: frozen, unchanged (Mode P) ---------- #
    def _derive(self, graph, gov):
        return self._gt._derive(graph, gov)

    # ---------- full pipeline ---------- #
    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self._v2.resolve_relationships(question, evidence)   # validated (v0.2)
        conf = dict(self._v2._conf)
        if self.scfg is None:
            gov = self._gt.resolve_governance(question, graph)
            gov_graph = graph
            # v0.2 confidence-gated abstention (unchanged) for the G0 control
            if not gov.abstain:
                supporting = [c for tr, c in conf.items() if tr in graph.edge_triples()]
                if supporting and max(supporting) < self.TAU and gov.governing:
                    gov = GovernanceResolution(abstain=True,
                                               abstain_reason="all supporting edges below confidence tau")
        else:
            result = GS.analyze(graph, question, conf, self.scfg)
            self._last_result = result
            gov_graph, gov = GS.adapt(graph, result)
        tfc, notice, penalty = self._gt._derive(gov_graph, gov)      # frozen packet
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)

    # ---------- reporting ---------- #
    def governance_result(self, question, evidence) -> dict:
        graph = self._v2.resolve_relationships(question, evidence)
        if self.scfg is None:
            return {"control": True}
        return GS.analyze(graph, question, dict(self._v2._conf), self.scfg).as_dict()

    def intermediate_artifacts(self, question, evidence) -> dict:
        res = self.resolve(question, evidence)
        gr = self.governance_result(question, evidence)
        return {
            "nodes": [{"key": n.key, "type": n.type} for n in res.graph.nodes],
            "governance_result": gr,
            "governing": res.governance.governing, "abstain": res.governance.abstain,
            "packet": {"tfc": res.tfc, "notice_days": res.notice_days, "penalty": res.penalty},
        }
