"""
Readiness Checker Adapter — Governance-Safe Readiness Signal
=============================================================

Phase S3: Bridges the ``ReadinessChecker`` from
``agentic.safety.governance_patterns.readiness_checker`` into the
governance authorization path as a bounded, deterministic signal.

The readiness checker evaluates multi-criterion readiness:
    1. Plasticity above minimum (system open to change)
    2. Cooldown respected (sufficient time since last action)
    3. No pending escalations blocking action

Input sourcing:
    This adapter sources inputs from already-resolved governance signals:
    - plasticity ← PlasticityResolution.plasticity (S2)
    - stability  ← CoreCoherenceResolution.semantic_stability or .coherence_score
    - pending_escalations ← derived from current escalation level
    - last_action_time ← NOT currently tracked (criterion skipped, neutral)

    Cooldown tracking requires cross-request state that does not yet
    exist in GovernanceService. When last_action_time is None, the
    cooldown criterion is skipped (fail-open for this criterion only,
    since absence of cooldown data should not block actions).

Design:
    Follows the signal adapter pattern (see plasticity_adapter, coherence_state_adapter):
    - Frozen Resolution dataclass (immutable, serializable)
    - ``resolve_readiness_signal()`` pure function (deterministic, fail-closed)
    - Bounded confidence penalty (max 0.03)
    - ``available`` / ``source_detail`` / ``reason_codes`` provenance
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from agentic.safety.governance_patterns.readiness_checker import (
    ReadinessChecker,
    ReadinessConfig,
    ReadinessResult,
    ReadinessStatus,
)


# =========================================================================
# Constants
# =========================================================================

# Max confidence penalty for NOT_READY status.
_MAX_PENALTY_NOT_READY: float = 0.03

# Confidence penalty for DEGRADED status (lower than NOT_READY).
_PENALTY_DEGRADED: float = 0.02

# Default stability when no coherence signal is available.
_DEFAULT_STABILITY: float = 0.5

# Default readiness config for governance use.
# min_plasticity=0.30 matches ReadinessConfig default.
# cooldown disabled (0.0) since we don't have cross-request state yet.
# escalation blocking enabled.
_GOVERNANCE_READINESS_CONFIG = ReadinessConfig(
    min_plasticity=0.30,
    min_time_since_action_seconds=0.0,  # disabled — no cross-request state
    block_during_escalations=True,
)


# =========================================================================
# Governance-facing contract
# =========================================================================

@dataclass(frozen=True)
class ReadinessResolution:
    """Governance-safe view of the readiness evaluation.

    Field categories
    ----------------

    BEHAVIOR-AFFECTING:
        status              READY, NOT_READY, or DEGRADED.
        ready               Convenience bool (True if READY).
        plasticity          Plasticity gate value used in check.
        stability           Stability signal used in check.
        pending_escalations Number of pending escalations detected.

    ADAPTER METADATA:
        confidence_penalty  Bounded [0, MAX_PENALTY] penalty applied.
        escalation_bias     Whether escalation should be bumped.
        reason_codes        Machine-readable governance codes.
        readiness_reason    Human-readable reason from ReadinessChecker.
        available           Whether signal was successfully resolved.
        source_detail       Human-readable provenance description.
    """

    # --- Behavior-affecting ---
    status: Optional[str]
    ready: Optional[bool]
    plasticity: Optional[float]
    stability: Optional[float]
    pending_escalations: Optional[int]

    # --- Adapter metadata ---
    confidence_penalty: float
    escalation_bias: bool
    reason_codes: Tuple[str, ...]
    readiness_reason: str
    available: bool
    source_detail: str

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to audit-safe dictionary."""
        d: Dict[str, Any] = {}
        for field_name in (
            "status", "ready", "plasticity", "stability",
            "pending_escalations",
            "confidence_penalty", "escalation_bias",
            "readiness_reason", "available", "source_detail",
        ):
            val = getattr(self, field_name)
            if isinstance(val, float):
                val = round(val, 6)
            d[field_name] = val
        d["reason_codes"] = list(self.reason_codes)
        return d


# =========================================================================
# Empty/fallback resolution
# =========================================================================

_EMPTY_RESOLUTION = ReadinessResolution(
    status=None,
    ready=None,
    plasticity=None,
    stability=None,
    pending_escalations=None,
    confidence_penalty=0.0,
    escalation_bias=False,
    reason_codes=(),
    readiness_reason="",
    available=False,
    source_detail="readiness signal unavailable",
)


