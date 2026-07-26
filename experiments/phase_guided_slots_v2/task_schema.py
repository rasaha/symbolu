"""
task_schema.py — v2 composite-identity fact schema + closed vocabulary.

Fixes the failure of v1 (all facts collapsed into ~2 slots) by giving every fact a
DISTINGUISHABLE COMPOSITE IDENTITY (contract × vendor × region × product) with
oracle ids, versioned values (supersession), source authority, risk/approval, and
an effective-after event. Distinct contracts must occupy distinct slots; versions
of the SAME contract supersede in-place.

Vocabulary is closed and word-level so answers are single tokens and answer-position
supervision is well-defined. Entity/contract pools are split-partitioned (train/val/
test disjoint) to prevent identity leakage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Closed vocabulary building blocks
# ---------------------------------------------------------------------------
CONTRACTS = [f"C{i}" for i in range(1, 61)]     # 60 contract ids
VENDORS = [f"V{i}" for i in range(1, 41)]       # 40 vendor ids
REGIONS = [f"R{i}" for i in range(1, 9)]        # 8 regions
PRODUCTS = [f"P{i}" for i in range(1, 13)]      # 12 products
SOURCES = [f"S{i}" for i in range(1, 21)]       # 20 sources
EVENTS = [f"E{i}" for i in range(1, 13)]        # 12 events
VERSIONS = ["v1", "v2", "v3", "v4"]
VALUES = [str(v) for v in range(10, 60)]        # 50 value tokens (chance ~0.02)
RISK = ["low", "medium", "high"]
APPROVAL = ["approved", "pending", "revoked"]
AUTHORITY = ["primary", "secondary", "tertiary"]  # source authority rank

# region aliases for paraphrase queries (indirect identifier, no exact token copy)
REGION_ALIAS = {
    "R1": "northern", "R2": "eastern", "R3": "southern", "R4": "western",
    "R5": "central", "R6": "coastal", "R7": "inland", "R8": "overseas",
}

SPECIAL = [
    "<pad>", "<Q>", "<A>", "<sep>", "INSUFFICIENT",
    # relational / template words
    "contract", "vendor", "region", "product", "value", "version", "source",
    "risk", "flag", "status", "effective", "after", "event", "authority",
    "what", "which", "is", "the", "latest", "valid", "of", "for", "current",
    "before", "amendment", "superseded", "authorized", "by", "approved", "with",
    "above", "below", "and", "unresolved", "supplier", "in", "record", "amended",
    "revoked", "than", "greater", "flagged",
]


@dataclass(frozen=True)
class Vocab:
    stoi: Dict[str, int]
    itos: List[str]

    @property
    def size(self) -> int:
        return len(self.itos)

    def id(self, w: str) -> int:
        return self.stoi[w]

    def encode(self, ws: List[str]) -> List[int]:
        unk = self.stoi["<sep>"]
        return [self.stoi.get(w, unk) for w in ws]

    @property
    def pad_id(self) -> int:
        return self.stoi["<pad>"]


def build_vocab() -> Vocab:
    words: List[str] = list(SPECIAL)
    words += CONTRACTS + VENDORS + REGIONS + PRODUCTS + SOURCES + EVENTS
    words += VERSIONS + VALUES + RISK + APPROVAL + AUTHORITY
    words += list(REGION_ALIAS.values())
    seen, ordered = set(), []
    for w in words:
        if w not in seen:
            seen.add(w); ordered.append(w)
    return Vocab(stoi={w: i for i, w in enumerate(ordered)}, itos=ordered)


@dataclass
class Fact:
    """A single versioned statement about a contract (its composite identity)."""
    contract: str
    vendor: str
    region: str
    product: str
    version: str
    value: str
    source: str
    authority: str
    risk: str
    approval: str
    event: str
    # oracle identity (for instrumentation; never seen by the model)
    fact_id: int = -1
    entity_id: int = -1     # contract-level identity (the slot identity)
    relation_id: int = -1
    version_id: int = -1
    source_id: int = -1
    arrival: int = -1       # arrival order in the fact stream

    def render(self) -> List[str]:
        return ["contract", self.contract, "vendor", self.vendor, "region", self.region,
                "product", self.product, "value", self.value, "version", self.version,
                "source", self.source, "authority", self.authority, "risk", self.risk,
                "status", self.approval, "effective", "after", "event", self.event, "<sep>"]

    def anchor_word(self) -> str:
        # the write-anchor token (value) — where we place the per-fact write label
        return "value"


@dataclass
class Example:
    tokens: List[int]
    answer_pos: int
    answer_id: int
    write_labels: List[int]            # 1 at each fact's write-anchor, -100 elsewhere
    facts: List[Fact]
    gold_support_entity_ids: List[int]  # slot identities that must be retained
    query_type: str
    target_position: str               # early / middle / late
    meta: Dict = field(default_factory=dict)
