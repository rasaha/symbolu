#!/usr/bin/env python3
"""
Baseline resolvers — deterministic scientific reference points. No ML, no tuning
toward benchmark scores. Three reference behaviours:

  FrozenResolver          — reproduces the current handover behaviour: it only
                            recognises the single prohibition→grant supersession
                            pattern and delegates answer derivation to the frozen
                            InHouseExtractor. Everything else is invisible to it.
  RuleResolver            — simple deterministic relationship rules (override,
                            governs_over, supersede, exception, definition-
                            conflict, section alias, reference, fee-amends) +
                            precedence governance. Does NOT abstain.
  GraphTraversalResolver  — RuleResolver's graph + traversal: cycle detection,
                            version-conflict and dangling-reference abstention,
                            numeric-conflict flagging.

These are reference baselines; a future HybridPhaseTransformer / SymbolU resolver
implements the same interface and is measured identically.
"""

from __future__ import annotations

from agentic.hybrid_handover.inhouse import InHouseExtractor
from agentic.hybrid_handover.schema import Corpus, Document, EvidenceSpan

from .graph import (
    Edge,
    GovernanceResolution,
    Node,
    ResolutionResult,
    ResolvedEvidenceGraph,
)
from .parse import parse_nodes

_INHOUSE = InHouseExtractor()


def _mini_corpus(evidence: list[EvidenceSpan]) -> Corpus:
    docs: dict[str, Document] = {}
    order = 0
    for s in evidence:
        if s.doc_id not in docs:
            docs[s.doc_id] = Document(doc_id=s.doc_id, citation=s.citation, order=order, text="")
            order += 1
        docs[s.doc_id].text = (docs[s.doc_id].text + " " + s.quote).strip()
    return Corpus(documents=list(docs.values()))


def _find(nodes, pred):
    for n in nodes:
        if pred(n):
            return n
    return None


def _clause_terminate(nodes):
    cands = [n for n in nodes if n.type in ("Clause",) and n.attrs.get("terminates")]
    cands.sort(key=lambda n: n.attrs.get("order", 0))
    return cands[0] if cands else None


# --------------------------------------------------------------------------- #
class FrozenResolver:
    name = "frozen"

    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        nodes = parse_nodes(evidence)
        edges = []
        prohibition = _find(nodes, lambda n: n.attrs.get("negation") and n.attrs.get("terminates"))
        grant = _find(nodes, lambda n: n.attrs.get("allows"))
        if prohibition and grant and prohibition.key != grant.key:
            edges.append(Edge(src=grant.key, type="supersedes", dst=prohibition.key))
        return ResolvedEvidenceGraph(nodes=nodes, edges=edges)

    def resolve_governance(self, question, graph) -> GovernanceResolution:
        superseded = {e.dst for e in graph.edges if e.type == "supersedes"}
        governing = [n.key for n in graph.nodes if n.type in ("Clause", "Policy") and n.key not in superseded]
        return GovernanceResolution(governing=governing, discarded={k: "superseded" for k in superseded})

    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self.resolve_relationships(question, evidence)
        gov = self.resolve_governance(question, graph)
        ans = _INHOUSE.resolve(question, _mini_corpus(evidence))  # current behaviour
        return ResolutionResult(graph=graph, governance=gov,
                                tfc=ans.termination_for_convenience,
                                notice_days=ans.notice_days, penalty=ans.penalty)


