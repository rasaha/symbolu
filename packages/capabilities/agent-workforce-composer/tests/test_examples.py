"""Synthetic-example tests (§24 — Procurement / Support / Security; I2, I10)."""
from __future__ import annotations

from ugence_agent_workforce_composer.contracts import NO_ELIGIBLE_AGENT, NodeDisposition
from ugence_agent_workforce_composer import fixtures


def _dispo(adapt):
    return {nd.node_id: nd.disposition for nd in adapt.node_dispositions}


def test_procurement_dispositions_and_authority_preservation():
    adapt, res = fixtures.run_demo("procurement")
    d = _dispo(adapt)
    assert d["proc_request_validation"] is NodeDisposition.DETERMINISTIC_SERVICE_PREFERRED
    assert d["proc_supplier_evidence"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["proc_supplier_risk"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["proc_recommendation"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["proc_binding_approval"] is NodeDisposition.HUMAN_AUTHORITY_REQUIRED
    assert d["proc_purchase_auth"] is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP
    assert d["proc_commit_clearance"] is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP
    assert adapt.accounting_holds()
    # supplier-risk role should have at least one eligible agent (procurement specialist)
    risk = next(r for r in res.reports if r.role_id == "role::proc_supplier_risk")
    assert "agent_procurement_specialist@2.1.0" in risk.eligible_agent_ids


def test_support_dispositions():
    adapt, res = fixtures.run_demo("support")
    d = _dispo(adapt)
    assert d["sup_classification"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["sup_retrieval"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["sup_draft"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["sup_escalation_decision"] is NodeDisposition.HUMAN_AUTHORITY_REQUIRED
    assert d["sup_human_approval"] is NodeDisposition.HUMAN_AUTHORITY_REQUIRED
    assert adapt.accounting_holds()


def test_security_dispositions_and_no_eligible_agent():
    adapt, res = fixtures.run_demo("security")
    d = _dispo(adapt)
    assert d["sec_evidence_collection"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["sec_threat_analysis"] is NodeDisposition.AI_AGENT_ELIGIBLE
    assert d["sec_sequence_risk"] is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP
    assert d["sec_human_escalation"] is NodeDisposition.HUMAN_AUTHORITY_REQUIRED
    assert d["sec_action_boundary"] is NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP
    assert adapt.accounting_holds()
    # threat analysis: only the high-security cyber analyst qualifies
    threat = next(r for r in res.reports if r.role_id == "role::sec_threat_analysis")
    assert threat.eligible_agent_ids == ("agent_cyber_analyst@1.0.0",)
    # evidence collection: no agent emits the incident-evidence contract -> typed empty set
    ec = next(r for r in res.reports if r.role_id == "role::sec_evidence_collection")
    assert ec.outcome == NO_ELIGIBLE_AGENT


def test_authority_preservation_across_all_examples():
    # I10: no governance-owned / human node is ever emitted as an agent role.
    for name in ("procurement", "support", "security"):
        adapt, _ = fixtures.run_demo(name)
        for na in adapt.non_agent_dispositions:
            assert na.disposition is not NodeDisposition.AI_AGENT_ELIGIBLE
        for nd in adapt.node_dispositions:
            if nd.disposition in (NodeDisposition.HUMAN_AUTHORITY_REQUIRED,
                                  NodeDisposition.EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP):
                assert not nd.is_agent_role
