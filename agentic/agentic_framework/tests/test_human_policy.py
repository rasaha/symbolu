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
    ActionCriticalityRegistry,
    AuthorityModeResolution,
    CriticalityClass,
    HumanPolicyBook,
    HumanPolicyEngine,
    HumanPolicyMode,
    HumanPolicyRule,
    HumanPolicyVerdict,
    RequestContext,
    UncertainDisposition,
    build_default_book,
    build_default_criticality_registry,
    build_request_context,
    resolve_authority_mode,
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


# --- Authority mode switch: BASELINE vs SOURCE_OF_TRUTH ---------------------


def _sot_svc():
    return GovernanceService(
        human_policy_engine=HumanPolicyEngine(
            build_default_book(), mode=HumanPolicyMode.SOURCE_OF_TRUTH,
        )
    )


def test_engine_mode_defaults_to_baseline():
    eng = HumanPolicyEngine(build_default_book())
    assert eng.mode == HumanPolicyMode.BASELINE
    res = eng.evaluate(_ctx(action_type="read", risk_level="read_only",
                            target_haystack="read fs"))
    assert res.mode == "baseline"


def test_source_of_truth_allow_overrides_weak_llm():
    # Read-only human ALLOW with terrible LLM signals:
    #   BASELINE  -> LLM tightens to DENY
    #   SOURCE_OF_TRUTH -> human ALLOW is dispositive
    weak = dict(action_type="file_read", tool_name="read_file", agency_level="FULL",
                quality_score=0.0, coherence_score=0.0, internal_consistency=0.0,
                goal_alignment=0.0, trajectory_confidence=0.0)
    baseline = _svc().authorize(AuthorizationRequest(actor_id="a", **weak))
    sot = _sot_svc().authorize(AuthorizationRequest(actor_id="a", **weak))
    assert baseline.governance_decision == APIGovernanceDecision.DENY
    assert sot.governance_decision == APIGovernanceDecision.ALLOW
    assert sot.human_policy["mode"] == "source_of_truth"
    assert sot.audit_event.request_snapshot["human_policy_source_of_truth_override"] is True
    assert "HUMAN_POLICY_AUTHORITATIVE" in sot.rationale_codes


def test_source_of_truth_still_honors_forbidden_capability_hard_block():
    # A human ALLOW cannot open a forbidden-capability action even in
    # source-of-truth mode — that hard block is an independent fail-closed
    # invariant.
    resp = _sot_svc().authorize(AuthorizationRequest(
        actor_id="a", action_type="file_read", tool_name="read_file",
        capabilities=["malware_execution"], agency_level="FULL",
        quality_score=1.0, coherence_score=1.0, internal_consistency=1.0,
        goal_alignment=1.0, trajectory_confidence=1.0))
    assert resp.governance_decision == APIGovernanceDecision.DENY


def test_source_of_truth_deny_and_require_approval_unchanged():
    sot = _sot_svc()
    deny = sot.authorize(AuthorizationRequest(
        actor_id="a", action_type="db_delete", tool_name="database_delete",
        metadata={"facts": {"last_replica": True}}, **_strong_signals()))
    assert deny.governance_decision == APIGovernanceDecision.DENY
    approval = sot.authorize(AuthorizationRequest(
        actor_id="a", action_type="db_delete", tool_name="database_delete",
        metadata={"facts": {}}, **_strong_signals()))
    assert approval.governance_decision == APIGovernanceDecision.DEFER
    assert approval.requires_human_approval


def test_source_of_truth_no_match_falls_back_to_llm():
    # No human rule matches a write => identical LLM pipeline in both modes.
    req = dict(action_type="file_write", tool_name="write_file", **_strong_signals())
    sot = _sot_svc().authorize(AuthorizationRequest(actor_id="a", **req))
    assert sot.human_policy["matched"] is False
    assert sot.governance_decision == APIGovernanceDecision.ALLOW
    assert "HUMAN_POLICY_AUTHORITATIVE" not in sot.rationale_codes


# =============================================================================
# Per-decision authority-mode resolution (criticality registry + precedence)
# =============================================================================


def test_criticality_registry_classifies_critical_noncritical_unknown():
    reg = build_default_criticality_registry()
    crit, _ = reg.classify(_ctx(risk_level="destructive"))
    assert crit == CriticalityClass.CRITICAL
    noncrit, _ = reg.classify(_ctx(risk_level="read_only"))
    assert noncrit == CriticalityClass.NON_CRITICAL
    unknown, basis = reg.classify(_ctx(risk_level="write"))
    assert unknown == CriticalityClass.UNKNOWN
    assert basis == ("unclassified",)


def test_criticality_promoting_fact_overrides_noncritical():
    # A deterministic impact fact promotes an otherwise non-critical action.
    reg = build_default_criticality_registry()
    crit, basis = reg.classify(_ctx(risk_level="read_only", facts={"last_replica": True}))
    assert crit == CriticalityClass.CRITICAL
    assert any("promoted:fact:last_replica" in b for b in basis)


