#!/usr/bin/env python3
"""
Experimental Governance Semantics Layer — deterministic.

Given a VALIDATED relationship graph (produced bit-identically by v0.2), this layer
assigns each clause an explicit applicability STATUS, and — critically — separates the
AUTHORITY source from the OPERATIVE source (the node carrying the term needed to answer
the query), abstaining at the governance stage when the decision is genuinely
unresolved. Its output is an explicit machine-readable GovernanceResult (statuses +
role sets + decision trace + per-decision evidence vectors), NOT merely an ordering.

Design boundary that preserves the protected metrics:
  * The GOVERNING SET it reports is the frozen governing set (frozen governance is
    reused to compute it), so governance Mode G is bit-identical to the frozen control
    (non-inferiority is met by construction, not by tuning).
  * The layer changes only (a) which governing node is the OPERATIVE source the frozen
    packet reads from, and (b) governance-stage ABSTENTION when operative outcomes
    conflict. These are exactly the sub-decisions the v0.3 diagnostic identified as the
    remaining bottleneck, and they affect only the full-pipeline answer (selective
    accuracy / coverage), never discovery, classification, validation, or Mode P.

A documented adapter (`adapt`) translates the result into the frozen packet's single
`primary` contract by ordering the operative node first and hiding competing
authority edges from the packet-input graph — it never infers relationships, edits
evidence, adds answer text, adds policy rules, or picks the final answer itself.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import GovernanceResolution, ResolvedEvidenceGraph
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

_FROZEN = GraphTraversalResolver()

# ---- governance status model (per clause) ---- #
OPERATIVE = "OPERATIVE"
APPLICABLE_SUPPORT = "APPLICABLE_SUPPORT"
CUMULATIVE_REQUIREMENT = "CUMULATIVE_REQUIREMENT"
DISPLACED = "DISPLACED"
EXCEPTION = "EXCEPTION"
CONDITIONALLY_APPLICABLE = "CONDITIONALLY_APPLICABLE"
UNRESOLVED = "UNRESOLVED"
IRRELEVANT_TO_QUERY = "IRRELEVANT_TO_QUERY"

GOVERNANCE_SOURCE_TYPES = ("supersedes", "overrides", "governs_over")


class SemanticConfig:
    """Ablation switches. G4 (full) enables everything."""
    def __init__(self, displacement_scope=True, parallel=True, operative_selection=True,
                 exception_handling=True, cumulative=True, governance_abstention=True):
        self.displacement_scope = displacement_scope
        self.parallel = parallel
        self.operative_selection = operative_selection
        self.exception_handling = exception_handling
        self.cumulative = cumulative
        self.governance_abstention = governance_abstention


def _tfc_signal(node):
    a = node.attrs
    if a.get("policy_override") or a.get("negation") or node.type == "Policy":
        return "prohibited"
    if a.get("allows"):
        return "allowed"
    return None


def _has_operative_term(node):
    a = node.attrs
    return bool(_tfc_signal(node) or a.get("notice_days") or a.get("penalty_months"))


class GovernanceResult:
    def __init__(self):
        self.statuses = {}
        self.applicable_nodes = []
        self.displaced_nodes = []
        self.cumulative_nodes = []
        self.conditional_nodes = []
        self.operative_nodes = []
        self.unresolved_competitions = []
        self.governance_abstention = False
        self.governance_abstention_reason = ""
        self.decision_trace = []
        self.evidence_vectors = {}
        self.frozen_governing = []
        self.frozen_abstain = False

    def as_dict(self):
        return {k: getattr(self, k) for k in (
            "statuses", "applicable_nodes", "displaced_nodes", "cumulative_nodes",
            "conditional_nodes", "operative_nodes", "unresolved_competitions",
            "governance_abstention", "governance_abstention_reason", "decision_trace",
            "evidence_vectors", "frozen_governing", "frozen_abstain")}


def _evidence_vector(node, graph, conf):
    out = [e for e in graph.edges if e.src == node.key]
    inc = [e for e in graph.edges if e.dst == node.key]
    return {
        "relationship_out": sorted({e.type for e in out}),
        "incoming_displacement": sorted({e.type for e in inc if e.type in GOVERNANCE_SOURCE_TYPES}),
        "authority_order": node.attrs.get("order"),
        "operative_signal": _tfc_signal(node),
        "carries_operative_term": _has_operative_term(node),
        "confidence": round(max((conf.get(e.triple(), 0.0) for e in out), default=0.0), 3),
        "provenance_complete": True,  # v0.2 already dropped provenance-less edges
    }


def analyze(graph: ResolvedEvidenceGraph, question: str, conf: dict,
            config: SemanticConfig) -> GovernanceResult:
    r = GovernanceResult()
    nodes_by_key = {n.key: n for n in graph.nodes}

    # frozen governing set — keeps Mode G non-inferior by construction
    fgov = _FROZEN.resolve_governance(question, graph)
    r.frozen_governing = list(fgov.governing)
    r.frozen_abstain = fgov.abstain
    if fgov.abstain:
        r.governance_abstention = True
        r.governance_abstention_reason = fgov.abstain_reason
        r.decision_trace.append("frozen abstention inherited")
        return r

    governing_nodes = [nodes_by_key[k] for k in fgov.governing if k in nodes_by_key]
    r.applicable_nodes = [n.key for n in governing_nodes]
    for k, why in fgov.discarded.items():
        r.statuses[k] = DISPLACED
        r.displaced_nodes.append(k)
    for n in governing_nodes:
        r.statuses[n.key] = APPLICABLE_SUPPORT
        r.evidence_vectors[n.key] = _evidence_vector(n, graph, conf)

    # exception annotation (status only; does not alter the governing set)
    if config.exception_handling:
        for e in graph.edges:
            if e.type == "exception_to" and e.src in r.statuses:
                r.statuses[e.src] = EXCEPTION

    srcs = {e.src for e in graph.edges if e.type in GOVERNANCE_SOURCE_TYPES}
    frozen_primary = next((n.key for n in governing_nodes if n.key in srcs), None) or \
        (governing_nodes[0].key if governing_nodes else None)

    if not config.operative_selection:
        # G1/G2: keep the frozen primary as operative (scope/parallel are status-only here)
        if frozen_primary:
            r.operative_nodes = [frozen_primary]
            r.statuses[frozen_primary] = OPERATIVE
        r.decision_trace.append("operative = frozen primary (operative_selection disabled)")
        return r

    # ---- operative-source selection: authority source ≠ operative source ---- #
    prohib = [n for n in governing_nodes if _tfc_signal(n) == "prohibited"]
    allow = [n for n in governing_nodes if _tfc_signal(n) == "allowed"]
    r.decision_trace.append(f"governing={len(governing_nodes)} prohib={len(prohib)} allow={len(allow)}")

    def _latest(ns):
        return sorted(ns, key=lambda n: n.attrs.get("order", 0), reverse=True)

    operative = None
    if prohib and allow:
        # both a prohibition and a permission remain in the governing set: a conflict
        if config.governance_abstention:
            r.unresolved_competitions.append({"prohibit": [n.key for n in prohib],
                                              "allow": [n.key for n in allow]})
            for n in prohib + allow:
                r.statuses[n.key] = UNRESOLVED
            r.governance_abstention = True
            r.governance_abstention_reason = "two conflicting operative outcomes equally supported"
            r.decision_trace.append("abstain: conflicting operative terms in the governing set")
            return r
        operative = _latest(prohib)[0]     # without abstention, prohibition dominates
    elif prohib:
        operative = _latest(prohib)[0]
    elif allow:
        operative = _latest(allow)[0]
    else:
        carriers = [n for n in governing_nodes if _has_operative_term(n)]
        if carriers:
            operative = _latest(carriers)[0]
        elif config.governance_abstention and governing_nodes:
            r.governance_abstention = True
            r.governance_abstention_reason = "authority established but operative term not locatable"
            r.decision_trace.append("abstain: no operative term among governing nodes")
            return r
        else:
            operative = nodes_by_key.get(frozen_primary)

    if operative is not None:
        r.operative_nodes = [operative.key]
        r.statuses[operative.key] = OPERATIVE
        r.decision_trace.append(f"operative={operative.key} signal={_tfc_signal(operative)} "
                                f"frozen_primary={frozen_primary}")

    if config.cumulative and operative is not None:
        for n in governing_nodes:
            if n.key != operative.key and n.attrs.get("penalty_months"):
                r.statuses[n.key] = CUMULATIVE_REQUIREMENT
                r.cumulative_nodes.append(n.key)

    return r


# --------------------------------------------------------------------------- #
# Adapter — translate the semantic result into the FROZEN packet's single-primary
# contract. It NEVER infers relationships, edits evidence, adds answer text, adds policy
# rules, or picks the final answer: it orders the operative node first and hides the
# competing governance-source edges from the packet-input graph so the frozen packet's
# own `primary` rule lands on the OPERATIVE node. Documented information loss: the frozen
# contract cannot natively express "operative ≠ authority", so non-operative authority
# edges are withheld from the packet-input graph only.
# --------------------------------------------------------------------------- #
def adapt(graph: ResolvedEvidenceGraph, result: GovernanceResult):
    discarded = {k: result.statuses.get(k, "displaced") for k in result.displaced_nodes}
    if result.governance_abstention:
        return graph, GovernanceResolution(abstain=True,
                                           abstain_reason=result.governance_abstention_reason,
                                           discarded=discarded)
    governing = list(result.frozen_governing)  # governing SET unchanged (Mode G-safe)
    op = result.operative_nodes[0] if result.operative_nodes else None
    if op and op in governing:
        governing = [op] + [k for k in governing if k != op]  # operative first
    keep = []
    for e in graph.edges:
        if e.type in GOVERNANCE_SOURCE_TYPES and e.src != op and e.src in result.frozen_governing:
            continue  # hide competing authority edges so frozen `primary` == operative
        keep.append(e)
    nodes = ([graph.node(op)] + [n for n in graph.nodes if n.key != op]) if op else list(graph.nodes)
    gov_graph = ResolvedEvidenceGraph(nodes=[n for n in nodes if n], edges=keep)
    return gov_graph, GovernanceResolution(governing=governing, discarded=discarded)


# preregistered ablations
ABLATIONS = {
    "G0_frozen": None,
    "G1_supersession_amendment": SemanticConfig(displacement_scope=True, parallel=False,
                                                operative_selection=False, exception_handling=False,
                                                cumulative=False, governance_abstention=False),
    "G2_parallel": SemanticConfig(displacement_scope=True, parallel=True,
                                  operative_selection=False, exception_handling=False,
                                  cumulative=False, governance_abstention=False),
    "G3_operative": SemanticConfig(displacement_scope=True, parallel=True,
                                   operative_selection=True, exception_handling=False,
                                   cumulative=False, governance_abstention=False),
    "G4_full": SemanticConfig(),
}
