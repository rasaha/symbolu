"""Pilot composition root (Task 104).

Wires the ProviderRegistry, TAP + ActionGate providers (via the pilot config and
scenario policy), the AssertionAssessmentIntegration, the full DGM service set, a
deterministic ExternalExecutionProvider, reconciliation, and a pilot observability
collector. All provider selection flows through the registry and configuration —
scenario handlers never instantiate a provider directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from actiongate_provider.configuration import ActionGateSettings, build_actiongate_provider
from decision_governance.api.audit import AuditService, InMemoryAuditRepository
from decision_governance.api.identity import StaticIdentityProvider
from decision_governance.api.policy import (
    AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
from decision_governance.api.ports import (
    FINALIZED_STATUS, LinkedRecordSnapshot, OfflineDeterministicExecutionAdapter)
from decision_governance.api.repositories import (
    InMemoryActionRequestRepository, InMemoryDecisionCaseRepository,
    InMemoryExecutionRepository)
from decision_governance.api.services import (
    ActionAuthorizationService, ActionRequestService, ActionRequestValidationService,
    CaseDecisionService, CaseRecommendationService, CaseValidationService, CERBindingService,
    DecisionCaseService, ExecutionService, ExecutionValidationService, ReconciliationService)
from governance_providers.api import (
    ActionGovernanceControlPlaneAdapter, AssertionAssessmentIntegration, ProviderKind,
    ProviderRegistry, ResolutionRecord, ResolutionRequest, resolve)
from tap_provider.configuration import TapSettings, build_tap_provider

from ..schemas.scenario import Scenario
from .config import action_provider_id, assertion_provider_id, load_config
from .determinism import make_clock, make_id_factory
from .engines import build_actiongate_engine, build_execution_adapter, build_tap_engine


class _NeutralLinked:
    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version or 1,
            tenant_id="t", status=FINALIZED_STATUS, subject_ref="subject")


@dataclass
class DGMServices:
    cases: DecisionCaseService
    rec: CaseRecommendationService
    dec: CaseDecisionService
    acts: ActionRequestService
    cer: CERBindingService
    authz: ActionAuthorizationService
    exe: ExecutionService
    reconcile: ReconciliationService
    audit: AuditService
    actor: str
    tenant: str

    def audit_events(self) -> list:
        return list(self.audit._repo.all())


class PilotComposition:
    """Everything one scenario needs, wired through the registry + configuration."""

    def __init__(self, scenario: Scenario) -> None:
        self.scenario = scenario
        self.config = load_config()

        tap_id = assertion_provider_id(self.config)
        ag_id = action_provider_id(self.config)

        # providers built from scenario policy but registered under configured ids;
        # the registry owns instantiation, so selection flows through it.
        tap_engine = build_tap_engine(scenario.assertion, scenario.tap_policy)
        ag_engine = build_actiongate_engine(
            scenario.proposed_action.action_type, scenario.action_policy)
        tap_descriptor = build_tap_provider(
            tap_engine, settings=TapSettings(provider_id=tap_id, mode="in_process")).descriptor()
        ag_descriptor = build_actiongate_provider(
            ag_engine, settings=ActionGateSettings(provider_id=ag_id, mode="in_process")
        ).descriptor()

        self.registry = ProviderRegistry()
        self.registry.register(tap_descriptor)
        self.registry.register(ag_descriptor)

        self._id_factory = make_id_factory(scenario.scenario_id)
        self._clock = make_clock(scenario.scenario_id)
        self.execution_adapter: OfflineDeterministicExecutionAdapter = build_execution_adapter(
            scenario.proposed_action.action_type, scenario.execution,
            id_factory=make_id_factory(scenario.scenario_id + ":exec"), clock=self._clock)
        self._resolution: dict[str, ResolutionRecord] = {}

    # --- provider resolution (deterministic, auditable) --------------------

    def resolve_assertion_provider(self):
        provider, record = resolve(
            self.registry, ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
        self._resolution["assertion"] = record
        return provider, record

    def resolve_action_provider(self):
        provider, record = resolve(
            self.registry, ResolutionRequest(ProviderKind.ACTION_GOVERNANCE))
        self._resolution["action"] = record
        return provider, record

    def assertion_integration(self, provider) -> AssertionAssessmentIntegration:
        return AssertionAssessmentIntegration(provider)

    def reevaluate_assertion(self, assertion, tap_policy):
        """Re-evaluate an assertion after human-supplied evidence.

        Builds a fresh registry with a TAP provider from the new policy and
        resolves through it — keeping provider selection registry-disciplined for
        the re-evaluation step, not a raw provider call.
        """
        tap_id = assertion_provider_id(self.config)
        engine = build_tap_engine(assertion, tap_policy)
        descriptor = build_tap_provider(
            engine, settings=TapSettings(provider_id=tap_id, mode="in_process")).descriptor()
        registry = ProviderRegistry()
        registry.register(descriptor)
        resolved, record = resolve(
            registry, ResolutionRequest(ProviderKind.ASSERTION_GOVERNANCE))
        self._resolution["assertion_reevaluation"] = record
        return resolved, record

    def control_plane(self, action_provider) -> ActionGovernanceControlPlaneAdapter:
        return ActionGovernanceControlPlaneAdapter(action_provider)

    # --- DGM service bundle -------------------------------------------------

    def build_dgm(self, control_plane) -> DGMServices:
        t, actor = "t", "gov"
        idp = StaticIdentityProvider(); idp.register_human(actor)
        idp.register_human("reviewer"); idp.register_human("senior")
        grants = GrantStore()
        grants.add(AccessGrant(actor, t, frozenset(Permission)))
        grants.add(AccessGrant("reviewer", t, frozenset(Permission)))
        grants.add(AccessGrant("senior", t, frozenset(Permission)))
        policy = EvidenceAccessPolicy(grants)
        audit = AuditService(InMemoryAuditRepository())
        cr, ar, er = (InMemoryDecisionCaseRepository(), InMemoryActionRequestRepository(),
                      InMemoryExecutionRepository())
        val = CaseValidationService(_NeutralLinked())
        idf, clk = self._id_factory, self._clock
        return DGMServices(
            cases=DecisionCaseService(cr, val, audit, idp, policy, id_factory=idf, clock=clk),
            rec=CaseRecommendationService(cr, val, audit, idp, policy, id_factory=idf, clock=clk),
            dec=CaseDecisionService(cr, val, audit, idp, policy, id_factory=idf, clock=clk),
            acts=ActionRequestService(ar, cr, ActionRequestValidationService(ar, cr),
                                      audit, idp, policy, id_factory=idf, clock=clk),
            cer=CERBindingService(ar, cr, audit, idp, policy, id_factory=idf, clock=clk),
            authz=ActionAuthorizationService(ar, control_plane, audit, idp, policy,
                                             id_factory=idf, clock=clk),
            exe=ExecutionService(er, ar, ExecutionValidationService(er, ar),
                                 self.execution_adapter, audit, idp, policy,
                                 id_factory=idf, clock=clk),
            reconcile=ReconciliationService(er, self.execution_adapter, audit, idp, policy,
                                            id_factory=idf, clock=clk),
            audit=audit, actor=actor, tenant=t)

    # --- observability ------------------------------------------------------

    @property
    def resolution_records(self) -> dict[str, ResolutionRecord]:
        return dict(self._resolution)
