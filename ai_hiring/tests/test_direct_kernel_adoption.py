"""Phase 5C — Direct Kernel Adoption and Compatibility-Surface Cleanup.

Proves that AI Hiring now consumes the Decision Governance kernel
(``decision_governance``) *directly*:

* the canonical composition root lives in ``applications.ai_hiring.platform`` and
  imports the kernel directly (no ``ai_hiring.*`` compatibility shim);
* the dependency direction ``applications.ai_hiring`` → ``domains.hiring`` →
  ``decision_governance`` holds, and the reverse never does;
* the subject-scope policy fields expose canonical ``subject_id`` / ``subject_ids``
  aliases with compatibility-first serialization;
* the audit catalog is partitioned into kernel / domain / legacy namespaces
  without renaming any value, and the neutral governance lifecycle emits only
  kernel events;
* the hiring error taxonomy has a canonical ``domains.hiring.errors`` surface;
* every legacy ``ai_hiring.*`` path still resolves to the identical objects.
"""

from __future__ import annotations

import ast
import pathlib
from typing import Optional

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# The pure DGM-kernel compatibility-shim module paths under ``ai_hiring``.
# Importing a *kernel concept* through one of these is the thing Phase 5C
# eliminates from active implementation code. (Real hiring modules that happen
# to live under ai_hiring — e.g. ``ai_hiring.services.evaluation_service`` — are
# deliberately NOT in this set.)
KERNEL_SHIM_PREFIXES = (
    "ai_hiring.decision_cases",
    "ai_hiring.action_requests",
    "ai_hiring.executions",
    "ai_hiring.services.decision_case_service",
    "ai_hiring.services.case_recommendation_service",
    "ai_hiring.services.case_decision_service",
    "ai_hiring.services.case_validation_service",
    "ai_hiring.services.action_request_service",
    "ai_hiring.services.action_request_validation_service",
    "ai_hiring.services.cer_binding_service",
    "ai_hiring.services.action_authorization_service",
    "ai_hiring.services.execution_service",
    "ai_hiring.services.execution_validation_service",
    "ai_hiring.services.reconciliation_service",
    "ai_hiring.services.compensation_service",
    "ai_hiring.services.audit_service",
    "ai_hiring.repositories.decision_case_repository",
    "ai_hiring.repositories.action_request_repository",
    "ai_hiring.repositories.execution_repository",
    "ai_hiring.policies.evidence_access_policy",
)


