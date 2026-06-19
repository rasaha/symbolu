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


@dataclass(frozen=True)
class AuthorityPolicy:
    """Evidence status (decision authority) assigned to each heuristic authority.

    PROVEN → may BLOCK; PROVISIONAL → confirm-only (never blocks). This makes the
    blocking-vs-advisory decision for JEPA / domain / shadow EXPLICIT and reviewable,
    rather than hardcoded. Default = PARITY (everything PROVEN, reproduces legacy).
    """
    jepa: EvidenceStatus = EvidenceStatus.PROVEN
    domain: EvidenceStatus = EvidenceStatus.PROVEN
    shadow: EvidenceStatus = EvidenceStatus.PROVEN


# PARITY: reproduce legacy exactly (all heuristics blocking).
PARITY_POLICY = AuthorityPolicy()
# REVIEWED (Phase 1.5A): JEPA demoted to confirm-only (heuristic, no proven evidence);
# domain kept blocking (explicit configured rules); shadow kept blocking (fires named
# deterministic registry rules, not a risk-score threshold).
REVIEWED_POLICY = AuthorityPolicy(jepa=EvidenceStatus.PROVISIONAL)


@dataclass
class ParityComparison:
    legacy: TrustDecision
    trust: TrustDecision
    mismatch: bool
    classification: str        # match | intended | unintended | unsafe_relaxation
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
    """Map a shadow containment mode to a verdict, faithfully mirroring the legacy
    `shadow_containment_to_governance`: ALLOW→SAFE; BLOCKED/QUARANTINED→UNSAFE (block);
    **every intermediate containment mode** (observe_only / read_only / draft_only /
    sandbox_only / memory_write_denied / require_confirmation) → DEFER → UNSURE (confirm).
    Treating the intermediate modes as SAFE would silently relax a legacy CONFIRM to ALLOW.
    """
    if shadow_assessment is None or not hasattr(shadow_assessment, "containment_mode"):
        return None
    cm = getattr(shadow_assessment.containment_mode, "value", "allow")
    if cm in ("blocked", "quarantined"):
        return Verdict.UNSAFE
    if cm == "allow":
        return Verdict.SAFE
    return Verdict.UNSURE


# Shadow `reason_codes` prefixes that establish a DETERMINISTIC / policy-backed basis for
# the containment (named declarative rules, fail-closed defaults, registry max-risk /
# blocked-capability enforcement). If any of these is present, the shadow block stands on
# policy grounds regardless of any derived escalation.
_SHADOW_DETERMINISTIC_PREFIXES = (
    "RULE:", "FAIL_CLOSED:", "EXCEEDS_MAX_RISK:", "BLOCKED_CAPABILITY:",
)
# Reason codes for the two DERIVED (heuristic-signal) escalations inside shadow.
_SHADOW_JEPA_DERIVED_CODE = "JEPA_REGIME_ESCALATION"
_SHADOW_SEMANTIC_DERIVED_CODE = "SEMANTIC_MISMATCH_ESCALATION"


