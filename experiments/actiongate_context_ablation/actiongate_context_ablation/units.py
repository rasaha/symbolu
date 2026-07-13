"""Semantic-unit model for context ablation.

A ``Context`` is an ordered list of ``SemanticUnit``s plus an un-ablatable
``base`` (the action identity: tool/verb/target the request always carries). Each
unit declares an *oracle contribution* (``contrib``) — the structured fragment it
adds to the request spec — and the natural-language ``text`` a realistic
extractor would have to parse to recover that fragment. The two are kept separate
so we can measure extractor error against ground truth (see extractor.py).

Token counts use a transparent regex word/punct tokenizer, NOT a model BPE
tokenizer. This is an approximation and is documented as such wherever token
fractions are reported.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Frozen unit-type taxonomy (task "Unit taxonomy").
SOURCE_TYPES = frozenset({
    "sentence", "clause", "list_item", "table_row", "table_cell", "json_field",
    "policy_rule", "exception", "approval_record", "evidence_record", "state_fact",
    "log_event", "tool_argument", "retrieved_passage", "chat_turn",
})

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def count_tokens(text: str) -> int:
    """Transparent word/punct token count (approximation, not a model tokenizer)."""
    return len(_TOKEN_RE.findall(text or ""))


@dataclass(frozen=True)
class SemanticUnit:
    id: str
    source_type: str
    text: str
    contrib: dict = field(default_factory=dict)   # oracle fragment -> request spec
    parent: str | None = None                      # group id
    provenance: str = "authored-fixture"
    references: tuple = ()                          # ids this unit points at
    dependency_links: tuple = ()                   # ids this unit needs to be meaningful
    redundancy_set: str | None = None              # shared id across duplicate facts

    def __post_init__(self):
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"unknown source_type {self.source_type!r}")

    @property
    def token_count(self) -> int:
        return count_tokens(self.text)


@dataclass(frozen=True)
class Context:
    """An ablatable context.

    ``base`` holds the action identity that is NOT a unit (so every ablation still
    yields a buildable envelope); units contribute args/evidence/approvals/target
    modifiers/reversibility/credential-scope/state on top of it.
    """

    id: str
    base: dict                     # {tool, verb, target:[...], principal?, ...}
    units: tuple                   # tuple[SemanticUnit], source order
    data_origin: str               # see origin.py
    description: str = ""
    # preregistered linked pairs to test jointly: tuple of (id_a, id_b, label)
    linked_pairs: tuple = ()

    def unit(self, uid: str) -> SemanticUnit:
        for u in self.units:
            if u.id == uid:
                return u
        raise KeyError(uid)

    @property
    def total_tokens(self) -> int:
        return sum(u.token_count for u in self.units)

    def redundancy_sets(self) -> dict:
        """Map redundancy_set id -> list of unit ids sharing it (size >= 2 only)."""
        out: dict[str, list] = {}
        for u in self.units:
            if u.redundancy_set:
                out.setdefault(u.redundancy_set, []).append(u.id)
        return {k: v for k, v in out.items() if len(v) >= 2}

    def groups(self) -> dict:
        """Map parent/group id -> list of unit ids (size >= 1)."""
        out: dict[str, list] = {}
        for u in self.units:
            if u.parent:
                out.setdefault(u.parent, []).append(u.id)
        return out