def _module_name_of(path: pathlib.Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _iter_py(*roots: str):
    for root in roots:
        for p in (REPO_ROOT / root).rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            yield p


def _absolute_import_targets(path: pathlib.Path) -> list[tuple[str, int]]:
    """Every module a file imports from, resolving relative imports to absolute."""
    tree = ast.parse(path.read_text(), filename=str(path))
    module_name = _module_name_of(path)
    pkg_parts = module_name.split(".")
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                target = node.module or ""
            else:
                base = pkg_parts[: len(pkg_parts) - node.level]
                target = ".".join(base + ([node.module] if node.module else []))
            out.append((target, node.lineno))
    return out


def _module_level_import_targets(path: pathlib.Path) -> list[tuple[str, int]]:
    """Only the top-level (module-scope) imports of a file."""
    tree = ast.parse(path.read_text(), filename=str(path))
    module_name = _module_name_of(path)
    pkg_parts = module_name.split(".")
    out: list[tuple[str, int]] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                target = node.module or ""
            else:
                base = pkg_parts[: len(pkg_parts) - node.level]
                target = ".".join(base + ([node.module] if node.module else []))
            out.append((target, node.lineno))
    return out


# --- Dependency-boundary checker -------------------------------------------

def test_kernel_never_imports_the_domain_or_application():
    """decision_governance must not import ai_hiring / domains / applications."""
    forbidden = ("ai_hiring", "domains", "applications")
    violations = []
    for path in _iter_py("decision_governance"):
        for target, lineno in _absolute_import_targets(path):
            if target.split(".")[0] in forbidden:
                violations.append(f"{_module_name_of(path)}:{lineno} -> {target}")
    assert not violations, "kernel imports upward:\n" + "\n".join(violations)


def test_domains_never_import_applications():
    violations = []
    for path in _iter_py("domains"):
        for target, lineno in _absolute_import_targets(path):
            if target.split(".")[0] == "applications":
                violations.append(f"{_module_name_of(path)}:{lineno} -> {target}")
    assert not violations, "domain imports application:\n" + "\n".join(violations)


def test_canonical_packages_do_not_use_kernel_shims():
    """applications.* and domains.* must adopt the kernel directly, never via a
    kernel-compat shim under ai_hiring."""
    violations = []
    for path in _iter_py("applications", "domains"):
        for target, lineno in _module_level_import_targets(path):
            if any(target == p or target.startswith(p + ".") for p in KERNEL_SHIM_PREFIXES):
                violations.append(f"{_module_name_of(path)}:{lineno} -> {target}")
    assert not violations, "canonical code uses kernel shims:\n" + "\n".join(violations)


def test_api_facades_adopt_the_kernel_directly():
    """The hiring API facades import governance concepts from the kernel, not the
    ai_hiring compat shims."""
    violations = []
    for path in _iter_py("ai_hiring/api"):
        for target, lineno in _module_level_import_targets(path):
            if any(target == p or target.startswith(p + ".") for p in KERNEL_SHIM_PREFIXES):
                violations.append(f"{_module_name_of(path)}:{lineno} -> {target}")
    assert not violations, "api facade uses kernel shims:\n" + "\n".join(violations)


def test_composition_root_imports_only_kernel_and_domain_at_module_scope():
    root = REPO_ROOT / "applications" / "ai_hiring" / "platform.py"
    bad = []
    for target, lineno in _module_level_import_targets(root):
        top = target.split(".")[0]
        if top in ("decision_governance", "domains", "dataclasses", "__future__", "typing"):
            continue
        bad.append(f"{lineno} -> {target}")
    assert not bad, "composition root has non-kernel/domain module-scope imports:\n" + "\n".join(bad)


# --- Canonical composition root --------------------------------------------

def test_composition_root_is_canonical_and_reexported():
    import ai_hiring
    import applications.ai_hiring as app
    import applications.ai_hiring.platform as platform

    assert ai_hiring.HiringPlatform is platform.HiringPlatform
    assert app.HiringPlatform is platform.HiringPlatform
    assert ai_hiring.build_in_memory_platform is platform.build_in_memory_platform
    assert app.build_in_memory_platform is platform.build_in_memory_platform
    # The canonical class lives under applications.ai_hiring.platform.
    assert platform.HiringPlatform.__module__ == "applications.ai_hiring.platform"


def test_legacy_and_canonical_facades_wire_identically():
    import ai_hiring
    import applications.ai_hiring as app

    p_legacy = ai_hiring.build_in_memory_platform()
    p_canonical = app.build_in_memory_platform()
    assert type(p_legacy) is type(p_canonical)
    # Same wiring: each attribute's service/repository type matches.
    for field in vars(p_legacy):
        assert type(getattr(p_legacy, field)) is type(getattr(p_canonical, field)), field


def test_platform_wires_governance_from_the_kernel():
    import ai_hiring

    p = ai_hiring.build_in_memory_platform()
    # Governance services/repositories are kernel-owned.
    for svc in (
        p.decision_case_service, p.case_recommendation_service, p.case_decision_service,
        p.case_validation_service, p.action_request_service, p.cer_binding_service,
        p.action_authorization_service, p.execution_service, p.reconciliation_service,
        p.compensation_service,
    ):
        assert type(svc).__module__.startswith("decision_governance."), type(svc).__module__
    assert type(p.audit_service).__module__.startswith("decision_governance.")
    for repo in (p.decision_case_repo, p.action_request_repo, p.execution_repo):
        assert type(repo).__module__.startswith("decision_governance."), type(repo).__module__
    # Hiring services remain hiring-owned.
    for svc in (p.evaluation_service, p.assessment_service, p.rubric_service):
        assert type(svc).__module__.startswith("ai_hiring."), type(svc).__module__


# --- Subject-scope naming aliases ------------------------------------------

def test_subject_scope_aliases_on_access_request():
    from decision_governance.policy import AccessRequest, Permission
    from decision_governance.errors import DomainValidationError

    legacy = AccessRequest("p", "t", Permission.EVIDENCE_READ, candidate_id="c1")
    assert legacy.candidate_id == "c1" and legacy.subject_id == "c1"

    canonical = AccessRequest("p", "t", Permission.EVIDENCE_READ, subject_id="c2")
    assert canonical.candidate_id == "c2" and canonical.subject_id == "c2"

    agree = AccessRequest("p", "t", Permission.EVIDENCE_READ, candidate_id="x", subject_id="x")
    assert agree.subject_id == "x"

    with pytest.raises(DomainValidationError):
        AccessRequest("p", "t", Permission.EVIDENCE_READ, candidate_id="x", subject_id="y")


def test_subject_scope_aliases_on_access_grant():
    from decision_governance.policy import AccessGrant, Permission
    from decision_governance.errors import DomainValidationError

    legacy = AccessGrant("p", "t", frozenset({Permission.EVIDENCE_READ}),
                         candidate_ids=frozenset({"a"}))
    assert legacy.candidate_ids == frozenset({"a"}) == legacy.subject_ids

    canonical = AccessGrant("p", "t", frozenset({Permission.EVIDENCE_READ}),
                            subject_ids=frozenset({"b"}))
    assert canonical.candidate_ids == frozenset({"b"}) == canonical.subject_ids

    with pytest.raises(DomainValidationError):
        AccessGrant("p", "t", frozenset(), candidate_ids=frozenset({"x"}),
                    subject_ids=frozenset({"y"}))


def test_subject_scope_serialization_is_compatibility_first():
    """Serialized form keeps the historical field name — no new ``subject_*`` key."""
    from dataclasses import asdict, fields
    from decision_governance.policy import AccessGrant, AccessRequest, Permission

    g = AccessGrant("p", "t", frozenset({Permission.EVIDENCE_READ}),
                    subject_ids=frozenset({"b"}))
    assert {f.name for f in fields(g)} >= {"candidate_ids"}
    assert "subject_ids" not in asdict(g)
    assert asdict(g)["candidate_ids"] == frozenset({"b"})

    r = AccessRequest("p", "t", Permission.EVIDENCE_READ, subject_id="c2")
    assert "subject_id" not in asdict(r)
    assert asdict(r)["candidate_id"] == "c2"


def test_subject_scope_authorization_unchanged():
    """Scoping still works whichever spelling built the grant/request."""
    from decision_governance.policy import (
        AccessGrant, AccessRequest, EvidenceAccessPolicy, GrantStore, Permission)

    store = GrantStore()
    store.add(AccessGrant("p", "t", frozenset({Permission.EVIDENCE_READ}),
                          subject_ids=frozenset({"s1"})))
    policy = EvidenceAccessPolicy(store)
    assert policy.authorize(
        AccessRequest("p", "t", Permission.EVIDENCE_READ, subject_id="s1")).allowed
    assert not policy.authorize(
        AccessRequest("p", "t", Permission.EVIDENCE_READ, subject_id="s2")).allowed


# --- Audit namespace partitioning ------------------------------------------

def test_audit_partition_is_total_and_disjoint():
    from decision_governance.audit import (
        AuditEventType, DOMAIN_EVENTS, KERNEL_EVENTS, LEGACY_EVENTS)
    allm = frozenset(AuditEventType)
    assert KERNEL_EVENTS | LEGACY_EVENTS | DOMAIN_EVENTS == allm
    assert not (KERNEL_EVENTS & LEGACY_EVENTS)
    assert not (KERNEL_EVENTS & DOMAIN_EVENTS)
    assert not (LEGACY_EVENTS & DOMAIN_EVENTS)


def test_hiring_events_disjoint_from_kernel():
    from decision_governance.audit import KERNEL_EVENTS
    from domains.hiring.audit import HIRING_EVENTS
    assert HIRING_EVENTS
    assert not (HIRING_EVENTS & KERNEL_EVENTS)


def test_audit_values_are_not_renamed():
    """Namespace partitioning must not rename any event value."""
    from decision_governance.audit import AuditEventType
    for member in AuditEventType:
        assert member.value == member.name


def _neutral_linked_records(tenant, subject):
    from decision_governance.ports.linked_record import FINALIZED_STATUS, LinkedRecordSnapshot

    class _NLR:
        def get_record(self, *, tenant_id, record_type, record_id, version=None
                       ) -> Optional["LinkedRecordSnapshot"]:
            return LinkedRecordSnapshot(
                record_type=record_type, record_id=record_id, version=version or 1,
                tenant_id=tenant, status=FINALIZED_STATUS, subject_ref=subject)
    return _NLR()


def test_neutral_governance_lifecycle_emits_only_kernel_events():
    """The kernel governance chain — run with no hiring imports — writes only
    KERNEL-namespace audit events (never a hiring/legacy event)."""
    from decision_governance.audit import (
        AuditService, InMemoryAuditRepository, audit_namespace, AuditNamespace)
    from decision_governance.identity import StaticIdentityProvider
    from decision_governance.policy import (
        AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
    from decision_governance.repositories import (
        InMemoryActionRequestRepository, InMemoryDecisionCaseRepository,
        InMemoryExecutionRepository)
    from decision_governance.services import (
        ActionAuthorizationService, ActionRequestService,
        ActionRequestValidationService, CaseValidationService, CERBindingService,
        DecisionCaseService, ExecutionService, ExecutionValidationService,
        ReconciliationService)
    from decision_governance.services.case_decision_service import CaseDecisionService
    from decision_governance.decisions import AuthorityContext, AuthorityType, DecisionOutcome
    from decision_governance.actions import (
        ActionMapping, OfflineDeterministicControlPlane, ParameterSchema)
    from decision_governance.execution import (
        BusinessOutcome, Finality, OfflineDeterministicExecutionAdapter, OutcomeSource,
        ReconciliationStatus)
    from decision_governance.vocabulary import ReasonCode

    tenant, subject, actor = "t1", "subj-1", "gov-1"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, tenant, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants)
    audit = AuditService(InMemoryAuditRepository())

    case_repo = InMemoryDecisionCaseRepository()
    ar_repo = InMemoryActionRequestRepository()
    ex_repo = InMemoryExecutionRepository()
    linked = _neutral_linked_records(tenant, subject)

    validation = CaseValidationService(linked)
    cases = DecisionCaseService(case_repo, validation, audit, idp, policy)
    decisions = CaseDecisionService(case_repo, validation, audit, idp, policy)
    ar_validation = ActionRequestValidationService(ar_repo, case_repo)
    actions = ActionRequestService(ar_repo, case_repo, ar_validation, audit, idp, policy)
    cer = CERBindingService(ar_repo, case_repo, audit, idp, policy)
    authz = ActionAuthorizationService(
        ar_repo, OfflineDeterministicControlPlane(), audit, idp, policy)
    ex_validation = ExecutionValidationService(ex_repo, ar_repo)
    adapter = OfflineDeterministicExecutionAdapter()
    execs = ExecutionService(ex_repo, ar_repo, ex_validation, adapter, audit, idp, policy)
    recon = ReconciliationService(ex_repo, adapter, audit, idp, policy)

    case = cases.create_case(tenant_id=tenant, decision_type="approve",
                             subject_ids=(subject,), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id="rec-1",
                          version=1, actor=actor)
    authority = AuthorityContext(authority_id=actor,
                                 authority_type=AuthorityType.HUMAN_APPROVER,
                                 decision_scope="approve")
    decision = decisions.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=authority, decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,))
    mapping = ActionMapping(
        mapping_id="map.adv", version=1, domain_id="generic", decision_type="approve",
        decision_outcome=DecisionOutcome.ADVANCE, permitted_action_type="ADVANCE_STAGE",
        target_system_type="SYS", parameter_schema=ParameterSchema(required_fields=("stage",)))
    actions.publish_action_mapping(mapping, actor=actor, tenant_id=tenant)
    req = actions.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.adv", target_system="SYS",
        created_by=actor, requested_parameters={"stage": "next"})
    actions.validate_action_request(request_id=req.action_request_id, actor=actor)
    cer.bind_cer(request_id=req.action_request_id, actor=actor)
    authz.submit_for_authorization(request_id=req.action_request_id, actor=actor)
    intent = execs.create_execution_intent(
        action_request_id=req.action_request_id, created_by=actor)
    execs.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    recon.record_external_outcome(
        intent_id=intent.execution_intent_id, actor=actor,
        business_outcome=BusinessOutcome.SUCCEEDED,
        observed_parameters={"stage": "next"}, finality=Finality.FINAL,
        source=OutcomeSource.EXTERNAL_CALLBACK)
    result = recon.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    assert result.status is ReconciliationStatus.RECONCILED

    emitted = {e.event_type for e in audit._repo.all()}
    assert emitted, "expected audit events"
    non_kernel = {e for e in emitted if audit_namespace(e) is not AuditNamespace.KERNEL}
    assert not non_kernel, f"neutral lifecycle emitted non-kernel events: {non_kernel}"


# --- Error taxonomy ---------------------------------------------------------

def test_hiring_error_taxonomy_identity():
    import ai_hiring.errors as legacy
    import decision_governance.errors as kernel
    import domains.hiring.errors as canonical

    # Base identity across all three surfaces.
    assert canonical.HiringError is legacy.HiringError is kernel.GovernanceError
    assert canonical.DomainValidationError is kernel.DomainValidationError
    # Hiring families identical between the canonical surface and the legacy one.
    for name in canonical.__all__:
        if name in ("GovernanceError", "DomainValidationError", "HiringError"):
            continue
        assert getattr(canonical, name) is getattr(legacy, name), name
        assert issubclass(getattr(canonical, name), kernel.GovernanceError), name


def test_ai_hiring_errors_exposes_both_families():
    import ai_hiring.errors as legacy
    # Neutral kernel family present…
    assert issubclass(legacy.VersionConflictError, legacy.GovernanceError)
    assert issubclass(legacy.ExecutionError, legacy.GovernanceError)
    # …alongside hiring-specific families.
    assert issubclass(legacy.AssessmentError, legacy.HiringError)
    assert issubclass(legacy.BoundaryViolationError, legacy.HiringError)
