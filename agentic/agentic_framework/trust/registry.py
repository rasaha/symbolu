"""
registry.py — the Phase-1 product trust observables, built from PROVEN gateway logic.

This is the single place that maps the Agentic Framework's already-proven signals onto
the typed `Observation` model. It introduces no new ML and no CG research features — it
reuses the existing adapters verbatim:

  * raw next-token entropy   → raw_entropy_adapter.resolve_raw_entropy_signal   (VALIDATOR)
  * confidence-risk gap      → confidence_risk_gap.assess_confidence_risk_gap   (VALIDATOR)
  * tool validity            → caller-supplied registration flag                (HARD_VETO)
  * approval requirement     → MCPToolDefinition.requires_confirmation          (VALIDATOR)
  * budget / cost gate       → caller-supplied budget-exceeded flag             (HARD_VETO)
  * verbalized safety        → MCPToolCall.verbalized_safety_confidence         (TRUST_SIGNAL)
  * action / tool risk       → recorded as context (modulates the gap, not a blocker)

CG-state read-outs (vritti / guna / kosha / JEPA-from-state / Bhava / CSR) are declared
RESEARCH and are NOT produced here — they never enter the product decision. See
`CG_RESEARCH_OBSERVABLES` for the registry of what stays off by default and why.
"""

from __future__ import annotations

from typing import List, Optional

from agentic.agentic_framework.signal_adapters.confidence_risk_gap import (
    assess_confidence_risk_gap,
)
from agentic.agentic_framework.signal_adapters.raw_entropy_adapter import (
    resolve_raw_entropy_signal,
)
from agentic.agentic_framework.signal_config import DEFAULT_SIGNAL_CONFIG, SignalConfig
from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    Observation,
    ObservableType,
    TRUST_CLAIM_SAFE,
    TRUST_DOUBT,
    Verdict,
)

# Catalog of the Phase-1 PROVEN product observables (documentation + introspection).
PRODUCT_OBSERVABLES = {
    "tool_validity": (ObservableType.HARD_VETO, EvidenceStatus.PROVEN),
    "budget_gate": (ObservableType.HARD_VETO, EvidenceStatus.PROVEN),
    "raw_entropy": (ObservableType.VALIDATOR, EvidenceStatus.PROVEN),
    "confidence_risk_gap": (ObservableType.VALIDATOR, EvidenceStatus.PROVEN),
    "approval_required": (ObservableType.VALIDATOR, EvidenceStatus.PROVEN),
    "verbalized_safety": (ObservableType.TRUST_SIGNAL, EvidenceStatus.PROVEN),
    "action_risk": (ObservableType.ADVISORY, EvidenceStatus.PROVEN),
}

# CG-state signals: RESEARCH ONLY. Never produced by the product builder; listed so the
# off-by-default contract is explicit and auditable. To even experiment with these in a
# decision you must (a) explicitly enable CG-state signals AND (b) promote them through
# the evidence gate — neither of which Phase 1 does.
CG_RESEARCH_OBSERVABLES = {
    "cg_state_entropy": "guna-imbalance of the 32-D state; anti-predictive in falsification",
    "vritti_risk": "heuristic sum over an unsupervised softmax slice; AUROC ~0.500",
    "guna": "imbalance read-out, not predictive uncertainty",
    "kosha": "inactive in the single-state path",
    "jepa_regime": "hand-coded rulebook; re-encodes tool risk",
    "bhava_write": "state→logit modulation; behavior, not trust",
    "csr": "phoneme-alignment write intervention; behavior, not trust",
}


def _clip01(x: float) -> float:
    return float(min(1.0, max(0.0, x)))