# --------------------------------------------------------------------------- #
class RuleResolver:
    name = "rule"
    ABSTAINS = False

    # ---- stage 2: relationships ----
    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        nodes = parse_nodes(evidence)
        edges: list[Edge] = []
        base = _clause_terminate(nodes)

        for n in nodes:
            # supersede (+ alias if section strings differ)
            tgt_sec = n.attrs.get("supersede_target")
            if tgt_sec:
                tgt = _find(nodes, lambda m, s=tgt_sec: m.key != n.key and m.section == s)
                if tgt:
                    edges.append(Edge(src=n.key, type="supersedes", dst=tgt.key))
                    if n.section and tgt.section and n.section == tgt.section and \
                       n.key.split()[0] != tgt.key.split()[0]:
                        edges.append(Edge(src=n.key, type="same_as", dst=tgt.key))
            # governs_over
            if n.attrs.get("governs_over_target"):
                tgt = _find(nodes, lambda m: m.key.lower().startswith(n.attrs["governs_over_target"]))
                if tgt and tgt.key != n.key:
                    edges.append(Edge(src=n.key, type="governs_over", dst=tgt.key))
            # policy override
            if n.attrs.get("policy_override") and base is not None and base.key != n.key:
                edges.append(Edge(src=n.key, type="overrides", dst=base.key))
            # exception
            if n.type == "Exception" and base is not None and base.key != n.key:
                edges.append(Edge(src=n.key, type="exception_to", dst=base.key))
            # references — resolve by target IDENTITY (citation), not by text
            # mention; skip a node's own title (e.g. a "Schedule C" heading).
            for ref in n.attrs.get("references", []):
                if ref.lower() in n.key.lower():
                    continue  # self-title, not a cross-reference
                tgt = _find(nodes, lambda m, r=ref: m.key != n.key and r.lower() in m.key.lower())
                if tgt:
                    edges.append(Edge(src=n.key, type="references", dst=tgt.key))
                else:
                    edges.append(Edge(src=n.key, type="references", dst=ref, attrs={"dangling": True}))
            # fee amends
            if n.attrs.get("introduces_fee") and n.type == "Clause" and not tgt_sec \
               and base is not None and base.key != n.key:
                edges.append(Edge(src=n.key, type="amends", dst=base.key))

        # definition conflicts (same term)
        defs = [n for n in nodes if n.type == "Definition" and n.attrs.get("definition_term")]
        for i in range(len(defs)):
            for j in range(len(defs)):
                if i != j and defs[i].attrs["definition_term"] == defs[j].attrs["definition_term"] \
                   and defs[i].attrs["order"] > defs[j].attrs["order"]:
                    edges.append(Edge(src=defs[i].key, type="conflicts_with", dst=defs[j].key))

        # version same_as / conflicts_with (same amendment base label)
        vbase: dict[str, list[Node]] = {}
        for n in nodes:
            vb = n.attrs.get("version_base")
            if vb:
                vbase.setdefault(vb, []).append(n)
        for vb, group in vbase.items():
            if len(group) >= 2:
                group.sort(key=lambda n: n.attrs.get("order", 0))
                a, b = group[0], group[1]
                edges.append(Edge(src=a.key, type="same_as", dst=b.key))
                va = a.attrs.get("allows"); na = a.attrs.get("negation")
                vb2 = b.attrs.get("allows"); nb = b.attrs.get("negation")
                if (va, na) != (vb2, nb) and (va or na) and (vb2 or nb):
                    edges.append(Edge(src=a.key, type="conflicts_with", dst=b.key))

        # table vs prose numeric conflict
        table = _find(nodes, lambda n: n.type == "Table")
        if table and base is not None and table.attrs.get("penalty_months") and \
           base.attrs.get("penalty_months") and table.attrs["penalty_months"] != base.attrs["penalty_months"]:
            edges.append(Edge(src=base.key, type="conflicts_with", dst=table.key))

        return ResolvedEvidenceGraph(nodes=nodes, edges=edges)

    # ---- stage 3: governance ----
    def _abstain(self, graph):
        return None  # RuleResolver never abstains

    def resolve_governance(self, question, graph) -> GovernanceResolution:
        ab = self._abstain(graph)
        if ab:
            return ab
        discarded = {}
        for e in graph.edges:
            if e.type in ("supersedes", "overrides", "governs_over"):
                discarded[e.dst] = e.type
        governing = [n.key for n in graph.nodes
                     if n.type in ("Clause", "Policy") and n.key not in discarded]
        # include referenced value clauses (cross-doc penalty carriers)
        for e in graph.edges:
            if e.type == "references":
                tgt = graph.node(e.dst)
                if tgt and tgt.type == "Clause" and e.dst not in governing and e.dst not in discarded:
                    governing.append(e.dst)
        return GovernanceResolution(governing=governing, discarded=discarded)

    # ---- stage 4: packet construction ----
    def _derive(self, graph, gov):
        if gov.abstain:
            return "unknown", None, None
        winners = [graph.node(k) for k in gov.governing]
        winners = [w for w in winners if w]
        # primary = a governs_over/overrides/supersedes source if present, else lone clause
        srcs = {e.src for e in graph.edges if e.type in ("overrides", "governs_over", "supersedes")}
        primary = next((w for w in winners if w.key in srcs), None) or \
                  next((w for w in winners if w.type in ("Policy", "Clause")), None)
        tfc, notice, penalty = "unknown", None, None
        if primary:
            if primary.type == "Policy" or primary.attrs.get("policy_override") or primary.attrs.get("negation"):
                tfc = "prohibited"
            elif primary.attrs.get("allows"):
                tfc = "allowed"
            notice = primary.attrs.get("notice_days")
        # penalty from amends source or referenced clause; unresolved if conflict
        conflict_pen = any(e.type == "conflicts_with" and
                           (graph.node(e.dst) and graph.node(e.dst).type == "Table")
                           for e in graph.edges)
        if not conflict_pen:
            for w in winners:
                if w.attrs.get("penalty_months"):
                    penalty = f"{w.attrs['penalty_months']} months' fees"
            for e in graph.edges:
                if e.type == "amends":
                    src = graph.node(e.src)
                    if src and src.attrs.get("penalty_months"):
                        penalty = f"{src.attrs['penalty_months']} months' fees"
        return tfc, notice, penalty

    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self.resolve_relationships(question, evidence)
        gov = self.resolve_governance(question, graph)
        tfc, notice, penalty = self._derive(graph, gov)
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc,
                                notice_days=notice, penalty=penalty)


