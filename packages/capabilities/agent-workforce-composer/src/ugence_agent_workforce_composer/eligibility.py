"""The deterministic hard-constraint eligibility engine + result/explanation/replay.

Pure functions only. Time, policies and the registry snapshot are injected — no
ambient state, no clock, no network, no execution. For every role × agent pair
exactly one :class:`AgentEligibilityResult` is produced (invariant I3), and the
engine emits **complete** elimination accounting: it does not stop at the first
failed condition (unless the policy explicitly enables short-circuit).

``ELIGIBLE`` means only: *no currently evaluated hard constraint disqualifies this
agent for this role under the pinned inputs.* It never means selected,
recommended, best, authorized, approved for execution, assigned, or production-safe.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .agents import AgentProfile, AgentRegistrySnapshot, AgentStatus
from .canonical import AwcModel
from .contracts import (
    NO_ELIGIBLE_AGENT,
    Criticality,
    EligibilityState,
    EvidenceClass,
    Verdict,
)
from .fingerprint import stamp_fingerprint
from .policy import EligibilityPolicy, EnterpriseAgentPolicy
from .reasons import EliminationReason
from .version import CONTRACT_VERSION
from .workflow import WorkflowRoleRequirement

_EVIDENCE_RANK = {"DECLARED": 1, "MEASURED": 2, "OBSERVED": 3}


class ConditionResult(AwcModel):
    """The outcome of a single hard-constraint condition (fully accounted)."""

    condition: str
    verdict: Verdict
    reason: str            # "OK" or an EliminationReason value
    criticality: Criticality
    detail: str = ""


class AgentEligibilityResult(AwcModel):
    """Exactly-one result for a role × agent pair."""

    contract_version: str = CONTRACT_VERSION
    role_id: str
    agent_id: str
    agent_version: str
    state: EligibilityState
    passed_conditions: Tuple[str, ...] = ()
    failed_conditions: Tuple[ConditionResult, ...] = ()
    unknown_conditions: Tuple[ConditionResult, ...] = ()
    elimination_reasons: Tuple[str, ...] = ()
    evidence_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    snapshot_digest: str = ""
    role_fingerprint: str = ""
    profile_fingerprint: str = ""
    policy_digest: str = ""
    evaluated_at: float = 0.0
    result_fingerprint: str = ""

    @property
    def eligible(self) -> bool:
        return self.state is EligibilityState.ELIGIBLE


class RoleEligibilityReport(AwcModel):
    """All results for one role across the whole snapshot (total agent accounting)."""

    contract_version: str = CONTRACT_VERSION
    role_id: str
    workflow_id: str = ""
    snapshot_digest: str = ""
    enterprise_policy_digest: str = ""
    eligibility_policy_digest: str = ""
    evaluated_at: float = 0.0
    results: Tuple[AgentEligibilityResult, ...] = ()
    eligible_agent_ids: Tuple[str, ...] = ()
    eliminated_agent_ids: Tuple[str, ...] = ()
    indeterminate_agent_ids: Tuple[str, ...] = ()
    outcome: str = NO_ELIGIBLE_AGENT
    report_fingerprint: str = ""


class EligibilityExplanation(AwcModel):
    """Deterministic, human-readable explanation for a role's evaluation."""

    role_id: str
    outcome: str
    eligible: Tuple[str, ...] = ()
    eliminated: Tuple[Tuple[str, Tuple[str, ...]], ...] = ()   # (agent@ver, reasons)
    indeterminate: Tuple[str, ...] = ()
    narrative: Tuple[str, ...] = ()


class EligibilityReplayRecord(AwcModel):
    """Everything needed to deterministically replay a role evaluation."""

    contract_version: str = CONTRACT_VERSION
    role_id: str
    role_fingerprint: str
    snapshot_digest: str
    enterprise_policy_digest: str
    eligibility_policy_digest: str
    logical_time: float
    result_fingerprints: Tuple[str, ...] = ()
    report_fingerprint: str = ""
    replay_fingerprint: str = ""


