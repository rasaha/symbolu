"""Authority-basis integrity + the authorization-only surface.

ActionGate preserves actor/authority/resource/policy/decision references, never
widens authority, never fabricates human authority from an AI principal, and never
creates decision authority of its own. It exposes an ``authorize`` method and NO
dispatch/execute/observe/reconcile/compensate surface.
"""
from __future__ import annotations

from ugence_governance_provider_framework.api import (
    ActionGovernanceRequest, ProviderKind)

from ugence_actiongate_provider.configuration import build_actiongate_provider
from ugence_actiongate_provider.core import ActionGateEngine
from ugence_actiongate_provider.mapping import map_request


def test_request_mapping_preserves_authority_context_without_widening():
    req = ActionGovernanceRequest(
        action_type="ACT", actor="ai-agent-7", authority_context="delegated:analyst",
        target_resource="ledger:42", policy_refs=("p:1", "p:2"), decision_refs=("d:9",),
        idempotency_key="idem", correlation_id="corr")
    n = map_request(req)
    assert n.principal == "ai-agent-7"           # no actor substitution
    assert n.authority == "delegated:analyst"    # no authority widening
    assert n.resource == "ledger:42"             # no resource substitution
    assert n.policy_context == ("p:1", "p:2")    # no policy-reference loss
    assert n.decision_refs == ("d:9",)           # no decision-reference loss
    assert n.correlation_id == "corr" and n.idempotency_key == "idem"


def test_missing_authority_is_not_replaced_by_fabricated_authority():
    n = map_request(ActionGovernanceRequest(action_type="ACT"))
    assert n.authority == "" and n.principal == ""  # empty, not fabricated


def test_authority_basis_survives_result_mapping():
    p = build_actiongate_provider(ActionGateEngine()); p.initialize()
    r = p.authorize(ActionGovernanceRequest("OK"))
    # the engine's authority basis is preserved verbatim; the provider does not mint
    # its own decision authority.
    assert r.authority_basis == "actiongate-policy"


def test_ai_principal_not_reclassified_as_human_authority():
    # ActionGate carries the principal string as-is; it never re-labels an AI
    # principal as a human authority.
    n = map_request(ActionGovernanceRequest(action_type="ACT", actor="ai:model-x",
                                            authority_context="ai_delegated"))
    assert "human" not in n.authority.lower()
    assert n.principal == "ai:model-x"


def test_provider_is_action_governance_and_authorize_only():
    p = build_actiongate_provider(ActionGateEngine()); p.initialize()
    assert p.descriptor().kind is ProviderKind.ACTION_GOVERNANCE
    assert hasattr(p, "authorize")
    for forbidden in ("dispatch", "execute", "observe", "reconcile", "compensate"):
        assert not hasattr(p, forbidden), forbidden
