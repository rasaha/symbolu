"""EvidenceAssurance adapter (read-only). Uses the FROZEN EA delivery contract (to_delivery) on an
AssuranceResult built from the case's evidence state - the same delivery mapping the EA study froze."""
from __future__ import annotations

from typing import Any, Dict

from evidence_assurance.adapter import to_delivery
from evidence_assurance.assurance import AssuranceResult
from evidence_assurance.taxonomy import EvidenceState as ES, DELIVERY_EFFECT
from .base import AdapterResult

_STAGE = "evidence_assurance"
_VERSION = "ea_evidence_v1"


def run(evidence_steer: Dict[str, Any], risk_class: str) -> AdapterResult:
    state = evidence_steer.get("evidence_state")
    if state is None or state not in {e.value for e in ES}:
        return AdapterResult(_STAGE, _VERSION, "INDETERMINATE", ["GIP.MISSING_FIELD", "EA.UNKNOWN_STATE"],
                             source_repr={"evidence_steer": evidence_steer})
    res = AssuranceResult(state=state, delivery_effect=DELIVERY_EFFECT[ES(state)],
                          reason_codes=[f"EA.{state}"])
    decision = to_delivery(res, risk_class)
    return AdapterResult(
        stage=_STAGE, component_version=_VERSION, local_disposition=decision.delivery,
        reason_codes=[f"EA.{state}"] + (["EA.RISK_ESCALATED"] if decision.escalated_by_risk else []),
        source_repr={"evidence_state": state, "delivery_effect": res.delivery_effect},
        transformed_repr={"delivery": decision.delivery, "risk_class": risk_class},
        extra={"evidence_state": state})