class WorkflowEligibilityResult(AwcModel):
    """Per-role reports + explanations + replay records for a whole workflow."""

    contract_version: str = CONTRACT_VERSION
    workflow_identity: str
    adaptation_fingerprint: str
    snapshot_digest: str
    enterprise_policy_digest: str
    eligibility_policy_digest: str
    logical_time: float
    reports: Tuple[RoleEligibilityReport, ...] = ()
    explanations: Tuple[EligibilityExplanation, ...] = ()
    replay_records: Tuple[EligibilityReplayRecord, ...] = ()
    workflow_fingerprint: str = ""


# --------------------------------------------------------------------------- #
# constraint checks — each appends ConditionResults to the accumulator
# --------------------------------------------------------------------------- #

class _Accum:
    __slots__ = ("passed", "failed", "unknown", "invalid")

    def __init__(self) -> None:
        self.passed: List[str] = []
        self.failed: List[ConditionResult] = []
        self.unknown: List[ConditionResult] = []
        self.invalid: bool = False

    def ok(self, cond: str) -> None:
        self.passed.append(cond)

    def fail(self, cond: str, reason: EliminationReason, crit: Criticality, detail: str = "") -> None:
        self.failed.append(ConditionResult(condition=cond, verdict=Verdict.FAIL,
                                           reason=reason.value, criticality=crit, detail=detail))

    def unk(self, cond: str, reason: EliminationReason, crit: Criticality, detail: str = "") -> None:
        self.unknown.append(ConditionResult(condition=cond, verdict=Verdict.UNKNOWN,
                                            reason=reason.value, criticality=crit, detail=detail))


def _subset_missing(required, available) -> List[str]:
    have = set(available or ())
    return [r for r in (required or ()) if r not in have]


def _strongest_required_rank(role: WorkflowRoleRequirement, enterprise: EnterpriseAgentPolicy,
                             policy: EligibilityPolicy) -> int:
    classes = set(role.required_evidence_classes) | set(enterprise.required_evidence_classes)
    rank = max((_EVIDENCE_RANK.get(c.upper(), 0) for c in classes), default=0)
    if rank == 0 and policy.require_measured_or_observed_for_hard:
        rank = 2  # MEASURED
    if rank == 0:
        rank = 1  # DECLARED acceptable
    return rank


def evaluate_agent_eligibility(
    role: WorkflowRoleRequirement,
    profile: AgentProfile,
    snapshot: AgentRegistrySnapshot,
    enterprise_policy: EnterpriseAgentPolicy,
    eligibility_policy: EligibilityPolicy,
    logical_time: float,
) -> AgentEligibilityResult:
    """Evaluate one role × agent pair deterministically, with full accounting."""
    acc = _Accum()
    now = logical_time
    ev = snapshot.evidence_set()

    def base_result(state: EligibilityState) -> AgentEligibilityResult:
        reasons: List[str] = []
        for cr in acc.failed:
            if cr.reason not in reasons:
                reasons.append(cr.reason)
        if state is EligibilityState.INELIGIBLE:
            for cr in acc.unknown:
                if cr.reason not in reasons:
                    reasons.append(cr.reason)
        res = AgentEligibilityResult(
            role_id=role.role_id, agent_id=profile.agent_id, agent_version=profile.agent_version,
            state=state, passed_conditions=tuple(acc.passed),
            failed_conditions=tuple(acc.failed), unknown_conditions=tuple(acc.unknown),
            elimination_reasons=tuple(reasons),
            evidence_refs=tuple(sorted({e.evidence_id for e in ev.items
                                        if e.agent_id == profile.agent_id
                                        and e.agent_version == profile.agent_version})),
            policy_refs=(enterprise_policy.policy_id, eligibility_policy.policy_id),
            snapshot_digest=snapshot.snapshot_digest,
            role_fingerprint=role.role_fingerprint,
            profile_fingerprint=profile.profile_fingerprint,
            policy_digest=_combined_policy_digest(enterprise_policy, eligibility_policy),
            evaluated_at=now)
        return stamp_fingerprint(res, "result_fingerprint")  # type: ignore[return-value]

    checks = {
        "input_integrity": lambda: _check_input_integrity(acc, role, profile, snapshot),
        "pinned_versions": lambda: _check_pinned_versions(acc, role, profile),
        "agent_status_and_version": lambda: _check_status(acc, profile, enterprise_policy, now),
        "capability_presence": lambda: _check_capability_presence(acc, role, profile),
        "capability_evidence": lambda: _check_capability_evidence(
            acc, role, profile, snapshot, enterprise_policy, eligibility_policy, now),
        "input_output_contract": lambda: _check_contracts(acc, role, profile),
        "tools": lambda: _check_tools(acc, role, profile, enterprise_policy),
        "provider": lambda: _check_provider(acc, role, profile, enterprise_policy),
        "residency_deployment": lambda: _check_residency(acc, role, profile, enterprise_policy),
        "security_audit": lambda: _check_security_audit(acc, role, profile, enterprise_policy),
        "permissions": lambda: _check_permissions(acc, role, profile, enterprise_policy),
        "authority_ceiling": lambda: _check_authority(acc, role, profile, enterprise_policy),
        "hard_limits": lambda: _check_hard_limits(acc, role, profile, enterprise_policy),
    }

    for key in eligibility_policy.evaluation_order:
        fn = checks.get(key)
        if fn is None:
            continue
        fn()
        if acc.invalid:
            return base_result(EligibilityState.INVALID_INPUT)
        if eligibility_policy.short_circuit and acc.failed:
            break

    if acc.invalid:
        return base_result(EligibilityState.INVALID_INPUT)
    if acc.failed:
        return base_result(EligibilityState.INELIGIBLE)
    if acc.unknown:
        if enterprise_policy.fail_closed_on_unknown or eligibility_policy.unknown_evidence_fail_closed:
            return base_result(EligibilityState.INELIGIBLE)
        return base_result(EligibilityState.INDETERMINATE)
    return base_result(EligibilityState.ELIGIBLE)


