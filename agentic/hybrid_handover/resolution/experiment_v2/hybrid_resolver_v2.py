#!/usr/bin/env python3
"""
HybridRelationshipResolver Experimental v0.2 — v0.1 proposal generation UNCHANGED,
plus a deterministic Proposal Validation Layer, feeding the FROZEN GraphTraversal
governance + packet builder (reused by composition, never modified).

Pipeline:
    v0.1 proposal  ->  Proposal Validation  ->  Validated Graph
                   ->  frozen governance     ->  frozen packet

With validation disabled (V0), this class reproduces Hybrid v0.1 bit-for-bit: the
proposal generator, the confidence-gated abstention (τ=0.5), the frozen governance,
and the frozen packet builder are all the v0.1 / frozen code paths. The ONLY new
behaviour is the validator between proposal and graph construction.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import (
    GovernanceResolution, ResolutionResult, ResolvedEvidenceGraph,
)
from agentic.hybrid_handover.resolution.parse import parse_nodes
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

from ..experiment.hybrid_resolver import HybridRelationshipResolver  # v0.1 (unchanged)
from .validator import ABLATIONS, ValidatorConfig, validate


class HybridRelationshipResolverV2:
    name = "hybrid_relationship_v2"
    TAU = HybridRelationshipResolver.TAU  # reuse v0.1 abstention threshold (unchanged)

    def __init__(self, validator_config: ValidatorConfig | None = ABLATIONS["V4_full"]):
        self.vcfg = validator_config           # None => pass-through (V0 == v0.1)
        self._v1 = HybridRelationshipResolver()  # v0.1 proposal generator (unchanged)
        self._gt = GraphTraversalResolver()      # frozen governance + packet (reused)
        self._conf = {}
        self._records = []

    # ---------- relationship discovery (proposal -> validation) ---------- #
    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        nodes = parse_nodes(evidence)
        edges, conf, prov = self._v1._propose(nodes)   # v0.1 proposal, verbatim
        # v0.1 provenance requirement (unchanged) then dedupe, exactly as v0.1 does,
        # so the pre-validation edge set matches v0.1 before the new layer runs.
        edges = [e for e in edges if prov.get(e.triple())]
        if self.vcfg is None:
            validated, self._records = edges, []
        else:
            validated, self._records = validate(nodes, edges, conf, prov, self.vcfg)
        # dedupe (idempotent; v0.1 also dedupes)
        seen, uniq = set(), []
        for e in validated:
            if e.triple() not in seen:
                seen.add(e.triple()); uniq.append(e)
        self._conf = {e.triple(): conf.get(e.triple(), 0.0) for e in uniq}
        self._prov = {e.triple(): prov.get(e.triple()) for e in uniq}
        return ResolvedEvidenceGraph(nodes=nodes, edges=uniq)

    # ---------- frozen governance + packet (delegated, unchanged) ---------- #
    def resolve_governance(self, question, graph) -> GovernanceResolution:
        return self._gt.resolve_governance(question, graph)

    def _derive(self, graph, gov):
        return self._gt._derive(graph, gov)

    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self.resolve_relationships(question, evidence)
        gov = self._gt.resolve_governance(question, graph)
        # v0.1 confidence-gated abstention (unchanged), now over validated edges
        if not gov.abstain:
            supporting = [c for tr, c in self._conf.items() if tr in graph.edge_triples()]
            if supporting and max(supporting) < self.TAU and gov.governing:
                gov = GovernanceResolution(abstain=True,
                                           abstain_reason="all supporting edges below confidence tau")
        tfc, notice, penalty = self._gt._derive(graph, gov)
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)

    # ---------- reporting ---------- #
    def validation_records(self, question, evidence) -> list[dict]:
        self.resolve_relationships(question, evidence)
        return list(self._records)

    def intermediate_artifacts(self, question, evidence) -> dict:
        graph = self.resolve_relationships(question, evidence)
        gov = self.resolve_governance(question, graph)
        res = self.resolve(question, evidence)
        return {
            "nodes": [{"key": n.key, "type": n.type} for n in graph.nodes],
            "validated_edges": [{"src": e.src, "type": e.type, "dst": e.dst,
                                 "confidence": self._conf.get(e.triple())} for e in graph.edges],
            "validation_records": self._records,
            "governing": gov.governing, "abstain": gov.abstain,
            "packet": {"tfc": res.tfc, "notice_days": res.notice_days, "penalty": res.penalty},
        }