def _shadow_driver_name(shadow_assessment: Any, verdict: Verdict) -> str:
    """Attribute an escalating shadow observation to its true source — REPORTING ONLY.

    A shadow CONFIRM/BLOCK is reattributed to ``shadow_jepa_derived`` /
    ``shadow_semantic_derived`` ONLY when the escalation is *solely* due to the JEPA-regime
    (Step 6) or semantic-mismatch (Step 5) escalation — i.e. no deterministic/policy-backed
    rule independently establishes the containment. When any deterministic rule co-fires,
    the block stands on policy grounds and keeps the generic ``shadow`` name (conservative:
    never over-claims a demotion opportunity). A non-escalating (SAFE) shadow observation
    always stays ``shadow``.

    This changes the audit DRIVER NAME only; it never affects the observation's verdict,
    evidence/authority, severity, or the resulting ALLOW/CONFIRM/BLOCK decision. JEPA is the
    more-severe escalation and so wins attribution when both derived escalations are present.
    """
    if verdict == Verdict.SAFE:
        return "shadow"
    codes = tuple(getattr(shadow_assessment, "reason_codes", ()) or ())
    if any(c.startswith(_SHADOW_DETERMINISTIC_PREFIXES) for c in codes):
        return "shadow"
    if any(c.startswith(_SHADOW_JEPA_DERIVED_CODE) for c in codes):
        return "shadow_jepa_derived"
    if any(c.startswith(_SHADOW_SEMANTIC_DERIVED_CODE) for c in codes):
        return "shadow_semantic_derived"
    return "shadow"


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
    forbidden_capabilities: Any = (),
    policy: "AuthorityPolicy" = PARITY_POLICY,
) -> List[Observation]:
    """Map the legacy decision authorities to trust observations.

    `policy` sets the decision authority (evidence status) of the heuristic authorities
    (JEPA / domain / shadow). PARITY_POLICY = all PROVEN (reproduces legacy); a demoted
    authority becomes PROVISIONAL (confirm-only, never blocks).
    """
    obs: List[Observation] = []
    read_only = getattr(getattr(tool_def, "risk_level", None), "value", "") == "read_only"

    # Hard pre-gate: a forbidden capability is a deterministic kill-switch that the gateway
    # enforces ABOVE the normal flow (it blocks before confidence/JEPA/domain/shadow). Map
    # it as a PROVEN HARD_VETO so the trust core reproduces the legacy BLOCK terminally —
    # no confidence, entropy, or gap can override it (BLOCK wins by weakest-link). Always
    # PROVEN (a correctness gate, never a heuristic) — unaffected by the authority policy.
    forbidden_hit = sorted(
        set(getattr(tool_def, "capabilities", None) or [])
        & set(forbidden_capabilities or []))
    if forbidden_hit:
        obs.append(Observation(
            name="forbidden_capability", otype=ObservableType.HARD_VETO,
            evidence=EvidenceStatus.PROVEN, verdict=Verdict.UNSAFE, severity=1.0,
            reason=f"forbidden capability: {', '.join(forbidden_hit)}",
            detail={"capabilities": forbidden_hit}))

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

    # JEPA heuristic regime — authority set by policy (PROVEN blocks; PROVISIONAL confirms).
    obs.append(Observation(
        name="jepa", otype=ObservableType.VALIDATOR, evidence=policy.jepa,
        verdict=_jepa_verdict(jepa_assessment, read_only),
        severity=0.6, reason=f"jepa regime={getattr(getattr(jepa_assessment,'regime',None),'value','normal')}",
    ))

    # Domain Semantic Policy — explicit configured rules (policy authority).
    dv = _domain_verdict(domain_result)
    if dv is not None:
        obs.append(Observation(
            name="domain", otype=ObservableType.VALIDATOR, evidence=policy.domain,
            verdict=dv, severity=0.7, reason="domain policy mode",
        ))

    # Shadow AI control — named deterministic registry rules (policy authority).
    # The driver NAME is attributed to the true source (deterministic `shadow` vs a
    # JEPA-/semantic-derived escalation) for honest demotion analysis; verdict/authority
    # and the resulting decision are unchanged.
    sv = _shadow_verdict(shadow_assessment)
    if sv is not None:
        obs.append(Observation(
            name=_shadow_driver_name(shadow_assessment, sv),
            otype=ObservableType.VALIDATOR, evidence=policy.shadow,
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
    forbidden_capabilities: Any = (),
    policy: "AuthorityPolicy" = PARITY_POLICY,
) -> ParityComparison:
    """Compute the parallel trust decision under `policy` and compare it to legacy.

    Classification:
      match            trust == legacy
      intended         a reviewed demotion explains the difference (under PARITY the
                       decision WOULD match legacy; the active policy relaxes BLOCK→CONFIRM)
      unsafe_relaxation a demotion turned BLOCK/CONFIRM into ALLOW (silent allow) — STOP
      unintended       a mapping gap independent of the demotion (PARITY also mismatches)
    """
    kw = dict(tool_def=tool_def, result=result, gate_decision=gate_decision,
              jepa_assessment=jepa_assessment, domain_result=domain_result,
              shadow_assessment=shadow_assessment, confidence_risk_gap=confidence_risk_gap,
              forbidden_capabilities=forbidden_capabilities)
    outcome = decide(build_parity_observations(policy=policy, **kw))
    legacy = legacy_decision_to_trust(result)
    mismatch = outcome.decision != legacy

    if not mismatch:
        classification = "match"
    elif outcome.decision == TrustDecision.ALLOW and legacy in (
            TrustDecision.BLOCK, TrustDecision.CONFIRM):
        classification = "unsafe_relaxation"   # demotion must never produce a silent allow
    else:
        parity_decision = decide(build_parity_observations(policy=PARITY_POLICY, **kw)).decision
        classification = "intended" if parity_decision == legacy else "unintended"

    return ParityComparison(legacy=legacy, trust=outcome.decision, mismatch=mismatch,
                            classification=classification, outcome=outcome)