def test_resolve_authority_mode_precedence():
    reg = build_default_criticality_registry()
    # 1. explicit rule mode wins over registry.
    rule_sot = HumanPolicyRule(rule_id="r", verdict=HumanPolicyVerdict.ALLOW,
                               authority_mode=HumanPolicyMode.SOURCE_OF_TRUTH)
    amr = resolve_authority_mode(rule=rule_sot, registry=reg,
                                 engine_default=HumanPolicyMode.BASELINE,
                                 ctx=_ctx(risk_level="read_only"))
    assert amr.effective_mode == HumanPolicyMode.SOURCE_OF_TRUTH
    assert amr.source == "rule_explicit"
    # 2. registry: critical -> SOURCE_OF_TRUTH, non-critical -> BASELINE.
    rule = HumanPolicyRule(rule_id="r", verdict=HumanPolicyVerdict.ALLOW)
    amr_c = resolve_authority_mode(rule=rule, registry=reg,
                                   engine_default=HumanPolicyMode.BASELINE,
                                   ctx=_ctx(risk_level="destructive"))
    assert amr_c.effective_mode == HumanPolicyMode.SOURCE_OF_TRUTH
    assert amr_c.source == "criticality_registry"
    amr_n = resolve_authority_mode(rule=rule, registry=reg,
                                   engine_default=HumanPolicyMode.SOURCE_OF_TRUTH,
                                   ctx=_ctx(risk_level="read_only"))
    assert amr_n.effective_mode == HumanPolicyMode.BASELINE
    # 3. no registry -> engine default.
    amr_d = resolve_authority_mode(rule=rule, registry=None,
                                   engine_default=HumanPolicyMode.SOURCE_OF_TRUTH,
                                   ctx=_ctx(risk_level="write"))
    assert amr_d.effective_mode == HumanPolicyMode.SOURCE_OF_TRUTH
    assert amr_d.source == "engine_default"


def test_resolve_authority_mode_uncertain_conservative():
    # REQUIRE_APPROVAL disposition → SOURCE_OF_TRUTH + DEFER floor.
    reg = ActionCriticalityRegistry(
        critical_risk_levels=(), non_critical_risk_levels=(),
        uncertain_disposition=UncertainDisposition.REQUIRE_APPROVAL)
    amr = resolve_authority_mode(
        rule=HumanPolicyRule(rule_id="r", verdict=HumanPolicyVerdict.ALLOW),
        registry=reg, engine_default=HumanPolicyMode.BASELINE,
        ctx=_ctx(risk_level="write"))
    assert amr.effective_mode == HumanPolicyMode.SOURCE_OF_TRUTH
    assert amr.source == "uncertain_conservative"
    assert amr.conservative_floor == "DEFER"
    # TREAT_AS_CRITICAL disposition → SOURCE_OF_TRUTH, no floor.
    reg2 = ActionCriticalityRegistry(
        critical_risk_levels=(), non_critical_risk_levels=(),
        uncertain_disposition=UncertainDisposition.TREAT_AS_CRITICAL)
    amr2 = resolve_authority_mode(
        rule=HumanPolicyRule(rule_id="r", verdict=HumanPolicyVerdict.ALLOW),
        registry=reg2, engine_default=HumanPolicyMode.BASELINE,
        ctx=_ctx(risk_level="write"))
    assert amr2.effective_mode == HumanPolicyMode.SOURCE_OF_TRUTH
    assert amr2.conservative_floor is None


def test_engine_populates_per_decision_resolution():
    reg = build_default_criticality_registry()
    eng = HumanPolicyEngine(build_default_book(), criticality_registry=reg)
    res = eng.evaluate(_ctx(action_type="read", risk_level="read_only",
                            target_haystack="read fs"))
    assert res.effective_mode == "baseline"
    assert res.mode_resolution_source == "criticality_registry"
    assert res.criticality == "non_critical"
    assert res.criticality_mode == "baseline"


# --- Concurrent per-decision modes on ONE service instance ------------------


def _concurrent_service():
    """A single service whose engine resolves mode per decision."""
    book = HumanPolicyBook(rules=(
        HumanPolicyRule(rule_id="crit-proddb", verdict=HumanPolicyVerdict.ALLOW,
                        tool_names=("prod_db",)),
        HumanPolicyRule(rule_id="noncrit-report", verdict=HumanPolicyVerdict.ALLOW,
                        tool_names=("report_view",)),
        HumanPolicyRule(rule_id="uncertain-batch", verdict=HumanPolicyVerdict.ALLOW,
                        tool_names=("batch_job",)),
        HumanPolicyRule(rule_id="special-sot", verdict=HumanPolicyVerdict.ALLOW,
                        tool_names=("special",),
                        authority_mode=HumanPolicyMode.SOURCE_OF_TRUTH),
    ))
    registry = ActionCriticalityRegistry(
        critical_tools=("prod_db",),
        non_critical_tools=("report_view", "special"),
        critical_risk_levels=(), non_critical_risk_levels=(),
        uncertain_disposition=UncertainDisposition.REQUIRE_APPROVAL,
    )
    return GovernanceService(
        human_policy_engine=HumanPolicyEngine(book, criticality_registry=registry)
    )


