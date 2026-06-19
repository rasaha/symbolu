"""
decision.py — the trust decision model (Phase 1, product).

Pure function: a list of `Observation`s → a `TrustOutcome` (ALLOW / CONFIRM / BLOCK)
plus the drivers and a human-readable audit reason. No I/O, no model, no CG.

The locked rules (see AGENTIC_FRAMEWORK_TRUST_OBSERVABLE_ARCHITECTURE.md §3):

  1. Hard gates first        — a PROVEN HARD_VETO with verdict UNSAFE → BLOCK (terminal).
  2. Staged authority        — only PROVEN observables may block; PROVISIONAL/ADVISORY
                               may escalate to CONFIRM but NEVER block; RESEARCH never
                               affects the decision (recorded only).
  3. Validators cap trust    — a PROVEN VALIDATOR: UNSAFE → BLOCK, UNSURE → CONFIRM.
  4. Asymmetry               — a TRUST_SIGNAL can only LOWER trust (admitted doubt →
                               CONFIRM); a confident "safe" claim can NEVER raise it.
  5. Weakest link            — the final decision is the MOST severe proposed decision
                               (BLOCK > CONFIRM > ALLOW); nothing averages it away.

This is deliberately a decision *tree*, not a threshold on an additive sum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    TRUST_CLAIM_SAFE,
    TRUST_DOUBT,
    TrustDecision,
    Verdict,
)

_SEVERITY_ORDER = {TrustDecision.ALLOW: 0, TrustDecision.CONFIRM: 1, TrustDecision.BLOCK: 2}


@dataclass
class TrustOutcome:
    decision: TrustDecision
    # Observations responsible for the outcome: for CONFIRM/BLOCK, the ones that RAISED it;
    # for ALLOW, the proven gates that were evaluated and CLEARED (the basis for allowing).
    drivers: List[Observation] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)  # everything considered
    reason: str = ""

    def to_audit(self) -> Dict[str, object]:
        return {
            "trust_decision": self.decision.value,
            "trust_reason": self.reason,
            "trust_drivers": [o.name for o in self.drivers],
            "trust_observations": [o.to_audit() for o in self.observations],
        }


def _proposed(obs: Observation) -> TrustDecision:
    """The decision a single observation argues for, under the staged-authority rules."""
    # RESEARCH never influences the decision — recorded only.
    if obs.evidence == EvidenceStatus.RESEARCH:
        return TrustDecision.ALLOW

    risky = obs.verdict in (Verdict.UNSURE, Verdict.UNSAFE)

    if obs.otype == ObservableType.HARD_VETO:
        # Hard vetoes are deterministic correctness checks; only PROVEN ones veto.
        if obs.evidence == EvidenceStatus.PROVEN and obs.verdict == Verdict.UNSAFE:
            return TrustDecision.BLOCK
        # A provisional/advisory "veto" can only advise.
        return TrustDecision.CONFIRM if risky else TrustDecision.ALLOW

    if obs.otype == ObservableType.TRUST_SIGNAL:
        # Asymmetric: admitted doubt may lower trust; a confident claim may not raise it.
        if obs.direction == TRUST_DOUBT and risky:
            return TrustDecision.CONFIRM
        return TrustDecision.ALLOW

    if obs.otype == ObservableType.VALIDATOR:
        if obs.evidence == EvidenceStatus.PROVEN:
            if obs.verdict == Verdict.UNSAFE:
                return TrustDecision.BLOCK
            if obs.verdict == Verdict.UNSURE:
                return TrustDecision.CONFIRM
            return TrustDecision.ALLOW
        # PROVISIONAL validator: advise/log only — never blocks.
        return TrustDecision.CONFIRM if risky else TrustDecision.ALLOW

    # ADVISORY: may escalate to CONFIRM, never blocks.
    return TrustDecision.CONFIRM if risky else TrustDecision.ALLOW


def _cleared_gates(observations: List[Observation]) -> List[Observation]:
    """Proven gates (HARD_VETO / VALIDATOR) that were evaluated and returned SAFE — the
    evidentiary basis for an ALLOW (they COULD have blocked/escalated but did not)."""
    return [o for o in observations
            if o.evidence == EvidenceStatus.PROVEN
            and o.otype in (ObservableType.HARD_VETO, ObservableType.VALIDATOR)
            and o.verdict == Verdict.SAFE]


def _discounted(observations: List[Observation]) -> List[Observation]:
    """Signals recorded but given no authority over the decision: RESEARCH (any), and
    confident TRUST_SIGNAL claims (which can never RAISE trust, by the asymmetry rule)."""
    out = []
    for o in observations:
        if o.evidence == EvidenceStatus.RESEARCH:
            out.append(o)
        elif o.otype == ObservableType.TRUST_SIGNAL and o.direction == TRUST_CLAIM_SAFE:
            out.append(o)
    return out


def decide(observations: List[Observation]) -> TrustOutcome:
    """Combine observations into ALLOW / CONFIRM / BLOCK with an explainable driver trace.

    Every decision is explained: BLOCK/CONFIRM by the observations that RAISED it; ALLOW by
    the proven gates it CLEARED. Both note any non-authoritative signals that were discounted
    (confident claims, RESEARCH) — so the asymmetry and evidence-gating are auditable.
    """
    decision = TrustDecision.ALLOW
    raisers: List[Observation] = []

    for obs in observations:
        proposed = _proposed(obs)
        if _SEVERITY_ORDER[proposed] > _SEVERITY_ORDER[decision]:
            decision = proposed
            raisers = [obs]
        elif proposed == decision and proposed != TrustDecision.ALLOW:
            raisers.append(obs)

    if decision == TrustDecision.ALLOW:
        drivers = sorted(_cleared_gates(observations), key=lambda o: o.name)
    else:
        # Order raisers by severity (highest first) for a stable, readable trail.
        drivers = sorted(raisers, key=lambda o: -float(o.severity))

    reason = _render_reason(decision, drivers, observations)
    return TrustOutcome(decision=decision, drivers=drivers,
                        observations=list(observations), reason=reason)


def _render_reason(decision: TrustDecision, drivers: List[Observation],
                   observations: List[Observation]) -> str:
    if decision == TrustDecision.ALLOW:
        if drivers:
            base = (f"ALLOW: cleared {len(drivers)} proven check(s) — "
                    + ", ".join(o.name for o in drivers))
        else:
            base = "ALLOW: no proven gate evaluated"
    else:
        parts = [(f"{o.name}({o.otype.value},{o.evidence.value},{o.verdict.value}): {o.reason}"
                  if o.reason else
                  f"{o.name}({o.otype.value},{o.evidence.value},{o.verdict.value})")
                 for o in drivers]
        base = f"{decision.value.upper()} driven by " + " | ".join(parts)

    discounted = _discounted(observations)
    if discounted:
        base += ("; discounted " + str(len(discounted)) + " non-authoritative signal(s): "
                 + ", ".join(o.name for o in discounted))
    return base
