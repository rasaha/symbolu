"""AssertionGate adapter (Phase 14). Maps an EvidenceAssurance disposition to an AssertionGate
DELIVERY decision. The boundary is deliberate: EvidenceAssurance decides the *evidence state*;
AssertionGate decides *what is delivered*. This adapter is the only coupling between them, and it
applies the one piece of context EvidenceAssurance does not own — the decision's risk tier.

`thin_assertion_gate` is a minimal reference consumer used only to prove the contract: a downstream
gate that trusts the disposition + delivery effect needs no evidence logic of its own. It does NOT
modify or depend on the frozen AssertionGate robustness study.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .assurance import assess, AssuranceResult
from .taxonomy import EvidenceState as ES

# delivery decisions the gate can take (AssertionGate vocabulary)
DELIVERY = ("ALLOW", "QUALIFY", "REJECT", "ESCALATE", "INDETERMINATE")

# soft withholds that a high/critical-risk decision escalates to human review
_SOFT_RISK_ESCALATE = {ES.INSUFFICIENT.value, ES.DEPENDENT.value, ES.STALE.value}


@dataclass
class DeliveryDecision:
    delivery: str                # one of DELIVERY
    state: str                   # the EvidenceState it came from
    escalated_by_risk: bool
    reason_codes: list


def to_delivery(result: AssuranceResult, risk_class: str) -> DeliveryDecision:
    eff = result.delivery_effect
    escalated = False
    if risk_class in ("high", "critical") and eff in ("INDETERMINATE", "QUALIFY") \
            and result.state in _SOFT_RISK_ESCALATE:
        eff = "ESCALATE"
        escalated = True
    return DeliveryDecision(delivery=eff, state=result.state, escalated_by_risk=escalated,
                            reason_codes=list(result.reason_codes))


def evidence_to_delivery(case: Dict[str, Any]) -> DeliveryDecision:
    """Full path: case -> EvidenceAssurance disposition -> AssertionGate delivery."""
    return to_delivery(assess(case), case.get("risk_class", "low"))


def thin_assertion_gate(decision: DeliveryDecision) -> Dict[str, Any]:
    """Minimal reference AssertionGate: it only routes on the delivery decision — no evidence logic,
    no re-derivation. This is the whole point of the contract: the gate stays thin because the
    evidence state was already established upstream."""
    deliver_as_supported = decision.delivery in ("ALLOW", "QUALIFY")
    return {
        "delivery": decision.delivery,
        "surface_claim": deliver_as_supported,
        "attach_caveat": decision.delivery == "QUALIFY",
        "route_to_human": decision.delivery == "ESCALATE",
        "withhold": decision.delivery in ("REJECT", "INDETERMINATE"),
        "evidence_state": decision.state,
    }