def observe_tool_call(
    *,
    tool_risk_level: str,
    raw_entropy: Optional[float] = None,
    raw_logprobs: Optional[object] = None,
    verbalized_safety_confidence: Optional[float] = None,
    tool_registered: bool = True,
    requires_confirmation: bool = False,
    budget_exceeded: bool = False,
    config: SignalConfig = DEFAULT_SIGNAL_CONFIG,
) -> List[Observation]:
    """Build the Phase-1 PROVEN observation set for one tool call.

    Inputs are plain values (provider-agnostic). Designed to be fed from an
    ``MCPToolCall`` + ``MCPToolDefinition`` at the gateway boundary, but kept decoupled
    so it is unit-testable without constructing a gateway.
    """
    obs: List[Observation] = []

    # --- HARD VETO: tool validity (calling an unregistered/hallucinated tool) ---
    obs.append(Observation(
        name="tool_validity",
        otype=ObservableType.HARD_VETO,
        evidence=EvidenceStatus.PROVEN,
        verdict=Verdict.SAFE if tool_registered else Verdict.UNSAFE,
        severity=0.0 if tool_registered else 1.0,
        reason="" if tool_registered else "tool is not registered/available (hallucinated tool)",
    ))

    # --- HARD VETO: budget / cost gate ---
    obs.append(Observation(
        name="budget_gate",
        otype=ObservableType.HARD_VETO,
        evidence=EvidenceStatus.PROVEN,
        verdict=Verdict.UNSAFE if budget_exceeded else Verdict.SAFE,
        severity=1.0 if budget_exceeded else 0.0,
        reason="budget/cost limit exceeded" if budget_exceeded else "",
    ))

    # --- VALIDATOR: raw next-token entropy (first-class uncertainty) ---
    re = resolve_raw_entropy_signal(
        raw_entropy=raw_entropy, logprobs=raw_logprobs,
        enabled=config.enable_raw_entropy_signal,
    )
    if re.available and re.raw_entropy is not None:
        high = re.raw_entropy >= config.raw_entropy_high
        obs.append(Observation(
            name="raw_entropy",
            otype=ObservableType.VALIDATOR,
            evidence=EvidenceStatus.PROVEN,
            verdict=Verdict.UNSURE if high else Verdict.SAFE,
            severity=_clip01(re.raw_entropy),
            reason=(f"raw entropy {re.raw_entropy:.2f} ≥ {config.raw_entropy_high:.2f} "
                    f"(model internally uncertain)") if high else
                   f"raw entropy {re.raw_entropy:.2f} below uncertainty threshold",
            detail={"raw_entropy": re.raw_entropy, "source": re.source},
        ))

    # --- VALIDATOR: confidence-risk gap (confident-but-uncertain) ---
    gap = assess_confidence_risk_gap(
        verbalized_safety_confidence=verbalized_safety_confidence,
        raw_entropy_resolution=re,
        tool_risk_level=tool_risk_level,
        config=config,
    )
    if gap.available:
        if gap.escalate:
            verdict = Verdict.UNSAFE if gap.level == "halt" else Verdict.UNSURE
        else:
            verdict = Verdict.SAFE
        obs.append(Observation(
            name="confidence_risk_gap",
            otype=ObservableType.VALIDATOR,
            evidence=EvidenceStatus.PROVEN,
            verdict=verdict,
            severity=_clip01(gap.gap),
            reason=gap.reason,
            detail={"level": gap.level, "gap": gap.gap},
        ))

    # --- VALIDATOR: approval requirement (org policy) ---
    if requires_confirmation:
        obs.append(Observation(
            name="approval_required",
            otype=ObservableType.VALIDATOR,
            evidence=EvidenceStatus.PROVEN,
            verdict=Verdict.UNSURE,   # forces at least CONFIRM, never blocks by itself
            severity=0.5,
            reason="tool requires human confirmation by policy",
        ))

    # --- TRUST_SIGNAL: verbalized safety (asymmetric; recorded) ---
    if verbalized_safety_confidence is not None:
        vs = _clip01(float(verbalized_safety_confidence))
        admits_doubt = vs < config.verbalized_safety_high
        obs.append(Observation(
            name="verbalized_safety",
            otype=ObservableType.TRUST_SIGNAL,
            evidence=EvidenceStatus.PROVEN,
            # A confident claim CANNOT raise trust → SAFE verdict is inert by the
            # asymmetry rule; admitted doubt → UNSURE → may escalate to CONFIRM.
            verdict=Verdict.UNSURE if admits_doubt else Verdict.SAFE,
            severity=_clip01(1.0 - vs),
            reason=(f"model admits doubt (verbalized safety {vs:.2f} < "
                    f"{config.verbalized_safety_high:.2f})") if admits_doubt else
                   f"model claims safe ({vs:.2f}) — cannot raise trust (asymmetry)",
            direction=TRUST_DOUBT if admits_doubt else TRUST_CLAIM_SAFE,
        ))

    # --- ADVISORY: action / tool risk level (context; modulates the gap, not a blocker) ---
    obs.append(Observation(
        name="action_risk",
        otype=ObservableType.ADVISORY,
        evidence=EvidenceStatus.PROVEN,
        verdict=Verdict.SAFE,   # risk level alone never escalates; it modulates the gap
        severity=0.0,
        reason=f"tool risk level = {tool_risk_level}",
        detail={"tool_risk_level": tool_risk_level},
    ))

    return obs
