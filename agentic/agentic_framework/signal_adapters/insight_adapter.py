"""
Insight Signal Adapter — Governance-time insight gate resolution (Phase S2).

Wraps the pure-function insight gate logic for governance consumption.
Accepts runtime-safe float inputs, returns structured governance-ready
outputs with eligibility, release status, and bounded confidence effects.

Fail-safe: if insight signals are unavailable, governance proceeds
unchanged (no weakening of posture).

Bounded effects:
- Insight ineligibility → bounded confidence penalty (max 0.10)
- Release disallowed → adds stricter-only confirmation pressure
- Surfacing penalty → informational only (not a hard block)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


# =========================================================================
# Resolution result
# =========================================================================

@dataclass(frozen=True)
class InsightResolution:
    """Resolved insight gate signal for governance use.

    Attributes:
        eligible: Stage 1 passed (system stable enough for insight).
        can_release: Stage 2 passed (risk low enough to release).
        stab_score: System stability score [0, 1].
        risk_score: Disruption risk score [0, 1].
        confidence_penalty: Bounded [0, 0.10] penalty to subtract from
            governance confidence when insight gate signals instability.
            Zero when gate passes or signals unavailable.
        confirmation_pressure: True if release is blocked and governance
            should increase confirmation requirements (stricter-only).
        reason_codes: Machine-readable gate reason codes.
        available: Whether insight signals were successfully computed.
        source_detail: Human-readable description of resolution path.
    """
    eligible: bool
    can_release: bool
    stab_score: float
    risk_score: float
    confidence_penalty: float
    confirmation_pressure: bool
    reason_codes: Tuple[str, ...]
    available: bool
    source_detail: str


# =========================================================================
# Confidence penalty from insight gate
# =========================================================================

# Max confidence penalty from insight gate (bounded, additive)
_MAX_INSIGHT_CONFIDENCE_PENALTY = 0.10
# Stability threshold below which penalty starts
_STAB_PENALTY_THRESHOLD = 0.60


def _compute_insight_confidence_penalty(
    eligible: bool,
    stab_score: float,
) -> float:
    """Compute bounded confidence penalty from insight gate signals.

    Penalty is zero when:
    - Insight gate is eligible (system is stable)
    - Stability is above threshold

    Penalty scales linearly from 0 to max when stability drops below
    threshold. This is additive with other penalties (entropy, etc).
    """
    if eligible:
        return 0.0
    if stab_score >= _STAB_PENALTY_THRESHOLD:
        return 0.0
    # Linear interpolation: stab 0.0 → max penalty, stab threshold → 0
    ratio = 1.0 - (stab_score / _STAB_PENALTY_THRESHOLD)
    return min(_MAX_INSIGHT_CONFIDENCE_PENALTY, ratio * _MAX_INSIGHT_CONFIDENCE_PENALTY)


# =========================================================================
# Resolution logic
# =========================================================================

def resolve_insight_signal(
    *,
    r_acc: Optional[float] = None,
    s_acc: Optional[float] = None,
    guna_coherence: Optional[float] = None,
    drift: Optional[float] = None,
    authority: Optional[float] = None,
    vritti: Optional[int] = None,
    d_max: float = 1.0,
) -> InsightResolution:
    """Resolve insight gate as a governance signal.

    Args:
        r_acc: Ontological accuracy [0, 1]. None if unavailable.
        s_acc: Reality grounding accuracy [0, 1]. None if unavailable.
        guna_coherence: Guna coherence [0, 1]. None if unavailable.
        drift: Semantic drift level. None if unavailable.
        authority: PID governor authority [0, 1]. None if unavailable.
        vritti: Current vritti mode (0-4). None if unavailable.
        d_max: Drift normalization ceiling.

    Returns:
        InsightResolution with gate results and bounded governance effects.

    Fail-safe:
        If insufficient signals are available, returns a safe resolution
        with available=False, no penalty, no confirmation pressure.
    """
    # Need at minimum r_acc, s_acc, and guna_coherence to run the gate
    if r_acc is None or s_acc is None or guna_coherence is None:
        return InsightResolution(
            eligible=False,
            can_release=False,
            stab_score=0.0,
            risk_score=0.0,
            confidence_penalty=0.0,
            confirmation_pressure=False,
            reason_codes=(),
            available=False,
            source_detail="insufficient insight signals",
        )

    try:
        from agentic.sovereign_insight_gate_pure import run_insight_gate_pure

        result = run_insight_gate_pure(
            r_acc=r_acc,
            s_acc=s_acc,
            guna_coherence=guna_coherence,
            drift=drift if drift is not None else 0.0,
            authority=authority if authority is not None else 1.0,
            vritti=vritti if vritti is not None else 0,
            d_max=d_max,
        )

        penalty = _compute_insight_confidence_penalty(
            result.eligible, result.stab_score,
        )
        # Confirmation pressure: eligible but release blocked (risk too high)
        confirmation = result.eligible and not result.can_release

        return InsightResolution(
            eligible=result.eligible,
            can_release=result.can_release,
            stab_score=result.stab_score,
            risk_score=result.risk_score,
            confidence_penalty=penalty,
            confirmation_pressure=confirmation,
            reason_codes=result.reason_codes,
            available=True,
            source_detail=(
                f"insight gate (stab={result.stab_score:.3f}, "
                f"risk={result.risk_score:.3f}, "
                f"{'RELEASE' if result.can_release else 'ELIGIBLE' if result.eligible else 'BLOCKED'})"
            ),
        )
    except Exception:
        return InsightResolution(
            eligible=False,
            can_release=False,
            stab_score=0.0,
            risk_score=0.0,
            confidence_penalty=0.0,
            confirmation_pressure=False,
            reason_codes=(),
            available=False,
            source_detail="insight gate evaluation failed",
        )
