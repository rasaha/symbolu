"""Phase 10 - Reviewer label schema + validation.

Defines the structured label a reviewer submits at each stage and validates it. Keeping the schema in one
place lets the interface, metrics, adjudication, and audit all agree on field names and allowed values.

The schema is deliberately explicit about the four things a reviewer must keep separate (obligation
assigned / obligation satisfied / claim true / deliverable-or-action) and about the native ActionGate
vocabulary, which must never be collapsed into allow/deny.

Validation REJECTS malformed labels; it never repairs or invents them. Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = "reviewer_label_v1"

OBLIGATION_LEVELS = ("E0", "E1", "E2", "E3", "E4", "ER")
RISK_TIERS = ("low", "medium", "high", "critical", "unknown")
SOURCE_AUTHORITY = ("authoritative", "non_authoritative", "self_referential", "stale", "unknown")
OVERRIDE_DIRECTIONS = ("stricter", "more_permissive", "none")
# Native ActionGate outcomes - preserved verbatim, never collapsed.
ACTIONGATE_OUTCOMES = ("ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
                       "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY", "not_applicable")


@dataclass
class StageALabel:
    """Blinded judgment - what the reviewer decides WITHOUT seeing the system result."""
    obligation: str = ""                         # OBLIGATION_LEVELS
    risk_tier: str = ""                           # RISK_TIERS
    source_authority: str = ""                    # SOURCE_AUTHORITY
    obligation_satisfied: Optional[bool] = None   # does available evidence meet the obligation?
    action_present: Optional[bool] = None
    action_requires_approval: Optional[bool] = None
    trap_detected: str = "none"                   # trap family name or "none"
    confidence: float = 0.0                       # 0..1
    review_time_seconds: float = 0.0
    reason: str = ""


@dataclass
class StageBLabel:
    """Post-reveal judgment - after the system result is shown."""
    obligation: str = ""
    agreement: Optional[bool] = None              # agrees with the system obligation?
    override: Optional[bool] = None
    override_direction: str = "none"              # OVERRIDE_DIRECTIONS
    override_reason: str = ""
    acceptable_actiongate_outcome: str = "not_applicable"   # ACTIONGATE_OUTCOMES
    explanation_useful: Optional[int] = None      # 1..5
    trace_comprehensible: Optional[bool] = None
    missing_context: Optional[bool] = None
    confidence: float = 0.0
    review_time_seconds: float = 0.0
    reason: str = ""


def _err(errors: List[str], cond: bool, msg: str) -> None:
    if not cond:
        errors.append(msg)


def validate_stage_a(label: StageALabel) -> List[str]:
    e: List[str] = []
    _err(e, label.obligation in OBLIGATION_LEVELS, f"obligation must be one of {OBLIGATION_LEVELS}")
    _err(e, label.risk_tier in RISK_TIERS, f"risk_tier must be one of {RISK_TIERS}")
    _err(e, label.source_authority in SOURCE_AUTHORITY, f"source_authority must be one of {SOURCE_AUTHORITY}")
    _err(e, 0.0 <= label.confidence <= 1.0, "confidence must be in [0,1]")
    _err(e, label.review_time_seconds >= 0.0, "review_time_seconds must be >= 0")
    # a claimed high/critical risk must not be labelled E0 (surface guard; the policy is the authority)
    if label.risk_tier in ("high", "critical"):
        _err(e, label.obligation != "E0", "E0 is invalid for high/critical risk")
    if label.action_present:
        _err(e, label.action_requires_approval is True,
             "action_present implies action_requires_approval=True")
    return e


def validate_stage_b(label: StageBLabel) -> List[str]:
    e: List[str] = []
    _err(e, label.obligation in OBLIGATION_LEVELS, f"obligation must be one of {OBLIGATION_LEVELS}")
    _err(e, label.override_direction in OVERRIDE_DIRECTIONS,
         f"override_direction must be one of {OVERRIDE_DIRECTIONS}")
    _err(e, label.acceptable_actiongate_outcome in ACTIONGATE_OUTCOMES,
         "acceptable_actiongate_outcome must be a native ActionGate outcome (never collapsed)")
    if label.override:
        _err(e, bool(label.override_reason), "override requires a reason")
        _err(e, label.override_direction in ("stricter", "more_permissive"),
             "override requires a direction")
    else:
        _err(e, label.override_direction == "none", "no override => direction must be 'none'")
    if label.explanation_useful is not None:
        _err(e, 1 <= label.explanation_useful <= 5, "explanation_useful must be 1..5")
    _err(e, 0.0 <= label.confidence <= 1.0, "confidence must be in [0,1]")
    return e


def stage_a_dict(label: StageALabel) -> Dict[str, Any]:
    return asdict(label)


def stage_b_dict(label: StageBLabel) -> Dict[str, Any]:
    return asdict(label)


def is_valid_stage_a(label: StageALabel) -> bool:
    return not validate_stage_a(label)


def is_valid_stage_b(label: StageBLabel) -> bool:
    return not validate_stage_b(label)
