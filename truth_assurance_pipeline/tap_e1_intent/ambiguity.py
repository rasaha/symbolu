"""
Ambiguity detection and materiality classification (Section 9).

Deterministic heuristics over the raw text + deterministic extraction + optional
conversation context. The detector aims to surface *materially different*
interpretations — readings that would change the requested operation or its risk —
and to classify each by materiality so the clarification policy can decide whether a
question is warranted. Harmless (non-material) ambiguity is recorded but never
triggers clarification.

These are heuristics, not an oracle: some material ambiguities will be missed and
some non-material ones flagged. Those misses/false-flags are exactly what the
material-ambiguity-detection and unnecessary-clarification metrics measure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import (
    AmbiguityClass, AmbiguityItem, ConversationTurn, Provenance, ProvenanceKind,
    Span,
)

# Definite references that need an antecedent to be actionable.
_DEFINITE_NOUNS = ("brief", "document", "doc", "report", "file", "spec", "ticket",
                   "page", "table", "section", "roadmap", "config", "deck",
                   "records", "migration", "release", "changes", "thing")
# Bare pronouns used as the object of the request.
_PRONOUNS = ("it", "them", "that", "this", "these", "those", "one")

# Verbs that create an edit-in-place vs new-version ambiguity when applied to a
# document without an explicit qualifier.
_EDIT_VERBS = ("update", "edit", "revise", "change", "modify")
_INPLACE_QUALIFIERS = ("in place", "in-place", "new version", "new copy", "a copy",
                       "separately", "overwrite", "duplicate")

# Vague quality goals that leave the acceptance criterion undefined. Only material
# when they are the HEAD result of a "make ... <quality>" / "look <quality>" request
# (see the pattern in ``detect``), not when they merely modify a concrete deliverable.
_VAGUE_QUALITY = ("faster", "modern", "better", "nicer", "professional",
                  "look better", "look nicer", "look good")

# Confirmation / authorization pressure (adversarial): asserting agreement the
# layer cannot verify.
_PRESSURE = ("as we both know", "as you know", "obviously", "we agreed",
             "we both know", "you already have my approval", "already approved",
             "right?", "usual way", "the usual", "we discussed", "as agreed",
             "you already have")

_STOP = frozenset(("the", "a", "an", "to", "of", "and", "with", "for", "in", "on",
                   "it", "this", "that", "all", "any", "your", "my", "our", "is",
                   "are", "be", "make", "just", "please"))


@dataclass(frozen=True)
class AmbiguityResult:
    items: Tuple[AmbiguityItem, ...]
    unresolved_context_refs: Tuple[str, ...]   # surface forms lacking an antecedent

    @property
    def material(self) -> Tuple[AmbiguityItem, ...]:
        return tuple(a for a in self.items if a.is_material)


def _prov(text: str, start: int, note: str,
          kind: ProvenanceKind = ProvenanceKind.DETERMINISTIC_EXTRACTION) -> Provenance:
    end = min(start + 30, len(text))
    return Provenance(kind, (Span(start, end, text[start:end]),), note=note)


def _count_context_candidates(conversation: Tuple[ConversationTurn, ...]) -> int:
    heads = set()
    for turn in conversation:
        for m in re.finditer(r"\b(?:the|a|an|two|my)\s+([a-z][a-z_]+)", turn.text.lower()):
            heads.add(m.group(1))
    return len(heads)


def _content_words_excluding(low: str, exclude: set) -> set:
    toks = set(re.findall(r"[a-z][a-z_]+", low))
    return {t for t in toks if t not in _STOP and t not in exclude and len(t) > 1}


def _context_has_single_antecedent(surface: str,
                                    conversation: Tuple[ConversationTurn, ...]
                                    ) -> Optional[str]:
    """Return the resolved antecedent iff conversation supplies exactly one
    plausible candidate; else None. A pronoun/definite ref with one clear
    antecedent is resolvable (no clarification); with zero or many, it is not."""
    if not conversation:
        return None
    # Gather noun-phrase candidates from prior user turns (very small heuristic).
    candidates: List[str] = []
    for turn in conversation:
        for m in re.finditer(r"\b(?:the|a|an|two|my)\s+([a-z][a-z_]+(?:\s+[a-z][a-z_]+){0,3})",
                             turn.text.lower()):
            phrase = m.group(1).strip()
            if phrase and phrase not in candidates:
                candidates.append(phrase)
    # de-duplicate trivially and require exactly one distinct head candidate
    heads = {c.split()[-1] for c in candidates}
    if len(candidates) == 1:
        return candidates[0]
    if len(heads) == 1 and candidates:
        return candidates[0]
    return None


def _has_local_antecedent(low: str, pron_start: int) -> bool:
    """A pronoun is resolved intra-message if a concrete object (filename, quoted
    name, or 'the/a <noun>') appears earlier in the SAME message."""
    prefix = low[:pron_start]
    if re.search(r"\b[\w./-]+\.\w{1,5}\b", prefix):        # a filename precedes
        return True
    # a concrete noun introduced by an article precedes (and is not itself a pronoun)
    for m in re.finditer(r"\b(?:the|a|an|its|their)\s+([a-z][a-z_]+)", prefix):
        if m.group(1) not in _PRONOUNS:
            return True
    return False


def detect(text: str,
           conversation: Tuple[ConversationTurn, ...] = (),
           task_is_document_edit: bool = False) -> AmbiguityResult:
    items: List[AmbiguityItem] = []
    unresolved: List[str] = []
    low = text.lower()

    # 1) bare pronoun object with no clear antecedent (intra-message or single
    #    context). Suppressed when a concrete object precedes it in the message or
    #    exactly one context antecedent exists; flagged when zero, or MANY context
    #    candidates (genuinely ambiguous, e.g. "merge them" with two branches).
    for pron in ("it", "them", "that", "this", "these", "those"):
        m = re.search(r"\b" + pron + r"\b", low)
        if not m:
            continue
        after = low[m.end():m.end() + 12].strip()
        if pron in ("this", "that", "these", "those") and after and after.split()[0] not in _STOP:
            continue  # determiner use ("that file"), not a bare pronoun
        if _has_local_antecedent(low, m.start()):
            break  # resolved within the same message
        # a referent supplied by conversation context (a named artifact or an
        # enumerated set) makes the pronoun resolvable; only a pronoun with NO
        # local antecedent AND NO context is genuinely unresolved.
        if _count_context_candidates(conversation) >= 1:
            break
        items.append(AmbiguityItem(
            "unresolved_reference",
            f"pronoun '{pron}' has no single clear antecedent",
            AmbiguityClass.EXECUTION_RELEVANT, _prov(text, m.start(), f"pronoun:{pron}")))
        unresolved.append(pron)
        break

    # 2) bare "update/edit/revise the <doc>" with no concrete change target ->
    #    edit-in-place vs new-version AND undefined update content (material).
    m = re.search(r"\b(update|edit|revise)\s+the\s+"
                  r"(brief|document|doc|report|roadmap|spec|page|deck|file|readme)\b", low)
    if m and not re.search(r"\b[\w./-]+\.\w{1,5}\b", low):
        extra = _content_words_excluding(low, {m.group(1), m.group(2)})
        if len(extra) <= 1:
            items.append(AmbiguityItem(
                "update_content_undefined",
                f"'{m.group(1)} the {m.group(2)}' does not say what to change or "
                "whether to edit in place vs create a new version",
                AmbiguityClass.EXECUTION_RELEVANT, _prov(text, m.start(), "bare_update")))

    # 3) vague action verb with no concrete artifact -> undefined target/scope
    #    ("handle the edge cases", "finish it", "sort this out").
    _VAGUE_ACTION = ("handle", "finish", "address", "deal with", "sort out",
                     "take care of", "sort")
    if not re.search(r"\b[\w./-]+\.\w{1,5}\b", low):  # no filename anchors it
        for va in _VAGUE_ACTION:
            m = re.search(r"\b" + re.escape(va) + r"\b", low)
            if m and not any(a.dimension == "unresolved_reference" for a in items):
                items.append(AmbiguityItem(
                    "target_undefined",
                    f"'{va}' names no concrete target or scope",
                    AmbiguityClass.SCOPE_RELEVANT, _prov(text, m.start(), f"vague_action:{va}")))
                break

    # 4) vague quality criterion, only as the HEAD result of the request
    #    ("make X faster", "make the numbers look better") -> undefined acceptance.
    for adj in _VAGUE_QUALITY:
        m = re.search(r"\b(?:make|look|be)\b[\w\s']{0,30}?\b" + re.escape(adj) + r"\b", low)
        if m:
            a = re.search(re.escape(adj), low[m.start():])
            items.append(AmbiguityItem(
                "undefined_quality_criterion",
                f"'{adj}' does not define an acceptance criterion",
                AmbiguityClass.EXECUTION_RELEVANT,
                _prov(text, m.start() + (a.start() if a else 0), f"vague:{adj}")))
            break

    # 5) confirmation / authorization pressure (adversarial)
    for phrase in _PRESSURE:
        idx = low.find(phrase)
        if idx >= 0:
            items.append(AmbiguityItem(
                "unverified_premise",
                f"request presumes an unverifiable premise: '{phrase}'",
                AmbiguityClass.SAFETY_RELEVANT, _prov(text, idx, f"pressure:{phrase}")))
            break

    # de-duplicate by dimension (keep the most material per dimension)
    best: dict = {}
    order = {AmbiguityClass.SAFETY_RELEVANT: 4, AmbiguityClass.EVIDENCE_RELEVANT: 3,
             AmbiguityClass.SCOPE_RELEVANT: 2, AmbiguityClass.EXECUTION_RELEVANT: 1,
             AmbiguityClass.NON_MATERIAL: 0}
    for a in items:
        cur = best.get(a.dimension)
        if cur is None or order[a.ambiguity_class] > order[cur.ambiguity_class]:
            best[a.dimension] = a
    return AmbiguityResult(tuple(best.values()), tuple(dict.fromkeys(unresolved)))


def _looks_underspecified(noun: str, low: str) -> bool:
    """A definite reference is underspecified unless the same text names a concrete
    instance (e.g. a filename ending, a quoted name, or an adjacent proper noun)."""
    # if a filename or explicit named artifact is present, treat as specified
    if re.search(r"\b[\w./-]+\.\w{1,5}\b", low):
        return False
    # 'the pricing table', 'the second file' etc. carry a qualifier -> specified
    m = re.search(r"\b(second|first|third|last|next|previous|final|"
                  r"pricing|troubleshooting|welcome|login|staging|production)\s+", low)
    if m:
        return False
    return True
