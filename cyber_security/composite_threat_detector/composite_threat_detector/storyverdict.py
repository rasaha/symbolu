"""Dual-story evaluation: forward completion-gating + contradiction scoring +
comparative verdict.

This is the top layer over :mod:`storygraph`. For a set of linked observed events
it evaluates the harmful story graph, weighs it against an independently *verified*
legitimate explanation (reusing the ``purpose``/``providers`` machinery — passed
in as a benign summary), scores contradictions, and — the strongest feature —
answers whether a *proposed* pre-commit action would **complete** the harmful
story that no verified counter-story covers.

Output is one comparative category (advisory only). It never asserts intent: it
states whether the linked activity is *structurally consistent* with a known
harmful pattern and whether verified context *explains* it.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from . import signals
from .canonical import digest
from .storygraph import ObservedEvent, StoryGraph, StoryMatch, match

# comparative verdict taxonomy (§ "Best output categories")
NO_MATERIAL_PATTERN = "NO_MATERIAL_PATTERN"
PARTIAL_HARMFUL_MATCH = "PARTIAL_HARMFUL_MATCH"
VERIFIED_LEGITIMATE = "VERIFIED_LEGITIMATE"
LEGITIMATE_PARTIALLY_COVERS = "LEGITIMATE_PARTIALLY_COVERS"
AMBIGUOUS_COMPETING = "AMBIGUOUS_COMPETING"
THREAT_CONSISTENT_WITHOUT_BENIGN = "THREAT_CONSISTENT_WITHOUT_BENIGN"
WOULD_COMPLETE_PROHIBITED = "WOULD_COMPLETE_PROHIBITED"
CONFIRMED_VIOLATION = "CONFIRMED_VIOLATION"

# advisory signal per category (analyzer alphabet only — never ALLOW/DENY/BLOCK)
_SIGNAL = {
    NO_MATERIAL_PATTERN: signals.OBSERVE,
    PARTIAL_HARMFUL_MATCH: signals.OBSERVE,
    VERIFIED_LEGITIMATE: signals.OBSERVE,
    LEGITIMATE_PARTIALLY_COVERS: signals.ESCALATE,
    AMBIGUOUS_COMPETING: signals.ESCALATE,
    THREAT_CONSISTENT_WITHOUT_BENIGN: signals.ESCALATE,
    WOULD_COMPLETE_PROHIBITED: signals.ESCALATE,
    CONFIRMED_VIOLATION: signals.ESCALATE,
}


@dataclass
class CompletionCheck:
    completes: bool
    story_ref: str
    already_complete: bool
    newly_present_nodes: list
    gates_ok: bool
    detail: str


def would_complete(graph: StoryGraph, events: list[ObservedEvent],
                   proposed: ObservedEvent) -> CompletionCheck:
    """Forward gate: would admitting ``proposed`` complete the harmful story?

    Completion = the proposed action makes the story fully covered *and* the
    completion node present *and* the structural gates (entity/ordering) hold,
    when it was not already complete beforehand.
    """
    before = match(graph, events)
    already = not before.missing_required and before.completion_present \
        and not before.risk.gate_triggered
    # a pre-commit proposed action happens "next": rebase its coordinate to just
    # after the latest observed event (so a valid completion isn't rejected purely
    # because the caller gave the hypothetical a placeholder position/time).
    if events and proposed.epoch is None:
        next_pos = max(e.position for e in events) + 1
        proposed = dataclasses.replace(proposed, position=next_pos)
    after = match(graph, events + [proposed])
    completes_now = (not after.missing_required and after.completion_present
                     and not after.risk.gate_triggered)
    newly = sorted(set(after.present_nodes) - set(before.present_nodes))
    completes = completes_now and not already
    return CompletionCheck(
        completes=completes, story_ref=graph.ref, already_complete=already,
        newly_present_nodes=newly, gates_ok=not after.risk.gate_triggered,
        detail=("proposed action completes the assembled pattern"
                if completes else
                ("pattern already complete" if already else
                 "proposed action does not complete the pattern "
                 "(coverage/entity/ordering not satisfied)")))


# ---------------------------------------------------------------------------
# Contradictions + benign summary
# ---------------------------------------------------------------------------
@dataclass
class BenignSummary:
    """Verified-context summary (adapted from purpose.PurposeAssessment)."""

    status: str = "UNVERIFIED"          # VERIFIED_CONSISTENT / PARTIALLY_CONSISTENT / ...
    scope_mismatch_fields: list = field(default_factory=list)
    provider_unavailable: bool = False

    @property
    def fully_covers(self) -> bool:
        return self.status == "VERIFIED_CONSISTENT"

    @property
    def partially_covers(self) -> bool:
        return self.status == "PARTIALLY_CONSISTENT"


def contradictions(match_res: StoryMatch, benign: BenignSummary, facts: dict) -> list:
    """Deterministic contradiction detectors (direction-tagged)."""
    out = []
    if benign.scope_mismatch_fields:
        out.append({"name": "approval_scope_mismatch",
                    "effect": "weakens_benign",
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
        return {
            "category": self.category, "signal": self.signal,
            "story_ref": self.story_ref, "risk": self.risk,
            "benign_status": self.benign_status, "contradictions": self.contradictions,
            "completion": self.completion, "explanation": self.explanation,
            "verdict_digest": self.verdict_digest,
        }


def evaluate(graph: StoryGraph, events: list[ObservedEvent], *,
             benign: BenignSummary | None = None, facts: dict | None = None,
             proposed: ObservedEvent | None = None) -> StoryVerdict:
    """Comparative dual-story evaluation → one advisory category."""
    benign = benign or BenignSummary()
    facts = facts or {}
    m = match(graph, events)
    contras = contradictions(m, benign, facts)
    weakens_both = any(c["effect"] == "weakens_both" for c in contras)
    raises_harmful = [c for c in contras if c["effect"] == "raises_harmful"]

    comp = None
    completes = False
    if proposed is not None:
        cc = would_complete(graph, events, proposed)
        comp = {"completes": cc.completes, "already_complete": cc.already_complete,
                "newly_present_nodes": cc.newly_present_nodes, "detail": cc.detail}
        completes = cc.completes

    category = _classify(graph, m, benign, contras, weakens_both, raises_harmful,
                         completes, facts)
    explanation = _explain(category, m, benign, contras, comp)
    body = {"story": graph.ref, "category": category, "risk": m.risk.to_dict(),
            "benign": benign.status, "completes": completes}
    return StoryVerdict(
        category=category, signal=_SIGNAL[category], story_ref=graph.ref,
        risk=m.risk.to_dict(), benign_status=benign.status, contradictions=contras,
        completion=comp, explanation=explanation,
        verdict_digest=digest(body, domain="CTD-VERDICT"))


def _classify(graph, m, benign, contras, weakens_both, raises_harmful, completes,
              facts) -> str:
    if facts.get("confirmed_violation") is True:
        return CONFIRMED_VIOLATION
    if m.risk.coverage < graph.material_floor and not completes:
        return NO_MATERIAL_PATTERN
    # a verified legitimate story that fully covers and is uncontradicted wins
    if benign.fully_covers and not contras and not completes:
        return VERIFIED_LEGITIMATE
    # the strongest signal: an otherwise-fine action completes a prohibited pattern
    if completes and not benign.fully_covers:
        return WOULD_COMPLETE_PROHIBITED
    if benign.partially_covers:
        return LEGITIMATE_PARTIALLY_COVERS
    if weakens_both or benign.provider_unavailable or benign.status == "AMBIGUOUS":
        return AMBIGUOUS_COMPETING
    if benign.fully_covers and contras:
        return AMBIGUOUS_COMPETING          # verified but contradicted -> ambiguous
    if (m.risk.harmful_score >= graph.threat_threshold and not m.risk.gate_triggered
            and not benign.fully_covers):
        return THREAT_CONSISTENT_WITHOUT_BENIGN
    return PARTIAL_HARMFUL_MATCH


def _explain(category, m, benign, contras, comp) -> str:
    r = m.risk
    base = {
        NO_MATERIAL_PATTERN: "Coverage below the material floor; no story assembled.",
        PARTIAL_HARMFUL_MATCH: (
            f"Partial assembly ({r.coverage:.0%} coverage); structural gates or "
            f"harmful score not met."),
        VERIFIED_LEGITIMATE: "A verified, scope-matched legitimate explanation fully "
                             "covers the activity.",
        LEGITIMATE_PARTIALLY_COVERS: "A verified explanation covers only part of the "
                                     "activity; uncovered steps remain.",
        AMBIGUOUS_COMPETING: "Competing explanations or unreliable evidence; additional "
                             "evidence required.",
        THREAT_CONSISTENT_WITHOUT_BENIGN: (
            f"Structurally consistent with the harmful pattern "
            f"(entity {r.entity_consistency:.0%}, order {r.ordering_consistency:.0%}) "
            f"with no verified benign explanation."),
        WOULD_COMPLETE_PROHIBITED: "The proposed action would complete an already-"
                                   "assembled prohibited capability not covered by "
                                   "verified context.",
        CONFIRMED_VIOLATION: "A hard policy contradiction holds regardless of claimed "
                             "purpose.",
    }.get(category, category)
    if r.gate_triggered:
        base += " [structural gate: " + "; ".join(r.gate_reasons) + "]"
    if contras:
        base += " Contradictions: " + ", ".join(c["name"] for c in contras) + "."
    return base
