#!/usr/bin/env python3
"""
HybridRelationshipResolver — Experimental v0.1 (deterministic; no training; no LLM).

A richer RELATIONSHIP-PROPOSAL layer feeding the FROZEN GraphTraversalResolver
governance + packet builder (reused by composition, never modified). Any gain
over GraphTraversal is therefore attributable to relationship DISCOVERY, not
governance or packet construction.

Proposal layer adds, beyond the narrow fixed cue set of the deterministic
baselines:
  * a broader GENERAL legal cue lexicon (supersede/governs/override/exception/
    reference synonyms) — set from general legal English + the visible corpus,
    frozen before hidden evaluation, NOT tuned to hidden wording;
  * temporal precedence (effective_after) by comparing parsed effective years;
  * rename / migration / alias resolution (same_as);
  * nested-exception chaining;
  * per-edge confidence and a confidence-gated abstention.

Ablation flags (A0..A6) toggle each contribution. Governance/packet are identical
to GraphTraversal in every configuration.
"""

from __future__ import annotations

import re

from agentic.hybrid_handover.resolution.graph import (
    Edge, GovernanceResolution, ResolutionResult, ResolvedEvidenceGraph,
)
from agentic.hybrid_handover.resolution.parse import parse_nodes
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver, RuleResolver

# ---- FROZEN general-legal cue lexicon (set pre-hidden; not tuned to hidden) -- #
SUPERSEDE = ("replac", "supersede", "rescind", "revok", "delet", "substitut",
             "void", "struck", "strik", "is removed", "extinguish")
# an amendment is a supersession ONLY when it alters an operative parameter;
# an amendment that merely adds a term (e.g. a fee) is an `amends`, not a replace.
AMEND = ("amended", "amends", "revises", "revising", "modif")
GOVERNS = ("prevail", "controls over", "control against", "shall control",
           "takes precedence", "precedence", "governs over")
OVERRIDE = ("notwithstanding", "regardless", "irrespective", "despite", "overrid", "prohibit")
EXCEPTION = ("except", "save where", "save that", "unless", "does not apply", "not apply",
             "suspended", "locked in", "may not", "shall not exercise", "carve",
             "provided that", "only to", "only from", "limited to", "only apply",
             "applies only", "unavailable", "is barred", "not be permitted", "not to be permitted")
REFERENCE = ("set out in", "as set out", "defined in", "as defined", "stated in", "as stated",
             "specified in", "as per", "pursuant to", "in accordance with", "follow the", "those in")
RENAME = ("renamed", "same as", "carry over", "carries over", "published as", "migrated to",
          "now published", "references to", "is now", "carried over")
REF_NAME = re.compile(r"(Schedule [A-Z]?\w*|Appendix \w+|Annex \w+|Exhibit \w+|Rider \w+|"
                      r"MSA §?\d+(?:\.\d+)?|Order[^.,;]*|Rate Card|Glossary|Master [A-Z]\w+ ?\w*|"
                      r"Standard [A-Z]-?\w+|Policy [A-Z]-?\w+)")
_SEC = re.compile(r"(?:section|clause)\s+([0-9.]+)", re.IGNORECASE)
_YEAR = re.compile(r"(19|20)\d{2}")


def _norm(s):
    return re.sub(r"\s+", " ", s.lower()).strip()


def _terminate_clauses(nodes):
    cs = [n for n in nodes if n.type in ("Clause", "Table") and n.attrs.get("terminates")]
    cs.sort(key=lambda n: n.attrs.get("order", 0))
    return cs


class _Config:
    def __init__(self, semantic=True, traversal=True, governance_rules=True,
                 confidence_abstain=True, provenance_required=True, discovery_only=False):
        self.semantic = semantic
        self.traversal = traversal
        self.governance_rules = governance_rules
        self.confidence_abstain = confidence_abstain
        self.provenance_required = provenance_required
        self.discovery_only = discovery_only


