"""provisional_evidence.py — routing targets for records that must not enter the exact ledger (§9)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .evidence_schema import EvidenceRecord

PROVISIONAL, HUMAN_REVIEW, ABSTAIN, CONFLICT_SET = "PROVISIONAL", "HUMAN_REVIEW", "ABSTAIN", "CONFLICT_SET"


@dataclass
class RoutedEvidence:
    authoritative: List[EvidenceRecord] = field(default_factory=list)   # admitted to the exact ledger
    provisional: List[EvidenceRecord] = field(default_factory=list)
    human_review: List[EvidenceRecord] = field(default_factory=list)
    conflict_set: List[EvidenceRecord] = field(default_factory=list)
    blocked: List[dict] = field(default_factory=list)                   # {record, reason}
