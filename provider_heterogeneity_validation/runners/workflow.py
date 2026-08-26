"""Heterogeneity workflow runner (composition — imports providers + reuses the pilot flow).

For one (scenario, configuration, failure profile): deterministically selects an
assertion provider, invokes it, feeds the result into the DGM assessment/
recommendation flow, then — if the assertion proceeds — selects an action provider,
authorizes through the control plane, enforces constraints, executes, and
reconciles. Selection happens strictly before invocation, so a substantive result
never influences selection (no governance shopping). Reuses the frozen, validated
Phase 5I/6A DGM flow so C1 (TAP + ActionGate) reproduces Phase 6A.
"""
from __future__ import annotations

import dataclasses

from comparative_governance_benchmark.runners.common import run_action_flow, run_case_flow
from comparative_governance_benchmark.runners.dgm import build_services
from comparative_governance_benchmark.runners.execution import build_execution_adapter
from comparative_governance_benchmark.runners.determinism import make_clock, make_id_factory
from governance_providers.api import (
    ActionGovernanceControlPlaneAdapter, AssertionGovernanceRequest)

from ..failure_injection.profiles import FailureProfile, failure_effect
from ..policies.requirements import (
    required_action_capabilities, required_assertion_capabilities)
from ..schemas.result import HeteroResult
from ..selection.resolve import ResolutionPolicy, SelectionRequest, select
from .composition import (
    _ACTION_BUILDERS, _ASSERTION_BUILDERS, build_action_catalog, build_assertion_catalog)

_ASSERT = "ASSERTION_GOVERNANCE"
_ACTION = "ACTION_GOVERNANCE"
_PROCEED = {"SUPPORTED", "CONSTRAINED"}
_IMPOSSIBLE = ("__impossible_capability__",)


def _assertion_request(config, scenario, effect):
    caps = ()
    if config.capability_driven:
        caps = required_assertion_capabilities(scenario)
    if effect.get("special") == "NO_CAPABILITY_MATCH":
        caps = _IMPOSSIBLE
    return SelectionRequest(
        kind=_ASSERT, policy=config.assertion_policy, fixed_id=config.assertion_fixed,
        preference_order=config.assertion_preference, required_capabilities=caps,
        allow_fallback=config.allow_fallback, allow_degraded=config.allow_degraded)


def _action_request(config, scenario, effect):
    caps = ()
    if config.capability_driven:
        caps = required_action_capabilities(scenario)
    if effect.get("special") == "NO_CAPABILITY_MATCH":
        caps = _IMPOSSIBLE
    return SelectionRequest(
        kind=_ACTION, policy=config.action_policy, fixed_id=config.action_fixed,
        preference_order=config.action_preference, required_capabilities=caps,
        allow_fallback=config.allow_fallback, allow_degraded=config.allow_degraded)


def run(scenario, config, failure_profile: FailureProfile = FailureProfile.NORMAL) -> HeteroResult:
    r = HeteroResult(scenario_id=scenario.scenario_id, configuration_id=config.config_id, cost={})
    try:
        _run(scenario, config, failure_profile, r)
    except Exception as exc:  # a runner error is recorded, never raised out
        r.error = f"{type(exc).__name__}: {exc}"
    return r


