"""Ground-truth scenario schema (Task 102) with strict policy/expected separation.

A scenario carries two disjoint regions:

* **provider-facing inputs** — ``assertion``, ``evidence``, ``proposed_action``,
  ``tap_policy``, ``action_policy``, ``execution`` — everything the deployed
  providers/engines see. These emulate the deployed governance *configuration*.
* **expected** — the independently-authored ground truth the evaluator compares
  against. It is **never** passed to any provider (enforced by a Task-103 test).

Deterministic (de)serialization: ``to_dict`` / ``from_dict`` round-trip through
plain JSON with stable key ordering.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from .taxonomy import (
    ActionClass, AssertionClass, ComplianceVerdict, CrossProviderClass,
    ExecutionBehavior, ReconciliationExpectation, RecommendationPosture)


@dataclass(frozen=True)
class EvidenceSpec:
    evidence_id: str
    source_type: str
    source_reference: str
    content: str
    provenance: str
    evidence_class: str = "direct"
    authority: str = ""


@dataclass(frozen=True)
class TapPolicy:
    """Deployed TAP engine configuration for this assertion signature."""

    outcome: str                                    # SUPPORTED/UNSUPPORTED/CONSTRAINED/INDETERMINATE
    evidence_coverage: Optional[float] = None
    supported_components: tuple[str, ...] = ()
    unsupported_components: tuple[str, ...] = ()
    omitted_qualifiers: tuple[str, ...] = ()
    constraints: tuple[tuple[str, str], ...] = ()
    obligations: tuple[tuple[str, str], ...] = ()
    reason_codes: tuple[str, ...] = ()
    fail: Optional[str] = None                       # timeout/unavailable/malformed/protocol/config
    emit_unknown: bool = False
    derive_from_evidence: bool = False               # use stance-derivation instead of a rule


@dataclass(frozen=True)
class ActionPolicy:
    """Deployed ActionGate engine configuration for this action type."""

    mode: str = "allow"                              # allow/deny/unknown/constrained
    constraints: tuple[tuple[str, str], ...] = ()
    obligations: tuple[tuple[str, str], ...] = ()
    expiry_seconds: Optional[int] = None
    fail: Optional[str] = None                        # timeout/unavailable/malformed/config
    available: bool = True                            # False → degraded provider


@dataclass(frozen=True)
class ProposedActionSpec:
    action_type: str
    parameters: dict = field(default_factory=dict)
    authority: str = "gov"
    resource: str = ""
    target_system: str = "SYS"
    domain_id: str = "generic"
    required_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutionSpec:
    transport_fail: bool = False
    timeout: bool = False
    business_outcome: str = "SUCCEEDED"               # BusinessOutcome name
    observed_overrides: dict = field(default_factory=dict)  # → reconciliation mismatch


@dataclass(frozen=True)
class HumanReviewSpec:
    """Deterministic human-review fixture (Task 106). Human authority only."""

    action: str                                       # supply_evidence/approve/decline/accept_constrained/reject
    approver: str = "reviewer"
    added_evidence: tuple[EvidenceSpec, ...] = ()
    reevaluate_tap: Optional[TapPolicy] = None        # TAP re-evaluation after new evidence
    note: str = ""


@dataclass(frozen=True)
class ExpectedOutcome:
    """Independently-authored ground truth — evaluator-only, never seen by providers."""

    tap_outcome: str
    supported_components: tuple[str, ...] = ()
    unsupported_components: tuple[str, ...] = ()
    omitted_qualifiers: tuple[str, ...] = ()
    evidence_coverage: Optional[float] = None
    recommendation_posture: str = RecommendationPosture.ADVANCE.value
    actiongate_outcome: str = "AUTHORIZED"
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    dispatched: bool = False
    execution_behavior: str = ExecutionBehavior.NOT_DISPATCHED.value
    reconciliation: str = ReconciliationExpectation.NONE.value
    compliance_verdict: str = ComplianceVerdict.NOT_APPLICABLE.value
    audit_milestones: tuple[str, ...] = ()


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    domain: str
    assertion_class: str
    action_class: str
    cross_class: str
    assertion: str
    assertion_type: str
    evidence: tuple[EvidenceSpec, ...]
    tap_policy: TapPolicy
    action_policy: ActionPolicy
    proposed_action: ProposedActionSpec
    execution: ExecutionSpec
    expected: ExpectedOutcome
    human_review: Optional[HumanReviewSpec] = None
    notes: str = ""

    # --- (de)serialization -------------------------------------------------

    def to_dict(self) -> dict:
        return _order(asdict(self))

    @staticmethod
    def from_dict(data: dict) -> "Scenario":
        ev = tuple(EvidenceSpec(**_pick(e, EvidenceSpec)) for e in data["evidence"])
        tp = TapPolicy(**_tuples(_pick(data["tap_policy"], TapPolicy),
                                 ("supported_components", "unsupported_components",
                                  "omitted_qualifiers", "reason_codes"),
                                 pairs=("constraints", "obligations")))
        ap = ActionPolicy(**_tuples(_pick(data["action_policy"], ActionPolicy), (),
                                    pairs=("constraints", "obligations")))
        pa = ProposedActionSpec(**_tuples(_pick(data["proposed_action"], ProposedActionSpec),
                                          ("required_fields",)))
        ex = ExecutionSpec(**_pick(data["execution"], ExecutionSpec))
        exp = ExpectedOutcome(**_tuples(_pick(data["expected"], ExpectedOutcome),
                                        ("supported_components", "unsupported_components",
                                         "omitted_qualifiers", "constraints", "obligations",
                                         "audit_milestones")))
        hr = None
        if data.get("human_review"):
            hd = data["human_review"]
            added = tuple(EvidenceSpec(**_pick(e, EvidenceSpec)) for e in hd.get("added_evidence", []))
            reev = None
            if hd.get("reevaluate_tap"):
                reev = TapPolicy(**_tuples(_pick(hd["reevaluate_tap"], TapPolicy),
                                           ("supported_components", "unsupported_components",
                                            "omitted_qualifiers", "reason_codes"),
                                           pairs=("constraints", "obligations")))
            hr = HumanReviewSpec(action=hd["action"], approver=hd.get("approver", "reviewer"),
                                 added_evidence=added, reevaluate_tap=reev, note=hd.get("note", ""))
        return Scenario(
            scenario_id=data["scenario_id"], domain=data["domain"],
            assertion_class=data["assertion_class"], action_class=data["action_class"],
            cross_class=data["cross_class"], assertion=data["assertion"],
            assertion_type=data["assertion_type"], evidence=ev, tap_policy=tp,
            action_policy=ap, proposed_action=pa, execution=ex, expected=exp,
            human_review=hr, notes=data.get("notes", ""))


def _pick(d: dict, cls) -> dict:
    names = {f for f in cls.__dataclass_fields__}
    return {k: v for k, v in d.items() if k in names}


def _tuples(d: dict, list_keys, pairs=()) -> dict:
    out = dict(d)
    for k in list_keys:
        if k in out and out[k] is not None:
            out[k] = tuple(out[k])
    for k in pairs:
        if k in out and out[k] is not None:
            out[k] = tuple(tuple(pair) for pair in out[k])
    return out


def _order(value):
    if isinstance(value, dict):
        return {k: _order(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_order(v) for v in value]
    return value


ASSERTION_CLASSES = tuple(c.value for c in AssertionClass)
ACTION_CLASSES = tuple(c.value for c in ActionClass)
CROSS_CLASSES = tuple(c.value for c in CrossProviderClass)
