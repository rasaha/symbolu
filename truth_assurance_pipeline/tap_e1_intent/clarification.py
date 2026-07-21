"""
Clarification and abstention policy (Section 12).

Given detected ambiguities, conflicts, and unresolved references, decide one of:

  * PROCEED               — no material uncertainty; interpret and stop.
  * PROCEED_WITH_ASSUMPTION — proceed but record explicit, removable assumptions.
  * CLARIFY               — ask minimal, decision-relevant, non-redundant questions.
  * ABSTAIN               — refuse to interpret (safety-relevant + unresolved, or no
                            actionable content at all).

Questions must be minimal, decision-relevant, non-redundant, and answerable by the
user — and must NOT ask anything already answered in the conversation context.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

from truth_assurance_pipeline.tap_e1_intent.ambiguity import AmbiguityResult
from truth_assurance_pipeline.tap_e1_intent.conflicts import ConflictResult
from truth_assurance_pipeline.tap_e1_intent.schema import (
    AmbiguityClass, AmbiguityItem, ClarificationQuestion, ConversationTurn,
    InterpretationStatus, Provenance, ProvenanceKind,
)


class Decision(str, Enum):
    PROCEED = "proceed"
    PROCEED_WITH_ASSUMPTION = "proceed_with_assumption"
    CLARIFY = "clarify"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class ClarificationOutcome:
    decision: Decision
    status: InterpretationStatus
    clarification_required: bool
    questions: Tuple[ClarificationQuestion, ...]
    assumptions: Tuple[str, ...]


# Minimal question templates keyed by ambiguity dimension. Kept generic so a
# question is decision-relevant without leaking a presumed answer.
_QUESTION_TEMPLATES = {
    "unresolved_reference": "Which item are you referring to?",
    "edit_vs_new": "Should I edit the existing version in place or create a new one?",
    "undefined_quality_criterion": "What specific outcome counts as done here?",
    "unverified_premise": "Can you confirm the premise before I proceed?",
    "target_undefined": "Which item should I act on?",
    "which_brief": "Which brief do you mean?",
    "which_document": "Which document do you mean?",
    "which_report": "Which report do you mean?",
    "which_file": "Which file do you mean?",
    "which_roadmap": "Which roadmap, and what change?",
    "which_records": "Which records should this apply to?",
}


def _question_for(item: AmbiguityItem) -> str:
    return _QUESTION_TEMPLATES.get(
        item.dimension,
        _QUESTION_TEMPLATES.get("target_undefined",
                                "Could you clarify this request?"))


def _answered_in_context(item: AmbiguityItem,
                         conversation: Tuple[ConversationTurn, ...]) -> bool:
    """A question is redundant if the conversation already resolves the dimension.
    Conservative: only treat a reference-style dimension as answered when context
    supplies exactly one candidate noun phrase."""
    if not conversation:
        return False
    if item.dimension in ("unresolved_reference",) or item.dimension.startswith("which_"):
        # count distinct 'the X' heads across prior user turns
        import re
        heads = set()
        for turn in conversation:
            for m in re.finditer(r"\b(?:the|a|an|two|my)\s+([a-z][a-z_]+)", turn.text.lower()):
                heads.add(m.group(1))
        return len(heads) == 1
    return False


def decide(ambiguity: AmbiguityResult,
           conflict: ConflictResult,
           conversation: Tuple[ConversationTurn, ...] = (),
           has_actionable_content: bool = True,
           references_prior_context: bool = False) -> ClarificationOutcome:

    material = ambiguity.material
    safety = [a for a in material if a.ambiguity_class is AmbiguityClass.SAFETY_RELEVANT]

    # 1) nothing actionable at all -> abstain
    if not has_actionable_content:
        return ClarificationOutcome(
            Decision.ABSTAIN, InterpretationStatus.ABSTAINED, True, (), ())

    # 2) unresolved intra-message conflict (no precedence winner) -> clarify
    if conflict.has_unresolved:
        qs = tuple(
            ClarificationQuestion(
                "These instructions conflict; which should take priority?",
                c.left + " vs " + c.right,
                Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION, note="conflict"))
            for c in conflict.items[:1])
        return ClarificationOutcome(
            Decision.CLARIFY, InterpretationStatus.CONFLICTING, True, qs, ())

    # 3) references prior context that is absent -> insufficient context -> clarify
    if references_prior_context and not conversation:
        qs: List[ClarificationQuestion] = []
        for a in material or ambiguity.items:
            qs.append(ClarificationQuestion(
                _question_for(a), a.dimension,
                Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION,
                           a.provenance.spans, note="insufficient_context")))
        return ClarificationOutcome(
            Decision.CLARIFY, InterpretationStatus.INSUFFICIENT_CONTEXT, True,
            _dedupe(qs), ())

    # 4) safety-relevant material ambiguity that context does not resolve -> clarify
    #    (do NOT silently assume authorization/approval)
    if safety and not all(_answered_in_context(a, conversation) for a in safety):
        qs = [ClarificationQuestion(_question_for(a), a.dimension,
                                    Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION,
                                               a.provenance.spans, note="safety"))
              for a in safety if not _answered_in_context(a, conversation)]
        return ClarificationOutcome(
            Decision.CLARIFY, InterpretationStatus.AMBIGUOUS, True, _dedupe(qs), ())

    # 5) other material ambiguity -> clarify only if not answered in context
    unanswered = [a for a in material if not _answered_in_context(a, conversation)]
    if unanswered:
        # An underspecified request with no actionable target is INSUFFICIENT_CONTEXT;
        # a request that is actionable but forks into readings is AMBIGUOUS.
        has_target = any(a.dimension not in ("target_undefined",
                                             "unresolved_reference")
                         for a in unanswered) or has_actionable_content
        # If the only material item is an undefined *quality criterion* on an
        # otherwise fully specified action, that is proceed-with-assumption.
        only_quality = all(a.dimension == "undefined_quality_criterion"
                           for a in unanswered)
        if only_quality:
            return ClarificationOutcome(
                Decision.PROCEED_WITH_ASSUMPTION,
                InterpretationStatus.PARTIALLY_RESOLVED, False, (),
                tuple(f"assume a reasonable interpretation of "
                      f"'{a.dimension}'" for a in unanswered))
        target_missing = any(a.dimension in ("target_undefined",
                                             "unresolved_reference")
                             for a in unanswered)
        status = (InterpretationStatus.INSUFFICIENT_CONTEXT
                  if target_missing and not conversation
                  else InterpretationStatus.AMBIGUOUS)
        qs = [ClarificationQuestion(_question_for(a), a.dimension,
                                    Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION,
                                               a.provenance.spans, note="material"))
              for a in unanswered]
        return ClarificationOutcome(Decision.CLARIFY, status, True, _dedupe(qs), ())

    # 6) only non-material ambiguity (or none) -> proceed
    status = (InterpretationStatus.RESOLVED if not ambiguity.items
              else InterpretationStatus.RESOLVED)
    return ClarificationOutcome(Decision.PROCEED, status, False, (), ())


def _dedupe(qs: List[ClarificationQuestion]) -> Tuple[ClarificationQuestion, ...]:
    seen = set()
    out: List[ClarificationQuestion] = []
    for q in qs:
        if q.question in seen:
            continue
        seen.add(q.question)
        out.append(q)
    return tuple(out)