def _combined_policy_digest(enterprise: EnterpriseAgentPolicy, eligibility: EligibilityPolicy) -> str:
    from .canonical import digest
    return digest({"enterprise": enterprise.policy_digest or enterprise.content_digest(),
                   "eligibility": eligibility.policy_digest or eligibility.content_digest()})


def _check_input_integrity(acc, role, profile, snapshot) -> None:
    if not role.role_id or not role.workflow_id:
        acc.fail("input_integrity:role", EliminationReason.MALFORMED_ROLE, Criticality.CRITICAL_GOV)
        acc.invalid = True
        return
    if not profile.agent_id or not profile.agent_version:
        acc.fail("input_integrity:profile", EliminationReason.MALFORMED_PROFILE, Criticality.CRITICAL_GOV)
        acc.invalid = True
        return
    if snapshot.snapshot_digest and snapshot.snapshot_digest != snapshot.logical_digest():
        acc.fail("input_integrity:snapshot", EliminationReason.SNAPSHOT_INTEGRITY_FAILURE,
                 Criticality.CRITICAL_GOV, "snapshot digest does not match recomputed logical digest")
        return
    acc.ok("input_integrity")


def _check_pinned_versions(acc, role, profile) -> None:
    if role.contract_version != CONTRACT_VERSION or profile.contract_version != CONTRACT_VERSION:
        acc.fail("pinned_versions", EliminationReason.MALFORMED_POLICY, Criticality.CRITICAL_GOV,
                 "contract version mismatch")
        acc.invalid = True
        return
    acc.ok("pinned_versions")


def _check_status(acc, profile, enterprise, now) -> None:
    ident = f"{profile.agent_id}@{profile.agent_version}"
    if profile.status is AgentStatus.REVOKED:
        acc.fail("agent_status", EliminationReason.AGENT_VERSION_REVOKED, Criticality.CRITICAL_GOV)
    elif profile.status is AgentStatus.INACTIVE:
        acc.fail("agent_status", EliminationReason.AGENT_INACTIVE, Criticality.CRITICAL_OP)
    else:
        acc.ok("agent_status")
    if profile.is_expired(now):
        acc.fail("profile_validity", EliminationReason.PROFILE_EXPIRED, Criticality.CRITICAL_OP)
    else:
        acc.ok("profile_validity")
    if ident in set(enterprise.forbidden_agent_versions):
        acc.fail("agent_version", EliminationReason.AGENT_VERSION_NOT_APPROVED, Criticality.CRITICAL_GOV,
                 "agent version explicitly forbidden")
    elif enterprise.approved_agent_versions and ident not in set(enterprise.approved_agent_versions):
        acc.fail("agent_version", EliminationReason.AGENT_VERSION_NOT_APPROVED, Criticality.CRITICAL_GOV,
                 "agent version not in approved set")
    else:
        acc.ok("agent_version")