def _empty_resolution(
    detail: str = "readiness signal unavailable",
) -> ReadinessResolution:
    """Return a safe empty resolution (fail-closed: zero penalty)."""
    if detail == _EMPTY_RESOLUTION.source_detail:
        return _EMPTY_RESOLUTION
    return ReadinessResolution(
        status=None,
        ready=None,
        plasticity=None,
        stability=None,
        pending_escalations=None,
        confidence_penalty=0.0,
        escalation_bias=False,
        reason_codes=(),
        readiness_reason="",
        available=False,
        source_detail=detail,
    )


# =========================================================================
# Main resolution function
# =========================================================================

def resolve_readiness_signal(
    *,
    plasticity: Optional[float] = None,
    coherence_score: Optional[float] = None,
    semantic_stability: Optional[float] = None,
    escalation_level: Optional[str] = None,
    last_action_time: Optional[float] = None,
    current_time: Optional[float] = None,
) -> ReadinessResolution:
    """Resolve readiness signal for governance use.

    Args:
        plasticity: PlasticityGate output [~0.27, 1.0] from S2.
        coherence_score: Overall pipeline coherence [0, 1].
        semantic_stability: Semantic consistency [0, 1] (preferred over coherence).
        escalation_level: Current effective escalation level string
            ("none", "notify", "confirm", "halt"). "confirm"/"halt" are
            treated as pending escalations.
        last_action_time: Unix timestamp of last action (None if unknown).
        current_time: Override for current time (testing).

    Returns:
        ReadinessResolution with readiness status and bounded penalty.

    Fail-closed semantics:
        If plasticity is None (S2 unavailable), returns unavailable
        with zero penalty. Readiness fundamentally depends on plasticity.
        If only stability/escalation are missing, defaults are used.
    """
    if plasticity is None:
        return _empty_resolution("plasticity unavailable — cannot assess readiness")

    try:
        return _compute_readiness(
            plasticity=plasticity,
            coherence_score=coherence_score,
            semantic_stability=semantic_stability,
            escalation_level=escalation_level,
            last_action_time=last_action_time,
            current_time=current_time,
        )
    except Exception:
        return _empty_resolution("readiness computation failed")


def _compute_readiness(
    *,
    plasticity: float,
    coherence_score: Optional[float],
    semantic_stability: Optional[float],
    escalation_level: Optional[str],
    last_action_time: Optional[float],
    current_time: Optional[float],
) -> ReadinessResolution:
    """Compute readiness from available inputs."""
    # Determine stability
    if semantic_stability is not None:
        stability = max(0.0, min(1.0, float(semantic_stability)))
    elif coherence_score is not None:
        stability = max(0.0, min(1.0, float(coherence_score)))
    else:
        stability = _DEFAULT_STABILITY

    # Determine pending escalations from escalation level
    _ESCALATION_COUNTS = {
        "none": 0,
        "notify": 0,
        "confirm": 1,
        "halt": 1,
    }
    pending = _ESCALATION_COUNTS.get(
        (escalation_level or "none").lower(), 0
    )

    # Run readiness checker
    checker = ReadinessChecker(config=_GOVERNANCE_READINESS_CONFIG)
    result: ReadinessResult = checker.check(
        plasticity=max(0.0, min(1.0, float(plasticity))),
        stability=stability,
        last_action_time=last_action_time,
        pending_escalations=pending,
        current_time=current_time,
    )

    # Compute bounded penalty based on status
    if result.status == ReadinessStatus.NOT_READY:
        penalty = _MAX_PENALTY_NOT_READY
        escalation = True
    elif result.status == ReadinessStatus.DEGRADED:
        penalty = _PENALTY_DEGRADED
        escalation = False
    else:
        penalty = 0.0
        escalation = False

    # Build reason codes
    codes = []
    if result.status == ReadinessStatus.NOT_READY:
        codes.append("READINESS_NOT_READY")
    elif result.status == ReadinessStatus.DEGRADED:
        codes.append("READINESS_DEGRADED")
    if penalty > 0:
        codes.append("READINESS_PENALTY")
    if escalation:
        codes.append("READINESS_ESCALATION")

    # Build source detail
    detail_parts = [
        f"status={result.status.value}",
        f"plasticity={result.plasticity:.3f}",
        f"stability={stability:.3f}",
    ]
    if pending > 0:
        detail_parts.append(f"pending_escalations={pending}")
    source_detail = f"ReadinessChecker ({', '.join(detail_parts)})"

    return ReadinessResolution(
        status=result.status.value,
        ready=result.ready,
        plasticity=result.plasticity,
        stability=stability,
        pending_escalations=pending,
        confidence_penalty=penalty,
        escalation_bias=escalation,
        reason_codes=tuple(codes),
        readiness_reason=result.reason,
        available=True,
        source_detail=source_detail,
    )
