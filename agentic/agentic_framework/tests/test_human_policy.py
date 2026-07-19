"""
Tests for the Human-Curated Policy Layer (``human_policy``) and its
integration into ``GovernanceService``.

Authority model under test — "human sets the baseline, the LLM can only
tighten":
    - a human DENY is dispositive (nothing downstream can loosen it);
    - a human REQUIRE_APPROVAL forces at least DEFER + requires_human;
    - a human ALLOW is a permissiveness ceiling that the LLM/JEPA/domain
      overlays may still tighten to DEFER/DENY;
    - no matching rule (or no engine) leaves the LLM-derived baseline
      unchanged (backward compatible);
    - a configured-but-erroring book fails closed to DENY.
"""

import pytest

from agentic.agentic_framework.governance_models import (
    APIGovernanceDecision,
    AuthorizationRequest,
)
from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.human_policy import (
    HumanPolicyBook,
    HumanPolicyEngine,
    HumanPolicyRule,
    HumanPolicyVerdict,
    RequestContext,
    build_default_book,
    build_request_context,
    resolve_human_policy,
    stricter_decision,
    verdict_severity,
)


# =============================================================================
# Engine / book unit tests (dependency-light, no GovernanceService)
# =============================================================================


def _ctx(**overrides):
    base = dict(
        action_type="db_delete",
        tool_name="db",
        risk_level="destructive",
        actor_id="agent-1",
        agency_level="FULL",
        capabilities=(),
        facts={},
        target_haystack="db_delete db",
    )
    base.update(overrides)
    return RequestContext(**base)


def test_default_book_denies_last_replica():
    eng = HumanPolicyEngine(build_default_book())
    res = eng.evaluate(_ctx(facts={"last_replica": True}))
    assert res.matched
    assert res.verdict == HumanPolicyVerdict.DENY
    assert res.matched_rule_id == "HP-DB-LAST-REPLICA"
    assert res.governance_decision() == "DENY"
    assert res.is_dispositive_deny


def test_default_book_requires_approval_for_destructive():
    eng = HumanPolicyEngine(build_default_book())
    res = eng.evaluate(_ctx(facts={}))
    assert res.verdict == HumanPolicyVerdict.REQUIRE_APPROVAL
    assert res.requires_human
    assert res.governance_decision() == "DEFER"
    assert res.approver_policy == "dual_control"


def test_default_book_allows_read_only():
    eng = HumanPolicyEngine(build_default_book())
    res = eng.evaluate(_ctx(action_type="read", risk_level="read_only",
                            target_haystack="read fs"))
    assert res.verdict == HumanPolicyVerdict.ALLOW
    assert res.governance_decision() == "ALLOW"


def test_no_match_is_silent():
    eng = HumanPolicyEngine(build_default_book())
    res = eng.evaluate(_ctx(action_type="write", risk_level="write",
                            target_haystack="write fs"))
    assert res.available
    assert not res.matched
    assert res.verdict is None
    assert res.governance_decision() is None


def test_most_restrictive_rule_wins_at_equal_priority():
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="allow-all", verdict=HumanPolicyVerdict.ALLOW),
        HumanPolicyRule(rule_id="deny-destructive",
                        verdict=HumanPolicyVerdict.DENY,
                        risk_levels=("destructive",)),
    ))
    res = HumanPolicyEngine(book).evaluate(_ctx())
    assert res.verdict == HumanPolicyVerdict.DENY
    assert res.matched_rule_id == "deny-destructive"


def test_higher_priority_allow_overrides_broad_deny():
    # A narrow, high-priority ALLOW exception beats a broad low-priority DENY.
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="deny-broad", verdict=HumanPolicyVerdict.DENY,
                        risk_levels=("destructive",), priority=0),
        HumanPolicyRule(rule_id="allow-trusted", verdict=HumanPolicyVerdict.ALLOW,
                        risk_levels=("destructive",), actor_ids=("trusted",),
                        priority=10),
    ))
    trusted = HumanPolicyEngine(book).evaluate(_ctx(actor_id="trusted"))
    assert trusted.verdict == HumanPolicyVerdict.ALLOW
    assert trusted.matched_rule_id == "allow-trusted"
    other = HumanPolicyEngine(book).evaluate(_ctx(actor_id="someone-else"))
    assert other.verdict == HumanPolicyVerdict.DENY


def test_when_and_unless_facts():
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="deny-freetext", verdict=HumanPolicyVerdict.DENY,
                        action_types=("send_email",), when_facts=("free_text",)),
        HumanPolicyRule(rule_id="allow-templated", verdict=HumanPolicyVerdict.ALLOW,
                        action_types=("send_email",), unless_facts=("free_text",),
                        priority=1),
    ))
    eng = HumanPolicyEngine(book)
    free = eng.evaluate(_ctx(action_type="send_email", risk_level="write",
                             facts={"free_text": True}, target_haystack="send_email"))
    assert free.verdict == HumanPolicyVerdict.DENY
    templated = eng.evaluate(_ctx(action_type="send_email", risk_level="write",
                                  facts={}, target_haystack="send_email"))
    assert templated.verdict == HumanPolicyVerdict.ALLOW


