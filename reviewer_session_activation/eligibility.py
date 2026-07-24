"""Reviewer eligibility gate for a REAL calibration round activation.

Validates a supplied reviewer roster against the frozen governance requirements
(REVIEWER_GOVERNANCE_PROTOCOL.md, REVIEWER_ROLE_MODEL.md) BEFORE any session activates. This is an
activation gate; it consumes the frozen reviewer_ready_pilot apparatus read-only and builds no new review
infrastructure.

Hard honesty rules (enforced here, non-negotiable):
  * A field left as an unfilled template placeholder (e.g. "[R1_ID]", "[YES/NO]", "[SCOPE]") is treated as
    MISSING - never inferred as complete.
  * `real_reviewer` must be an explicit boolean True. A placeholder or "YES" string that is not backed by
    a filled, non-placeholder pseudonymous ID does not make a reviewer real.
  * A reviewer flagged mock/test, or carrying a mock/test-looking ID, can NEVER be treated as real.
  * The gate NEVER fabricates a reviewer, and NEVER upgrades a failing field.

A roster passes only if every required reviewer is REAL and every eligibility field is satisfied.
Deterministic, stdlib-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from reviewer_ready_pilot.review_interface import _BLINDED_FIELDS  # noqa: F401  (read-only apparatus link)

VALID_ROLES = {"TECHNICAL REVIEWER", "POLICY-RISK REVIEWER", "DOMAIN REVIEWER", "INDEPENDENT ADJUDICATOR"}
_PLACEHOLDER = re.compile(r"^\s*\[.*\]\s*$")          # e.g. "[R1_ID]", "[YES/NO]"
_MOCKISH = re.compile(r"\b(mock|test|dummy|fake|sample|example|placeholder)\b", re.I)
# Substantive-independence exclusion (REVIEWER_GOVERNANCE_PROTOCOL.md / REVIEWER_RECRUITMENT_PLAN.md):
# "No reviewer who authored the frozen policy's rules or has a stake in its acceptance." A self-declared
# COI = YES attests a declaration was filed; it does NOT waive a structural stake. This flag is categorical
# and independent of the checkbox.
_STAKEHOLDER = re.compile(
    r"\b(founder|co-?founder|owner of|product owner|policy (author|owner)|authored the (policy|rules?)"
    r"|created the (policy|system|architecture)|inventor|maintainer of the (policy|rules?)"
    r"|stake in (its|the policy'?s) acceptance)\b", re.I)


def is_placeholder(v: Any) -> bool:
    """True if the value is empty, None, or an unfilled template placeholder like '[...]'."""
    if v is None:
        return True
    if isinstance(v, str):
        s = v.strip()
        if s == "" or _PLACEHOLDER.match(s):
            return True
    return False


def _yes(v: Any) -> bool:
    """A field is affirmatively YES only if it is a filled, non-placeholder 'YES' (case-insensitive)."""
    if is_placeholder(v):
        return False
    return isinstance(v, str) and v.strip().upper() == "YES"


@dataclass
class ReviewerEligibility:
    slot: str                              # R1, R2, A1
    reviewer_id: Optional[str]
    role: Optional[str]
    passed: bool
    failures: List[str] = field(default_factory=list)
    is_real: bool = False
    is_adjudicator: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {"slot": self.slot, "reviewer_id": self.reviewer_id, "role": self.role,
                "passed": self.passed, "is_real": self.is_real, "is_adjudicator": self.is_adjudicator,
                "failures": self.failures}


def validate_reviewer(slot: str, r: Dict[str, Any], *, required: bool = True,
                      prohibited_artifacts: Optional[set] = None) -> ReviewerEligibility:
    prohibited_artifacts = prohibited_artifacts or set()
    failures: List[str] = []

    rid = r.get("pseudonymous_id")
    role = r.get("role")
    is_adj = (not is_placeholder(role) and str(role).strip().upper() == "INDEPENDENT ADJUDICATOR") \
        or slot.upper().startswith("A")

    # An optional adjudicator slot explicitly marked NONE / NOT APPLICABLE is simply absent (not a failure).
    if not required:
        raw_id = "" if rid is None else str(rid).strip().upper()
        if raw_id in ("NONE", "NOT APPLICABLE", "N/A") or is_placeholder(rid):
            return ReviewerEligibility(slot=slot, reviewer_id=None, role=None, passed=False,
                                       failures=["absent / not supplied"], is_real=False,
                                       is_adjudicator=True)

    # pseudonymous, non-placeholder ID
    if is_placeholder(rid):
        failures.append("pseudonymous_id is missing / unfilled placeholder")
    elif _MOCKISH.search(str(rid)):
        failures.append("pseudonymous_id looks like a mock/test identity")

    # explicit real-person status: an affirmative flag ALONE is not enough - a real reviewer must also
    # have a filled, non-placeholder, non-mock pseudonymous ID. A "YES" behind "[R1_ID]" is not a person.
    real_flag = r.get("real_reviewer")
    real_flag_ok = (real_flag is True) or _yes(real_flag)
    id_backed = not is_placeholder(rid) and not _MOCKISH.search(str(rid or ""))
    is_real = real_flag_ok and id_backed
    if not real_flag_ok:
        failures.append("real_reviewer is not explicitly confirmed True/YES")
    elif not id_backed:
        failures.append("real_reviewer asserted but not backed by a filled, non-placeholder ID")
    if r.get("is_mock") or r.get("is_test"):
        failures.append("reviewer is flagged mock/test")
        is_real = False

    # role assigned + valid
    if is_placeholder(role):
        failures.append("role is missing / unfilled placeholder")
    elif str(role).strip().upper() not in VALID_ROLES:
        failures.append(f"role '{role}' is not a recognized role")

    # confidentiality acknowledgment
    if not _yes(r.get("confidentiality_ack")):
        failures.append("confidentiality acknowledgment not complete (YES required)")

    # adjudicator uses an independence declaration instead of COI
    if is_adj:
        if not _yes(r.get("independence_declaration")):
            failures.append("adjudicator independence declaration not complete (YES required)")
    else:
        if not _yes(r.get("coi_declaration")):
            failures.append("conflict-of-interest declaration not complete (YES required)")

    # approved access scope
    if is_placeholder(r.get("access_scope")):
        failures.append("approved access scope is missing / unfilled placeholder")

    # substantive independence: exclude authors of / stakeholders in the frozen policy (categorical;
    # a self-declared COI = YES does not waive it). Applies to reviewers, not the adjudicator role check.
    stake_text = f"{role or ''} {r.get('expertise', '') or ''}"
    if not is_adj and _STAKEHOLDER.search(stake_text):
        failures.append("independence: declared role/expertise indicates authorship of or a stake in the "
                        "policy's acceptance (e.g. founder / product owner); the governance protocol "
                        "excludes stakeholders regardless of a self-declared COI = YES")

    # no prohibited artifacts assigned
    assigned = set(r.get("assigned_artifacts", []) or [])
    if assigned & prohibited_artifacts:
        failures.append(f"assigned prohibited artifacts: {sorted(assigned & prohibited_artifacts)}")

    return ReviewerEligibility(slot=slot, reviewer_id=(None if is_placeholder(rid) else rid),
                               role=(None if is_placeholder(role) else role),
                               passed=not failures, failures=failures, is_real=is_real,
                               is_adjudicator=is_adj)


@dataclass
class EligibilityReport:
    activatable: bool
    reviewers: List[ReviewerEligibility]
    real_reviewer_count: int
    adjudicator: Optional[ReviewerEligibility]
    reason: str

    def as_dict(self) -> Dict[str, Any]:
        return {"activatable": self.activatable, "real_reviewer_count": self.real_reviewer_count,
                "reason": self.reason,
                "reviewers": [r.as_dict() for r in self.reviewers],
                "adjudicator": self.adjudicator.as_dict() if self.adjudicator else None}


def evaluate_roster(roster: Dict[str, Any], *, prohibited_artifacts: Optional[set] = None) -> EligibilityReport:
    """`roster`: {"R1": {...}, "R2": {...}, "A1": {...optional...}}. Both R1 and R2 must pass and be REAL
    for the session to be activatable."""
    reviewers: List[ReviewerEligibility] = []
    for slot in ("R1", "R2"):
        reviewers.append(validate_reviewer(slot, roster.get(slot, {}) or {},
                                           required=True, prohibited_artifacts=prohibited_artifacts))
    adj = None
    if "A1" in roster:
        adj = validate_reviewer("A1", roster.get("A1", {}) or {}, required=False,
                                prohibited_artifacts=prohibited_artifacts)

    real_count = sum(1 for r in reviewers if r.is_real and r.passed)
    both_pass = all(r.passed and r.is_real for r in reviewers)
    if both_pass:
        reason = "Both R1 and R2 are real and pass every eligibility field."
    else:
        reason = ("Activation blocked: not all required reviewers are real and eligible. "
                  + "; ".join(f"{r.slot}: {', '.join(r.failures)}" for r in reviewers if not r.passed))
    return EligibilityReport(activatable=both_pass, reviewers=reviewers, real_reviewer_count=real_count,
                             adjudicator=adj, reason=reason)
