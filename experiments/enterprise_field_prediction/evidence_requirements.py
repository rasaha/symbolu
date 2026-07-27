"""
evidence_requirements.py — the field→evidence contract (§4), derived from `field_contracts`.

For every field: required evidence types, optional evidence, deterministic prerequisites, the
relation path from the runtime query anchor, the version-selection rule, the conflict rule, and the
valid abstention condition. A field head must not emit a confident value when its evidence contract
is incomplete — `sufficient_support` encodes that check.
"""
from __future__ import annotations

from typing import Dict, List

from .field_contracts import CONTRACTS, FieldContract


def requirements(field: str) -> Dict:
    c: FieldContract = CONTRACTS[field]
    return {"required_evidence": c.required_evidence, "optional_evidence": c.optional_evidence,
            "relation_path": c.relation_path, "version_rule": c.version_rule,
            "conflict_rule": c.conflict_rule, "abstain_when": c.abstain_when,
            "ownership": c.ownership}


def sufficient_support(field: str, present_tags) -> bool:
    """True iff every required-evidence tag for the field is present in the working set."""
    present = set(present_tags)
    return all(tag in present for tag in CONTRACTS[field].required_evidence)


REQUIREMENTS = {f: requirements(f) for f in CONTRACTS}