def test_capabilities_any_and_target_patterns():
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="deny-cred", verdict=HumanPolicyVerdict.DENY,
                        capabilities_any=("credential_access",)),
        HumanPolicyRule(rule_id="deny-prod-target", verdict=HumanPolicyVerdict.DENY,
                        target_patterns=(r"prod/",)),
    ))
    eng = HumanPolicyEngine(book)
    assert eng.evaluate(_ctx(capabilities=("credential_access",))).verdict == HumanPolicyVerdict.DENY
    assert eng.evaluate(_ctx(target_haystack="delete prod/db")).verdict == HumanPolicyVerdict.DENY
    assert not eng.evaluate(_ctx(target_haystack="delete staging/db",
                                 risk_level="write")).matched


def test_fact_truthiness_string_values():
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="deny", verdict=HumanPolicyVerdict.DENY,
                        when_facts=("flag",)),
    ))
    eng = HumanPolicyEngine(book)
    assert eng.evaluate(_ctx(facts={"flag": "true"}, risk_level="write")).matched
    assert not eng.evaluate(_ctx(facts={"flag": "false"}, risk_level="write")).matched
    assert not eng.evaluate(_ctx(facts={"flag": ""}, risk_level="write")).matched


def test_engine_fail_closed_on_bad_regex():
    # An invalid regex in target_patterns raises during matching -> DENY.
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="bad", verdict=HumanPolicyVerdict.ALLOW,
                        target_patterns=("(unclosed",)),
    ))
    res = HumanPolicyEngine(book).evaluate(_ctx())
    assert res.verdict == HumanPolicyVerdict.DENY
    assert res.fail_closed_error
    assert any("HUMAN_POLICY_ERROR" in c for c in res.reason_codes)


def test_book_content_hash_is_stable_and_order_independent():
    r1 = HumanPolicyRule(rule_id="a", verdict=HumanPolicyVerdict.DENY,
                         risk_levels=("destructive",))
    r2 = HumanPolicyRule(rule_id="b", verdict=HumanPolicyVerdict.ALLOW,
                         risk_levels=("read_only",))
    book1 = HumanPolicyBook(rules=(r1, r2), name="x", version="1")
    book2 = HumanPolicyBook(rules=(r1, r2), name="x", version="1")
    assert book1.content_hash() == book2.content_hash()
    assert book1.policy_version() == book2.policy_version()
    # Different version string -> different policy_version
    book3 = HumanPolicyBook(rules=(r1, r2), name="x", version="2")
    assert book3.policy_version() != book1.policy_version()


def test_verdict_severity_ordering():
    assert verdict_severity(HumanPolicyVerdict.DENY) > verdict_severity(HumanPolicyVerdict.REQUIRE_APPROVAL)
    assert verdict_severity(HumanPolicyVerdict.REQUIRE_APPROVAL) > verdict_severity(HumanPolicyVerdict.ALLOW_WITH_CONSTRAINTS)
    assert verdict_severity(HumanPolicyVerdict.ALLOW_WITH_CONSTRAINTS) > verdict_severity(HumanPolicyVerdict.ALLOW)


def test_stricter_decision_helper():
    assert stricter_decision("ALLOW", "DENY") == "DENY"
    assert stricter_decision("DENY", "ALLOW") == "DENY"
    assert stricter_decision("ALLOW", "DEFER") == "DEFER"
    assert stricter_decision("ALLOW", "ALLOW") == "ALLOW"


def test_resolve_human_policy_no_engine_is_unavailable():
    res = resolve_human_policy(None, object(), "write")
    assert not res.available
    assert not res.matched


# =============================================================================
# build_request_context extraction
# =============================================================================


class _Req:
    def __init__(self, **kw):
        self.action_type = kw.get("action_type", "act")
        self.tool_name = kw.get("tool_name")
        self.actor_id = kw.get("actor_id", "a")
        self.agency_level = kw.get("agency_level", "FULL")
        self.capabilities = kw.get("capabilities", [])
        self.parameters_summary = kw.get("parameters_summary")
        self.metadata = kw.get("metadata")


def test_build_request_context_extracts_facts_and_haystack():
    req = _Req(action_type="db_delete", tool_name="db", actor_id="agent-1",
               parameters_summary={"path": "prod/db"},
               metadata={"facts": {"last_replica": True}, "target": "k8s://prod"})
    ctx = build_request_context(req, "destructive")
    assert ctx.risk_level == "destructive"
    assert ctx.facts == {"last_replica": True}
    assert "prod/db" in ctx.target_haystack
    assert "k8s://prod" in ctx.target_haystack