_WEAK = dict(quality_score=0.0, coherence_score=0.0, internal_consistency=0.0,
             goal_alignment=0.0, trajectory_confidence=0.0, agency_level="FULL")


def test_concurrent_critical_source_of_truth_allow():
    # critical + human ALLOW + model DENY → ALLOW (no hard block).
    svc = _concurrent_service()
    resp = svc.authorize(AuthorizationRequest(
        actor_id="a", action_type="act", tool_name="prod_db", **_WEAK))
    assert resp.governance_decision == APIGovernanceDecision.ALLOW
    hp = resp.human_policy
    assert hp["effective_mode"] == "source_of_truth"
    assert hp["mode_resolution_source"] == "criticality_registry"
    assert hp["criticality"] == "critical"
    assert hp["model_advisory_decision"] == "DENY"
    assert hp["final_authority_used"] == "HUMAN_SOURCE_OF_TRUTH"


def test_concurrent_noncritical_baseline_deny():
    # non-critical + human ALLOW + model DENY → DENY (baseline tightening).
    svc = _concurrent_service()
    resp = svc.authorize(AuthorizationRequest(
        actor_id="a", action_type="act", tool_name="report_view", **_WEAK))
    assert resp.governance_decision == APIGovernanceDecision.DENY
    hp = resp.human_policy
    assert hp["effective_mode"] == "baseline"
    assert hp["criticality"] == "non_critical"
    assert hp["final_authority_used"] == "HUMAN_BASELINE_COMPOSED"


def test_concurrent_critical_forbidden_capability_hard_block():
    # critical + human ALLOW + forbidden capability → DENY (hard block wins).
    svc = _concurrent_service()
    resp = svc.authorize(AuthorizationRequest(
        actor_id="a", action_type="act", tool_name="prod_db",
        capabilities=["malware_execution"], **_WEAK))
    assert resp.governance_decision == APIGovernanceDecision.DENY
    hp = resp.human_policy
    assert hp["final_authority_used"] == "HARD_BLOCK"
    assert any("malware_execution" in p for p in hp["hard_block_provenance"])


def test_concurrent_uncertain_criticality_conservative():
    # uncertain criticality + human ALLOW → conservative DEFER + requires_human.
    svc = _concurrent_service()
    resp = svc.authorize(AuthorizationRequest(
        actor_id="a", action_type="act", tool_name="batch_job",
        quality_score=1.0, coherence_score=1.0, internal_consistency=1.0,
        goal_alignment=1.0, trajectory_confidence=1.0, agency_level="FULL"))
    assert resp.governance_decision == APIGovernanceDecision.DEFER
    assert resp.requires_human_approval
    hp = resp.human_policy
    assert hp["criticality"] == "unknown"
    assert hp["mode_resolution_source"] == "uncertain_conservative"
    assert hp["conservative_floor"] == "DEFER"


def test_concurrent_explicit_rule_mode_overrides_action_class_default():
    # 'special' is non-critical in the registry (→ baseline) but the matched
    # rule explicitly forces SOURCE_OF_TRUTH, so a model DENY cannot override.
    svc = _concurrent_service()
    resp = svc.authorize(AuthorizationRequest(
        actor_id="a", action_type="act", tool_name="special", **_WEAK))
    assert resp.governance_decision == APIGovernanceDecision.ALLOW
    hp = resp.human_policy
    assert hp["effective_mode"] == "source_of_truth"
    assert hp["mode_resolution_source"] == "rule_explicit"
    assert hp["criticality"] == "non_critical"
    assert hp["criticality_mode"] == "baseline"


def test_one_service_handles_all_classes_in_sequence():
    # The same service instance processes critical, non-critical, and uncertain
    # requests back-to-back, each under its own resolved authority mode.
    svc = _concurrent_service()
    crit = svc.authorize(AuthorizationRequest(actor_id="a", action_type="act",
                                              tool_name="prod_db", **_WEAK))
    noncrit = svc.authorize(AuthorizationRequest(actor_id="a", action_type="act",
                                                 tool_name="report_view", **_WEAK))
    assert crit.human_policy["effective_mode"] == "source_of_truth"
    assert noncrit.human_policy["effective_mode"] == "baseline"
    assert crit.governance_decision == APIGovernanceDecision.ALLOW
    assert noncrit.governance_decision == APIGovernanceDecision.DENY


def test_no_registry_preserves_engine_default_mode():
    # No criticality registry and no per-rule mode → engine default governs,
    # exactly as before this feature existed.
    baseline_eng = HumanPolicyEngine(build_default_book())  # default BASELINE
    svc = GovernanceService(human_policy_engine=baseline_eng)
    resp = svc.authorize(AuthorizationRequest(
        actor_id="a", action_type="file_read", tool_name="read_file", **_WEAK))
    hp = resp.human_policy
    assert hp["effective_mode"] == "baseline"
    assert hp["mode_resolution_source"] == "engine_default"
    assert resp.governance_decision == APIGovernanceDecision.DENY  # LLM tightened


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
