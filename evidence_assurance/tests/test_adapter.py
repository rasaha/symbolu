"""Phase 14 contract tests: the EvidenceAssurance -> AssertionGate adapter, and the thin gate.

The safety invariant under test: the thin AssertionGate never surfaces a claim as supported when the
gold delivery withholds it. Plus: risk escalation fires correctly, and the thin gate routes purely on
the delivery decision.
"""
from dataclasses import asdict

from evidence_assurance import dataset, adapter
from evidence_assurance.assurance import AssuranceResult
from evidence_assurance.taxonomy import EvidenceState as ES, DELIVERY_EFFECT

_CASES = [asdict(c) for c in dataset.all_cases()]


def test_no_delivery_level_escape():
    """No case is surfaced as supported when its gold delivery withholds it."""
    escapes = []
    for c in _CASES:
        gate = adapter.thin_assertion_gate(adapter.evidence_to_delivery(c))
        gold_supported = c["gold_delivery"] in ("ALLOW", "QUALIFY")
        if gate["surface_claim"] and not gold_supported:
            escapes.append(c["case_id"])
    assert not escapes, f"delivery-level escapes: {escapes[:5]} (+{max(0,len(escapes)-5)} more)"


def test_correlated_failure_never_surfaced():
    """Every trap case (correlated-failure / adversarial) is withheld end-to-end."""
    for c in _CASES:
        if c["partition"] in ("CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE"):
            gate = adapter.thin_assertion_gate(adapter.evidence_to_delivery(c))
            assert not gate["surface_claim"], f"{c['case_id']} surfaced a correlated failure"


def test_high_risk_escalates_soft_withholds():
    """A soft withhold (DEPENDENT) escalates under high/critical risk, not under low."""
    soft = AssuranceResult(state=ES.DEPENDENT.value,
                           delivery_effect=DELIVERY_EFFECT[ES.DEPENDENT], reason_codes=[])
    assert adapter.to_delivery(soft, "critical").delivery == "ESCALATE"
    assert adapter.to_delivery(soft, "high").delivery == "ESCALATE"
    assert adapter.to_delivery(soft, "low").delivery == "QUALIFY"
    assert adapter.to_delivery(soft, "critical").escalated_by_risk is True
    assert adapter.to_delivery(soft, "low").escalated_by_risk is False


def test_hard_states_not_escalated_by_risk():
    """A hard reject stays REJECT regardless of risk (nothing to soften/escalate)."""
    hard = AssuranceResult(state=ES.MISALIGNED.value,
                           delivery_effect=DELIVERY_EFFECT[ES.MISALIGNED], reason_codes=[])
    assert adapter.to_delivery(hard, "critical").delivery == "REJECT"
    assert adapter.to_delivery(hard, "critical").escalated_by_risk is False


def test_thin_gate_routes_only_on_delivery():
    """The thin gate's output is a pure function of the delivery decision — verified structurally by
    routing each delivery value and checking the surface/withhold/escalate flags are consistent."""
    for delivery in adapter.DELIVERY:
        d = adapter.DeliveryDecision(delivery=delivery, state="(any)",
                                     escalated_by_risk=False, reason_codes=[])
        gate = adapter.thin_assertion_gate(d)
        assert gate["surface_claim"] == (delivery in ("ALLOW", "QUALIFY"))
        assert gate["route_to_human"] == (delivery == "ESCALATE")
        assert gate["withhold"] == (delivery in ("REJECT", "INDETERMINATE"))


def test_verified_is_delivered():
    """Sanity: a clean VERIFIED disposition surfaces the claim."""
    v = AssuranceResult(state=ES.VERIFIED.value,
                        delivery_effect=DELIVERY_EFFECT[ES.VERIFIED], reason_codes=[])
    gate = adapter.thin_assertion_gate(adapter.to_delivery(v, "low"))
    assert gate["surface_claim"] is True and gate["delivery"] == "ALLOW"
