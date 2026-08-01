"""Dual-story evaluation: verdict taxonomy, minimal completion witness, and the
pre-commit ``evaluate_proposed_action`` entry point.

Weighs a harmful story graph against a *verified legitimate* counter-story
(per-node coverage, see ``legitimate.py``), emits typed contradictions
(``contradictions.py``), and — the strongest feature — answers whether an exact
proposed pre-commit action would *complete* the harmful story that verified
context does not cover, returning a minimal completion **witness** (a deterministic
certificate whose proposed action is necessary for completion).

Advisory only: the analyzer-facing signal is ``OBSERVE`` / ``ESCALATE`` /
``UNAVAILABLE``. Policy owns HOLD/BLOCK. It never asserts intent.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from . import contradictions as contra_mod
from . import legitimate as L
from . import signals
from .canonical import digest
from .storygraph import ObservedEvent, StoryGraph, StoryMatch, match

# canonical comparative verdict taxonomy (§9)
NO_MATERIAL_PATTERN = "NO_MATERIAL_PATTERN"
PARTIAL_HARMFUL_STORY = "PARTIAL_HARMFUL_STORY"
VERIFIED_LEGITIMATE_STORY = "VERIFIED_LEGITIMATE_STORY"
LEGITIMATE_STORY_PARTIAL_COVERAGE = "LEGITIMATE_STORY_PARTIAL_COVERAGE"
AMBIGUOUS_COMPETING_STORIES = "AMBIGUOUS_COMPETING_STORIES"
THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT = "THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT"
WOULD_COMPLETE_PROHIBITED_CAPABILITY = "WOULD_COMPLETE_PROHIBITED_CAPABILITY"
HARD_POLICY_VIOLATION = "HARD_POLICY_VIOLATION"

# backward-compatible aliases (prior turn's names)
PARTIAL_HARMFUL_MATCH = PARTIAL_HARMFUL_STORY
VERIFIED_LEGITIMATE = VERIFIED_LEGITIMATE_STORY
LEGITIMATE_PARTIALLY_COVERS = LEGITIMATE_STORY_PARTIAL_COVERAGE
AMBIGUOUS_COMPETING = AMBIGUOUS_COMPETING_STORIES
THREAT_CONSISTENT_WITHOUT_BENIGN = THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT
WOULD_COMPLETE_PROHIBITED = WOULD_COMPLETE_PROHIBITED_CAPABILITY
CONFIRMED_VIOLATION = HARD_POLICY_VIOLATION

_SIGNAL = {
    NO_MATERIAL_PATTERN: signals.OBSERVE,
    PARTIAL_HARMFUL_STORY: signals.OBSERVE,
    VERIFIED_LEGITIMATE_STORY: signals.OBSERVE,
    LEGITIMATE_STORY_PARTIAL_COVERAGE: signals.ESCALATE,
    AMBIGUOUS_COMPETING_STORIES: signals.ESCALATE,
    THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT: signals.ESCALATE,
    WOULD_COMPLETE_PROHIBITED_CAPABILITY: signals.ESCALATE,
    HARD_POLICY_VIOLATION: signals.ESCALATE,
}


# ---------------------------------------------------------------------------
# Legacy benign summary path (kept for the existing single-status callers)
# ---------------------------------------------------------------------------
@dataclass
class BenignSummary:
    status: str = "UNVERIFIED"
    scope_mismatch_fields: list = field(default_factory=list)
    provider_unavailable: bool = False

    @property
    def fully_covers(self) -> bool:
        return self.status == "VERIFIED_CONSISTENT"

    @property
    def partially_covers(self) -> bool:
        return self.status == "PARTIALLY_CONSISTENT"


# ---------------------------------------------------------------------------
# Minimal completion witness / deterministic certificate (§7, §10)
# ---------------------------------------------------------------------------
@dataclass
class CompletionWitness:
    story_ref: str
    completes: bool
    completion_node: str
    witness_events: dict            # node_id -> event_id (one per required node)
    proved_relations: list          # satisfied edges proving the completion binding
    removal_breaks_completion: bool
    proposed_is_necessary: bool
    certificate_digest: str

    def to_dict(self) -> dict:
        return {
            "story_ref": self.story_ref, "completes": self.completes,
            "completion_node": self.completion_node,
            "witness_events": self.witness_events,
            "proved_relations": self.proved_relations,
            "removal_breaks_completion": self.removal_breaks_completion,
            "proposed_is_necessary": self.proposed_is_necessary,
            "certificate_digest": self.certificate_digest,
        }


def _rebase(events, proposed):
    if events and proposed.epoch is None:
        return dataclasses.replace(proposed, position=max(e.position for e in events) + 1)
    return proposed


def completion_witness(graph: StoryGraph, events: list, proposed: ObservedEvent):
    """Return the minimal witness proving ``proposed`` completes the harmful story.

    ``None`` if it does not complete. The witness is one event per required node
    plus the proposed action; removing the proposed action makes the story
    incomplete (the certificate's necessity property).
    """
    before = match(graph, events)
    proposed = _rebase(events, proposed)
    after = match(graph, events + [proposed])
    if before.is_complete() or not after.is_complete():
        return None

    completion_ids = [n.node_id for n in graph.nodes if n.is_completion]
    comp_node = next((nid for nid in completion_ids
                      if after.binding.get(nid) == proposed.event_id), "")
    proposed_necessary = bool(comp_node)  # proposed is bound to the completion node

    witness = {n.node_id: after.binding[n.node_id]
               for n in graph.required_nodes() if n.node_id in after.binding}
    events_by_id = {e.event_id: e for e in (events + [proposed])}
    proved = []
    for e in graph.edges:
        if e.a in after.binding and (not e.b or e.b in after.binding):
            ea = events_by_id[after.binding[e.a]]
            rel = {"kind": e.kind, "a": e.a, "b": e.b, "dim": e.dim}
            if e.kind == "SAME_ENTITY":
                rel["value"] = ea.entities.get(e.dim, "")
            proved.append(rel)

    body = {"story": graph.ref, "completion_node": comp_node, "witness": witness,
            "proposed": proposed.event_id}
    return CompletionWitness(
        story_ref=graph.ref, completes=True, completion_node=comp_node,
        witness_events=witness, proved_relations=proved,
        removal_breaks_completion=not before.is_complete(),
        proposed_is_necessary=proposed_necessary,
        certificate_digest=digest(body, domain="CTD-WITNESS"))


# ---------------------------------------------------------------------------
# Proposed-action evaluation (the pre-commit entry point, §6)
# ---------------------------------------------------------------------------
@dataclass
class ProposedActionResult:
    category: str
    signal: str
    story_ref: str
    harmful_before_complete: bool
    harmful_after_complete: bool
    risk_after: dict
    legitimate_coverage: dict | None
    contradictions: list
    completion_witness: dict | None
    explanation: str
    verdict_digest: str

    def to_dict(self) -> dict:
        return {
            "category": self.category, "signal": self.signal,
            "story_ref": self.story_ref,
            "harmful_before_complete": self.harmful_before_complete,
            "harmful_after_complete": self.harmful_after_complete,
            "risk_after": self.risk_after,
            "legitimate_coverage": self.legitimate_coverage,
            "contradictions": self.contradictions,
            "completion_witness": self.completion_witness,
            "explanation": self.explanation, "verdict_digest": self.verdict_digest,
        }


def _merge_coverage(harmful_after, harmful_graph, events_by_id, legitimate_stories,
                    authorizations, now, completion_ids):
    """Coverage across all legitimate stories (a node is covered if any covers it)."""
    if not legitimate_stories:
        return None
    merged = None
    for legit in legitimate_stories:
        cov = L.coverage(legit, harmful_after, harmful_graph, events_by_id,
                         authorizations, now, completion_ids)
        if merged is None:
            merged = cov
            continue
        for nid, info in cov.per_node.items():
            if info["status"] == L.COVERED and \
                    merged.per_node.get(nid, {}).get("status") != L.COVERED:
                merged.per_node[nid] = info
    if merged is None:
        return None
    covered = sorted(n for n, i in merged.per_node.items() if i["status"] == L.COVERED)
    uncovered = sorted(n for n, i in merged.per_node.items() if i["status"] == L.UNCOVERED)
    present = [n for n, i in merged.per_node.items() if i["status"] != L.NOT_PRESENT]
    status = (L.NONE if not covered
              else L.FULL if all(merged.per_node[n]["status"] == L.COVERED for n in present)
              else L.PARTIAL)
    completion_covered = any(n in covered for n in completion_ids)
    merged.covered_nodes, merged.uncovered_nodes = covered, uncovered
    merged.status, merged.completion_covered = status, completion_covered
    return merged


def evaluate_proposed_action(assembly_events, proposed_action, harmful_story_graph,
                             legitimate_stories=(), authorizations=(), *,
                             facts=None, now=None) -> ProposedActionResult:
    """Hypothetically insert ``proposed_action`` and classify (advisory)."""
    facts = facts or {}
    graph = harmful_story_graph
    proposed = _rebase(assembly_events, proposed_action)
    before = match(graph, assembly_events)
    after = match(graph, assembly_events + [proposed])
    events_by_id = {e.event_id: e for e in (assembly_events + [proposed])}
    completion_ids = {n.node_id for n in graph.nodes if n.is_completion}

    witness = completion_witness(graph, assembly_events, proposed_action)
    cov = _merge_coverage(after, graph, events_by_id, legitimate_stories,
                          authorizations, now, completion_ids)
    contras = contra_mod.detect(after, cov, facts)

    category = _classify_proposed(graph, before, after, cov, contras, witness, facts)
    signal = signals.UNAVAILABLE if after.unavailable else _SIGNAL[category]
    explanation = _explain_proposed(category, after, cov, contras, witness)
    body = {"story": graph.ref, "category": category,
            "risk_after": after.risk.to_dict(),
            "completes": bool(witness), "cov": cov.status if cov else None}
    return ProposedActionResult(
        category=category, signal=signal, story_ref=graph.ref,
        harmful_before_complete=before.is_complete(),
        harmful_after_complete=after.is_complete(),
        risk_after=after.risk.to_dict(),
        legitimate_coverage=cov.to_dict() if cov else None,
        contradictions=[c.to_dict() for c in contras],
        completion_witness=witness.to_dict() if witness else None,
        explanation=explanation, verdict_digest=digest(body, domain="CTD-PROPOSED"))


def _classify_proposed(graph, before, after, cov, contras, witness, facts) -> str:
    decisive = [c for c in contras if c.decisive]
    ambiguous = (after.ordering_ambiguous
                 or any(c.type == contra_mod.ENTITY_LINKAGE_AMBIGUOUS for c in contras))
    if facts.get("confirmed_violation") is True:
        return HARD_POLICY_VIOLATION
    if after.risk.coverage < graph.material_floor and witness is None:
        return NO_MATERIAL_PATTERN
    completion_covered = bool(cov and cov.completion_covered)
    if witness is not None and not completion_covered:
        return WOULD_COMPLETE_PROHIBITED_CAPABILITY
    if cov is not None and cov.status == L.FULL and not decisive and witness is None:
        return VERIFIED_LEGITIMATE_STORY
    if cov is not None and cov.status == L.PARTIAL:
        return LEGITIMATE_STORY_PARTIAL_COVERAGE
    if ambiguous:
        return AMBIGUOUS_COMPETING_STORIES
    if (after.risk.harmful_score >= graph.threat_threshold
            and not after.risk.gate_triggered
            and (cov is None or cov.status == L.NONE)):
        return THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT
    return PARTIAL_HARMFUL_STORY


def _explain_proposed(category, after, cov, contras, witness) -> str:
    parts = {
        NO_MATERIAL_PATTERN: "Coverage below the material floor; no story assembled.",
        PARTIAL_HARMFUL_STORY: "Partial harmful assembly; structural gates or score "
                               "not met for a threat-consistent verdict.",
        VERIFIED_LEGITIMATE_STORY: "A verified legitimate story fully covers the "
                                   "activity.",
        LEGITIMATE_STORY_PARTIAL_COVERAGE: "A verified legitimate story covers only "
                                           "part of the activity.",
        AMBIGUOUS_COMPETING_STORIES: "Competing explanations or unresolved ordering/"
                                     "linkage; additional evidence required.",
        THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT: "Structurally consistent with the "
                                                     "harmful pattern with no verified "
                                                     "legitimate coverage.",
        WOULD_COMPLETE_PROHIBITED_CAPABILITY: "The proposed action would complete the "
                                              "harmful pattern; verified context does "
                                              "not cover the completing step.",
        HARD_POLICY_VIOLATION: "A hard policy contradiction holds regardless of claimed "
                               "purpose.",
    }.get(category, category)
    if cov is not None and cov.uncovered_nodes:
        parts += " Uncovered: " + ", ".join(cov.uncovered_nodes) + "."
    if contras:
        parts += " Contradictions: " + ", ".join(c.type for c in contras) + "."
    return parts


# ---------------------------------------------------------------------------
# Legacy single-graph evaluation (BenignSummary path) — kept working
# ---------------------------------------------------------------------------
def would_complete(graph, events, proposed):
    w = completion_witness(graph, events, proposed)

    @dataclass
    class _CC:
        completes: bool
        story_ref: str
        already_complete: bool
        newly_present_nodes: list
        gates_ok: bool
        detail: str
    if w is not None:
        return _CC(True, graph.ref, False, [], True,
                   "proposed action completes the assembled pattern")
    before = match(graph, events)
    return _CC(False, graph.ref, before.is_complete(), [], not before.risk.gate_triggered,
               "proposed action does not complete the pattern")


def contradictions(match_res, benign, facts):  # legacy helper used by evaluate()
    out = []
    if benign.scope_mismatch_fields:
        out.append({"name": "approval_scope_mismatch", "effect": "weakens_benign",
                    "detail": "verified approval does not cover: "
                              + ", ".join(benign.scope_mismatch_fields)})
    if facts.get("destination_authorized") is False:
        out.append({"name": "unauthorized_destination", "effect": "raises_harmful",
                    "detail": "outbound destination is not in the authorized set"})
    if facts.get("amount_within_cap") is False:
        out.append({"name": "amount_exceeds_cap", "effect": "raises_harmful",
                    "detail": "value exceeds the approved amount"})
    if facts.get("after_approval_expiry") is True:
        out.append({"name": "after_approval_expiry", "effect": "weakens_benign",
                    "detail": "activity occurred after the approval window"})
    if facts.get("concealment_present") is True:
        out.append({"name": "concealment", "effect": "raises_harmful",
                    "detail": "control-bypass/concealment behavior present"})
    if facts.get("linkage_confident") is False:
        out.append({"name": "weak_linkage", "effect": "weakens_both",
                    "detail": "actors/resources cannot be reliably linked"})
    return out


@dataclass
class StoryVerdict:
    category: str
    signal: str
    story_ref: str
    risk: dict
    benign_status: str
    contradictions: list
    completion: dict | None
    explanation: str
    verdict_digest: str

    def to_dict(self) -> dict:
        return {"category": self.category, "signal": self.signal,
                "story_ref": self.story_ref, "risk": self.risk,
                "benign_status": self.benign_status,
                "contradictions": self.contradictions, "completion": self.completion,
                "explanation": self.explanation, "verdict_digest": self.verdict_digest}


def evaluate(graph, events, *, benign=None, facts=None, proposed=None) -> StoryVerdict:
    """Legacy single-graph dual-story evaluation (BenignSummary path)."""
    benign = benign or BenignSummary()
    facts = facts or {}
    m = match(graph, events)
    contras = contradictions(m, benign, facts)
    weakens_both = any(c["effect"] == "weakens_both" for c in contras)
    comp = None
    completes = False
    if proposed is not None:
        cc = would_complete(graph, events, proposed)
        comp = {"completes": cc.completes, "already_complete": cc.already_complete,
                "detail": cc.detail}
        completes = cc.completes
    category = _classify_legacy(graph, m, benign, contras, weakens_both, completes, facts)
    signal = signals.UNAVAILABLE if m.unavailable else _SIGNAL[category]
    body = {"story": graph.ref, "category": category, "risk": m.risk.to_dict(),
            "benign": benign.status, "completes": completes}
    return StoryVerdict(
        category=category, signal=signal, story_ref=graph.ref,
        risk=m.risk.to_dict(), benign_status=benign.status,
        contradictions=contras, completion=comp,
        explanation=_explain_proposed(category, m, None, [], None),
        verdict_digest=digest(body, domain="CTD-VERDICT"))


def _classify_legacy(graph, m, benign, contras, weakens_both, completes, facts) -> str:
    if facts.get("confirmed_violation") is True:
        return HARD_POLICY_VIOLATION
    if m.risk.coverage < graph.material_floor and not completes:
        return NO_MATERIAL_PATTERN
    if benign.fully_covers and not contras and not completes:
        return VERIFIED_LEGITIMATE_STORY
    if completes and not benign.fully_covers:
        return WOULD_COMPLETE_PROHIBITED_CAPABILITY
    if benign.partially_covers:
        return LEGITIMATE_STORY_PARTIAL_COVERAGE
    if weakens_both or benign.provider_unavailable or benign.status == "AMBIGUOUS":
        return AMBIGUOUS_COMPETING_STORIES
    if benign.fully_covers and contras:
        return AMBIGUOUS_COMPETING_STORIES
    if (m.risk.harmful_score >= graph.threat_threshold and not m.risk.gate_triggered
            and not benign.fully_covers):
        return THREAT_CONSISTENT_WITH_INSUFFICIENT_CONTEXT
    return PARTIAL_HARMFUL_STORY
