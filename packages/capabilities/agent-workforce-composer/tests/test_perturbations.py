"""Deterministic perturbation scenarios (§25) — each yields an explainable plan
change or a typed NO_FEASIBLE_TEAM result."""
from __future__ import annotations

from ugence_agent_workforce_composer import fixtures
from ugence_agent_workforce_composer.agents import build_registry_snapshot
from ugence_agent_workforce_composer.composition_contracts import AgentTeamPlanState
from ugence_agent_workforce_composer.plan import build_agent_team_plan
from ugence_agent_workforce_composer.policy import (
    finalize_enterprise_policy,
    finalize_eligibility_policy,
)
from ugence_agent_workforce_composer.workflow import Provenance
from ._p2 import adaptation

BASE_ADAPT = None


def _plan(*, enterprise=None, eligibility=None, composition=None, snapshot=None, now=None, name="procurement"):
    adapt = adaptation(name)
    return build_agent_team_plan(
        adapt, snapshot or fixtures.registry_snapshot(),
        enterprise or fixtures.enterprise_policy(), eligibility or fixtures.eligibility_policy(),
        fixtures.ranking_policy(), composition or fixtures.team_composition_policy(),
        fixtures.permission_policy(), fixtures.fallback_policy(),
        now if now is not None else fixtures.LOGICAL_TIME)


def _ent(**kw):
    return finalize_enterprise_policy(
        fixtures.enterprise_policy().model_copy(update={**kw, "policy_digest": ""}))


BASELINE = None


def _baseline():
    global BASELINE
    if BASELINE is None:
        BASELINE = _plan()
    return BASELINE


def test_provider_policy_change_changes_plan():
    p = _plan(enterprise=_ent(forbidden_providers=("forbiddenco", "openai")))
    assert p.plan_fingerprint != _baseline().plan_fingerprint


def test_residency_policy_change():
    p = _plan(enterprise=_ent(required_residencies=("IN",), allowed_residencies=("IN",)))
    # no US-only agents remain eligible for US-resident roles → no feasible team
    assert p.plan_state in (AgentTeamPlanState.NO_FEASIBLE_TEAM, AgentTeamPlanState.COMPLETE)
    assert p.plan_fingerprint != _baseline().plan_fingerprint


def test_cost_ceiling_reduction():
    from ugence_agent_workforce_composer.composition import TeamCompositionPolicy
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    tight = stamp_fingerprint(fixtures.team_composition_policy().model_copy(
        update={"team_cost_hard_ceiling": 0.0, "policy_digest": ""}), "policy_digest")
    p = _plan(composition=tight)
    assert p.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM


def test_latency_ceiling_reduction():
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    tight = stamp_fingerprint(fixtures.team_composition_policy().model_copy(
        update={"team_latency_hard_ceiling": 1.0, "policy_digest": ""}), "policy_digest")
    p = _plan(composition=tight)
    assert p.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM


def test_agent_version_revocation():
    p = _plan(enterprise=_ent(forbidden_agent_versions=("agent_procurement_specialist@2.1.0",)))
    # the sole risk/recommendation candidate is revoked → no feasible team
    assert p.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM
    assert p.plan_fingerprint != _baseline().plan_fingerprint


def test_evidence_expiry_via_injected_time():
    # advance logical time beyond all evidence validity (valid_until=2_000_000) → ineligible
    p = _plan(now=3_000_000.0)
    assert p.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM


def test_permission_policy_tightening():
    from ugence_agent_workforce_composer.permissions import PermissionBoundingPolicy
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    adapt = adaptation("procurement")
    tight = stamp_fingerprint(
        PermissionBoundingPolicy(policy_id="pp", policy_version="1",
                                 governance_owned_permissions=("read_context",)), "policy_digest")
    p = build_agent_team_plan(adapt, fixtures.registry_snapshot(), fixtures.enterprise_policy(),
                              fixtures.eligibility_policy(), fixtures.ranking_policy(),
                              fixtures.team_composition_policy(), tight, fixtures.fallback_policy(),
                              fixtures.LOGICAL_TIME)
    # read_context is now governance-owned → risk/recommendation roles (which require it) infeasible
    assert p.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM


def test_provider_concentration_tightening():
    from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint
    # 30% cap: two anthropic roles (risk+recommendation) exceed any small team → infeasible
    tight = stamp_fingerprint(fixtures.team_composition_policy().model_copy(
        update={"provider_concentration_limit_pct": 30, "policy_digest": ""}), "policy_digest")
    p = _plan(composition=tight)
    assert p.plan_state is AgentTeamPlanState.NO_FEASIBLE_TEAM


def test_candidate_removal_changes_plan():
    snap = fixtures.registry_snapshot()
    removed = ("agent_support_specialist", "1.3.0")
    profiles = [p for p in snap.agent_profiles if (p.agent_id, p.agent_version) != removed]
    evidence = [e for e in snap.capability_evidence if (e.agent_id, e.agent_version) != removed]
    reduced = build_registry_snapshot(
        snapshot_id="reduced", registry_version="awc_synth.v1", logical_time=fixtures.LOGICAL_TIME,
        agent_profiles=profiles, capability_evidence=evidence,
        provenance=Provenance(source_kind="perturbation", synthetic=True))
    p = _plan(snapshot=reduced)
    # removing the openai supplier-evidence pick forces a different (or no) team
    assert p.plan_fingerprint != _baseline().plan_fingerprint