def _agent_claims(profile) -> set:
    return (set(profile.declared_capability_ids())
            | set(profile.measured_capabilities) | set(profile.observed_capabilities))


def _check_capability_presence(acc, role, profile) -> None:
    claims = _agent_claims(profile)
    for cap in role.required_capabilities:
        if cap in claims:
            acc.ok(f"capability_presence:{cap}")
        else:
            acc.fail(f"capability_presence:{cap}", EliminationReason.MISSING_REQUIRED_CAPABILITY,
                     Criticality.CRITICAL_OP, f"agent does not claim capability {cap!r}")


def _check_capability_evidence(acc, role, profile, snapshot, enterprise, policy, now) -> None:
    ev = snapshot.evidence_set()
    claims = _agent_claims(profile)
    required_rank = _strongest_required_rank(role, enterprise, policy)
    for cap in role.required_capabilities:
        if cap not in claims:
            continue  # already failed on presence
        cond = f"capability_evidence:{cap}"
        all_items = ev.for_capability(profile.agent_id, profile.agent_version, cap)
        best = ev.best_class(profile.agent_id, profile.agent_version, cap, now)
        if best is None:
            # any evidence at all? distinguish expired vs version-mismatch vs declared-only vs unknown
            any_version = [e for e in ev.items if e.capability_id == cap
                           and e.agent_id == profile.agent_id
                           and e.agent_version != profile.agent_version]
            if all_items and all(e.is_expired(now) for e in all_items):
                acc.fail(cond, EliminationReason.CAPABILITY_EVIDENCE_EXPIRED, Criticality.CRITICAL_OP,
                         "all matching evidence expired")
            elif any_version and not all_items:
                acc.fail(cond, EliminationReason.CAPABILITY_EVIDENCE_VERSION_MISMATCH,
                         Criticality.CRITICAL_OP, "evidence exists only for a different agent version")
            elif required_rank >= 2:
                # declared-only claim, but measured/observed required
                acc.fail(cond, EliminationReason.DECLARED_ONLY_WHEN_MEASURED_REQUIRED,
                         Criticality.CRITICAL_OP,
                         "no measured/observed evidence for a hard requirement")
            elif policy.unknown_evidence_fail_closed:
                acc.unk(cond, EliminationReason.UNKNOWN_REQUIRED_EVIDENCE, Criticality.CRITICAL_OP,
                        "no evidence and none required class satisfiable")
            else:
                acc.ok(cond)
            continue
        best_rank = _EVIDENCE_RANK[best.value]
        if best_rank < required_rank:
            reason = (EliminationReason.DECLARED_ONLY_WHEN_MEASURED_REQUIRED
                      if best is EvidenceClass.DECLARED
                      else EliminationReason.CAPABILITY_EVIDENCE_INSUFFICIENT)
            acc.fail(cond, reason, Criticality.CRITICAL_OP,
                     f"best evidence class {best.value} below required rank {required_rank}")
        else:
            acc.ok(cond)


def _check_contracts(acc, role, profile) -> None:
    miss_in = _subset_missing(role.input_contract_refs, profile.input_contracts)
    if miss_in:
        acc.fail("input_contract", EliminationReason.INPUT_CONTRACT_INCOMPATIBLE, Criticality.CRITICAL_OP,
                 f"unsatisfied input contracts: {miss_in}")
    else:
        acc.ok("input_contract")
    miss_out = _subset_missing(role.output_contract_refs, profile.output_contracts)
    if miss_out:
        acc.fail("output_contract", EliminationReason.OUTPUT_CONTRACT_INCOMPATIBLE, Criticality.CRITICAL_OP,
                 f"unsatisfied output contracts: {miss_out}")
    else:
        acc.ok("output_contract")