# --------------------------------------------------------------------------- #
class GraphTraversalResolver(RuleResolver):
    name = "graph_traversal"
    ABSTAINS = True

    def _has_cycle(self, graph) -> bool:
        adj: dict[str, list[str]] = {}
        for e in graph.edges:
            if e.type == "references":
                adj.setdefault(e.src, []).append(e.dst)
        # detect any back-edge among reference nodes
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {}

        def dfs(u):
            color[u] = GRAY
            for v in adj.get(u, []):
                if color.get(v, WHITE) == GRAY:
                    return True
                if color.get(v, WHITE) == WHITE and v in adj and dfs(v):
                    return True
            color[u] = BLACK
            return False

        return any(color.get(n, WHITE) == WHITE and dfs(n) for n in list(adj))

    def _abstain(self, graph):
        # cycle
        if self._has_cycle(graph):
            return GovernanceResolution(abstain=True, abstain_reason="circular reference; no ground term")
        # version conflict
        if any(e.type == "conflicts_with" and
               graph.node(e.src) and graph.node(e.src).type == "Version" and
               graph.node(e.dst) and graph.node(e.dst).type == "Version"
               for e in graph.edges):
            return GovernanceResolution(abstain=True, abstain_reason="unresolvable version conflict")
        # dangling / unusable reference
        for e in graph.edges:
            if e.type == "references":
                if e.attrs.get("dangling"):
                    return GovernanceResolution(abstain=True, abstain_reason="referenced document absent")
                tgt = graph.node(e.dst)
                if tgt and tgt.type == "Document" and tgt.attrs.get("unusable"):
                    return GovernanceResolution(abstain=True, abstain_reason="referenced document not machine-readable")
        return None


ALL_RESOLVERS = {
    "frozen": FrozenResolver,
    "rule": RuleResolver,
    "graph_traversal": GraphTraversalResolver,
}
RESOLVER_ORDER = ["frozen", "rule", "graph_traversal"]
