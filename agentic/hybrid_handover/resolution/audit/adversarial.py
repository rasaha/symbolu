#!/usr/bin/env python3
"""
Adversarial "cheating" resolvers — deliberately weak strategies that do NO
genuine relationship reasoning. If any of these scores highly on a component
metric, that metric is gameable and cannot be trusted as evidence of relationship
reasoning.

Each implements the resolver interface (resolve_relationships / resolve_governance
/ resolve). They build a (usually empty) graph and a trivial governance decision.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import (
    GovernanceResolution,
    ResolutionResult,
    ResolvedEvidenceGraph,
)
from agentic.hybrid_handover.resolution.parse import parse_nodes


class _Base:
    name = "adv"

    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        return ResolvedEvidenceGraph(nodes=parse_nodes(evidence), edges=[])

    def resolve_governance(self, question, graph) -> GovernanceResolution:
        return GovernanceResolution()

    def _answer_from(self, node):
        if not node:
            return "unknown", None, None
        a = node.attrs
        tfc = "prohibited" if a.get("negation") or a.get("policy_override") else \
              ("allowed" if a.get("allows") else "unknown")
        return tfc, a.get("notice_days"), (
            f"{a['penalty_months']} months' fees" if a.get("penalty_months") else None)

    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self.resolve_relationships(question, evidence)
        gov = self.resolve_governance(question, graph)
        node = None
        if gov.governing:
            node = graph.node(gov.governing[0])
        tfc, notice, penalty = ("unknown", None, None) if gov.abstain else self._answer_from(node)
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)


class AlwaysAbstain(_Base):
    name = "always_abstain"

    def resolve_governance(self, question, graph):
        return GovernanceResolution(abstain=True, abstain_reason="cheat: always abstain")


class AlwaysFirstDocument(_Base):
    name = "always_first_document"

    def resolve_governance(self, question, graph):
        clauses = [n for n in graph.nodes if n.type in ("Clause", "Policy")]
        return GovernanceResolution(governing=[clauses[0].key] if clauses else [])


class AlwaysLatest(_Base):
    name = "always_latest"

    def resolve_governance(self, question, graph):
        clauses = [n for n in graph.nodes if n.type in ("Clause", "Policy")]
        if not clauses:
            return GovernanceResolution()
        last = max(clauses, key=lambda n: n.attrs.get("order", 0))
        return GovernanceResolution(governing=[last.key])


class AlwaysOverride(_Base):
    """Assume the highest-order node overrides everything (always 'the last word wins')."""
    name = "always_override"

    def resolve_governance(self, question, graph):
        clauses = [n for n in graph.nodes if n.type in ("Clause", "Policy")]
        if not clauses:
            return GovernanceResolution()
        last = max(clauses, key=lambda n: n.attrs.get("order", 0))
        disc = {n.key: "assumed_overridden" for n in clauses if n.key != last.key}
        return GovernanceResolution(governing=[last.key], discarded=disc)


class AlwaysAllowed(_Base):
    name = "always_allowed"

    def resolve(self, question, evidence):
        graph = self.resolve_relationships(question, evidence)
        # ignore everything; assert allowed with a guessed notice
        notice = next((n.attrs.get("notice_days") for n in graph.nodes
                       if n.attrs.get("notice_days")), None)
        return ResolutionResult(graph=graph, governance=GovernanceResolution(),
                                tfc="allowed", notice_days=notice, penalty=None)


class NullResolver(_Base):
    name = "null"  # empty graph, no governance, unknown answer


ADVERSARIAL = {
    "always_abstain": AlwaysAbstain,
    "always_first_document": AlwaysFirstDocument,
    "always_latest": AlwaysLatest,
    "always_override": AlwaysOverride,
    "always_allowed": AlwaysAllowed,
    "null": NullResolver,
}
ADVERSARIAL_ORDER = list(ADVERSARIAL)
