"""
field_contracts.py — typed field vocabularies + exact semantic contracts (§3/§4/§8).

Each field carries a finite typed vocabulary, an UNKNOWN/INSUFFICIENT_EVIDENCE state, its required
and optional evidence, the relation path needed, version/conflict rules, a valid abstention
condition, and an ownership class (DETERMINISTIC / RELATIONAL / HYBRID). Ownership decides whether a
field is computed exactly from the deterministic join or genuinely needs multi-record quadratic
comparison.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

DETERMINISTIC, RELATIONAL, HYBRID, UNRESOLVED = "DETERMINISTIC", "RELATIONAL", "HYBRID", "UNRESOLVED"

# ---- typed vocabularies (last entry is always the abstention/unknown state) ----
BUDGET_STATUS = ("SUFFICIENT", "INSUFFICIENT", "MISSING", "UNKNOWN")
POLICY_STATUS = ("IDENTIFIED", "MISSING", "CONFLICTED", "UNKNOWN")
APPROVAL_REQUIREMENT = (*(f"ROLE_{i}" for i in range(5)), "NONE", "UNKNOWN")
APPROVAL_EVIDENCE = ("PRESENT_VALID", "PRESENT_INVALID", "MISSING", "CONFLICTED", "UNKNOWN")
MATERIAL_CONFLICT = ("NO", "YES", "UNKNOWN")
EVIDENCE_COMPLETE = ("NO", "YES", "UNKNOWN")


@dataclass
class FieldContract:
    name: str
    vocab: Tuple[str, ...]
    ownership: str
    required_evidence: List[str]           # evidence tags that must be present
    optional_evidence: List[str]
    relation_path: List[str]               # deterministic join path from the query anchor
    version_rule: str
    conflict_rule: str
    abstain_when: str                       # condition producing UNKNOWN / INSUFFICIENT
    unknown_index: int

    @property
    def n(self):
        return len(self.vocab)


CONTRACTS = {
    "budget_status": FieldContract(
        "budget_status", BUDGET_STATUS, DETERMINISTIC,
        required_evidence=["budget"], optional_evidence=[], relation_path=["request.has_budget"],
        version_rule="n/a", conflict_rule="n/a",
        abstain_when="no budget record for the request in the working set", unknown_index=3),
    "active_policy_status": FieldContract(
        "active_policy_status", POLICY_STATUS, RELATIONAL,
        required_evidence=["policy_active"], optional_evidence=["policy_superseded", "policy_conflict"],
        relation_path=["request.awarded_to.vendor.governed_by.contract.governed_by.policy"],
        version_rule="latest ACTIVE version among governed_by policies for the contract",
        conflict_rule=">1 ACTIVE policy of different version ⇒ CONFLICTED",
        abstain_when="no active policy record reachable", unknown_index=3),
    "approval_requirement": FieldContract(
        "approval_requirement", APPROVAL_REQUIREMENT, DETERMINISTIC,
        required_evidence=["budget", "policy_active"], optional_evidence=[],
        relation_path=["POLICY_TABLE[active_version][budget_tier]"],
        version_rule="uses active policy version", conflict_rule="n/a",
        abstain_when="budget tier or active policy version unavailable", unknown_index=6),
    "approval_evidence_status": FieldContract(
        "approval_evidence_status", APPROVAL_EVIDENCE, RELATIONAL,
        required_evidence=["approval_requirement"], optional_evidence=["approval"],
        relation_path=["request.authorized_by.role == approval_requirement"],
        version_rule="n/a", conflict_rule="conflicting authority records ⇒ CONFLICTED",
        abstain_when="approval requirement unresolved", unknown_index=4),
    "material_conflict": FieldContract(
        "material_conflict", MATERIAL_CONFLICT, RELATIONAL,
        required_evidence=["policy_active"], optional_evidence=["policy_conflict"],
        relation_path=["governed_by policies for the contract"],
        version_rule="n/a", conflict_rule=">1 ACTIVE governance record of different version/object",
        abstain_when="fewer than one governance record present", unknown_index=2),
    "evidence_complete": FieldContract(
        "evidence_complete", EVIDENCE_COMPLETE, DETERMINISTIC,
        required_evidence=["budget", "policy_active"], optional_evidence=[],
        relation_path=["presence(budget) AND presence(active policy)"],
        version_rule="n/a", conflict_rule="n/a",
        abstain_when="never (presence is directly observable)", unknown_index=2),
}

FIELDS = tuple(CONTRACTS.keys())
DETERMINISTIC_FIELDS = tuple(f for f, c in CONTRACTS.items() if c.ownership == DETERMINISTIC)
RELATIONAL_FIELDS = tuple(f for f, c in CONTRACTS.items() if c.ownership == RELATIONAL)