def _check_tools(acc, role, profile, enterprise) -> None:
    forbidden = set(enterprise.forbidden_tools) | set(role.prohibited_tools)
    for tool in role.required_tools:
        if tool in forbidden:
            acc.fail(f"tool:{tool}", EliminationReason.PROHIBITED_TOOL_REQUIRED, Criticality.CRITICAL_GOV,
                     "role requires a prohibited tool")
        elif tool not in set(profile.supported_tools):
            acc.fail(f"tool:{tool}", EliminationReason.REQUIRED_TOOL_UNAVAILABLE, Criticality.CRITICAL_OP,
                     "agent does not support a required tool")
        elif enterprise.allowed_tools and tool not in set(enterprise.allowed_tools):
            acc.fail(f"tool:{tool}", EliminationReason.REQUIRED_TOOL_UNAVAILABLE, Criticality.CRITICAL_GOV,
                     "required tool not in the enterprise allow-list")
        else:
            acc.ok(f"tool:{tool}")


def _check_provider(acc, role, profile, enterprise) -> None:
    p = profile.provider_id
    if p in set(enterprise.forbidden_providers):
        acc.fail("provider", EliminationReason.PROVIDER_FORBIDDEN, Criticality.CRITICAL_GOV)
    elif enterprise.allowed_providers and p not in set(enterprise.allowed_providers):
        acc.fail("provider", EliminationReason.PROVIDER_NOT_APPROVED, Criticality.CRITICAL_GOV,
                 "provider not in enterprise allow-list")
    elif role.provider_constraints and p not in set(role.provider_constraints):
        acc.fail("provider", EliminationReason.PROVIDER_NOT_APPROVED, Criticality.CRITICAL_OP,
                 "provider not permitted by role")
    else:
        acc.ok("provider")


def _check_residency(acc, role, profile, enterprise) -> None:
    r = profile.residency
    ok = True
    if enterprise.required_residencies and r not in set(enterprise.required_residencies):
        ok = False
    if enterprise.allowed_residencies and r not in set(enterprise.allowed_residencies):
        ok = False
    if role.residency_constraints and r not in set(role.residency_constraints):
        ok = False
    if ok:
        acc.ok("residency")
    else:
        acc.fail("residency", EliminationReason.RESIDENCY_MISMATCH, Criticality.CRITICAL_GOV,
                 f"agent residency {r!r} not permitted")
    d = profile.deployment_environment
    dok = True
    if enterprise.allowed_deployment_environments and d not in set(enterprise.allowed_deployment_environments):
        dok = False
    if role.deployment_constraints and d not in set(role.deployment_constraints):
        dok = False
    if dok:
        acc.ok("deployment")
    else:
        acc.fail("deployment", EliminationReason.DEPLOYMENT_ENVIRONMENT_MISMATCH, Criticality.CRITICAL_GOV,
                 f"deployment environment {d!r} not permitted")


def _check_security_audit(acc, role, profile, enterprise) -> None:
    required_sec = max(role.required_security_classification, enterprise.minimum_security_classification)
    if profile.security_classification < required_sec:
        acc.fail("security_classification", EliminationReason.SECURITY_CLASSIFICATION_INSUFFICIENT,
                 Criticality.CRITICAL_GOV,
                 f"security {profile.security_classification} < required {required_sec}")
    else:
        acc.ok("security_classification")
    required_audit = set(role.required_audit_capabilities) | set(enterprise.required_audit_capabilities)
    missing = _subset_missing(sorted(required_audit), profile.audit_capabilities)
    if missing:
        acc.fail("audit_capability", EliminationReason.AUDIT_CAPABILITY_INSUFFICIENT, Criticality.CRITICAL_GOV,
                 f"missing audit capabilities: {missing}")
    else:
        acc.ok("audit_capability")


def _check_permissions(acc, role, profile, enterprise) -> None:
    scope = set(enterprise.maximum_permission_scope)
    prohibited = set(role.prohibited_permissions)
    requested = set(profile.requested_permissions)
    if prohibited & requested:
        acc.fail("permissions", EliminationReason.PERMISSION_REQUIREMENT_EXCEEDS_POLICY,
                 Criticality.CRITICAL_GOV, f"agent requests role-prohibited permissions: "
                 f"{sorted(prohibited & requested)}")
        return
    if scope:
        over = (requested | set(role.required_permissions)) - scope
        if over:
            acc.fail("permissions", EliminationReason.PERMISSION_REQUIREMENT_EXCEEDS_POLICY,
                     Criticality.CRITICAL_GOV, f"permissions exceed enterprise scope: {sorted(over)}")
            return
    acc.ok("permissions")


