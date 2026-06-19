"""
test_outcome_reputation.py — deterministic rules for the Phase 2 reputation observable.

Covers classification of prior outcomes, the rate computations, the SAFE/UNSURE/UNSAFE verdict
thresholds, the minimum-volume inertness, the asymmetry (only lowers trust), and the
confirm-only (PROVISIONAL) guarantee.
"""

from __future__ import annotations

from types import SimpleNamespace

from agentic.agentic_framework.trust.decision import decide
from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    ObservableType,
    TrustDecision,
    Verdict,
)
from agentic.agentic_framework.trust.outcome_reputation import (
    build_reputation_observation,
    compute_reputation,
)


def _e(tool, decision, human_confirmed=False):
    return SimpleNamespace(tool_name=tool,
                           decision=SimpleNamespace(value=decision),
                           human_confirmed=human_confirmed)


def _history(tool, *, approved=0, denied=0, blocked=0, auto=0, error=0):
    out = []
    out += [_e(tool, "allowed", True) for _ in range(approved)]
    out += [_e(tool, "escalate") for _ in range(denied)]
    out += [_e(tool, "blocked") for _ in range(blocked)]
    out += [_e(tool, "allowed", False) for _ in range(auto)]
    out += [_e(tool, "error") for _ in range(error)]
    return out


# ---- aggregation ------------------------------------------------------------

def test_rates_and_filtering_by_tool():
    entries = _history("t", approved=3, denied=1, blocked=1) + _history("other", blocked=9)
    s = compute_reputation(entries, tool_name="t")
    assert s.n == 5 and s.approvals == 3 and s.denials == 1 and s.blocked == 1
    assert abs(s.approval_rate - 0.75) < 1e-9
    assert abs(s.violation_rate - 0.2) < 1e-9
    assert abs(s.confirmation_rate - 0.8) < 1e-9     # 4 adjudicated / 5


# ---- verdict thresholds -----------------------------------------------------

def test_good_reputation_is_safe():
    s = compute_reputation(_history("t", approved=6, auto=4), tool_name="t")
    assert build_reputation_observation(s).verdict == Verdict.SAFE


def test_mostly_denied_is_poor_unsure():
    s = compute_reputation(_history("t", approved=1, denied=4, auto=3), tool_name="t")
    obs = build_reputation_observation(s)
    assert obs.verdict == Verdict.UNSURE             # approval_rate 0.2 < floor


def test_all_denied_is_egregious_unsafe():
    s = compute_reputation(_history("t", denied=5, auto=3), tool_name="t")
    assert build_reputation_observation(s).verdict == Verdict.UNSAFE   # approval_rate 0.0


def test_recurring_violations_is_poor_or_egregious():
    poor = compute_reputation(_history("t", blocked=3, auto=3), tool_name="t")  # 0.5
    assert build_reputation_observation(poor).verdict in (Verdict.UNSURE, Verdict.UNSAFE)
    egr = compute_reputation(_history("t", blocked=9, auto=1), tool_name="t")   # 0.9
    assert build_reputation_observation(egr).verdict == Verdict.UNSAFE


def test_recurring_denied_escalations_is_poor():
    # recurring DENIED escalations (high denial_rate) → poor, even at borderline approval.
    s = compute_reputation(_history("t", approved=3, denied=3, auto=0), tool_name="t")
    assert s.denial_rate >= 0.3
    assert build_reputation_observation(s).verdict == Verdict.UNSURE


def test_high_confirmation_but_approved_is_safe():
    # an approval-gated action humans consistently APPROVE is NOT poor (asymmetry/no friction
    # penalty): high confirmation_rate but high approval_rate and zero denials → SAFE.
    s = compute_reputation(_history("t", approved=8, auto=1), tool_name="t")
    assert s.confirmation_rate >= 0.6 and s.denial_rate == 0.0
    assert build_reputation_observation(s).verdict == Verdict.SAFE


# ---- minimum volume / inertness --------------------------------------------

def test_below_min_volume_is_inert():
    s = compute_reputation(_history("t", denied=4), tool_name="t")   # n=4 < 5
    assert build_reputation_observation(s) is None


def test_no_history_is_inert():
    s = compute_reputation([], tool_name="t")
    assert s.n == 0
    assert build_reputation_observation(s) is None


# ---- taxonomy + asymmetry + confirm-only ------------------------------------

def test_observation_is_provisional_validator():
    s = compute_reputation(_history("t", denied=5, auto=2), tool_name="t")
    obs = build_reputation_observation(s)
    assert obs.otype == ObservableType.VALIDATOR
    assert obs.evidence == EvidenceStatus.PROVISIONAL
    assert obs.name == "outcome_reputation" and obs.detail["n"] == 7


def test_provisional_only_confirms_never_blocks():
    s = compute_reputation(_history("t", denied=6, auto=1), tool_name="t")  # egregious
    obs = build_reputation_observation(s)
    assert obs.verdict == Verdict.UNSAFE
    assert decide([obs]).decision == TrustDecision.CONFIRM     # never BLOCK while provisional


def test_good_reputation_never_raises_trust():
    # asymmetry: a SAFE reputation contributes no escalation (decision stays ALLOW).
    s = compute_reputation(_history("t", approved=8, auto=4), tool_name="t")
    obs = build_reputation_observation(s)
    assert obs.verdict == Verdict.SAFE
    assert decide([obs]).decision == TrustDecision.ALLOW


def test_promoted_egregious_would_block():
    s = compute_reputation(_history("t", blocked=9, auto=1), tool_name="t")
    obs = build_reputation_observation(s, evidence=EvidenceStatus.PROVEN)
    assert decide([obs]).decision == TrustDecision.BLOCK
