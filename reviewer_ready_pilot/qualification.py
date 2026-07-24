"""Phase 7 - Reviewer qualification scorer.

Scores the responses a REAL candidate reviewer submits on the training-derived qualification quiz against
the criteria in docs/reviewer_ready_pilot/REVIEWER_QUALIFICATION_PROTOCOL.md. Gates who may submit
final-set labels.

HONESTY (binding, enforced by construction):
  * This module SCORES responses; it NEVER synthesizes a reviewer's answers. `score_candidate` requires
    caller-supplied responses. There is no function that fabricates responses.
  * Any response set flagged `is_mock=True` (used only to exercise the scorer in tests) is scored the same
    way but callers must exclude mock results from any real qualification record.
  * Qualification draws only from the TRAINING set (revealed labels); the final review set is never used.
  * The frozen minimal policy is consumed READ-ONLY, only to supply the reference obligation for a quiz
    item. No policy rule is modified or tuned here.

A candidate qualifies only if every criterion (C1..C8) passes. Safe (upward) errors are tolerated; unsafe
(downward) errors fail. Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_ORDER = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "ER": 5}
_RISK_FLOOR = {"low": "E1", "medium": "E2", "high": "E3", "critical": "E4", "unknown": "ER"}
_HIGH_RISK = {"high", "critical"}
_TRAP_FAMILIES = {"self_verification", "circular_evidence", "stale_authority", "fixture_as_telemetry",
                  "impl_as_operational", "action_no_approval", "attribution_as_truth", "high_risk_opinion"}


def short_level(ob: Optional[str]) -> Optional[str]:
    """Normalize a policy obligation code (short 'E2' or long 'E2_AUTHORITATIVE_...') to E0..ER."""
    if ob is None:
        return None
    head = ob.split("_", 1)[0]
    return head if head in _ORDER else ob


def _ge(a: str, b: str) -> bool:
    """obligation a is at least as strict as b (both normalized to short levels)."""
    return _ORDER.get(short_level(a), -1) >= _ORDER.get(short_level(b), 99)


@dataclass
class Criterion:
    key: str
    label: str
    passed: bool
    detail: str = ""


@dataclass
class QualificationResult:
    reviewer_id: str
    is_mock: bool
    qualified: bool
    criteria: List[Criterion] = field(default_factory=list)
    scores: Dict[str, Any] = field(default_factory=dict)
    n_items: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {"reviewer_id": self.reviewer_id, "is_mock": self.is_mock, "qualified": self.qualified,
                "n_items": self.n_items,
                "criteria": [{"key": c.key, "label": c.label, "passed": c.passed, "detail": c.detail}
                             for c in self.criteria],
                "scores": self.scores}


def _item_index(quiz_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {it["artifact_id"]: it for it in quiz_items}


def score_candidate(reviewer_id: str,
                    quiz_items: List[Dict[str, Any]],
                    responses: List[Dict[str, Any]],
                    is_mock: bool = False) -> QualificationResult:
    """Grade `responses` (submitted by a real candidate) against `quiz_items` (drawn from the training set).

    `quiz_items`   : each has artifact_id, gold_obligation, risk_tier / risk_floor, optional trap_type,
                     claim_family / claim_actionability (to know if it is action-bearing).
    `responses`    : each has artifact_id, obligation, risk_floor, trap_detected, action_requires_approval.
                     THESE COME FROM A HUMAN. This function does not and cannot create them.
    """
    if responses is None:
        raise ValueError("responses must be supplied by a real candidate; the scorer never generates them")

    idx = _item_index(quiz_items)
    n = 0
    # per-criterion accumulators
    unsafe_downgrade = []              # C1
    risk_correct = 0; risk_total = 0    # C2
    traps_flagged = set()               # C3
    traps_present = set()
    unsafe_trap_level = []              # C3/C4 safety
    selfcirc_ok = True                  # C4
    attribution_ok = True               # C5
    action_ok = True                    # C6
    er_unknown_ok = True                # C7
    e2e3_correct = 0; e2e3_total = 0    # C8

    for r in responses:
        it = idx.get(r.get("artifact_id"))
        if it is None:
            continue
        n += 1
        gold = short_level(it.get("gold_obligation"))
        risk = it.get("risk_tier") or it.get("risk_floor") or "unknown"
        floor = _RISK_FLOOR.get(risk, "ER")
        resp_ob = short_level(r.get("obligation"))
        trap = it.get("trap_type")
        is_action = (it.get("claim_actionability") in ("action_directive", "action_recommendation")
                     or it.get("claim_family") == "action_proposal")

        # C1 no high-risk downgrade / never below floor
        if resp_ob is not None:
            if risk in _HIGH_RISK and resp_ob == "E0":
                unsafe_downgrade.append(it["artifact_id"])
            elif not _ge(resp_ob, floor):
                unsafe_downgrade.append(it["artifact_id"])

        # C2 risk floor read (upward tolerated)
        risk_total += 1
        rf = r.get("risk_floor")
        if rf == risk:
            risk_correct += 1
        elif rf in _RISK_FLOOR and _ORDER.get(_RISK_FLOOR[rf], -1) >= _ORDER.get(floor, 99):
            risk_correct += 1  # conservative upward read counts as safe-correct

        # C3 trap detection
        if trap in _TRAP_FAMILIES:
            traps_present.add(trap)
            if r.get("trap_detected") == trap:
                traps_flagged.add(trap)
            # safety: if they under-leveled a trap that demands >= E3, that's unsafe
            if trap in ("self_verification", "circular_evidence", "fixture_as_telemetry",
                        "impl_as_operational", "stale_authority") and resp_ob is not None:
                if not _ge(resp_ob, "E3"):
                    unsafe_trap_level.append(it["artifact_id"])

        # C4 self-verification / circularity >= E3
        if trap in ("self_verification", "circular_evidence") and resp_ob is not None:
            if not _ge(resp_ob, "E3"):
                selfcirc_ok = False

        # C5 attribution != truth
        if trap == "attribution_as_truth" and resp_ob is not None:
            if resp_ob == "E0" or (gold and not _ge(resp_ob, gold)):
                attribution_ok = False

        # C6 action -> approval and >= E3
        if is_action:
            if not r.get("action_requires_approval") or (resp_ob is not None and not _ge(resp_ob, "E3")):
                action_ok = False

        # C7 ER on unknown
        if risk == "unknown" and resp_ob is not None and resp_ob != "ER":
            er_unknown_ok = False

        # C8 E2 vs E3 discrimination on relevant items
        if gold in ("E2", "E3") and trap is None and resp_ob is not None:
            e2e3_total += 1
            if resp_ob == gold:
                e2e3_correct += 1

    risk_rate = (risk_correct / risk_total) if risk_total else 0.0
    e2e3_rate = (e2e3_correct / e2e3_total) if e2e3_total else 1.0

    criteria = [
        Criterion("C1", "No high-risk downgrade / never below risk floor",
                  not unsafe_downgrade, f"{len(unsafe_downgrade)} unsafe downgrade(s)"),
        Criterion("C2", "Risk-floor agreement >= 80% (upward tolerated)",
                  risk_rate >= 0.80, f"{risk_correct}/{risk_total} = {risk_rate:.0%}"),
        Criterion("C3", "Trap detection >= 7/8 families and no unsafe under-leveling",
                  len(traps_flagged & traps_present) >= min(7, len(traps_present)) and not unsafe_trap_level,
                  f"flagged {len(traps_flagged & traps_present)}/{len(traps_present)}; "
                  f"{len(unsafe_trap_level)} under-leveled"),
        Criterion("C4", "Self-verification / circular >= E3 (INV-1/INV-2)", selfcirc_ok),
        Criterion("C5", "Attribution not treated as truth", attribution_ok),
        Criterion("C6", "Action items require approval and >= E3", action_ok),
        Criterion("C7", "ER chosen on unknown risk/authority/type", er_unknown_ok),
        Criterion("C8", "E2-vs-E3 discrimination >= 70%",
                  e2e3_rate >= 0.70, f"{e2e3_correct}/{e2e3_total} = {e2e3_rate:.0%}"),
    ]
    qualified = all(c.passed for c in criteria) and n > 0
    return QualificationResult(
        reviewer_id=reviewer_id, is_mock=is_mock, qualified=qualified, criteria=criteria, n_items=n,
        scores={"risk_rate": risk_rate, "e2e3_rate": e2e3_rate,
                "traps_flagged": sorted(traps_flagged & traps_present),
                "unsafe_downgrades": unsafe_downgrade, "unsafe_trap_levels": unsafe_trap_level})


def build_quiz(training_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Draw quiz items from the TRAINING set only. Returns the items WITH their reference labels retained
    (the administrator uses these to grade; the candidate is shown a blinded copy). Never draws from the
    final review set. Deterministic (sorted by artifact_id)."""
    items = [dict(it) for it in training_items]
    items.sort(key=lambda x: x["artifact_id"])
    return items


def blind_quiz(quiz_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The copy shown to the candidate: strip revealed labels/explanations."""
    strip = ("gold_obligation", "gold_explanation", "invariants_triggered")
    return [{k: v for k, v in it.items() if k not in strip} for it in quiz_items]


if __name__ == "__main__":
    from reviewer_ready_pilot import dataset
    quiz = build_quiz(dataset.load_training())
    print(f"qualification quiz drawn from training set: {len(quiz)} items "
          f"({sum(1 for i in quiz if i.get('synthetic'))} traps)")
    print("no candidate responses exist in this track; scorer awaits real submissions")