def _check_authority(acc, role, profile, enterprise) -> None:
    ceilings = [c for c in (role.authority_ceiling, enterprise.maximum_authority_scope) if c > 0]
    if ceilings:
        ceiling = min(ceilings)
        if profile.maximum_authority_scope > ceiling:
            acc.fail("authority_ceiling", EliminationReason.AUTHORITY_REQUIREMENT_EXCEEDS_CEILING,
                     Criticality.CRITICAL_GOV,
                     f"agent authority {profile.maximum_authority_scope} > ceiling {ceiling}")
            return
    acc.ok("authority_ceiling")


def _hard_limit(acc, cond, metric, limit, reason, higher_is_bad, fail_closed) -> None:
    if limit is None:
        acc.ok(cond)
        return
    if metric is None:
        if fail_closed:
            acc.unk(cond, EliminationReason.UNKNOWN_REQUIRED_EVIDENCE, Criticality.CRITICAL_OP,
                    "hard limit set but agent has no evidence for the metric")
        else:
            acc.ok(cond)
        return
    breached = metric > limit if higher_is_bad else metric < limit
    if breached:
        acc.fail(cond, reason, Criticality.CRITICAL_OP, f"metric {metric} breaches limit {limit}")
    else:
        acc.ok(cond)


def _check_hard_limits(acc, role, profile, enterprise) -> None:
    cost_limit = _min_opt(role.maximum_cost_constraint, enterprise.maximum_cost_hard_limit)
    lat_limit = _min_opt(role.maximum_latency_constraint, enterprise.maximum_latency_hard_limit)
    q_floor = _max_opt(role.minimum_quality_constraint, enterprise.minimum_quality_hard_limit)
    fc = enterprise.fail_closed_on_unknown
    _hard_limit(acc, "cost_hard_limit", profile.cost_evidence, cost_limit,
                EliminationReason.COST_HARD_LIMIT_EXCEEDED, True, fc)
    _hard_limit(acc, "latency_hard_limit", profile.latency_evidence, lat_limit,
                EliminationReason.LATENCY_HARD_LIMIT_EXCEEDED, True, fc)
    _hard_limit(acc, "quality_floor", profile.quality_evidence, q_floor,
                EliminationReason.QUALITY_FLOOR_NOT_MET, False, fc)


def _min_opt(a, b):
    vals = [v for v in (a, b) if v is not None]
    return min(vals) if vals else None


def _max_opt(a, b):
    vals = [v for v in (a, b) if v is not None]
    return max(vals) if vals else None


# --------------------------------------------------------------------------- #
# registry- and workflow-level evaluation
# --------------------------------------------------------------------------- #

def evaluate_registry_for_role(
    role: WorkflowRoleRequirement,
    snapshot: AgentRegistrySnapshot,
    enterprise_policy: EnterpriseAgentPolicy,
    eligibility_policy: EligibilityPolicy,
    logical_time: float,
) -> RoleEligibilityReport:
    """Evaluate every agent in the snapshot for one role (total agent accounting)."""
    profiles = sorted(snapshot.agent_profiles, key=lambda p: p.identity)
    results = tuple(
        evaluate_agent_eligibility(role, p, snapshot, enterprise_policy, eligibility_policy, logical_time)
        for p in profiles)
    eligible = tuple(f"{r.agent_id}@{r.agent_version}" for r in results
                     if r.state is EligibilityState.ELIGIBLE)
    eliminated = tuple(f"{r.agent_id}@{r.agent_version}" for r in results
                       if r.state in (EligibilityState.INELIGIBLE, EligibilityState.INVALID_INPUT))
    indeterminate = tuple(f"{r.agent_id}@{r.agent_version}" for r in results
                          if r.state is EligibilityState.INDETERMINATE)
    report = RoleEligibilityReport(
        role_id=role.role_id, workflow_id=role.workflow_id,
        snapshot_digest=snapshot.snapshot_digest,
        enterprise_policy_digest=enterprise_policy.policy_digest,
        eligibility_policy_digest=eligibility_policy.policy_digest,
        evaluated_at=logical_time, results=results,
        eligible_agent_ids=eligible, eliminated_agent_ids=eliminated,
        indeterminate_agent_ids=indeterminate,
        outcome=("HAS_ELIGIBLE_AGENT" if eligible else NO_ELIGIBLE_AGENT))
    return stamp_fingerprint(report, "report_fingerprint")  # type: ignore[return-value]


