"""AssertionGate adapter (read-only). Calls the FROZEN govern() with a constructed SignalBundle."""
from __future__ import annotations

from typing import Any, Dict

from assertion_gate_robustness.gate import govern, GATE_VERSION
from assertion_gate_robustness.signals import SignalBundle, Grounding, Entailment, EvidenceMeta
from .base import AdapterResult

_STAGE = "assertion_gate"


def run(signals: Dict[str, Any], risk_class: str) -> AdapterResult:
    support = float(signals.get("support", 0.5))
    entail = signals.get("entail", "neutral")
    adequacy = float(signals.get("adequacy", 0.8))
    conflict = signals.get("conflict", "none")
    bundle = SignalBundle(
        grounding=Grounding(support=support, confidence=1.0),
        entailment=Entailment(label=entail, confidence=0.9),
        evidence=EvidenceMeta(adequacy=adequacy, conflict=conflict,
                              provenance_present=signals.get("provenance_present", True)),
        risk_class=risk_class)
    claim_strength = float(signals.get("claim_strength", support + 0.1))
    gd = govern(bundle, claim_strength=claim_strength)
    return AdapterResult(
        stage=_STAGE, component_version=GATE_VERSION, local_disposition=gd.disposition,
        reason_codes=gd.reason_codes,
        source_repr={"signals": signals},
        transformed_repr={"disposition": gd.disposition, "uncertainty": gd.uncertainty,
                          "effective_support": gd.effective_support},
        extra={"qualification": gd.qualification})
