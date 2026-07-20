#!/usr/bin/env python3
"""
HybridRelationshipResolver Experimental v0.5 — G3 operative-source selection UNCHANGED,
plus a deterministic Competing Operative Resolution Layer that adds precise
governance-stage abstention only on genuine unresolved conflict.

Pipeline:
    proposal (v0.1) -> validation (v0.2) -> governing set (frozen) -> G3 operative source
    -> Competing Operative Resolution -> governance decision / precise abstention
    -> frozen packet (via the v0.4 adapter)

Boundary guarantees (structural):
- `resolve_relationships` and `resolve_governance` delegate to the v0.4 G3 resolver
  verbatim → discovery, classification, validation, governing set, and Mode G are
  bit-identical to G3.
- `_derive` delegates to the frozen packet builder → Mode P bit-identical.
- With C0 the resolver reproduces G3 exactly. C1–C3 build the operative representation
  without changing the decision. Only C4 can add abstention, and only on a genuinely
  unresolved conflict.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import (
    GovernanceResolution, ResolutionResult, ResolvedEvidenceGraph,
)

from ..experiment_v4 import governance_semantics as GS
from ..experiment_v4.hybrid_resolver_v4 import HybridRelationshipResolverV4
from . import competing_operative as CO


class HybridRelationshipResolverV5:
    name = "hybrid_relationship_v5"

    def __init__(self, config: CO.Config | None = CO.ABLATIONS["C4_full"]):
        self.cfg = config                                     # None => C0 (G3 control)
        self._g3 = HybridRelationshipResolverV4(GS.ABLATIONS["G3_operative"])
        self._g3cfg = GS.ABLATIONS["G3_operative"]
        self._last = None

    # ---------- protected stages: delegated to G3 (unchanged) ---------- #
    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        return self._g3.resolve_relationships(question, evidence)

    def resolve_governance(self, question, graph) -> GovernanceResolution:
        return self._g3.resolve_governance(question, graph)   # frozen governing set → Mode G identical

    def _derive(self, graph, gov):
        return self._g3._derive(graph, gov)                    # frozen packet → Mode P identical

    # ---------- full pipeline ---------- #
    def resolve(self, question, evidence) -> ResolutionResult:
        if self.cfg is None:
            return self._g3.resolve(question, evidence)        # C0 == G3 exactly

        graph = self._g3.resolve_relationships(question, evidence)
        conf = dict(self._g3._v2._conf)
        # G3 governance result (governing set + operative source) — unchanged
        gr = GS.analyze(graph, question, conf, self._g3cfg)
        if gr.governance_abstention:  # inherited frozen abstention (cycle/version/dangling)
            gov_graph, gov = GS.adapt(graph, gr)
            tfc, notice, penalty = self._g3._derive(gov_graph, gov)
            return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)

        operative = gr.operative_nodes[0] if gr.operative_nodes else None
        opset = CO.resolve(graph, gr.frozen_governing, operative, conf, self.cfg)
        self._last = opset

        if opset.operative_abstention:
            gov = GovernanceResolution(abstain=True, abstain_reason=opset.operative_abstention_reason,
                                       discarded={k: "displaced" for k in gr.displaced_nodes})
            return ResolutionResult(graph=graph, governance=gov, tfc="unknown", notice_days=None, penalty=None)

        # no genuine conflict → keep the G3 decision exactly
        gov_graph, gov = GS.adapt(graph, gr)
        tfc, notice, penalty = self._g3._derive(gov_graph, gov)
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)

    # ---------- reporting ---------- #
    def operative_set(self, question, evidence) -> dict:
        if self.cfg is None:
            return {"control": "G3"}
        graph = self._g3.resolve_relationships(question, evidence)
        conf = dict(self._g3._v2._conf)
        gr = GS.analyze(graph, question, conf, self._g3cfg)
        operative = gr.operative_nodes[0] if gr.operative_nodes else None
        return CO.resolve(graph, gr.frozen_governing, operative, conf, self.cfg).as_dict()

    def intermediate_artifacts(self, question, evidence) -> dict:
        res = self.resolve(question, evidence)
        return {"operative_set": self.operative_set(question, evidence),
                "governing": res.governance.governing, "abstain": res.governance.abstain,
                "abstain_reason": res.governance.abstain_reason,
                "packet": {"tfc": res.tfc, "notice_days": res.notice_days, "penalty": res.penalty}}