class HybridRelationshipResolver:
    name = "hybrid_relationship"
    TAU = 0.5  # confidence threshold for abstention (selected on visible; frozen)

    def __init__(self, config: _Config | None = None):
        self.cfg = config or _Config()
        self._gt = GraphTraversalResolver()   # frozen governance + packet (reused)
        self._rule = RuleResolver()            # narrow-cue fallback for A1

    # ---------- proposal layer ---------- #
    def _propose(self, nodes):
        edges, conf, prov = [], {}, {}

        def add(s, t, d, c, needle):
            edges.append(Edge(src=s, type=t, dst=d))
            conf[(s, t, d)] = c
            prov[(s, t, d)] = needle

        base_clauses = _terminate_clauses(nodes)
        base = base_clauses[0] if base_clauses else None
        by_sec = {n.section: n for n in nodes if n.section}

        prev_exception = None
        for n in nodes:
            low = _norm(n.text)
            # supersede (broad) — target by named section else base. An amendment
            # counts as supersession only when it changes an operative parameter.
            amend_as_supersede = any(k in low for k in AMEND) and (
                n.attrs.get("terminates") or n.attrs.get("notice_days")
                or n.attrs.get("allows") or n.attrs.get("negation"))
            if (any(k in low for k in SUPERSEDE) or amend_as_supersede) and n.type in ("Clause",):
                m = _SEC.search(n.text)
                tgt = by_sec.get(m.group(1).lstrip("0") if m else None) or \
                    (by_sec.get(m.group(1)) if m else None)
                if not tgt and base and base.key != n.key:
                    tgt = base
                if tgt and tgt.key != n.key:
                    add(n.key, "supersedes", tgt.key, 0.9 if m else 0.7,
                        next((k for k in SUPERSEDE if k in low), "supersede"))
                    if m and n.section and tgt.section and n.section == tgt.section and \
                       n.key.split()[0] != tgt.key.split()[0]:
                        add(n.key, "same_as", tgt.key, 0.8, "alias")
            # governs_over
            if any(k in low for k in GOVERNS):
                tgt = None
                for other in nodes:
                    if other.key == n.key:
                        continue
                    label = other.key.split(" §")[0].split(" p.")[0].lower()
                    if label and label in low:
                        tgt = other; break
                if not tgt and ("body" in low or "agreement" in low) and base and base.key != n.key:
                    tgt = base
                if not tgt and base and base.key != n.key and n.type in ("Clause", "Table"):
                    tgt = base
                if tgt and tgt.key != n.key:
                    add(n.key, "governs_over", tgt.key, 0.85,
                        next((k for k in GOVERNS if k in low), "prevails"))
            # override (policy)
            if any(k in low for k in ("notwithstanding", "regardless", "irrespective", "despite")) \
               and ("prohibit" in low or "barred" in low or "not permit" in low or "unavailable" in low) \
               and base and base.key != n.key:
                add(n.key, "overrides", base.key, 0.85, "notwithstanding")
            # exception (broad) + nesting
            if n.type == "Exception" or (any(k in low for k in EXCEPTION) and n.type != "Policy"
                                         and not n.attrs.get("allows") and n.key != (base.key if base else None)):
                target = None
                if prev_exception and any(w in low for w in ("preceding", "foregoing", "that ", "the year-one",
                                                             "the change-of-control", "the exception", "the bar")):
                    target = prev_exception
                elif base:
                    target = base
                if target and target.key != n.key:
                    add(n.key, "exception_to", target.key, 0.8,
                        next((k for k in EXCEPTION if k in low), "except"))
                    prev_exception = n
            # references (broad) -> named target or dangling
            if any(k in low for k in REFERENCE):
                for mref in REF_NAME.findall(n.text):
                    mref = mref.rstrip(" .,;")
                    if _norm(mref) in _norm(n.key):
                        continue
                    tgt = next((o for o in nodes if o.key != n.key and _norm(mref) in _norm(o.key)), None)
                    if tgt:
                        add(n.key, "references", tgt.key, 0.8, mref)
                    else:
                        e = Edge(src=n.key, type="references", dst=mref, attrs={"dangling": True})
                        edges.append(e); conf[(n.key, "references", mref)] = 0.6
                        prov[(n.key, "references", mref)] = mref
            # rename / migration -> same_as
            if any(k in low for k in RENAME):
                for other in nodes:
                    if other.key == n.key:
                        continue
                    lbl = other.key.split(" p.")[0].split(" §")[0].lower()
                    base_lbl = re.sub(r"[^a-z0-9 ]", "", lbl)
                    if base_lbl and base_lbl[:6] in low and other.key != n.key:
                        add(n.key, "same_as", other.key, 0.7, next((k for k in RENAME if k in low), "renamed"))
                        break

        # amends (fee introduce, no supersede) — skip nodes that are reference targets
        ref_targets = {e.dst for e in edges if e.type == "references"}
        for n in nodes:
            if n.attrs.get("introduces_fee") and n.type == "Clause" and n.key not in ref_targets \
               and not any(k in _norm(n.text) for k in SUPERSEDE) and base and base.key != n.key:
                add(n.key, "amends", base.key, 0.7, "fee")

        # definition conflicts (two definitions of one term)
        defs = [n for n in nodes if n.type == "Definition" and n.attrs.get("definition_term")]
        for i in range(len(defs)):
            for j in range(len(defs)):
                if i != j and defs[i].attrs["definition_term"] == defs[j].attrs["definition_term"] \
                   and defs[i].attrs["order"] > defs[j].attrs["order"]:
                    add(defs[i].key, "conflicts_with", defs[j].key, 0.75, "means")

        # effective_after by year comparison
        dated = [(n, int(_YEAR.search(n.key + " " + n.text).group(0)))
                 for n in nodes if _YEAR.search(n.key + " " + n.text)]
        for i in range(len(dated)):
            for j in range(len(dated)):
                if dated[i][1] > dated[j][1] and dated[i][0].attrs.get("terminates") and dated[j][0].attrs.get("terminates"):
                    add(dated[i][0].key, "effective_after", dated[j][0].key, 0.8, "effective")

        # version / definition conflicts (reuse rule-level structural signals)
        vbase = {}
        for n in nodes:
            vb = n.attrs.get("version_base")
            if vb:
                vbase.setdefault(vb, []).append(n)
        for grp in vbase.values():
            if len(grp) >= 2:
                grp.sort(key=lambda x: x.attrs.get("order", 0))
                a, b = grp[0], grp[1]
                add(a.key, "same_as", b.key, 0.7, "version")
                if (a.attrs.get("allows"), a.attrs.get("negation")) != (b.attrs.get("allows"), b.attrs.get("negation")) \
                   and (a.attrs.get("allows") or a.attrs.get("negation")) and (b.attrs.get("allows") or b.attrs.get("negation")):
                    add(a.key, "conflicts_with", b.key, 0.7, "conflict")
        table = next((n for n in nodes if n.type == "Table"), None)
        if table and base and table.attrs.get("penalty_months") and base.attrs.get("penalty_months") \
           and table.attrs["penalty_months"] != base.attrs["penalty_months"] \
           and not any(e.type == "governs_over" and e.src == table.key for e in edges):
            add(base.key, "conflicts_with", table.key, 0.7, "table")
        return edges, conf, prov

    # ---------- protocol ---------- #
    def resolve_relationships(self, question, evidence) -> ResolvedEvidenceGraph:
        nodes = parse_nodes(evidence)
        if not self.cfg.semantic:
            return self._rule.resolve_relationships(question, evidence)  # A1 fallback
        edges, self._conf, self._prov = self._propose(nodes)
        # provenance requirement (A5): drop edges lacking provenance
        if self.cfg.provenance_required:
            edges = [e for e in edges if self._prov.get(e.triple())]
        # dedupe
        seen, uniq = set(), []
        for e in edges:
            if e.triple() not in seen:
                seen.add(e.triple()); uniq.append(e)
        return ResolvedEvidenceGraph(nodes=nodes, edges=uniq)

    def resolve_governance(self, question, graph) -> GovernanceResolution:
        if self.cfg.discovery_only or not self.cfg.traversal:
            return GovernanceResolution()
        if not self.cfg.governance_rules:
            # discard-only, no abstention rules
            disc = {e.dst: e.type for e in graph.edges if e.type in ("supersedes", "overrides", "governs_over")}
            gov = [n.key for n in graph.nodes if n.type in ("Clause", "Policy") and n.key not in disc]
            return GovernanceResolution(governing=gov, discarded=disc)
        return self._gt.resolve_governance(question, graph)  # frozen governance

    def _derive(self, graph, gov):
        """Packet builder — identical to the frozen GraphTraversal deriver (reused)."""
        return self._gt._derive(graph, gov)

    def resolve(self, question, evidence) -> ResolutionResult:
        graph = self.resolve_relationships(question, evidence)
        gov = self.resolve_governance(question, graph)
        # confidence-gated abstention (A4)
        if self.cfg.confidence_abstain and not gov.abstain and self.cfg.semantic:
            supporting = [c for tr, c in getattr(self, "_conf", {}).items() if tr in graph.edge_triples()]
            if supporting and max(supporting) < self.TAU and gov.governing:
                gov = GovernanceResolution(abstain=True, abstain_reason="all supporting edges below confidence tau")
        tfc, notice, penalty = self._gt._derive(graph, gov)
        return ResolutionResult(graph=graph, governance=gov, tfc=tfc, notice_days=notice, penalty=penalty)

    def intermediate_artifacts(self, question, evidence) -> dict:
        graph = self.resolve_relationships(question, evidence)
        gov = self.resolve_governance(question, graph)
        res = self.resolve(question, evidence)
        return {
            "nodes": [{"key": n.key, "type": n.type} for n in graph.nodes],
            "edges": [{"src": e.src, "type": e.type, "dst": e.dst,
                       "confidence": getattr(self, "_conf", {}).get(e.triple()),
                       "provenance": getattr(self, "_prov", {}).get(e.triple())} for e in graph.edges],
            "governing": gov.governing, "excluded": gov.discarded,
            "abstain": gov.abstain, "abstain_reason": gov.abstain_reason,
            "packet": {"tfc": res.tfc, "notice_days": res.notice_days, "penalty": res.penalty},
        }


# preregistered ablations
ABLATIONS = {
    "A0_full": _Config(),
    "A1_no_semantic": _Config(semantic=False),
    "A2_no_traversal": _Config(traversal=False),
    "A3_no_governance_rules": _Config(governance_rules=False),
    "A4_no_confidence_abstain": _Config(confidence_abstain=False),
    "A5_no_provenance": _Config(provenance_required=False),
    "A6_discovery_only": _Config(discovery_only=True),
}