def _run(scenario, config, failure_profile, r):
    effect = failure_effect(failure_profile)
    a_cat = build_assertion_catalog(scenario, config, effect)
    b_cat = build_action_catalog(scenario, config, effect)
    request_id = f"{scenario.scenario_id}:{config.config_id}"

    # --- assertion selection (registry duplicate id fails safe) -------------
    if effect.get("special") == "REGISTRY_DUPLICATE_ID" and a_cat.has_duplicate_ids(_ASSERT):
        r.no_valid_assertion_provider = True
        r.assertion_outcome = "INDETERMINATE"
        r.trace = {"scenario_id": scenario.scenario_id, "configuration": config.config_id,
                   "registry_error": "duplicate_provider_id", "dispatched": False}
        return

    a_entry, a_rec = select(a_cat, _assertion_request(config, scenario, effect),
                            request_id=request_id + ":assert")
    r.assertion_selection = a_rec
    r.assertion_fallback_used = a_rec.fallback_used
    if a_entry is None:
        r.no_valid_assertion_provider = True
        r.assertion_outcome = "INDETERMINATE"       # fail-safe: no valid provider
        r.trace = {"scenario_id": scenario.scenario_id, "configuration": config.config_id,
                   "assertion_selected": None, "dispatched": False}
        return

    r.assertion_provider_id = a_entry.provider_id
    provider = a_entry.build(); provider.initialize()
    req = AssertionGovernanceRequest(
        assertion=scenario.assertion, assertion_type=scenario.assertion_type,
        evidence_refs=tuple(e.evidence_id for e in scenario.evidence),
        correlation_id=scenario.scenario_id)
    result = provider.evaluate(req)

    # human review: supply evidence for INDETERMINATE → re-invoke same selected provider
    if (result.coverage.value == "INDETERMINATE" and scenario.human_review
            and scenario.human_review.action == "supply_evidence"
            and scenario.human_review.reevaluate_tap is not None):
        r.human_review_requested = True
        r.human_authority = scenario.human_review.approver
        reeval_scn = dataclasses.replace(scenario, tap_policy=scenario.human_review.reevaluate_tap)
        reprovider = _ASSERTION_BUILDERS[a_entry.provider_id](reeval_scn, None)()
        reprovider.initialize()
        result = reprovider.evaluate(dataclasses.replace(
            req, evidence_refs=req.evidence_refs
            + tuple(e.evidence_id for e in scenario.human_review.added_evidence)))

    r.assertion_outcome = result.coverage.value

    # --- DGM assessment / recommendation / decision -------------------------
    seed = request_id
    assessment_id = "assess-" + (result.fingerprint or "0")[:12]
    dgm = build_services(seed + ":case")
    flow = run_case_flow(dgm, scenario, coverage=result.coverage.value,
                         assessment_id=assessment_id)
    r.audit_events = len(dgm.audit_events())
    r.trace_links = 4
    r.trace = {"scenario_id": scenario.scenario_id, "configuration": config.config_id,
               "assertion_selected": a_entry.provider_id,
               "assertion_fallback": a_rec.fallback_used,
               "assertion_outcome": result.coverage.value,
               "case_id": flow.case_id, "decision_id": flow.decision_id}

    if result.coverage.value not in _PROCEED:
        r.execution_outcome = "NOT_PERFORMED"
        r.trace["dispatched"] = False
        return

    # --- action selection + authorization -----------------------------------
    b_entry, b_rec = select(b_cat, _action_request(config, scenario, effect),
                            request_id=request_id + ":action")
    r.action_selection = b_rec
    r.action_fallback_used = b_rec.fallback_used
    if b_entry is None:
        r.no_valid_action_provider = True
        r.authorization_outcome = "INDETERMINATE"    # fail-safe: no valid provider, no dispatch
        r.trace.update(action_selected=None, dispatched=False)
        return

    r.action_provider_id = b_entry.provider_id
    action_provider = b_entry.build(); action_provider.initialize()
    # same time domain as the DGM services built from `seed + ":act"` below: the
    # CER is issued on the scenario clock, so the adapter must read it too.
    control_plane = ActionGovernanceControlPlaneAdapter(
        action_provider, clock=make_clock(seed + ":act"))
    adapter = build_execution_adapter(scenario.proposed_action.action_type, scenario.execution,
                                      id_factory=make_id_factory(seed + ":exec"),
                                      clock=make_clock(seed + ":exec"))
    dgm2 = build_services(seed + ":act", control_plane=control_plane, execution_adapter=adapter)
    flow2 = run_case_flow(dgm2, scenario, coverage=result.coverage.value,
                          assessment_id=assessment_id)

    approval = _approval(scenario)
    if scenario.human_review and scenario.human_review.action in ("approve_action", "decline_action"):
        r.human_review_requested = True
        r.human_authority = scenario.human_review.approver
    action = run_action_flow(dgm2, scenario, flow2.decision_id, approval=approval)

    r.authorization_outcome = action.authorization_outcome
    r.constraints = tuple(action.constraints)
    r.obligations = tuple(action.obligations)
    r.dispatched = action.dispatched
    r.execution_outcome = action.execution_outcome
    r.reconciliation_outcome = action.reconciliation
    r.final_governance_compliance = action.compliance
    r.audit_events = len(dgm2.audit_events())
    r.trace_links = 6
    r.trace.update(action_selected=b_entry.provider_id, action_fallback=b_rec.fallback_used,
                   authorization_outcome=action.authorization_outcome,
                   dispatched=action.dispatched, reconciliation=action.reconciliation)


def _approval(scenario):
    hr = scenario.human_review
    if hr and hr.action == "approve_action":
        return True
    if hr and hr.action == "decline_action":
        return False
    return None
