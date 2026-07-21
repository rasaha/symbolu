"""
Conflict detection with deterministic instruction precedence (Section 10).

Detects instruction pairs that cannot both be honored:

  * a PROHIBITION whose subject clashes with an imperative on the same subject
    ("do not change the architecture" vs "redesign the data layer" — same
    change-family verb on an architecture subject);
  * a preservation requirement clashing with an expansion/rewrite
    ("keep the same length" vs "add five sections"; "change nothing observable"
    vs "rewrite from scratch");
  * a current-message instruction clashing with older conversation context.

True conflicts are never resolved silently (Section 10). Where a deterministic
precedence winner exists (current explicit beats older context; explicit beats
inferred) it is recorded, but an intra-message clash between two equally explicit
instructions has no precedence winner and is surfaced for clarification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import (
    ConflictItem, ConflictKind, Constraint, ConstraintPolarity, ConversationTurn,
    Provenance, ProvenanceKind, Span,
)

# Verb families: a preservation cue and an alteration cue on the same target clash.
_PRESERVE = ("keep", "preserve", "maintain", "same", "unchanged", "intact",
             "as is", "as long as", "do not change", "leave", "nothing observable",
             "change nothing", "untouched", "no change")
_ALTER = ("change", "redesign", "restructure", "rewrite", "modify", "alter",
          "add", "expand", "extend", "rework", "overhaul", "from scratch",
          "more detailed", "improve", "detailed")

# Length-preservation vs expansion.
_LENGTH_KEEP = ("same length", "under one page", "keep it under", "as long as it is",
                "exactly as long", "one page", "keep the length", "keep it short")
_EXPAND = ("add", "new sections", "new detailed", "more detailed", "five", "expand",
           "lengthen", "sections")


@dataclass(frozen=True)
class ConflictResult:
    items: Tuple[ConflictItem, ...]

    @property
    def has_unresolved(self) -> bool:
        # intra-message clashes have no precedence winner -> unresolved
        return any(c.kind is ConflictKind.INTRA_MESSAGE for c in self.items)


def _prov(text: str, note: str) -> Provenance:
    return Provenance(ProvenanceKind.DETERMINISTIC_EXTRACTION,
                      (Span(0, min(40, len(text)), text[:40]),), note=note)


def _present(low: str, cues) -> bool:
    return any(re.search(r"\b" + re.escape(c) + r"\b", low) for c in cues)


def detect(text: str,
           constraints: Tuple[Constraint, ...] = (),
           conversation: Tuple[ConversationTurn, ...] = ()) -> ConflictResult:
    items: List[ConflictItem] = []
    low = text.lower()

    # 1) length-preservation vs expansion/improvement (both current, equally explicit)
    if _present(low, _LENGTH_KEEP) and _present(low, ("add", "sections", "more detailed",
                                                      "expand", "detailed", "lengthen",
                                                      "improve", "rewrite", "redesign",
                                                      "enhance", "more")):
        items.append(ConflictItem(
            ConflictKind.INTRA_MESSAGE,
            "preserve-length instruction conflicts with an expansion instruction",
            left="keep the same length", right="add / expand content",
            winner_provenance=ProvenanceKind.EXPLICIT_TEXT,
            provenance=_prov(text, "length_vs_expand")))

    # 2) explicit "do not change / keep unchanged X" vs an alteration verb elsewhere
    prohibition_alter = any(
        c.polarity is ConstraintPolarity.PROHIBITION and
        any(a in c.text.lower() for a in ("change", "alter", "modify", "redesign",
                                          "rewrite", "touch", "observable"))
        for c in constraints)
    keep_unchanged = _present(low, ("do not change", "change nothing",
                                    "nothing observable", "unchanged", "leave everything"))
    alter_verb = _present(low, ("redesign", "rewrite", "restructure", "rework",
                                "overhaul", "from scratch", "improve", "more detailed"))
    if (prohibition_alter or keep_unchanged) and alter_verb:
        items.append(ConflictItem(
            ConflictKind.INTRA_MESSAGE,
            "a preservation prohibition conflicts with an alteration instruction",
            left="do not change / keep unchanged", right="redesign / rewrite",
            winner_provenance=ProvenanceKind.EXPLICIT_TEXT,
            provenance=_prov(text, "prohibit_vs_alter")))

    # 3) current message vs older conversation context (precedence: current wins)
    if conversation:
        for turn in conversation:
            tl = turn.text.lower()
            # crude antonym clash: context says "do X" and current says "do not X"
            for verb in ("delete", "remove", "change", "deploy", "publish", "send"):
                if re.search(r"\bdo not\s+" + verb + r"\b", low) and \
                        re.search(r"\b" + verb + r"\b", tl) and \
                        "do not" not in tl and "don't" not in tl:
                    items.append(ConflictItem(
                        ConflictKind.CONTEXT_OVERRIDE,
                        f"current message forbids '{verb}' that earlier context requested",
                        left=f"context: {verb}", right=f"current: do not {verb}",
                        winner_provenance=ProvenanceKind.EXPLICIT_TEXT,
                        provenance=_prov(text, f"context_override:{verb}")))

    # de-duplicate by (kind, left, right)
    seen = set()
    uniq: List[ConflictItem] = []
    for c in items:
        key = (c.kind, c.left, c.right)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return ConflictResult(tuple(uniq))
