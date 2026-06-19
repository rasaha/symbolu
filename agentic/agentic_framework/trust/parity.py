"""
parity.py — Phase 1.5 shadow/parity bridge (migration only, no new observables).

Maps the SafeMCPGateway's already-computed legacy decision authorities onto the typed
trust `Observation` model so the trust core (`trust.decision.decide`) can produce a
PARALLEL decision and be compared to the legacy outcome. This is the differential
substrate for the legacy → shadow → trust_core migration.

Goal of the mapping: **parity** — reproduce the legacy decision faithfully, not improve
it. Each legacy authority becomes a PROVEN observation whose verdict is derived from the
value the gateway already computed for that authority:

    confidence_floor      min_confidence threshold (effective_confidence < min)
    jepa                  JEPA regime (+ read-only DEFER special case)
    domain                DomainActionMode (BLOCKED / >= CONFIRM_REQUIRED)
    shadow                ShadowContainmentMode (BLOCKED/QUARANTINED / REQUIRE_CONFIRMATION)
    execution_permission  base ConfidenceGate can_execute + approval/gap (human confirm)

Human confirmation is a POST-DECISION ACTION: the governance decision is CONFIRM; whether
the human then approves converts CONFIRM→ALLOWED at runtime. The legacy→trust mapping
accounts for this (ALLOWED + human_confirmed ⇒ the decision was CONFIRM).

No new ML, no CG research signals. CG-derived signals are already decision-gated upstream
in `_jepa_check`; this module never reintroduces them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, List, Optional, Tuple

from agentic.agentic_framework.trust.decision import TrustOutcome, decide
from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    TrustDecision,
    Verdict,
)


class TrustMode(str, Enum):
    """How SafeMCPGateway treats the trust decision core."""
    LEGACY = "legacy"          # trust core not computed; pure legacy behavior
    SHADOW = "shadow"          # trust core computed in parallel + audited; legacy acts
    TRUST_CORE = "trust_core"  # trust core computed + audited; FLIP to authoritative is
                               # parity-gated and not yet enabled (behaves as SHADOW)


@dataclass
class ParityComparison:
    legacy: TrustDecision
    trust: TrustDecision
    mismatch: bool
    classification: str        # "match" | "intended" | "unintended" | "unresolved"
    outcome: TrustOutcome


def legacy_decision_to_trust(result: Any) -> TrustDecision:
    """Map a legacy GatewayDecision (+ human_confirmed) to a TrustDecision.

    ALLOWED/TIMEOUT/ERROR mean the gate permitted execution → ALLOW, UNLESS a human
    confirmation was required and granted, in which case the governance decision was
    CONFIRM (the post-decision action approved it).
    """
    d = getattr(result.decision, "value", str(result.decision)).lower()
    if d == "blocked":
        return TrustDecision.BLOCK
    if d == "escalate":
        return TrustDecision.CONFIRM
    # allowed / timeout / error
    if getattr(result, "human_confirmed", False):
        return TrustDecision.CONFIRM
    return TrustDecision.ALLOW


def _jepa_verdict(jepa_assessment: Any, read_only: bool) -> Verdict:
    regime = (getattr(getattr(jepa_assessment, "regime", None), "value", "normal")
              if jepa_assessment else "normal")
    if regime in ("dual_anomaly", "unknown"):
        return Verdict.UNSAFE                       # HALT → block
    if regime in ("process_drift", "semantic_shift"):
        return Verdict.UNSURE if read_only else Verdict.UNSAFE  # DEFER: escalate RO, block else
    return Verdict.SAFE


def _domain_verdict(domain_result: Any) -> Optional[Verdict]:
    if domain_result is None or not hasattr(domain_result, "mode"):
        return None
    from agentic.agentic_framework.domain_policy import DomainActionMode
    mode = domain_result.mode
    if mode == DomainActionMode.BLOCKED:
        return Verdict.UNSAFE
    if mode.severity >= DomainActionMode.CONFIRM_REQUIRED.severity:
        return Verdict.UNSURE
    return Verdict.SAFE


def _shadow_verdict(shadow_assessment: Any) -> Optional[Verdict]:
    if shadow_assessment is None or not hasattr(shadow_assessment, "containment_mode"):
        return None
    cm = getattr(shadow_assessment.containment_mode, "value", "allow")
    if cm in ("blocked", "quarantined"):
        return Verdict.UNSAFE
    if cm == "require_confirmation":
        return Verdict.UNSURE
    return Verdict.SAFE


def _gap_requires_human(confidence_risk_gap: Any) -> bool:
    g = confidence_risk_gap
    return bool(g is not None and getattr(g, "available", False)
                and getattr(g, "escalate", False)
                and getattr(g, "level", "none") in ("confirm", "halt"))


def build_parity_observations(
    *,
    tool_def: Any,
    result: Any,
    gate_decision: Any,
    jepa_assessment: Any = None,
    domain_result: Any = None,
    shadow_assessment: Any = None,
    confidence_risk_gap: Any = None,
) -> List[Observation]:
    """Reproduce the legacy decision authorities as PROVEN trust observations."""
    obs: List[Observation] = []
    read_only = getattr(getattr(tool_def, "risk_level", None), "value", "") == "read_only"

    # min_confidence floor (base ConfidenceGate threshold).
    eff_conf = float(getattr(result, "confidence", 1.0))
    min_conf = float(getattr(tool_def, "min_confidence", 0.0))
    obs.append(Observation(
        name="confidence_floor", otype=ObservableType.VALIDATOR,
        evidence=EvidenceStatus.PROVEN,
        verdict=Verdict.UNSAFE if eff_conf < min_conf else Verdict.SAFE,
        severity=max(0.0, min_conf - eff_conf),
        reason=(f"effective confidence {eff_conf:.2f} < min {min_conf:.2f}"
                if eff_conf < min_conf else f"confidence {eff_conf:.2f} ≥ min {min_conf:.2f}"),
    ))

    # JEPA heuristic regime.
    obs.append(Observation(
        name="jepa", otype=ObservableType.VALIDATOR, evidence=EvidenceStatus.PROVEN,
        verdict=_jepa_verdict(jepa_assessment, read_only),
        severity=0.6, reason=f"jepa regime={getattr(getattr(jepa_assessment,'regime',None),'value','normal')}",
    ))

    # Domain Semantic Policy.
    dv = _domain_verdict(domain_result)
    if dv is not None:
        obs.append(Observation(
            name="domain", otype=ObservableType.VALIDATOR, evidence=EvidenceStatus.PROVEN,
            verdict=dv, severity=0.7, reason="domain policy mode",
        ))

    # Shadow AI control.
    sv = _shadow_verdict(shadow_assessment)
    if sv is not None:
        obs.append(Observation(
            name="shadow", otype=ObservableType.VALIDATOR, evidence=EvidenceStatus.PROVEN,
            verdict=sv, severity=0.7, reason="shadow containment mode",
        ))

    # Approval requirement (org policy): requires_confirmation → at least CONFIRM. Modeled
    # as its own observation (mirrors the Phase-1 registry) rather than folded behind the
    # execution gate, so an approval-gated tool maps to CONFIRM even when the base gate
    # would otherwise auto-execute.
    requires_conf = bool(getattr(tool_def, "requires_confirmation", False))
    if requires_conf:
        obs.append(Observation(
            name="approval_required", otype=ObservableType.VALIDATOR,
            evidence=EvidenceStatus.PROVEN, verdict=Verdict.UNSURE, severity=0.5,
            reason="tool requires human confirmation by policy",
        ))

    # Execution permission (base gate can_execute + confidence-risk gap → human confirm).
    can_exec = bool(getattr(getattr(gate_decision, "execution", None), "can_execute", True))
    requires_human = bool(getattr(getattr(gate_decision, "escalation", None),
                                  "requires_human", False))
    gap_human = _gap_requires_human(confidence_risk_gap)
    if (not can_exec) or gap_human:
        verdict = (Verdict.UNSURE if (requires_human or requires_conf or gap_human)
                   else Verdict.UNSAFE)
    else:
        verdict = Verdict.SAFE
    obs.append(Observation(
        name="execution_permission", otype=ObservableType.VALIDATOR,
        evidence=EvidenceStatus.PROVEN, verdict=verdict, severity=0.5,
        reason=(f"can_execute={can_exec} requires_human={requires_human} "
                f"requires_confirmation={requires_conf} gap_human={gap_human}"),
    ))
    return obs


def shadow_compare(
    *,
    tool_def: Any,
    result: Any,
    gate_decision: Any,
    jepa_assessment: Any = None,
    domain_result: Any = None,
    shadow_assessment: Any = None,
    confidence_risk_gap: Any = None,
) -> ParityComparison:
    """Compute the parallel trust decision and compare it to the legacy outcome."""
    observations = build_parity_observations(
        tool_def=tool_def, result=result, gate_decision=gate_decision,
        jepa_assessment=jepa_assessment, domain_result=domain_result,
        shadow_assessment=shadow_assessment, confidence_risk_gap=confidence_risk_gap)
    outcome = decide(observations)
    legacy = legacy_decision_to_trust(result)
    mismatch = outcome.decision != legacy
    classification = "match" if not mismatch else classify_mismatch(legacy, outcome.decision)
    return ParityComparison(legacy=legacy, trust=outcome.decision, mismatch=mismatch,
                            classification=classification, outcome=outcome)


# Known, reviewed difference patterns. Phase 1.5 starts with none "intended" — every
# mismatch is "unintended" until a reviewer promotes a pattern here. Conservative by
# design: trust STRICTER than legacy is safer than trust LOOSER.
def classify_mismatch(legacy: TrustDecision, trust: TrustDecision) -> str:
    order = {TrustDecision.ALLOW: 0, TrustDecision.CONFIRM: 1, TrustDecision.BLOCK: 2}
    if order[trust] > order[legacy]:
        return "unintended"   # trust stricter than legacy — safe but a behavior change
    return "unintended"       # trust looser than legacy — must NOT flip until resolved
