"""Provider conformance kit — validates any populated provider registry.

Domain- and implementation-agnostic: it exercises a registry (containing at least
one provider per kind) across registration, resolution, configuration, capability
reporting, error propagation, version compatibility, lifecycle, and a full
kernel-lifecycle integration through the provider adapters. The same kit will
later validate TAP, ActionGate, and third-party providers without modification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..adapters import (
    AssertionProviderLinkedRecordAdapter,
    AuthorizationProviderControlPlaneAdapter,
    ExecutionProviderExternalSystemAdapter,
)
from ..contracts import LifecycleState
from ..descriptor import ProviderDescriptor
from ..errors import (
    IncompatibleProviderVersionError,
    ProviderConflictError,
    ProviderNotFoundError,
)
from ..metadata import ProviderCapabilities, ProviderKind, ProviderMetadata
from ..registry import ProviderRegistry
from ..resolution import (
    ProviderConfiguration,
    ProviderSelection,
    resolve_configuration,
    resolve_provider,
)


@dataclass(frozen=True)
class CheckResult:
    dimension: str
    name: str
    passed: bool
    detail: str = ""


@dataclass
class ProviderConformanceReport:
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"{ok}/{len(self.results)} provider-conformance checks passed"


def _ok(dim, name, detail=""):
    return CheckResult(dim, name, True, detail)


def _fail(dim, name, detail=""):
    return CheckResult(dim, name, False, detail)


def run_provider_conformance(registry: ProviderRegistry) -> ProviderConformanceReport:
    """Validate a populated registry (one+ provider per kind) across all dimensions."""
    r = ProviderConformanceReport()
    r.results += _registration(registry)
    r.results += _resolution(registry)
    r.results += _configuration(registry)
    r.results += _capability_reporting(registry)
    r.results += _error_propagation(registry)
    r.results += _version_compatibility(registry)
    r.results += _lifecycle(registry)
    r.results += _integration(registry)
    return r


def _registration(registry):
    out = []
    for kind in ProviderKind:
        present = bool(registry.list_descriptors(kind))
        out.append(_ok("registration", f"has:{kind.value}") if present
                   else _fail("registration", f"has:{kind.value}", "no provider registered"))
    try:
        registry.validate()
        out.append(_ok("registration", "registry_valid"))
    except Exception as exc:  # noqa: BLE001
        out.append(_fail("registration", "registry_valid", repr(exc)))
    return out


def _resolution(registry):
    out = []
    for kind in ProviderKind:
        try:
            p = resolve_provider(registry, ProviderSelection(kind))
            out.append(_ok("resolution", f"default:{kind.value}", p.metadata().name))
        except Exception as exc:  # noqa: BLE001
            out.append(_fail("resolution", f"default:{kind.value}", repr(exc)))
        # by name
        descs = registry.list_descriptors(kind)
        if descs:
            name = descs[0].name
            try:
                p = resolve_provider(registry, ProviderSelection(kind, name=name))
                out.append(_ok("resolution", f"named:{kind.value}", name)
                           if p.metadata().name == name
                           else _fail("resolution", f"named:{kind.value}", "wrong provider"))
            except Exception as exc:  # noqa: BLE001
                out.append(_fail("resolution", f"named:{kind.value}", repr(exc)))
    return out


def _configuration(registry):
    selections = tuple(ProviderSelection(k) for k in ProviderKind
                       if registry.list_descriptors(k))
    try:
        resolved = resolve_configuration(registry, ProviderConfiguration(selections))
        ok = set(resolved) == {s.kind for s in selections}
        return [_ok("configuration", "resolve_all") if ok
                else _fail("configuration", "resolve_all", "kinds mismatch")]
    except Exception as exc:  # noqa: BLE001
        return [_fail("configuration", "resolve_all", repr(exc))]


def _capability_reporting(registry):
    out = []
    for d in registry.list_descriptors():
        p = registry.get_provider(d.name)
        caps = p.capabilities()
        good = caps.kind is d.kind and p.metadata().name == d.name
        out.append(_ok("capability", d.name) if good
                   else _fail("capability", d.name, "capability/metadata mismatch"))
    return out


def _error_propagation(registry):
    out = []
    # unknown name → ProviderNotFoundError
    try:
        registry.get_descriptor("does-not-exist")
        out.append(_fail("errors", "not_found", "no error raised"))
    except ProviderNotFoundError:
        out.append(_ok("errors", "not_found"))
    # duplicate registration → ProviderConflictError
    existing = registry.list_descriptors()
    if existing:
        try:
            registry.register(existing[0])
            out.append(_fail("errors", "conflict", "no error raised"))
        except ProviderConflictError:
            out.append(_ok("errors", "conflict"))
    return out


def _version_compatibility(registry):
    out = []
    for d in registry.list_descriptors():
        from ..version import is_kernel_compatible
        out.append(_ok("version", d.name) if is_kernel_compatible(d.metadata.kernel_port_version)
                   else _fail("version", d.name, "incompatible kernel version registered"))
    # an incompatible provider must be rejected
    probe = ProviderRegistry()
    bad = ProviderDescriptor(
        ProviderMetadata(name="bad", version="0.1.0", kind=ProviderKind.ASSERTION,
                         kernel_port_version="99.0.0"),
        ProviderCapabilities(kind=ProviderKind.ASSERTION), factory=lambda: None)
    try:
        probe.register(bad)
        out.append(_fail("version", "reject_incompatible", "incompatible provider accepted"))
    except IncompatibleProviderVersionError:
        out.append(_ok("version", "reject_incompatible"))
    return out


def _lifecycle(registry):
    out = []
    for d in registry.list_descriptors():
        p = registry.get_provider(d.name)
        started = p.health().healthy
        out.append(_ok("lifecycle", f"started:{d.name}") if started
                   else _fail("lifecycle", f"started:{d.name}", "provider not healthy after start"))
    registry.stop_all()
    out.append(_ok("lifecycle", "stop_all"))
    return out


def _integration(registry):
    """Run a full kernel governance lifecycle through the provider adapters."""
    try:
        status, events_ok = _run_kernel_lifecycle(registry)
        out = [
            _ok("integration", "reconciled") if status == "RECONCILED"
            else _fail("integration", "reconciled", f"status={status}"),
            _ok("integration", "kernel_events") if events_ok
            else _fail("integration", "kernel_events", "unexpected audit events"),
        ]
        return out
    except Exception as exc:  # noqa: BLE001
        return [_fail("integration", "lifecycle", repr(exc))]


def _run_kernel_lifecycle(registry):
    from decision_governance.api.audit import (
        AuditEventType, AuditService, InMemoryAuditRepository, audit_namespace, AuditNamespace)
    from decision_governance.api.identity import StaticIdentityProvider
    from decision_governance.api.policy import (
        AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
    from decision_governance.api.repositories import (
        InMemoryActionRequestRepository, InMemoryDecisionCaseRepository,
        InMemoryExecutionRepository)
    from decision_governance.api.services import (
        ActionAuthorizationService, ActionRequestService, ActionRequestValidationService,
        CaseDecisionService, CaseValidationService, CERBindingService, DecisionCaseService,
        ExecutionService, ExecutionValidationService, ReconciliationService)
    from decision_governance.api.contracts import (
        ActionMapping, AuthorityContext, AuthorityType, DecisionOutcome, ParameterSchema)
    from decision_governance.api.vocabulary import ReasonCode

    assertion = registry.get_provider(registry.list_descriptors(ProviderKind.ASSERTION)[0].name)
    authz = registry.get_provider(registry.list_descriptors(ProviderKind.AUTHORIZATION)[0].name)
    execp = registry.get_provider(registry.list_descriptors(ProviderKind.EXECUTION)[0].name)
    linked = AssertionProviderLinkedRecordAdapter(assertion)
    control_plane = AuthorizationProviderControlPlaneAdapter(authz)
    exec_adapter = ExecutionProviderExternalSystemAdapter(execp)

    t, actor = "t", "gov"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, t, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants); audit = AuditService(InMemoryAuditRepository())
    cr, ar, er = (InMemoryDecisionCaseRepository(), InMemoryActionRequestRepository(),
                  InMemoryExecutionRepository())
    val = CaseValidationService(linked)
    cases = DecisionCaseService(cr, val, audit, idp, policy)
    dec = CaseDecisionService(cr, val, audit, idp, policy)
    acts = ActionRequestService(ar, cr, ActionRequestValidationService(ar, cr), audit, idp, policy)
    cer = CERBindingService(ar, cr, audit, idp, policy)
    aauthz = ActionAuthorizationService(ar, control_plane, audit, idp, policy)
    exe = ExecutionService(er, ar, ExecutionValidationService(er, ar), exec_adapter, audit, idp, policy)
    rec = ReconciliationService(er, exec_adapter, audit, idp, policy)

    # The mock assertion provider reports subject_ref="subject"; the case subject
    # must match for the kernel's linked-record subject check.
    case = cases.create_case(tenant_id=t, decision_type="approve",
                             subject_ids=("subject",), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id="a", version=1, actor=actor)
    decision = dec.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=AuthorityContext(authority_id=actor, authority_type=AuthorityType.HUMAN_APPROVER,
                                   decision_scope="approve"),
        decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,))
    acts.publish_action_mapping(
        ActionMapping(mapping_id="m", version=1, domain_id="generic", decision_type="approve",
                      decision_outcome=DecisionOutcome.ADVANCE, permitted_action_type="ACT",
                      target_system_type="SYS", parameter_schema=ParameterSchema(required_fields=("k",))),
        actor=actor, tenant_id=t)
    req = acts.create_action_request(decision_id=decision.decision_id, mapping_id="m",
        target_system="SYS", created_by=actor, requested_parameters={"k": "v"})
    acts.validate_action_request(request_id=req.action_request_id, actor=actor)
    cer.bind_cer(request_id=req.action_request_id, actor=actor)
    aauthz.submit_for_authorization(request_id=req.action_request_id, actor=actor)
    intent = exe.create_execution_intent(action_request_id=req.action_request_id, created_by=actor)
    exe.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    rec.query_external_status(intent_id=intent.execution_intent_id, actor=actor)
    result = rec.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)

    events = {e.event_type for e in audit._repo.all()}
    events_ok = (AuditEventType.EXECUTION_RECONCILED in events
                 and all(audit_namespace(e) is AuditNamespace.KERNEL for e in events))
    return result.status.value, events_ok