def test_build_request_context_tolerates_missing_metadata():
    ctx = build_request_context(_Req(metadata=None), "write")
    assert ctx.facts == {}
    assert ctx.action_type == "act"


# =============================================================================
# GovernanceService integration
# =============================================================================


def _svc():
    return GovernanceService(human_policy_engine=HumanPolicyEngine(build_default_book()))


def _strong_signals(**kw):
    base = dict(quality_score=1.0, coherence_score=1.0, internal_consistency=1.0,
                goal_alignment=1.0, trajectory_confidence=1.0, agency_level="FULL")
    base.update(kw)
    return base


def test_service_human_deny_is_dispositive_over_strong_llm():
    svc = _svc()
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="db_delete", tool_name="database_delete",
        metadata={"facts": {"last_replica": True}}, **_strong_signals())
    resp = svc.authorize(req)
    assert resp.governance_decision == APIGovernanceDecision.DENY
    assert not resp.eligible
    assert resp.human_policy["verdict"] == "DENY"
    assert resp.human_policy["matched_rule_id"] == "HP-DB-LAST-REPLICA"
    assert "HUMAN_POLICY:DENY" in resp.rationale_codes


def test_service_human_require_approval_forces_defer():
    svc = _svc()
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="db_delete", tool_name="database_delete",
        metadata={"facts": {}}, **_strong_signals())
    resp = svc.authorize(req)
    assert resp.governance_decision == APIGovernanceDecision.DEFER
    assert resp.requires_human_approval
    assert resp.human_policy["verdict"] == "REQUIRE_APPROVAL"


def test_service_human_allow_is_ceiling_llm_can_tighten():
    svc = _svc()
    # Read-only => human ALLOW baseline, but terrible LLM signals tighten to DENY.
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="file_read", tool_name="read_file",
        quality_score=0.0, coherence_score=0.0, internal_consistency=0.0,
        goal_alignment=0.0, trajectory_confidence=0.0, agency_level="FULL")
    resp = svc.authorize(req)
    assert resp.human_policy["verdict"] == "ALLOW"
    assert resp.governance_decision == APIGovernanceDecision.DENY  # LLM tightened


def test_service_human_allow_and_strong_llm_allows():
    svc = _svc()
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="file_read", tool_name="read_file",
        **_strong_signals())
    resp = svc.authorize(req)
    assert resp.human_policy["verdict"] == "ALLOW"
    assert resp.governance_decision == APIGovernanceDecision.ALLOW


def test_service_no_matching_rule_leaves_llm_baseline():
    svc = _svc()
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="file_write", tool_name="write_file",
        **_strong_signals())
    resp = svc.authorize(req)
    assert resp.human_policy["matched"] is False
    assert resp.governance_decision == APIGovernanceDecision.ALLOW


def test_service_without_engine_is_backward_compatible():
    svc = GovernanceService()  # no human policy engine
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="file_read", tool_name="read_file",
        **_strong_signals())
    resp = svc.authorize(req)
    assert resp.human_policy is None
    assert resp.governance_decision == APIGovernanceDecision.ALLOW


def test_service_records_human_policy_in_audit_event():
    svc = _svc()
    req = AuthorizationRequest(
        actor_id="agent-1", action_type="db_delete", tool_name="database_delete",
        metadata={"facts": {"last_replica": True}}, **_strong_signals())
    resp = svc.authorize(req)
    snap = resp.audit_event.request_snapshot
    assert snap["human_policy_matched"] is True
    assert snap["human_policy_verdict"] == "DENY"
    assert snap["human_policy_rule_id"] == "HP-DB-LAST-REPLICA"
    assert resp.audit_event.human_policy["governance_decision"] == "DENY"


def test_service_custom_book_actor_scoped_allow_exception():
    # High-priority allow exception for a trusted actor overrides a broad deny.
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="deny-writes", verdict=HumanPolicyVerdict.DENY,
                        risk_levels=("write",)),
        HumanPolicyRule(rule_id="allow-trusted-writes",
                        verdict=HumanPolicyVerdict.ALLOW,
                        risk_levels=("write",), actor_ids=("service-account",),
                        priority=100),
    ))
    svc = GovernanceService(human_policy_engine=HumanPolicyEngine(book))
    denied = svc.authorize(AuthorizationRequest(
        actor_id="random", action_type="file_write", tool_name="write_file",
        **_strong_signals()))
    assert denied.governance_decision == APIGovernanceDecision.DENY
    allowed = svc.authorize(AuthorizationRequest(
        actor_id="service-account", action_type="file_write", tool_name="write_file",
        **_strong_signals()))
    assert allowed.governance_decision == APIGovernanceDecision.ALLOW