def explain_role_report(report: RoleEligibilityReport) -> EligibilityExplanation:
    """Produce a deterministic explanation from a role report."""
    eliminated: List[Tuple[str, Tuple[str, ...]]] = []
    for r in report.results:
        if r.state in (EligibilityState.INELIGIBLE, EligibilityState.INVALID_INPUT):
            eliminated.append((f"{r.agent_id}@{r.agent_version}", tuple(r.elimination_reasons)))
    narrative = [
        f"role {report.role_id}: {report.outcome}",
        f"evaluated {len(report.results)} agent(s); "
        f"{len(report.eligible_agent_ids)} eligible, {len(eliminated)} eliminated, "
        f"{len(report.indeterminate_agent_ids)} indeterminate",
    ]
    for agent, reasons in eliminated:
        narrative.append(f"  - {agent} eliminated: {', '.join(reasons) or 'unspecified'}")
    return EligibilityExplanation(
        role_id=report.role_id, outcome=report.outcome,
        eligible=report.eligible_agent_ids, eliminated=tuple(eliminated),
        indeterminate=report.indeterminate_agent_ids, narrative=tuple(narrative))


def build_replay_record(
    role: WorkflowRoleRequirement, report: RoleEligibilityReport,
    enterprise_policy: EnterpriseAgentPolicy, eligibility_policy: EligibilityPolicy,
    logical_time: float,
) -> EligibilityReplayRecord:
    rec = EligibilityReplayRecord(
        role_id=role.role_id, role_fingerprint=role.role_fingerprint,
        snapshot_digest=report.snapshot_digest,
        enterprise_policy_digest=enterprise_policy.policy_digest,
        eligibility_policy_digest=eligibility_policy.policy_digest,
        logical_time=logical_time,
        result_fingerprints=tuple(r.result_fingerprint for r in report.results),
        report_fingerprint=report.report_fingerprint)
    return stamp_fingerprint(rec, "replay_fingerprint")  # type: ignore[return-value]


def evaluate_workflow_eligibility(
    adaptation_result,
    snapshot: AgentRegistrySnapshot,
    enterprise_policy: EnterpriseAgentPolicy,
    eligibility_policy: EligibilityPolicy,
    logical_time: float,
) -> WorkflowEligibilityResult:
    """Evaluate every AI-agent-eligible role in an adaptation against the snapshot."""
    reports: List[RoleEligibilityReport] = []
    explanations: List[EligibilityExplanation] = []
    replays: List[EligibilityReplayRecord] = []
    for role in sorted(adaptation_result.role_requirements, key=lambda r: r.role_id):
        report = evaluate_registry_for_role(role, snapshot, enterprise_policy,
                                            eligibility_policy, logical_time)
        reports.append(report)
        explanations.append(explain_role_report(report))
        replays.append(build_replay_record(role, report, enterprise_policy,
                                            eligibility_policy, logical_time))
    result = WorkflowEligibilityResult(
        workflow_identity=adaptation_result.workflow_identity,
        adaptation_fingerprint=adaptation_result.adaptation_fingerprint,
        snapshot_digest=snapshot.snapshot_digest,
        enterprise_policy_digest=enterprise_policy.policy_digest,
        eligibility_policy_digest=eligibility_policy.policy_digest,
        logical_time=logical_time,
        reports=tuple(reports), explanations=tuple(explanations),
        replay_records=tuple(replays))
    return stamp_fingerprint(result, "workflow_fingerprint")  # type: ignore[return-value]


__all__ = [
    "ConditionResult",
    "AgentEligibilityResult",
    "RoleEligibilityReport",
    "EligibilityExplanation",
    "EligibilityReplayRecord",
    "WorkflowEligibilityResult",
    "evaluate_agent_eligibility",
    "evaluate_registry_for_role",
    "explain_role_report",
    "build_replay_record",
    "evaluate_workflow_eligibility",
]
